"""tests/test_ome365_decisions.py · v1.1 W2 · Decisions CRUD + lifecycle"""
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_decisions import (  # noqa: E402
    VALID_ANCHORS,
    capture_calibration,
    close_decision,
    create_decision,
    decision_path,
    make_decision_id,
)


@pytest.fixture
def tmp_vault(tmp_path):
    return tmp_path


# ── slug / id generation ─────────────────────────────────────────────────────


def test_make_decision_id_slugify():
    did = make_decision_id("Pick LLM Backend!")
    assert did.startswith(date.today().isoformat())
    assert "pick-llm-backend" in did


def test_make_decision_id_chinese_supported():
    did = make_decision_id("选择 LLM 后端", when=date(2026, 5, 8))
    assert did.startswith("2026-05-08-")
    assert "选择" in did or "llm" in did


# ── create_decision ──────────────────────────────────────────────────────────


def test_create_decision_writes_8_sections(tmp_vault):
    p = create_decision(tmp_vault, "Pick X", "alice", participants=["bob"])
    text = p.read_text("utf-8")
    # 8 sections present
    for marker in ("## ① Problem", "## ② Data", "## ③ Models", "## ④ Options",
                   "## ⑤ Decision", "## ⑥ Reflection", "## ⑦ Execution log",
                   "## ⑧ Feedback"):
        assert marker in text, f"missing section: {marker}"
    # frontmatter sane
    assert "status: open" in text
    assert "owner: alice" in text
    assert "value_anchors: []" in text


def test_create_decision_duplicate_raises(tmp_vault):
    create_decision(tmp_vault, "Same Title", "alice", when=date(2026, 5, 8))
    with pytest.raises(FileExistsError):
        create_decision(tmp_vault, "Same Title", "bob", when=date(2026, 5, 8))


def test_create_decision_planned_duration_optional(tmp_vault):
    p = create_decision(tmp_vault, "T", "a", planned_duration_days=7)
    assert "planned_duration_days: 7" in p.read_text()


# ── close_decision ───────────────────────────────────────────────────────────


def test_close_decision_sets_outcome_and_anchors(tmp_vault):
    p = create_decision(tmp_vault, "Pick", "alice", when=date(2026, 5, 8))
    did = p.stem
    close_decision(tmp_vault, did, outcome="went-with-A", value_anchors=["P", "L"])
    text = p.read_text("utf-8")
    assert "status: closed" in text
    assert 'outcome: "went-with-A"' in text
    assert "value_anchors: [P, L]" in text


def test_close_decision_invalid_anchor_rejected(tmp_vault):
    p = create_decision(tmp_vault, "Pick", "alice", when=date(2026, 5, 8))
    with pytest.raises(ValueError, match="invalid anchors"):
        close_decision(tmp_vault, p.stem, outcome="x", value_anchors=["Bogus"])


def test_close_decision_not_found_raises(tmp_vault):
    with pytest.raises(FileNotFoundError):
        close_decision(tmp_vault, "nonexistent-id", outcome="x", value_anchors=["P"])


def test_close_decision_with_roi_estimated(tmp_vault):
    p = create_decision(tmp_vault, "T", "a", when=date(2026, 5, 8))
    close_decision(tmp_vault, p.stem, outcome="ok", value_anchors=["P"], roi_estimated="+15%")
    text = p.read_text()
    assert 'roi_estimated: "+15%"' in text


# ── capture_calibration ──────────────────────────────────────────────────────


def test_capture_calibration_writes_diff(tmp_vault):
    p = capture_calibration(
        tmp_vault, "decision-x",
        ai_draft="line1\nline2\nai_added",
        human_final="line1\nline2\nhuman_changed",
    )
    text = p.read_text("utf-8")
    assert "decision_id: decision-x" in text
    assert "## AI Draft" in text
    assert "## Human Final" in text
    assert "## Diff" in text
    assert "ai_draft_hash:" in text
    assert "human_final_hash:" in text


def test_capture_calibration_creates_dir(tmp_vault):
    capture_calibration(tmp_vault, "d-1", "a", "b")
    assert (tmp_vault / "Decisions" / ".calibration").exists()


# ── VALID_ANCHORS sanity ─────────────────────────────────────────────────────


def test_valid_anchors_set():
    assert "P" in VALID_ANCHORS
    assert "维护性" in VALID_ANCHORS
    assert "Revert" in VALID_ANCHORS
    assert "Bogus" not in VALID_ANCHORS
    # 6 anchors total (example-vendor范式)
    assert len(VALID_ANCHORS) == 6


# ── End-to-end decision lifecycle ────────────────────────────────────────────


def test_full_lifecycle_open_close_calibrate(tmp_vault):
    """Full cycle: open → close → calibrate · all artifacts exist."""
    p = create_decision(
        tmp_vault, "Vendor Pick", "alice",
        participants=["bob"], planned_duration_days=7,
        when=date(2026, 5, 8),
    )
    did = p.stem
    close_decision(tmp_vault, did, outcome="vendor-A", value_anchors=["P", "L"], roi_estimated="+15%")
    capture_calibration(tmp_vault, did, "AI v1", "Human v2")

    # All 3 artifacts present
    assert decision_path(tmp_vault, did).exists()
    calibs = list((tmp_vault / "Decisions" / ".calibration").glob(f"{did}-feedback-*.md"))
    assert len(calibs) >= 1

    # Decision frontmatter reflects close
    text = p.read_text("utf-8")
    assert "status: closed" in text
    assert "value_anchors: [P, L]" in text
