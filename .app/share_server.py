"""
Ome365 Share Server — 独立只读文档分享站（向后兼容启动器）

启动: cd .app && python3 share_server.py
默认端口: 3651 (可通过 SHARE_PORT 环境变量修改)

v0.9.6 之后业务逻辑搬到 share_routes.py 的 APIRouter；本文件保留为独立进程启动器，
挂同一个 router 到根路径 `/`，维持旧的分享 URL `http://:3651/{user}/{slug}` 工作不变。

部署模式：
  A. 主站+分享站同进程（推荐）—— 直接运行 server.py，分享端走 http://:3650/s/{user}/{slug}
  B. 分享站独立进程（向后兼容）—— 运行此文件，旧 URL 继续可用
  C. 同时跑两个 —— 迁移期常用，老链接走 B，新链接走 A
"""
import os
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from share_routes import build_router


# ── T1 Privacy headers（反爬 + 反嵌入 + 无 referer）──
# 作用：所有经过本进程的响应都带上这几个头，防止 Google/Bing 索引、
# 防止被 iframe 嵌入、防止 referrer 泄漏 URL。
# CSP 选的是宽松版：允许 inline 与 eval，因为 share_home.html / share.html
# 里有 inline script。等 T2 做密码时再做 nonce 收紧。
_T1_HEADERS = {
    "X-Robots-Tag": "noindex, nofollow, noarchive, nosnippet",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Permissions-Policy": "interest-cohort=(), browsing-topics=()",
    "Content-Security-Policy": (
        "default-src 'self' data: blob:; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    ),
}


# ── 运行时常量 ─────────────────────────────────────
VAULT = Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()
PORT = int(os.environ.get("SHARE_PORT", "3651"))
BASE_URL = os.environ.get("SHARE_BASE_URL", f"http://localhost:{PORT}")
REGISTRY_PATH = Path(__file__).parent / "share_registry.json"
STATIC_DIR = Path(__file__).parent / "static"


# ── Tenant config (live → sample fallback) ─────────
_TENANT_LIVE = Path(__file__).parent / "tenant_config.json"
_TENANT_SAMPLE = Path(__file__).parent / "tenant_config.sample.json"


def _load_tenant():
    for fp in (_TENANT_LIVE, _TENANT_SAMPLE):
        if fp.exists():
            try:
                d = json.loads(fp.read_text("utf-8"))
                d.setdefault("_source", fp.name)
                return d
            except Exception as e:
                return {"_source": "error", "_error": str(e)}
    return {"_source": "empty", "brand": {}, "cockpit": {}}


TENANT = _load_tenant()
_reports_rel = ((TENANT.get("reports") or {}).get("dir")) or "reports"
REPORTS_DIR = VAULT / _reports_rel


# ── FastAPI 组装 ───────────────────────────────────
app = FastAPI(title="Ome365 Share")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def add_privacy_headers(request: Request, call_next):
    resp = await call_next(request)
    for k, v in _T1_HEADERS.items():
        resp.headers.setdefault(k, v)
    return resp


# 静态资源挂载——必须在 include_router 之前注册，
# 否则会被 share_routes 的 /{user}/{slug} 通配吃掉。
@app.get("/static/{filepath:path}")
async def serve_static(filepath: str):
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    fp = STATIC_DIR / filepath
    if not fp.is_file():
        raise HTTPException(404)
    return FileResponse(fp, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/reports-static/{filepath:path}")
async def serve_reports_static(filepath: str):
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    fp = REPORTS_DIR / filepath
    if not fp.is_file():
        raise HTTPException(404)
    return FileResponse(fp)


# 主业务路由（挂根，保旧 URL）——在 static 之后注册
router = build_router(
    get_vault=lambda: VAULT,
    get_registry_path=lambda: REGISTRY_PATH,
    get_tenant=lambda: TENANT,
    get_static_dir=lambda: STATIC_DIR,
    get_reports_dir=lambda: REPORTS_DIR,
    get_base_url=lambda: BASE_URL,
    prefix="",
)
app.include_router(router)


if __name__ == "__main__":

    def load_registry():
        if REGISTRY_PATH.exists():
            return json.loads(REGISTRY_PATH.read_text("utf-8"))
        return {}

    reg = load_registry()
    total = sum(len(v) for v in reg.values())
    users = list(reg.keys())
    print(f"\n  Ome365 Share · port {PORT}")
    print(f"  {total} docs · users: {', '.join(users) or '(none)'}")
    print(f"  http://localhost:{PORT}")
    for u in users:
        print(f"    /{u}/ — {len(reg[u])} docs")
    print()

    # Python 3.6 兼容：uvicorn 0.15+ 的 uvicorn.run() 内部用 asyncio.run()（3.7+）。
    # 这里手动拿 event loop，3.6/3.7+ 都走同一路径。
    import asyncio
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(server.serve())
