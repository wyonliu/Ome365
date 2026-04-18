"""
AuthRegistry · 每租户一套 AuthProvider 实例

为什么需要：
  - 企业 A 租户装 wecom（A 的 corp_id）
  - 企业 B 租户装 oidc（B 的 issuer）
  - 默认 tenant 装 none/basic
  - 三方互不干扰：企业 A 的企微扫码不能登进企业 B 租户

HTTP 进来之后：
  1. resolve_tenant(request) → tid（见 tenant_router.py）
  2. registry.get(tid) → AuthProvider 实例
  3. middleware 用该 provider 解析 cookie session、决定是否放行

缓存策略：
  - 首次 get(tid) 时按 $OME365_HOME/tenants/{tid}/tenant_config.json 实例化
  - 租户配置热更新：外部调用 invalidate(tid) 清缓存重建
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    from ctx import load_tenant_config, ome365_home
except ImportError:
    from ..ctx import load_tenant_config, ome365_home

from .session_store import SessionStore
from .providers.none_provider import NoneProvider
from .providers.basic_provider import BasicProvider
from .providers.magic_link_provider import MagicLinkProvider
from .providers.oidc_provider import OIDCProvider, OIDCPendingStore
from .providers.wecom_provider import WecomProvider, WecomPendingStore


class AuthRegistry:
    def __init__(self, session_store: SessionStore, oidc_pending: OIDCPendingStore | None = None, wecom_pending: WecomPendingStore | None = None):
        self.session_store = session_store
        self.oidc_pending = oidc_pending or OIDCPendingStore(ome365_home() / "oidc_pending.db")
        self.wecom_pending = wecom_pending or WecomPendingStore(ome365_home() / "wecom_pending.db")
        self._providers: dict[str, object] = {}

    def get(self, tenant_id: str):
        if tenant_id not in self._providers:
            self._providers[tenant_id] = self._build(tenant_id)
        return self._providers[tenant_id]

    def invalidate(self, tenant_id: str) -> None:
        self._providers.pop(tenant_id, None)

    def _build(self, tenant_id: str):
        cfg = load_tenant_config(tenant_id)
        acfg = (cfg.get("auth") or {})
        name = os.environ.get("OME365_AUTH_PROVIDER") or acfg.get("provider") or "none"
        # 允许 env 按租户覆盖：OME365_AUTH_PROVIDER_ACME=wecom
        env_override = os.environ.get(f"OME365_AUTH_PROVIDER_{tenant_id.upper()}")
        if env_override:
            name = env_override

        pcfg = ((acfg.get("providers") or {}).get(name) or {})
        pcfg = {**pcfg, "tenant_id": tenant_id}

        if name == "none":
            return NoneProvider(pcfg)
        if name == "basic":
            return BasicProvider(pcfg, session_store=self.session_store)
        if name == "magic_link":
            return MagicLinkProvider(pcfg, session_store=self.session_store, token_db_path=ome365_home() / f"magic_tokens_{tenant_id}.db")
        if name == "oidc":
            return OIDCProvider(pcfg, session_store=self.session_store, pending_store=self.oidc_pending, tenant_id=tenant_id)
        if name == "wecom":
            return WecomProvider(pcfg, session_store=self.session_store, pending_store=self.wecom_pending, tenant_id=tenant_id)
        print(f"[auth.registry] unknown provider '{name}' for tenant '{tenant_id}', falling back to none")
        return NoneProvider(pcfg)

    def healthcheck(self) -> dict:
        out = {"ok": True, "tenants": {}, "sessions": self.session_store.count()}
        for tid, prov in self._providers.items():
            hc = prov.healthcheck()
            out["tenants"][tid] = hc
            if not hc.get("ok"):
                out["ok"] = False
        return out
