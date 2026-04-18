"""
WecomProvider · 企业微信扫码登录（自建应用，OAuth2）

企微生态企业走这个。**只接受 corp_id 匹配的企微用户**，其它企业的员工扫也登不进。
配合多租户 registry：每个租户装各自的 corp_id，互不干扰。

流程（企业自建应用 + 扫码登录二合一模式 wwlogin）：
  1. 前端跳 https://login.work.weixin.qq.com/wwlogin/sso/login
       ?login_type=CorpApp&appid={corp_id}&agentid={agent_id}
       &redirect_uri={callback}&state={state}
  2. 用户在企微里扫码授权后，302 回 callback?code=xxx&state=xxx&appid=xxx
  3. 后端校验 state → 取 tid → registry 拿对应租户 provider
  4. provider 先拿自己的 access_token（独立于用户 code）：
       GET /cgi-bin/gettoken?corpid={corp_id}&corpsecret={secret}
  5. 用 code 换 userid：
       GET /cgi-bin/auth/getuserinfo?access_token={t}&code={code}
       returns {errcode:0, userid, user_ticket, open_userid, ...}
  6. 如果 userid 非空：确认本企业员工（userid 跨企业不通用）；
     如果只有 open_userid：外部联系人，按租户配置决定拒 or 记录
  7. 校验 allowlist_userids（限定某几个人，可选）
  8. 建 session

Config schema (tenant_config.auth.providers.wecom):
    {
      "corp_id": "wwxxxxxxxxxxxxxxxx",
      "agent_id": "1000002",
      "secret_env": "OME365_WECOM_SECRET",
      "redirect_uri": "https://ome.example.com/auth/wecom/callback",
      "allowlist_userids": ["alice", "bob"],           // 可选
      "reject_external_contacts": true                  // 默认 true，只接受本企业员工
    }
"""
from __future__ import annotations

import os
import time
import secrets
import threading
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import requests

from ..base import User, Session, AuthError, AuthConfigError


