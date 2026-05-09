"""tests/test_ome365_trace.py · v1.1 W3 · Trace SDK + CLI + monthly rollup contract tests"""
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_trace import (  # noqa: E402
    cli_main,
    log,
    monthly_rollup,
    query,
    session,
)


# ── log() · append-only jsonl write ──────────────────────────────────────────


def test_log_writes_jsonl_in_trace_dir(tmp_path):
    fp = log(actor="alice", cost_usd=0.012, skill="meeting-summarize", vault=tmp_path)
    assert fp.parent == tmp_path / "Trace"
    assert fp.suffix == ".jsonl"
    line = fp.read_text("utf-8").strip()
    obj = json.loads(line)
    assert obj["actor"] == "alice"
    assert obj["cost_usd"] == 0.012
    assert obj["skill"] == "meeting-summarize"
    assert obj["ts"].endswith("Z")


def test_log_schema_has_all_v11_fields(tmp_path):
    """Schema MUST match v1.1 impl spec §四 4.5 · 11 fields + ts."""
    fp = log(
        actor="alice", cost_usd=0.01, skill="x", decision_id="d-1",
        model="claude-sonnet-4-6", tokens_in=100, tokens_out=50,
        output_value_usd=0.5, value_attribution="manual",
        elapsed_ms=1234, tenant="acme", vault=tmp_path,
    )
    obj = json.loads(fp.read_text("utf-8").strip())
    expected = {
        "ts", "actor", "skill", "decision_id", "model", "tokens_in", "tokens_out",
        "cost_usd", "output_value_usd", "value_attribution", "elapsed_ms", "tenant",
    }
    assert set(obj.keys()) == expected


def test_log_appends_multiple_lines(tmp_path):
    log(actor="alice", cost_usd=0.01, vault=tmp_path)
    log(actor="bob", cost_usd=0.02, vault=tmp_path)
    log(actor="alice", cost_usd=0.03, vault=tmp_path)
    files = list((tmp_path / "Trace").glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text("utf-8").strip().split("\n")
    assert len(lines) == 3


def test_log_when_param_controls_filename(tmp_path):
    custom = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)
    fp = log(actor="alice", cost_usd=0.01, when=custom, vault=tmp_path)
    assert fp.name == "2026-05-09.jsonl"


# ── session() · context manager auto-time ────────────────────────────────────


def test_session_auto_writes_on_exit(tmp_path):
    with session("alice", skill="x", vault=tmp_path) as t:
        t.tokens_in = 100
        t.tokens_out = 50
        t.cost_usd = 0.01
    files = list((tmp_path / "Trace").glob("*.jsonl"))
    assert len(files) == 1
    obj = json.loads(files[0].read_text("utf-8").strip())
    assert obj["actor"] == "alice"
    assert obj["tokens_in"] == 100
    assert obj["cost_usd"] == 0.01
    assert obj["elapsed_ms"] is not None
    assert obj["elapsed_ms"] >= 0


def test_session_auto_extracts_anthropic_usage(tmp_path):
    """record_response() handles anthropic-style usage object."""
    class FakeUsage:
        input_tokens = 200
        output_tokens = 80

    class FakeResponse:
        usage = FakeUsage()

    with session("alice", vault=tmp_path) as t:
        t.record_response(FakeResponse())
        t.cost_usd = 0.05
    obj = json.loads(list((tmp_path / "Trace").glob("*.jsonl"))[0].read_text("utf-8").strip())
    assert obj["tokens_in"] == 200
    assert obj["tokens_out"] == 80


def test_session_auto_extracts_dict_usage(tmp_path):
    """record_response() handles dict usage (openai-style)."""
    fake_response = {"usage": {"prompt_tokens": 150, "completion_tokens": 60}}

    with session("alice", vault=tmp_path) as t:
        t.record_response(fake_response)
        t.cost_usd = 0.03
    obj = json.loads(list((tmp_path / "Trace").glob("*.jsonl"))[0].read_text("utf-8").strip())
    assert obj["tokens_in"] == 150
    assert obj["tokens_out"] == 60


# ── query() · grep-style filter ──────────────────────────────────────────────


