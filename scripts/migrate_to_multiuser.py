#!/usr/bin/env python3
"""
Ome365 · 单用户 legacy 布局 → 多用户 $OME365_HOME/tenants/{tid}/users/{uid}/ 迁移

## 做什么

1. 建 $OME365_HOME/tenants/default/users/{uid}/{state,}（$OME365_HOME 默认 ~/.ome365）
2. 从 .app/ 下移动 {settings,growth,reminders,...}.json 到 users/{uid}/
3. 从 .app/ 下移动 {tenant_config,cockpit_config,share_registry}.json 到 tenants/default/
4. 原位置留下 symlink 保 legacy 入口兼容
5. profile.json 里 vault_path 写成 **原 $OME365_VAULT 绝对路径**（vault 数据不搬、不做符号链接，
   天然避免 vault 内嵌 tenants/ 的递归陷阱）
6. 打印 rollback 指引

## 零破坏保证

- vault 数据 0 搬移；tenants/ 在 $OME365_HOME 下，与 vault 彻底解耦
- .app/ 下的配置文件原位 symlink，旧脚本/编辑器继续能访问
- 脚本幂等：重跑不重复移动（检查 symlink 状态）
- --dry-run 只打印不执行
- --rollback 撤销迁移

## 用法

    # 预演（OME365_HOME 未设时默认 ~/.ome365）
    OME365_HOME=/tmp/ome365-home python3 scripts/migrate_to_multiuser.py --uid captain --dry-run

    # 执行
    OME365_HOME=~/.ome365 python3 scripts/migrate_to_multiuser.py \\
        --uid captain --email captain@example.com --display "Captain Wyon"

    # 撤销
    OME365_HOME=~/.ome365 python3 scripts/migrate_to_multiuser.py --rollback --uid captain
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / ".app"
LEGACY_VAULT = Path(os.environ.get("OME365_VAULT", APP_DIR.parent)).expanduser().resolve()
HOME = Path(
    os.environ.get("OME365_HOME")
    or os.environ.get("OME365_ROOT")
    or str(Path.home() / ".ome365")
).expanduser().resolve()

TENANT_ID = "default"

# tenant-scope files (moved to tenants/default/)
TENANT_FILES = [
    "tenant_config.json",
    "cockpit_config.json",
    "share_registry.json",
]

# user-scope state files (moved to users/{uid}/state/)
USER_STATE_FILES = [
    "growth.json",
    "reminders.json",
    "meditations.json",
    "life_state.json",
    "ome_state.json",
    "contacts_cats.json",
]

USER_SETTINGS = "settings.json"
SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")


def log(msg: str, dry: bool):
    print(("[DRY] " if dry else "[DO ] ") + msg, flush=True)


def tenant_dir() -> Path:
    return HOME / "tenants" / TENANT_ID


def user_dir(uid: str) -> Path:
    return tenant_dir() / "users" / uid


def _move_then_link(src: Path, dst: Path, dry: bool):
    """移动 src → dst 后在 src 留下指向 dst 的 symlink（保 legacy 路径兼容）。"""
    if not src.exists() or src.is_symlink():
        log(f"skip   {src} (missing or already symlink)", dry)
        return
    if dst.exists():
        log(f"exists {dst} (not overwriting)", dry)
        return
    log(f"move   {src} → {dst}", dry)
    if not dry:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        src.symlink_to(dst)
        log(f"ln -s  {dst} {src}  (compat)", dry)


def migrate(uid: str, email: str, display: str, dry: bool):
    if not SLUG_RE.match(uid):
        print(f"❌ invalid uid: {uid!r}", file=sys.stderr)
        sys.exit(1)

    tdir = tenant_dir()
    udir = user_dir(uid)

    # 1. dirs
    for d in [HOME, tdir, tdir / "shared", udir, udir / "state"]:
        if d.exists():
            log(f"exists {d}", dry)
        else:
            log(f"mkdir  {d}", dry)
            if not dry:
                d.mkdir(parents=True, exist_ok=True)

    # 2. tenant-scope files
    for fn in TENANT_FILES:
        _move_then_link(APP_DIR / fn, tdir / fn, dry)

    # 3. user settings
    _move_then_link(APP_DIR / USER_SETTINGS, udir / USER_SETTINGS, dry)

    # 4. user state
    for fn in USER_STATE_FILES:
        _move_then_link(APP_DIR / fn, udir / "state" / fn, dry)

    # 5. profile.json — 核心：记录 vault_path = 原 $OME365_VAULT
    profile_fp = udir / "profile.json"
    if profile_fp.exists():
        log(f"exists {profile_fp} (not overwriting)", dry)
    else:
        profile = {
            "user_id": uid,
            "tenant_id": TENANT_ID,
            "display_name": display,
            "email": email,
            "roles": ["admin"],
            "provider": "none",
            "provider_uid": uid,
            "vault_path": str(LEGACY_VAULT),
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        log(f"write  {profile_fp}", dry)
        if not dry:
            profile_fp.write_text(json.dumps(profile, indent=2, ensure_ascii=False), "utf-8")

    print("\n" + "─" * 60)
    print(f"Migration {'PLAN' if dry else 'DONE'} · tenant={TENANT_ID} user={uid}")
    print(f"  OME365_HOME   : {HOME}")
    print(f"  user dir      : {udir}")
    print(f"  vault_path    : {LEGACY_VAULT}  (unchanged, referenced by profile.json)")
    print("─" * 60)
    print(f"\nRollback:  OME365_HOME={HOME} python3 scripts/migrate_to_multiuser.py --rollback --uid {uid}")
    if dry:
        print("\n(dry-run — no changes made)")


def rollback(uid: str, dry: bool):
    tdir = tenant_dir()
    udir = user_dir(uid)

    # 还原 tenant files
    for fn in TENANT_FILES:
        link, real = APP_DIR / fn, tdir / fn
        if link.is_symlink() and real.exists():
            log(f"restore {link}", dry)
            if not dry:
                link.unlink()
                shutil.move(str(real), str(link))

    # 还原 settings
    link, real = APP_DIR / USER_SETTINGS, udir / USER_SETTINGS
    if link.is_symlink() and real.exists():
        log(f"restore {link}", dry)
        if not dry:
            link.unlink()
            shutil.move(str(real), str(link))

    # 还原 state
    for fn in USER_STATE_FILES:
        link, real = APP_DIR / fn, udir / "state" / fn
        if link.is_symlink() and real.exists():
            log(f"restore {link}", dry)
            if not dry:
                link.unlink()
                shutil.move(str(real), str(link))

    # 清理 tenants/ 树
    if (HOME / "tenants").exists():
        log(f"rm -rf {HOME / 'tenants'}", dry)
        if not dry:
            shutil.rmtree(HOME / "tenants")
    # HOME 目录若为空且不是 home 根则清掉
    if HOME.exists() and HOME != Path.home() and not any(HOME.iterdir()):
        log(f"rmdir  {HOME}", dry)
        if not dry:
            HOME.rmdir()

    print(f"\nRollback {'PLAN' if dry else 'DONE'}")


def main():
    ap = argparse.ArgumentParser(description="Ome365 single-user → multi-user migration")
    ap.add_argument("--uid", default="captain", help="user slug (^[a-z][a-z0-9_-]{1,31}$)")
    ap.add_argument("--email", default="", help="user email (profile.json)")
    ap.add_argument("--display", default="", help="display name (profile.json)")
    ap.add_argument("--dry-run", action="store_true", help="preview only")
    ap.add_argument("--rollback", action="store_true", help="undo a previous migration")
    args = ap.parse_args()

    if args.rollback:
        rollback(args.uid, dry=args.dry_run)
    else:
        migrate(args.uid, args.email, args.display or args.uid.title(), dry=args.dry_run)


if __name__ == "__main__":
    main()
