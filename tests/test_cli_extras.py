"""tests/test_cli_extras.py · v1.1.3 polish CLI · verify / status / eval"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_cli_extras import cmd_eval, cmd_status, cmd_verify  # noqa: E402


VAULT_EXAMPLE = Path(__file__).resolve().parent.parent / "vault.example"


def test_status_runs(monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(VAULT_EXAMPLE))
    rc = cmd_status([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Decisions" in out
    assert "Traces" in out
    assert "Skills" in out


def test_status_handles_empty_vault(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    rc = cmd_status([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Decisions   : 0" in out


def test_status_json_shape(monkeypatch, capsys):
    """`status --json` returns parseable dict with all module sections."""
    monkeypatch.setenv("OME365_VAULT", str(VAULT_EXAMPLE))
    rc = cmd_status(["--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    # Required top-level sections
    for k in ("vault", "decisions", "traces", "skills",
              "wiki_categories", "audit_files"):
        assert k in data, f"missing section: {k}"
    # Decisions sub-shape
    for k in ("total", "closed", "open", "owners"):
        assert k in data["decisions"]
    # Traces sub-shape
    for k in ("total", "cost_usd", "actors"):
        assert k in data["traces"]
    # Skills sub-shape
    for k in ("total", "authors"):
        assert k in data["skills"]


def test_status_json_empty_vault(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    rc = cmd_status(["--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["decisions"]["total"] == 0
    assert data["traces"]["total"] == 0
    assert data["skills"]["total"] == 0
    assert data["backups"] is None
    assert data["rbac"] is None
    assert data["signing"] is None


def test_eval_help(capsys):
    rc = cmd_eval([])
    assert rc == 0
    assert "ome365 eval" in capsys.readouterr().out


def test_eval_unknown_returns_2(capsys):
    rc = cmd_eval(["bogus"])
    assert rc == 2


def test_eval_member_runs_on_example(monkeypatch, capsys):
    pytest.importorskip("yaml")
    monkeypatch.setenv("OME365_VAULT", str(VAULT_EXAMPLE))
    rc = cmd_eval(["member", "alice", "--window-days", "365"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "D1_delivery" in out
    assert "alice" in out


def test_eval_member_needs_actor(capsys):
    rc = cmd_eval(["member"])
    assert rc == 2


def test_eval_finops_dashboard_runs(monkeypatch, capsys):
    pytest.importorskip("yaml")
    monkeypatch.setenv("OME365_VAULT", str(VAULT_EXAMPLE))
    rc = cmd_eval(["finops"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "cost_per_resolved_decision" in out


def test_eval_skills_runs(monkeypatch, capsys):
    pytest.importorskip("yaml")
    monkeypatch.setenv("OME365_VAULT", str(VAULT_EXAMPLE))
    rc = cmd_eval(["skills"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "skill" in out.lower()


def test_eval_skills_json(monkeypatch, capsys):
    """`eval skills --json` returns parseable list with name/author/created fields."""
    pytest.importorskip("yaml")
    monkeypatch.setenv("OME365_VAULT", str(VAULT_EXAMPLE))
    rc = cmd_eval(["skills", "--json"])
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    assert isinstance(rows, list)
    assert len(rows) >= 1
    for k in ("name", "author", "created"):
        assert k in rows[0], f"missing field: {k}"


def test_eval_skills_json_empty_vault(tmp_path, monkeypatch, capsys):
    pytest.importorskip("yaml")
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    rc = cmd_eval(["skills", "--json"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == []


def test_eval_whoami_default(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("OME365_ACTOR", raising=False)
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    rc = cmd_eval(["whoami"])
    assert rc == 0
    out = capsys.readouterr().out
    assert json.loads(out.strip())["source"] == "default"


def test_eval_whoami_env_priority(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("OME365_ACTOR", "tester")
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    rc = cmd_eval(["whoami"])
    assert rc == 0
    out = capsys.readouterr().out
    j = json.loads(out.strip())
    assert j["actor"] == "tester"
    assert j["source"] == "env"


def test_verify_needs_arg(capsys):
    rc = cmd_verify([])
    assert rc == 2


def test_verify_signed_local_file(tmp_path, capsys):
    pytest.importorskip("cryptography")
    from ome365_signing import sign

    payload = {"name": "Ome365", "version": "test"}
    signed = sign(payload, vault=tmp_path)
    f = tmp_path / "card.json"
    f.write_text(json.dumps(signed), "utf-8")
    rc = cmd_verify([str(f)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "valid" in out


def test_verify_unsigned_local_file_returns_1(tmp_path, capsys):
    f = tmp_path / "unsigned.json"
    f.write_text('{"name": "X", "version": "1"}', "utf-8")
    rc = cmd_verify([str(f)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "unsigned" in out
