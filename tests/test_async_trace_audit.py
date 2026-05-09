"""tests/test_async_trace_audit.py · P2 #11 + P2 #13
[decision: 2026-05-09-p2-async-trace-and-audit]
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_audit import VALID_ACTIONS  # noqa: E402
from ome365_audit import cli_main as audit_cli  # noqa: E402
from ome365_audit import grep_recent
from ome365_audit import log as audit_log  # noqa: E402
from ome365_trace import _flush_async, log_async, queue_size  # noqa: E402


# ── Async trace ──────────────────────────────────────────────────────────────


def test_log_async_writes_eventually(tmp_path):
    """log_async should not block · daemon thread eventually writes file."""
    log_async(actor="alice", cost_usd=0.01, vault=tmp_path)
    log_async(actor="bob", cost_usd=0.02, vault=tmp_path)
    log_async(actor="carol", cost_usd=0.03, vault=tmp_path)

    # Wait up to 2s for queue to drain
    deadline = time.time() + 2.0
    trace_dir = tmp_path / "Trace"
    while time.time() < deadline:
        if trace_dir.exists() and any(trace_dir.glob("*.jsonl")):
            files = list(trace_dir.glob("*.jsonl"))
            if files:
                lines = files[0].read_text("utf-8").strip().split("\n")
                if len(lines) >= 3:
                    actors = {json.loads(l)["actor"] for l in lines}
                    if {"alice", "bob", "carol"} <= actors:
                        return
        time.sleep(0.05)
    pytest.fail("async writes did not flush within 2s")


def test_log_async_returns_immediately(tmp_path):
    """The enqueue itself must be sub-millisecond fast."""
    start = time.perf_counter()
    for _ in range(100):
        log_async(actor="alice", cost_usd=0.01, vault=tmp_path)
    elapsed = time.perf_counter() - start
    # 100 enqueues in well under 100ms even on a slow machine
    assert elapsed < 0.5, f"100 enqueues took {elapsed*1000:.1f}ms (>500ms)"


def test_queue_size_observable():
    """queue_size returns int (may be 0 after drain)."""
    n = queue_size()
    assert isinstance(n, int) and n >= 0


# ── Audit log ───────────────────────────────────────────────────────────────


def test_audit_log_appends(tmp_path):
    fp = audit_log(
        actor="alice", action="decision.close",
        target_type="decision", target_id="d-1",
        details={"outcome": "shipped"},
        vault=tmp_path,
    )
    assert fp.parent == tmp_path / "Audit"
    line = fp.read_text("utf-8").strip()
    j = json.loads(line)
    assert j["actor"] == "alice"
    assert j["action"] == "decision.close"
    assert j["target_id"] == "d-1"


def test_audit_log_unknown_action_tagged(tmp_path):
    fp = audit_log(actor="x", action="bogus.event", vault=tmp_path)
    j = json.loads(fp.read_text("utf-8").strip())
    assert j["details"].get("_unknown_action") is True


def test_audit_log_all_valid_actions_pass(tmp_path):
    """All 12 (now 14) valid actions must be writable."""
    for action in VALID_ACTIONS:
        audit_log(actor="alice", action=action, vault=tmp_path)
    files = list((tmp_path / "Audit").glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text("utf-8").strip().split("\n")
    assert len(lines) == len(VALID_ACTIONS)


def test_audit_grep_filters_by_actor(tmp_path):
    audit_log(actor="alice", action="decision.close", vault=tmp_path)
    audit_log(actor="bob", action="decision.close", vault=tmp_path)
    audit_log(actor="alice", action="wiki.update", vault=tmp_path)

    rows = grep_recent(actor="alice", vault=tmp_path)
    assert len(rows) == 2
    assert all(r["actor"] == "alice" for r in rows)


def test_audit_grep_filters_by_target(tmp_path):
    audit_log(actor="alice", action="decision.close", target_id="d-1", vault=tmp_path)
    audit_log(actor="alice", action="decision.close", target_id="d-2", vault=tmp_path)
    rows = grep_recent(target_id="d-1", vault=tmp_path)
    assert len(rows) == 1


def test_audit_grep_respects_days_window(tmp_path):
    old = datetime(2025, 1, 1, tzinfo=timezone.utc)
    audit_log(actor="alice", action="decision.close", vault=tmp_path, when=old)
    audit_log(actor="alice", action="decision.close", vault=tmp_path)
    rows = grep_recent(days=30, vault=tmp_path)
    # Only the recent (today) entry within 30 days
    assert len(rows) == 1


def test_audit_cli_log_and_grep(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    rc = audit_cli(["log", "--actor", "alice", "--action", "decision.close",
                    "--target-id", "d-1"])
    assert rc == 0
    capsys.readouterr()
    rc = audit_cli(["grep", "--actor", "alice"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alice" in out
    assert "1 rows" in out


def test_audit_cli_help(capsys):
    rc = audit_cli([])
    assert rc == 0
    assert "ome365 audit" in capsys.readouterr().out


def test_audit_cli_log_missing_required(capsys):
    rc = audit_cli(["log"])
    assert rc == 2


def test_decision_close_writes_audit_entry(tmp_path):
    """End-to-end: close_decision should write to Audit/<date>.jsonl."""
    pytest.importorskip("yaml")
    from ome365_decisions import close_decision, create_decision

    create_decision(tmp_path, "Pick", "alice")
    p = list((tmp_path / "Decisions").glob("*.md"))[0]
    close_decision(tmp_path, p.stem, outcome="shipped", value_anchors=["P", "L"])

    audit_files = list((tmp_path / "Audit").glob("*.jsonl"))
    assert len(audit_files) == 1
    rows = [json.loads(l) for l in audit_files[0].read_text("utf-8").splitlines() if l.strip()]
    closes = [r for r in rows if r["action"] == "decision.close"]
    assert len(closes) >= 1
    assert closes[0]["target_id"] == p.stem
