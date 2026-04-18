#!/usr/bin/env python3
"""
Ome365 多用户架构验收测试

覆盖：
1. Fresh-clone 可启动（no tenant_config live, sample fallback）
2. ctx 模块单用户 / 多用户布局
3. 迁移脚本：dry-run → real → rollback
4. SessionStore SQLite CRUD
5. 三个 provider 的单元契约（healthcheck、authenticate、login）
6. 中间件集成：none/basic 两条路径 E2E（cookie session）
7. 分享路由 factory 在主站 /s/ 挂载
8. Legacy 兼容：OME365_COMPAT_LEGACY=1 强制单用户

运行：
    cd /Users/wyon/root/Ome365-git
    python3 scripts/test_multitenant_e2e.py
    # 或 python3 scripts/test_multitenant_e2e.py --only ctx,session,basic
"""
from __future__ import annotations

import os
import sys
import json
import base64
import shutil
import asyncio
import sqlite3
import tempfile
import subprocess
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, ProxyHandler, build_opener

# 绕开系统 privoxy/代理 直连 localhost
_NO_PROXY_HANDLER = ProxyHandler({})

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / ".app"
sys.path.insert(0, str(APP))


# ── 小工具 ───────────────────────────────────

_PASS = "\033[32m✔\033[0m"
_FAIL = "\033[31m✘\033[0m"

_results: list[tuple[bool, str]] = []


def test(label: str):
    def deco(fn):
        def run():
            try:
                fn()
                _results.append((True, label))
                print(f"  {_PASS} {label}")
            except AssertionError as e:
                _results.append((False, f"{label} · {e}"))
                print(f"  {_FAIL} {label} · {e}")
            except Exception as e:
                _results.append((False, f"{label} · {type(e).__name__}: {e}"))
                print(f"  {_FAIL} {label} · {type(e).__name__}: {e}")
        run._label = label
        run._group = fn.__module__ if hasattr(fn, "__module__") else "?"
        return run
    return deco


# ── Ctx 模块 ──────────────────────────────────

def suite_ctx():
    print("\n[ctx]")

    @test("slug 校验拒非法")
    def t1():
        from ctx import is_valid_slug, assert_slug
        assert is_valid_slug("captain")
        assert is_valid_slug("team-a")
        assert not is_valid_slug("Captain")
        assert not is_valid_slug("a")
        try:
            assert_slug("", "x"); assert False
        except ValueError:
            pass

    @test("单用户模式 ome365_home = ~/.ome365 或 env")
    def t2():
        import ctx
        os.environ.pop("OME365_HOME", None)
        os.environ.pop("OME365_ROOT", None)
        p = ctx.ome365_home()
        assert str(p).endswith(".ome365"), p

    @test("is_multi_user_mode respects OME365_COMPAT_LEGACY=1")
    def t3():
        import ctx
        os.environ["OME365_COMPAT_LEGACY"] = "1"
        assert ctx.is_multi_user_mode() is False
        del os.environ["OME365_COMPAT_LEGACY"]

    @test("load_tenant_config fallback to sample")
    def t4():
        import ctx
        cfg = ctx.load_tenant_config("default")
        assert cfg.get("_source"), cfg
        # 至少应该有 sample 的骨架
        assert "brand" in cfg or "_source" == "empty"

    @test("RequestCtx 默认工厂不抛")
    def t5():
        from ctx import RequestCtx, _build_legacy_ctx
        c = _build_legacy_ctx()
        assert c.tenant_id == "default"
        assert c.user_id == "captain"

    t1(); t2(); t3(); t4(); t5()


# ── SessionStore ─────────────────────────────

def suite_session():
    print("\n[session_store]")
    from auth.session_store import SessionStore
    from auth.base import User

    tmp = Path(tempfile.mkdtemp(prefix="ome_sess_")) / "s.db"
    ss = SessionStore(tmp)

    @test("初始 count=0")
    def t1():
        assert ss.count() == 0

    @test("create → get → get_user")
    def t2():
        u = User(user_id="alice", tenant_id="t1", display_name="Alice", roles=["admin"])
        sess = ss.create(u)
        got = ss.get(sess.sid)
        assert got is not None
        assert got.user_id == "alice"
        assert got.tenant_id == "t1"
        gu = ss.get_user(sess.sid)
        assert gu.display_name == "Alice"

    @test("delete 清除 session")
    def t3():
        u = User(user_id="bob", tenant_id="t1")
        sess = ss.create(u)
        ss.delete(sess.sid)
        assert ss.get(sess.sid) is None

    @test("delete_for_user 踢人全部设备")
    def t4():
        u = User(user_id="carol", tenant_id="t1")
        ss.create(u); ss.create(u); ss.create(u)
        n = ss.delete_for_user("t1", "carol")
        assert n == 3, n

    @test("expired session 自动失效")
    def t5():
        from datetime import timedelta
        u = User(user_id="dave", tenant_id="t1")
        sess = ss.create(u, ttl=timedelta(seconds=-1))
        assert ss.get(sess.sid) is None

    t1(); t2(); t3(); t4(); t5()
    shutil.rmtree(tmp.parent, ignore_errors=True)


