"""
OIDCProvider · OpenID Connect 标准 Authorization Code Flow + PKCE

用于任意 OIDC 兼容 SSO：
  - Okta / Azure AD / Auth0 / Keycloak / Google Workspace
  - 企业自建 SSO（只要实现 /.well-known/openid-configuration 即可）

流程：
  1. 用户访问 → 后端生成 state(签 tenant_id) + code_verifier/code_challenge + nonce
     → 302 到 {issuer}/authorize?client_id=...&scope=openid+profile+email&
        redirect_uri=...&state=...&code_challenge=...
  2. 用户在公司 SSO 登录、同意授权 → 302 回到 redirect_uri?code=xxx&state=xxx
  3. 后端校验 state → 取 tid → 查 tenant 的 provider 实例
  4. provider POST {issuer}/token 换 access_token + id_token
  5. 解 id_token claims；默认走 JWKS 验签（RS256/ES256），校验 iss/aud/exp/nonce
     仅当 verify_signature=false 时跳过验签（只推荐本地 dev 用）
  6. GET {issuer}/userinfo 拿完整 profile（按 scope）
  7. 校验 allowed_domains / allowlist_userids（企业白名单）
  8. 建 session，redirect 回 next_url

Config schema (tenant_config.auth.providers.oidc):
    {
      "issuer": "https://sso.example.com",
      "client_id": "ome365",
      "client_secret_env": "OME365_OIDC_SECRET",
      "redirect_uri": "https://ome.example.com/auth/oidc/callback",
      "scopes": ["openid", "profile", "email"],
      "allowed_domains": ["example.com"],        // email 域白名单（可选）
      "allowlist_userids": ["alice", "bob"],     // sub/uid 白名单（可选，留空=不限）
      "uid_claim": "preferred_username",         // userinfo 里哪个字段当 uid（默认 sub）
      "email_claim": "email",
      "display_name_claim": "name",
      "role_map": {"company-admins": "admin"},   // group claim → 角色（可选）
      "discovery_cache_seconds": 3600,           // 可选，默认 1h 不重新拉 issuer 配置
      "verify_signature": true,                  // 默认 true。设 false 只允许本地 dev
      "allowed_algorithms": ["RS256", "ES256"],  // 允许的 JWS 签名算法；HS* 默认禁
      "jwks_cache_seconds": 3600                 // JWKS 缓存 TTL
    }

state/verifier 存 SQLite（同 SessionStore 的模式，独立表避免冲突）：
    oidc_pending(state TEXT PK, tenant_id, nonce, code_verifier, next_url, created_at, expires_at)
"""
from __future__ import annotations

import os
import json
import time
import base64
import hashlib
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urlparse

import requests  # 已经在 requirements.txt

try:
    import jwt as _jwt  # PyJWT，验签用
    from jwt import PyJWKClient as _PyJWKClient
    _JWT_AVAILABLE = True
except Exception:
    _jwt = None
    _PyJWKClient = None
    _JWT_AVAILABLE = False

from ..base import User, Session, AuthError, AuthConfigError


# ── state/verifier 存储 ─────────────────────────────