class WecomPendingStore:
    """state → tid/next_url；企微回调用。独立表，和 oidc 不冲突。"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._lock, sqlite3.connect(str(self.db_path), isolation_level=None) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS wecom_pending ("
                "  state TEXT PRIMARY KEY,"
                "  tenant_id TEXT NOT NULL,"
                "  next_url TEXT NOT NULL,"
                "  created_at REAL NOT NULL,"
                "  expires_at REAL NOT NULL"
                ")"
            )

    def put(self, state: str, tid: str, next_url: str, ttl_seconds: int = 900) -> None:
        now = datetime.utcnow().timestamp()
        with self._lock, sqlite3.connect(str(self.db_path), isolation_level=None) as c:
            c.execute(
                "INSERT INTO wecom_pending(state, tenant_id, next_url, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (state, tid, next_url, now, now + ttl_seconds),
            )

    def consume(self, state: str) -> Optional[dict]:
        now = datetime.utcnow().timestamp()
        with self._lock, sqlite3.connect(str(self.db_path), isolation_level=None) as c:
            row = c.execute(
                "SELECT tenant_id, next_url, expires_at FROM wecom_pending WHERE state = ?",
                (state,),
            ).fetchone()
            if not row:
                return None
            tid, next_url, exp = row
            c.execute("DELETE FROM wecom_pending WHERE state = ?", (state,))
            if now >= exp:
                return None
            return {"tenant_id": tid, "next_url": next_url}

    def gc(self) -> int:
        now = datetime.utcnow().timestamp()
        with self._lock, sqlite3.connect(str(self.db_path), isolation_level=None) as c:
            cur = c.execute("DELETE FROM wecom_pending WHERE expires_at < ?", (now,))
            return cur.rowcount


class WecomProvider:
    name = "wecom"

    def __init__(self, config: dict | None = None, *, session_store=None, pending_store: WecomPendingStore | None = None, tenant_id: str = "default"):
        self.config = config or {}
        self.session_store = session_store
        self.pending_store = pending_store
        self.tenant_id = self.config.get("tenant_id", tenant_id)

        self.corp_id = self.config.get("corp_id", "")
        self.agent_id = str(self.config.get("agent_id", ""))
        self.secret = os.environ.get(self.config.get("secret_env", ""), "") if self.config.get("secret_env") else self.config.get("secret", "")
        self.redirect_uri = self.config.get("redirect_uri", "")
        self.allowlist_userids = set(self.config.get("allowlist_userids") or [])
        self.reject_external = bool(self.config.get("reject_external_contacts", True))

        # access_token 缓存（企微 7200s 有效，我们缓存 6000s 保险）
        self._access_token = ""
        self._access_token_expires = 0.0
        self._session = requests.Session()

    # ---------- AuthProvider Protocol ----------

    async def authenticate(self, request) -> Optional[User]:
        if self.session_store is None:
            return None
        sid = request.cookies.get("ome365_sid") if hasattr(request, "cookies") else None
        if not sid:
            return None
        u = self.session_store.get_user(sid)
        if u and u.tenant_id != self.tenant_id:
            return None
        return u

    async def login_url(self, redirect_to: str = "/") -> str:
        return f"/auth/wecom/start?next={redirect_to or '/'}"

    async def callback(self, request) -> Optional[Session]:
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code or not state:
            raise AuthError("missing code or state")
        pending = self.pending_store.consume(state) if self.pending_store else None
        if not pending:
            raise AuthError("invalid or expired state")
        if pending["tenant_id"] != self.tenant_id:
            raise AuthError(f"state/tenant mismatch: {pending['tenant_id']} vs {self.tenant_id}")
        userinfo = self._exchange_code(code)
        user = self._build_user(userinfo)
        if not self.session_store:
            raise AuthConfigError("session_store not wired")
        sess = self.session_store.create(user)
        sess.data["_next_url"] = pending["next_url"]
        return sess

    async def logout(self, session_id: str) -> None:
        if self.session_store:
            self.session_store.delete(session_id)

    def healthcheck(self) -> dict:
        issues = []
        if not self.corp_id:
            issues.append("corp_id missing")
        if not self.agent_id:
            issues.append("agent_id missing")
        if not self.secret:
            issues.append(f"secret not resolved (env {self.config.get('secret_env')} empty?)")
        if not self.redirect_uri:
            issues.append("redirect_uri missing")
        return {
            "ok": not issues,
            "provider": "wecom",
            "tenant_id": self.tenant_id,
            "corp_id": self.corp_id,
            "allowlist_size": len(self.allowlist_userids),
            "reject_external": self.reject_external,
            "issues": issues,
        }

    # ---------- 企微专用 API ----------

    def start_url(self, next_url: str = "/") -> str:
        if not (self.corp_id and self.agent_id and self.redirect_uri):
            raise AuthConfigError("wecom not fully configured (corp_id/agent_id/redirect_uri)")
        if self.pending_store is None:
            raise AuthConfigError("pending_store not wired")
        state = secrets.token_urlsafe(24)
        self.pending_store.put(state, self.tenant_id, next_url)
        q = urlencode({
            "login_type": "CorpApp",
            "appid": self.corp_id,
            "agentid": self.agent_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
        })
        return f"https://login.work.weixin.qq.com/wwlogin/sso/login?{q}"

    # ---------- HTTP 细节 ----------

    def _get_access_token(self) -> str:
        """企业 access_token；7200s 有效，缓存 6000s。"""
        if self._access_token and time.time() < self._access_token_expires:
            return self._access_token
        r = self._session.get(
            "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
            params={"corpid": self.corp_id, "corpsecret": self.secret},
            timeout=10,
        )
        d = r.json()
        if d.get("errcode") != 0:
            raise AuthError(f"wecom gettoken failed: {d}")
        self._access_token = d["access_token"]
        self._access_token_expires = time.time() + 6000
        return self._access_token

    def _exchange_code(self, code: str) -> dict:
        tok = self._get_access_token()
        r = self._session.get(
            "https://qyapi.weixin.qq.com/cgi-bin/auth/getuserinfo",
            params={"access_token": tok, "code": code},
            timeout=10,
        )
        d = r.json()
        if d.get("errcode") != 0:
            raise AuthError(f"wecom getuserinfo failed: {d}")
        return d

    def _build_user(self, info: dict) -> User:
        import re
        userid = info.get("userid") or info.get("UserId") or ""
        open_userid = info.get("open_userid") or ""

        # 外部联系人拒绝（没 userid 只有 open_userid）
        if not userid:
            if self.reject_external:
                raise AuthError("external contact not allowed (only internal corp members)")
            # 走 open_userid 路径
            userid = f"ext-{open_userid[:24]}"

        if self.allowlist_userids and userid not in self.allowlist_userids:
            raise AuthError(f"wecom userid '{userid}' not in allowlist")

        uid = re.sub(r"[^a-z0-9_-]", "-", userid.lower())[:32] or "user"
        return User(
            user_id=uid,
            tenant_id=self.tenant_id,
            display_name=userid,  # 企微 userinfo 不含姓名；后续可调 getuser 接口取
            email="",
            roles=["user"],
            provider="wecom",
            provider_uid=userid,
            extra={"wecom": {"userid": userid, "open_userid": open_userid}},
        )
