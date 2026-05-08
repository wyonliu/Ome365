"""
ome365.id · Tenant DID + Member ID + Agent DID + Signed Agent Card
v3.6 §六 line 328-374 · V1 真空带 Ome365 侧实现

This module implements W3C DID Core 1.0 + W3C VC Data Model 2.0 patterns for:
  - tenant DID:  did:web:omnity.ai:<tenant-slug>
  - member ID:   tenant:<tenant-slug>/member:<member-slug>
  - agent DID:   did:web:omnity.ai:<tenant-slug>:agent:<agent-name>
  - 4 Skill VC types (a/b/c/d · see §6.2 line 339-348):
      a) personality traits  (signed by ome.id · employee owns · follows on departure)
      b) generic skills      (signed by ome.id · employee owns · follows on departure)
      c) enterprise certs    (signed by ome365.id · employee earns · keeps on departure)
      d) business skills     (signed by ome365.id · enterprise owns · stays on departure)

Status: v0.1 stub · schema + helpers only · no signing crypto yet
        signing/verification pending mindos.protocol integration (D+5~D+12)

Reference: <https://www.w3.org/TR/did-core/> · <https://www.w3.org/TR/vc-data-model-2.0/>
"""
from __future__ import annotations
import json
import re
import time
import uuid
from typing import Optional, Literal


# ── Tenant DID generation ──────────────────────────────────────────────────────
def make_tenant_did(domain: str, tenant_slug: str) -> str:
    """
    did:web:<domain>:<tenant-slug>

    Examples:
      make_tenant_did("omnity.ai", "acme-corp") → "did:web:omnity.ai:acme-corp"
      make_tenant_did("ome365.example.com", "demo") → "did:web:ome365.example.com:demo"
    """
    if not _slug_safe(tenant_slug):
        raise ValueError(f"invalid tenant_slug: {tenant_slug!r} · use a-z0-9-")
    return f"did:web:{domain}:{tenant_slug}"


def make_agent_did(domain: str, tenant_slug: str, agent_name: str) -> str:
    """
    did:web:<domain>:<tenant-slug>:agent:<agent-name>

    Example:
      make_agent_did("omnity.ai", "acme-corp", "cockpit") → "did:web:omnity.ai:acme-corp:agent:cockpit"
    """
    if not _slug_safe(agent_name):
        raise ValueError(f"invalid agent_name: {agent_name!r} · use a-z0-9-")
    return f"did:web:{domain}:{tenant_slug}:agent:{agent_name}"


def make_member_id(tenant_slug: str, member_slug: str) -> str:
    """
    tenant:<tenant-slug>/member:<member-slug>

    Member IDs are NOT W3C DIDs (they're internal scoped identifiers).
    Only the tenant DID + agent DID + employee's personal ome.id need to be DIDs.

    Example:
      make_member_id("acme-corp", "alice") → "tenant:acme-corp/member:alice"
    """
    if not _slug_safe(tenant_slug) or not _slug_safe(member_slug):
        raise ValueError(f"invalid slug")
    return f"tenant:{tenant_slug}/member:{member_slug}"


def parse_did(did: str) -> Optional[dict]:
    """
    Parse a did:web:<domain>:<tenant-slug>[:agent:<agent-name>] into components.

    Returns dict with keys: method · domain · tenant_slug · agent_name (optional)
    Returns None if the input is not a valid did:web Ome365-style DID.
    """
    if not did or not did.startswith("did:web:"):
        return None
    rest = did[len("did:web:"):]
    parts = rest.split(":")
    if len(parts) < 2:
        return None
    domain = parts[0]
    tenant_slug = parts[1]
    if len(parts) == 2:
        return {"method": "web", "domain": domain, "tenant_slug": tenant_slug}
    if len(parts) == 4 and parts[2] == "agent":
        return {"method": "web", "domain": domain, "tenant_slug": tenant_slug, "agent_name": parts[3]}
    return None


# ── 4 Skill VC types schema (v3.6 §6.2 line 339-348) ──────────────────────────
SkillVCType = Literal["a", "b", "c", "d"]

