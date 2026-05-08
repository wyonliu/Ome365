"""tests/test_ome365_cost.py · ome365.cost v0.1 stub contract tests"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_cost import (  # noqa: E402
    POLICY_DEFINITIONS,
    DEFAULT_THRESHOLDS,
    set_budget,
    record_usage,
    compute_pct,
    check_alerts,
    is_request_allowed,
    reset_period,
    _BUDGETS,
    _USAGE,
)


@pytest.fixture(autouse=True)
def _clear_state():
    """Each test starts with empty in-memory stores."""
    _BUDGETS.clear()
    _USAGE.clear()
    yield
    _BUDGETS.clear()
    _USAGE.clear()


# ── Policy enum ──────────────────────────────────────────────────────────────

def test_three_policies_defined():
    assert set(POLICY_DEFINITIONS.keys()) == {"warn", "throttle", "block"}


def test_default_thresholds_50_80_100():
    assert DEFAULT_THRESHOLDS == [50, 80, 100]


# ── Budget setting ───────────────────────────────────────────────────────────

def test_set_budget_basic():
    b = set_budget("acme", 100.0, "warn")
    assert b.monthly_usd == 100.0
    assert b.policy == "warn"
    assert b.fired_thresholds == []


def test_set_budget_rejects_negative():
    with pytest.raises(ValueError):
        set_budget("acme", -1, "warn")


def test_set_budget_rejects_unknown_policy():
    with pytest.raises(ValueError):
        set_budget("acme", 100, "ban")  # type: ignore


# ── Usage recording ──────────────────────────────────────────────────────────

def test_record_usage_increments():
    u1 = record_usage("acme", tokens_in=100, tokens_out=50, dollars=0.01)
    u2 = record_usage("acme", tokens_in=200, tokens_out=100, dollars=0.02)
    assert u2.tokens_in == 300
    assert u2.tokens_out == 150
    assert abs(u2.dollars_spent - 0.03) < 1e-9
    assert u2.requests == 2


# ── Pct computation ──────────────────────────────────────────────────────────

def test_pct_zero_when_no_budget():
    record_usage("acme", dollars=10)
    assert compute_pct("acme") == 0.0


def test_pct_50_percent():
    set_budget("acme", 100.0, "warn")
    record_usage("acme", dollars=50)
    assert compute_pct("acme") == 50.0


def test_pct_can_exceed_100():
    set_budget("acme", 100.0, "warn")
    record_usage("acme", dollars=150)
    assert compute_pct("acme") == 150.0


# ── Alert thresholds ─────────────────────────────────────────────────────────

def test_alerts_fire_at_50_80_100():
    set_budget("acme", 100.0, "warn")
    record_usage("acme", dollars=55)
    fired = check_alerts("acme")
    assert {a["threshold_pct"] for a in fired} == {50}

    record_usage("acme", dollars=30)  # cumulative 85
    fired = check_alerts("acme")
    assert {a["threshold_pct"] for a in fired} == {80}

    record_usage("acme", dollars=20)  # cumulative 105
    fired = check_alerts("acme")
    assert {a["threshold_pct"] for a in fired} == {100}


def test_alerts_idempotent_within_period():
    """An already-fired threshold should not re-fire."""
    set_budget("acme", 100.0, "warn")
    record_usage("acme", dollars=55)
    check_alerts("acme")
    record_usage("acme", dollars=1)  # still over 50%
    fired = check_alerts("acme")
    assert fired == []  # already fired


# ── Enforcement policy ───────────────────────────────────────────────────────

def test_warn_policy_always_allows():
    set_budget("acme", 100.0, "warn")
    record_usage("acme", dollars=200)
    ok, reason = is_request_allowed("acme")
    assert ok
    assert "warn" in reason


def test_throttle_policy_allows_with_hint():
    set_budget("acme", 100.0, "throttle")
    record_usage("acme", dollars=200)
    ok, reason = is_request_allowed("acme")
    assert ok
    assert "throttle" in reason


def test_block_policy_rejects_over_budget():
    set_budget("acme", 100.0, "block")
    record_usage("acme", dollars=200)
    ok, reason = is_request_allowed("acme")
    assert not ok
    assert "block" in reason


def test_block_policy_allows_under_budget():
    set_budget("acme", 100.0, "block")
    record_usage("acme", dollars=50)
    ok, _ = is_request_allowed("acme")
    assert ok


# ── Reset period ─────────────────────────────────────────────────────────────

def test_reset_clears_usage_and_alerts():
    set_budget("acme", 100.0, "warn")
    record_usage("acme", dollars=110)
    check_alerts("acme")
    reset_period("acme")
    assert _USAGE["acme"].dollars_spent == 0.0
    assert _BUDGETS["acme"].fired_thresholds == []
    assert _BUDGETS["acme"].monthly_usd == 100.0  # budget preserved


# ── Multi-tenant isolation ───────────────────────────────────────────────────

def test_tenants_isolated():
    set_budget("acme", 100.0, "warn")
    set_budget("globex", 200.0, "block")
    record_usage("acme", dollars=50)
    record_usage("globex", dollars=300)

    ok_acme, _ = is_request_allowed("acme")
    ok_globex, _ = is_request_allowed("globex")
    assert ok_acme  # under budget
    assert not ok_globex  # over budget + block
