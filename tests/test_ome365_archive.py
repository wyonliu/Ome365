"""tests/test_ome365_archive.py · v1.1 W7 · Moxt 95/5 nightly archive"""
import gzip
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_archive import archive, cli_main, recall  # noqa: E402


def _seed_jsonl(vault: Path, day: date, lines: int = 3) -> Path:
    trace_dir = vault / "Trace"
    trace_dir.mkdir(parents=True, exist_ok=True)
    fp = trace_dir / f"{day.isoformat()}.jsonl"
    with fp.open("w", encoding="utf-8") as f:
        for i in range(lines):
            f.write(json.dumps({"ts": f"{day.isoformat()}T0{i}:00:00Z",
                                "actor": f"a{i}", "cost_usd": 0.01}) + "\n")
    return fp


def test_archive_moves_old_files(tmp_path):
    today = date(2026, 5, 9)
    _seed_jsonl(tmp_path, today - timedelta(days=60))
    _seed_jsonl(tmp_path, today - timedelta(days=45))
    _seed_jsonl(tmp_path, today - timedelta(days=10))  # recent · should stay

    result = archive(vault=tmp_path, older_than_days=30, today=today)
    assert result["moved"] == 2
    assert result["skipped_recent"] == 1

    # Old files gone, recent stays
    assert (tmp_path / "Trace" / f"{(today - timedelta(days=10)).isoformat()}.jsonl").exists()
    assert not (tmp_path / "Trace" / f"{(today - timedelta(days=60)).isoformat()}.jsonl").exists()
    # Archive .gz exist
    assert (tmp_path / "Trace" / "archive" / "2026-03.jsonl.gz").exists()


def test_archive_concatenates_by_month(tmp_path):
    today = date(2026, 5, 9)
    _seed_jsonl(tmp_path, date(2026, 3, 1), lines=2)
    _seed_jsonl(tmp_path, date(2026, 3, 15), lines=2)
    _seed_jsonl(tmp_path, date(2026, 3, 30), lines=2)

    archive(vault=tmp_path, older_than_days=30, today=today)
    arc = tmp_path / "Trace" / "archive" / "2026-03.jsonl.gz"
    with gzip.open(arc, "rt") as gz:
        lines = [l for l in gz if l.strip()]
    assert len(lines) == 6  # 3 files × 2 lines


def test_archive_idempotent(tmp_path):
    today = date(2026, 5, 9)
    _seed_jsonl(tmp_path, today - timedelta(days=60))
    archive(vault=tmp_path, older_than_days=30, today=today)
    second = archive(vault=tmp_path, older_than_days=30, today=today)
    assert second["moved"] == 0  # nothing to do · file already archived


def test_recall_yields_lines(tmp_path):
    today = date(2026, 5, 9)
    _seed_jsonl(tmp_path, date(2026, 3, 1), lines=3)
    archive(vault=tmp_path, older_than_days=30, today=today)
    rows = list(recall("2026-03", vault=tmp_path))
    assert len(rows) == 3
    assert all("ts" in r for r in rows)


def test_recall_empty_when_no_archive(tmp_path):
    rows = list(recall("2026-99", vault=tmp_path))
    assert rows == []


def test_archive_handles_empty_vault(tmp_path):
    result = archive(vault=tmp_path, older_than_days=30)
    assert result["moved"] == 0


def test_archive_skips_non_date_filenames(tmp_path):
    trace_dir = tmp_path / "Trace"
    trace_dir.mkdir()
    (trace_dir / "weirdfile.jsonl").write_text("{}\n")
    result = archive(vault=tmp_path, older_than_days=30, today=date(2026, 5, 9))
    assert result["moved"] == 0
    assert (trace_dir / "weirdfile.jsonl").exists()


def test_cli_archive_smoke(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    rc = cli_main(["--older-than", "30"])
    assert rc == 0
    assert '"moved"' in capsys.readouterr().out


def test_cli_help_returns_0(capsys):
    rc = cli_main([])
    assert rc == 0
    assert "ome365 archive" in capsys.readouterr().out
