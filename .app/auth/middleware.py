"""
Ome365 · Auth 中间件

职责：
1. 每个 HTTP 请求进来先解 cookie → session_store → User
2. 把 User + tenant_id 注入 ctx.RequestCtx（ContextVar）
3. 挂到哪些路由前面，让 VAULT 调用点自动按 tenant 走到正确的 user vault
4. 未登录且路径在保护列表 → 301 到 login_url；否则放行（public 路径仍可访问）

使用姿势（在 server.py 里）:
    from auth.middleware import AuthMiddleware, install_auth
    install_auth(app, provider, session_store, tenant_config=TENANT)

保护策略默认：
- /api/** 要求已登录（除了 /api/tenant/config、/api/health 等白名单）
- /auth/** 永远放行（登录流程自身）
- /share-static/**、/s/** 放行（分享站走 token，不走登录）
- / 与静态资源放行（前端路由；未登录由前端触发登录）
"""
from __future__ import annotations

import os
import fnmatch
from typing import Optional, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from starlette.requests import Request  # 放在模块级，方便 FastAPI 通过 __globals__ 解析类型注解

try:
    from ctx import RequestCtx, _ctx_var, load_tenant_config, user_vault, user_state_dir, user_settings_path, ome365_home, is_multi_user_mode
except ImportError:  # pragma: no cover
    from ..ctx import RequestCtx, _ctx_var, load_tenant_config, user_vault, user_state_dir, user_settings_path, ome365_home, is_multi_user_mode


DEFAULT_PUBLIC_PATTERNS = [
    "/auth/*",
    "/share-static/*",
    "/s/*",
    "/static/*",
    "/favicon.ico",
    "/",                 # index.html（前端路由；登录态由前端检查）
    "/api/tenant/config",
    "/api/cockpit/config",
    "/api/_ctx/healthcheck",
    "/api/auth/healthcheck",
    "/api/auth/me",
    "/api/auth/login",   # POST 登录表单
    "/api/auth/logout",
    "/api/auth/magic/request",
    # 分享站公开路径
    "/api/doc/*",
    "/api/registry",
    "/api/user/*/docs",
]


def _path_matches(path: str, patterns: list[str]) -> bool:
    for p in patterns:
        if fnmatch.fnmatch(path, p):
            return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    """
    每请求：
    - 读 cookie 'ome365_sid' → provider.authenticate(request) → User
    - 写 ContextVar（ctx.RequestCtx）供下游代码读
    - 保护路径未登录时重定向到 login_url 或返回 401
    """

    def __init__(
        self,
        app,
        provider,
        session_store=None,
        tenant_config: dict | None = None,
        public_patterns: list[str] | None = None,
        protect_api: bool = True,
    ):
        super().__init__(app)
        self.provider = provider
        self.session_store = session_store
        self.tenant_config = tenant_config or {}
        self.public_patterns = list(public_patterns or DEFAULT_PUBLIC_PATTERNS)
        self.protect_api = protect_api

    async def dispatch(self, request, call_next):
        path = request.url.path
        user = None
        try:
            user = await self.provider.authenticate(request)
        except Exception as e:
            # Provider 炸了不要阻断请求，降级成未登录
            print(f"[auth] provider.authenticate error: {e}")
            user = None

        tenant_id = (user.tenant_id if user else self.tenant_config.get("tenant_id") or "default")
        uid = (user.user_id if user else "captain")

        # 构造 RequestCtx 并注入 ContextVar
        try:
            ctx = RequestCtx(
                tenant_id=tenant_id,
                user_id=uid,
                vault_path=user_vault(tenant_id, uid),
                state_dir=user_state_dir(tenant_id, uid),
                settings_path=user_settings_path(tenant_id, uid),
                tenant_config=load_tenant_config(tenant_id),
                is_multi_user=is_multi_user_mode(),
                user=user,
            )
        except Exception as e:
            print(f"[auth] ctx build error: {e}")
            ctx = None

        token = _ctx_var.set(ctx) if ctx is not None else None

        try:
            # 保护策略：未登录 + 非 public → 拦截
            needs_auth = self._needs_auth(path)
            if needs_auth and user is None:
                if path.startswith("/api/"):
                    return JSONResponse({"error": "unauthorized", "login_url": await self.provider.login_url(path)}, status_code=401)
                return RedirectResponse(await self.provider.login_url(path))
            resp = await call_next(request)
            return resp
        finally:
            if token is not None:
                _ctx_var.reset(token)

    def _needs_auth(self, path: str) -> bool:
        if _path_matches(path, self.public_patterns):
            return False
        if self.protect_api and path.startswith("/api/"):
            return True
        # 其它路径默认放行（前端自己处理登录态）
        return False


