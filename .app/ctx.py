"""
Ome365 · Tenant / User / Request Context 基础设施

Phase 2a 目标：定义多租户 / 多用户目录布局 + 解析辅助 + FastAPI 依赖。
本模块**不**改写现有 server.py 的 VAULT 常量——那是 Phase 2b 配合认证层一起做。
当前阶段 resolve_context() 在单用户模式下返回默认 tenant=default, user=captain。

## 目录布局（install home 与 user vault 分离）

    $OME365_HOME/                 ← 安装元数据根（默认 ~/.ome365）
      tenants/
        {tid}/                    ← tenant slug (^[a-z][a-z0-9_-]{1,31}$)
          tenant_config.json      ← 租户品牌/分类配置（gitignored）
          cockpit_config.json     ← 驾舱字典（gitignored）
          share_registry.json     ← 租户共享池（gitignored）
          shared/                 ← 租户全员可读资源（EEG/taxonomy）
          users/
            {uid}/                ← user slug
              profile.json        ← email / display_name / roles / vault_path
              settings.json       ← 个人 API key / AI 偏好
              state/              ← growth.json / reminders.json 等运行时状态

    $OME365_VAULT/                ← 用户个人 vault（可任意位置，不必在 $OME365_HOME 下）
      Journal/ Notes/ Memory/ ...

    profile.json 里的 vault_path 指向该用户的 vault（绝对路径）；
    默认 = $OME365_HOME/tenants/{tid}/users/{uid}/vault/（若未显式指定）。
    这样 metadata 与 data 分离，单用户 legacy 场景下 user vault 可继续指向
    原有 $OME365_VAULT，零搬迁。

## 兼容模式

- 若 $OME365_HOME/tenants/ 不存在 → legacy 单用户模式
- legacy 模式下 ctx.vault_path = $OME365_VAULT
- $OME365_COMPAT_LEGACY=1 强制启用 legacy（忽略 tenants/）
- 迁移脚本 scripts/migrate_to_multiuser.py 建 $OME365_HOME/tenants/default/...
  并把 profile.json.vault_path 写成原 $OME365_VAULT（无需搬移数据）

## 配置解析优先级

1. 读 tenant-level config: $OME365_ROOT/tenants/{tid}/tenant_config.json
2. 若缺失 → 降级 .app/tenant_config.json (legacy live)
3. 若仍缺失 → .app/tenant_config.sample.json
"""
from __future__ import annotations

import os
import re
import json
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Slug 规范 ────────────────────────────────────────────
SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
DEFAULT_TENANT_ID = "default"
DEFAULT_USER_ID = "captain"  # legacy 单用户的默认 uid（迁移时可改）


def is_valid_slug(s: str) -> bool:
    return bool(s) and bool(SLUG_RE.match(s))


def assert_slug(s: str, kind: str = "slug") -> str:
    if not is_valid_slug(s):
        raise ValueError(f"Invalid {kind}: {s!r} (must match {SLUG_RE.pattern})")
    return s


# ── 根目录解析 ────────────────────────────────────────────

def _app_dir() -> Path:
    return Path(__file__).resolve().parent


def _legacy_vault() -> Path:
    """legacy 单用户 VAULT：env OME365_VAULT 或 .app 父目录。"""
    return Path(os.environ.get("OME365_VAULT", _app_dir().parent)).resolve()


def ome365_home() -> Path:
    """
    安装元数据根 $OME365_HOME（tenants/ 所在目录）。

    优先级：
    1. env OME365_HOME（显式指定，推荐）
    2. env OME365_ROOT（兼容早期字段名）
    3. ~/.ome365（标准 XDG-ish 默认）
    """
    env_home = os.environ.get("OME365_HOME") or os.environ.get("OME365_ROOT")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".ome365").resolve()


# 保留旧 API 名字以兼容调用方
ome365_root = ome365_home