def test_query_filters_by_actor(tmp_path):
    log(actor="alice", cost_usd=0.01, vault=tmp_path)
    log(actor="bob", cost_usd=0.02, vault=tmp_path)
    log(actor="alice", cost_usd=0.03, vault=tmp_path)
    rows = query(actor="alice", vault=tmp_path)
    assert len(rows) == 2
    assert all(r["actor"] == "alice" for r in rows)


def test_query_filters_by_skill_and_decision(tmp_path):
    log(actor="alice", cost_usd=0.01, skill="x", decision_id="d-1", vault=tmp_path)
    log(actor="alice", cost_usd=0.01, skill="y", decision_id="d-1", vault=tmp_path)
    log(actor="alice", cost_usd=0.01, skill="x", decision_id="d-2", vault=tmp_path)
    rows = query(skill="x", decision_id="d-1", vault=tmp_path)
    assert len(rows) == 1


def test_query_empty_when_no_trace_dir(tmp_path):
    assert query(vault=tmp_path) == []


# ── monthly_rollup() · nightly job ───────────────────────────────────────────


def test_monthly_rollup_aggregates_by_actor_skill_decision(tmp_path):
    when = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)
    log(actor="alice", cost_usd=0.10, skill="x", decision_id="d-1",
        output_value_usd=1.0, when=when, vault=tmp_path)
    log(actor="alice", cost_usd=0.20, skill="x", decision_id="d-1",
        output_value_usd=2.0, when=when, vault=tmp_path)
    log(actor="bob", cost_usd=0.05, skill="y", decision_id="d-2",
        output_value_usd=0.5, when=when, vault=tmp_path)

    out = monthly_rollup(period="2026-05", vault=tmp_path)
    assert out is not None
    summary = json.loads(out.read_text("utf-8"))
    assert summary["period"] == "2026-05"
    assert summary["totals"]["requests"] == 3
    assert abs(summary["totals"]["cost_usd"] - 0.35) < 1e-9
    assert abs(summary["totals"]["value_usd"] - 3.5) < 1e-9
    assert summary["by_actor"]["alice"]["requests"] == 2
    assert summary["by_skill"]["x"]["requests"] == 2
    assert summary["by_decision"]["d-1"]["requests"] == 2


def test_monthly_rollup_returns_none_when_no_data(tmp_path):
    assert monthly_rollup(period="2026-05", vault=tmp_path) is None


def test_monthly_rollup_writes_summary_file(tmp_path):
    when = datetime(2026, 5, 9, tzinfo=timezone.utc)
    log(actor="alice", cost_usd=0.01, when=when, vault=tmp_path)
    out = monthly_rollup(period="2026-05", vault=tmp_path)
    assert out.parent.name == "monthly"
    assert out.name == "2026-05.summary.json"
    assert out.exists()


# ── cli_main · subcommand dispatch ───────────────────────────────────────────


def test_cli_add_appends_line(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    rc = cli_main(["add", "--actor", "alice", "--cost", "0.01", "--skill", "x"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "appended" in out
    assert (tmp_path / "Trace").exists()


def test_cli_add_missing_required_returns_2(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    rc = cli_main(["add", "--actor", "alice"])  # missing --cost
    assert rc == 2
    assert "ERROR" in capsys.readouterr().out


def test_cli_query_prints_rows(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    cli_main(["add", "--actor", "alice", "--cost", "0.01"])
    capsys.readouterr()
    rc = cli_main(["query", "--actor", "alice"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alice" in out
    assert "1 rows" in out


def test_cli_rollup_for_current_month(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    today = date.today()
    period = f"{today.year}-{today.month:02d}"
    cli_main(["add", "--actor", "alice", "--cost", "0.01"])
    capsys.readouterr()
    rc = cli_main(["rollup", "--period", period])
    assert rc == 0
    assert "rolled up" in capsys.readouterr().out


def test_cli_help_returns_0(capsys):
    rc = cli_main([])
    assert rc == 0
    assert "ome365 trace" in capsys.readouterr().out


def test_cli_unknown_subcommand_returns_2(capsys):
    rc = cli_main(["bogus"])
    assert rc == 2
    assert "unknown subcommand" in capsys.readouterr().out
