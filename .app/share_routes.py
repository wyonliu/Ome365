"""
Ome365 · Share routes (public read-only 访客入口)

这个模块把分享站的所有公共路由抽成 **APIRouter**，供两端复用：

1. share_server.py（兼容进程）把它挂到根 `/`——保留旧 URL `http://:3651/{user}/{slug}`
2. server.py（主站整合）把它挂到前缀 `/s`——新统一 URL `http://:3650/s/{user}/{slug}`

逻辑与以前 share_server.py 一致，只是抽出来做成 APIRouter。VAULT / REGISTRY / TENANT
通过 factory 注入，让两端各自管理运行时常量。
"""
import json
import re
from pathlib import Path
from typing import Callable

import hmac
import os

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header, Request
from fastapi.responses import HTMLResponse, FileResponse
from typing import List, Optional


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

    # ── Publish token（SSH 被锁时的 HTTPS 推文件通道）──
    #   读取顺序：env OME365_PUBLISH_TOKEN > /data/ome365/.app/publish_token
    #   为空 → /api/publish 返回 501 关闭；有值 → 必须 X-Publish-Token 匹配
    def load_publish_token() -> str:
        tok = os.environ.get("OME365_PUBLISH_TOKEN", "").strip()
        if tok:
            return tok
        fp = Path(__file__).parent / "publish_token"
        if fp.exists():
            return fp.read_text("utf-8").strip()
        return ""

    def _safe_rel_path(p: str) -> Path:
        """拒绝 ../ / 绝对路径 / Windows 盘符。"""
        if not p or ".." in p.replace("\\", "/").split("/"):
            raise HTTPException(400, f"unsafe path: {p}")
        pp = Path(p)
        if pp.is_absolute() or (len(p) > 1 and p[1] == ":"):
            raise HTTPException(400, f"absolute path not allowed: {p}")
        return pp

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

    @r.post("/api/publish")
    async def api_publish(
        request: Request,
        user: str = Form(...),
        slug: str = Form(...),
        path: str = Form(...),          # doc 相对 vault 根的路径
        title: str = Form(""),
        doc: UploadFile = File(...),    # markdown 正文
        images: List[UploadFile] = File(default=[]),
        image_paths: List[str] = Form(default=[]),   # 每张图相对 vault 根的路径，顺序和 images 对齐
        x_publish_token: Optional[str] = Header(None, alias="X-Publish-Token"),
    ):
        """
        HTTPS 推文件通道 · 让本地 cockpit 绕过 SSH 直接发布文档到远端分享站。

        语义：幂等 upsert —— 覆盖同一份 user/slug 的 doc + 全部引用图 + registry。
        Auth：X-Publish-Token 必须非空且匹配 server 侧 publish_token。
        """
        expected = load_publish_token()
        if not expected:
            raise HTTPException(501, "publish disabled (no token configured on server)")
        if not x_publish_token or not hmac.compare_digest(expected, x_publish_token):
            raise HTTPException(401, "bad or missing X-Publish-Token")
        if not _SLUG_RE.match(slug):
            raise HTTPException(400, "slug must match ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
        if len(images) != len(image_paths):
            raise HTTPException(400, f"images/image_paths mismatch: {len(images)} vs {len(image_paths)}")

        vault = get_vault()
        doc_rel = _safe_rel_path(path)
        doc_abs = (vault / doc_rel).resolve()
        try:
            doc_abs.relative_to(vault.resolve())
        except ValueError:
            raise HTTPException(400, f"doc path escapes vault: {path}")

        # 写 doc
        doc_abs.parent.mkdir(parents=True, exist_ok=True)
        doc_bytes = await doc.read()
        doc_abs.write_bytes(doc_bytes)

        # 写图片
        written_imgs = []
        for img, img_rel_str in zip(images, image_paths):
            img_rel = _safe_rel_path(img_rel_str)
            img_abs = (vault / img_rel).resolve()
            try:
                img_abs.relative_to(vault.resolve())
            except ValueError:
                raise HTTPException(400, f"image path escapes vault: {img_rel_str}")
            img_abs.parent.mkdir(parents=True, exist_ok=True)
            img_bytes = await img.read()
            img_abs.write_bytes(img_bytes)
            written_imgs.append(str(img_rel))

        # 更新 registry
        reg = load_registry()
        ns = reg.setdefault(user, {})
        old_slugs = [k for k, v in ns.items() if v.get("path") == path and k != slug]
        for old in old_slugs:
            del ns[old]
        existing = ns.get(slug, {})
        if not title:
            title = existing.get("title") or _extract_title(doc_abs)
        from datetime import date
        ns[slug] = {
            "path": path,
            "title": title,
            "created": existing.get("created") or date.today().isoformat(),
            "updated": date.today().isoformat(),
            "folder": existing.get("folder", ""),
        }
        save_registry(reg)

        base = get_base_url().rstrip("/")
        return {
            "url": f"{base}{prefix}/{user}/{slug}",
            "slug": slug,
            "user": user,
            "doc_bytes": len(doc_bytes),
            "images": written_imgs,
        }

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

    # ── Brand icon (与主站驾舱同款：金色渐变 O) ──
    _ICON_SVG = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
        '<rect width="512" height="512" rx="96" fill="#09090f"/>'
        '<text x="256" y="340" font-size="320" font-family="system-ui" font-weight="900" '
        'fill="url(#g)" text-anchor="middle">O</text>'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#c8a96e"/>'
        '<stop offset="100%" stop-color="#8a6d3b"/>'
        '</linearGradient></defs></svg>'
    )

    @r.get("/icon.svg")
    async def share_icon():
        return HTMLResponse(_ICON_SVG, media_type="image/svg+xml",
                            headers={"Cache-Control": "public, max-age=86400"})

    @r.get("/favicon.ico")
    async def share_favicon():
        # 浏览器默认找 /favicon.ico —— 直接把 SVG 回给它，现代浏览器都认
        return HTMLResponse(_ICON_SVG, media_type="image/svg+xml",
                            headers={"Cache-Control": "public, max-age=86400"})

    # ── Landing page & users API (必须在 `/{user}` 之前注册) ──
    @r.get("/api/users")
    async def api_users_list():
        """列出所有有共享文档的用户 + 计数，供首页渲染。"""
        reg = load_registry()
        out = []
        for user, ns in (reg or {}).items():
            if not isinstance(ns, dict):
                continue
            folders = {
                entry.get("folder", "")
                for entry in ns.values()
                if isinstance(entry, dict) and entry.get("folder")
            }
            out.append({
                "user": user,
                "doc_count": len(ns),
                "folder_count": len(folders),
            })
        out.sort(key=lambda x: (-x["doc_count"], x["user"]))
        return {"users": out}

    @r.get("/", response_class=HTMLResponse)
    async def landing():
        landing_html = get_static_dir() / "share_landing.html"
        if not landing_html.exists():
            # 降级：如果模板被删了，至少给个可用 fallback
            reg = load_registry()
            users = list((reg or {}).keys())
            links = "".join(
                f'<li><a href="/{_esc(u)}">/{_esc(u)}</a></li>' for u in users
            ) or "<li>(暂无共享用户)</li>"
            return HTMLResponse(
                f"<!doctype html><meta charset=utf-8><title>Ome365 共享知识库</title>"
                f"<h1>Ome365 共享知识库</h1><ul>{links}</ul>"
            )
        return HTMLResponse(landing_html.read_text("utf-8"))

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
