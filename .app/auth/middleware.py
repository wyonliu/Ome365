"""
Ome365 · Auth 中间件（多租户 · registry 模式）

职责：
1. 解析请求的 tenant_id（subdomain / path / header / env）
2. 从 AuthRegistry 取该租户的 AuthProvider
3. 用 provider.authenticate 解 cookie → User（且校验 user.tenant_id 匹配）
4. 注入 RequestCtx（含 provider & tid）到 ContextVar
5. 保护路径未登录 → 302 到 provider.login_url 或 401

企业 A 的企微扫码只能登进企业 A 租户；企业 B 的 OIDC 只能登进企业 B 租户。
跨租户 cookie 由 middleware 拒认（provider.authenticate 内部比 tenant_id）。
"""
from __future__ import annotations

import os
import time
import fnmatch
import threading
from typing import Optional, Callable
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from starlette.requests import Request  # 放模块级，FastAPI 通过 __globals__ 解析类型注解

try:
    from ctx import RequestCtx, _ctx_var, load_tenant_config, user_vault, user_state_dir, user_settings_path, ome365_home, is_multi_user_mode
    from auth.tenant_router import resolve_tenant_id
    from auth.registry import AuthRegistry
except ImportError:  # pragma: no cover
    from ..ctx import RequestCtx, _ctx_var, load_tenant_config, user_vault, user_state_dir, user_settings_path, ome365_home, is_multi_user_mode
    from .tenant_router import resolve_tenant_id
    from .registry import AuthRegistry


DEFAULT_PUBLIC_PATTERNS = [
    "/auth/*",
    "/share-static/*",
    "/s/*",
    "/static/*",
    "/favicon.ico",
    "/",
    "/api/tenant/config",
    "/api/cockpit/config",
    "/api/_ctx/healthcheck",
    "/api/auth/healthcheck",
    "/api/auth/me",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/magic/request",
    "/api/doc/*",
    "/api/registry",
    "/api/user/*/docs",
]


def _path_matches(path: str, patterns: list[str]) -> bool:
    for p in patterns:
        if fnmatch.fnmatch(path, p):
            return True
    return False


class LoginRateLimiter:
    """进程内登录限流：防 basic / magic_link 暴力破解。

    规则：窗口 WINDOW 秒内失败 ≥ MAX_ATTEMPTS → 锁 LOCKOUT 秒。
    Key = (tenant_id, uid 或 email 或 client_ip)。成功登录清零。
    env：
      OME365_LOGIN_MAX_ATTEMPTS (default 5)
      OME365_LOGIN_WINDOW_SECONDS (default 300)
      OME365_LOGIN_LOCKOUT_SECONDS (default 900)

    注意：进程内 dict，多进程部署请用 Redis 替换（换 store 即可）。
    """

    def __init__(self, max_attempts: int | None = None, window: int | None = None, lockout: int | None = None):
        self.max_attempts = int(max_attempts if max_attempts is not None else os.environ.get("OME365_LOGIN_MAX_ATTEMPTS", "5"))
        self.window = int(window if window is not None else os.environ.get("OME365_LOGIN_WINDOW_SECONDS", "300"))
        self.lockout = int(lockout if lockout is not None else os.environ.get("OME365_LOGIN_LOCKOUT_SECONDS", "900"))
        self._attempts: dict[tuple, list[float]] = {}
        self._lockout: dict[tuple, float] = {}
        self._lock = threading.Lock()

    def check(self, *keys) -> tuple[bool, int]:
        """返回 (allowed, retry_after_seconds)。allowed=False 时 retry_after>0。"""
        now = time.time()
        key = tuple(keys)
        with self._lock:
            until = self._lockout.get(key, 0.0)
            if now < until:
                return False, max(1, int(until - now))
        return True, 0

    def record_fail(self, *keys) -> None:
        now = time.time()
        key = tuple(keys)
        with self._lock:
            lst = [t for t in self._attempts.get(key, []) if now - t < self.window]
            lst.append(now)
            self._attempts[key] = lst
            if len(lst) >= self.max_attempts:
                self._lockout[key] = now + self.lockout

    def record_success(self, *keys) -> None:
        key = tuple(keys)
        with self._lock:
            self._attempts.pop(key, None)
            self._lockout.pop(key, None)

    def reset(self) -> None:
        """测试用。"""
        with self._lock:
            self._attempts.clear()
            self._lockout.clear()