class OIDCPendingStore:
    """存未完成的授权流：state / code_verifier / nonce / tid / next_url。

    单次使用，授权回调成功后立刻删除；超时 15 分钟自动 gc。
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._lock, sqlite3.connect(str(self.db_path), isolation_level=None) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS oidc_pending ("
                "  state TEXT PRIMARY KEY,"
                "  tenant_id TEXT NOT NULL,"
                "  nonce TEXT NOT NULL,"
                "  code_verifier TEXT NOT NULL,"
                "  next_url TEXT NOT NULL,"
                "  created_at REAL NOT NULL,"
                "  expires_at REAL NOT NULL"
                ")"
            )

    def put(self, state: str, tid: str, nonce: str, verifier: str, next_url: str, ttl_seconds: int = 900) -> None:
        now = datetime.utcnow().timestamp()
        with self._lock, sqlite3.connect(str(self.db_path), isolation_level=None) as c:
            c.execute(
                "INSERT INTO oidc_pending(state, tenant_id, nonce, code_verifier, next_url, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (state, tid, nonce, verifier, next_url, now, now + ttl_seconds),
            )

    def consume(self, state: str) -> Optional[dict]:
        """拿出来就删，避免 replay。过期视为不存在。"""
        now = datetime.utcnow().timestamp()
        with self._lock, sqlite3.connect(str(self.db_path), isolation_level=None) as c:
            row = c.execute(
                "SELECT tenant_id, nonce, code_verifier, next_url, expires_at FROM oidc_pending WHERE state = ?",
                (state,),
            ).fetchone()
            if not row:
                return None
            tid, nonce, verifier, next_url, exp = row
            c.execute("DELETE FROM oidc_pending WHERE state = ?", (state,))
            if now >= exp:
                return None
            return {"tenant_id": tid, "nonce": nonce, "code_verifier": verifier, "next_url": next_url}

    def gc(self) -> int:
        now = datetime.utcnow().timestamp()
        with self._lock, sqlite3.connect(str(self.db_path), isolation_level=None) as c:
            cur = c.execute("DELETE FROM oidc_pending WHERE expires_at < ?", (now,))
            return cur.rowcount


# ── Provider ────────────────────────────────────────

def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class OIDCProvider:
    """Authorization Code Flow + PKCE，最小生产可用。"""

    name = "oidc"

    def __init__(self, config: dict | None = None, *, session_store=None, pending_store: OIDCPendingStore | None = None, tenant_id: str = "default"):
        self.config = config or {}
        self.session_store = session_store
        self.pending_store = pending_store
        self.tenant_id = self.config.get("tenant_id", tenant_id)

        self.issuer = (self.config.get("issuer") or "").rstrip("/")
        self.client_id = self.config.get("client_id", "")
        self.client_secret = os.environ.get(self.config.get("client_secret_env", ""), "") if self.config.get("client_secret_env") else self.config.get("client_secret", "")
        self.redirect_uri = self.config.get("redirect_uri", "")
        self.scopes = list(self.config.get("scopes") or ["openid", "profile", "email"])

        self.allowed_domains = set(d.lower() for d in (self.config.get("allowed_domains") or []))
        self.allowlist_userids = set(self.config.get("allowlist_userids") or [])
        self.uid_claim = self.config.get("uid_claim", "sub")
        self.email_claim = self.config.get("email_claim", "email")
        self.display_claim = self.config.get("display_name_claim", "name")
        self.role_map = dict(self.config.get("role_map") or {})
        self.discovery_cache_sec = int(self.config.get("discovery_cache_seconds", 3600))
        self.verify_signature = bool(self.config.get("verify_signature", True))
        self.allowed_algorithms = list(self.config.get("allowed_algorithms") or ["RS256", "ES256", "RS384", "RS512", "ES384", "ES512"])
        self.jwks_cache_sec = int(self.config.get("jwks_cache_seconds", 3600))

        self._discovery = None
        self._discovery_fetched_at = 0.0
        self._jwks_client = None
        self._jwks_uri = None
        self._jwks_fetched_at = 0.0
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
            return None  # 跨租户 session 不承认
        return u

    async def login_url(self, redirect_to: str = "/") -> str:
        """浏览器跳转登录起点；AuthMiddleware 会 302 到这里。"""
        return f"/auth/oidc/start?next={redirect_to or '/'}"

    async def callback(self, request) -> Optional[Session]:
        """OIDC redirect_uri 回调：code + state → session"""
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code or not state:
            raise AuthError("missing code or state")
        pending = self.pending_store.consume(state) if self.pending_store else None
        if not pending:
            raise AuthError("invalid or expired state (possible CSRF)")
        if pending["tenant_id"] != self.tenant_id:
            raise AuthError(f"state/tenant mismatch: {pending['tenant_id']} vs {self.tenant_id}")
        token_set = self._exchange_code(code, pending["code_verifier"])
        claims = self._parse_id_token(token_set.get("id_token", ""))
        # nonce 校验：id_token.nonce == pending.nonce
        if claims.get("nonce") and claims.get("nonce") != pending["nonce"]:
            raise AuthError("nonce mismatch")
        profile = self._fetch_userinfo(token_set.get("access_token", "")) if token_set.get("access_token") else {}
        merged = {**claims, **profile}
        self._check_allowlist(merged)
        user = self._build_user(merged)
        if not self.session_store:
            raise AuthConfigError("session_store not wired")
        sess = self.session_store.create(user)
        # 把 next_url 塞进 session.data 临时保管；handler 读完跳转
        sess.data["_next_url"] = pending["next_url"]
        return sess

    async def logout(self, session_id: str) -> None:
        if self.session_store:
            self.session_store.delete(session_id)

    def healthcheck(self) -> dict:
        issues = []
        if not self.issuer:
            issues.append("issuer missing")
        if not self.client_id:
            issues.append("client_id missing")
        if not self.client_secret:
            issues.append(f"client_secret not resolved (env {self.config.get('client_secret_env')} empty?)")
        if not self.redirect_uri:
            issues.append("redirect_uri missing")
        if self.verify_signature and not _JWT_AVAILABLE:
            issues.append("verify_signature=true but PyJWT/cryptography not installed")
        if not self.verify_signature:
            issues.append("verify_signature=false (dev mode) — DO NOT use in prod")
        return {
            "ok": not issues,
            "provider": "oidc",
            "tenant_id": self.tenant_id,
            "issuer": self.issuer,
            "verify_signature": self.verify_signature,
            "allowed_algorithms": self.allowed_algorithms,
            "allowed_domains": list(self.allowed_domains),
            "allowlist_size": len(self.allowlist_userids),
            "issues": issues,
        }

    # ---------- OIDC 专用 API ----------

    def start_url(self, next_url: str = "/") -> str:
        """构造 authorize URL，保存 state/verifier 到 pending store"""
        if not self.issuer or not self.client_id or not self.redirect_uri:
            raise AuthConfigError("oidc not fully configured (issuer/client_id/redirect_uri)")
        if self.pending_store is None:
            raise AuthConfigError("pending_store not wired")
        state = _b64url(secrets.token_bytes(24))
        nonce = _b64url(secrets.token_bytes(16))
        verifier = _b64url(secrets.token_bytes(32))
        challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
        self.pending_store.put(state, self.tenant_id, nonce, verifier, next_url)
        disc = self._discover()
        authorize = disc.get("authorization_endpoint") or f"{self.issuer}/authorize"
        q = urlencode({
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        return f"{authorize}?{q}"

    # ---------- HTTP 细节 ----------

    def _discover(self) -> dict:
        """拉 /.well-known/openid-configuration；简单 TTL 缓存。"""
        if self._discovery and (time.time() - self._discovery_fetched_at) < self.discovery_cache_sec:
            return self._discovery
        url = f"{self.issuer}/.well-known/openid-configuration"
        try:
            r = self._session.get(url, timeout=5)
            r.raise_for_status()
            self._discovery = r.json()
            self._discovery_fetched_at = time.time()
        except Exception as e:
            # issuer 没开 discovery？按约定 endpoint 兜底
            self._discovery = {
                "authorization_endpoint": f"{self.issuer}/authorize",
                "token_endpoint": f"{self.issuer}/token",
                "userinfo_endpoint": f"{self.issuer}/userinfo",
            }
            self._discovery_fetched_at = time.time()
        return self._discovery

    def _exchange_code(self, code: str, verifier: str) -> dict:
        disc = self._discover()
        token_url = disc.get("token_endpoint") or f"{self.issuer}/token"
        r = self._session.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code_verifier": verifier,
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        if r.status_code != 200:
            raise AuthError(f"token exchange failed ({r.status_code}): {r.text[:200]}")
        return r.json()

    def _get_jwks_client(self):
        """拿（并缓存）PyJWKClient。jwks_uri 从 discovery 取。"""
        if not _JWT_AVAILABLE:
            raise AuthConfigError("PyJWT not installed; cannot verify id_token signature")
        now = time.time()
        if self._jwks_client and (now - self._jwks_fetched_at) < self.jwks_cache_sec:
            return self._jwks_client
        disc = self._discover()
        jwks_uri = disc.get("jwks_uri") or f"{self.issuer}/.well-known/jwks.json"
        # PyJWKClient 内部有自己的 cache，但我们外层 TTL 控制重建频率
        self._jwks_client = _PyJWKClient(jwks_uri, cache_keys=True, lifespan=self.jwks_cache_sec)
        self._jwks_uri = jwks_uri
        self._jwks_fetched_at = now
        return self._jwks_client

    def _decode_payload_unverified(self, id_token: str) -> dict:
        """仅解 JWT payload，不验签。只在 verify_signature=false 时用。"""
        parts = id_token.split(".")
        if len(parts) != 3:
            return {}
        try:
            payload = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
            return json.loads(base64.urlsafe_b64decode(payload.encode()).decode("utf-8"))
        except Exception:
            return {}

    def _parse_id_token(self, id_token: str) -> dict:
        """验签 + 校验 claims 并返回 payload。

        默认走 JWKS 验签（RS256/ES256）+ 校验 iss/aud/exp/iat/nbf。
        只有 verify_signature=false 才跳过（本地 dev 用，生产严禁）。
        nonce 校验在 callback() 中，因为要和 pending_store 的值比对。
        """
        if not id_token:
            return {}
        if not self.verify_signature:
            # dev 兜底：不验签，只解 payload
            return self._decode_payload_unverified(id_token)
        if not _JWT_AVAILABLE:
            raise AuthConfigError("PyJWT/cryptography not installed; install or set verify_signature=false (dev only)")
        try:
            # 从 header 拿 kid，找对应 signing key
            jwks_client = self._get_jwks_client()
            signing_key = jwks_client.get_signing_key_from_jwt(id_token)
            claims = _jwt.decode(
                id_token,
                signing_key.key,
                algorithms=self.allowed_algorithms,
                audience=self.client_id,
                issuer=self.issuer or None,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                    "verify_aud": bool(self.client_id),
                    "verify_iss": bool(self.issuer),
                    "require": ["exp", "iat", "iss", "sub"],
                },
                leeway=60,  # 容忍 1 分钟时钟漂移
            )
            return claims
        except _jwt.ExpiredSignatureError as e:
            raise AuthError(f"id_token expired: {e}")
        except _jwt.InvalidAudienceError as e:
            raise AuthError(f"id_token audience mismatch: {e}")
        except _jwt.InvalidIssuerError as e:
            raise AuthError(f"id_token issuer mismatch: {e}")
        except _jwt.InvalidSignatureError as e:
            raise AuthError(f"id_token signature invalid: {e}")
        except _jwt.InvalidTokenError as e:
            raise AuthError(f"id_token invalid: {e}")
        except Exception as e:
            raise AuthError(f"id_token verify failed: {e}")

    def _fetch_userinfo(self, access_token: str) -> dict:
        disc = self._discover()
        ui_url = disc.get("userinfo_endpoint") or f"{self.issuer}/userinfo"
        try:
            r = self._session.get(ui_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=8)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def _check_allowlist(self, claims: dict) -> None:
        """按邮箱域 + userid 白名单校验；都没配就放行。"""
        if self.allowed_domains:
            email = (claims.get(self.email_claim) or "").lower()
            dom = email.split("@")[-1] if "@" in email else ""
            if dom not in self.allowed_domains:
                raise AuthError(f"email domain '{dom}' not allowed")
        if self.allowlist_userids:
            uid = claims.get(self.uid_claim) or claims.get("sub") or ""
            if uid not in self.allowlist_userids:
                raise AuthError(f"user '{uid}' not in allowlist")

    def _build_user(self, claims: dict) -> User:
        import re
        raw_uid = claims.get(self.uid_claim) or claims.get("sub") or claims.get("email") or "user"
        uid = re.sub(r"[^a-z0-9_-]", "-", str(raw_uid).lower())[:32] or "user"
        email = claims.get(self.email_claim, "")
        display = claims.get(self.display_claim) or uid

        # role 映射：claim "groups" 或 "roles" 或自定义
        roles = ["user"]
        groups = claims.get("groups") or claims.get("roles") or []
        if isinstance(groups, str):
            groups = [groups]
        for g in groups:
            r = self.role_map.get(g)
            if r and r not in roles:
                roles.append(r)

        return User(
            user_id=uid,
            tenant_id=self.tenant_id,
            display_name=display,
            email=email,
            roles=roles,
            provider="oidc",
            provider_uid=str(raw_uid),
            extra={"oidc_claims": {k: claims.get(k) for k in ("sub", "iss", "aud", "email_verified")}},
        )
