"""tests/test_ome365_eval.py · v1.1 W1 first iteration · ome365_eval contract tests"""
import json
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_eval import (  # noqa: E402
    EvalDisabledForRegion,
    EvalOptedOut,
    PIPLNotifyRequired,
    Score,
    D1_delivery,
    D2_cost_per_outcome,
    D5_ecosystem,
    D7_learning,
    eval_member,
    finops_summary,
    grep_decisions_all,
    grep_skills_all,
    grep_trace_all,
    load_eval_config,
)


VAULT_EXAMPLE = Path(__file__).resolve().parent.parent / "vault.example"


# ── Vault scanners (against checked-in vault.example) ────────────────────────


def test_grep_decisions_finds_sample():
    decisions = grep_decisions_all(VAULT_EXAMPLE)
    assert len(decisions) >= 1
    d = next((x for x in decisions if x.id == "2026-05-08-pick-llm-backend"), None)
    assert d is not None
    assert d.owner == "alice"
    assert d.status == "closed"
    assert "P" in d.value_anchors
    assert "L" in d.value_anchors


def test_grep_trace_finds_jsonl():
    traces = grep_trace_all(VAULT_EXAMPLE)
    assert len(traces) >= 6  # vault.example/Trace/2026-05-08.jsonl has 6 lines
    actors = {t.actor for t in traces}
    assert "alice" in actors
    assert "bob" in actors
    assert "carol" in actors


def test_grep_skills_finds_three():
    skills = grep_skills_all(VAULT_EXAMPLE)
    names = {s.name for s in skills}
    assert "meeting-summarize" in names
    assert "hike-wiki-update" in names
    assert "hike-wiki-query" in names


# ── Region-aware enforcement (Fix 5) ─────────────────────────────────────────


def _tmp_vault(region: str = "global", **overrides) -> Path:
    """Create a tmp vault with .ome365/eval-config.yml for region tests."""
    d = Path(tempfile.mkdtemp(prefix="omeval_"))
    cfg_dir = d / ".ome365"
    cfg_dir.mkdir(parents=True)
    cfg = {
        "preset": "engineer",
        "weights": {
            "delivery": 0.15, "cost_per_outcome": 0.15, "quality": 0.15,
            "judgment": 0.10, "ecosystem": 0.20,
            "revenue_per_workflow": 0.15, "learning": 0.10,
        },
        "sample_size_min": 5,
        "region": region,
        "value_anchor_weights": {
            "P": 2.0, "XL": 3.0, "L": 2.0, "M": 1.0,
            "维护性": -0.5, "Revert": -2.0,
        },
    }
    cfg.update(overrides)
    (cfg_dir / "eval-config.yml").write_text(
        "\n".join(f"{k}: {v!r}" if not isinstance(v, dict) else f"{k}:\n  " +
                 "\n  ".join(f"{kk}: {vv!r}" for kk, vv in v.items())
                 for k, v in cfg.items())
    )
    return d


def test_eu_region_default_deny():
    """Fix 5 + edge case #3: EU region default 403."""
    pytest.importorskip("yaml")
    vault = _tmp_vault(region="eu")
    with pytest.raises(EvalDisabledForRegion):
        eval_member(vault, "alice")


def test_eu_region_explicit_enable():
    """Fix 5 + edge case #4: EU explicit enable bypasses default-deny."""
    pytest.importorskip("yaml")
    vault = _tmp_vault(region="eu", eval_enabled_eu=True)
    result = eval_member(vault, "alice")
    assert result["region"] == "eu"
    assert result["human_review_required"] is True
    assert "GDPR Art. 22" in result["warning"]


def test_cn_region_pipl_required():
    """Fix 5 + edge case #22: cn region first eval requires PIPL §13 ack."""
    pytest.importorskip("yaml")
    vault = _tmp_vault(region="cn")
    with pytest.raises(PIPLNotifyRequired):
        eval_member(vault, "alice")


def test_cn_region_pipl_acknowledged():
    """cn region · alice signed PIPL · proceeds normally with cn warning."""
    pytest.importorskip("yaml")
    vault = _tmp_vault(
        region="cn",
        pipl_notify_acknowledged_by={"alice": "2026-05-08"},
    )
    result = eval_member(vault, "alice")
    assert result["region"] == "cn"
    assert "个人信息保护法" in result["warning"]


