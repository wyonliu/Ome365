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


def _collect_status(v: Path) -> dict:
    """Gather status data once · used by both text and JSON output."""
    from ome365_eval import grep_decisions_all, grep_skills_all, grep_trace_all
    decisions = grep_decisions_all(v)
    closed = sum(1 for d in decisions if d.status == "closed")
    open_ = sum(1 for d in decisions if d.status == "open")
    owners = sorted({d.owner for d in decisions if d.owner})

    traces = grep_trace_all(v)
    trace_cost = sum(t.cost_usd for t in traces)
    trace_actors = sorted({t.actor for t in traces})

    skills = grep_skills_all(v)
    skill_authors = sorted({s.author for s in skills if s.author})

    l2 = v / "Knowledge" / "L2-distilled"
    wiki_categories = len(list(l2.glob("*.md"))) if l2.exists() else 0

    audit_dir = v / "Audit"
    audit_files = sum(1 for _ in audit_dir.glob("*.jsonl")) if audit_dir.exists() else 0

    backups_dir = v / "Backups"
    backup_info = None
    if backups_dir.exists():
        bks = list(backups_dir.glob("vault-*.tar.gz"))
        if bks:
            from datetime import datetime, timezone
            latest = max(bks, key=lambda p: p.stat().st_mtime)
            mtime = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)
            backup_info = {
                "count": len(bks),
                "latest_name": latest.name,
                "latest_age_days": (date.today() - mtime.date()).days,
            }

    rbac_info = None
    roles_fp = v / ".ome365" / "roles.yml"
    if roles_fp.exists():
        try:
            from ome365_rbac import load_roles
            cfg = load_roles(v)
            rbac_info = {
                "members": len(cfg.get("members", {})),
                "default_role": cfg.get("default_role", "contributor"),
            }
        except Exception:
            rbac_info = {"error": "parse failed"}

    signing_info = None
    key_fp = v / ".ome365" / "keys" / "agent-card.ed25519"
    if key_fp.exists():
        try:
            from ome365_signing import public_key_b64
            signing_info = {"alg": "ed25519", "pubkey_b64": public_key_b64(v)}
        except Exception:
            signing_info = {"error": "load failed"}

    return {
        "vault": str(v),
        "decisions": {
            "total": len(decisions),
            "closed": closed,
            "open": open_,
            "owners": owners,
        },
        "traces": {
            "total": len(traces),
            "cost_usd": round(trace_cost, 3),
            "actors": trace_actors,
        },
        "skills": {"total": len(skills), "authors": skill_authors},
        "wiki_categories": wiki_categories,
        "audit_files": audit_files,
        "backups": backup_info,
        "rbac": rbac_info,
        "signing": signing_info,
    }


def cmd_status(argv: list[str]) -> int:
    """One-glance vault summary · what's in there · how big · how recent."""
    try:
        v = _vault_root()
        data = _collect_status(v)
    except ImportError:
        print("ERROR: ome365_eval not importable", flush=True)
        return 2

    if "--json" in argv:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    print("─" * 60)
    print(f"  Ome365 status · vault={data['vault']}")
    print("─" * 60)

    d = data["decisions"]
    print(f"  Decisions   : {d['total']} ({d['closed']} closed · {d['open']} open)")
    if d["owners"]:
        print(f"                owners: {', '.join(d['owners'])}")

    t = data["traces"]
    print(f"  Traces      : {t['total']}")
    if t["total"]:
        print(f"                ${t['cost_usd']:.3f} total · {len(t['actors'])} actors")

    s = data["skills"]
    print(f"  Skills      : {s['total']}")
    if s["authors"]:
        print(f"                authors: {', '.join(s['authors'])}")

    if data["wiki_categories"]:
        n = data["wiki_categories"]
        print(f"  Wiki (L2)   : {n} categor{'y' if n == 1 else 'ies'}")

    if data["audit_files"]:
        print(f"  Audit       : {data['audit_files']} day file(s)")

    bk = data["backups"]
    if bk:
        print(f"  Backups     : {bk['count']} · latest {bk['latest_age_days']}d ago "
              f"({bk['latest_name']})")

    if data["rbac"]:
        rb = data["rbac"]
        if "error" in rb:
            print(f"  Roles (RBAC): config present ({rb['error']})")
        else:
            print(f"  Roles (RBAC): {rb['members']} members · default={rb['default_role']}")

    if data["signing"]:
        sg = data["signing"]
        if "error" in sg:
            print(f"  Signing key : present ({sg['error']})")
        else:
            print(f"  Signing key : ed25519 · {sg['pubkey_b64'][:32]}...")

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