def safe_next_url(next_url: str | None, default: str = "/") -> str:
    """Open-redirect 防护：next_url 必须是本站相对路径。

    拒绝：
      - 协议-相对 "//evil.com/..."（浏览器会当外站跳）
      - 带 scheme 的绝对 URL "https://evil.com/..."
      - javascript:/data: 等 scheme
      - 非 "/" 开头的 "evil.com" 这类裸域名

    允许：以 "/" 开头（非 "//"）且无 scheme/netloc 的 path（可带 query/fragment）。
    """
    if not next_url or not isinstance(next_url, str):
        return default
    if next_url.startswith("//"):
        return default
    if not next_url.startswith("/"):
        return default
    try:
        p = urlparse(next_url)
    except Exception:
        return default
    if p.scheme or p.netloc:
        return default
    return next_url


class AuthMiddleware(BaseHTTPMiddleware):
    """每请求：解租户 → 取 provider → 解 session → 注入 ctx → 放行或拦截"""

    def __init__(
        self,
        app,
        registry: AuthRegistry,
        public_patterns: list[str] | None = None,
        default_protect_api: bool = True,
    ):
        super().__init__(app)
        self.registry = registry
        self.public_patterns = list(public_patterns or DEFAULT_PUBLIC_PATTERNS)
        self.default_protect_api = default_protect_api

    async def dispatch(self, request, call_next):
        path = request.url.path
        tid = resolve_tenant_id(request)
        provider = self.registry.get(tid)

        # 取当前租户的保护开关
        tcfg = load_tenant_config(tid) or {}
        acfg = tcfg.get("auth") or {}
        protect_api = bool(acfg.get("protect_api", self.default_protect_api if provider.name != "none" else False))

        user = None
        try:
            user = await provider.authenticate(request)
        except Exception as e:
            print(f"[auth] provider.authenticate error (tid={tid}): {e}")
            user = None

        uid = (user.user_id if user else "captain")
        # 构造 RequestCtx
        try:
            ctx = RequestCtx(
                tenant_id=tid,
                user_id=uid,
                vault_path=user_vault(tid, uid),
                state_dir=user_state_dir(tid, uid),
                settings_path=user_settings_path(tid, uid),
                tenant_config=tcfg,
                is_multi_user=is_multi_user_mode(),
                user=user,
            )
        except Exception as e:
            print(f"[auth] ctx build error (tid={tid}): {e}")
            ctx = None

        token = _ctx_var.set(ctx) if ctx is not None else None

        try:
            if self._needs_auth(path, protect_api) and user is None:
                login_url = await provider.login_url(path)
                if path.startswith("/api/"):
                    return JSONResponse(
                        {"error": "unauthorized", "tenant": tid, "provider": provider.name, "login_url": login_url},
                        status_code=401,
                    )
                return RedirectResponse(login_url)
            return await call_next(request)
        finally:
            if token is not None:
                _ctx_var.reset(token)

    def _needs_auth(self, path: str, protect_api: bool) -> bool:
        if _path_matches(path, self.public_patterns):
            return False
        if protect_api and path.startswith("/api/"):
            return True
        return False


# ──────────────────────────────────────────────────
# Install: middleware + 通用登录端点
# ──────────────────────────────────────────────────

