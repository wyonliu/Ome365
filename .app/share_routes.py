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
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from typing import List, Optional

from share_auth import (
    AuthStore,
    generate_passphrase,
    hash_password,
    verify_password,
    is_password_protected,
    make_password_policy,
    make_public_policy,
    cookie_name,
    _iso_after_seconds,
)


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

    # ── Privacy tier 1: 反爬 + 反列表（tenant_config.share.hide_listings）──
    # 缺省 True：安全默认，缺 config 时最严。config 明确写 false 才放开。
    def _privacy_cfg() -> dict:
        t = get_tenant() or {}
        return (t.get("share") or {})

    def _hide_listings() -> bool:
        cfg = _privacy_cfg()
        v = cfg.get("hide_listings", True)
        return bool(v)

    # ── Privacy tier 2: 密码保护 · AuthStore 懒初始化 ──
    _auth_ref = [None]  # type: List[Optional[AuthStore]]

    def auth_store() -> AuthStore:
        if _auth_ref[0] is None:
            db_path = get_registry_path().parent / "share_auth.db"
            _auth_ref[0] = AuthStore(db_path)
        return _auth_ref[0]

    _SESSION_TTL_SECONDS = 30 * 86400  # 30 天滚动

    def _client_ip(req: Request) -> str:
        """优先 X-Forwarded-For 首段；否则 request.client.host。"""
        xff = req.headers.get("x-forwarded-for", "")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
        return (req.client.host if req.client else "") or ""

    def _client_ua(req: Request) -> str:
        return (req.headers.get("user-agent", "") or "")[:256]

    def _check_publish_token(tok: Optional[str]):
        """管理端点鉴权 · 用同一把 publish_token，返回 401 if bad。"""
        expected = load_publish_token()
        if not expected:
            raise HTTPException(501, "management disabled (no token configured on server)")
        if not tok or not hmac.compare_digest(expected, tok):
            raise HTTPException(401, "bad or missing X-Publish-Token")

    def _get_entry(user: str, slug: str) -> dict:
        reg = load_registry()
        ns = reg.get(user) or {}
        entry = ns.get(slug)
        if not entry:
            raise HTTPException(404, "Not found")
        return entry

    def _save_entry(user: str, slug: str, entry: dict):
        reg = load_registry()
        reg.setdefault(user, {})[slug] = entry
        save_registry(reg)

    def _valid_session_for(req: Request, user: str, slug: str) -> Optional[dict]:
        """
        读 cookie → 查 session → 校验归属 + 未过期 + 未 revoke。
        命中 → touch 续期（rolling），返回 session row dict；否则 None。
        """
        sid = req.cookies.get(cookie_name(user, slug))
        if not sid:
            return None
        row = auth_store().get_session(sid)
        if not row:
            return None
        if row["user"] != user or row["slug"] != slug:
            return None
        if int(row["revoked"]):
            return None
        if row["expires_at"] <= _iso_after_seconds(0):
            return None
        new_exp = _iso_after_seconds(_SESSION_TTL_SECONDS)
        auth_store().touch_session(sid, new_exp)
        return {"sid": sid, "user": user, "slug": slug, "expires_at": new_exp}

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

    # ── robots.txt（T1 反爬）──
    @r.get("/robots.txt")
    async def robots_txt():
        body = "User-agent: *\nDisallow: /\n"
        return HTMLResponse(body, media_type="text/plain",
                            headers={"Cache-Control": "public, max-age=86400"})

    # ── Registry API ──
    @r.get("/api/registry")
    async def api_registry():
        if _hide_listings():
            raise HTTPException(403, "listing disabled")
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

    # ── Static assets publish channel（UI/CSS/JS 热更远端）──
    #   与 /api/publish 同一把 publish_token，路径锁死在 get_static_dir()。
    #   本地 UI 改完 → scripts/publish_static_to_remote.py 推过来 → 远端立即生效，
    #   不再需要 tarball + WebSSH 走旧 install-remote.sh 流程。
    _ALLOWED_STATIC_SUFFIXES = {
        ".html", ".css", ".js", ".mjs", ".map",
        ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
        ".woff", ".woff2", ".ttf", ".json", ".txt",
    }

    @r.get("/api/publish_static/manifest")
    async def api_publish_static_manifest(
        x_publish_token: Optional[str] = Header(None, alias="X-Publish-Token"),
    ):
        """列出远端 static/ 下每个文件的 sha1 + size，供本地 diff 决定推什么。"""
        expected = load_publish_token()
        if not expected:
            raise HTTPException(501, "publish disabled (no token configured on server)")
        if not x_publish_token or not hmac.compare_digest(expected, x_publish_token):
            raise HTTPException(401, "bad or missing X-Publish-Token")
        import hashlib
        root = get_static_dir().resolve()
        out = {}
        if root.is_dir():
            for fp in root.rglob("*"):
                if not fp.is_file():
                    continue
                rel = fp.relative_to(root).as_posix()
                b = fp.read_bytes()
                out[rel] = {"sha1": hashlib.sha1(b).hexdigest(), "size": len(b)}
        return {"root": "static", "files": out}

    @r.post("/api/publish_static")
    async def api_publish_static(
        files: List[UploadFile] = File(default=[]),
        file_paths: List[str] = Form(default=[]),
        x_publish_token: Optional[str] = Header(None, alias="X-Publish-Token"),
    ):
        """
        HTTPS 推静态资源 · 本地 .app/static/ → 远端 .app/static/ 。
        路径必须在 get_static_dir() 内，且后缀在白名单内。
        """
        expected = load_publish_token()
        if not expected:
            raise HTTPException(501, "publish disabled (no token configured on server)")
        if not x_publish_token or not hmac.compare_digest(expected, x_publish_token):
            raise HTTPException(401, "bad or missing X-Publish-Token")
        if len(files) != len(file_paths):
            raise HTTPException(400, f"files/file_paths mismatch: {len(files)} vs {len(file_paths)}")
        root = get_static_dir().resolve()
        root.mkdir(parents=True, exist_ok=True)
        written = []
        for up, rel_str in zip(files, file_paths):
            rel = _safe_rel_path(rel_str)
            suffix = rel.suffix.lower()
            if suffix not in _ALLOWED_STATIC_SUFFIXES:
                raise HTTPException(400, f"disallowed suffix: {rel_str}")
            abs_p = (root / rel).resolve()
            try:
                abs_p.relative_to(root)
            except ValueError:
                raise HTTPException(400, f"path escapes static root: {rel_str}")
            abs_p.parent.mkdir(parents=True, exist_ok=True)
            data = await up.read()
            abs_p.write_bytes(data)
            written.append({"path": str(rel), "size": len(data)})
        return {"ok": True, "written": written}

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
    async def api_doc_content(user: str, slug: str, request: Request):
        reg = load_registry()
        ns = reg.get(user, {})
        entry = ns.get(slug)
        if not entry:
            raise HTTPException(404, "Not found")
        # T2：密码保护门禁。未解锁 → 401 + WWW-Authenticate 指示前端上锁屏。
        if is_password_protected(entry):
            sess = _valid_session_for(request, user, slug)
            if not sess:
                return JSONResponse(
                    {"error": "password_required", "user": user, "slug": slug},
                    status_code=401,
                    headers={"WWW-Authenticate": 'OmePassphrase realm="share"'},
                )
            auth_store().log(user, slug, "view", sid=sess["sid"],
                             ip=_client_ip(request), ua=_client_ua(request))
        fp = get_vault() / entry["path"]
        if not fp.exists():
            raise HTTPException(404, "File missing from vault")
        raw = fp.read_text("utf-8")
        meta = _parse_frontmatter(raw)
        return {"raw": raw, "meta": meta, "title": entry["title"], "slug": slug, "user": user}

    # ── T2 · 访客解锁 ──
    @r.post("/unlock/{user}/{slug}")
    async def unlock(user: str, slug: str, request: Request):
        """
        访客提交密码 → 生成 session → Set-Cookie（HttpOnly, SameSite=Lax, path=/）。
        body: {"password": "sunset-dragon-forge-42"}
        返回 200 {ok:true, expires_at} / 401 {error, remaining} / 429 {error, reason}
        """
        entry = _get_entry(user, slug)
        if not is_password_protected(entry):
            # 公共 doc 提交解锁 → 幂等 200 但不 Set-Cookie，前端据此直接放行
            return {"ok": True, "visibility": "public"}

        ip = _client_ip(request)
        ua = _client_ua(request)
        store = auth_store()

        # 速率限制在先（防止慢密码验证被当作放大器）
        reason = store.check_rate_limit(user, slug, ip)
        if reason:
            store.log(user, slug, "rate_block_" + reason, ip=ip, ua=ua)
            return JSONResponse(
                {"error": "rate_limited", "reason": reason},
                status_code=429,
            )

        try:
            body = await request.json()
        except Exception:
            body = {}
        password = (body.get("password") or "").strip()
        if not password or len(password) > 256:
            raise HTTPException(400, "missing or oversize password")

        stored_hash = ((entry.get("policy") or {}).get("password_hash") or "")
        if not verify_password(password, stored_hash):
            store.record_fail(user, slug, ip)
            store.log(user, slug, "unlock_fail", ip=ip, ua=ua)
            # 再读一次看是否这一击触发锁
            new_reason = store.check_rate_limit(user, slug, ip)
            snap = store.rate_limit_snapshot(user, slug, ip)
            return JSONResponse(
                {"error": "invalid_password", "locked": new_reason,
                 "fails_ip_10min": snap["ip_10min"]},
                status_code=401,
            )

        sid, expires_at = store.create_session(user, slug, ip, ua, _SESSION_TTL_SECONDS)
        store.log(user, slug, "unlock_ok", sid=sid, ip=ip, ua=ua)

        resp = JSONResponse({"ok": True, "expires_at": expires_at})
        resp.set_cookie(
            cookie_name(user, slug),
            sid,
            max_age=_SESSION_TTL_SECONDS,
            path="/",
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
        )
        return resp

    # ── T2 · 管理 API（需要 X-Publish-Token） ──
    @r.get("/api/share/{user}/{slug}/password/info")
    async def share_password_info(
        user: str, slug: str, request: Request,
        x_publish_token: Optional[str] = Header(None, alias="X-Publish-Token"),
    ):
        _check_publish_token(x_publish_token)
        entry = _get_entry(user, slug)
        pol = entry.get("policy") or {}
        protected = is_password_protected(entry)
        snap = auth_store().rate_limit_snapshot(user, slug, _client_ip(request))
        sess_count = len(auth_store().list_sessions(user, slug))
        return {
            "user": user,
            "slug": slug,
            "visibility": pol.get("visibility", "public"),
            "protected": protected,
            "password_set_at": pol.get("password_set_at"),
            "active_sessions": sess_count,
            "rate_limit": snap,
        }

    @r.post("/api/share/{user}/{slug}/password/enable")
    async def share_password_enable(
        user: str, slug: str, request: Request,
        x_publish_token: Optional[str] = Header(None, alias="X-Publish-Token"),
    ):
        """
        public → password。自动生成密码 + hash 存 registry，明文只在此次返回。
        已加密 → 409（显式提示走 rotate）。
        """
        _check_publish_token(x_publish_token)
        entry = _get_entry(user, slug)
        if is_password_protected(entry):
            raise HTTPException(409, "already password-protected; use rotate to change")
        plain = generate_passphrase()
        h = hash_password(plain)
        entry["policy"] = make_password_policy(h)
        _save_entry(user, slug, entry)
        auth_store().log(user, slug, "password_enable", ip=_client_ip(request), ua=_client_ua(request))
        base = get_base_url().rstrip("/")
        return {
            "ok": True,
            "visibility": "password",
            "password": plain,
            "password_set_at": entry["policy"]["password_set_at"],
            "url": "{}{}/{}/{}".format(base, prefix, user, slug),
            "title": entry.get("title") or slug,
        }

    @r.post("/api/share/{user}/{slug}/password/rotate")
    async def share_password_rotate(
        user: str, slug: str, request: Request,
        x_publish_token: Optional[str] = Header(None, alias="X-Publish-Token"),
    ):
        """password → password（新 hash，踢所有 session）。"""
        _check_publish_token(x_publish_token)
        entry = _get_entry(user, slug)
        if not is_password_protected(entry):
            raise HTTPException(409, "not protected; use enable")
        plain = generate_passphrase()
        h = hash_password(plain)
        entry["policy"] = make_password_policy(h)
        _save_entry(user, slug, entry)
        revoked = auth_store().revoke_all_sessions(user, slug)
        auth_store().log(user, slug, "password_rotate",
                         ip=_client_ip(request), ua=_client_ua(request))
        base = get_base_url().rstrip("/")
        return {
            "ok": True,
            "password": plain,
            "password_set_at": entry["policy"]["password_set_at"],
            "revoked_sessions": revoked,
            "url": "{}{}/{}/{}".format(base, prefix, user, slug),
            "title": entry.get("title") or slug,
        }

    @r.post("/api/share/{user}/{slug}/password/disable")
    async def share_password_disable(
        user: str, slug: str, request: Request,
        x_publish_token: Optional[str] = Header(None, alias="X-Publish-Token"),
    ):
        """password → public。清除 hash + 踢所有 session。"""
        _check_publish_token(x_publish_token)
        entry = _get_entry(user, slug)
        if not is_password_protected(entry):
            return {"ok": True, "visibility": "public", "revoked_sessions": 0}
        entry["policy"] = make_public_policy()
        _save_entry(user, slug, entry)
        revoked = auth_store().revoke_all_sessions(user, slug)
        auth_store().log(user, slug, "password_disable",
                         ip=_client_ip(request), ua=_client_ua(request))
        return {"ok": True, "visibility": "public", "revoked_sessions": revoked}

    @r.get("/api/share/{user}/{slug}/sessions")
    async def share_sessions_list(
        user: str, slug: str,
        x_publish_token: Optional[str] = Header(None, alias="X-Publish-Token"),
    ):
        _check_publish_token(x_publish_token)
        _get_entry(user, slug)
        return {"sessions": auth_store().list_sessions(user, slug)}

    @r.post("/api/share/{user}/{slug}/sessions/revoke")
    async def share_sessions_revoke(
        user: str, slug: str, request: Request,
        x_publish_token: Optional[str] = Header(None, alias="X-Publish-Token"),
    ):
        """body: {sid: "..."} 踢单个；或 {all: true} 全部。"""
        _check_publish_token(x_publish_token)
        _get_entry(user, slug)
        try:
            body = await request.json()
        except Exception:
            body = {}
        if body.get("all"):
            n = auth_store().revoke_all_sessions(user, slug)
            auth_store().log(user, slug, "sessions_revoke_all",
                             ip=_client_ip(request), ua=_client_ua(request))
            return {"ok": True, "revoked": n}
        sid = (body.get("sid") or "").strip()
        if not sid:
            raise HTTPException(400, "missing sid or all")
        auth_store().revoke_session(sid)
        auth_store().log(user, slug, "session_revoke", sid=sid,
                         ip=_client_ip(request), ua=_client_ua(request))
        return {"ok": True, "revoked": 1}

    @r.get("/api/share/{user}/{slug}/audit")
    async def share_audit(
        user: str, slug: str, limit: int = 20,
        x_publish_token: Optional[str] = Header(None, alias="X-Publish-Token"),
    ):
        _check_publish_token(x_publish_token)
        _get_entry(user, slug)
        return {"audit": auth_store().tail_audit(user, slug, limit)}

    @r.get("/api/share/info_batch")
    async def share_info_batch(
        user: str,
        x_publish_token: Optional[str] = Header(None, alias="X-Publish-Token"),
    ):
        """
        批量读 user 名下所有 doc 的密码保护状态。用于设置页列表渲染 🔒 icon。
        返回 {slug: {protected, visibility, password_set_at, active_sessions}}。
        """
        _check_publish_token(x_publish_token)
        reg = load_registry()
        ns = reg.get(user) or {}
        out = {}
        store = auth_store()
        for slug, entry in ns.items():
            pol = entry.get("policy") or {}
            protected = is_password_protected(entry)
            out[slug] = {
                "protected": protected,
                "visibility": pol.get("visibility", "public"),
                "password_set_at": pol.get("password_set_at"),
                "active_sessions": len(store.list_sessions(user, slug)) if protected else 0,
            }
        return {"user": user, "items": out}

    @r.get("/api/user/{user}/docs")
    async def api_user_docs(user: str):
        if _hide_listings():
            raise HTTPException(403, "listing disabled")
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
        if _hide_listings():
            raise HTTPException(403, "listing disabled")
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
        # T1 锁定：hide_listings=true 时只渲染 locked splash，不暴露用户清单
        if _hide_listings():
            locked = get_static_dir() / "share_landing_locked.html"
            if locked.exists():
                return HTMLResponse(locked.read_text("utf-8"))
            return HTMLResponse(
                "<!doctype html><meta charset=utf-8><title>Ome365</title>"
                "<body style='font-family:system-ui;padding:40px;color:#6b7280;text-align:center'>"
                "<h1 style='color:#0055a6'>Ome365 · 共享工作台</h1>"
                "<p>请使用完整的文档链接访问。</p></body>"
            )
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
        # T1 锁定：hide_listings=true 时不暴露用户 slug 清单
        if _hide_listings():
            locked = get_static_dir() / "share_home_locked.html"
            if locked.exists():
                return HTMLResponse(locked.read_text("utf-8").replace("{{USER}}", _esc(user)))
            return HTMLResponse(
                "<!doctype html><meta charset=utf-8><title>Ome365</title>"
                "<body style='font-family:system-ui;padding:40px;color:#6b7280;text-align:center'>"
                "<h1 style='color:#0055a6'>Ome365 · 共享工作台</h1>"
                "<p>请使用完整的文档链接访问。</p></body>"
            )
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