def install_auth(app, provider, session_store=None, tenant_config=None, public_patterns=None, protect_api=None):
    """
    在 FastAPI app 上装好 auth 中间件 + 登录/登出/me 三个标准端点。
    """
    from fastapi.responses import JSONResponse, RedirectResponse

    # 保护策略开关：tenant_config.auth.protect_api（默认 True；none provider 建议 False）
    if protect_api is None:
        tcfg = (tenant_config or {}).get("auth") or {}
        protect_api = bool(tcfg.get("protect_api", provider.name != "none"))

    app.add_middleware(
        AuthMiddleware,
        provider=provider,
        session_store=session_store,
        tenant_config=tenant_config,
        public_patterns=public_patterns,
        protect_api=protect_api,
    )

    @app.get("/auth/login")
    async def _login_page(request: Request):
        """登录页（静态 HTML 通过根 static 挂载提供，这里转发）"""
        from pathlib import Path as _P
        login_html = _P(__file__).parent.parent / "static" / "login.html"
        if not login_html.exists():
            return JSONResponse({"error": "login page missing"}, status_code=500)
        from starlette.responses import HTMLResponse
        return HTMLResponse(login_html.read_text("utf-8"))

    @app.get("/api/auth/me")
    async def _me(request: Request):
        u = await provider.authenticate(request)
        if not u:
            return JSONResponse({"authenticated": False, "provider": provider.name}, status_code=200)
        return {"authenticated": True, "provider": provider.name, "user": u.to_dict()}

    @app.post("/api/auth/logout")
    async def _logout(request: Request):
        sid = request.cookies.get("ome365_sid")
        if sid:
            await provider.logout(sid)
        resp = JSONResponse({"ok": True})
        resp.delete_cookie("ome365_sid", path="/")
        return resp

    # Basic provider 登录（表单或 JSON POST）
    @app.post("/api/auth/login")
    async def _login(request: Request):
        if provider.name != "basic":
            return JSONResponse({"error": f"{provider.name} 不支持密码登录"}, status_code=400)
        try:
            if request.headers.get("content-type", "").startswith("application/json"):
                payload = await request.json()
                uid = payload.get("uid") or payload.get("username")
                password = payload.get("password")
                next_url = payload.get("next") or "/"
            else:
                form = await request.form()
                uid = form.get("uid") or form.get("username")
                password = form.get("password")
                next_url = form.get("next") or "/"
        except Exception:
            return JSONResponse({"error": "bad request"}, status_code=400)

        user = await provider.verify_password(uid, password or "")
        if not user:
            return JSONResponse({"error": "invalid credentials"}, status_code=401)
        if session_store is None:
            return JSONResponse({"error": "session store not configured"}, status_code=500)
        sess = session_store.create(user)
        resp = JSONResponse({"ok": True, "user": user.to_dict(), "next": next_url})
        resp.set_cookie(
            "ome365_sid", sess.sid,
            httponly=True, samesite="lax",
            secure=os.environ.get("OME365_COOKIE_SECURE", "0") == "1",
            path="/", max_age=60 * 60 * 24 * 30,
        )
        return resp

    # Magic-link endpoints
    @app.post("/api/auth/magic/request")
    async def _magic_request(request: Request):
        if provider.name != "magic_link":
            return JSONResponse({"error": f"{provider.name} 不支持 magic link"}, status_code=400)
        try:
            if request.headers.get("content-type", "").startswith("application/json"):
                payload = await request.json()
                email = payload.get("email", "")
                next_url = payload.get("next") or "/"
            else:
                form = await request.form()
                email = form.get("email", "")
                next_url = form.get("next") or "/"
        except Exception:
            return JSONResponse({"error": "bad request"}, status_code=400)
        try:
            await provider.request_link(email, next_url=next_url, request=request)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return {"ok": True, "message": "如果该邮箱在允许列表中，登录链接已发送；请查收邮件。"}

    @app.get("/auth/magic/verify")
    async def _magic_verify(request: Request):
        if provider.name != "magic_link":
            return JSONResponse({"error": f"{provider.name} 不支持 magic link"}, status_code=400)
        token = request.query_params.get("token", "")
        next_url = request.query_params.get("next") or "/"
        sess = await provider.verify_token(token)
        if not sess:
            return JSONResponse({"error": "invalid or expired token"}, status_code=401)
        resp = RedirectResponse(next_url)
        resp.set_cookie(
            "ome365_sid", sess.sid,
            httponly=True, samesite="lax",
            secure=os.environ.get("OME365_COOKIE_SECURE", "0") == "1",
            path="/", max_age=60 * 60 * 24 * 30,
        )
        return resp

    return app
