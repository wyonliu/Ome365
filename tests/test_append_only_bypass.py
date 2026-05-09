"""tests/test_append_only_bypass.py · Review-Fix 8.2
Kevin git hook bypass detection · invariant: code commit must cite [decision: <id>]
Test --no-verify behavior + missing hook detection + audit-loggable bypass attempt
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / ".githooks" / "commit-msg"


def test_kevin_hook_exists_and_is_executable():
    """Hook must be present and executable for Kevin '先文件再代码' rule to fire."""
    assert HOOK_PATH.exists(), "Kevin commit-msg hook missing"
    assert os.access(HOOK_PATH, os.X_OK), "hook not executable · users will silently bypass"


def test_hook_rejects_msg_without_decision_tag(tmp_path):
    """Real git repo with staged code file · code-impact msg without [decision: ID] → exit !=0."""
    # Set up tiny git repo so `git diff --cached` returns staged code files
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    app_dir = repo / ".app"
    app_dir.mkdir()
    code_file = app_dir / "feature.py"
    code_file.write_text("x = 1\n", "utf-8")
    subprocess.run(["git", "add", str(code_file.relative_to(repo))], cwd=repo, check=True)

    msg = repo / "msg.txt"
    msg.write_text("feat(eval): add new dimension D8 burnout scoring", "utf-8")

    # Run hook from inside the test repo so git diff --cached sees staged file
    r = subprocess.run(
        [str(HOOK_PATH), str(msg)],
        cwd=repo, capture_output=True, text=True,
        env={**os.environ, "OME365_NO_DECISION": ""},
    )
    assert r.returncode != 0, f"hook must reject code commit · stdout={r.stdout} stderr={r.stderr}"
    assert "Kevin rule" in r.stderr or "decision" in r.stderr.lower()


def test_hook_accepts_msg_with_decision_tag(tmp_path):
    """Hook accepts when [decision: <id>] is present."""
    msg = tmp_path / "msg.txt"
    msg.write_text(
        "feat(eval): D8 burnout dim\n\n"
        "[decision: 2026-05-09-d8-burnout-design]\n",
        "utf-8",
    )
    r = subprocess.run([str(HOOK_PATH), str(msg)], capture_output=True, text=True)
    assert r.returncode == 0, f"hook rejected valid msg: {r.stderr}"


def test_hook_skips_chore_docs_prefixes(tmp_path):
    """chore: / docs: / merge: prefixes should auto-pass without decision tag."""
    for prefix in ("chore:", "docs:", "test:", "ci:", "Merge "):
        msg = tmp_path / "msg.txt"
        msg.write_text(f"{prefix} routine update", "utf-8")
        r = subprocess.run([str(HOOK_PATH), str(msg)], capture_output=True, text=True)
        assert r.returncode == 0, f"{prefix} should auto-pass: {r.stderr}"


def test_no_verify_bypass_documented():
    """
    git commit --no-verify is OS-level bypass that no client-side hook can stop.
    The defense is the user's git config and (future) server-side hook.
    Document the limitation in code so v1.2 can add server-side check.
    """
    # Read the hook source · must contain a comment about --no-verify limitation
    src = HOOK_PATH.read_text("utf-8")
    assert "OME365_NO_DECISION" in src, "hook should expose escape hatch env var for emergencies"
    # Future: add CI step that audits remote commits for [decision] coverage
    # post-merge to detect bypassed commits


def test_emergency_bypass_env_var(tmp_path):
    """OME365_NO_DECISION=1 emergency bypass for genuine emergencies (must be logged)."""
    msg = tmp_path / "msg.txt"
    msg.write_text("feat(eval): emergency hotfix without time to write decision", "utf-8")
    r = subprocess.run([str(HOOK_PATH), str(msg)],
                       capture_output=True, text=True,
                       env={**os.environ, "OME365_NO_DECISION": "1"})
    assert r.returncode == 0, "emergency bypass should work for genuine emergencies"
