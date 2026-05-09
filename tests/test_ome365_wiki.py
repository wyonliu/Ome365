"""tests/test_ome365_wiki.py · v1.1 W6 · wiki update + query (Karpathy file-first)"""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_wiki import (  # noqa: E402
    cli_main,
    query,
    update,
)


VAULT_EXAMPLE = Path(__file__).resolve().parent.parent / "vault.example"


def _make_decision(vault: Path, did: str, owner: str, category: str,
                   outcome: str, anchors: list, status: str = "closed",
                   closed: str = "2026-04-10T00:00:00Z") -> Path:
    decisions_dir = vault / "Decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    fp = decisions_dir / f"{did}.md"
    anchor_yaml = "\n".join(f"  - {a}" for a in anchors)
    fp.write_text(
        f"---\n"
        f"id: {did}\n"
        f"opened: 2026-04-01T00:00:00Z\n"
        f"closed: {closed}\n"
        f"status: {status}\n"
        f"owner: {owner}\n"
        f"category: {category}\n"
        f"outcome: '"f"{outcome}"f"'\n"
        f"value_anchors:\n{anchor_yaml}\n"
        f"---\n# d\n",
        "utf-8",
    )
    return fp


# ── update ──────────────────────────────────────────────────────────────────


def test_update_creates_l2_distilled_files(tmp_path):
    pytest.importorskip("yaml")
    _make_decision(tmp_path, "d1", "alice", "infra", "shipped vault SDK", ["P", "L"])
    _make_decision(tmp_path, "d2", "alice", "infra", "fixed N+1 query", ["P", "M"])
    _make_decision(tmp_path, "d3", "alice", "frontend", "redesigned cards", ["P"])

    result = update(vault=tmp_path)
    assert result["appended"] == 3
    assert result["skipped_dup"] == 0

    l2 = tmp_path / "Knowledge" / "L2-distilled"
    assert (l2 / "infra.md").exists()
    assert (l2 / "frontend.md").exists()
    infra = (l2 / "infra.md").read_text("utf-8")
    assert "<!-- key: d1 -->" in infra
    assert "<!-- key: d2 -->" in infra
    assert "shipped vault SDK" in infra
    assert "P" in infra and "L" in infra


def test_update_idempotent_on_rerun(tmp_path):
    pytest.importorskip("yaml")
    _make_decision(tmp_path, "d1", "alice", "infra", "first", ["P"])
    update(vault=tmp_path)
    second = update(vault=tmp_path)
    assert second["appended"] == 0
    assert second["skipped_dup"] == 1


def test_update_skips_open_decisions(tmp_path):
    pytest.importorskip("yaml")
    _make_decision(tmp_path, "d_open", "alice", "infra", "wip", ["P"], status="open")
    result = update(vault=tmp_path)
    assert result["appended"] == 0
    assert result["skipped_open"] >= 1


def test_update_uses_uncategorized_when_no_category(tmp_path):
    pytest.importorskip("yaml")
    decisions = tmp_path / "Decisions"
    decisions.mkdir()
    (decisions / "d_nc.md").write_text(
        "---\nid: d_nc\nopened: 2026-04-01T00:00:00Z\nclosed: 2026-04-10T00:00:00Z\n"
        "status: closed\nowner: alice\noutcome: '"
        "no category"
        "'\nvalue_anchors: []\n---\n",
        "utf-8",
    )
    update(vault=tmp_path)
    assert (tmp_path / "Knowledge" / "L2-distilled" / "uncategorized.md").exists()


def test_update_handles_empty_vault(tmp_path):
    pytest.importorskip("yaml")
    result = update(vault=tmp_path)
    assert result["scanned"] == 0
    assert result["appended"] == 0


def test_update_records_files_written(tmp_path):
    pytest.importorskip("yaml")
    _make_decision(tmp_path, "d1", "alice", "infra", "x", ["P"])
    result = update(vault=tmp_path)
    assert any("infra.md" in f for f in result["files_written"])


# ── query ──────────────────────────────────────────────────────────────────


