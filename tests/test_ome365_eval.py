"""tests/test_ome365_eval.py · v1.1 W1 first iteration · ome365_eval contract tests"""
import json
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_eval import (  # noqa: E402
    EvalDisabledForRegion,
    EvalOptedOut,
    PIPLNotifyRequired,
    Score,
    D1_delivery,
    D2_cost_per_outcome,
    D4_judgment,
    D5_ecosystem,
    D7_learning,
    dashboard_data,
    eval_member,
    finops_summary,
    grep_decisions_all,
    grep_skills_all,
    grep_trace_all,
    load_eval_config,
)


VAULT_EXAMPLE = Path(__file__).resolve().parent.parent / "vault.example"


# ── Vault scanners (against checked-in vault.example) ────────────────────────


def test_grep_decisions_finds_sample():
    decisions = grep_decisions_all(VAULT_EXAMPLE)
    assert len(decisions) >= 1
    d = next((x for x in decisions if x.id == "2026-05-08-pick-llm-backend"), None)
    assert d is not None
    assert d.owner == "alice"
    assert d.status == "closed"
    assert "P" in d.value_anchors
    assert "L" in d.value_anchors


def test_grep_trace_finds_jsonl():
    traces = grep_trace_all(VAULT_EXAMPLE)
    assert len(traces) >= 6  # vault.example/Trace/2026-05-08.jsonl has 6 lines
    actors = {t.actor for t in traces}
    assert "alice" in actors
    assert "bob" in actors
    assert "carol" in actors


def test_grep_skills_finds_three():
    skills = grep_skills_all(VAULT_EXAMPLE)
    names = {s.name for s in skills}
    assert "meeting-summarize" in names
    assert "hike-wiki-update" in names
    assert "hike-wiki-query" in names


# ── Region-aware enforcement (Fix 5) ─────────────────────────────────────────


def _tmp_vault(region: str = "global", **overrides) -> Path:
    """Create a tmp vault with .ome365/eval-config.yml for region tests."""
    d = Path(tempfile.mkdtemp(prefix="omeval_"))
    cfg_dir = d / ".ome365"
    cfg_dir.mkdir(parents=True)
    cfg = {
        "preset": "engineer",
        "weights": {
            "delivery": 0.15, "cost_per_outcome": 0.15, "quality": 0.15,
            "judgment": 0.10, "ecosystem": 0.20,
            "revenue_per_workflow": 0.15, "learning": 0.10,
        },
        "sample_size_min": 5,
        "region": region,
        "value_anchor_weights": {
            "P": 2.0, "XL": 3.0, "L": 2.0, "M": 1.0,
            "维护性": -0.5, "Revert": -2.0,
        },
    }
    cfg.update(overrides)
    (cfg_dir / "eval-config.yml").write_text(
        "\n".join(f"{k}: {v!r}" if not isinstance(v, dict) else f"{k}:\n  " +
                 "\n  ".join(f"{kk}: {vv!r}" for kk, vv in v.items())
                 for k, v in cfg.items())
    )
    return d


def test_eu_region_default_deny():
    """Fix 5 + edge case #3: EU region default 403."""
    pytest.importorskip("yaml")
    vault = _tmp_vault(region="eu")
    with pytest.raises(EvalDisabledForRegion):
        eval_member(vault, "alice")


def test_eu_region_explicit_enable():
    """Fix 5 + edge case #4: EU explicit enable bypasses default-deny."""
    pytest.importorskip("yaml")
    vault = _tmp_vault(region="eu", eval_enabled_eu=True)
    result = eval_member(vault, "alice")
    assert result["region"] == "eu"
    assert result["human_review_required"] is True
    assert "GDPR Art. 22" in result["warning"]


def test_cn_region_pipl_required():
    """Fix 5 + edge case #22: cn region first eval requires PIPL §13 ack."""
    pytest.importorskip("yaml")
    vault = _tmp_vault(region="cn")
    with pytest.raises(PIPLNotifyRequired):
        eval_member(vault, "alice")


