#!/usr/bin/env python3
"""
publish_to_remote.py — 把本地已注册的分享文档推到远端分享站 (ome365.example.com)。

走 HTTPS POST /api/publish，用 X-Publish-Token 鉴权。SSH/JumpServer 一概不碰。

用法（命令行）：
    scripts/publish_to_remote.py <user> <slug>
    scripts/publish_to_remote.py alice DemoWorld

用法（库）：
    from scripts.publish_to_remote import publish
    result = publish(vault_root, user="alice", slug="demo",
                     remote_base="https://ome365.example.com", token="abc123")

依赖：requests（已在 requirements.txt）。

远端配置读取顺序：
    1. 命令行 --base / --token 参数
    2. vault/.app/tenant_config.json 里的 `remote.base_url` + `remote.token`

远端无配置时：no-op，打印提示退出 0（这样本地脚本可以静默无副作用调用）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import requests

VAULT = Path(__file__).resolve().parent.parent
APP = VAULT / ".app"
REGISTRY = APP / "share_registry.json"
TENANT = APP / "tenant_config.json"

IMG_RE = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')


def _load_remote_config(tenant_path: Path = TENANT) -> dict:
    if not tenant_path.exists():
        return {}
    try:
        return (json.loads(tenant_path.read_text("utf-8")) or {}).get("remote") or {}
    except Exception:
        return {}


def _find_image_refs(md_text: str) -> list[str]:
    out = []
    for raw in IMG_RE.findall(md_text):
        if raw.startswith("http://") or raw.startswith("https://"):
            continue
        out.append(raw.split("#", 1)[0].split("?", 1)[0])
    return out


def _resolve_image(ref: str, doc_abs: Path, reports_dir: Path) -> Path | None:
    if ref.startswith("/reports-static/"):
        return reports_dir / ref[len("/reports-static/"):]
    if ref.startswith("/"):
        return None
    return (doc_abs.parent / ref).resolve()


def publish(
    vault: Path,
    *,
    user: str,
    slug: str,
    remote_base: str,
    token: str,
    timeout: float = 60.0,
) -> dict:
    """把 user/slug 这份文档 + 引用图 全量推到 remote_base。"""
    if not REGISTRY.exists():
        raise FileNotFoundError(f"missing registry: {REGISTRY}")
    reg = json.loads(REGISTRY.read_text("utf-8"))
    entry = (reg.get(user) or {}).get(slug)
    if not entry:
        raise KeyError(f"{user}/{slug} not in local registry")

    doc_rel = entry["path"]
    doc_abs = vault / doc_rel
    if not doc_abs.exists():
        raise FileNotFoundError(f"doc file missing: {doc_abs}")

    tenant = json.loads(TENANT.read_text("utf-8")) if TENANT.exists() else {}
    reports_rel = (tenant.get("reports") or {}).get("dir") or "reports"
    reports_dir = vault / reports_rel

    md = doc_abs.read_text("utf-8")
    img_refs = _find_image_refs(md)

    # 构造 multipart
    files: list[tuple[str, tuple[str, bytes, str]]] = []
    files.append(("doc", (doc_abs.name, md.encode("utf-8"), "text/markdown")))

    image_paths: list[str] = []
    sent_imgs: list[str] = []
    seen = set()
    for ref in img_refs:
        img = _resolve_image(ref, doc_abs, reports_dir)
        if img is None or not img.exists():
            print(f"  skip missing image: {ref}", file=sys.stderr)
            continue
        try:
            rel = str(img.resolve().relative_to(vault.resolve()))
        except ValueError:
            print(f"  skip out-of-vault image: {img}", file=sys.stderr)
            continue
        if rel in seen:
            continue
        seen.add(rel)
        files.append(("images", (img.name, img.read_bytes(), "application/octet-stream")))
        image_paths.append(rel)
        sent_imgs.append(rel)

    data = [
        ("user", user),
        ("slug", slug),
        ("path", doc_rel),
        ("title", entry.get("title", "")),
    ]
    for p in image_paths:
        data.append(("image_paths", p))

    url = f"{remote_base.rstrip('/')}/api/publish"
    # 内网 remote（ome365.example.com → 10.0.0.50）必须绕开本机 VPN 代理；
    # 否则 requests 会吃 https_proxy env 走公网，返回 SSLEOFError。
    remote_cfg = _load_remote_config()
    if remote_cfg.get("use_proxy") is True:
        proxies = None  # 显式允许走代理（外网 remote 时用）
    else:
        proxies = {"http": None, "https": None}
    resp = requests.post(
        url,
        files=files,
        data=data,
        headers={"X-Publish-Token": token},
        timeout=timeout,
        proxies=proxies,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"remote {resp.status_code}: {resp.text[:500]}")
    result = resp.json()
    result["_local_images"] = sent_imgs
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("user")
    ap.add_argument("slug")
    ap.add_argument("--base", default=None, help="远端 base URL (默认读 tenant_config.remote.base_url)")
    ap.add_argument("--token", default=None, help="publish token (默认读 tenant_config.remote.token)")
    ap.add_argument("--silent-if-unconfigured", action="store_true",
                    help="remote 未配置时静默退出 0（本地流程用）")
    args = ap.parse_args()

    cfg = _load_remote_config()
    base = args.base or cfg.get("base_url") or ""
    token = args.token or cfg.get("token") or ""

    if not base or not token:
        msg = "remote not configured (tenant_config.remote.base_url / .token)"
        if args.silent_if_unconfigured:
            print(f"[publish] {msg} — skip")
            return 0
        print(f"[publish] {msg}", file=sys.stderr)
        return 2

    try:
        result = publish(VAULT, user=args.user, slug=args.slug, remote_base=base, token=token)
    except Exception as e:
        print(f"[publish] FAIL: {e}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n[publish] OK → {result['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
