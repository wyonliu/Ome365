"""
Ome365 Share Server — 独立只读文档分享站
启动: cd .app && python3 share_server.py
默认端口: 3651 (可通过 SHARE_PORT 环境变量修改)
"""

import os, re, json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

VAULT = Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()
PORT = int(os.environ.get("SHARE_PORT", "3651"))
BASE_URL = os.environ.get("SHARE_BASE_URL", f"http://localhost:{PORT}")
REGISTRY_PATH = Path(__file__).parent / "share_registry.json"
STATIC_DIR = Path(__file__).parent / "static"
REPORTS_DIR = VAULT / "Projects" / "LongFor" / "reports"

app = FastAPI(title="Ome365 Share")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Registry ──

def load_registry():
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text("utf-8"))
    return {}

def save_registry(data):
    REGISTRY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


# ── API ──

@app.get("/api/cockpit/config")
async def api_cockpit_config():
    """Serve ASR/Speaker dictionaries for ticnote-renderer.js (live → sample fallback)."""
    live = Path(__file__).parent / "cockpit_config.json"
    sample = Path(__file__).parent / "cockpit_config.sample.json"
    fp = live if live.exists() else sample
    if not fp.exists():
        # 空配置：渲染器降级为原文显示
        return {"_source": "empty", "ASR_FIXES": [], "KNOWN_SPEAKER_MAPS": {}, "SPEAKER_HINTS": []}
    try:
        data = json.loads(fp.read_text("utf-8"))
        data["_source"] = fp.name
        return data
    except Exception as e:
        return {"_source": "error", "_error": str(e), "ASR_FIXES": [], "KNOWN_SPEAKER_MAPS": {}, "SPEAKER_HINTS": []}


@app.get("/api/registry")
async def api_registry():
    """Full registry dump."""
    return load_registry()

@app.post("/api/register")
async def api_register(user: str, slug: str, path: str, title: str = ""):
    """Register a share link: /<user>/<slug> → vault file at <path>."""
    slug_re = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')
    if not slug_re.match(slug):
        raise HTTPException(400, "Slug must be alphanumeric/hyphens/underscores, 1-64 chars, start with letter/digit")
    fp = VAULT / path
    if not fp.exists():
        raise HTTPException(404, f"File not found: {path}")
    reg = load_registry()
    ns = reg.setdefault(user, {})
    if slug in ns:
        existing = ns[slug]["path"]
        if existing != path:
            raise HTTPException(
                409,
                f"Slug '{slug}' already registered to a different document: {existing}. "
                f"Use a different slug or DELETE first."
            )
    # Dedup: remove any existing slug pointing to the same path
    old_slugs = [k for k, v in ns.items() if v["path"] == path and k != slug]
    for old in old_slugs:
        del ns[old]
    if not title:
        title = _extract_title(fp)
    ns[slug] = {"path": path, "title": title, "created": __import__("datetime").date.today().isoformat()}
    save_registry(reg)
    return {"url": f"{BASE_URL.rstrip('/')}/{user}/{slug}", "slug": slug, "user": user}

@app.delete("/api/register")
async def api_unregister(user: str, slug: str):
    """Remove a share link."""
    reg = load_registry()
    ns = reg.get(user, {})
    if slug not in ns:
        raise HTTPException(404, "Slug not found")
    del ns[slug]
    if not ns:
        del reg[user]
    save_registry(reg)
    return {"ok": True}

@app.get("/api/doc/{user}/{slug}")
async def api_doc_content(user: str, slug: str):
    """Get document raw content + metadata."""
    reg = load_registry()
    ns = reg.get(user, {})
    entry = ns.get(slug)
    if not entry:
        raise HTTPException(404, "Not found")
    fp = VAULT / entry["path"]
    if not fp.exists():
        raise HTTPException(404, "File missing from vault")
    raw = fp.read_text("utf-8")
    meta = _parse_frontmatter(raw)
    return {"raw": raw, "meta": meta, "title": entry["title"], "slug": slug, "user": user}


# ── Static files (must be before catch-all /{user} routes) ──

@app.get("/static/{filepath:path}")
async def serve_static(filepath: str):
    from fastapi.responses import FileResponse
    fp = STATIC_DIR / filepath
    if not fp.is_file():
        raise HTTPException(404)
    return FileResponse(fp, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/reports-static/{filepath:path}")
async def serve_reports_static(filepath: str):
    from fastapi.responses import FileResponse
    fp = REPORTS_DIR / filepath
    if not fp.is_file():
        raise HTTPException(404)
    return FileResponse(fp)


# ── Pages ──

@app.get("/api/user/{user}/docs")
async def api_user_docs(user: str):
    """All docs + folders for a user."""
    reg = load_registry()
    ns = reg.get(user)
    if ns is None:
        raise HTTPException(404, "User not found")
    docs = []
    for slug, entry in ns.items():
        docs.append({
            "slug": slug, "title": entry.get("title", slug),
            "created": entry.get("created", ""), "folder": entry.get("folder", ""),
        })
    docs.sort(key=lambda x: x.get("created", ""), reverse=True)
    folders = list({d["folder"] for d in docs if d.get("folder")})
    folders.sort()
    return {"user": user, "docs": docs, "folders": folders}

@app.post("/api/user/{user}/folder")
async def api_create_folder(user: str, name: str):
    """Move docs into a folder or create an empty folder entry."""
    return {"ok": True, "folder": name}

@app.put("/api/user/{user}/doc/{slug}")
async def api_update_doc_meta(user: str, slug: str, folder: str = None, title: str = None):
    """Update doc metadata (folder, title alias)."""
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

@app.get("/{user}")
async def user_index(user: str):
    """User namespace — document listing."""
    reg = load_registry()
    ns = reg.get(user)
    if ns is None:
        raise HTTPException(404, "User not found")
    home_html = STATIC_DIR / "share_home.html"
    if home_html.exists():
        content = home_html.read_text("utf-8").replace("{{USER}}", _esc(user))
        return HTMLResponse(content)
    return HTMLResponse(f"<h1>{_esc(user)}</h1><p>Home template not found</p>")


@app.get("/{user}/{slug}")
async def user_doc_page(user: str, slug: str):
    """Serve the share page."""
    reg = load_registry()
    ns = reg.get(user)
    if not ns or slug not in ns:
        raise HTTPException(404, "Not found")
    share_html = STATIC_DIR / "share.html"
    return HTMLResponse(share_html.read_text("utf-8"))


# ── Helpers ──

def _esc(s):
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def _extract_title(fp):
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

def _parse_frontmatter(raw):
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


# ── Static files ──



if __name__ == "__main__":
    reg = load_registry()
    total = sum(len(v) for v in reg.values())
    users = list(reg.keys())
    print(f"\n  Ome365 Share · port {PORT}")
    print(f"  {total} docs · users: {', '.join(users) or '(none)'}")
    print(f"  http://localhost:{PORT}")
    for u in users:
        print(f"    /{u}/ — {len(reg[u])} docs")
        for slug in reg[u]:
            print(f"      /{u}/{slug}")
    print()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