def test_cn_region_pipl_acknowledged():
    """cn region · alice signed PIPL · proceeds normally with cn warning."""
    pytest.importorskip("yaml")
    vault = _tmp_vault(
        region="cn",
        pipl_notify_acknowledged_by={"alice": "2026-05-08"},
    )
    result = eval_member(vault, "alice")
    assert result["region"] == "cn"
    assert "个人信息保护法" in result["warning"]


def test_cn_opted_out_member():
    """Fix 5 + edge case #23: opted-out member always 403."""
    pytest.importorskip("yaml")
    vault = _tmp_vault(
        region="cn",
        pipl_notify_acknowledged_by={"alice": "2026-05-08"},
        opted_out_members=["alice"],
    )
    with pytest.raises(EvalOptedOut):
        eval_member(vault, "alice")


def test_global_region_default_open():
    """Fix 5 + edge case #24: global region default open with warning."""
    pytest.importorskip("yaml")
    vault = _tmp_vault(region="global")
    result = eval_member(vault, "alice")
    assert result["region"] == "global"
    assert result["human_review_required"] is True


# ── eval_member integration on vault.example ─────────────────────────────────


def test_eval_member_on_example_vault():
    pytest.importorskip("yaml")
    result = eval_member(VAULT_EXAMPLE, "alice", window_days=365)
    assert result["member_id"] == "alice"
    assert result["human_review_required"] is True
    assert "anti_tokenmaxxing_note" in result
    assert "preset" in result
    assert "dimensions" in result
    # All 7 dims present
    assert set(result["dimensions"].keys()) == {
        "D1_delivery", "D2_cost_per_outcome", "D3_quality",
        "D4_judgment", "D5_ecosystem", "D6_revenue_per_workflow", "D7_learning",
    }


def test_eval_warning_anti_tokenmaxxing_present():
    """Anti-Tokenmaxxing stance must appear in every response."""
    pytest.importorskip("yaml")
    result = eval_member(VAULT_EXAMPLE, "alice", window_days=365)
    assert "value/cost ROI" in result["anti_tokenmaxxing_note"]
    assert "NOT for token leaderboard" in result["anti_tokenmaxxing_note"]


# ── 7 维派生函数 unit tests ──────────────────────────────────────────────────


def test_d1_delivery_insufficient_sample():
    """edge case #1: n<5 returns score=None + reason."""
    s = D1_delivery("alice", date.today() - timedelta(days=365), VAULT_EXAMPLE, sample_min=5)
    # vault.example grows over weekly milestones · count from vault
    n_alice_closed = sum(
        1 for d in grep_decisions_all(VAULT_EXAMPLE)
        if d.owner == "alice" and d.status == "closed"
        and d.closed_at and d.closed_at >= date.today() - timedelta(days=365)
    )
    if n_alice_closed < 5:
        assert s.score is None
        assert s.reason == "insufficient_sample"
        assert s.n == n_alice_closed
    else:
        # Once vault.example exceeds threshold, just sanity-check it returns a real score
        assert s.score is not None and 0 <= s.score <= 5
        assert s.n == n_alice_closed


def test_d2_cost_per_outcome_returns_score(tmp_path):
    """D2: build isolated vault · single decision + traces with value=0 → ROI=0 → score=0."""
    pytest.importorskip("yaml")
    trace_dir = tmp_path / "Trace"
    trace_dir.mkdir()
    import json as _j
    with (trace_dir / "2026-04-15.jsonl").open("w") as f:
        for i in range(6):
            f.write(_j.dumps({"ts": "2026-04-15T10:00:00Z", "actor": "alice",
                              "skill": "x", "cost_usd": 0.01,
                              "output_value_usd": None, "tenant": "default"}) + "\n")
    s = D2_cost_per_outcome("alice", date.today() - timedelta(days=365), tmp_path, sample_min=1)
    assert s.n == 6
    assert s.score == 0  # value=0 → ROI=0 → log10(0+1)=0