SKILL_VC_DEFINITIONS = {
    "a": {
        "category": "personality_traits",
        "issued_by": "ome.id (self-issued)",
        "owner": "employee",
        "examples": ["BigFive personality traits", "communication style", "catchphrases"],
        "transferable_on_departure": True,
        "rationale": "Personality is intrinsic to the human · always portable",
    },
    "b": {
        "category": "generic_skills",
        "issued_by": "ome.id (self-issued)",
        "owner": "employee",
        "examples": ["writes Python", "understands RAG", "speaks Mandarin", "AWS Solutions Architect cert"],
        "transferable_on_departure": True,
        "rationale": "Skills are the employee's human capital · cannot be revoked by employer",
    },
    "c": {
        "category": "enterprise_certifications",
        "issued_by": "ome365.id (enterprise-issued)",
        "owner": "employee (after issuance)",
        "examples": ["completed Acme AI Bootcamp", "passed Acme InfoSec training Q3-2024"],
        "transferable_on_departure": True,
        "rationale": "Certification is a credential the employee earned · they keep the proof",
    },
    "d": {
        "category": "business_specific_skills",
        "issued_by": "ome365.id (enterprise-issued)",
        "owner": "enterprise",
        "examples": ["uses Acme's TicNote workflow", "approves Acme's expense flow"],
        "transferable_on_departure": False,
        "rationale": "Business-process knowledge is the enterprise's IP · stays with the company",
    },
}


def make_skill_vc(
    vc_type: SkillVCType,
    subject_did: str,
    issuer_did: str,
    skill_name: str,
    issuance_date: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """
    Construct a W3C VC Data Model 2.0-compatible Skill credential.

    Args:
      vc_type: one of "a"/"b"/"c"/"d" (see SKILL_VC_DEFINITIONS)
      subject_did: did:omnity:<personal-slug> (employee's ome.id) or member_id
      issuer_did: ome.id self-DID (for type a/b) OR ome365.id tenant DID (for type c/d)
      skill_name: human-readable skill description
      issuance_date: ISO 8601 timestamp · defaults to now
      metadata: optional dict with additional skill-specific fields

    Returns: VC dict ready to be signed (signing happens in next layer · D+5~D+12)
    """
    if vc_type not in SKILL_VC_DEFINITIONS:
        raise ValueError(f"vc_type must be a/b/c/d · got {vc_type!r}")
    if issuance_date is None:
        issuance_date = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    vc_def = SKILL_VC_DEFINITIONS[vc_type]
    return {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            "https://omnity.ai/contexts/skill-vc/v1",
        ],
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiableCredential", "OmeSkillCredential", f"OmeSkillType{vc_type.upper()}"],
        "issuer": issuer_did,
        "validFrom": issuance_date,
        "credentialSubject": {
            "id": subject_did,
            "skill": {
                "name": skill_name,
                "category": vc_def["category"],
                "type": vc_type,
                "transferable": vc_def["transferable_on_departure"],
                **(metadata or {}),
            },
        },
        # Proof to be added by signing layer (Ed25519 / RSA)
        "_unsigned": True,
    }


# ── Signed Agent Card (v3.6 §九 line 478) ──────────────────────────────────────
def make_agent_card(
    agent_did: str,
    capabilities: list[str],
    auth_methods: list[str],
    signed_by: Optional[str] = None,
) -> dict:
    """
    Build a /.well-known/agent-card.json payload (A2A v1.0 compatible).

    Args:
      agent_did: this agent's DID (did:web:domain:tenant:agent:name)
      capabilities: list of capability tags (e.g. ["hike.lookup", "hike.suggest", "share.read"])
      auth_methods: e.g. ["bearer", "did-pinned", "tenant-internal"]
      signed_by: tenant DID that signs this card (for verification by peers)
    """
    parsed = parse_did(agent_did)
    if not parsed or "agent_name" not in parsed:
        raise ValueError(f"agent_did must be a did:web:...:agent:... · got {agent_did!r}")
    return {
        "did": agent_did,
        "tenant": make_tenant_did(parsed["domain"], parsed["tenant_slug"]),
        "agent_name": parsed["agent_name"],
        "capabilities": list(capabilities),
        "auth": list(auth_methods),
        "signed_by": signed_by or make_tenant_did(parsed["domain"], parsed["tenant_slug"]),
        "version": "0.1",
        "protocol": "a2a/1.0",
        # Signing happens at network layer · this stub returns the unsigned payload
        "_unsigned": True,
    }


