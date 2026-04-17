"""
Ome365 · AuthProvider 抽象基座

设计目标：同一份 server 代码，在 5 个场景下只改 tenant_config.auth.provider 就能切换：
  - none        : 单人自用 / 开发 / sample-vault，无认证（Phase 2a 默认）
  - basic       : 开源 demo 模式，OME365_DEMO_PASSWORD env 单用户
  - magic_link  : 家庭/小团队，邮件 + 一次性链接
  - oidc        : OIDC 标准（云图搜等企业 SSO，Phase 2c 实现）
  - wecom       : 企微扫码（贝壳等，Phase 2c 实现）

Session 存储走服务端 SQLite（非 JWT），可撤销、不泄露 payload。
Provider 构造时接收自己的 config dict，自行校验。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable, Optional


@dataclass
class User:
    """认证后的用户上下文。写入 session、注入 RequestCtx。"""
    user_id: str           # slug，用于路径（^[a-z][a-z0-9_-]{1,31}$）
    tenant_id: str         # 所属租户 slug
    display_name: str = ""
    email: str = ""
    roles: list[str] = field(default_factory=list)
    provider: str = "none"  # 产生此身份的 provider name
    provider_uid: str = ""  # provider 侧原始 ID（sso sub / wecom userid / email）
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "display_name": self.display_name,
            "email": self.email,
            "roles": list(self.roles),
            "provider": self.provider,
            "provider_uid": self.provider_uid,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "User":
        return cls(
            user_id=d["user_id"],
            tenant_id=d.get("tenant_id", "default"),
            display_name=d.get("display_name", ""),
            email=d.get("email", ""),
            roles=list(d.get("roles", [])),
            provider=d.get("provider", "none"),
            provider_uid=d.get("provider_uid", ""),
            extra=dict(d.get("extra", {})),
        )


@dataclass
class Session:
    """服务端 session 记录。"""
    sid: str                         # opaque secure random token（cookie 里的值）
    user_id: str
    tenant_id: str
    expires_at: datetime
    created_at: datetime = field(default_factory=datetime.utcnow)
    data: dict = field(default_factory=dict)

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        return (now or datetime.utcnow()) >= self.expires_at


@runtime_checkable
class AuthProvider(Protocol):
    """所有认证方式都实现这个接口。"""
    name: str  # "none" / "basic" / "magic_link" / "oidc" / "wecom"

    async def authenticate(self, request) -> Optional[User]:
        """
        尝试从 request 中解析出已认证用户（常见姿势：读 cookie → session_store → User）。
        返回 None 表示未登录。
        """
        ...

    async def login_url(self, redirect_to: str = "/") -> str:
        """浏览器跳转登录起点；basic/magic_link 可以返回 /auth/login?next=..."""
        ...

    async def callback(self, request) -> Optional[Session]:
        """
        登录回调。SSO: 处理 code 换 token；magic_link: 校验一次性 token；basic: 校验密码。
        成功返回 Session（调用方写 cookie）；失败返回 None 或抛 HTTPException。
        """
        ...

    async def logout(self, session_id: str) -> None:
        """销毁 session。"""
        ...

    def healthcheck(self) -> dict:
        """自检配置，返回 {'ok': bool, 'issues': [...]}"""
        ...


class AuthError(Exception):
    """认证失败（密码错、token 过期、code 无效等）"""


class AuthConfigError(Exception):
    """provider 配置错误（缺 client_secret、allowlist 空等）"""