def test_d5_ecosystem_anti_self_gaming():
    """edge case #6: D5 must exclude actor=author trace from adopters."""
    # vault.example contains 4 alice-authored skills · adopters from non-alice actors
    s = D5_ecosystem("alice", date.today() - timedelta(days=365), VAULT_EXAMPLE)
    # n = number of skills authored by alice in window
    n_authored = sum(
        1 for sk in grep_skills_all(VAULT_EXAMPLE)
        if sk.author == "alice"
        and (sk.created is None or sk.created >= date.today() - timedelta(days=365))
    )
    assert s.n == n_authored
    # raw must be a non-negative product
    assert s.raw is not None and s.raw >= 0


def test_d7_learning_first_use_in_window():
    """D7: count distinct non-null skills used in window."""
    s = D7_learning("alice", date.today() - timedelta(days=365), VAULT_EXAMPLE)
    # vault.example has alice traces with various skills · just assert at least 3
    assert s.n >= 3


# ── finops_summary three views ───────────────────────────────────────────────


def test_finops_cost_per_resolved_decision():
    r = finops_summary(VAULT_EXAMPLE, scope="cost_per_resolved_decision", since_days=365)
    assert r["scope"] == "cost_per_resolved_decision"
    assert r["unit"] == "USD per closed decision"
    n_closed = sum(
        1 for d in grep_decisions_all(VAULT_EXAMPLE)
        if d.status == "closed"
        and d.closed_at and d.closed_at >= date.today() - timedelta(days=365)
    )
    assert r["n_decisions_closed"] == n_closed
    assert r["human_review_required"] is True


def test_finops_unknown_scope_raises():
    with pytest.raises(ValueError):
        finops_summary(VAULT_EXAMPLE, scope="bogus")


def test_finops_three_scopes_all_work():
    for scope in ("cost_per_resolved_decision", "human_equivalent_hourly", "revenue_per_workflow"):
        r = finops_summary(VAULT_EXAMPLE, scope=scope, since_days=365)
        assert r["human_review_required"] is True
        assert "value" in r


# ── W4 · D4 anchor-based judgment scoring ────────────────────────────────────


def _seed_vault_with_anchors(tmp_path: Path, anchor_lists: list[list[str]]) -> None:
    """Create N closed decisions for actor 'alice' with given anchor sets."""
    decisions_dir = tmp_path / "Decisions"
    decisions_dir.mkdir()
    for i, anchors in enumerate(anchor_lists):
        anchor_yaml = "\n".join(f"  - {a}" for a in anchors) if anchors else " []"
        (decisions_dir / f"d{i}.md").write_text(
            f"---\n"
            f"id: d{i}\n"
            f"opened: 2026-04-01T00:00:00Z\n"
            f"closed: 2026-04-10T00:00:00Z\n"
            f"status: closed\n"
            f"owner: alice\n"
            f"outcome: '"f"shipped"f"'\n"
            f"value_anchors:\n{anchor_yaml}\n"
            f"---\n# d{i}\n",
            "utf-8",
        )


def test_d4_anchor_based_positive_anchors_lift_score(tmp_path):
    pytest.importorskip("yaml")
    # All 5 decisions tagged with strong positives
    _seed_vault_with_anchors(tmp_path, [["P", "L"], ["P"], ["XL"], ["L", "M"], ["P", "L"]])
    s = D4_judgment("alice", date(2026, 1, 1), tmp_path, sample_min=5)
    assert s.score is not None
    assert s.score > 3.5  # strong positive lift
    assert s.n == 5


def test_d4_anchor_based_revert_drags_score(tmp_path):
    pytest.importorskip("yaml")
    # Mix of Revert (very negative) decisions
    _seed_vault_with_anchors(tmp_path, [["Revert"], ["Revert"], ["Revert"], ["Revert"], ["Revert"]])
    s = D4_judgment("alice", date(2026, 1, 1), tmp_path, sample_min=5)
    assert s.score is not None
    assert s.score == 0  # all Revert clipped to 0


