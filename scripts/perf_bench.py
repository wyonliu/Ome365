#!/usr/bin/env python3
"""
scripts/perf_bench.py · v1.1.1 P2 #14
[decision: 2026-05-09-p2-async-trace-and-audit]

Benchmark eval / dashboard / metrics under realistic load:
  · 1000 decisions / 5000 traces / 50 members
  · 4 cockpit endpoints + /metrics
  · prints latency p50/p95/p99 + cache speedup

Usage:
    python3 scripts/perf_bench.py [--decisions 1000] [--traces 5000] [--members 50]
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_eval import (  # noqa: E402
    _compute_team_distribution,
    eval_member,
    finops_summary,
    grep_decisions_all,
    grep_skills_all,
    grep_trace_all,
)
from ome365_metrics import render as render_metrics  # noqa: E402


def _seed_large_vault(vault: Path, n_decisions: int, n_traces: int, n_members: int) -> None:
    """Build a realistic vault with N members each owning ~ N/N_M decisions."""
    decisions_dir = vault / "Decisions"
    trace_dir = vault / "Trace"
    cfg_dir = vault / ".ome365"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)
    cfg_dir.mkdir(parents=True, exist_ok=True)

    (cfg_dir / "eval-config.yml").write_text(
        "preset: 'engineer'\nregion: 'global'\nsample_size_min: 5\n"
        "weights:\n  delivery: 0.20\n  cost_per_outcome: 0.15\n  quality: 0.20\n"
        "  judgment: 0.15\n  ecosystem: 0.10\n  revenue_per_workflow: 0.10\n  learning: 0.10\n"
        "value_anchor_weights:\n  P: 2.0\n  XL: 3.0\n  L: 2.0\n  M: 1.0\n"
        "  '维护性': -0.5\n  Revert: -2.0\n",
        "utf-8",
    )

    members = [f"m{i:03d}" for i in range(n_members)]
    rng = random.Random(20260509)
    today = date(2026, 5, 9)

    # Decisions
    for i in range(n_decisions):
        days_ago = rng.randint(5, 300)
        owner = members[i % n_members]
        anchors = rng.sample(["P", "L", "XL", "M", "维护性"], k=rng.randint(1, 3))
        closed = today - timedelta(days=days_ago)
        opened = closed - timedelta(days=rng.randint(1, 14))
        roi = round(rng.uniform(500, 8000), 2) if rng.random() > 0.5 else None
        anchor_lines = "\n".join(f"  - {a}" for a in anchors)

        (decisions_dir / f"d{i:05d}.md").write_text(
            f"---\nid: d{i:05d}\n"
            f"opened: {opened.isoformat()}T09:00:00Z\n"
            f"closed: {closed.isoformat()}T17:00:00Z\n"
            f"status: closed\nowner: {owner}\n"
            f"outcome: '"f"shipped {i}"f"'\n"
            f"value_anchors:\n{anchor_lines}\n"
            f"roi_actual: {roi if roi else 'null'}\n"
            f"category: bench\n---\n# d{i}\n",
            "utf-8",
        )

    # Traces grouped by date
    by_date: dict[str, list[dict]] = {}
    for i in range(n_traces):
        days_ago = rng.randint(5, 90)
        when = datetime.combine(today - timedelta(days=days_ago),
                                datetime.min.time(), tzinfo=timezone.utc) + timedelta(
            hours=rng.randint(8, 18), minutes=rng.randint(0, 59))
        actor = members[i % n_members]
        line = {
            "ts": when.isoformat().replace("+00:00", "Z"),
            "actor": actor,
            "skill": rng.choice(["meeting-summarize", "code-review", "estimate-cost"]),
            "decision_id": f"d{rng.randint(0, n_decisions - 1):05d}",
            "model": rng.choice(["claude-haiku-4-5-20251001", "gpt-4o"]),
            "tokens_in": rng.randint(80, 1200),
            "tokens_out": rng.randint(40, 600),
            "cost_usd": round(rng.uniform(0.001, 0.06), 4),
            "output_value_usd": round(rng.uniform(0.5, 8.0), 3) if rng.random() > 0.4 else None,
            "value_attribution": "manual",
            "elapsed_ms": rng.randint(200, 8000),
            "tenant": "default",
        }
        date_key = when.date().isoformat()
        by_date.setdefault(date_key, []).append(line)

    for date_key, lines in by_date.items():
        with (trace_dir / f"{date_key}.jsonl").open("w") as f:
            for line in lines:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")


def time_it(fn, *args, n_iter: int = 5, **kwargs) -> dict:
    samples = []
    for _ in range(n_iter):
        t0 = time.perf_counter()
        fn(*args, **kwargs)
        samples.append((time.perf_counter() - t0) * 1000)
    return {
        "p50_ms": round(statistics.median(samples), 2),
        "p95_ms": round(sorted(samples)[int(0.95 * len(samples))], 2) if len(samples) > 1 else round(samples[0], 2),
        "min_ms": round(min(samples), 2),
        "max_ms": round(max(samples), 2),
        "n_iter": n_iter,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", type=int, default=1000)
    parser.add_argument("--traces", type=int, default=5000)
    parser.add_argument("--members", type=int, default=50)
    args = parser.parse_args()

    print("─" * 70)
    print(f"  Ome365 perf benchmark · {args.decisions} decisions · {args.traces} traces · {args.members} members")
    print("─" * 70)

    with tempfile.TemporaryDirectory(prefix="ome_bench_") as td:
        vault = Path(td)
        print(f"  Seeding vault at {vault} ...")
        t0 = time.perf_counter()
        _seed_large_vault(vault, args.decisions, args.traces, args.members)
        seed_s = time.perf_counter() - t0
        print(f"  Seed: {seed_s:.2f}s · {args.decisions / seed_s:.0f} decisions/sec")

        # 1. grep_decisions_all
        r = time_it(grep_decisions_all, vault, n_iter=3)
        print(f"\n  [1] grep_decisions_all · p50 {r['p50_ms']:>7.2f}ms · p95 {r['p95_ms']:>7.2f}ms")

        # 2. grep_trace_all
        r = time_it(grep_trace_all, vault, n_iter=3)
        print(f"  [2] grep_trace_all     · p50 {r['p50_ms']:>7.2f}ms · p95 {r['p95_ms']:>7.2f}ms")

        # 3. eval_member (single)
        members = [f"m{i:03d}" for i in range(args.members)]
        r = time_it(eval_member, vault, members[0], n_iter=3, window_days=365)
        print(f"  [3] eval_member single · p50 {r['p50_ms']:>7.2f}ms · p95 {r['p95_ms']:>7.2f}ms")

        # 4. _compute_team_distribution (full team)
        r = time_it(_compute_team_distribution, members, date.today() - timedelta(days=365), vault, n_iter=3, sample_min=5)
        print(f"  [4] team_distribution  · p50 {r['p50_ms']:>7.2f}ms · p95 {r['p95_ms']:>7.2f}ms")

        # 5. finops_summary
        r = time_it(finops_summary, vault, n_iter=3, scope="cost_per_resolved_decision", since_days=365)
        print(f"  [5] finops_summary     · p50 {r['p50_ms']:>7.2f}ms · p95 {r['p95_ms']:>7.2f}ms")

        # 6. /metrics render
        r = time_it(render_metrics, vault, n_iter=3)
        print(f"  [6] /metrics render    · p50 {r['p50_ms']:>7.2f}ms · p95 {r['p95_ms']:>7.2f}ms")

        # 7. cache speedup: 1 eval_member vs 1 _compute_team_distribution
        # If team has 50 members and we want all percentiles, naive = 50 × eval_member,
        # cached = 1 × team_distribution.
        single_p50 = time_it(eval_member, vault, members[0], n_iter=3)["p50_ms"]
        team_p50 = time_it(_compute_team_distribution, members, date.today() - timedelta(days=365), vault, n_iter=2, sample_min=5)["p50_ms"]
        naive = single_p50 * args.members
        speedup = naive / team_p50 if team_p50 > 0 else float("inf")
        print(f"\n  [7] N+1 cache speedup:")
        print(f"      naive (50×eval_member): {naive/1000:>7.2f}s")
        print(f"      cached (1×team_dist):   {team_p50/1000:>7.2f}s")
        print(f"      speedup: {speedup:.1f}×")

    print("─" * 70)
    print("  All benchmarks complete.")
    print("─" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