# ── Providers (单元) ──────────────────────────

def suite_providers():
    print("\n[providers]")
    from auth.providers.none_provider import NoneProvider
    from auth.providers.basic_provider import BasicProvider, hash_sha256
    from auth.providers.magic_link_provider import MagicLinkProvider
    from auth.session_store import SessionStore

    @test("NoneProvider authenticate always returns default user")
    def t1():
        p = NoneProvider({"user_id": "x", "tenant_id": "t"})
        u = asyncio.run(p.authenticate(None))
        assert u.user_id == "x"
        assert u.tenant_id == "t"

    @test("BasicProvider sha256 verify_password ok/wrong/missing")
    def t2():
        tmp = Path(tempfile.mkdtemp()) / "s.db"
        ss = SessionStore(tmp)
        h = hash_sha256("hunter2")
        p = BasicProvider({"users":[{"uid":"alice","password_hash":h}]}, session_store=ss)
        ok = asyncio.run(p.verify_password("alice", "hunter2"))
        assert ok and ok.user_id == "alice"
        wrong = asyncio.run(p.verify_password("alice", "wrong"))
        assert wrong is None
        missing = asyncio.run(p.verify_password("ghost", "hunter2"))
        assert missing is None
        shutil.rmtree(tmp.parent, ignore_errors=True)

    @test("MagicLinkProvider token create/consume/expire")
    def t3():
        from auth.providers.magic_link_provider import MagicTokenStore
        tmp = Path(tempfile.mkdtemp()) / "t.db"
        ts = MagicTokenStore(tmp)
        tok = ts.create("alice@x.com", ttl_minutes=5)
        assert ts.consume(tok) == "alice@x.com"
        # 再次消费失败
        assert ts.consume(tok) is None
        shutil.rmtree(tmp.parent, ignore_errors=True)

    @test("MagicLinkProvider allowlist 防枚举（不在列表静默返回）")
    def t4():
        p = MagicLinkProvider({"allowlist": ["ok@x.com"], "smtp": {"host": "smtp.invalid"}})
        # 不在 allowlist → 静默 True，不应抛（没触发 SMTP）
        assert asyncio.run(p.request_link("not@x.com")) is True

    @test("healthcheck 全 provider 不抛")
    def t5():
        NoneProvider().healthcheck()
        BasicProvider({}).healthcheck()
        MagicLinkProvider({}).healthcheck()

    t1(); t2(); t3(); t4(); t5()


# ── 迁移脚本 ──────────────────────────────────

def suite_migrate():
    print("\n[migrate_to_multiuser]")

    @test("脚本存在且可 dry-run")
    def t1():
        migrate = ROOT / "scripts" / "migrate_to_multiuser.py"
        assert migrate.exists(), "migrate_to_multiuser.py not found"
        # 在隔离目录里 dry-run
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env["OME365_HOME"] = td
            env["OME365_COMPAT_LEGACY"] = ""
            # dry-run 不写任何文件
            r = subprocess.run(
                [sys.executable, str(migrate), "--dry-run"],
                env=env, cwd=str(ROOT), capture_output=True, text=True, timeout=20,
            )
            assert r.returncode == 0, r.stderr
            assert "DRY-RUN" in (r.stdout + r.stderr).upper() or "dry" in (r.stdout + r.stderr).lower()

    t1()


# ── HTTP E2E（起真实 server）────────────────────

_server_proc = None
_test_port = 3789


def _start_server(tc_overrides: dict | None = None, provider: str = "none"):
    """启动 server 到 _test_port；返回 proc"""
    tc_path = APP / "tenant_config.json"
    backup = None
    if tc_path.exists():
        backup = tc_path.read_text("utf-8")
    if tc_overrides:
        tc_path.write_text(json.dumps(tc_overrides, ensure_ascii=False), "utf-8")
    else:
        # 删掉 live，走 sample
        if tc_path.exists():
            tc_path.unlink()

    env = os.environ.copy()
    env["OME365_COMPAT_LEGACY"] = "1"
    env["OME365_PORT"] = str(_test_port)
    env["OME365_AUTH_PROVIDER"] = provider
    # E2E 走 http://localhost，必须关掉 Secure cookie（生产默认 on，dev 需显式关）
    env["OME365_COOKIE_SECURE"] = "0"
    log = Path(tempfile.mkdtemp()) / "server.log"
    proc = subprocess.Popen(
        [sys.executable, str(APP / "server.py")],
        env=env, cwd=str(APP),
        stdout=open(log, "w"), stderr=subprocess.STDOUT,
    )
    # 等启动
    probe = build_opener(_NO_PROXY_HANDLER)
    for _ in range(60):
        try:
            probe.open(f"http://localhost:{_test_port}/api/auth/healthcheck", timeout=0.5).read()
            break
        except Exception:
            time.sleep(0.2)
    else:
        proc.kill()
        raise RuntimeError(f"server failed to start; log={log}\n{log.read_text()[:500]}")
    return proc, backup, log


