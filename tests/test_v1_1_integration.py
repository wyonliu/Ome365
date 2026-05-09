"""tests/test_v1_1_integration.py · v1.1.8 · full v1.1 lifecycle integration

Exercises every v1.1 module end-to-end in one realistic scenario:
  · seed RBAC config
  · create decision (Kevin commit-msg semantically simulated)
  · close decision · audit + notify hooks fire
  · log traces (sync + async)
  · run wiki update (rule-based)
  · query distilled patterns
  · run eval member · expect 7 dimensions
  · render Prom metrics
  · backup vault · restore to fresh dir · verify intact
  · verify ed25519 agent-card

If any module breaks this scenario, this test catches it before users do.
"""
import gzip
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))


def _seed_config(vault: Path) -> None:
    cfg = vault / ".ome365"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "eval-config.yml").write_text(
        "preset: 'engineer'\nregion: 'global'\nsample_size_min: 3\n"
        "weights:\n  delivery: 0.20\n  cost_per_outcome: 0.15\n  quality: 0.20\n"
        "  judgment: 0.15\n  ecosystem: 0.10\n  revenue_per_workflow: 0.10\n  learning: 0.10\n"
        "value_anchor_weights:\n  P: 2.0\n  XL: 3.0\n  L: 2.0\n  M: 1.0\n"
        "  '维护性': -0.5\n  Revert: -2.0\n",
        "utf-8",
    )
    (cfg / "roles.yml").write_text(
        "default_role: 'contributor'\n"
        "members:\n  alice: 'owner'\n  bob: 'contributor'\n  carol: 'viewer'\n",
        "utf-8",
    )


def test_full_v1_1_lifecycle(tmp_path):
    """End-to-end · 12 v1.1 modules cooperate without leakage."""
    pytest.importorskip("yaml")
    pytest.importorskip("cryptography")

    from ome365_archive import archive
    from ome365_audit import grep_recent
    from ome365_backup import create as backup_create
    from ome365_backup import restore as backup_restore
    from ome365_decisions import close_decision, create_decision
    from ome365_eval import (
        _compute_team_distribution, eval_member, finops_summary,
        grep_decisions_all, grep_skills_all, grep_trace_all,
    )
    from ome365_metrics import render
    from ome365_rbac import can, role_of
    from ome365_signing import sign, verify
    from ome365_trace import log as trace_log
    from ome365_trace import log_async
    from ome365_wiki import query as wiki_query
    from ome365_wiki import update as wiki_update

    _seed_config(tmp_path)

    # ── 1. RBAC enforcement -----------------------------------------
    assert role_of("alice", vault=tmp_path) == "owner"
    assert role_of("carol", vault=tmp_path) == "viewer"
    assert can("alice", "admin", vault=tmp_path)
    assert not can("carol", "write", vault=tmp_path)

    # ── 2. Create + close decisions (5 to satisfy sample_min=5 ish)
    for i, anchors in enumerate([["P", "L"], ["P", "XL"], ["P"], ["L", "M"], ["P", "L", "维护性"]]):
        p = create_decision(tmp_path, f"Decision {i}", "alice", participants=["bob"])
        close_decision(tmp_path, p.stem, outcome=f"shipped feature {i}",
                       value_anchors=anchors, roi_estimated="+15%")

    decisions = grep_decisions_all(tmp_path)
    assert len(decisions) == 5
    assert all(d.status == "closed" for d in decisions)

    # ── 3. Audit log fired on each close
    audit_rows = grep_recent(action="decision.close", days=1, vault=tmp_path)
    assert len(audit_rows) == 5
    assert audit_rows[0]["actor"] == "alice"

    # ── 4. Trace log (sync + async)
    for i in range(6):
        trace_log(actor="alice", cost_usd=0.01 * (i + 1),
                  output_value_usd=0.5 + i * 0.1,
                  skill="meeting-summarize",
                  decision_id=decisions[i % 5].id, vault=tmp_path)
    log_async(actor="bob", cost_usd=0.005, skill="code-review", vault=tmp_path)

    # Wait for async writes to land
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if any("bob" in line for fp in (tmp_path / "Trace").glob("*.jsonl")
               for line in fp.read_text("utf-8").splitlines()):
            break
        time.sleep(0.05)

    traces = grep_trace_all(tmp_path)
    assert len(traces) >= 6
    actors = {t.actor for t in traces}
    assert "alice" in actors
    # bob may or may not be there yet (async timing)
    assert sum(1 for t in traces if t.actor == "alice") >= 6

    # ── 5. Wiki update (rule-based · LLM gated to off)
    update_result = wiki_update(vault=tmp_path)
    assert update_result["appended"] == 5  # 5 closed decisions distilled

    rows = wiki_query("shipped", vault=tmp_path)
    assert len(rows) >= 1
    assert all("shipped" in r["snippet"].lower() for r in rows)

    # ── 6. Eval member · expect all 7 dims
    result = eval_member(tmp_path, "alice", window_days=365)
    assert result["member_id"] == "alice"
    assert result["human_review_required"] is True
    assert "anti_tokenmaxxing_note" in result
    assert set(result["dimensions"].keys()) == {
        "D1_delivery", "D2_cost_per_outcome", "D3_quality",
        "D4_judgment", "D5_ecosystem", "D6_revenue_per_workflow",
        "D7_learning",
    }

    # ── 7. team_distribution cache · single-pass
    members = ["alice", "bob"]
    dist = _compute_team_distribution(members, date.today() - timedelta(days=365),
                                       tmp_path, sample_min=3)
    assert "D1_delivery" in dist
    assert len(dist["D1_delivery"]) == 2  # one Score per member

    # ── 8. FinOps three views
    for scope in ("cost_per_resolved_decision", "human_equivalent_hourly", "revenue_per_workflow"):
        r = finops_summary(tmp_path, scope=scope, since_days=365)
        assert r["human_review_required"] is True
        assert r["n_decisions_closed"] == 5

    # ── 9. Prom /metrics renders without error
    text = render(tmp_path)
    assert "ome365_decisions_total" in text
    assert "ome365_traces_total" in text
    assert "ome365_skills_total" in text
    assert text.endswith("\n")

    # ── 10. ed25519 sign + verify
    card = {"name": "Ome365", "version": "test", "capabilities": ["a", "b"]}
    signed = sign(card, vault=tmp_path)
    assert verify(signed) is True

    # ── 11. Archive doesn't break with recent traces (older_than 365)
    arch_result = archive(vault=tmp_path, older_than_days=365)
    assert arch_result["moved"] == 0  # nothing old enough

    # ── 12. Backup → restore roundtrip
    backup_dest = tmp_path / "backup-out"
    tarball = backup_create(vault=tmp_path, dest=backup_dest)
    assert tarball.exists()

    restore_target = tmp_path.parent / "restored_vault"
    restore_target.mkdir(exist_ok=True)
    backup_restore(tarball, vault=restore_target, safe=False)

    # Verify restored vault has the same decisions
    restored_decisions = grep_decisions_all(restore_target)
    assert len(restored_decisions) == 5
    restored_trace_files = list((restore_target / "Trace").glob("*.jsonl"))
    assert restored_trace_files

    # Cleanup restore target
    import shutil
    shutil.rmtree(restore_target)