def install_auth(app, registry: AuthRegistry, public_patterns=None, default_protect_api: bool = True, rate_limiter: LoginRateLimiter | None = None):
    """
    装中间件 + 全部登录端点。
    所有端点都按请求里解析出的 tenant_id 取对应 provider，不依赖单例。
    rate_limiter 不传则用默认参数（5 次 / 5 分钟 / 锁 15 分钟）。
    """
    from fastapi.responses import JSONResponse, RedirectResponse
    from starlette.responses import HTMLResponse
    from pathlib import Path as _P

    _rate = rate_limiter or LoginRateLimiter()
    # 挂到 app.state 供外部（测试/管理端）访问
    try:
        app.state.login_rate_limiter = _rate
    except Exception:
        pass

    app.add_middleware(
        AuthMiddleware,
        registry=registry,
        public_patterns=public_patterns,
        default_protect_api=default_protect_api,
    )

    def _prov(request: Request):
        tid = resolve_tenant_id(request)
        return tid, registry.get(tid)

    def _client_ip(request: Request) -> str:
        # 反代下优先 X-Forwarded-For 首个
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip()
        return (request.client.host if request.client else "") or ""

    def _cookie_secure() -> bool:
        """默认 secure=true（生产 HTTPS）。仅 OME365_COOKIE_SECURE=0 时关（本地 http dev）。"""
        return os.environ.get("OME365_COOKIE_SECURE", "1") != "0"

    def _set_session_cookie(resp, sid: str):
        resp.set_cookie(
            "ome365_sid", sid,
            httponly=True, samesite="lax",
            secure=_cookie_secure(),
            path="/", max_age=60 * 60 * 24 * 30,
        )

    def _rotate_and_set(request: Request, resp, new_sid: str) -> None:
        """Session fixation 防护：登录成功时先吊销请求里带的旧 sid，再下发新 cookie。

        即使攻击者在受害者浏览器里预埋 ome365_sid=ATTACKER_SID，
        登录成功后旧 sid 会从 session_store 删掉 + 被新 Set-Cookie 覆盖。
        """
        old_sid = request.cookies.get("ome365_sid")
        if old_sid and old_sid != new_sid:
            try:
                registry.session_store.delete(old_sid)
            except Exception:
                pass
        _set_session_cookie(resp, new_sid)

    @app.get("/auth/login")
    async def _login_page(request: Request):
        login_html = _P(__file__).parent.parent / "static" / "login.html"
        if not login_html.exists():
            return JSONResponse({"error": "login page missing"}, status_code=500)
        return HTMLResponse(login_html.read_text("utf-8"))

    @app.get("/api/auth/me")
    async def _me(request: Request):
        tid, provider = _prov(request)
        u = await provider.authenticate(request)
        if not u:
            return JSONResponse({"authenticated": False, "tenant": tid, "provider": provider.name}, status_code=200)
        return {"authenticated": True, "tenant": tid, "provider": provider.name, "user": u.to_dict()}

    @app.post("/api/auth/logout")
    async def _logout(request: Request):
        _, provider = _prov(request)
        sid = request.cookies.get("ome365_sid")
        if sid:
            await provider.logout(sid)
        resp = JSONResponse({"ok": True})
        resp.delete_cookie("ome365_sid", path="/")
        return resp

    # ── basic ──
    @app.post("/api/auth/login")
    async def _login(request: Request):
        tid, provider = _prov(request)
        if provider.name != "basic":
            return JSONResponse({"error": f"tenant '{tid}' uses {provider.name}, not basic", "provider": provider.name}, status_code=400)
        try:
            if request.headers.get("content-type", "").startswith("application/json"):
                payload = await request.json()
                uid = payload.get("uid") or payload.get("username")
                password = payload.get("password")
                next_url = safe_next_url(payload.get("next"))
            else:
                form = await request.form()
                uid = form.get("uid") or form.get("username")
                password = form.get("password")
                next_url = safe_next_url(form.get("next"))
        except Exception:
            return JSONResponse({"error": "bad request"}, status_code=400)

        # 限流：(tid, uid, client_ip) —— 按 uid 锁定也按 ip 锁定，防撒网
        ip = _client_ip(request)
        ok, retry = _rate.check(tid, "basic", str(uid or "").lower(), ip)
        if not ok:
            return JSONResponse(
                {"error": "too many attempts, temporarily locked", "retry_after": retry},
                status_code=429,
                headers={"Retry-After": str(retry)},
            )

        user = await provider.verify_password(uid, password or "")
        if not user:
            _rate.record_fail(tid, "basic", str(uid or "").lower(), ip)
            return JSONResponse({"error": "invalid credentials"}, status_code=401)
        _rate.record_success(tid, "basic", str(uid or "").lower(), ip)
        sess = registry.session_store.create(user)
        resp = JSONResponse({"ok": True, "user": user.to_dict(), "next": next_url, "tenant": tid})
        _rotate_and_set(request, resp, sess.sid)
        return resp

    # ── magic_link ──
    @app.post("/api/auth/magic/request")
    async def _magic_request(request: Request):
        tid, provider = _prov(request)
        if provider.name != "magic_link":
            return JSONResponse({"error": f"tenant '{tid}' uses {provider.name}, not magic_link"}, status_code=400)
        try:
            if request.headers.get("content-type", "").startswith("application/json"):
                payload = await request.json()
                email = payload.get("email", "")
                next_url = safe_next_url(payload.get("next"))
            else:
                form = await request.form()
                email = form.get("email", "")
                next_url = safe_next_url(form.get("next"))
        except Exception:
            return JSONResponse({"error": "bad request"}, status_code=400)
        # 限流：防邮件枚举 + SMTP 轰炸
        ip = _client_ip(request)
        ok, retry = _rate.check(tid, "magic", str(email or "").lower(), ip)
        if not ok:
            return JSONResponse(
                {"error": "too many requests, please try later", "retry_after": retry},
                status_code=429,
                headers={"Retry-After": str(retry)},
            )
        try:
            await provider.request_link(email, next_url=next_url, request=request)
        except Exception as e:
            _rate.record_fail(tid, "magic", str(email or "").lower(), ip)
            return JSONResponse({"error": str(e)}, status_code=400)
        # 成功触发了邮件发送也算一次 request（防同一 email 无限请求）；但不直接锁死
        _rate.record_fail(tid, "magic", str(email or "").lower(), ip)
        return {"ok": True, "tenant": tid, "message": "如邮箱在允许列表，登录链接已发送。"}

    @app.get("/auth/magic/verify")
    async def _magic_verify(request: Request):
        tid, provider = _prov(request)
        if provider.name != "magic_link":
            return JSONResponse({"error": f"tenant '{tid}' uses {provider.name}, not magic_link"}, status_code=400)
        token = request.query_params.get("token", "")
        next_url = safe_next_url(request.query_params.get("next"))
        sess = await provider.verify_token(token)
        if not sess:
            return JSONResponse({"error": "invalid or expired token"}, status_code=401)
        resp = RedirectResponse(next_url)
        _rotate_and_set(request, resp, sess.sid)
        return resp

    # ── OIDC ──
    @app.get("/auth/oidc/start")
    async def _oidc_start(request: Request):
        tid, provider = _prov(request)
        if provider.name != "oidc":
            return JSONResponse({"error": f"tenant '{tid}' uses {provider.name}, not oidc"}, status_code=400)
        next_url = safe_next_url(request.query_params.get("next"))
        try:
            url = provider.start_url(next_url)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
        return RedirectResponse(url)

    @app.get("/auth/oidc/callback")
    async def _oidc_callback(request: Request):
        # 注意：state 里签了 tid；这里先看 pending store 解 tid，然后取对应 provider
        state = request.query_params.get("state", "")
        pending = registry.oidc_pending
        # 窥视一下 state 里的 tid（不消费，provider.callback 会消费）
        # 为避免窥视后再消费的 TOCTOU，改为：按当前 request 解析 tid 即可——
        # 正常情况下 redirect_uri 就是租户专属 URL（不同 subdomain），自然回到对的租户。
        tid, provider = _prov(request)
        if provider.name != "oidc":
            return JSONResponse({"error": f"callback for oidc but tenant '{tid}' uses {provider.name}"}, status_code=400)
        try:
            sess = await provider.callback(request)
        except Exception as e:
            return JSONResponse({"error": str(e), "tenant": tid}, status_code=401)
        if not sess:
            return JSONResponse({"error": "callback returned no session"}, status_code=401)
        next_url = safe_next_url((sess.data or {}).get("_next_url"))
        resp = RedirectResponse(next_url)
        _rotate_and_set(request, resp, sess.sid)
        return resp

    # ── Wecom ──
    @app.get("/auth/wecom/start")
    async def _wecom_start(request: Request):
        tid, provider = _prov(request)
        if provider.name != "wecom":
            return JSONResponse({"error": f"tenant '{tid}' uses {provider.name}, not wecom"}, status_code=400)
        next_url = safe_next_url(request.query_params.get("next"))
        try:
            url = provider.start_url(next_url)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
        return RedirectResponse(url)

    @app.get("/auth/wecom/callback")
    async def _wecom_callback(request: Request):
        tid, provider = _prov(request)
        if provider.name != "wecom":
            return JSONResponse({"error": f"callback for wecom but tenant '{tid}' uses {provider.name}"}, status_code=400)
        try:
            sess = await provider.callback(request)
        except Exception as e:
            return JSONResponse({"error": str(e), "tenant": tid}, status_code=401)
        if not sess:
            return JSONResponse({"error": "callback returned no session"}, status_code=401)
        next_url = safe_next_url((sess.data or {}).get("_next_url"))
        resp = RedirectResponse(next_url)
        _rotate_and_set(request, resp, sess.sid)
        return resp

    # ── 健康检查 ──
    @app.get("/api/auth/healthcheck")
    async def _auth_hc(request: Request):
        tid, provider = _prov(request)
        hc = provider.healthcheck()
        hc["tenant_id"] = tid
        hc["sessions"] = registry.session_store.count()
        return hc

    return app
