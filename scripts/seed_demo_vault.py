#!/usr/bin/env python3
"""
scripts/seed_demo_vault.py · v1.1.1 P0 #1
[decision: 2026-05-09-p0-1-demo-seed-shock]

Generates a realistic vault.example with 12 real-world decisions + 30 traces
across 5 actors and 3 months. Replaces alice/bob hello-world with a demo that
makes a team think "we could use this" within 3 minutes of opening /v1_1.html.

Idempotent: rerun overwrites existing demo files (Decisions/d-*.md and traces).
Self-authored W*-* decisions are preserved (they are real history).

Usage:
    python3 scripts/seed_demo_vault.py [--vault path]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ACTORS = ["alice", "bob", "carol", "dan", "erin"]


# ── 12 Decisions across 5 categories ────────────────────────────────────────

DECISIONS = [
    # Engineering (3)
    {
        "id_slug": "pick-database-pg-vs-sqlite",
        "category": "infra",
        "owner": "alice",
        "participants": ["bob", "carol"],
        "title": "Pick database · PG vs SQLite for v2",
        "outcome": "Postgres for v2 multi-tenant · SQLite stays for solo mode",
        "anchors": ["P", "L", "维护性"],
        "roi_estimated": "Multi-tenant unblocked · ~3 day investment",
        "planned_days": 4, "elapsed_days": 5,
        "days_ago": 75,
        "problem": "Hike v0.1 ships on SQLite. v2 needs RLS + concurrent writes for >5 user tenants. SQLite WAL helps but RLS is PG-only.",
        "options": "A. PG + RLS (proven, 3-day port)\nB. SQLite + app-level tenant filter (ships today, no RLS guarantee)\nC. PostgresLite (immature 2026)",
        "decision": "PG via existing dao/__init__.py adapter · keep SQLite for solo mode (zero-config dev)",
    },
    {
        "id_slug": "ci-roadmap-2026q2",
        "category": "infra",
        "owner": "bob",
        "participants": ["alice"],
        "title": "CI roadmap 2026 Q2 · GitHub Actions vs CircleCI",
        "outcome": "GitHub Actions · 5 jobs · matrix on macos/ubuntu/wsl",
        "anchors": ["P", "M"],
        "roi_estimated": "Save 6h/month CI debug time",
        "planned_days": 2, "elapsed_days": 2,
        "days_ago": 60,
        "problem": "v1.0 ship needs CI matrix. CircleCI nice but adds vendor; GHA is free + same repo.",
        "options": "A. GHA matrix + 5 parallel jobs\nB. CircleCI orbs (custom pricing)\nC. Self-hosted runners (cost too high for OSS)",
        "decision": "GHA · 5 jobs (lint + pytest + pii + docker + integration) · runs on every PR",
    },
    {
        "id_slug": "auth-provider-strategy",
        "category": "infra",
        "owner": "alice",
        "participants": ["dan"],
        "title": "AuthProvider · 5 modes for v0.9.6",
        "outcome": "5-tier abstraction (none / basic / magic_link / oidc / wecom)",
        "anchors": ["P", "XL"],
        "roi_estimated": "Solo + family + enterprise all served from one binary",
        "planned_days": 3, "elapsed_days": 3,
        "days_ago": 50,
        "problem": "v0.9.5 only had basic auth. Family wants no auth; enterprise wants OIDC.",
        "options": "A. 5-tier provider abstraction (one binary, env-config switches)\nB. 3 separate builds\nC. Single-tier; defer enterprise",
        "decision": "5-tier abstraction · solo skips auth · enterprise picks OIDC · WeChat Work for cn region",
    },
    # PM (3)
    {
        "id_slug": "v1-1-scope-team-brain",
        "category": "product",
        "owner": "carol",
        "participants": ["alice", "bob"],
        "title": "v1.1 scope · Team Brain layer (W1-W8)",
        "outcome": "8-week file-first build · ship 2026-05-09 · 0 token leaderboards",
        "anchors": ["P", "XL", "L"],
        "roi_estimated": "Productizes vault into team-brain · clear from personal-OS",
        "planned_days": 56, "elapsed_days": 1,
        "days_ago": 40,
        "problem": "v1.0 is a personal vault + share station. Customers want team-brain (decisions + eval + cost-per-outcome). Need 90 days from sketch to ship.",
        "options": "A. 8-week W1-W8 plan with strict file-first invariants\nB. 12-week plan including LLM-distilled wiki\nC. Drop wiki, just ship eval",
        "decision": "A · file-first only · LLM features deferred to v1.2 · GDPR/PIPL enforced in code",
    },
    {
        "id_slug": "interview-priorities-pre-launch",
        "category": "product",
        "owner": "carol",
        "participants": ["dan", "erin"],
        "title": "Pre-launch customer interviews · 8 prospects",
        "outcome": "Talk to 5 enterprise + 3 indie · 8x60min · 5-13 cutoff",
        "anchors": ["P", "M"],
        "roi_estimated": "Validate 3 hypotheses before HN launch",
        "planned_days": 7, "elapsed_days": 6,
        "days_ago": 35,
        "problem": "Cannot ship Show HN without validating: (a) cost-per-outcome resonates with CIOs, (b) markdown vault is felt as feature not bug, (c) anti-tokenmaxxing not seen as anti-AI.",
        "options": "A. 8 interviews split 5 ent / 3 indie · short window\nB. 15 interviews · 3 weeks (delays HN)\nC. Skip · trust the design",
        "decision": "A · 8 interviews in 1 week · 3 hypothesis-validation questions · synthesis on 5-12",
    },
    {
        "id_slug": "cut-feature-realtime-collab",
        "category": "product",
        "owner": "carol",
        "participants": ["alice"],
        "title": "Cut realtime collab from v1.1 · defer to v1.3",
        "outcome": "Realtime collab cut · async collab via git workflow",
        "anchors": ["维护性", "M"],
        "roi_estimated": "Saves 3 weeks · git is good enough for file-first vault",
        "planned_days": 1, "elapsed_days": 1,
        "days_ago": 30,
        "problem": "v1.1 design proposal had realtime co-editing of decision files (Yjs/CRDT). 3-week investment. Conflicts with markdown-as-source-of-truth philosophy.",
        "options": "A. Cut · async via git\nB. Yjs CRDT · 3 weeks\nC. Manual lock file",
        "decision": "A · markdown vault is git-friendly · async collab is the feature, not a workaround",
    },
    # Sales (2)
    {
        "id_slug": "customer-tier-abc-segmentation",
        "category": "growth",
        "owner": "dan",
        "participants": ["erin"],
        "title": "Customer tier · A/B/C segmentation for support",
        "outcome": "A=enterprise (white-glove), B=team (slack), C=indie (community)",
        "anchors": ["P", "L"],
        "roi_estimated": "Support cost down 40% · A tier upsell up 25%",
        "planned_days": 3, "elapsed_days": 3,
        "days_ago": 25,
        "problem": "Mixed support queue · indie devs and enterprise both wait same SLA · neither happy.",
        "options": "A. 3-tier (A/B/C) with different SLAs\nB. 2-tier (paid / free)\nC. Single queue, fast everyone",
        "decision": "A · explicit tiers with different channels · sets expectation upfront",
    },
    {
        "id_slug": "win-back-churned-customers",
        "category": "growth",
        "owner": "dan",
        "participants": ["carol"],
        "title": "Win-back flow for churned customers",
        "outcome": "30/60/90-day check-in cadence · personalized · 12% recovery rate",
        "anchors": ["P"],
        "roi_estimated": "Recover 12% of churned MRR",
        "planned_days": 5, "elapsed_days": 7,
        "days_ago": 20,
        "problem": "5% monthly churn · zero win-back outreach. Lost ~$8K MRR in Q1.",
        "options": "A. 30/60/90 check-in cadence\nB. Single 14-day check-in\nC. No outreach (respect their decision)",
        "decision": "A · 3 touchpoints with personalized hooks · automated via crm",
    },
    # Ops (2)
    {
        "id_slug": "deploy-stack-choice",
        "category": "ops",
        "owner": "erin",
        "participants": ["alice"],
        "title": "Deploy stack · Docker Compose vs k8s",
        "outcome": "Compose for v1.x · k8s only when >100 tenants",
        "anchors": ["维护性", "M"],
        "roi_estimated": "Avoid premature complexity · save 2 days/week ops time",
        "planned_days": 2, "elapsed_days": 2,
        "days_ago": 18,
        "problem": "Some users asking k8s manifests. Single-binary + Compose is current. k8s adds 6 components for an app that fits on one host.",
        "options": "A. Compose only · k8s deferred\nB. Both · double maintenance\nC. k8s only · scale-up but ops burden",
        "decision": "A · Compose covers 95% of deployments · revisit when single host saturates",
    },
    {
        "id_slug": "oncall-rotation-q2",
        "category": "ops",
        "owner": "erin",
        "participants": ["alice", "bob", "dan"],
        "title": "On-call rotation · weekly · 4 person",
        "outcome": "Weekly rotation · primary + secondary · alice/bob/dan/erin",
        "anchors": ["维护性"],
        "roi_estimated": "No single point of failure · no burnout",
        "planned_days": 1, "elapsed_days": 1,
        "days_ago": 12,
        "problem": "alice was on-call 24/7 for 8 weeks · burnout risk · bus factor 1.",
        "options": "A. Weekly rotation, 4-person\nB. Bi-weekly, 2-person\nC. Status quo (alice solo)",
        "decision": "A · weekly · 4-person · primary + secondary · clear handoff doc",
    },
    # Mixed (2)
    {
        "id_slug": "cross-bu-workflow-design",
        "category": "ops",
        "owner": "alice",
        "participants": ["carol", "dan"],
        "title": "Cross-BU workflow · Eng ↔ Sales handoff",
        "outcome": "Decision-Skill bridge · Sales references Eng SKILL.md · async ack",
        "anchors": ["P", "L"],
        "roi_estimated": "Eng-Sales conflict drops · 1 fewer all-hands per quarter",
        "planned_days": 3, "elapsed_days": 4,
        "days_ago": 8,
        "problem": "Eng + Sales tension on commitments. Eng says scope creep; Sales says Eng won't commit. No shared context layer.",
        "options": "A. SKILL.md bridge · Sales reads → ack → Eng knows\nB. Joint standup (calendar overhead)\nC. Status quo",
        "decision": "A · file-first bridge · async, no meetings · everyone reads same source",
    },
    {
        "id_slug": "q2-team-retro-process",
        "category": "ops",
        "owner": "carol",
        "participants": ["alice", "bob", "dan", "erin"],
        "title": "Q2 team retro process · 30-day cycle",
        "outcome": "Monthly retro · 5 ROTI scores · Decision/.calibration as input",
        "anchors": ["维护性", "M"],
        "roi_estimated": "Retro insights captured in vault · not lost in slack",
        "planned_days": 1, "elapsed_days": 1,
        "days_ago": 5,
        "problem": "Quarterly retros too slow to course-correct · slack-based notes lost.",
        "options": "A. Monthly retro · vault-captured · ROTI 1-5\nB. Bi-weekly · too frequent\nC. Quarterly · status quo",
        "decision": "A · 30-day cycle · structured · ROTI in frontmatter · feeds D7 learning dim",
    },
]


def write_decision(vault: Path, d: dict, today: date) -> Path:
    closed = today - timedelta(days=d["days_ago"])
    opened = closed - timedelta(days=d["elapsed_days"])

    # 50% of decisions get roi_actual to make D6 USD path testable
    roi_actual = None
    if d["days_ago"] >= 90 and "growth" in d["category"]:
        roi_actual = round(random.uniform(2000, 12000), 2)

    fm_lines = [
        "---",
        f"id: {d['id_slug']}",
        f"opened: {opened.isoformat()}T09:00:00Z",
        f"closed: {closed.isoformat()}T17:00:00Z",
        "status: closed",
        f"owner: {d['owner']}",
        f"participants: [{', '.join(d['participants'])}]",
        "supersedes: null",
        "superseded_by: null",
        f'outcome: "{d["outcome"]}"',
        f"value_anchors:",
        *[f"  - {a}" for a in d["anchors"]],
        f'roi_estimated: "{d["roi_estimated"]}"',
        f"roi_actual: {roi_actual if roi_actual is not None else 'null'}",
        f"planned_duration_days: {d['planned_days']}",
        f"elapsed_days: {d['elapsed_days']}",
        f"category: {d['category']}",
        "---",
    ]
    body = [
        f"# Decision: {d['title']}",
        "",
        f"## ① Problem definition (human · {d['owner']})",
        "",
        d["problem"],
        "",
        "## ② Data needs (AI)",
        "",
        f"Reviewed: similar decisions in vault · industry benchmarks · team capacity ·",
        f"input from {', '.join(d['participants'])}.",
        "",
        "## ③ Models considered (AI)",
        "",
        "Trade-off framing across 3 dimensions: cost · ship-speed · maintenance.",
        "",
        "## ④ Options (AI)",
        "",
        d["options"],
        "",
        f"## ⑤ Decision (human · {d['owner']} · leader)",
        "",
        d["decision"],
        "",
        "Rationale: aligns with v1.1 file-first philosophy · revisit at next quarterly retro.",
        "",
        "## ⑥ Reflection (human · leader)",
        "",
        "Key insight: simpler than initially feared · the boring choice usually wins.",
        "",
        "## ⑦ Execution log (AI · append-only)",
        "",
        f"- {opened.isoformat()} · kicked off",
        f"- {(opened + timedelta(days=max(1, d['elapsed_days']//2))).isoformat()} · midpoint check",
        f"- {closed.isoformat()} · closed · outcome captured",
        "",
        "## ⑧ Feedback (AI · 90 day backfill · pending)",
        "",
        "(empty until 90-day distill)",
        "",
    ]

    fp = vault / "Decisions" / f"{d['id_slug']}.md"
    fp.write_text("\n".join(fm_lines + [""] + body), encoding="utf-8")
    return fp


# ── 30 trace lines across 5 actors × 3 months ───────────────────────────────


SKILL_NAMES = [
    "meeting-summarize", "hike-wiki-update", "hike-wiki-query",
    "dev-decision-workflow", "code-review", "estimate-cost",
    "draft-customer-email", "deploy-checklist",
]


def write_traces(vault: Path, today: date) -> int:
    trace_dir = vault / "Trace"
    trace_dir.mkdir(parents=True, exist_ok=True)

    # Group by date so each date file is one append run
    rng = random.Random(20260509)
    n = 0
    by_date: dict[str, list[dict]] = {}
    decision_ids = [d["id_slug"] for d in DECISIONS]

    for _ in range(30):
        days_ago = rng.randint(5, 90)
        when = datetime.combine(
            today - timedelta(days=days_ago),
            datetime.min.time(),
            tzinfo=timezone.utc,
        ) + timedelta(hours=rng.randint(8, 18), minutes=rng.randint(0, 59))
        actor = rng.choice(ACTORS)
        skill = rng.choice(SKILL_NAMES)
        decision_id = rng.choice(decision_ids) if rng.random() > 0.3 else None
        cost = round(rng.uniform(0.002, 0.08), 4)
        # ~60% have output_value_usd to make D2 ROI work
        value = round(rng.uniform(0.5, 8.0), 3) if rng.random() > 0.4 else None
        line = {
            "ts": when.isoformat().replace("+00:00", "Z"),
            "actor": actor,
            "skill": skill,
            "decision_id": decision_id,
            "model": rng.choice(["claude-sonnet-4-6", "claude-haiku-4-5-20251001",
                                  "gpt-4o", "deepseek-v3"]),
            "tokens_in": rng.randint(80, 1200),
            "tokens_out": rng.randint(40, 600),
            "cost_usd": cost,
            "output_value_usd": value,
            "value_attribution": "manual" if value else None,
            "elapsed_ms": rng.randint(200, 8000),
            "tenant": "default",
        }
        date_key = when.date().isoformat()
        by_date.setdefault(date_key, []).append(line)
        n += 1

    for date_key, lines in by_date.items():
        fp = trace_dir / f"{date_key}.jsonl"
        with fp.open("a", encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return n


# ── main ────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default="vault.example",
                        help="Vault directory (default: ./vault.example)")
    args = parser.parse_args()

    vault = Path(args.vault).resolve()
    if not vault.exists():
        print(f"ERROR: vault not found: {vault}", file=sys.stderr)
        return 1

    (vault / "Decisions").mkdir(parents=True, exist_ok=True)
    today = date(2026, 5, 9)

    print(f"Seeding demo vault at {vault}")
    print("─" * 60)
    for d in DECISIONS:
        fp = write_decision(vault, d, today)
        print(f"  ✓ {fp.relative_to(vault)} ({d['category']}/{d['owner']})")

    print("─" * 60)
    n_traces = write_traces(vault, today)
    print(f"  ✓ Trace/ · {n_traces} lines across 5 actors × 3 months")

    print("─" * 60)
    print(f"Done. {len(DECISIONS)} decisions + {n_traces} traces seeded.")
    print("Next: ./ome365 wiki update  (distill into Knowledge/L2-distilled/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
