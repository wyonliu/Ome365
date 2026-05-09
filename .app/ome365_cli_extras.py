"""
ome365.cli_extras · v1.1.3 polish · 3 lightweight CLI subcommands
[decision: 2026-05-09-v1-1-3-polish]

  · ome365 verify <agent-card-url>   · ed25519 verify a remote agent-card
  · ome365 status                    · one-glance vault overview
  · ome365 eval member <actor>       · CLI mirror of /api/eval/member
  · ome365 eval finops [scope]       · CLI mirror of /api/eval/finops
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path


def _vault_root() -> Path:
    return Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()


# ── verify ──────────────────────────────────────────────────────────────────


def cmd_verify(argv: list[str]) -> int:
    if not argv:
        print("usage: ome365 verify <agent-card-url-or-file>", flush=True)
        return 2
    arg = argv[0]
    try:
        if arg.startswith("http://") or arg.startswith("https://"):
            with urllib.request.urlopen(arg, timeout=5) as r:
                data = json.loads(r.read())
        else:
            data = json.loads(Path(arg).read_text("utf-8"))
    except Exception as e:
        print(f"ERROR: cannot fetch/parse {arg}: {e}", flush=True)
        return 2

    if not data.get("signature"):
        print(f"\033[33m! unsigned\033[0m  {arg}")
        return 1

    try:
        from ome365_signing import verify
    except ImportError:
        print("ERROR: install cryptography>=41 to verify", flush=True)
        return 2

    if verify(data):
        print(f"\033[32m✓ valid\033[0m  {arg}")
        print(f"  alg:      {data.get('signing_alg')}")
        pk = data.get("signing_pubkey_b64", "")
        print(f"  pubkey:   {pk[:32]}...")
        print(f"  name:     {data.get('name')}")
        print(f"  version:  {data.get('version')}")
        return 0
    else:
        print(f"\033[31m✗ invalid signature\033[0m  {arg}")
        return 1


# ── status ──────────────────────────────────────────────────────────────────


def cmd_status(argv: list[str]) -> int:
    """One-glance vault summary · what's in there · how big · how recent."""
    try:
        from ome365_eval import grep_decisions_all, grep_skills_all, grep_trace_all
    except ImportError:
        print("ERROR: ome365_eval not importable", flush=True)
        return 2

    v = _vault_root()
    print("─" * 60)
    print(f"  Ome365 status · vault={v}")
    print("─" * 60)

    decisions = grep_decisions_all(v)
    closed = sum(1 for d in decisions if d.status == "closed")
    open_ = sum(1 for d in decisions if d.status == "open")
    print(f"  Decisions   : {len(decisions)} ({closed} closed · {open_} open)")
    if decisions:
        owners = {d.owner for d in decisions if d.owner}
        print(f"                owners: {', '.join(sorted(owners))}")

    traces = grep_trace_all(v)
    print(f"  Traces      : {len(traces)}")
    if traces:
        cost = sum(t.cost_usd for t in traces)
        actors = {t.actor for t in traces}
        print(f"                ${cost:.3f} total · {len(actors)} actors")

    skills = grep_skills_all(v)
    print(f"  Skills      : {len(skills)}")
    if skills:
        authors = {s.author for s in skills}
        print(f"                authors: {', '.join(sorted(a for a in authors if a))}")

    # Knowledge / L2-distilled
    l2 = v / "Knowledge" / "L2-distilled"
    if l2.exists():
        files = list(l2.glob("*.md"))
        print(f"  Wiki (L2)   : {len(files)} categor{'y' if len(files) == 1 else 'ies'}")

    # Audit
    audit = v / "Audit"
    if audit.exists():
        n = sum(1 for fp in audit.glob("*.jsonl"))
        print(f"  Audit       : {n} day file(s)")

    # Backups
    backups = v / "Backups"
    if backups.exists():
        bks = list(backups.glob("vault-*.tar.gz"))
        if bks:
            latest = max(bks, key=lambda p: p.stat().st_mtime)
            from datetime import datetime, timezone
            mtime = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)
            age_days = (date.today() - mtime.date()).days
            print(f"  Backups     : {len(bks)} · latest {age_days}d ago ({latest.name})")

    # Roles
    roles_fp = v / ".ome365" / "roles.yml"
    if roles_fp.exists():
        try:
            from ome365_rbac import load_roles
            cfg = load_roles(v)
            n_members = len(cfg.get("members", {}))
            print(f"  Roles (RBAC): {n_members} members · default={cfg.get('default_role')}")
        except Exception:
            print(f"  Roles (RBAC): config present (parse failed)")

    # Signing
    key_fp = v / ".ome365" / "keys" / "agent-card.ed25519"
    if key_fp.exists():
        try:
            from ome365_signing import public_key_b64
            pk = public_key_b64(v)
            print(f"  Signing key : ed25519 · {pk[:32]}...")
        except Exception:
            print(f"  Signing key : present (load failed)")

    print("─" * 60)
    return 0


