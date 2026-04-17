"""
NoneProvider · 不认证，用于：
- Phase 2a legacy 单用户模式（当前船长的本地 setup）
- 开发调试
- sample-vault demo 不需要登录的场景

返回固定的 default user（captain@default）。所有请求视为已登录。
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime, timedelta

from ..base import User, Session, AuthProvider


class NoneProvider:
    name = "none"

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.user_id = self.config.get("user_id", "captain")
        self.tenant_id = self.config.get("tenant_id", "default")
        self.display_name = self.config.get("display_name", "Captain")

    def _default_user(self) -> User:
        return User(
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            display_name=self.display_name,
            provider="none",
            provider_uid=self.user_id,
            roles=["admin"],
        )

    async def authenticate(self, request) -> Optional[User]:
        return self._default_user()

    async def login_url(self, redirect_to: str = "/") -> str:
        # None provider 不需要登录页，返回重定向到目标
        return redirect_to or "/"

    async def callback(self, request) -> Optional[Session]:
        # 永远返回无需 session（调用方可不写 cookie）
        return None

    async def logout(self, session_id: str) -> None:
        return

    def healthcheck(self) -> dict:
        return {"ok": True, "provider": "none", "issues": []}
