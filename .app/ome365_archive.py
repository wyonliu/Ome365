"""
ome365.archive · v1.1 W7 · Moxt-style 95%/5% nightly archive
[decision: 2026-05-09-archive-agent-card-w7]

Move old Trace/<YYYY-MM-DD>.jsonl into Trace/archive/<YYYY-MM>.jsonl.gz
to keep hot path small (typical 5-10x compression, 90%+ files moved).

Operations:
  · archive(vault, older_than_days=30) → returns {moved: N, archived: paths}
  · recall(vault, period='YYYY-MM') → iter of trace dicts (parses .gz)
  · cli_main · `ome365 archive [--older-than 30]`
"""
from __future__ import annotations

import gzip
import json
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

ARCHIVE_DIR_REL = Path("Trace") / "archive"
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.jsonl$")


def _vault_root(vault: Optional[Path] = None) -> Path:
    if vault:
        return Path(vault).resolve()
    return Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()


def archive(
    vault: Optional[Path] = None,
    older_than_days: int = 30,
    today: Optional[date] = None,
    dry_run: bool = False,
) -> dict:
    """
    Move per-day Trace/<YYYY-MM-DD>.jsonl files older than `older_than_days`
    into Trace/archive/<YYYY-MM>.jsonl.gz · concatenated by month bucket.
    Idempotent: re-running on same input is a no-op.

    dry_run=True: report what WOULD be moved without touching disk.

    Returns:
      {"moved": int, "skipped_recent": int, "archived": [<rel-path>...], "dry_run": bool}
    """
    v = _vault_root(vault)
    trace_dir = v / "Trace"
    if not trace_dir.exists():
        return {"moved": 0, "skipped_recent": 0, "archived": []}

    arc_dir = v / ARCHIVE_DIR_REL
    arc_dir.mkdir(parents=True, exist_ok=True)
    cutoff = (today or date.today()) - timedelta(days=older_than_days)

    by_month: dict[str, list[Path]] = defaultdict(list)
    skipped_recent = 0
    for fp in sorted(trace_dir.glob("*.jsonl")):
        m = DATE_RE.match(fp.name)
        if not m:
            continue
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        if d > cutoff:
            skipped_recent += 1
            continue
        period = f"{d.year}-{d.month:02d}"
        by_month[period].append(fp)

    archived: list[str] = []
    moved = 0
    if dry_run:
        for period, files in sorted(by_month.items()):
            target = arc_dir / f"{period}.jsonl.gz"
            archived.append(str(target.relative_to(v)))
            moved += len(files)
        return {
            "moved": 0,
            "would_move": moved,
            "skipped_recent": skipped_recent,
            "archived": [],
            "would_archive": archived,
            "older_than_days": older_than_days,
            "dry_run": True,
        }

    for period, files in sorted(by_month.items()):
        target = arc_dir / f"{period}.jsonl.gz"
        # Append mode for gzip concatenation works (gzip handles multi-member transparently)
        with gzip.open(target, "ab") as gz:
            for src in files:
                data = src.read_bytes()
                if not data.endswith(b"\n"):
                    data += b"\n"
                gz.write(data)
        for src in files:
            src.unlink()
            moved += 1
        archived.append(str(target.relative_to(v)))

    return {
        "moved": moved,
        "skipped_recent": skipped_recent,
        "archived": archived,
        "older_than_days": older_than_days,
    }


def recall(period: str, vault: Optional[Path] = None) -> Iterable[dict]:
    """Yield trace dicts from Trace/archive/<period>.jsonl.gz · empty iter if absent."""
    v = _vault_root(vault)
    fp = v / ARCHIVE_DIR_REL / f"{period}.jsonl.gz"
    if not fp.exists():
        return
    with gzip.open(fp, "rt", encoding="utf-8") as gz:
        for line in gz:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def list_periods(vault: Optional[Path] = None) -> list[dict]:
    """List archived month buckets · sorted oldest-first.

    Returns list of {period, path, size_bytes, size_mb, modified}.
    """
    from datetime import datetime, timezone
    v = _vault_root(vault)
    arc_dir = v / ARCHIVE_DIR_REL
    if not arc_dir.exists():
        return []
    out: list[dict] = []
    for fp in sorted(arc_dir.glob("*.jsonl.gz")):
        try:
            st = fp.stat()
            period = fp.name.replace(".jsonl.gz", "")
            out.append({
                "period": period,
                "path": str(fp),
                "size_bytes": st.st_size,
                "size_mb": round(st.st_size / (1024 * 1024), 3),
                "modified": datetime.fromtimestamp(
                    st.st_mtime, tz=timezone.utc,
                ).isoformat().replace("+00:00", "Z"),
            })
        except OSError:
            continue
    return out


def cli_main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "usage:\n"
            "  ome365 archive [--older-than 30] [--dry-run]\n"
            "  ome365 archive recall --period YYYY-MM\n"
            "  ome365 archive list                 # list archived periods\n"
        )
        return 0

    rest = argv[:]
    args: dict = {}
    positional: list[str] = []
    dry_run = False
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok == "--dry-run":
            dry_run = True
            i += 1
        elif tok.startswith("--") and i + 1 < len(rest):
            args[tok.lstrip("-").replace("-", "_")] = rest[i + 1]
            i += 2
        else:
            positional.append(tok)
            i += 1

    if positional and positional[0] == "recall":
        period = args.get("period")
        if not period:
            print("ERROR: recall needs --period YYYY-MM", flush=True)
            return 2
        n = 0
        for r in recall(period):
            print(json.dumps(r, ensure_ascii=False))
            n += 1
        print(f"--- {n} rows from {period}", flush=True)
        return 0

    if positional and positional[0] == "list":
        rows = list_periods()
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0

    older = int(args.get("older_than", "30"))
    result = archive(older_than_days=older, dry_run=dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


__all__ = ["archive", "recall", "list_periods", "cli_main"]