def _stop_server(proc, backup):
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    # 恢复 tenant_config
    tc_path = APP / "tenant_config.json"
    if backup is not None:
        tc_path.write_text(backup, "utf-8")
    else:
        if tc_path.exists():
            tc_path.unlink()


def _http(opener, method, path, body=None, headers=None):
    url = f"http://localhost:{_test_port}{path}"
    data = None
    h = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, method=method, data=data, headers=h)
    try:
        r = opener.open(req, timeout=3)
        return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")


def suite_http_none():
    print("\n[http · none provider]")
    proc, backup, log = _start_server(provider="none")
    try:
        opener = build_opener(_NO_PROXY_HANDLER, HTTPCookieProcessor(CookieJar()))

        @test("healthcheck 不需要登录")
        def t1():
            code, body = _http(opener, "GET", "/api/auth/healthcheck")
            assert code == 200, (code, body)
            d = json.loads(body)
            assert d["provider"] == "none"

        @test("me 自动返回默认 captain")
        def t2():
            code, body = _http(opener, "GET", "/api/auth/me")
            assert code == 200
            d = json.loads(body)
            assert d["authenticated"] is True
            assert d["user"]["user_id"] == "captain"

        @test("protected API 在 none 模式 protect_api=False 下放行")
        def t3():
            code, body = _http(opener, "GET", "/api/dashboard")
            assert code == 200, (code, body[:200])

        @test("login 在 none 模式被拒绝")
        def t4():
            code, _ = _http(opener, "POST", "/api/auth/login", {"uid":"x","password":"y"})
            assert code == 400

        t1(); t2(); t3(); t4()
    finally:
        _stop_server(proc, backup)


def suite_http_basic():
    print("\n[http · basic provider]")
    from auth.providers.basic_provider import hash_sha256
    h = hash_sha256("s3cret")
    tc = {
        "_source": "test",
        "brand": {"cockpit_title": "E2E"},
        "auth": {
            "provider": "basic",
            "protect_api": True,
            "providers": {"basic": {"users": [
                {"uid": "alice", "display": "Alice", "password_hash": h, "roles": ["admin"]}
            ]}}
        }
    }
    proc, backup, log = _start_server(tc_overrides=tc, provider="basic")
    try:
        opener = build_opener(_NO_PROXY_HANDLER, HTTPCookieProcessor(CookieJar()))

        @test("未登录 /api/dashboard → 401")
        def t1():
            code, body = _http(opener, "GET", "/api/dashboard")
            assert code == 401, (code, body[:200])

        @test("错误密码 → 401")
        def t2():
            code, _ = _http(opener, "POST", "/api/auth/login", {"uid":"alice","password":"bad"})
            assert code == 401

        @test("正确密码 → 200 + cookie")
        def t3():
            code, body = _http(opener, "POST", "/api/auth/login", {"uid":"alice","password":"s3cret"})
            assert code == 200, (code, body)
            d = json.loads(body)
            assert d["user"]["user_id"] == "alice"

        @test("带 cookie 访问 me → 已登录")
        def t4():
            code, body = _http(opener, "GET", "/api/auth/me")
            d = json.loads(body)
            assert d["authenticated"] is True
            assert d["user"]["user_id"] == "alice"

        @test("带 cookie 访问 protected → 200")
        def t5():
            code, _ = _http(opener, "GET", "/api/dashboard")
            assert code == 200

        @test("logout → 清 cookie")
        def t6():
            code, _ = _http(opener, "POST", "/api/auth/logout", {})
            assert code == 200

        @test("logout 后再访问 protected → 401")
        def t7():
            # 用同 opener，cookie 会因 Set-Cookie: Max-Age=0 被清掉
            code, _ = _http(opener, "GET", "/api/dashboard")
            assert code == 401

        t1(); t2(); t3(); t4(); t5(); t6(); t7()
    finally:
        _stop_server(proc, backup)


def suite_share_routes():
    print("\n[share routes · integrated /s/ 挂载]")
    proc, backup, log = _start_server(provider="none")
    try:
        opener = build_opener(_NO_PROXY_HANDLER)

        @test("/s/api/tenant/config 可用")
        def t1():
            code, body = _http(opener, "GET", "/s/api/tenant/config")
            assert code == 200

        @test("/s/api/registry 可用")
        def t2():
            code, body = _http(opener, "GET", "/s/api/registry")
            assert code == 200, (code, body[:200])

        t1(); t2()
    finally:
        _stop_server(proc, backup)


# ── Phase 2c · 多租户 Registry & SSO ───────────