def is_multi_user_mode() -> bool:
    """
    检测当前是否为多用户模式。

    - 显式 OME365_COMPAT_LEGACY=1 → 强制 legacy
    - $OME365_HOME/tenants/ 存在 → 多用户
    - 否则 → legacy
    """
    if os.environ.get("OME365_COMPAT_LEGACY") == "1":
        return False
    return (ome365_home() / "tenants").exists()


# ── 路径解析 ────────────────────────────────────────────

def tenants_root() -> Path:
    return ome365_home() / "tenants"


def tenant_dir(tid: str) -> Path:
    assert_slug(tid, "tenant_id")
    return tenants_root() / tid


def tenant_config_path(tid: str) -> Path:
    """tenant 级 tenant_config.json 优先；fallback 到 .app/tenant_config.json。"""
    return tenant_dir(tid) / "tenant_config.json"


def tenant_shared_dir(tid: str) -> Path:
    return tenant_dir(tid) / "shared"


def tenant_users_dir(tid: str) -> Path:
    return tenant_dir(tid) / "users"


def user_dir(tid: str, uid: str) -> Path:
    assert_slug(uid, "user_id")
    return tenant_users_dir(tid) / uid


def _read_profile(tid: str, uid: str) -> dict:
    fp = user_profile_path(tid, uid)
    if fp.exists():
        try:
            return json.loads(fp.read_text("utf-8"))
        except Exception:
            pass
    return {}


def user_profile_path(tid: str, uid: str) -> Path:
    if is_multi_user_mode():
        return user_dir(tid, uid) / "profile.json"
    return _app_dir() / "profile.json"


def user_vault(tid: str, uid: str) -> Path:
    """
    多用户模式：读 profile.json.vault_path；未设则默认
    $OME365_HOME/tenants/{tid}/users/{uid}/vault/。
    legacy 模式：= $OME365_VAULT。
    """
    if is_multi_user_mode():
        prof = _read_profile(tid, uid)
        vp = prof.get("vault_path")
        if vp:
            return Path(vp).expanduser().resolve()
        return user_dir(tid, uid) / "vault"
    return _legacy_vault()


def user_state_dir(tid: str, uid: str) -> Path:
    if is_multi_user_mode():
        return user_dir(tid, uid) / "state"
    return _app_dir()


def user_settings_path(tid: str, uid: str) -> Path:
    if is_multi_user_mode():
        return user_dir(tid, uid) / "settings.json"
    return _app_dir() / "settings.json"


def iter_tenants() -> list[str]:
    """列出所有租户 slug。"""
    if not is_multi_user_mode():
        return [DEFAULT_TENANT_ID]
    return sorted(
        p.name for p in tenants_root().iterdir()
        if p.is_dir() and is_valid_slug(p.name)
    )


def iter_users(tid: str) -> list[str]:
    """列出某租户下所有用户 slug。"""
    if not is_multi_user_mode():
        return [DEFAULT_USER_ID]
    users_d = tenant_users_dir(tid)
    if not users_d.exists():
        return []
    return sorted(
        p.name for p in users_d.iterdir()
        if p.is_dir() and is_valid_slug(p.name)
    )


# ── Tenant Config 读取（分层 fallback）────────────────

def load_tenant_config(tid: str = DEFAULT_TENANT_ID) -> dict:
    """
    分层读取 tenant_config：
    1. $OME365_HOME/tenants/{tid}/tenant_config.json （多用户 live）
    2. .app/tenant_config.json  （legacy live）
    3. .app/tenant_config.sample.json  （fallback 占位）
    """
    candidates = []
    if is_multi_user_mode():
        candidates.append(tenant_config_path(tid))
    candidates.append(_app_dir() / "tenant_config.json")
    candidates.append(_app_dir() / "tenant_config.sample.json")
    for fp in candidates:
        if fp.exists():
            try:
                data = json.loads(fp.read_text("utf-8"))
                # 记录来源文件名（便于调试 live/sample）
                data.setdefault("_source", fp.name)
                data.setdefault("_tenant_id", tid)
                return data
            except Exception as e:
                return {"_source": "error", "_error": str(e), "_tenant_id": tid}
    return {"_source": "empty", "_tenant_id": tid, "brand": {}, "cockpit": {}, "prompts": {}, "categories": {}, "entities": {}}


