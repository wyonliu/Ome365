"""tests/test_ome365_backup_metrics.py · P1 #8 + P2 #12
[decision: 2026-05-09-p1-backup-and-metrics]
"""
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_backup import cli_main as backup_cli  # noqa: E402
from ome365_backup import create, list_backups, restore  # noqa: E402
from ome365_metrics import inc, render  # noqa: E402


# ── Backup ──────────────────────────────────────────────────────────────────


def _seed_min_vault(vault: Path) -> None:
    (vault / "Decisions").mkdir(parents=True, exist_ok=True)
    (vault / "Decisions" / "d1.md").write_text(
        "---\nid: d1\nstatus: closed\nowner: alice\n"
        "opened: 2026-04-01T00:00:00Z\nclosed: 2026-04-10T00:00:00Z\n---\n# d1\n",
        "utf-8",
    )
    (vault / "Trace").mkdir(parents=True, exist_ok=True)
    (vault / "Trace" / "2026-05-01.jsonl").write_text(
        '{"ts": "2026-05-01T10:00:00Z", "actor": "alice", "cost_usd": 0.01}\n',
        "utf-8",
    )
    cfg = vault / ".ome365"
    cfg.mkdir()
    (cfg / "eval-config.yml").write_text("preset: 'engineer'\nregion: 'global'\n", "utf-8")
    (cfg / "notify_webhooks.json").write_text(
        '[{"platform": "slack", "url": "https://hooks.slack.com/SECRET"}]', "utf-8",
    )


def test_backup_create_writes_tarball(tmp_path):
    _seed_min_vault(tmp_path)
    out = create(vault=tmp_path)
    assert out.exists()
    assert out.suffix == ".gz"
    assert out.stat().st_size > 0


def test_backup_excludes_secrets(tmp_path):
    _seed_min_vault(tmp_path)
    out = create(vault=tmp_path)
    with tarfile.open(out, "r:gz") as tar:
        names = tar.getnames()
    # eval-config.yml allowed
    assert any("eval-config.yml" in n for n in names)
    # notify_webhooks.json must be excluded
    assert not any("notify_webhooks.json" in n for n in names)


def test_backup_includes_decisions_and_traces(tmp_path):
    _seed_min_vault(tmp_path)
    out = create(vault=tmp_path)
    with tarfile.open(out, "r:gz") as tar:
        names = tar.getnames()
    assert any("Decisions/d1.md" in n for n in names)
    assert any("Trace/2026-05-01.jsonl" in n for n in names)


def test_backup_restore_roundtrip(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _seed_min_vault(src)
    tarball = create(vault=src, dest=tmp_path)

    dst.mkdir()
    result = restore(tarball, vault=dst, safe=False)
    assert result["n_files"] >= 2
    assert (dst / "Decisions" / "d1.md").exists()
    assert (dst / "Trace" / "2026-05-01.jsonl").exists()


def test_backup_safe_restore_makes_prior_backup(tmp_path):
    """safe=True (default) should backup existing vault before restore."""
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _seed_min_vault(src)
    _seed_min_vault(dst)  # dst already has data
    tarball = create(vault=src, dest=tmp_path)

    result = restore(tarball, vault=dst, safe=True)
    assert result["prior_backup"] is not None
    assert Path(result["prior_backup"]).exists()


def test_backup_restore_blocks_path_traversal(tmp_path):
    """Tarball with ../ entries must be rejected."""
    bad = tmp_path / "bad.tar.gz"
    payload = tmp_path / "payload.txt"
    payload.write_text("evil", "utf-8")
    with tarfile.open(bad, "w:gz") as tar:
        ti = tarfile.TarInfo(name="../escape.txt")
        ti.size = payload.stat().st_size
        with payload.open("rb") as f:
            tar.addfile(ti, f)

    with pytest.raises(ValueError, match="unsafe"):
        restore(bad, vault=tmp_path / "victim", safe=False)


def test_backup_list(tmp_path):
    from datetime import datetime, timezone, timedelta
    _seed_min_vault(tmp_path)
    t0 = datetime.now(timezone.utc)
    create(vault=tmp_path, when=t0)
    create(vault=tmp_path, when=t0 + timedelta(seconds=2))
    rows = list_backups(tmp_path / "Backups")
    assert len(rows) == 2
    assert all("size_mb" in r for r in rows)


def test_backup_cli_create_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    _seed_min_vault(tmp_path)
    rc = backup_cli(["create"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "created" in out

    rc = backup_cli(["list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "vault-" in out


def test_backup_cli_help(capsys):
    rc = backup_cli([])
    assert rc == 0
    assert "ome365 backup" in capsys.readouterr().out


def test_backup_cli_restore_needs_path(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    rc = backup_cli(["restore"])
    assert rc == 2


# ── Metrics ─────────────────────────────────────────────────────────────────


def test_metrics_render_basic(tmp_path, monkeypatch):
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    _seed_min_vault(tmp_path)
    text = render(vault=tmp_path)
    assert "ome365_decisions_total" in text
    assert "ome365_traces_total" in text
    assert "ome365_skills_total" in text
    assert "# HELP" in text
    assert "# TYPE" in text


def test_metrics_render_includes_uptime(tmp_path):
    text = render(vault=tmp_path)
    assert "ome365_uptime_seconds" in text


def test_metrics_inc_counter(tmp_path):
    inc("eval_member", 3)
    text = render(vault=tmp_path)
    assert 'endpoint="eval_member"' in text


def test_metrics_render_handles_empty_vault(tmp_path):
    """Empty vault should still render valid Prometheus text."""
    text = render(vault=tmp_path)
    assert text.endswith("\n")
    # No # comments without metrics should crash a parser
    assert "ome365_decisions_total{} 0" in text or "ome365_decisions_total 0" in text


def test_metrics_via_http(tmp_path, monkeypatch):
    """Smoke: GET /metrics endpoint returns 200 and text/plain."""
    pytest.importorskip("yaml")
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from fastapi.responses import PlainTextResponse

    _seed_min_vault(tmp_path)
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))

    app = fastapi.FastAPI()

    @app.get("/metrics", response_class=PlainTextResponse)
    def m():
        return render()

    client = TestClient(app)
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "ome365_decisions_total" in r.text


# ── v1.1.15 backup --dry-run ─────────────────────────────────────────────────


def test_backup_dry_run_no_disk_writes(tmp_path):
    _seed_min_vault(tmp_path)
    # Add a __pycache__ file in Decisions/ so DEFAULT_EXCLUDE_PATTERNS skip is exercised
    (tmp_path / "Decisions" / "__pycache__").mkdir(exist_ok=True)
    (tmp_path / "Decisions" / "__pycache__" / "junk.pyc").write_bytes(b"\x00")
    result = create(vault=tmp_path, dest=tmp_path, dry_run=True)
    assert isinstance(result, dict)
    assert result["dry_run"] is True
    assert result["would_include_count"] >= 2  # d1.md + 2026-05-01.jsonl + eval-config.yml
    assert result["would_skip_count"] >= 1  # __pycache__/junk.pyc
    # No tarball written
    assert not list(tmp_path.glob("vault-*.tar.gz"))


def test_backup_cli_create_dry_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OME365_VAULT", str(tmp_path))
    _seed_min_vault(tmp_path)
    rc = backup_cli(["create", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"dry_run": true' in out
    # No tarball created in default Backups/
    assert not (tmp_path / "Backups").exists() or \
           not list((tmp_path / "Backups").glob("vault-*.tar.gz"))
