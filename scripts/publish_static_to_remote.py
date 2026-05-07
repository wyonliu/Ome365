#!/usr/bin/env python3
"""
publish_static_to_remote.py — 把本地 .app/static/ 推到远端分享站。

与 publish_to_remote.py 互补：那个推 doc + 图；这个推 share.html / style.css / app.js 等 UI 资源。
走同一把 X-Publish-Token 鉴权，同一个远端 base_url。

流程：
    1. GET  /api/publish_static/manifest  → 拿到远端每文件的 sha1
    2. 本地 sha1 计算后做 diff（缺失 / 内容不同）
    3. POST /api/publish_static with 变动文件  → 远端落盘到 static/

用法：
    scripts/publish_static_to_remote.py                 # 默认推所有 UI 资源
    scripts/publish_static_to_remote.py --dry-run       # 只 diff 不推
    scripts/publish_static_to_remote.py share.html style.css   # 指定文件
    scripts/publish_static_to_remote.py --with-config   # 同时把 .app/cockpit_config.json 热更到远端

远端配置读取顺序：
    1. --base / --token 参数
    2. .app/tenant_config.json 里 remote.base_url + remote.token
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import requests

VAULT = Path(__file__).resolve().parent.parent
APP = VAULT / ".app"
STATIC_DIR = APP / "static"
TENANT = APP / "tenant_config.json"

ALLOWED_SUFFIXES = {
    ".html", ".css", ".js", ".mjs", ".map",
    ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".woff", ".woff2", ".ttf", ".json", ".txt",
}


def _load_remote_config() -> dict:
    if not TENANT.exists():
        return {}
    try:
        return (json.loads(TENANT.read_text("utf-8")) or {}).get("remote") or {}
    except Exception:
        return {}


def _proxies_for(cfg: dict):
    if cfg.get("use_proxy") is True:
        return None
    return {"http": None, "https": None}


def _local_manifest(only: set[str] | None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not STATIC_DIR.is_dir():
        return out
    for fp in STATIC_DIR.rglob("*"):
        if not fp.is_file():
            continue
        if fp.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        rel = fp.relative_to(STATIC_DIR).as_posix()
        if only and rel not in only and fp.name not in only:
            continue
        b = fp.read_bytes()
        out[rel] = {"sha1": hashlib.sha1(b).hexdigest(), "size": len(b), "_bytes": b}
    return out


def _fetch_remote_manifest(base: str, token: str, cfg: dict, timeout: float) -> dict:
    url = f"{base.rstrip('/')}/api/publish_static/manifest"
    resp = requests.get(
        url,
        headers={"X-Publish-Token": token},
        timeout=timeout,
        proxies=_proxies_for(cfg),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"manifest {resp.status_code}: {resp.text[:500]}")
    return (resp.json() or {}).get("files") or {}


def _push(base: str, token: str, cfg: dict, to_push: list[tuple[str, bytes]], timeout: float) -> dict:
    url = f"{base.rstrip('/')}/api/publish_static"
    files = []
    data = []
    for rel, b in to_push:
        files.append(("files", (Path(rel).name, b, "application/octet-stream")))
        data.append(("file_paths", rel))
    resp = requests.post(
        url,
        files=files,
        data=data,
        headers={"X-Publish-Token": token},
        timeout=timeout,
        proxies=_proxies_for(cfg),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"push {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="只推这些文件（相对 static/ 或裸文件名）；留空=所有变动文件")
    ap.add_argument("--base", default=None)
    ap.add_argument("--token", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--with-config", action="store_true",
                    help="同时推 .app/cockpit_config.json 到 /api/publish_config（热更组织/CARD_INDEX 数据）")
    args = ap.parse_args()

    cfg = _load_remote_config()
    base = args.base or cfg.get("base_url") or ""
    token = args.token or cfg.get("token") or ""
    if not base or not token:
        print("no remote configured (base/token empty); nothing to do", file=sys.stderr)
        return 0

    only = set(args.files) if args.files else None
    local = _local_manifest(only)
    if not local:
        print("no local static files matched", file=sys.stderr)
        return 1

    remote = _fetch_remote_manifest(base, token, cfg, args.timeout)

    to_push: list[tuple[str, bytes]] = []
    unchanged = 0
    for rel, info in sorted(local.items()):
        rinfo = remote.get(rel)
        if rinfo and rinfo.get("sha1") == info["sha1"]:
            unchanged += 1
            continue
        status = "new" if not rinfo else "diff"
        print(f"  [{status}] {rel}  ({info['size']} bytes)")
        to_push.append((rel, info["_bytes"]))

    if args.dry_run:
        if not to_push:
            print(f"dry-run: all up-to-date ({unchanged} files identical)")
        else:
            print(f"\ndry-run: would push {len(to_push)} files ({unchanged} unchanged)")
        return 0

    if to_push:
        print(f"\npushing {len(to_push)} files to {base}…")
        result = _push(base, token, cfg, to_push, args.timeout)
        written = result.get("written") or []
        for w in written:
            print(f"  ✓ {w['path']}  ({w['size']} bytes)")
        print(f"\ndone: {len(written)} written, {unchanged} unchanged")
    else:
        print(f"static: all up-to-date ({unchanged} files identical)")

    if args.with_config:
        cfg_path = APP / "cockpit_config.json"
        if not cfg_path.exists():
            print("  [with-config] skip: .app/cockpit_config.json not found")
            return 0
        b = cfg_path.read_bytes()
        url = f"{base.rstrip('/')}/api/publish_config"
        resp = requests.post(
            url,
            files=[("file", ("cockpit_config.json", b, "application/json"))],
            headers={"X-Publish-Token": token},
            timeout=args.timeout,
            proxies=_proxies_for(cfg),
        )
        if resp.status_code == 501:
            print("  [with-config] ⚠️ 远端未更新到含 /api/publish_config 的 server.py；先推一次 share_routes.py 并重启远端 service 再跑本命令")
        elif resp.status_code == 200:
            print(f"  [with-config] ✓ cockpit_config.json ({len(b)} bytes) pushed")
        else:
            print(f"  [with-config] ✗ {resp.status_code}: {resp.text[:300]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
