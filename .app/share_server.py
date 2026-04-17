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
from __future__ import annotations

import os
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from share_routes import build_router


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

# 主业务路由（挂根，保旧 URL）
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


# 静态资源挂载（保旧路径）
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

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
