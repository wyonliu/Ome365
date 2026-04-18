"""
MagicLinkProvider · 邮件一次性登录链接，用于：
- 家庭 / 小团队（无 SSO，但不想每人记密码）
- 内测用户

流程：
1. 用户输入 email → POST /auth/magic/request
2. 服务端查 allowlist；命中则生成 one-time token（随机 32 字节，TTL 15min），存 SQLite
3. 发邮件："点这里登录 https://host/auth/magic/verify?token=xxx&next=..."
4. 用户点链接 → GET /auth/magic/verify → 校验 token 未用未过期 → 建 session → set cookie → redirect next

Config schema（tenant_config.auth.providers.magic_link）:
    {
        "allowlist": ["alice@example.com", "bob@example.com"],
        "users": {                       # 可选：email → {uid, display, roles} 覆盖
            "alice@example.com": {"uid": "alice", "display": "Alice", "roles": ["admin"]}
        },
        "smtp": {
            "host": "smtp.gmail.com",
            "port": 587,
            "username": "ome365-bot@...",
            "password_env": "OME365_SMTP_PASSWORD",
            "from": "Ome365 <noreply@...>",
            "starttls": true
        },
        "token_ttl_minutes": 15,
        "link_base_url": "https://ome.example.com"   # 不填则用 request 推断
    }
"""
from __future__ import annotations

