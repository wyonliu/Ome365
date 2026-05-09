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


# ── W7 · agent-card v1.1 capability surface ──────────────────────────────────


def test_agent_card_advertises_v1_1_capabilities():
    """W7 · /.well-known/agent-card.json must list decisions/eval/wiki/trace/archive."""
    from ome365_a2a import agent_card_well_known
    card = agent_card_well_known()
    assert "capabilities_v1_1" in card
    v11 = card["capabilities_v1_1"]
    for group in ("decisions", "eval", "wiki", "trace", "archive"):
        assert group in v11, f"missing capability group: {group}"
    # Each capability has name + tier
    for group, caps in v11.items():
        for c in caps:
            assert "name" in c
            assert "tier" in c and c["tier"] in {"T1", "T2", "T3"}


def test_agent_card_compliance_block():
    """W7 · agent-card must surface compliance posture."""
    from ome365_a2a import agent_card_well_known
    card = agent_card_well_known()
    assert "compliance" in card
    comp = card["compliance"]
    assert "gdpr_art_22" in comp
    assert "pipl_art_13_24" in comp
    assert "anti_tokenmaxxing" in comp


# ── v1.1.36 · card.version reflects v1.1, federation preview is segregated ──


def test_agent_card_top_level_version_is_1_1():
    """v1.1.36 fix: previous code splatted PREVIEW_META so card claimed
    version=0.1-stub even though v1.1 is shipping. Now version=1.1 at top level."""
    from ome365_a2a import agent_card_well_known
    card = agent_card_well_known()
    assert card["version"].startswith("1.1"), \
        f"top-level version should be 1.1.x, got {card['version']!r}"
    # Top-level _preview flag should NOT be true (this is a real card)
    assert card.get("_preview") is not True


def test_agent_card_federation_preview_segregated():
    """The preview flag belongs in `federation_preview`, not at the card root."""
    from ome365_a2a import agent_card_well_known
    card = agent_card_well_known()
    fp = card.get("federation_preview", {})
    assert fp.get("_preview") is True
    assert fp.get("_real_in_version") == "v1.3"


# ── v1.1.38 · agent-card advertised endpoints must really exist ─────────────


def _normalize_path(path: str) -> str:
    """Replace any {...} segment with the literal {} so path templates with
    different parameter names ({id} vs {decision_id}) compare equal."""
    import re
    return re.sub(r"\{[^}]+\}", "{}", path)


def _registered_route_set():
    """Set of (method, normalized_path) tuples for v1.1 routers + known
    top-level routes mounted directly on the FastAPI app in server.py."""
    from ome365_decisions import router as dec_router
    from ome365_eval import router as eval_router
    out = set()
    for r in list(dec_router.routes) + list(eval_router.routes):
        if hasattr(r, "methods") and r.methods:
            for m in r.methods:
                if m in ("HEAD",):
                    continue
                out.add((m, _normalize_path(r.path)))
    # Known top-level routes (defined directly on FastAPI app in server.py · not
    # on a sub-router). Keep this list small and explicit; if it grows, refactor
    # to import server.py app or split into routers.
    out.update({
        ("GET", "/metrics"),
        ("GET", "/.well-known/agent-card.json"),
    })
    return out


def test_agent_card_advertised_http_endpoints_exist():
    """Every HTTP endpoint in capabilities_v1_1 must be registered.

    Catches the "advertised but not implemented" drift that would mislead
    A2A clients. Also catches the inverse — capabilities frozen while
    the route was renamed under the table.
    """
    from ome365_a2a import agent_card_well_known
    registered = _registered_route_set()

    card = agent_card_well_known()
    advertised = []
    for group, items in card.get("capabilities_v1_1", {}).items():
        for c in items:
            ep = c.get("endpoint")
            if not ep:
                continue
            method, _, path = ep.partition(" ")
            advertised.append((c["name"], method, path))

    missing = []
    for name, method, path in advertised:
        norm = _normalize_path(path)
        if (method, norm) not in registered:
            # Check if this is a {scope}-style sub-value (e.g. "dashboard")
            # matched by a parameterized parent route
            parent = norm.rsplit("/", 1)[0] + "/{}"
            if (method, parent) not in registered:
                missing.append(f"{name}: {method} {path}")

    assert not missing, f"agent-card advertises non-existent endpoints: {missing}"


def test_agent_card_advertised_cli_modules_loadable():
    """Every CLI listed in capabilities_v1_1 must point to a loadable module."""
    from ome365_a2a import agent_card_well_known
    card = agent_card_well_known()
    cli_to_module = {
        "ome365 wiki": "ome365_wiki",
        "ome365 trace": "ome365_trace",
        "ome365 archive": "ome365_archive",
    }
    missing = []
    for group, items in card.get("capabilities_v1_1", {}).items():
        for c in items:
            cli = c.get("cli")
            if not cli:
                continue
            # First two tokens identify the module
            head = " ".join(cli.split()[:2])
            mod_name = cli_to_module.get(head)
            if mod_name is None:
                continue
            try:
                __import__(mod_name)
                # Must have cli_main
                mod = sys.modules[mod_name]
                if not hasattr(mod, "cli_main"):
                    missing.append(f"{c['name']}: {mod_name} has no cli_main")
            except Exception as e:
                missing.append(f"{c['name']}: cannot import {mod_name}: {e}")
    assert not missing, missing