def test_d4_falls_back_to_outcome_string_when_no_anchors(tmp_path):
    pytest.importorskip("yaml")
    # 5 decisions with empty anchors but outcome strings
    decisions_dir = tmp_path / "Decisions"
    decisions_dir.mkdir()
    for i, outcome in enumerate(["OK", "OK", "成功", "shipped", "rolled-back"]):
        (decisions_dir / f"d{i}.md").write_text(
            f"---\nid: d{i}\nopened: 2026-04-01T00:00:00Z\nclosed: 2026-04-10T00:00:00Z\n"
            f"status: closed\nowner: alice\noutcome: '"f"{outcome}"f"'\nvalue_anchors: []\n---\n",
            "utf-8",
        )
    s = D4_judgment("alice", date(2026, 1, 1), tmp_path, sample_min=5)
    # 3 of 5 start with ok/success/成功 (case-insensitive)
    assert s.raw == 0.6
    assert s.score == 3.0


# ── W4 · dashboard_data composite ────────────────────────────────────────────


def test_dashboard_data_combines_scopes_and_actors():
    pytest.importorskip("yaml")
    d = dashboard_data(VAULT_EXAMPLE, since_days=365)
    assert d["human_review_required"] is True
    assert set(d["by_scope"].keys()) == {
        "cost_per_resolved_decision", "human_equivalent_hourly", "revenue_per_workflow",
    }
    assert "alice" in d["by_actor"]
    assert d["by_actor"]["alice"]["requests"] >= 4
    assert d["by_actor"]["alice"]["cost_usd"] > 0


def test_dashboard_data_reads_monthly_summaries(tmp_path):
    pytest.importorskip("yaml")
    monthly = tmp_path / "Trace" / "monthly"
    monthly.mkdir(parents=True)
    import json as _json
    (monthly / "2026-04.summary.json").write_text(_json.dumps({
        "period": "2026-04", "totals": {"requests": 10, "cost_usd": 0.5, "value_usd": 1.0},
        "by_actor": {"alice": {"requests": 10, "cost_usd": 0.5, "value_usd": 1.0,
                               "tokens_in": 0, "tokens_out": 0}},
        "by_skill": {}, "by_decision": {}, "generated_at": "2026-04-30T00:00:00Z",
    }))
    d = dashboard_data(tmp_path, since_days=30, months_back=3)
    assert len(d["monthly_trend"]) == 1
    assert d["monthly_trend"][0]["period"] == "2026-04"


# ── W4 · HTTP router (FastAPI) ───────────────────────────────────────────────


def test_eval_router_finops_dashboard_endpoint(monkeypatch):
    pytest.importorskip("yaml")
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from ome365_eval import router

    app = fastapi.FastAPI()
    app.include_router(router)
    monkeypatch.setenv("OME365_VAULT", str(VAULT_EXAMPLE))
    client = TestClient(app)

    r = client.get("/api/eval/finops/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert "by_scope" in data
    assert data["human_review_required"] is True


def test_eval_router_member_endpoint(monkeypatch):
    pytest.importorskip("yaml")
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from ome365_eval import router

    app = fastapi.FastAPI()
    app.include_router(router)
    monkeypatch.setenv("OME365_VAULT", str(VAULT_EXAMPLE))
    client = TestClient(app)

    r = client.get("/api/eval/member/alice?window_days=365")
    assert r.status_code == 200
    data = r.json()
    assert data["member_id"] == "alice"
    assert data["human_review_required"] is True


def test_eval_router_skills_endpoint(monkeypatch):
    pytest.importorskip("yaml")
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from ome365_eval import router

    app = fastapi.FastAPI()
    app.include_router(router)
    monkeypatch.setenv("OME365_VAULT", str(VAULT_EXAMPLE))
    client = TestClient(app)

    r = client.get("/api/eval/skills")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 3
    names = {s["name"] for s in data["skills"]}
    assert "meeting-summarize" in names