# ── eval ────────────────────────────────────────────────────────────────────


def cmd_eval(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "usage:\n"
            "  ome365 eval member <actor> [--window-days N]\n"
            "  ome365 eval finops [<scope>] [--window-days N]\n"
            "  ome365 eval skills\n"
            "  ome365 eval whoami\n",
        )
        return 0

    cmd = argv[0]
    rest = argv[1:]
    args: dict = {}
    positional: list[str] = []
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok.startswith("--") and i + 1 < len(rest):
            args[tok.lstrip("-").replace("-", "_")] = rest[i + 1]
            i += 2
        else:
            positional.append(tok)
            i += 1

    try:
        from ome365_eval import (
            dashboard_data, eval_member as _eval, finops_summary,
            grep_skills_all,
        )
    except ImportError as e:
        print(f"ERROR: ome365_eval not importable: {e}", flush=True)
        return 2

    v = _vault_root()
    window_days = int(args.get("window_days", "365"))

    if cmd == "member":
        if not positional:
            print("ERROR: ome365 eval member <actor>", flush=True)
            return 2
        try:
            r = _eval(v, positional[0], window_days=window_days)
        except Exception as e:
            print(f"ERROR: {e}", flush=True)
            return 2
        print(f"=== eval · {r['member_id']} · {window_days}d window ===")
        for dim, s in r["dimensions"].items():
            score = f"{s['score']:.2f}/5" if s["score"] is not None else s["reason"]
            print(f"  {dim:<28} {score:<20} (n={s['n']})")
        if r.get("total_score") is not None:
            print(f"  {'total':<28} {r['total_score']:.2f}/5  preset={r.get('preset')}")
        print(f"\n  ⚠ {r['warning']}")
        print(f"  ⚠ {r['anti_tokenmaxxing_note']}")
        return 0

    if cmd == "finops":
        scope = positional[0] if positional else "dashboard"
        try:
            if scope == "dashboard":
                r = dashboard_data(v, since_days=window_days)
                print(f"=== finops dashboard · {window_days}d ===")
                for k, s in r["by_scope"].items():
                    print(f"  {k:<32} ${s['value']:.3f} {s['unit']}")
                print(f"\n  by actor (top 5):")
                actors = sorted(r["by_actor"].items(),
                                key=lambda kv: -kv[1]["cost_usd"])[:5]
                for name, stats in actors:
                    print(f"    {name:<10} {stats['requests']:>4} req  "
                          f"${stats['cost_usd']:.3f} → ${stats['value_usd']:.2f}")
            else:
                r = finops_summary(v, scope=scope, since_days=window_days)
                print(json.dumps(r, indent=2, ensure_ascii=False))
        except ValueError as e:
            print(f"ERROR: {e}", flush=True)
            return 2
        return 0

    if cmd == "skills":
        skills = grep_skills_all(v)
        print(f"=== {len(skills)} skill(s) ===")
        for s in skills:
            print(f"  {s.name:<32} @{s.author}  "
                  f"{s.created.isoformat() if s.created else '-'}")
        return 0

    if cmd == "whoami":
        # Mirror the HTTP /api/eval/whoami logic
        actor = os.environ.get("OME365_ACTOR", "").strip()
        if actor:
            print(json.dumps({"actor": actor, "source": "env"}, ensure_ascii=False))
            return 0
        whoami_fp = v / ".ome365" / "whoami"
        if whoami_fp.exists():
            actor = whoami_fp.read_text("utf-8").strip()
            if actor:
                print(json.dumps({"actor": actor, "source": "vault"}, ensure_ascii=False))
                return 0
        try:
            from collections import Counter
            from ome365_eval import grep_decisions_all
            decisions = grep_decisions_all(v)
            owners = [d.owner for d in decisions if d.owner]
            most = Counter(owners).most_common(1)
            if most:
                print(json.dumps({"actor": most[0][0], "source": "vault_inferred"},
                                  ensure_ascii=False))
                return 0
        except Exception:
            pass
        print(json.dumps({"actor": "alice", "source": "default"}))
        return 0

    print(f"ERROR: unknown subcommand '{cmd}' (try member | finops | skills | whoami)", flush=True)
    return 2


__all__ = ["cmd_verify", "cmd_status", "cmd_eval"]
