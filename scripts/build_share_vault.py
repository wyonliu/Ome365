#!/usr/bin/env python3
"""
build_share_vault.py — 从 share_registry.json 抽出最小 vault 子集。

为什么最小集：分享站只需要 registered 的几份文档 + 它们引用的图片，
没必要把 .app/ 全量 vault（数万文件、大量 PII）整包推到外部服务器。

产出：
  <staging>/
    <doc-path-1>.md
    <doc-path-2>.md
    Projects/acme/reports/04-triad/projects/images/*.jpg
    .app/
      share_registry.json
      tenant_config.json
      cockpit_config.json

用法：
  python3 scripts/build_share_vault.py
  python3 scripts/build_share_vault.py --staging /tmp/ome365-share-vault
  python3 scripts/build_share_vault.py --list-only    # 只列出会复制的文件
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


VAULT = Path(__file__).resolve().parent.parent
APP = VAULT / ".app"
REGISTRY = APP / "share_registry.json"
TENANT = APP / "tenant_config.json"
COCKPIT = APP / "cockpit_config.json"
DEFAULT_STAGING = Path("/tmp/ome365-share-staging")

IMG_RE = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')


def find_image_refs(md_text: str) -> list[str]:
    """抽出 markdown 里引用的本地图片路径（绝对 /reports-static/ 或相对）"""
    refs = []
    for raw in IMG_RE.findall(md_text):
        if raw.startswith("http://") or raw.startswith("https://"):
            continue
        refs.append(raw.split("#", 1)[0].split("?", 1)[0])
    return refs


def resolve_image(ref: str, doc_path: Path, reports_dir: Path) -> Path | None:
    """把 markdown 里写的路径还原成磁盘绝对路径。"""
    if ref.startswith("/reports-static/"):
        # /reports-static/04-triad/.../x.jpg  →  <reports_dir>/04-triad/.../x.jpg
        return reports_dir / ref[len("/reports-static/"):]
    if ref.startswith("/"):
        return None  # 未知绝对路径前缀
    # 相对路径：相对于 doc_path 所在目录
    return (doc_path.parent / ref).resolve()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--staging", default=str(DEFAULT_STAGING))
    ap.add_argument("--list-only", action="store_true")
    args = ap.parse_args()

    if not REGISTRY.exists():
        sys.exit(f"missing: {REGISTRY}")

    reg = json.loads(REGISTRY.read_text("utf-8"))
    tenant = json.loads(TENANT.read_text("utf-8")) if TENANT.exists() else {}
    reports_rel = (tenant.get("reports") or {}).get("dir") or "reports"
    reports_dir = VAULT / reports_rel

    staging = Path(args.staging).resolve()
    if not args.list_only:
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)

    files_to_copy: list[tuple[Path, Path]] = []  # (src_abs, dst_rel_to_staging)
    total_chars = 0

    for user, docs in reg.items():
        for slug, entry in docs.items():
            src = VAULT / entry["path"]
            if not src.exists():
                print(f"  MISSING doc: {user}/{slug} → {entry['path']}", file=sys.stderr)
                continue
            dst_rel = Path(entry["path"])
            files_to_copy.append((src, dst_rel))
            md = src.read_text("utf-8")
            total_chars += len(md)
            for ref in find_image_refs(md):
                img = resolve_image(ref, src, reports_dir)
                if img is None:
                    print(f"  SKIP unknown ref in {slug}: {ref}", file=sys.stderr)
                    continue
                if not img.exists():
                    print(f"  MISSING image in {slug}: {ref} → {img}", file=sys.stderr)
                    continue
                try:
                    rel = img.relative_to(VAULT)
                except ValueError:
                    print(f"  SKIP out-of-vault image: {img}", file=sys.stderr)
                    continue
                files_to_copy.append((img, rel))

    # 去重
    seen = set()
    dedup: list[tuple[Path, Path]] = []
    for src, rel in files_to_copy:
        key = str(rel)
        if key in seen:
            continue
        seen.add(key)
        dedup.append((src, rel))

    print(f"\n[build-share-vault] {len(reg.get('alice', {}))} docs · {total_chars:,} chars · "
          f"{len(dedup)} files to copy")
    for _, rel in dedup:
        print(f"  {rel}")

    if args.list_only:
        return

    # 复制
    for src, rel in dedup:
        dst = staging / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # .app/ 配置三件套（share_registry + tenant_config + cockpit_config）
    app_dst = staging / ".app"
    app_dst.mkdir(exist_ok=True)
    for fp in (REGISTRY, TENANT, COCKPIT):
        if fp.exists():
            shutil.copy2(fp, app_dst / fp.name)

    size = sum(f.stat().st_size for f in staging.rglob("*") if f.is_file())
    print(f"\n[build-share-vault] staging ready: {staging} ({size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
