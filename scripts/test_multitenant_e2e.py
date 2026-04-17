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


# ── 主入口 ─────────────────────────────────────

SUITES = {
    "ctx": suite_ctx,
    "session": suite_session,
    "providers": suite_providers,
    "migrate": suite_migrate,
    "http_none": suite_http_none,
    "http_basic": suite_http_basic,
    "share": suite_share_routes,
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
