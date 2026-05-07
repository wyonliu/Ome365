"""tests/test_ome365_id.py · ome365.id v0.1 stub contract tests"""
import sys
from pathlib import Path
import pytest

# Ensure .app/ on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from ome365_id import (  # noqa: E402
    make_tenant_did,
    make_agent_did,
    make_member_id,
    parse_did,
    SKILL_VC_DEFINITIONS,
    make_skill_vc,
    make_agent_card,
    plan_tenant_did_rotation,
)


# ── DID generation ────────────────────────────────────────────────────────────

def test_tenant_did():
    assert make_tenant_did("omnity.ai", "acme-corp") == "did:web:omnity.ai:acme-corp"


def test_agent_did():
    assert make_agent_did("omnity.ai", "acme-corp", "cockpit") == "did:web:omnity.ai:acme-corp:agent:cockpit"


def test_member_id():
    assert make_member_id("acme-corp", "alice") == "tenant:acme-corp/member:alice"


def test_invalid_slug_rejected():
    with pytest.raises(ValueError):
        make_tenant_did("omnity.ai", "BAD UPPER")
    with pytest.raises(ValueError):
        make_tenant_did("omnity.ai", "with space")
    with pytest.raises(ValueError):
        make_agent_did("omnity.ai", "ok-slug", "BAD-Agent_NAME")


def test_parse_did_tenant():
    p = parse_did("did:web:omnity.ai:acme-corp")
    assert p == {"method": "web", "domain": "omnity.ai", "tenant_slug": "acme-corp"}


def test_parse_did_agent():
    p = parse_did("did:web:omnity.ai:acme-corp:agent:cockpit")
    assert p == {"method": "web", "domain": "omnity.ai", "tenant_slug": "acme-corp", "agent_name": "cockpit"}


def test_parse_did_invalid():
    assert parse_did("not-a-did") is None
    assert parse_did("") is None
    assert parse_did(None) is None
    assert parse_did("did:web:") is None


# ── 4 Skill VC types ──────────────────────────────────────────────────────────

def test_skill_vc_definitions_complete():
    assert set(SKILL_VC_DEFINITIONS.keys()) == {"a", "b", "c", "d"}


def test_skill_vc_a_transferable():
    """Type a (personality) follows employee on departure."""
    assert SKILL_VC_DEFINITIONS["a"]["transferable_on_departure"] is True


def test_skill_vc_b_transferable():
    """Type b (generic skills) follows employee on departure."""
    assert SKILL_VC_DEFINITIONS["b"]["transferable_on_departure"] is True


def test_skill_vc_c_transferable():
    """Type c (enterprise certs) follows employee on departure."""
    assert SKILL_VC_DEFINITIONS["c"]["transferable_on_departure"] is True


def test_skill_vc_d_NOT_transferable():
    """Type d (business skills) stays with enterprise on departure."""
    assert SKILL_VC_DEFINITIONS["d"]["transferable_on_departure"] is False


def test_make_skill_vc_type_a():
    vc = make_skill_vc("a", "did:omnity:alice", "did:omnity:alice", "curious learner")
    assert vc["type"][2] == "OmeSkillTypeA"
    assert vc["credentialSubject"]["skill"]["transferable"] is True
    assert vc["credentialSubject"]["skill"]["category"] == "personality_traits"
    assert vc["_unsigned"] is True


def test_make_skill_vc_type_d():
    tenant_did = make_tenant_did("omnity.ai", "acme-corp")
    member = make_member_id("acme-corp", "bob")
    vc = make_skill_vc("d", member, tenant_did, "Acme TicNote workflow approver")
    assert vc["type"][2] == "OmeSkillTypeD"
    assert vc["credentialSubject"]["skill"]["transferable"] is False
    assert vc["credentialSubject"]["skill"]["category"] == "business_specific_skills"


def test_make_skill_vc_invalid_type():
    with pytest.raises(ValueError):
        make_skill_vc("x", "did:omnity:eve", "did:omnity:eve", "fake")


def test_make_skill_vc_w3c_context():
    vc = make_skill_vc("b", "did:omnity:carol", "did:omnity:carol", "writes Python")
    assert "https://www.w3.org/ns/credentials/v2" in vc["@context"]
    assert "VerifiableCredential" in vc["type"]


# ── Signed Agent Card ─────────────────────────────────────────────────────────

def test_make_agent_card_basic():
    agent = make_agent_did("omnity.ai", "acme-corp", "cockpit")
    card = make_agent_card(agent, ["hike.lookup", "hike.suggest"], ["bearer", "did-pinned"])
    assert card["did"] == agent
    assert card["tenant"] == "did:web:omnity.ai:acme-corp"
    assert card["agent_name"] == "cockpit"
    assert "hike.lookup" in card["capabilities"]
    assert card["protocol"] == "a2a/1.0"
    assert card["_unsigned"] is True


def test_agent_card_rejects_non_agent_did():
    with pytest.raises(ValueError):
        make_agent_card("did:web:omnity.ai:acme-corp", ["x"], ["y"])  # tenant DID, not agent


# ── Tenant DID rotation SOP ──────────────────────────────────────────────────

def test_rotation_plan_5_steps():
    old = make_tenant_did("omnity.ai", "acme-corp")
    new = make_tenant_did("omnity.ai", "acme-renamed")
    plan = plan_tenant_did_rotation(old, new, grace_days=30)
    assert plan["grace_period_days"] == 30
    assert len(plan["steps"]) == 5
    actions = [s["action"] for s in plan["steps"]]
    assert "publish_new_did" in actions
    assert "resign_agent_cards" in actions
    assert "notify_federation_peers" in actions
    assert "log_audit_trail" in actions


def test_rotation_plan_invalid_did():
    with pytest.raises(ValueError):
        plan_tenant_did_rotation("not-a-did", "did:web:omnity.ai:x")
