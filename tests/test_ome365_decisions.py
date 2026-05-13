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
    cli_main as decision_cli,
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
    # 6 anchors total (industry pattern)
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


# ── v1.1.26 · decision CLI ──────────────────────────────────────────────────


def test_decision_cli_help(capsys):
    rc = decision_cli([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ome365 decision" in out
    assert "list" in out and "show" in out


def test_decision_cli_list_text(tmp_vault, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    create_decision(tmp_vault, "Pick X", "alice", when=date(2026, 5, 8))
    create_decision(tmp_vault, "Pick Y", "bob", when=date(2026, 5, 8))
    rc = decision_cli(["list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[open]" in out
    assert "alice" in out and "bob" in out


def test_decision_cli_list_json(tmp_vault, monkeypatch, capsys):
    import json as _json
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    create_decision(tmp_vault, "Pick X", "alice", when=date(2026, 5, 8))
    rc = decision_cli(["list", "--json"])
    assert rc == 0
    rows = _json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["owner"] == "alice"
    assert rows[0]["status"] == "open"


def test_decision_cli_list_filters(tmp_vault, monkeypatch, capsys):
    import json as _json
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    p1 = create_decision(tmp_vault, "Pick X", "alice", when=date(2026, 5, 8))
    create_decision(tmp_vault, "Pick Y", "bob", when=date(2026, 5, 8))
    close_decision(tmp_vault, p1.stem, outcome="shipped", value_anchors=["P"])

    rc = decision_cli(["list", "--status", "closed", "--json"])
    assert rc == 0
    rows = _json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["owner"] == "alice"

    rc = decision_cli(["list", "--owner", "bob", "--json"])
    assert rc == 0
    rows = _json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["status"] == "open"


def test_decision_cli_list_empty(tmp_vault, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    rc = decision_cli(["list"])
    assert rc == 0
    assert "no decisions" in capsys.readouterr().out


def test_decision_cli_show(tmp_vault, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    p = create_decision(tmp_vault, "Pick LLM", "alice", when=date(2026, 5, 8))
    rc = decision_cli(["show", p.stem])
    assert rc == 0
    out = capsys.readouterr().out
    assert "## ① Problem" in out
    assert "alice" in out


def test_decision_cli_show_not_found(tmp_vault, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    rc = decision_cli(["show", "nonexistent-id"])
    assert rc == 2
    assert "not found" in capsys.readouterr().out


# ── v1.1.27 · decision CLI mutations ────────────────────────────────────────


def test_decision_cli_new(tmp_vault, monkeypatch, capsys):
    import json as _json
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    rc = decision_cli(["new", "Pick", "vendor", "X", "--owner", "alice"])
    assert rc == 0
    parsed = _json.loads(capsys.readouterr().out)
    assert "id" in parsed and "path" in parsed
    assert (tmp_vault / "Decisions").exists()
    assert any((tmp_vault / "Decisions").glob("*pick*.md"))


def test_decision_cli_new_with_options(tmp_vault, monkeypatch, capsys):
    import json as _json
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    rc = decision_cli([
        "new", "Hire", "engineer",
        "--owner", "alice",
        "--participants", "bob,carol",
        "--category", "hiring",
        "--planned-duration-days", "30",
    ])
    assert rc == 0
    parsed = _json.loads(capsys.readouterr().out)
    text = (tmp_vault / "Decisions" / f"{parsed['id']}.md").read_text("utf-8")
    assert "category: hiring" in text
    assert "planned_duration_days: 30" in text
    assert "bob" in text and "carol" in text


def test_decision_cli_new_requires_owner(tmp_vault, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    rc = decision_cli(["new", "title-only"])
    assert rc == 2
    assert "ERROR" in capsys.readouterr().out


def test_decision_cli_close(tmp_vault, monkeypatch, capsys):
    import json as _json
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    p = create_decision(tmp_vault, "Pick LLM", "alice", when=date(2026, 5, 8))
    rc = decision_cli([
        "close", p.stem,
        "--outcome", "shipped Claude",
        "--value-anchors", "P,L",
    ])
    assert rc == 0
    parsed = _json.loads(capsys.readouterr().out)
    assert parsed["status"] == "closed"
    assert parsed["value_anchors"] == ["P", "L"]
    text = p.read_text("utf-8")
    assert "status: closed" in text


def test_decision_cli_close_invalid_anchor(tmp_vault, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    p = create_decision(tmp_vault, "Pick X", "alice", when=date(2026, 5, 8))
    rc = decision_cli([
        "close", p.stem,
        "--outcome", "x",
        "--value-anchors", "godmode",  # not a valid anchor
    ])
    assert rc == 2
    assert "ERROR" in capsys.readouterr().out


def test_decision_cli_close_fires_audit(tmp_vault, monkeypatch, capsys):
    """Closing via CLI must hit the same audit hook as HTTP route."""
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    p = create_decision(tmp_vault, "Pick X", "alice", when=date(2026, 5, 8))
    decision_cli(["close", p.stem, "--outcome", "shipped", "--value-anchors", "P"])
    audit_dir = tmp_vault / "Audit"
    assert audit_dir.exists()
    audit_files = list(audit_dir.glob("*.jsonl"))
    assert len(audit_files) >= 1
    text = audit_files[0].read_text("utf-8")
    assert "decision.close" in text
    assert "alice" in text


# ── v1.1.33 · decision list --limit N ───────────────────────────────────────


def test_decision_cli_list_limit(tmp_vault, monkeypatch, capsys):
    """--limit N keeps the N most recent decisions."""
    import json as _json
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    # Create 5 decisions across different days
    for i, day in enumerate([date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3),
                              date(2026, 5, 4), date(2026, 5, 5)]):
        create_decision(tmp_vault, f"Title {i}", "alice", when=day)
    rc = decision_cli(["list", "--limit", "2", "--json"])
    assert rc == 0
    rows = _json.loads(capsys.readouterr().out)
    assert len(rows) == 2
    # Should be the latest two — IDs include 2026-05-04 and 2026-05-05
    ids = [r["id"] for r in rows]
    assert any("2026-05-04" in i for i in ids)
    assert any("2026-05-05" in i for i in ids)


def test_decision_cli_list_limit_zero_or_negative_no_op(tmp_vault, monkeypatch, capsys):
    """--limit 0 should not filter (matches trace --limit 0 semantics)."""
    import json as _json
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    create_decision(tmp_vault, "A", "alice", when=date(2026, 5, 1))
    create_decision(tmp_vault, "B", "alice", when=date(2026, 5, 2))
    rc = decision_cli(["list", "--limit", "0", "--json"])
    assert rc == 0
    rows = _json.loads(capsys.readouterr().out)
    assert len(rows) == 2  # all returned


def test_decision_cli_list_limit_combines_with_filters(tmp_vault, monkeypatch, capsys):
    import json as _json
    monkeypatch.setenv("OME365_VAULT", str(tmp_vault))
    create_decision(tmp_vault, "Old A", "alice", when=date(2026, 4, 1))
    create_decision(tmp_vault, "Old B", "bob", when=date(2026, 4, 2))
    create_decision(tmp_vault, "New A", "alice", when=date(2026, 5, 5))
    rc = decision_cli([
        "list", "--owner", "alice", "--limit", "1", "--json"
    ])
    assert rc == 0
    rows = _json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["owner"] == "alice"
    assert "2026-05-05" in rows[0]["id"]
