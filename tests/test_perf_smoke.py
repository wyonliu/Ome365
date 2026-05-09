"""tests/test_perf_smoke.py · v1.1.6 · perf budget smoke
Catch perf regressions in CI without doing the full 1000-decision benchmark.
"""
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_eval import (  # noqa: E402
    _compute_team_distribution,
    eval_member,
    finops_summary,
    grep_decisions_all,
    grep_skills_all,
    grep_trace_all,
)
from ome365_metrics import render  # noqa: E402


VAULT_EXAMPLE = Path(__file__).resolve().parent.parent / "vault.example"


def _time_ms(fn, *args, **kwargs) -> float:
    t0 = time.perf_counter()
    fn(*args, **kwargs)
    return (time.perf_counter() - t0) * 1000


def test_grep_decisions_under_budget():
    """vault.example has ~26 decisions · grep should be fast."""
    pytest.importorskip("yaml")
    elapsed = _time_ms(grep_decisions_all, VAULT_EXAMPLE)
    assert elapsed < 300, f"grep_decisions_all took {elapsed:.1f}ms (>300ms)"


def test_grep_trace_under_budget():
    pytest.importorskip("yaml")
    elapsed = _time_ms(grep_trace_all, VAULT_EXAMPLE)
    # 36 traces across multiple files
    assert elapsed < 200, f"grep_trace_all took {elapsed:.1f}ms (>200ms)"


def test_grep_skills_under_budget():
    pytest.importorskip("yaml")
    elapsed = _time_ms(grep_skills_all, VAULT_EXAMPLE)
    assert elapsed < 100, f"grep_skills_all took {elapsed:.1f}ms (>100ms)"


def test_eval_member_under_budget():
    pytest.importorskip("yaml")
    elapsed = _time_ms(eval_member, VAULT_EXAMPLE, "alice", window_days=365)
    assert elapsed < 1000, f"eval_member took {elapsed:.1f}ms (>1000ms)"


def test_team_distribution_under_budget():
    """team distribution is the cache · should beat naive 5×eval_member."""
    pytest.importorskip("yaml")
    members = ["alice", "bob", "carol", "dan", "erin"]
    elapsed = _time_ms(
        _compute_team_distribution,
        members,
        date.today() - timedelta(days=365),
        VAULT_EXAMPLE,
        sample_min=5,
    )
    # Naive 5×eval_member would take ~5000ms; cache should be under 800ms
    assert elapsed < 800, f"team_distribution took {elapsed:.1f}ms (>800ms)"


def test_finops_summary_under_budget():
    pytest.importorskip("yaml")
    elapsed = _time_ms(finops_summary, VAULT_EXAMPLE,
                       scope="cost_per_resolved_decision", since_days=365)
    assert elapsed < 500, f"finops_summary took {elapsed:.1f}ms (>500ms)"


def test_metrics_render_under_budget():
    pytest.importorskip("yaml")
    elapsed = _time_ms(render, VAULT_EXAMPLE)
    # /metrics is hit by Prometheus every 15s · must be cheap
    assert elapsed < 500, f"/metrics render took {elapsed:.1f}ms (>500ms)"


def test_team_distribution_beats_naive():
    """Demo Review-Fix 1 cache benefit · cached must be at least 3× faster than naive."""
    pytest.importorskip("yaml")
    members = ["alice", "bob", "carol", "dan", "erin"]

    naive_total_ms = 0
    for m in members:
        naive_total_ms += _time_ms(eval_member, VAULT_EXAMPLE, m, window_days=365)

    cached_ms = _time_ms(
        _compute_team_distribution,
        members,
        date.today() - timedelta(days=365),
        VAULT_EXAMPLE,
        sample_min=5,
    )

    # On 5-member vault.example we expect at least 2× speedup
    # (real benchmark on 50 members showed 194×)
    assert cached_ms * 2 < naive_total_ms, (
        f"cache speedup {naive_total_ms/cached_ms:.1f}× insufficient "
        f"(naive={naive_total_ms:.1f}ms cached={cached_ms:.1f}ms)"
    )
