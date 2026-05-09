"""tests/test_doctor_json.py · v1.1.17 · pin `./ome365 doctor --json` contract
[decision: 2026-05-09-v1-1-3-polish]

The JSON shape is an ops integration contract — monitoring/alerting parses it.
Breaking the shape silently breaks dashboards. These tests fail loudly if any
top-level key changes name, drops, or flips type.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "ome365"


def _run_doctor_json(env_extra: Optional[dict] = None):
    env = os.environ.copy()
    env.pop("OME365_PORT", None)
    if env_extra:
        env.update(env_extra)
    r = subprocess.run(
        [sys.executable, str(LAUNCHER), "doctor", "--json"],
        capture_output=True, text=True, env=env, timeout=30, cwd=ROOT,
    )
    # rc may be 0 (ok) or 1 (missing pkgs) — both should still emit valid JSON.
    # Strip stderr (pythonwarnings etc.) and parse stdout.
    return json.loads(r.stdout), r.returncode


def test_doctor_json_top_level_keys():
    """Top-level keys are the public ops contract — pin them."""
    data, _ = _run_doctor_json({"OME365_VAULT": "/tmp/ome365-doctor-nonexistent"})
    required = {
        "platform", "python_version", "git_sha", "missing_core_pkgs",
        "ports", "files", "v1_1_modules", "ok",
    }
    assert required <= set(data.keys()), f"missing keys: {required - set(data.keys())}"


def test_doctor_json_git_sha_is_short_hex_or_empty():
    """git_sha is a short hex hash when in a repo, empty string otherwise."""
    data, _ = _run_doctor_json({"OME365_VAULT": "/tmp/ome365-doctor-nonexistent"})
    sha = data["git_sha"]
    assert isinstance(sha, str)
    if sha:
        assert all(c in "0123456789abcdef" for c in sha), f"non-hex git_sha: {sha!r}"
        assert 7 <= len(sha) <= 12, f"git_sha length out of range: {len(sha)}"


def test_doctor_json_types():
    """Pin types — alerting libs cast directly without runtime check."""
    data, _ = _run_doctor_json({"OME365_VAULT": "/tmp/ome365-doctor-nonexistent"})
    assert isinstance(data["platform"], str)
    assert isinstance(data["python_version"], str)
    assert isinstance(data["missing_core_pkgs"], list)
    assert isinstance(data["ports"], dict)
    assert isinstance(data["files"], dict)
    assert isinstance(data["v1_1_modules"], dict)
    assert isinstance(data["ok"], bool)


def test_doctor_json_ports_shape():
    data, _ = _run_doctor_json({"OME365_VAULT": "/tmp/ome365-doctor-nonexistent"})
    assert "3650_free" in data["ports"]
    assert "3651_free" in data["ports"]
    assert isinstance(data["ports"]["3650_free"], bool)
    assert isinstance(data["ports"]["3651_free"], bool)


def test_doctor_json_files_shape():
    data, _ = _run_doctor_json({"OME365_VAULT": "/tmp/ome365-doctor-nonexistent"})
    for k in ("env_exists", "tenant_config_live", "tenant_config_sample"):
        assert k in data["files"]
        assert isinstance(data["files"][k], bool)


def test_doctor_json_lists_all_v1_1_modules():
    """Regression guard: if a module is renamed/dropped, this catches it."""
    data, _ = _run_doctor_json({"OME365_VAULT": "/tmp/ome365-doctor-nonexistent"})
    expected_modules = {
        "ome365_eval", "ome365_decisions", "ome365_trace", "ome365_wiki",
        "ome365_archive", "ome365_backup", "ome365_audit", "ome365_metrics",
        "ome365_notify", "ome365_rbac", "ome365_signing", "ome365_cli_extras",
    }
    assert set(data["v1_1_modules"].keys()) == expected_modules
    # Each value is "ok" or "error: ..."
    for name, status in data["v1_1_modules"].items():
        assert status == "ok" or status.startswith("error:"), \
            f"{name} has unexpected status: {status!r}"


def test_doctor_json_ok_flag_true_when_modules_load(tmp_path):
    """ok=True iff no missing core pkgs and all modules import."""
    data, rc = _run_doctor_json({"OME365_VAULT": str(tmp_path)})
    if not data["missing_core_pkgs"] and all(v == "ok" for v in data["v1_1_modules"].values()):
        assert data["ok"] is True
        assert rc == 0
    else:
        assert data["ok"] is False
        assert rc == 1


def test_doctor_json_includes_vault_when_present(tmp_path):
    """When OME365_VAULT exists, doctor surfaces vault state for ops."""
    (tmp_path / "Decisions").mkdir()
    (tmp_path / "Decisions" / "d1.md").write_text("---\nid: d1\n---\n", "utf-8")
    data, _ = _run_doctor_json({"OME365_VAULT": str(tmp_path)})
    assert "vault" in data
    assert data["vault"]["path"] == str(tmp_path.resolve())
    assert data["vault"]["decisions_count"] == 1
    for k in ("trace_files", "skills_count", "signing_key_present", "rbac_present"):
        assert k in data["vault"], f"missing vault.{k}"


def test_doctor_json_machine_parseable():
    """One-line invariant: stdout is parseable JSON, full stop."""
    r = subprocess.run(
        [sys.executable, str(LAUNCHER), "doctor", "--json"],
        capture_output=True, text=True, timeout=30, cwd=ROOT,
        env={**os.environ, "OME365_VAULT": "/tmp/ome365-doctor-nonexistent"},
    )
    # Should not raise
    parsed = json.loads(r.stdout)
    assert isinstance(parsed, dict)
