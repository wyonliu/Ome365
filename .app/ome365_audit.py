"""
ome365.audit · v1.1.1 P2 #13 · who-did-what append-only audit log
[decision: 2026-05-09-p2-async-trace-and-audit]

Compliance: SOC2 CC7.2 · ISO27001 A.12.4.1 · GDPR Art. 30
Schema: Audit/<date>.jsonl · {ts, actor, action, target_type, target_id, details, source_ip}

12 actions:
  decision.create / decision.close / decision.calibrate
  skill.create / skill.update
  trace.log
  wiki.update
  backup.create / backup.restore
  eval.member.compute
  share.create / share.revoke
  archive.run
  config.change
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


VALID_ACTIONS = {
    "decision.create", "decision.close", "decision.calibrate",
    "skill.create", "skill.update",
    "trace.log",
    "wiki.update",
    "backup.create", "backup.restore",
    "eval.member.compute",
    "share.create", "share.revoke",
    "archive.run",
    "config.change",
}


def _vault_root(vault: Optional[Path] = None) -> Path:
    if vault:
        return Path(vault).resolve()
    return Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()


def log(
    *,
    actor: str,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    details: Optional[dict] = None,
    source_ip: Optional[str] = None,
    vault: Optional[Path] = None,
    when: Optional[datetime] = None,
) -> Path:
    """Append one audit line. Returns file path."""
    when = when or datetime.now(timezone.utc)
    if action not in VALID_ACTIONS:
        # Allow non-strict actions but tag them
        details = (details or {}) | {"_unknown_action": True}

    line = {
        "ts": when.isoformat().replace("+00:00", "Z"),
        "actor": actor,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "details": details or {},
        "source_ip": source_ip,
    }

    v = _vault_root(vault)
    audit_dir = v / "Audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    fp = audit_dir / f"{when.date().isoformat()}.jsonl"
    with fp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return fp


def grep_recent(
    *,
    actor: Optional[str] = None,
    action: Optional[str] = None,
    target_id: Optional[str] = None,
    days: int = 30,
    vault: Optional[Path] = None,
    limit: int = 100,
) -> list[dict]:
    """Tail audit log · returns matching dicts (newest-first up to limit)."""
    v = _vault_root(vault)
    audit_dir = v / "Audit"
    if not audit_dir.exists():
        return []

    from datetime import timedelta
    since_dt = datetime.now(timezone.utc) - timedelta(days=days)

    out: list[dict] = []
    for fp in sorted(audit_dir.glob("*.jsonl"), reverse=True):
        for line in reversed(fp.read_text("utf-8").splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_str = j.get("ts", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if ts < since_dt:
                continue
            if actor and j.get("actor") != actor:
                continue
            if action and j.get("action") != action:
                continue
            if target_id and j.get("target_id") != target_id:
                continue
            out.append(j)
            if len(out) >= limit:
                return out
    return out


def cli_main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "usage:\n"
            "  ome365 audit log --actor X --action decision.close [--target-type decision --target-id D]\n"
            "  ome365 audit grep [--actor X] [--action A] [--target-id T] [--days 30]\n"
        )
        return 0

    cmd = argv[0]
    rest = argv[1:]
    args: dict = {}
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok.startswith("--") and i + 1 < len(rest):
            args[tok.lstrip("-").replace("-", "_")] = rest[i + 1]
            i += 2
        else:
            i += 1

    if cmd == "log":
        if "actor" not in args or "action" not in args:
            print("ERROR: --actor and --action required", flush=True)
            return 2
        path = log(
            actor=args["actor"],
            action=args["action"],
            target_type=args.get("target_type"),
            target_id=args.get("target_id"),
            details=json.loads(args["details"]) if "details" in args else None,
        )
        print(f"audit → {path}")
        return 0

    if cmd == "grep":
        rows = grep_recent(
            actor=args.get("actor"),
            action=args.get("action"),
            target_id=args.get("target_id"),
            days=int(args.get("days", "30")),
            limit=int(args.get("limit", "100")),
        )
        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
        print(f"--- {len(rows)} rows", flush=True)
        return 0

    print(f"ERROR: unknown subcommand '{cmd}' (try log | grep)", flush=True)
    return 2


__all__ = ["log", "grep_recent", "cli_main", "VALID_ACTIONS"]