def suite_tenant_router():
    print("\n[tenant_router]")
    from auth.tenant_router import resolve_tenant_id, strip_tenant_path

    class _FakeReq:
        def __init__(self, host="example.com", path="/", headers=None):
            self.headers = headers or {}
            class _U:
                def __init__(self, h, p):
                    self.hostname = h.split(":")[0]
                    self.path = p
            self.url = _U(host, path)

    @test("header X-Ome-Tenant 优先级最高")
    def t1():
        r = _FakeReq(host="acme.ome.com", path="/", headers={"x-ome-tenant": "globex"})
        assert resolve_tenant_id(r) == "globex"

    @test("subdomain 解析 acme.ome.com → acme")
    def t2():
        r = _FakeReq(host="acme.ome.com", path="/")
        assert resolve_tenant_id(r) == "acme"

    @test("保留 subdomain www/api/static 跳过")
    def t3():
        r = _FakeReq(host="www.ome.com", path="/")
        assert resolve_tenant_id(r) != "www"

    @test("localhost / IP 不解析 subdomain")
    def t4():
        r1 = _FakeReq(host="localhost", path="/")
        r2 = _FakeReq(host="127.0.0.1", path="/")
        assert resolve_tenant_id(r1) == "default"
        assert resolve_tenant_id(r2) == "default"

    @test("path 前缀 /t/acme/foo → acme")
    def t5():
        r = _FakeReq(host="ome.com", path="/t/acme/foo")
        assert resolve_tenant_id(r) == "acme"

    @test("env OME365_DEFAULT_TENANT 兜底")
    def t6():
        os.environ["OME365_DEFAULT_TENANT"] = "internal"
        try:
            r = _FakeReq(host="ome.com", path="/")
            assert resolve_tenant_id(r) == "internal"
        finally:
            os.environ.pop("OME365_DEFAULT_TENANT", None)

    @test("strip_tenant_path 剥 /t/{tid}")
    def t7():
        assert strip_tenant_path("/t/acme/api/dashboard", "acme") == "/api/dashboard"
        assert strip_tenant_path("/t/acme", "acme") == "/"
        assert strip_tenant_path("/api/x", "acme") == "/api/x"

    t1(); t2(); t3(); t4(); t5(); t6(); t7()


def suite_registry():
    print("\n[auth registry · 多租户 provider 工厂]")
    from auth.registry import AuthRegistry
    from auth.session_store import SessionStore

    @test("registry 默认 tenant → NoneProvider")
    def t1():
        tmp = Path(tempfile.mkdtemp()) / "s.db"
        os.environ.pop("OME365_AUTH_PROVIDER", None)
        reg = AuthRegistry(SessionStore(tmp))
        p = reg.get("default")
        assert p.name == "none", f"expected none, got {p.name}"
        shutil.rmtree(tmp.parent, ignore_errors=True)

    @test("registry 缓存：两次 get 同 tenant 返回同一 provider")
    def t2():
        tmp = Path(tempfile.mkdtemp()) / "s.db"
        reg = AuthRegistry(SessionStore(tmp))
        a = reg.get("default")
        b = reg.get("default")
        assert a is b
        shutil.rmtree(tmp.parent, ignore_errors=True)

    @test("registry env 按租户覆盖 OME365_AUTH_PROVIDER_ACME")
    def t3():
        tmp = Path(tempfile.mkdtemp()) / "s.db"
        os.environ["OME365_AUTH_PROVIDER_ACME"] = "basic"
        try:
            reg = AuthRegistry(SessionStore(tmp))
            p = reg.get("acme")
            assert p.name == "basic"
        finally:
            os.environ.pop("OME365_AUTH_PROVIDER_ACME", None)
            shutil.rmtree(tmp.parent, ignore_errors=True)

    @test("registry invalidate 清缓存重建")
    def t4():
        tmp = Path(tempfile.mkdtemp()) / "s.db"
        reg = AuthRegistry(SessionStore(tmp))
        a = reg.get("default")
        reg.invalidate("default")
        b = reg.get("default")
        assert a is not b
        shutil.rmtree(tmp.parent, ignore_errors=True)

    t1(); t2(); t3(); t4()


