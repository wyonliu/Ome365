"""tests/test_tenant_isolation_fuzz.py · Review-Fix 8.1
100 trials random tenant data · 0 leak invariant · SOC2 Type 1 fuzz
"""
import json
import random
import string
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_eval import (  # noqa: E402
    eval_member,
    finops_summary,
    grep_decisions_all,
    grep_trace_all,
)


def _rand_id(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


def _seed_tenant(root: Path, tenant: str, n_decisions: int = 5,
                 n_traces: int = 8, owner: str = "alice") -> dict:
    """Build a tiny vault with random decisions + traces under root/<tenant>/"""
    vault = root / tenant
    decisions_dir = vault / "Decisions"
    trace_dir = vault / "Trace"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)
    cfg_dir = vault / ".ome365"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "eval-config.yml").write_text(
        "preset: 'engineer'\nregion: 'global'\nsample_size_min: 5\n"
        "weights:\n  delivery: 0.15\n  cost_per_outcome: 0.15\n  quality: 0.15\n"
        "  judgment: 0.10\n  ecosystem: 0.20\n  revenue_per_workflow: 0.15\n  learning: 0.10\n"
        "value_anchor_weights:\n  P: 2.0\n  XL: 3.0\n  L: 2.0\n  M: 1.0\n"
        "  '维护性': -0.5\n  Revert: -2.0\n",
        "utf-8",
    )

    decision_ids = []
    for i in range(n_decisions):
        did = f"{tenant}-d-{_rand_id()}"
        decision_ids.append(did)
        (decisions_dir / f"{did}.md").write_text(
            f"---\nid: {did}\nopened: 2026-04-01T00:00:00Z\nclosed: 2026-04-10T00:00:00Z\n"
            f"status: closed\nowner: {owner}\noutcome: '"f"shipped"f"'\n"
            f"value_anchors:\n  - P\n  - L\n---\n",
            "utf-8",
        )

    trace_path = trace_dir / "2026-04-15.jsonl"
    with trace_path.open("w", encoding="utf-8") as f:
        for i in range(n_traces):
            f.write(json.dumps({
                "ts": "2026-04-15T12:00:00Z", "actor": owner,
                "skill": f"{tenant}-skill-{_rand_id()}",
                "decision_id": random.choice(decision_ids),
                "cost_usd": round(random.uniform(0.001, 0.05), 4),
                "tenant": tenant,
            }) + "\n")
    return {"decision_ids": decision_ids}


@pytest.mark.parametrize("trial", range(100))
def test_tenant_isolation_fuzz_100_trials(trial, tmp_path):
    """Random 2 tenants · 100 trials · tenant A's eval must NOT see tenant B's decisions."""
    pytest.importorskip("yaml")
    random.seed(trial)
    tenant_a = f"a_{trial}_{_rand_id()}"
    tenant_b = f"b_{trial}_{_rand_id()}"
    info_a = _seed_tenant(tmp_path, tenant_a, n_decisions=3, n_traces=5)
    info_b = _seed_tenant(tmp_path, tenant_b, n_decisions=3, n_traces=5)

    vault_a = tmp_path / tenant_a
    vault_b = tmp_path / tenant_b

    # eval_member on A must only see A decisions
    rows_a = grep_decisions_all(vault_a)
    rows_b = grep_decisions_all(vault_b)

    a_ids = {d.id for d in rows_a}
    b_ids = {d.id for d in rows_b}

    # Hard isolation invariant
    assert a_ids == set(info_a["decision_ids"])
    assert b_ids == set(info_b["decision_ids"])
    assert a_ids.isdisjoint(b_ids), f"trial {trial}: leak between {tenant_a} and {tenant_b}"

    # Likewise for traces
    traces_a = grep_trace_all(vault_a)
    traces_b = grep_trace_all(vault_b)
    a_skills = {t.skill for t in traces_a if t.skill}
    b_skills = {t.skill for t in traces_b if t.skill}
    assert a_skills.isdisjoint(b_skills), f"trial {trial}: skill leak"

    # finops_summary on A must only count A's data
    summary_a = finops_summary(vault_a, scope="cost_per_resolved_decision", since_days=365)
    assert summary_a["n_decisions_closed"] == len(info_a["decision_ids"])


def test_tenant_isolation_no_dotdot_traversal(tmp_path):
    """Ensure ../ doesn't escape vault root in scanners."""
    pytest.importorskip("yaml")
    _seed_tenant(tmp_path, "good", n_decisions=2, n_traces=2)
    # Try to inject a sibling tenant via path traversal
    (tmp_path / "secret").mkdir()
    (tmp_path / "secret" / "Decisions").mkdir()
    (tmp_path / "secret" / "Decisions" / "leak.md").write_text(
        "---\nid: secret-leak\nstatus: closed\nowner: eve\n"
        "opened: 2026-04-01T00:00:00Z\nclosed: 2026-04-02T00:00:00Z\n---\n",
        "utf-8",
    )
    rows = grep_decisions_all(tmp_path / "good")
    ids = {d.id for d in rows}
    assert "secret-leak" not in ids
