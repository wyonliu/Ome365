"""
ome365.backup · v1.1.1 P1 #8 · vault snapshot + restore (tar.gz)
[decision: 2026-05-09-p1-backup-and-metrics]

stdlib only · 0 deps · 3 subcommands:
  · ome365 backup create [--dest DIR]   → vault → tar.gz timestamped
  · ome365 backup restore <tarball>     → tarball → vault (safe: backs up first)
  · ome365 backup list [--dir DIR]      → list backups with size + date

Default-include: Decisions/ Trace/ Skills/ Knowledge/ Contacts/ .ome365/eval-config.yml
Default-exclude: .ome365/notify_webhooks.json (secrets) · .git/ · __pycache__/ · *.pyc
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DEFAULT_INCLUDE = [
    "Decisions", "Trace", "Skills", "Knowledge", "Contacts",
    "Notes", "Journal", "Memory", "Insights",
]
DEFAULT_INCLUDE_FILES = [
    ".ome365/eval-config.yml",
]
DEFAULT_EXCLUDE_PATTERNS = [
    "__pycache__", ".pyc", ".git",
    "notify_webhooks.json",  # secrets
    "share_auth.db",  # session cookies
    "share_registry.json",  # share state
]


def _vault_root(vault: Optional[Path] = None) -> Path:
    if vault:
        return Path(vault).resolve()
    return Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()


def _filter_excluded(tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
    """Drop secrets / cache / git from tarball."""
    name = tarinfo.name
    for pat in DEFAULT_EXCLUDE_PATTERNS:
        if pat in name:
            return None
    return tarinfo


def create(
    vault: Optional[Path] = None,
    dest: Optional[Path] = None,
    *,
    when: Optional[datetime] = None,
    dry_run: bool = False,
) -> Path | dict:
    """Create tar.gz of vault. Returns path to tarball.

    dry_run=True: returns dict {dry_run, would_include_count, would_skip_count,
                  would_write_to} without touching disk."""
    v = _vault_root(vault)
    when = when or datetime.now(timezone.utc)
    timestamp = when.strftime("%Y%m%dT%H%M%S")

    dest_dir = Path(dest).resolve() if dest else v / "Backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"vault-{timestamp}.tar.gz"

    if dry_run:
        # Walk what would be included without writing
        n_would = 0
        n_skipped = 0
        for sub in DEFAULT_INCLUDE:
            sub_path = v / sub
            if sub_path.is_dir():
                for fp in sub_path.rglob("*"):
                    if not fp.is_file():
                        continue
                    if any(pat in str(fp) for pat in DEFAULT_EXCLUDE_PATTERNS):
                        n_skipped += 1
                    else:
                        n_would += 1
            elif sub_path.is_file():
                n_would += 1
        for f in DEFAULT_INCLUDE_FILES:
            if (v / f).exists():
                n_would += 1
        return {
            "dry_run": True,
            "would_include_count": n_would,
            "would_skip_count": n_skipped,
            "would_write_to": str(out),
            "vault": str(v),
        }

    n_files = 0
    n_bytes = 0
    with tarfile.open(out, "w:gz") as tar:
        for sub in DEFAULT_INCLUDE:
            sub_path = v / sub
            if sub_path.exists():
                tar.add(sub_path, arcname=sub, filter=_filter_excluded)
                # Tally
                if sub_path.is_dir():
                    for fp in sub_path.rglob("*"):
                        if fp.is_file() and not any(
                            pat in str(fp) for pat in DEFAULT_EXCLUDE_PATTERNS
                        ):
                            n_files += 1
                            try:
                                n_bytes += fp.stat().st_size
                            except OSError:
                                pass

        for f in DEFAULT_INCLUDE_FILES:
            fp = v / f
            if fp.exists():
                tar.add(fp, arcname=f)
                n_files += 1
                try:
                    n_bytes += fp.stat().st_size
                except OSError:
                    pass

    return out


def restore(
    tarball: Path,
    vault: Optional[Path] = None,
    *,
    safe: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Restore tarball into vault. Safe mode (default) backs up existing vault first.

    dry_run=True: validates tarball + returns preview without extracting.
        Returns {dry_run, n_files, total_bytes, sample_files, would_restore_to,
                 would_backup_prior}.

    Returns: {restored_to, prior_backup, n_files}
    """
    v = _vault_root(vault)
    src = Path(tarball).resolve()
    if not src.exists():
        raise FileNotFoundError(f"backup tarball not found: {src}")

    if dry_run:
        n_files = 0
        total_bytes = 0
        sample = []
        with tarfile.open(src, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name.startswith("/") or ".." in member.name.split("/"):
                    raise ValueError(f"unsafe member path in tarball: {member.name}")
                n_files += 1
                total_bytes += member.size
                if len(sample) < 10:
                    sample.append(member.name)
        would_backup_prior = bool(safe and v.exists() and any(v.iterdir()))
        return {
            "dry_run": True,
            "tarball": str(src),
            "n_files": n_files,
            "total_bytes": total_bytes,
            "sample_files": sample,
            "would_restore_to": str(v),
            "would_backup_prior": would_backup_prior,
        }

    prior_backup = None
    if safe and v.exists() and any(v.iterdir()):
        prior_backup = create(vault=v, dest=v / "Backups" / "_pre_restore")

    n_files = 0
    with tarfile.open(src, "r:gz") as tar:
        # Filter for path traversal safety
        for member in tar.getmembers():
            if member.name.startswith("/") or ".." in member.name.split("/"):
                raise ValueError(f"unsafe member path in tarball: {member.name}")
            n_files += 1
        # Extract — Python 3.12+ has filter; older falls back
        try:
            tar.extractall(v, filter="data")  # type: ignore[arg-type]
        except TypeError:
            tar.extractall(v)

    return {
        "restored_to": str(v),
        "prior_backup": str(prior_backup) if prior_backup else None,
        "tarball": str(src),
        "n_files": n_files,
    }


def list_backups(directory: Optional[Path] = None) -> list[dict]:
    """List backups in a directory · sorted newest-first."""
    d = Path(directory).resolve() if directory else _vault_root() / "Backups"
    if not d.exists():
        return []
    out = []
    for fp in sorted(d.glob("vault-*.tar.gz"), reverse=True):
        try:
            st = fp.stat()
            out.append({
                "name": fp.name,
                "path": str(fp),
                "size_bytes": st.st_size,
                "size_mb": round(st.st_size / (1024 * 1024), 2),
                "modified": datetime.fromtimestamp(
                    st.st_mtime, tz=timezone.utc
                ).isoformat().replace("+00:00", "Z"),
            })
        except OSError:
            continue
    return out


def cli_main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "usage:\n"
            "  ome365 backup create [--dest DIR] [--dry-run]\n"
            "  ome365 backup restore <tarball> [--unsafe] [--dry-run]\n"
            "  ome365 backup list [--dir DIR]\n"
        )
        return 0

    cmd = argv[0]
    rest = argv[1:]
    args: dict = {}
    positional: list[str] = []
    dry_run = False
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok == "--unsafe":
            args["unsafe"] = True
            i += 1
        elif tok == "--dry-run":
            dry_run = True
            i += 1
        elif tok.startswith("--") and i + 1 < len(rest):
            args[tok.lstrip("-").replace("-", "_")] = rest[i + 1]
            i += 2
        else:
            positional.append(tok)
            i += 1

    if cmd == "create":
        out = create(dest=args.get("dest"), dry_run=dry_run)
        if dry_run:
            print(json.dumps(out, indent=2, ensure_ascii=False))
        else:
            size_mb = out.stat().st_size / (1024 * 1024)
            print(f"created → {out} ({size_mb:.2f} MB)")
        return 0

    if cmd == "restore":
        if not positional:
            print("ERROR: restore needs a tarball path", flush=True)
            return 2
        try:
            result = restore(
                Path(positional[0]),
                safe=not args.get("unsafe", False),
                dry_run=dry_run,
            )
            print(json.dumps(result, indent=2))
            return 0
        except (FileNotFoundError, ValueError) as e:
            print(f"ERROR: {e}", flush=True)
            return 2

    if cmd == "list":
        rows = list_backups(args.get("dir"))
        if not rows:
            print("no backups found", flush=True)
            return 0
        for r in rows:
            print(f"  {r['name']:<40} {r['size_mb']:>6.2f} MB  {r['modified']}")
        print(f"--- {len(rows)} backup(s)", flush=True)
        return 0

    print(f"ERROR: unknown subcommand '{cmd}' (try create | restore | list)", flush=True)
    return 2


__all__ = ["create", "restore", "list_backups", "cli_main"]