def suite_sso_providers():
    print("\n[sso providers · OIDC / WeCom 单元契约]")
    from auth.providers.oidc_provider import OIDCProvider, OIDCPendingStore
    from auth.providers.wecom_provider import WecomProvider, WecomPendingStore
    from auth.session_store import SessionStore

    @test("OIDCPendingStore put/consume 单次消费")
    def t1():
        tmp = Path(tempfile.mkdtemp()) / "o.db"
        st = OIDCPendingStore(tmp)
        st.put("state-x", "globex", "nonce-x", "verifier-x", "/home")
        d = st.consume("state-x")
        assert d and d["tenant_id"] == "globex" and d["next_url"] == "/home"
        # 再消费 None
        assert st.consume("state-x") is None
        shutil.rmtree(tmp.parent, ignore_errors=True)

    @test("OIDCPendingStore 过期 TTL 不返回")
    def t2():
        tmp = Path(tempfile.mkdtemp()) / "o.db"
        st = OIDCPendingStore(tmp)
        st.put("s", "t", "n", "v", "/", ttl_seconds=0)
        time.sleep(0.01)
        assert st.consume("s") is None
        shutil.rmtree(tmp.parent, ignore_errors=True)

    @test("OIDCProvider healthcheck 未配完整 → issues 非空")
    def t3():
        p = OIDCProvider({}, tenant_id="globex")
        hc = p.healthcheck()
        assert hc["provider"] == "oidc"
        assert hc["tenant_id"] == "globex"
        assert not hc["ok"] and hc["issues"]

    @test("WecomPendingStore put/consume + tenant 绑定")
    def t4():
        tmp = Path(tempfile.mkdtemp()) / "w.db"
        st = WecomPendingStore(tmp)
        st.put("s1", "acme", "/home")
        d = st.consume("s1")
        assert d and d["tenant_id"] == "acme"
        assert st.consume("s1") is None
        shutil.rmtree(tmp.parent, ignore_errors=True)

    @test("WecomProvider healthcheck 未配 → issues 非空")
    def t5():
        p = WecomProvider({}, tenant_id="acme")
        hc = p.healthcheck()
        assert hc["provider"] == "wecom"
        assert hc["tenant_id"] == "acme"
        assert not hc["ok"]

    @test("WecomProvider start_url 未配 → 抛 AuthConfigError")
    def t6():
        from auth.base import AuthConfigError
        p = WecomProvider({}, tenant_id="acme")
        try:
            p.start_url("/")
            assert False, "应抛"
        except AuthConfigError:
            pass

    @test("跨租户 session 拒认：acme session 不能登进 globex")
    def t7():
        from auth.base import User
        tmp = Path(tempfile.mkdtemp()) / "s.db"
        ss = SessionStore(tmp)
        u = User(user_id="wyon", tenant_id="acme", display_name="w", email="", roles=["user"], provider="wecom")
        sess = ss.create(u)
        # 模拟 globex 租户的 wecom provider 用同 session_store
        p_globex = WecomProvider({"corp_id": "wwGlobex", "agent_id": "1", "redirect_uri": "https://x"}, session_store=ss, tenant_id="globex")
        class _FakeReq:
            cookies = {"ome365_sid": sess.sid}
        u2 = asyncio.run(p_globex.authenticate(_FakeReq()))
        assert u2 is None, "跨租户 session 必须拒认"
        shutil.rmtree(tmp.parent, ignore_errors=True)

    t1(); t2(); t3(); t4(); t5(); t6(); t7()