# ── 请求上下文 ───────────────────────────────────────

@dataclass
class RequestCtx:
    """每个请求的解析上下文。由 resolve_context() 填充。"""
    tenant_id: str = DEFAULT_TENANT_ID
    user_id: str = DEFAULT_USER_ID
    vault_path: Path = field(default_factory=_legacy_vault)
    state_dir: Path = field(default_factory=_app_dir)
    settings_path: Path = field(default_factory=lambda: _app_dir() / "settings.json")
    tenant_config: dict = field(default_factory=dict)
    is_multi_user: bool = False
    user: Optional[object] = None  # auth.base.User 实例；legacy 模式为 None

    def resolve_vault(self, rel: str | Path) -> Path:
        """安全解析 vault 内相对路径，防 path traversal。"""
        target = (self.vault_path / rel).resolve()
        if not str(target).startswith(str(self.vault_path.resolve())):
            raise ValueError(f"Path traversal blocked: {rel}")
        return target


# ContextVar：允许 middleware 按请求切换上下文，其它代码无需改动签名
_ctx_var: ContextVar[Optional[RequestCtx]] = ContextVar("ome365_ctx", default=None)


def current_ctx() -> RequestCtx:
    """获取当前请求上下文；未设置则返回 legacy 默认。"""
    ctx = _ctx_var.get()
    if ctx is not None:
        return ctx
    return _build_legacy_ctx()


def set_ctx(ctx: RequestCtx) -> None:
    _ctx_var.set(ctx)


def _build_legacy_ctx() -> RequestCtx:
    """Legacy 单用户模式的默认 ctx。"""
    tid = DEFAULT_TENANT_ID
    uid = DEFAULT_USER_ID
    return RequestCtx(
        tenant_id=tid,
        user_id=uid,
        vault_path=_legacy_vault(),
        state_dir=_app_dir(),
        settings_path=_app_dir() / "settings.json",
        tenant_config=load_tenant_config(tid),
        is_multi_user=False,
    )


def build_ctx(tid: str, uid: str) -> RequestCtx:
    """根据 tid/uid 构建 ctx（多用户模式）。"""
    if not is_multi_user_mode():
        return _build_legacy_ctx()
    assert_slug(tid, "tenant_id")
    assert_slug(uid, "user_id")
    return RequestCtx(
        tenant_id=tid,
        user_id=uid,
        vault_path=user_vault(tid, uid),
        state_dir=user_state_dir(tid, uid),
        settings_path=user_settings_path(tid, uid),
        tenant_config=load_tenant_config(tid),
        is_multi_user=True,
    )


# ── FastAPI 依赖 ───────────────────────────────────────

async def resolve_context(request=None) -> RequestCtx:
    """
    FastAPI `Depends(resolve_context)` 入口。

    Phase 2a：总是返回 legacy ctx（等 Phase 2b 加 auth middleware 后真正按请求切换）。
    """
    return current_ctx()


# ── 自检 ───────────────────────────────────────────────

def healthcheck() -> dict:
    """返回当前 ctx 基础配置，用于调试端点。"""
    multi = is_multi_user_mode()
    out = {
        "is_multi_user": multi,
        "ome365_home": str(ome365_home()),
        "compat_legacy_env": os.environ.get("OME365_COMPAT_LEGACY"),
    }
    if multi:
        tenants = iter_tenants()
        out["tenants"] = tenants
        out["users_per_tenant"] = {t: iter_users(t) for t in tenants}
    else:
        out["legacy_vault"] = str(_legacy_vault())
    ctx = current_ctx()
    out["current_ctx"] = {
        "tenant_id": ctx.tenant_id,
        "user_id": ctx.user_id,
        "vault_path": str(ctx.vault_path),
        "is_multi_user": ctx.is_multi_user,
    }
    return out
