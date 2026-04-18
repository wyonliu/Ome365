"""
BasicProvider · 简单密码登录，用于：
- 开源 demo（OME365_DEMO_PASSWORD env）
- 家庭轻量部署（tenant_config.auth.providers.basic.users 里列成员）

不是 HTTP Basic Auth——是一个 `/auth/login` 表单页 + cookie session。
密码存 argon2 / bcrypt 哈希；如果配置里是明文，启动时警告。

Config schema（tenant_config.auth.providers.basic）:
    {
        "users": [
            {"uid": "captain", "email": "cap@example.com", "password_hash": "$argon2...", "display": "Captain", "roles": ["admin"]},
            ...
        ],
        "demo_password_env": "OME365_DEMO_PASSWORD"  // 可选，兜底单用户 demo
    }
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from typing import Optional

from ..base import User, Session, AuthError, AuthConfigError


def _verify_password(password: str, password_hash: str, *, allow_plaintext: bool = False) -> bool:
    """支持多种格式：argon2 / bcrypt / sha256$salt$hex。

    明文（不带 $argon2 / $2 / sha256$ 前缀的哈希）默认 **运行时拒绝**，
    只有 allow_plaintext=True 才放行——目前仅 OME365_DEMO_PASSWORD 注入的
    "_from_env" demo 用户允许。健康检查会把明文用户列入 issues。
    """
    if not password_hash:
        return False
    if password_hash.startswith("$argon2"):
        try:
            from argon2 import PasswordHasher
            return PasswordHasher().verify(password_hash, password) is None or True
        except Exception:
            return False
    if password_hash.startswith("$2"):
        try:
            import bcrypt
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        except Exception:
            return False
    if password_hash.startswith("sha256$"):
        try:
            _, salt, expected = password_hash.split("$", 2)
            actual = hashlib.sha256((salt + password).encode()).hexdigest()
            return hmac.compare_digest(actual, expected)
        except Exception:
            return False
    # 未知前缀 → 视为明文
    if allow_plaintext:
        return hmac.compare_digest(password_hash, password)
    return False  # 拒绝明文，保护 tenant_config 误配置场景


def hash_sha256(password: str, salt: str | None = None) -> str:
    """用户辅助函数：生成 sha256$salt$hex 密码哈希（demo 用；生产用 argon2/bcrypt）"""
    salt = salt or secrets.token_hex(8)
    return "sha256$" + salt + "$" + hashlib.sha256((salt + password).encode()).hexdigest()


class BasicProvider:
    name = "basic"

    def __init__(self, config: dict | None = None, *, session_store=None):
        self.config = config or {}
        self.session_store = session_store
        self._users_by_uid: dict[str, dict] = {u["uid"]: u for u in self.config.get("users", [])}
        # 兜底：env 里的 demo 密码构造一个 demo 用户
        demo_env = self.config.get("demo_password_env") or "OME365_DEMO_PASSWORD"
        demo_pass = os.environ.get(demo_env)
        if demo_pass and "demo" not in self._users_by_uid:
            self._users_by_uid["demo"] = {
                "uid": "demo",
                "email": "demo@example.com",
                "display": "Demo User",
                "password_hash": demo_pass,  # 明文，仅用于 demo
                "roles": ["admin"],
                "_from_env": True,
            }

    async def authenticate(self, request) -> Optional[User]:
        if self.session_store is None:
            return None
        sid = request.cookies.get("ome365_sid") if hasattr(request, "cookies") else None
        if not sid:
            return None
        return self.session_store.get_user(sid)

    async def login_url(self, redirect_to: str = "/") -> str:
        return f"/auth/login?next={redirect_to or '/'}"

    async def verify_password(self, uid: str, password: str) -> Optional[User]:
        """核心登录入口；/auth/login 表单 handler 会调它。

        明文密码仅 OME365_DEMO_PASSWORD 注入的 demo 用户允许（_from_env=True），
        或用户显式标注 allow_plaintext=True（不推荐，仅兼容历史配置）。
        """
        u = self._users_by_uid.get(uid)
        if not u:
            return None
        allow_pt = bool(u.get("_from_env")) or bool(u.get("allow_plaintext"))
        if not _verify_password(password, u.get("password_hash", ""), allow_plaintext=allow_pt):
            return None
        return User(
            user_id=u["uid"],
            tenant_id=self.config.get("tenant_id", "default"),
            display_name=u.get("display", u["uid"]),
            email=u.get("email", ""),
            roles=list(u.get("roles", [])),
            provider="basic",
            provider_uid=u["uid"],
        )

    async def callback(self, request) -> Optional[Session]:
        # Basic 没有标准 callback（登录走 verify_password + form handler）
        return None

    async def logout(self, session_id: str) -> None:
        if self.session_store:
            self.session_store.delete(session_id)

    def healthcheck(self) -> dict:
        issues = []
        plaintext_blocked = []
        if not self._users_by_uid:
            issues.append("no users configured; set tenant_config.auth.providers.basic.users or OME365_DEMO_PASSWORD")
        for uid, u in self._users_by_uid.items():
            ph = u.get("password_hash", "")
            if ph.startswith(("$argon2", "$2", "sha256$")):
                continue
            allow_pt = bool(u.get("_from_env")) or bool(u.get("allow_plaintext"))
            if allow_pt:
                issues.append(f"user {uid}: plaintext password allowed (_from_env demo or allow_plaintext=true) — DO NOT use in prod")
            else:
                # 运行时拒绝：verify_password 会返回 False
                plaintext_blocked.append(uid)
                issues.append(f"user {uid}: plaintext password REJECTED at runtime (use argon2/bcrypt/sha256$)")
        return {
            "ok": not issues or all(("plaintext password allowed" in i) for i in issues),
            "provider": "basic",
            "users": list(self._users_by_uid.keys()),
            "plaintext_blocked": plaintext_blocked,
            "issues": issues,
        }