# ── Tenant DID rotation SOP (v3.6 §6.3 line 350) ───────────────────────────────
def plan_tenant_did_rotation(old_did: str, new_did: str, grace_days: int = 30) -> dict:
    """
    Returns a structured rotation plan (what to do · in what order · within grace period).

    Triggers: enterprise acquired / split / renamed / brand changed.

    The rotation is NOT executed here · this returns a plan for `audit/erasure` workflows.
    """
    old = parse_did(old_did)
    new = parse_did(new_did)
    if not old or not new:
        raise ValueError("both DIDs must be valid did:web Ome365 format")

    return {
        "rotation_id": f"rot-{uuid.uuid4().hex[:12]}",
        "old_did": old_did,
        "new_did": new_did,
        "grace_period_days": grace_days,
        "steps": [
            {
                "order": 1,
                "action": "publish_new_did",
                "description": f"Publish new tenant DID at /.well-known/did.json (old + new co-exist)",
            },
            {
                "order": 2,
                "action": "resign_agent_cards",
                "description": "Re-sign all agent cards with new tenant DID · keep old signatures valid until grace ends",
            },
            {
                "order": 3,
                "action": "notify_federation_peers",
                "description": "Send rotation notice to all known A2A peers · they update their pin lists",
            },
            {
                "order": 4,
                "action": "log_audit_trail",
                "description": "Record rotation in ome365.audit · timestamp · reason · authorizer",
            },
            {
                "order": 5,
                "action": f"sunset_old_did_after_{grace_days}_days",
                "description": f"After {grace_days}-day grace · stop accepting old DID · purge old cert chain",
            },
        ],
    }


# ── Helpers ────────────────────────────────────────────────────────────────────
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def _slug_safe(s: str) -> bool:
    """tenant/member/agent slug: a-z0-9-, 1-64 chars, no leading/trailing dash."""
    return bool(s and isinstance(s, str) and _SLUG_RE.match(s))


# ── Public API summary ────────────────────────────────────────────────────────
__all__ = [
    "make_tenant_did",
    "make_agent_did",
    "make_member_id",
    "parse_did",
    "SKILL_VC_DEFINITIONS",
    "make_skill_vc",
    "make_agent_card",
    "plan_tenant_did_rotation",
    "router",
]


# ── HTTP router (mounted by .app/server.py · Hike v0.1 stub level) ───────────
# Status: v0.1 stub · returns schema + helpers · NO signing crypto yet
# Real signing (Ed25519/RSA) integrates with mindos.protocol.a2a in D+5 ~ D+12
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/identity", tags=["identity"])


@router.get("/whoami")
def whoami():
    """Return current member identity from session.
    v0.1 stub: returns placeholder · session-aware version pending tenant ctx wiring."""
    return {
        "tenant_did": "did:web:omnity.ai:default",
        "member_id": "tenant:default/member:demo",
        "version": "0.1-stub",
        "signing": "no signing yet · pending mindos.protocol integration",
    }


@router.get("/tenant/{tenant_slug}")
def get_tenant_did_endpoint(tenant_slug: str):
    """Construct a tenant DID for a given slug."""
    try:
        return {"tenant_did": make_tenant_did("omnity.ai", tenant_slug), "version": "0.1-stub"}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/agent/{tenant_slug}/{agent_name}")
def get_agent_did_endpoint(tenant_slug: str, agent_name: str):
    """Construct an agent DID for a given (tenant, agent) pair."""
    try:
        return {"agent_did": make_agent_did("omnity.ai", tenant_slug, agent_name), "version": "0.1-stub"}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/skill-vc/types")
def list_skill_vc_types():
    """List the 4 Skill VC types (a/b/c/d · v3.6 §6.2 line 339-348)."""
    return {"types": SKILL_VC_DEFINITIONS, "version": "0.1-stub"}


@router.post("/skill-vc/issue")
def issue_skill_vc(payload: dict):
    """Issue an unsigned Skill VC (v0.1 stub · signing pending)."""
    vc_type = payload.get("type")
    subject_did = payload.get("subject_did", "did:omnity:demo")
    issuer_did = payload.get("issuer_did", "did:web:omnity.ai:default")
    skill_name = payload.get("skill_name", "")
    if vc_type not in ("a", "b", "c", "d"):
        raise HTTPException(400, "type must be one of a/b/c/d (see /api/identity/skill-vc/types)")
    if not skill_name:
        raise HTTPException(400, "skill_name required")
    try:
        vc = make_skill_vc(vc_type, subject_did, issuer_did, skill_name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"vc": vc, "note": "v0.1 stub · _unsigned=True · signing pending mindos.protocol D+5~D+12"}


@router.post("/rotation/plan")
def plan_rotation_endpoint(payload: dict):
    """Plan a tenant DID rotation (acquisition / split / rename · v3.6 §6.3 line 350)."""
    old = payload.get("old_did", "")
    new = payload.get("new_did", "")
    grace_days = int(payload.get("grace_days", 30))
    try:
        return plan_tenant_did_rotation(old, new, grace_days)
    except ValueError as e:
        raise HTTPException(400, str(e))