def test_cn_opted_out_member():
    """Fix 5 + edge case #23: opted-out member always 403."""
    pytest.importorskip("yaml")
    vault = _tmp_vault(
        region="cn",
        pipl_notify_acknowledged_by={"alice": "2026-05-08"},
        opted_out_members=["alice"],
    )
    with pytest.raises(EvalOptedOut):
        eval_member(vault, "alice")


def test_global_region_default_open():
    """Fix 5 + edge case #24: global region default open with warning."""
    pytest.importorskip("yaml")
    vault = _tmp_vault(region="global")
    result = eval_member(vault, "alice")
    assert result["region"] == "global"
    assert result["human_review_required"] is True


# ── eval_member integration on vault.example ─────────────────────────────────


def test_eval_member_on_example_vault():
    pytest.importorskip("yaml")
    result = eval_member(VAULT_EXAMPLE, "alice", window_days=365)
    assert result["member_id"] == "alice"
    assert result["human_review_required"] is True
    assert "anti_tokenmaxxing_note" in result
    assert "preset" in result
    assert "dimensions" in result
    # All 7 dims present
    assert set(result["dimensions"].keys()) == {
        "D1_delivery", "D2_cost_per_outcome", "D3_quality",
        "D4_judgment", "D5_ecosystem", "D6_revenue_per_workflow", "D7_learning",
    }


def test_eval_warning_anti_tokenmaxxing_present():
    """Anti-Tokenmaxxing stance must appear in every response."""
    pytest.importorskip("yaml")
    result = eval_member(VAULT_EXAMPLE, "alice", window_days=365)
    assert "value/cost ROI" in result["anti_tokenmaxxing_note"]
    assert "NOT for token leaderboard" in result["anti_tokenmaxxing_note"]


# ── 7 维派生函数 unit tests ──────────────────────────────────────────────────


def test_d1_delivery_insufficient_sample():
    """edge case #1: n<5 returns score=None + reason."""
    s = D1_delivery("alice", date.today() - timedelta(days=365), VAULT_EXAMPLE, sample_min=5)
    # vault.example has 1 closed decision · n=1 < 5 → insufficient
    assert s.score is None
    assert s.reason == "insufficient_sample"
    assert s.n == 1


def test_d2_cost_per_outcome_zero_value_zero_score():
    """vault.example has 6 traces · all output_value_usd=null → value=0 → ROI=0 → score=0."""
    s = D2_cost_per_outcome("alice", date.today() - timedelta(days=365), VAULT_EXAMPLE, sample_min=1)
    # alice has 4 traces in vault.example
    assert s.n == 4
    assert s.score == 0  # log10(0+1) = 0


def test_d5_ecosystem_anti_self_gaming():
    """edge case #6: D5 must exclude actor=author trace from adopters."""
    # alice authored 3 skills (meeting-summarize / hike-wiki-update / hike-wiki-query)
    # trace shows: alice uses own 3 (excluded) · bob uses code-review (NOT alice's·skip) ·
    # carol uses meeting-summarize (alice's·counted)
    # → distinct adopters = {carol} = 1 · raw = 3 × 1 = 3
    s = D5_ecosystem("alice", date.today() - timedelta(days=365), VAULT_EXAMPLE)
    assert s.n == 3
    assert s.raw == 3  # 3 skills × 1 adopter (carol) · alice self excluded


def test_d7_learning_first_use_in_window():
    """D7: count skills first used in window."""
    # alice used 3 distinct skills today · all "first use" since vault is fresh
    s = D7_learning("alice", date.today() - timedelta(days=365), VAULT_EXAMPLE)
    # alice traces use: meeting-summarize, hike-wiki-query, hike-wiki-update + 1 trace skill=null
    assert s.n == 3  # 3 distinct non-null skills


# ── finops_summary three views ───────────────────────────────────────────────


def test_finops_cost_per_resolved_decision():
    r = finops_summary(VAULT_EXAMPLE, scope="cost_per_resolved_decision", since_days=365)
    assert r["scope"] == "cost_per_resolved_decision"
    assert r["unit"] == "USD per closed decision"
    assert r["n_decisions_closed"] == 1
    assert r["human_review_required"] is True


def test_finops_unknown_scope_raises():
    with pytest.raises(ValueError):
        finops_summary(VAULT_EXAMPLE, scope="bogus")


def test_finops_three_scopes_all_work():
    for scope in ("cost_per_resolved_decision", "human_equivalent_hourly", "revenue_per_workflow"):
        r = finops_summary(VAULT_EXAMPLE, scope=scope, since_days=365)
        assert r["human_review_required"] is True
        assert "value" in r