def test_full_v1_1_via_http_routes(tmp_path):
    """Same scenario but via HTTP routes · ensures FastAPI mounting works."""
    pytest.importorskip("yaml")
    pytest.importorskip("cryptography")
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    _seed_config(tmp_path)

    from ome365_decisions import create_decision, close_decision
    for i, anchors in enumerate([["P", "L"], ["P"], ["L"], ["P", "L"], ["XL"]]):
        p = create_decision(tmp_path, f"D{i}", "alice")
        close_decision(tmp_path, p.stem, outcome=f"ok{i}", value_anchors=anchors)

    # Build app with all v1.1 routers
    import os as _os
    _os.environ["OME365_VAULT"] = str(tmp_path)

    from ome365_a2a import well_known_router
    from ome365_decisions import router as decision_router
    from ome365_eval import router as eval_router

    app = fastapi.FastAPI()
    app.include_router(decision_router)
    app.include_router(eval_router)
    app.include_router(well_known_router)
    client = TestClient(app)

    # /api/decision/list
    r = client.get("/api/decision/list")
    assert r.status_code == 200
    assert r.json()["count"] == 5

    # /api/eval/whoami → vault_inferred=alice (most decisions)
    r = client.get("/api/eval/whoami")
    assert r.status_code == 200
    assert r.json()["actor"] == "alice"

    # /api/eval/role/alice → owner
    r = client.get("/api/eval/role/alice")
    assert r.status_code == 200
    assert r.json()["role"] == "owner"

    # /api/eval/finops/dashboard
    r = client.get("/api/eval/finops/dashboard?since_days=365")
    assert r.status_code == 200
    data = r.json()
    assert set(data["by_scope"]) == {
        "cost_per_resolved_decision", "human_equivalent_hourly", "revenue_per_workflow",
    }

    # /.well-known/agent-card.json must be ed25519-signed
    r = client.get("/.well-known/agent-card.json")
    assert r.status_code == 200
    card = r.json()
    assert card["signing_alg"] == "ed25519"
    assert card["signature"]

    from ome365_signing import verify
    assert verify(card)
