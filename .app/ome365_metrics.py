"""
ome365.metrics · v1.1.1 P2 #12 · Prometheus /metrics endpoint
[decision: 2026-05-09-p1-backup-and-metrics]

stdlib-only Prometheus text format exporter. 12 metric families derived from vault.

Mounted at GET /metrics (text/plain; charset=utf-8; version=0.0.4).
"""
from __future__ import annotations

import os
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


def _vault_root(vault: Optional[Path] = None) -> Path:
    if vault:
        return Path(vault).resolve()
    return Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()


# Cumulative counters that survive across requests (best-effort process-local)
_request_counters = {
    "decision_list": 0,
    "decision_get": 0,
    "decision_create": 0,
    "decision_close": 0,
    "eval_member": 0,
    "eval_dashboard": 0,
    "eval_skills": 0,
    "trace_log": 0,
    "wiki_update": 0,
    "wiki_query": 0,
    "backup_create": 0,
    "backup_restore": 0,
}


def inc(key: str, n: int = 1) -> None:
    """Bump a counter from any code path."""
    if key in _request_counters:
        _request_counters[key] += n


def render(vault: Optional[Path] = None) -> str:
    """Return Prometheus text format for /metrics."""
    try:
        from ome365_eval import grep_decisions_all, grep_skills_all, grep_trace_all
    except ImportError:
        return "# ome365_eval not importable\n"

    v = _vault_root(vault)
    decisions = grep_decisions_all(v)
    traces = grep_trace_all(v)
    skills = grep_skills_all(v)

    lines: list[str] = []
    ts = int(time.time() * 1000)

    def metric(name: str, type_: str, help_: str, samples: list[tuple[str, float]]) -> None:
        lines.append(f"# HELP ome365_{name} {help_}")
        lines.append(f"# TYPE ome365_{name} {type_}")
        for label_str, value in samples:
            label_part = "{" + label_str + "}" if label_str else ""
            lines.append(f"ome365_{name}{label_part} {value} {ts}")

    # 1. decisions_total (counter)
    metric("decisions_total", "gauge", "Total decisions in vault",
           [("", float(len(decisions)))])

    # 2. decisions_by_status
    by_status: dict[str, int] = defaultdict(int)
    for d in decisions:
        by_status[d.status] += 1
    metric("decisions_by_status", "gauge", "Decisions grouped by status",
           [(f'status="{s}"', float(n)) for s, n in by_status.items()])

    # 3. decisions_by_owner_count
    by_owner: dict[str, int] = defaultdict(int)
    for d in decisions:
        by_owner[d.owner or "(none)"] += 1
    metric("decisions_by_owner", "gauge", "Decisions count per owner",
           [(f'owner="{o}"', float(n)) for o, n in sorted(by_owner.items())])

    # 4. traces_total
    metric("traces_total", "gauge", "Total trace events", [("", float(len(traces)))])

    # 5. trace_cost_usd_total (sum)
    total_cost = sum(t.cost_usd for t in traces)
    metric("trace_cost_usd_total", "gauge", "Sum of trace cost_usd",
           [("", float(total_cost))])

    # 6. trace_value_usd_total
    total_value = sum((t.output_value_usd or 0) for t in traces)
    metric("trace_value_usd_total", "gauge", "Sum of trace output_value_usd",
           [("", float(total_value))])

    # 7. trace_by_actor (cost per actor)
    cost_by_actor: dict[str, float] = defaultdict(float)
    n_by_actor: dict[str, int] = defaultdict(int)
    for t in traces:
        cost_by_actor[t.actor] += t.cost_usd
        n_by_actor[t.actor] += 1
    metric("trace_cost_usd_by_actor", "gauge", "Cumulative cost per actor",
           [(f'actor="{a}"', float(v)) for a, v in sorted(cost_by_actor.items())])
    metric("trace_count_by_actor", "gauge", "Trace count per actor",
           [(f'actor="{a}"', float(n)) for a, n in sorted(n_by_actor.items())])

    # 8. skills_total
    metric("skills_total", "gauge", "Total SKILL.md files", [("", float(len(skills)))])

    # 9. skills_by_author
    by_author: dict[str, int] = defaultdict(int)
    for s in skills:
        by_author[s.author or "(none)"] += 1
    metric("skills_by_author", "gauge", "Skills count per author",
           [(f'author="{a}"', float(n)) for a, n in sorted(by_author.items())])

    # 10. http_requests_total (per-endpoint counter)
    metric("http_requests_total", "counter", "Total HTTP requests by endpoint",
           [(f'endpoint="{k}"', float(n)) for k, n in sorted(_request_counters.items())])

    # 11. uptime_seconds
    pid_start = _PROCESS_START
    metric("uptime_seconds", "gauge", "Process uptime in seconds",
           [("", float(time.time() - pid_start))])

    # 12. recent_traces_24h
    recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    n_recent = sum(1 for t in traces if t.ts >= recent_cutoff)
    metric("traces_recent_24h", "gauge", "Traces in last 24 hours",
           [("", float(n_recent))])

    # Trailing newline required for Prom text format
    return "\n".join(lines) + "\n"


_PROCESS_START = time.time()


def cli_main(argv: list[str]) -> int:
    """`./ome365 metrics` · dump Prometheus text without booting server.

    Useful for cron-driven scrapes, debugging, and air-gapped environments.
    """
    if argv and argv[0] in ("-h", "--help", "help"):
        print(
            "usage:\n"
            "  ome365 metrics             # dump Prometheus text from $OME365_VAULT\n"
            "  ome365 metrics --vault DIR # dump from specific vault\n",
            flush=True,
        )
        return 0
    vault = None
    if argv and argv[0] == "--vault" and len(argv) >= 2:
        vault = Path(argv[1])
    print(render(vault=vault), end="", flush=True)
    return 0


__all__ = ["render", "inc", "cli_main"]
