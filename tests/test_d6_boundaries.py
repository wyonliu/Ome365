"""tests/test_d6_boundaries.py · Review-Fix 8.3
D6 revenue_per_workflow boundary tests:
  · 89 vs 90 days (off-by-one)
  · roi_actual=0 (no revenue) vs roi_actual=null (not yet backfilled)
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_eval import D6_revenue_per_workflow  # noqa: E402


def _make_decision(vault: Path, did: str, owner: str, days_ago: int,
                   roi_actual=None, anchors: list = None) -> Path:
    decisions = vault / "Decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    closed = (date.today() - timedelta(days=days_ago)).isoformat() + "T00:00:00Z"
    opened = (date.today() - timedelta(days=days_ago + 5)).isoformat() + "T00:00:00Z"
    roi_line = f"roi_actual: {roi_actual}\n" if roi_actual is not None else "roi_actual: null\n"
    anchor_yaml = "\n".join(f"  - {a}" for a in (anchors or []))
    if not anchor_yaml:
        anchor_yaml = " []"
        anchor_block = f"value_anchors:{anchor_yaml}\n"
    else:
        anchor_block = f"value_anchors:\n{anchor_yaml}\n"
    fp = decisions / f"{did}.md"
    fp.write_text(
        f"---\nid: {did}\nopened: {opened}\nclosed: {closed}\nstatus: closed\n"
        f"owner: {owner}\noutcome: '"f"shipped"f"'\n{roi_line}{anchor_block}---\n",
        "utf-8",
    )
    return fp


# ── 89 vs 90 day boundary ───────────────────────────────────────────────────


def test_d6_89_days_falls_back_to_anchor(tmp_path):
    """Decision closed 89 days ago · roi_actual present · should use anchor path (< 90)."""
    pytest.importorskip("yaml")
    aw = {"P": 2.0, "L": 2.0, "Revert": -2.0, "维护性": -0.5}
    for i in range(3):
        _make_decision(tmp_path, f"d{i}", "alice", days_ago=89,
                       roi_actual=10000.0, anchors=["P", "L"])
    s = D6_revenue_per_workflow("alice", date.today() - timedelta(days=365),
                                 tmp_path, aw, sample_min=3)
    # 89 < 90 → anchor path · NOT USD
    assert s.score is not None
    # anchor avg = 2.0 → score=2.0 (clipped); USD path would give log10(30000)-2 ≈ 2.48
    # so we just confirm we used anchor by checking raw is small (anchor weight) not large (USD)
    assert s.raw is not None
    assert s.raw < 5  # anchor weights are small numbers


def test_d6_90_days_uses_roi_actual_usd(tmp_path):
    """Decision closed exactly 90 days ago · roi_actual → USD path."""
    pytest.importorskip("yaml")
    aw = {"P": 2.0, "L": 2.0}
    for i in range(3):
        _make_decision(tmp_path, f"d{i}", "alice", days_ago=90,
                       roi_actual=5000.0, anchors=["P"])
    s = D6_revenue_per_workflow("alice", date.today() - timedelta(days=365),
                                 tmp_path, aw, sample_min=3)
    assert s.score is not None
    # USD path · raw = sum(roi_actual) = 15000 (3 decisions × 5000)
    assert s.raw == 15000.0


def test_d6_91_days_uses_roi_actual_usd(tmp_path):
    """Decision closed 91 days ago · same as 90 (>= 90 trigger)."""
    pytest.importorskip("yaml")
    aw = {"P": 2.0}
    for i in range(3):
        _make_decision(tmp_path, f"d{i}", "alice", days_ago=91,
                       roi_actual=2000.0, anchors=["P"])
    s = D6_revenue_per_workflow("alice", date.today() - timedelta(days=365),
                                 tmp_path, aw, sample_min=3)
    assert s.raw == 6000.0


# ── roi_actual=0 vs null distinction ────────────────────────────────────────


def test_d6_roi_actual_null_uses_anchor_path(tmp_path):
    """roi_actual: null · 90+ days · should fall back to anchor (no roi yet)."""
    pytest.importorskip("yaml")
    aw = {"P": 2.0, "L": 2.0}
    for i in range(3):
        _make_decision(tmp_path, f"d{i}", "alice", days_ago=120,
                       roi_actual=None, anchors=["P", "L"])
    s = D6_revenue_per_workflow("alice", date.today() - timedelta(days=365),
                                 tmp_path, aw, sample_min=3)
    assert s.score is not None
    assert s.reason != "no_roi_data"  # has anchors
    # anchor path → small raw value (avg of P+L = 2.0)
    assert s.raw is not None and s.raw < 5


def test_d6_roi_actual_zero_falls_back_to_anchor(tmp_path):
    """
    roi_actual: 0 (post-fix 8.3): means "shipped · no revenue tracked yet" ·
    semantically equivalent to null for D6 purposes · should use anchor path.
    """
    pytest.importorskip("yaml")
    aw = {"P": 2.0}
    for i in range(3):
        _make_decision(tmp_path, f"d{i}", "alice", days_ago=120,
                       roi_actual=0.0, anchors=["P"])
    s = D6_revenue_per_workflow("alice", date.today() - timedelta(days=365),
                                 tmp_path, aw, sample_min=3)
    # Fixed: 0 falls to anchor path · score derived from P=2.0 weight
    assert s.score is not None
    assert s.reason != "no_roi_data"
    assert s.raw == 2.0  # avg anchor weight (P=2.0 across 3 decisions)


def test_d6_mixed_old_and_new_decisions(tmp_path):
    """3 decisions: 1 at 120 days (roi=2000) + 2 at 30 days (anchors only)
    → only the 120-day one contributes USD · total_usd = 2000."""
    pytest.importorskip("yaml")
    aw = {"P": 2.0, "L": 2.0}
    _make_decision(tmp_path, "old", "alice", days_ago=120, roi_actual=2000.0, anchors=["P"])
    _make_decision(tmp_path, "mid1", "alice", days_ago=30, anchors=["P", "L"])
    _make_decision(tmp_path, "mid2", "alice", days_ago=30, anchors=["L"])
    s = D6_revenue_per_workflow("alice", date.today() - timedelta(days=365),
                                 tmp_path, aw, sample_min=3)
    # USD path triggered because total_usd > 0 (the 120-day one)
    assert s.raw == 2000.0


def test_d6_no_roi_no_anchors_returns_no_data_reason(tmp_path):
    """No roi_actual (or 0) and no anchors · should reason='no_roi_data'."""
    pytest.importorskip("yaml")
    aw = {}
    for i in range(3):
        _make_decision(tmp_path, f"d{i}", "alice", days_ago=120,
                       roi_actual=None, anchors=[])
    s = D6_revenue_per_workflow("alice", date.today() - timedelta(days=365),
                                 tmp_path, aw, sample_min=3)
    assert s.reason == "no_roi_data"