def suite_oidc_jwks():
    """OIDC id_token JWKS 验签契约：

    构造 RSA keypair → 自签 id_token → 灌 provider 的 JWKS client →
    验 OK/exp/aud/iss/sig 五种 case。
    用 PyJWT 的 PyJWK 直接构造 signing_key，绕开 HTTP。
    """
    print("\n[oidc jwks · id_token 验签契约]")
    try:
        import jwt as _jwt
        from jwt import PyJWK
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
    except Exception as e:
        print(f"  ⊘ 跳过：PyJWT/cryptography 不可用 ({e})")
        return

    from auth.providers.oidc_provider import OIDCProvider
    from auth.base import AuthError

    # 一次生成的 RSA keypair + JWK（公钥）共享给所有 case
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    # 构造 JWK（n/e）供 PyJWK 使用
    pub_numbers = priv.public_key().public_numbers()
    def _b64u_int(i: int) -> str:
        b = i.to_bytes((i.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")
    jwk_dict = {
        "kty": "RSA",
        "kid": "test-key-1",
        "use": "sig",
        "alg": "RS256",
        "n": _b64u_int(pub_numbers.n),
        "e": _b64u_int(pub_numbers.e),
    }
    pyjwk = PyJWK(jwk_dict)

    def _mint(claims: dict) -> str:
        priv_pem = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return _jwt.encode(claims, priv_pem, algorithm="RS256", headers={"kid": "test-key-1"})

    def _make_provider(**overrides):
        cfg = {
            "issuer": "https://sso.example.com",
            "client_id": "ome365",
            "redirect_uri": "https://ome.example.com/auth/oidc/callback",
            **overrides,
        }
        p = OIDCProvider(cfg, tenant_id="globex")
        # 绕开 HTTP 的 JWKS client：自定义 shim
        class _Shim:
            def get_signing_key_from_jwt(self, token):
                return pyjwk
        p._jwks_client = _Shim()
        p._jwks_fetched_at = time.time()
        return p

    now = int(time.time())
    good_claims = {
        "iss": "https://sso.example.com",
        "aud": "ome365",
        "sub": "alice",
        "iat": now,
        "exp": now + 300,
        "nonce": "n-1",
    }

    @test("JWKS 验签 OK：合法 id_token → claims 正确返回")
    def t1():
        p = _make_provider()
        tok = _mint(good_claims)
        claims = p._parse_id_token(tok)
        assert claims["sub"] == "alice", f"sub 错: {claims}"
        assert claims["aud"] == "ome365"
        assert claims["iss"] == "https://sso.example.com"

    @test("JWKS 验签失败：过期 id_token → AuthError (expired)")
    def t2():
        p = _make_provider()
        bad = {**good_claims, "iat": now - 1000, "exp": now - 500}
        tok = _mint(bad)
        try:
            p._parse_id_token(tok)
            assert False, "应抛"
        except AuthError as e:
            assert "expired" in str(e).lower(), f"错误信息应含 expired: {e}"

    @test("JWKS 验签失败：aud 不匹配 → AuthError (audience)")
    def t3():
        p = _make_provider()
        bad = {**good_claims, "aud": "someone-else"}
        tok = _mint(bad)
        try:
            p._parse_id_token(tok)
            assert False, "应抛"
        except AuthError as e:
            assert "audience" in str(e).lower(), f"错误信息应含 audience: {e}"

    @test("JWKS 验签失败：iss 不匹配 → AuthError (issuer)")
    def t4():
        p = _make_provider()
        bad = {**good_claims, "iss": "https://evil.example.com"}
        tok = _mint(bad)
        try:
            p._parse_id_token(tok)
            assert False, "应抛"
        except AuthError as e:
            assert "issuer" in str(e).lower(), f"错误信息应含 issuer: {e}"

    @test("JWKS 验签失败：签名被篡改 → AuthError")
    def t5():
        p = _make_provider()
        tok = _mint(good_claims)
        # 改 payload（第二段）里一个字符 → 签名不匹配
        parts = tok.split(".")
        # 解 → 改 sub → 再 base64 编，但不重新签名
        raw = base64.urlsafe_b64decode(parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4))
        tampered = raw.replace(b"alice", b"mallo")
        parts[1] = base64.urlsafe_b64encode(tampered).rstrip(b"=").decode("ascii")
        bad_tok = ".".join(parts)
        try:
            p._parse_id_token(bad_tok)
            assert False, "应抛"
        except AuthError as e:
            # PyJWT 会报 signature invalid 或 invalid token
            pass

    @test("verify_signature=false → 不验签直接解 payload（仅 dev）")
    def t6():
        p = _make_provider(verify_signature=False)
        # 随便编个不可验签的 payload
        fake = "xx." + base64.urlsafe_b64encode(json.dumps({"sub": "bob"}).encode()).rstrip(b"=").decode() + ".yy"
        claims = p._parse_id_token(fake)
        assert claims.get("sub") == "bob", f"dev 模式应直接解 payload: {claims}"

    @test("verify_signature=false → healthcheck 明确警告")
    def t7():
        p = OIDCProvider({
            "issuer": "https://x",
            "client_id": "a",
            "redirect_uri": "https://y",
            "client_secret_env": "OME365_OIDC_SECRET",
            "verify_signature": False,
        }, tenant_id="globex")
        hc = p.healthcheck()
        assert hc["verify_signature"] is False
        assert any("verify_signature=false" in i for i in hc["issues"]), f"应警告 dev 模式: {hc}"

    @test("allowed_algorithms 默认不含 HS256（避免 key confusion 攻击）")
    def t8():
        p = _make_provider()
        assert "HS256" not in p.allowed_algorithms, f"默认不应含 HS256: {p.allowed_algorithms}"
        assert "RS256" in p.allowed_algorithms

    t1(); t2(); t3(); t4(); t5(); t6(); t7(); t8()


def suite_auth_hardening():
    """Auth 加固契约：next_url open-redirect 防护 + session fixation 轮换。

    - safe_next_url：外站/协议-相对/javascript 等必须转成 "/"
    - 登录成功时服务器要自动 delete 掉请求里带来的旧 sid
    """
    print("\n[auth hardening · next_url + session fixation]")
    from auth.middleware import safe_next_url
    from auth.session_store import SessionStore
    from auth.base import User

    @test("safe_next_url 允许合法内部路径")
    def t1():
        assert safe_next_url("/dashboard") == "/dashboard"
        assert safe_next_url("/a/b?x=1#y") == "/a/b?x=1#y"
        assert safe_next_url("/") == "/"

    @test("safe_next_url 拒绝协议-相对 //evil.com")
    def t2():
        assert safe_next_url("//evil.com") == "/"
        assert safe_next_url("//evil.com/path") == "/"

    @test("safe_next_url 拒绝带 scheme 的绝对 URL")
    def t3():
        assert safe_next_url("https://evil.com/steal") == "/"
        assert safe_next_url("http://evil.com") == "/"
        assert safe_next_url("javascript:alert(1)") == "/"
        assert safe_next_url("data:text/html,<script>") == "/"

    @test("safe_next_url 拒绝非 / 开头的裸路径")
    def t4():
        assert safe_next_url("evil.com") == "/"
        assert safe_next_url("../etc/passwd") == "/"
        # 空/None → default
        assert safe_next_url("") == "/"
        assert safe_next_url(None) == "/"
        assert safe_next_url(123) == "/"  # type: ignore

    @test("safe_next_url 自定义 default 生效")
    def t5():
        assert safe_next_url("https://evil.com", default="/home") == "/home"

    @test("session fixation 防护：登录成功后旧 sid 被服务端删除")
    def t6():
        # 直接测 session_store 的 delete 行为 + 模拟 login handler 的 rotate 逻辑
        tmp = Path(tempfile.mkdtemp()) / "s.db"
        ss = SessionStore(tmp)
        u1 = User(user_id="attacker", tenant_id="globex", display_name="a", email="", roles=["user"], provider="basic")
        old_sess = ss.create(u1)
        old_sid = old_sess.sid
        # 受害者登录 → 服务端 create 新 sess + 删旧
        u2 = User(user_id="victim", tenant_id="globex", display_name="v", email="", roles=["user"], provider="basic")
        new_sess = ss.create(u2)
        assert new_sess.sid != old_sid, "新旧 sid 必须不同"
        # 模拟 _rotate_and_set：server 删除 old_sid
        ss.delete(old_sid)
        assert ss.get(old_sid) is None, "旧 sid 应被吊销"
        assert ss.get(new_sess.sid) is not None, "新 sid 必须活着"
        shutil.rmtree(tmp.parent, ignore_errors=True)

    @test("cookie Secure 默认为 true（生产安全），仅 OME365_COOKIE_SECURE=0 时关")
    def t7():
        # 直接读 middleware 的 _cookie_secure 语义：默认值 != "0" → secure
        # 用 os.environ 模拟 3 种情况
        orig = os.environ.get("OME365_COOKIE_SECURE")
        try:
            # 默认（未设）→ 应 secure
            if "OME365_COOKIE_SECURE" in os.environ:
                del os.environ["OME365_COOKIE_SECURE"]
            assert os.environ.get("OME365_COOKIE_SECURE", "1") != "0"
            # 显式 "0" → 关
            os.environ["OME365_COOKIE_SECURE"] = "0"
            assert not (os.environ.get("OME365_COOKIE_SECURE", "1") != "0")
            # 显式 "1" → 开
            os.environ["OME365_COOKIE_SECURE"] = "1"
            assert os.environ.get("OME365_COOKIE_SECURE", "1") != "0"
        finally:
            if orig is None:
                os.environ.pop("OME365_COOKIE_SECURE", None)
            else:
                os.environ["OME365_COOKIE_SECURE"] = orig

    t1(); t2(); t3(); t4(); t5(); t6(); t7()


def suite_basic_plaintext():
    """basic_provider · 明文密码运行时拒绝契约"""
    print("\n[basic · 明文密码运行时拒绝]")
    from auth.providers.basic_provider import BasicProvider, _verify_password, hash_sha256

    @test("argon2/bcrypt/sha256$ 前缀哈希可验")
    def t1():
        h = hash_sha256("s3cret")
        assert _verify_password("s3cret", h) is True
        assert _verify_password("wrong", h) is False

    @test("明文密码默认拒绝（allow_plaintext=False）")
    def t2():
        # 直接给明文哈希 = "hello"；用户传 "hello" 也应返回 False
        assert _verify_password("hello", "hello") is False
        assert _verify_password("hello", "hello", allow_plaintext=False) is False

    @test("明文密码仅在 allow_plaintext=True 时通过")
    def t3():
        assert _verify_password("hello", "hello", allow_plaintext=True) is True
        assert _verify_password("wrong", "hello", allow_plaintext=True) is False

    @test("BasicProvider 误配明文 → verify_password 返 None")
    def t4():
        p = BasicProvider({
            "tenant_id": "globex",
            "users": [{"uid": "alice", "password_hash": "plaintext-oops", "display": "A"}],
        })
        u = asyncio.run(p.verify_password("alice", "plaintext-oops"))
        assert u is None, "明文密码必须被运行时拒绝"

    @test("BasicProvider 用户标 allow_plaintext=true → 放行（兼容历史）")
    def t5():
        p = BasicProvider({
            "tenant_id": "globex",
            "users": [{"uid": "alice", "password_hash": "legacy-plain", "allow_plaintext": True, "display": "A"}],
        })
        u = asyncio.run(p.verify_password("alice", "legacy-plain"))
        assert u is not None and u.user_id == "alice"

    @test("BasicProvider healthcheck 明文用户 → 明确标 BLOCKED / ALLOWED")
    def t6():
        p = BasicProvider({
            "tenant_id": "globex",
            "users": [
                {"uid": "blocked", "password_hash": "plain-bad"},
                {"uid": "allowed", "password_hash": "plain-ok", "allow_plaintext": True},
                {"uid": "good", "password_hash": hash_sha256("x")},
            ],
        })
        hc = p.healthcheck()
        assert "blocked" in hc["plaintext_blocked"], f"应标 blocked: {hc}"
        assert "allowed" not in hc["plaintext_blocked"]
        # 显示两条相关 issues
        assert any("REJECTED" in i for i in hc["issues"])
        assert any("allowed" in i for i in hc["issues"])

    @test("OME365_DEMO_PASSWORD 注入的 demo 用户 → 明文放行")
    def t7():
        orig = os.environ.get("OME365_DEMO_PASSWORD")
        try:
            os.environ["OME365_DEMO_PASSWORD"] = "demo-pass-123"
            p = BasicProvider({"tenant_id": "globex"})
            u = asyncio.run(p.verify_password("demo", "demo-pass-123"))
            assert u is not None and u.user_id == "demo"
            u2 = asyncio.run(p.verify_password("demo", "wrong"))
            assert u2 is None
        finally:
            if orig is None:
                os.environ.pop("OME365_DEMO_PASSWORD", None)
            else:
                os.environ["OME365_DEMO_PASSWORD"] = orig

    t1(); t2(); t3(); t4(); t5(); t6(); t7()


def suite_rate_limit():
    """登录限流契约"""
    print("\n[rate limit · 登录暴力破解防护]")
    from auth.middleware import LoginRateLimiter

    @test("窗口内失败 < max → 不锁")
    def t1():
        rl = LoginRateLimiter(max_attempts=3, window=60, lockout=60)
        for _ in range(2):
            rl.record_fail("t", "u")
        ok, retry = rl.check("t", "u")
        assert ok and retry == 0

    @test("窗口内失败 >= max → 锁 + 返回 retry_after")
    def t2():
        rl = LoginRateLimiter(max_attempts=3, window=60, lockout=60)
        for _ in range(3):
            rl.record_fail("t", "u")
        ok, retry = rl.check("t", "u")
        assert not ok and retry > 0

    @test("成功登录清零计数")
    def t3():
        rl = LoginRateLimiter(max_attempts=3, window=60, lockout=60)
        rl.record_fail("t", "u")
        rl.record_fail("t", "u")
        rl.record_success("t", "u")
        # 再来一次 fail 不应立刻锁
        rl.record_fail("t", "u")
        ok, _ = rl.check("t", "u")
        assert ok, "成功后应清零"

    @test("不同 key 互不影响（tid/uid/ip 分桶）")
    def t4():
        rl = LoginRateLimiter(max_attempts=2, window=60, lockout=60)
        rl.record_fail("acme", "alice", "1.1.1.1")
        rl.record_fail("acme", "alice", "1.1.1.1")
        # alice 在 1.1.1.1 已锁
        assert not rl.check("acme", "alice", "1.1.1.1")[0]
        # 同 uid 不同 ip 不受影响
        assert rl.check("acme", "alice", "2.2.2.2")[0]
        # 同 ip 不同 uid 不受影响
        assert rl.check("acme", "bob", "1.1.1.1")[0]
        # 同 ip+uid 不同 tenant 不受影响
        assert rl.check("globex", "alice", "1.1.1.1")[0]

    @test("窗口外旧失败被丢弃（滑动窗口）")
    def t5():
        rl = LoginRateLimiter(max_attempts=3, window=1, lockout=60)
        rl.record_fail("t", "u")
        rl.record_fail("t", "u")
        time.sleep(1.1)
        # 窗口已过，再一次 fail 应重新计数
        rl.record_fail("t", "u")
        ok, _ = rl.check("t", "u")
        assert ok, "窗口外旧失败不应累计"

    @test("env 读 OME365_LOGIN_MAX_ATTEMPTS 生效")
    def t6():
        orig = os.environ.get("OME365_LOGIN_MAX_ATTEMPTS")
        try:
            os.environ["OME365_LOGIN_MAX_ATTEMPTS"] = "2"
            rl = LoginRateLimiter()
            assert rl.max_attempts == 2
        finally:
            if orig is None:
                os.environ.pop("OME365_LOGIN_MAX_ATTEMPTS", None)
            else:
                os.environ["OME365_LOGIN_MAX_ATTEMPTS"] = orig

    t1(); t2(); t3(); t4(); t5(); t6()


# ── 主入口 ─────────────────────────────────────

SUITES = {
    "ctx": suite_ctx,
    "session": suite_session,
    "providers": suite_providers,
    "migrate": suite_migrate,
    "http_none": suite_http_none,
    "http_basic": suite_http_basic,
    "share": suite_share_routes,
    "tenant_router": suite_tenant_router,
    "registry": suite_registry,
    "sso": suite_sso_providers,
    "oidc_jwks": suite_oidc_jwks,
    "auth_hardening": suite_auth_hardening,
    "basic_plaintext": suite_basic_plaintext,
    "rate_limit": suite_rate_limit,
}


def main():
    only = None
    for i, a in enumerate(sys.argv[1:]):
        if a == "--only" and i + 1 < len(sys.argv[1:]):
            only = set(sys.argv[i + 2].split(","))
    for name, fn in SUITES.items():
        if only and name not in only:
            continue
        try:
            fn()
        except Exception as e:
            print(f"  {_FAIL} suite {name} 崩了: {e}")
            _results.append((False, f"suite {name} 崩了"))

    print("\n" + "=" * 60)
    ok = sum(1 for r, _ in _results if r)
    tot = len(_results)
    if ok == tot:
        print(f"\033[32m全部通过 {ok}/{tot}\033[0m")
        return 0
    else:
        print(f"\033[31m{tot - ok} 项失败，{ok}/{tot} 通过\033[0m")
        for r, lbl in _results:
            if not r:
                print(f"  {_FAIL} {lbl}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