def test_query_finds_term(tmp_path):
    pytest.importorskip("yaml")
    _make_decision(tmp_path, "d1", "alice", "infra", "shipped trace SDK with monthly rollup", ["P"])
    _make_decision(tmp_path, "d2", "alice", "infra", "fixed cache invalidation", ["M"])
    update(vault=tmp_path)
    rows = query("trace", vault=tmp_path)
    assert len(rows) == 1
    assert rows[0]["decision_id"] == "d1"
    assert "trace" in rows[0]["snippet"].lower()


def test_query_ranks_by_term_frequency(tmp_path):
    pytest.importorskip("yaml")
    _make_decision(tmp_path, "d1", "alice", "infra", "cache cache cache invalidation", ["P"])
    _make_decision(tmp_path, "d2", "alice", "infra", "added cache layer", ["P"])
    update(vault=tmp_path)
    rows = query("cache", vault=tmp_path)
    # d1 has 4 occurrences (3 in claim + nothing else, but decision_id may not match)
    # we just assert d1 ranks first
    assert rows[0]["decision_id"] == "d1"


def test_query_empty_when_no_l2(tmp_path):
    rows = query("anything", vault=tmp_path)
    assert rows == []


def test_query_returns_empty_for_blank(tmp_path):
    pytest.importorskip("yaml")
    _make_decision(tmp_path, "d1", "alice", "infra", "x", ["P"])
    update(vault=tmp_path)
    assert query("", vault=tmp_path) == []
    assert query("   ", vault=tmp_path) == []


# ── CLI ────────────────────────────────────────────────────────────────────


def test_cli_help_returns_0(capsys):
    rc = cli_main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ome365 wiki" in out


def test_cli_unknown_subcommand_returns_2(capsys):
    rc = cli_main(["bogus"])
    assert rc == 2


def test_cli_query_needs_term(capsys):
    rc = cli_main(["query"])
    assert rc == 2
    assert "needs a term" in capsys.readouterr().out


def test_cli_update_then_query_on_vault_example(monkeypatch, capsys):
    """Round-trip on the checked-in vault.example."""
    pytest.importorskip("yaml")
    monkeypatch.setenv("OME365_VAULT", str(VAULT_EXAMPLE))
    rc = cli_main(["update"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "appended" in out

    rc = cli_main(["query", "trace", "SDK"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "matches" in out


# ── P0 #15 dry-run mode ─────────────────────────────────────────────────────


def test_dry_run_does_not_write_files(tmp_path):
    """--dry-run reports what WOULD be written but doesn't touch disk."""
    pytest.importorskip("yaml")
    _make_decision(tmp_path, "d1", "alice", "infra", "shipped X", ["P", "L"])
    _make_decision(tmp_path, "d2", "alice", "infra", "fixed Y", ["P"])

    result = update(vault=tmp_path, dry_run=True)
    assert result["dry_run"] is True
    assert result["appended"] == 0  # nothing written
    assert result["would_append"] == 2
    assert result["would_write"]
    # No files actually written
    l2 = tmp_path / "Knowledge" / "L2-distilled"
    assert not l2.exists() or not list(l2.glob("*.md"))


def test_dry_run_then_real_run_idempotent(tmp_path):
    """dry_run should report the same set as a real run · idempotent."""
    pytest.importorskip("yaml")
    _make_decision(tmp_path, "d1", "alice", "infra", "shipped", ["P"])
    dry = update(vault=tmp_path, dry_run=True)
    real = update(vault=tmp_path, dry_run=False)
    assert dry["would_append"] == real["appended"]


def test_cli_update_dry_run(monkeypatch, tmp_path, capsys):
    """CLI --dry-run flag works."""
    pytest.importorskip("yaml")
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    _make_decision(tmp_path, "d1", "alice", "infra", "shipped", ["P"])
    rc = cli_main(["update", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"dry_run": true' in out
    assert '"appended": 0' in out
    # No files actually written
    assert not (tmp_path / "Knowledge" / "L2-distilled").exists() or \
           not list((tmp_path / "Knowledge" / "L2-distilled").glob("*.md"))