import os
import re
import sqlite3
import secrets
import threading
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from ..base import User, Session, AuthError, AuthConfigError


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class MagicTokenStore:
    """SQLite 里存一次性 token：tokens(token PK, email, expires_at, used_at, created_at)"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._lock, sqlite3.connect(str(self.db_path), isolation_level=None) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS magic_tokens ("
                "  token TEXT PRIMARY KEY,"
                "  email TEXT NOT NULL,"
                "  expires_at REAL NOT NULL,"
                "  used_at REAL,"
                "  created_at REAL NOT NULL"
                ")"
            )

    def create(self, email: str, ttl_minutes: int = 15) -> str:
        tok = secrets.token_urlsafe(32)
        now = datetime.utcnow().timestamp()
        exp = (datetime.utcnow() + timedelta(minutes=ttl_minutes)).timestamp()
        with self._lock, sqlite3.connect(str(self.db_path), isolation_level=None) as c:
            c.execute(
                "INSERT INTO magic_tokens(token, email, expires_at, used_at, created_at) VALUES (?, ?, ?, NULL, ?)",
                (tok, email, exp, now),
            )
        return tok

    def consume(self, token: str) -> Optional[str]:
        """一次性消费。返回 email 或 None。"""
        now = datetime.utcnow().timestamp()
        with self._lock, sqlite3.connect(str(self.db_path), isolation_level=None) as c:
            row = c.execute(
                "SELECT email, expires_at, used_at FROM magic_tokens WHERE token = ?",
                (token,),
            ).fetchone()
            if not row:
                return None
            email, exp, used_at = row
            if used_at is not None:
                return None
            if now >= exp:
                return None
            c.execute("UPDATE magic_tokens SET used_at = ? WHERE token = ?", (now, token))
            return email

    def gc(self) -> int:
        cutoff = (datetime.utcnow() - timedelta(days=1)).timestamp()
        with self._lock, sqlite3.connect(str(self.db_path), isolation_level=None) as c:
            cur = c.execute("DELETE FROM magic_tokens WHERE expires_at < ?", (cutoff,))
            return cur.rowcount


class MagicLinkProvider:
    name = "magic_link"

    def __init__(self, config: dict | None = None, *, session_store=None, token_db_path: Path | None = None):
        self.config = config or {}
        self.session_store = session_store
        self.tenant_id = self.config.get("tenant_id", "default")
        self.allowlist = set(e.lower() for e in self.config.get("allowlist", []))
        self.users_overrides = {
            k.lower(): v for k, v in (self.config.get("users") or {}).items()
        }
        self.smtp_cfg = self.config.get("smtp", {}) or {}
        self.token_ttl = int(self.config.get("token_ttl_minutes", 15))
        self.link_base_url = self.config.get("link_base_url", "")
        db = Path(token_db_path) if token_db_path else Path.home() / ".ome365" / "magic_tokens.db"
        self.tokens = MagicTokenStore(db)

    # ---------- AuthProvider Protocol ----------

    async def authenticate(self, request) -> Optional[User]:
        if self.session_store is None:
            return None
        sid = request.cookies.get("ome365_sid") if hasattr(request, "cookies") else None
        if not sid:
            return None
        u = self.session_store.get_user(sid)
        if u and u.tenant_id != self.tenant_id:
            return None  # 跨租户 session 不承认
        return u

    async def login_url(self, redirect_to: str = "/") -> str:
        return f"/auth/magic?next={redirect_to or '/'}"

    async def callback(self, request) -> Optional[Session]:
        # magic_link 走专用 handler（verify_token），callback 不用
        return None

    async def logout(self, session_id: str) -> None:
        if self.session_store:
            self.session_store.delete(session_id)

    def healthcheck(self) -> dict:
        issues = []
        if not self.allowlist:
            issues.append("allowlist empty — nobody can log in")
        if not self.smtp_cfg.get("host"):
            issues.append("smtp.host missing — can't send magic links")
        if self.smtp_cfg.get("password_env") and not os.environ.get(self.smtp_cfg["password_env"]):
            issues.append(f"smtp password env `{self.smtp_cfg['password_env']}` not set")
        return {"ok": not issues, "provider": "magic_link", "allowlist": list(self.allowlist), "issues": issues}

    # ---------- Magic-link 专用 API ----------

    def _is_allowed(self, email: str) -> bool:
        email = email.lower()
        return email in self.allowlist

    def _user_for(self, email: str) -> User:
        email = email.lower()
        override = self.users_overrides.get(email, {})
        uid = override.get("uid") or email.split("@")[0].lower()
        uid = re.sub(r"[^a-z0-9_-]", "-", uid)[:32] or "user"
        return User(
            user_id=uid,
            tenant_id=self.config.get("tenant_id", "default"),
            display_name=override.get("display", uid),
            email=email,
            roles=list(override.get("roles", ["user"])),
            provider="magic_link",
            provider_uid=email,
        )

    async def request_link(self, email: str, next_url: str = "/", request=None) -> bool:
        """生成 token 并发邮件。邮件失败抛异常；email 不在 allowlist 静默返回 True（防枚举）。"""
        if not EMAIL_RE.match(email or ""):
            raise AuthError("invalid email")
        email = email.strip().lower()
        if not self._is_allowed(email):
            # 防用户枚举：假装发了
            return True
        token = self.tokens.create(email, ttl_minutes=self.token_ttl)
        base = self.link_base_url
        if not base and request is not None:
            try:
                base = f"{request.url.scheme}://{request.url.netloc}"
            except Exception:
                base = ""
        link = f"{base}/auth/magic/verify?{urlencode({'token': token, 'next': next_url or '/'})}"
        self._send_email(email, link)
        return True

    async def verify_token(self, token: str) -> Optional[Session]:
        """点链接后校验；成功写 session。"""
        if not token:
            return None
        email = self.tokens.consume(token)
        if not email:
            return None
        user = self._user_for(email)
        if not self.session_store:
            raise AuthConfigError("session_store not wired")
        return self.session_store.create(user)

    # ---------- SMTP ----------

    def _send_email(self, to_email: str, link: str) -> None:
        # 测试兜底：OME365_MAGIC_LINK_SINK_FILE 把邮件内容 append 成 JSONL 到文件，
        # 绕开真实 SMTP。仅供 E2E / 本地调试，切勿在生产设置这个变量。
        sink = os.environ.get("OME365_MAGIC_LINK_SINK_FILE")
        if sink:
            import json as _json
            with open(sink, "a", encoding="utf-8") as fh:
                fh.write(_json.dumps({"to": to_email, "link": link}, ensure_ascii=False) + "\n")
            return

        cfg = self.smtp_cfg
        host = cfg.get("host")
        if not host:
            raise AuthConfigError("smtp.host missing")
        port = int(cfg.get("port", 587))
        username = cfg.get("username", "")
        password = os.environ.get(cfg.get("password_env", ""), "") if cfg.get("password_env") else cfg.get("password", "")
        from_addr = cfg.get("from") or username
        use_tls = bool(cfg.get("starttls", True))

        msg = EmailMessage()
        msg["Subject"] = "Ome365 登录链接（15 分钟内有效）"
        msg["From"] = from_addr
        msg["To"] = to_email
        msg.set_content(
            f"点击下方链接登录 Ome365（15 分钟内有效；只能用一次）：\n\n{link}\n\n"
            f"如果不是你本人申请的，请忽略本邮件。"
        )

        with smtplib.SMTP(host, port, timeout=15) as s:
            if use_tls:
                s.starttls()
            if username and password:
                s.login(username, password)
            s.send_message(msg)
