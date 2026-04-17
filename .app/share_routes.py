"""
Ome365 · Share routes (public read-only 访客入口)

这个模块把分享站的所有公共路由抽成 **APIRouter**，供两端复用：

1. share_server.py（兼容进程）把它挂到根 `/`——保留旧 URL `http://:3651/{user}/{slug}`
2. server.py（主站整合）把它挂到前缀 `/s`——新统一 URL `http://:3650/s/{user}/{slug}`

逻辑与以前 share_server.py 一致，只是抽出来做成 APIRouter。VAULT / REGISTRY / TENANT
通过 factory 注入，让两端各自管理运行时常量。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse


_SLUG_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _parse_frontmatter(raw: str) -> dict:
    meta = {}
    lines = raw.split("\n")
    if not lines or lines[0].strip() != "---":
        return meta
    for li in lines[1:]:
        if li.strip() == "---":
            break
        m = re.match(r"^(\w[\w-]*):\s*(.+)$", li)
        if m:
            val = m.group(2).strip()
            if val.startswith("[") and val.endswith("]"):
                val = [v.strip().strip("'\"") for v in val[1:-1].split(",")]
            meta[m[1]] = val
    return meta


def _extract_title(fp: Path) -> str:
    try:
        head = fp.read_text("utf-8")[:600]
        lines = head.split("\n")
        if lines and lines[0].strip() == "---":
            for li in lines[1:]:
                if li.strip() == "---":
                    break
                m = re.match(r"^title:\s*(.+)$", li)
                if m:
                    return m.group(1).strip()
    except Exception:
        pass
    return fp.stem


def build_router(
    *,
    get_vault: Callable[[], Path],
    get_registry_path: Callable[[], Path],
    get_tenant: Callable[[], dict],
    get_static_dir: Callable[[], Path],
    get_reports_dir: Callable[[], Path],
    get_base_url: Callable[[], str],
    prefix: str = "",
) -> APIRouter:
    """
    构造 share 路由集合。

    - prefix="" 时挂根（share_server 兼容模式）
    - prefix="/s" 时挂主站子路径（整合模式）
    """
    r = APIRouter(prefix=prefix)

    # ── Registry helpers（闭包内） ──
    def load_registry() -> dict:
        p = get_registry_path()
        if p.exists():
            return json.loads(p.read_text("utf-8"))
        return {}

    def save_registry(data: dict):
        get_registry_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")

    # ── Tenant / cockpit config ──
    @r.get("/api/tenant/config")
    async def api_tenant_config():
        return get_tenant()

    @r.get("/api/cockpit/config")
    async def api_cockpit_config():
        app_dir = Path(__file__).parent
        live = app_dir / "cockpit_config.json"
        sample = app_dir / "cockpit_config.sample.json"
        fp = live if live.exists() else sample
        if not fp.exists():
            return {"_source": "empty", "ASR_FIXES": [], "KNOWN_SPEAKER_MAPS": {}, "SPEAKER_HINTS": []}
        try:
            data = json.loads(fp.read_text("utf-8"))
            data["_source"] = fp.name
            return data
        except Exception as e:
            return {"_source": "error", "_error": str(e), "ASR_FIXES": [], "KNOWN_SPEAKER_MAPS": {}, "SPEAKER_HINTS": []}

    # ── Registry API ──
    @r.get("/api/registry")
    async def api_registry():
        return load_registry()

    @r.post("/api/register")
    async def api_register(user: str, slug: str, path: str, title: str = ""):
        if not _SLUG_RE.match(slug):
            raise HTTPException(400, "Slug must be alphanumeric/hyphens/underscores, 1-64 chars, start with letter/digit")
        fp = get_vault() / path
        if not fp.exists():
            raise HTTPException(404, f"File not found: {path}")
        reg = load_registry()
        ns = reg.setdefault(user, {})
        if slug in ns:
            existing = ns[slug]["path"]
            if existing != path:
                raise HTTPException(409, f"Slug '{slug}' already registered to a different document: {existing}.")
        old_slugs = [k for k, v in ns.items() if v["path"] == path and k != slug]
        for old in old_slugs:
            del ns[old]
        if not title:
            title = _extract_title(fp)
        from datetime import date
        ns[slug] = {"path": path, "title": title, "created": date.today().isoformat()}
        save_registry(reg)
        base = get_base_url().rstrip("/")
        return {"url": f"{base}{prefix}/{user}/{slug}", "slug": slug, "user": user}

    @r.delete("/api/register")
    async def api_unregister(user: str, slug: str):
        reg = load_registry()
        ns = reg.get(user, {})
        if slug not in ns:
            raise HTTPException(404, "Slug not found")
        del ns[slug]
        if not ns:
            del reg[user]
        save_registry(reg)
        return {"ok": True}

    @r.get("/api/doc/{user}/{slug}")
    async def api_doc_content(user: str, slug: str):
        reg = load_registry()
        ns = reg.get(user, {})
        entry = ns.get(slug)
        if not entry:
            raise HTTPException(404, "Not found")
        fp = get_vault() / entry["path"]
        if not fp.exists():
            raise HTTPException(404, "File missing from vault")
        raw = fp.read_text("utf-8")
        meta = _parse_frontmatter(raw)
        return {"raw": raw, "meta": meta, "title": entry["title"], "slug": slug, "user": user}

    @r.get("/api/user/{user}/docs")
    async def api_user_docs(user: str):
        reg = load_registry()
        ns = reg.get(user)
        if ns is None:
            raise HTTPException(404, "User not found")
        docs = [
            {
                "slug": slug,
                "title": entry.get("title", slug),
                "created": entry.get("created", ""),
                "folder": entry.get("folder", ""),
            }
            for slug, entry in ns.items()
        ]
        docs.sort(key=lambda x: x.get("created", ""), reverse=True)
        folders = sorted({d["folder"] for d in docs if d.get("folder")})
        return {"user": user, "docs": docs, "folders": folders}

    @r.post("/api/user/{user}/folder")
    async def api_create_folder(user: str, name: str):
        return {"ok": True, "folder": name}

    @r.put("/api/user/{user}/doc/{slug}")
    async def api_update_doc_meta(user: str, slug: str, folder: str = None, title: str = None):
        reg = load_registry()
        ns = reg.get(user, {})
        if slug not in ns:
            raise HTTPException(404, "Doc not found")
        if folder is not None:
            ns[slug]["folder"] = folder
        if title is not None:
            ns[slug]["title"] = title
        save_registry(reg)
        return {"ok": True}

    # ── Static files (同名但前缀隔离) ──
    @r.get("/share-static/{filepath:path}")
    async def serve_share_static(filepath: str):
        fp = get_static_dir() / filepath
        if not fp.is_file():
            raise HTTPException(404)
        return FileResponse(fp, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    # ── Viewer pages ──
    @r.get("/{user}")
    async def user_index(user: str):
        reg = load_registry()
        ns = reg.get(user)
        if ns is None:
            raise HTTPException(404, "User not found")
        home_html = get_static_dir() / "share_home.html"
        if home_html.exists():
            content = home_html.read_text("utf-8").replace("{{USER}}", _esc(user))
            return HTMLResponse(content)
        return HTMLResponse(f"<h1>{_esc(user)}</h1><p>Home template not found</p>")

    @r.get("/{user}/{slug}")
    async def user_doc_page(user: str, slug: str):
        reg = load_registry()
        ns = reg.get(user)
        if not ns or slug not in ns:
            raise HTTPException(404, "Not found")
        share_html = get_static_dir() / "share.html"
        return HTMLResponse(share_html.read_text("utf-8"))

    return r
