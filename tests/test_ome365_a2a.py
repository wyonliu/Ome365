"""tests/test_ome365_a2a.py · ome365.a2a v0.1 stub contract tests"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_a2a import (  # noqa: E402
    TRUST_TIER_DEFINITIONS,
    check_trust_tier,
    SLA_SECONDS,
    A2ATask,
    make_task,
    transition_task,
    FederationEntry,
    FederationRegistry,
)


# ── 3-tier trust ──────────────────────────────────────────────────────────────

def test_tier_definitions_complete():
    assert set(TRUST_TIER_DEFINITIONS.keys()) == {"T1", "T2", "T3"}


def test_T1_open_to_anyone():
    ok, _ = check_trust_tier("did:web:any.com:foo:agent:bar", "T1")
    assert ok


def test_T2_requires_pinlist():
    ok, _ = check_trust_tier("did:web:partner.com:bob", "T2", tenant_pinlist=[])
    assert not ok
    ok, _ = check_trust_tier(
        "did:web:partner.com:bob", "T2", tenant_pinlist=["did:web:partner.com:bob"]
    )
    assert ok


def test_T2_pinlist_excludes_unknown():
    ok, _ = check_trust_tier(
        "did:web:other.com:eve",
        "T2",
        tenant_pinlist=["did:web:partner.com:bob"],
    )
    assert not ok


def test_T3_same_tenant_only():
    same_tenant = "did:web:omnity.ai:acme-corp"
    ok, _ = check_trust_tier(
        "did:web:omnity.ai:acme-corp:agent:cockpit", "T3", same_tenant_did=same_tenant
    )
    assert ok


def test_T3_rejects_other_tenant():
    same_tenant = "did:web:omnity.ai:acme-corp"
    ok, _ = check_trust_tier(
        "did:web:omnity.ai:other-corp:agent:cockpit",
        "T3",
        same_tenant_did=same_tenant,
    )
    assert not ok


def test_T3_requires_same_tenant_did_param():
    ok, reason = check_trust_tier("did:web:any.com:x:agent:y", "T3")
    assert not ok
    assert "same_tenant_did not provided" in reason


def test_unknown_tier():
    ok, _ = check_trust_tier("did:web:x:y", "T9")
    assert not ok


# ── SLA ───────────────────────────────────────────────────────────────────────

def test_sla_seconds_immediate():
    assert SLA_SECONDS["immediate"] == 5


def test_sla_seconds_near_realtime():
    assert SLA_SECONDS["near_realtime"] == 60


def test_sla_seconds_async():
    assert SLA_SECONDS["async"] == 3600


# ── Task lifecycle ────────────────────────────────────────────────────────────

def test_make_task_default_state():
    t = make_task(
        caller_did="did:web:omnity.ai:acme-corp:agent:cockpit",
        callee_did="did:web:omnity.ai:partner-corp:agent:hike",
        capability="hike.lookup",
        payload={"q": "Alice"},
    )
    assert t.state == "created"
    assert t.task_id.startswith("a2a-")
    assert t.sla == "near_realtime"


def test_task_deadline():
    t = make_task("did:web:x:y", "did:web:a:b", "cap", {}, sla="immediate")
    assert t.deadline() == t.created_at + 5


def test_task_lifecycle_happy_path():
    t = make_task("did:web:x:y", "did:web:a:b", "cap", {})
    assert transition_task(t, "claimed")
    assert t.state == "claimed"
    assert t.claimed_at is not None
    assert transition_task(t, "executing")
    assert transition_task(t, "completed", result={"data": "ok"})
    assert t.state == "completed"
    assert t.result == {"data": "ok"}
    assert t.completed_at is not None


def test_task_invalid_transition_blocked():
    """created → completed (skipping intermediate states) must fail."""
    t = make_task("did:web:x:y", "did:web:a:b", "cap", {})
    assert not transition_task(t, "completed")
    assert t.state == "created"  # unchanged


def test_task_terminal_states_locked():
    t = make_task("did:web:x:y", "did:web:a:b", "cap", {})
    transition_task(t, "claimed")
    transition_task(t, "executing")
    transition_task(t, "completed")
    assert not transition_task(t, "error")
    assert t.state == "completed"  # still


def test_task_error_path():
    t = make_task("did:web:x:y", "did:web:a:b", "cap", {})
    assert transition_task(t, "error", error="callee unreachable")
    assert t.state == "error"
    assert t.error == "callee unreachable"


# ── Federation Registry ──────────────────────────────────────────────────────

def test_registry_register_lookup():
    reg = FederationRegistry()
    e = FederationEntry(
        tenant_did="did:web:omnity.ai:acme-corp",
        tenant_label="Acme Corp",
        contact_email="ops@acme-corp.example.com",
        public_capabilities=["hike.lookup", "share.read"],
    )
    assert reg.register(e)
    assert reg.lookup("did:web:omnity.ai:acme-corp").tenant_label == "Acme Corp"


def test_registry_duplicate_rejected():
    reg = FederationRegistry()
    e = FederationEntry(
        tenant_did="did:web:omnity.ai:dup",
        tenant_label="Dup",
        contact_email="x@x",
        public_capabilities=[],
    )
    reg.register(e)
    assert not reg.register(e)


def test_registry_search_by_capability():
    reg = FederationRegistry()
    reg.register(FederationEntry(
        tenant_did="did:web:omnity.ai:acme-corp",
        tenant_label="A",
        contact_email="x",
        public_capabilities=["hike.lookup"],
    ))
    reg.register(FederationEntry(
        tenant_did="did:web:omnity.ai:bee-corp",
        tenant_label="B",
        contact_email="y",
        public_capabilities=["share.read"],
    ))
    assert len(reg.search("hike.lookup")) == 1
    assert len(reg.search("share.read")) == 1
    assert len(reg.search("nonexistent")) == 0


def test_registry_all():
    reg = FederationRegistry()
    assert reg.all() == []
    reg.register(FederationEntry(
        tenant_did="did:web:omnity.ai:tx", tenant_label="T", contact_email="x", public_capabilities=[]
    ))
    assert len(reg.all()) == 1
