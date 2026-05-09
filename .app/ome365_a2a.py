"""
ome365.a2a · Agent-to-Agent Gateway · 3-tier trust + Federation Registry
v3.6 §九 line 466-496 · V5 真空带 Ome365 侧实现

This module implements the A2A v1.0 server-side gateway:
  - inbound DID verification (delegates to mindos.protocol.a2a · D+5~D+12 integration)
  - 3-tier trust check (T1 Public · T2 Pinned · T3 Internal)
  - Task lifecycle (create → claim → execute → complete/error)
  - Federation Registry (omnity.ai/federation/ opt-in directory)
  - SLA enforcement (3 segments: immediate 5s · near-realtime 1m · async 1h)

Status: v0.1 stub · trust check + lifecycle state machine · no signing crypto yet
        signing/federation discovery pending (D+14~D+45 + ome.protocol.a2a integration)

Reference: <https://a2aproject.github.io/A2A/> v1.0 spec
"""
from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Literal


# ── 3-Tier Trust (v3.6 §九 5.2 line 226-237) ──────────────────────────────────
TrustTier = Literal["T1", "T2", "T3"]

TRUST_TIER_DEFINITIONS = {
    "T1": {
        "label": "Public",
        "trust_level": "any A2A peer",
        "who": "全网开放",
        "can_read": "仅 privacy=public 字段（如 BU 公开列表）",
        "auth_required": "agent-card-only",
    },
    "T2": {
        "label": "Pinned",
        "trust_level": "DID-pinned partners (whitelisted)",
        "who": "whitelisted peer (mutual DID pin · pre-shared)",
        "can_read": "T1 + whitelisted scope（脱敏摘要·如「项目状态」）",
        "auth_required": "agent-card + DID signature + tenant-pin",
    },
    "T3": {
        "label": "Internal",
        "trust_level": "same-tenant BU only",
        "who": "internal BU within same tenant_slug",
        "can_read": "全 vault · 受 RBAC 限",
        "auth_required": "agent-card + tenant-internal session",
    },
}


def check_trust_tier(
    caller_did: str,
    requested_tier: TrustTier,
    tenant_pinlist: Optional[list[str]] = None,
    same_tenant_did: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Decide if a caller (identified by DID) is allowed to read at requested_tier.

    Returns (allowed: bool, reason: str)

    Args:
      caller_did: did:web:... of the calling peer
      requested_tier: T1 / T2 / T3
      tenant_pinlist: list of pinned DIDs (T2 access list) · loaded from registry
      same_tenant_did: this tenant's own DID (used to detect T3 internal calls)
    """
    if requested_tier == "T1":
        # T1 = open to anyone with a valid agent-card
        return True, "T1 public · open"

    if requested_tier == "T2":
        if not tenant_pinlist:
            return False, "T2 denied · no pinlist configured"
        if caller_did not in tenant_pinlist:
            return False, f"T2 denied · {caller_did} not in pinlist"
        return True, f"T2 allowed · pinned"

    if requested_tier == "T3":
        if not same_tenant_did:
            return False, "T3 denied · same_tenant_did not provided"
        # Check caller is within same tenant
        # T3 = same tenant DID prefix (e.g. did:web:omnity.ai:acme-corp:agent:* same tenant as did:web:omnity.ai:acme-corp:*)
        if not caller_did.startswith(same_tenant_did):
            return False, f"T3 denied · {caller_did} not within {same_tenant_did}"
        return True, "T3 allowed · same tenant internal"

    return False, f"unknown tier {requested_tier}"


# ── A2A Task Lifecycle (v3.6 §9.2 line 481) ──────────────────────────────────
TaskState = Literal["created", "claimed", "executing", "completed", "error", "timeout"]

# SLA segments (v3.6 §9.3 line 487-495)
SLA_SECONDS = {
    "immediate": 5,         # synchronous query · timeout → immediate alert
    "near_realtime": 60,    # quasi-realtime · retry 3 + email
    "async": 3600,          # long async task · timeout → admin email
}


@dataclass
class A2ATask:
    """
    A2A task entry. Stored in-memory for v0.1 (move to PG/SQLite for production).

    Lifecycle: created → claimed → executing → completed | error | timeout
    """
    task_id: str
    caller_did: str            # who initiated
    callee_did: str            # who should execute
    capability: str            # e.g. "hike.lookup" · "share.read"
    payload: dict
    sla: Literal["immediate", "near_realtime", "async"] = "near_realtime"
    state: TaskState = "created"
    created_at: float = field(default_factory=time.time)
    claimed_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[dict] = None
    error: Optional[str] = None

    def deadline(self) -> float:
        """When this task should be completed by · for timeout enforcement."""
        return self.created_at + SLA_SECONDS[self.sla]

    def is_overdue(self, now: Optional[float] = None) -> bool:
        if self.state in ("completed", "error", "timeout"):
            return False
        return (now or time.time()) > self.deadline()


def make_task(
    caller_did: str,
    callee_did: str,
    capability: str,
    payload: dict,
    sla: Literal["immediate", "near_realtime", "async"] = "near_realtime",
) -> A2ATask:
    """Construct a new task in `created` state · ready to be persisted by Gateway."""
    return A2ATask(
        task_id=f"a2a-{uuid.uuid4().hex[:16]}",
        caller_did=caller_did,
        callee_did=callee_did,
        capability=capability,
        payload=payload,
        sla=sla,
    )


def transition_task(task: A2ATask, target: TaskState, result: Optional[dict] = None, error: Optional[str] = None) -> bool:
    """
    State machine transition. Returns True if transition is valid.

    Valid transitions:
      created → claimed | error | timeout
      claimed → executing | error | timeout
      executing → completed | error | timeout
      completed → (terminal)
      error → (terminal)
      timeout → (terminal)
    """
    valid_transitions = {
        "created": {"claimed", "error", "timeout"},
        "claimed": {"executing", "error", "timeout"},
        "executing": {"completed", "error", "timeout"},
        "completed": set(),
        "error": set(),
        "timeout": set(),
    }
    if target not in valid_transitions.get(task.state, set()):
        return False

    task.state = target
    now = time.time()
    if target == "claimed":
        task.claimed_at = now
    if target in ("completed", "error", "timeout"):
        task.completed_at = now
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error
    return True


# ── Federation Registry stub (v3.6 §9.2 line 484) ─────────────────────────────
@dataclass
class FederationEntry:
    """A federated tenant in omnity.ai/federation/ directory."""
    tenant_did: str
    tenant_label: str
    contact_email: str
    public_capabilities: list[str]      # T1 features advertised
    trust_signers: list[str] = field(default_factory=list)  # endorsing DIDs (LF / Linux Foundation)
    listed_since: float = field(default_factory=time.time)


class FederationRegistry:
    """
    In-memory federation registry · v0.1 stub.
    Production: backed by signed JSON-LD at omnity.ai/federation/<tenant-slug>.json
    """

    def __init__(self):
        self._entries: dict[str, FederationEntry] = {}

    def register(self, entry: FederationEntry) -> bool:
        """Add a tenant to the federation. Returns True if newly added."""
        if entry.tenant_did in self._entries:
            return False
        self._entries[entry.tenant_did] = entry
        return True

    def lookup(self, tenant_did: str) -> Optional[FederationEntry]:
        return self._entries.get(tenant_did)

    def search(self, capability: str) -> list[FederationEntry]:
        """Find all federated tenants advertising a given capability (T1 only)."""
        return [e for e in self._entries.values() if capability in e.public_capabilities]

    def all(self) -> list[FederationEntry]:
        return list(self._entries.values())


# ── Public API summary ────────────────────────────────────────────────────────
__all__ = [
    "TRUST_TIER_DEFINITIONS",
    "check_trust_tier",
    "SLA_SECONDS",
    "A2ATask",
    "make_task",
    "transition_task",
    "FederationEntry",
    "FederationRegistry",
    "router",
    "well_known_router",
]


# ── HTTP routers (mounted by .app/server.py · v3.6 §九 V5 真空带) ────────────
# Status: v0.1 stub · trust check + lifecycle state machine · NO signing crypto
# Real DID verification + agent-card signing integrate with mindos.protocol.a2a
# in D+5 ~ D+12 · full Federation discovery + 3-tier trust enforcement D+14 ~ D+45
from fastapi import APIRouter, HTTPException

# Process-singleton federation registry (v0.1 in-memory · v1.x backed by signed JSON-LD)
_REGISTRY = FederationRegistry()

# Preview policy (per MASTER-PLAN stub policy A · 2026-05-08):
# All endpoints in this module return mock JSON with _preview=True · real federation in v1.3.
PREVIEW_META = {
    "version": "0.1-stub",
    "_preview": True,
    "_real_in_version": "v1.3",
    "_real_ship_date": "2026-11-01",
}

router = APIRouter(prefix="/api/a2a", tags=["a2a"])


@router.get("/trust/tiers")
def list_trust_tiers():
    """List the 3 trust tiers (T1 Public · T2 Pinned · T3 Internal · v3.6 §5.2 line 226)."""
    return {"tiers": TRUST_TIER_DEFINITIONS, **PREVIEW_META}


@router.post("/trust/check")
def check_trust(payload: dict):
    """Check whether a caller (DID) is allowed at requested tier."""
    caller = payload.get("caller_did", "")
    tier = payload.get("tier", "T1")
    pinlist = payload.get("tenant_pinlist") or None
    same_tenant = payload.get("same_tenant_did") or None
    allowed, reason = check_trust_tier(caller, tier, tenant_pinlist=pinlist, same_tenant_did=same_tenant)
    return {"allowed": allowed, "reason": reason, "tier": tier, **PREVIEW_META}


@router.post("/task/create")
def create_task_endpoint(payload: dict):
    """Create an A2A task (v0.1 stub · returns id + state · NO actual execution)."""
    caller = payload.get("caller_did")
    callee = payload.get("callee_did")
    capability = payload.get("capability")
    sla = payload.get("sla", "near_realtime")
    if not caller or not callee or not capability:
        raise HTTPException(400, "caller_did + callee_did + capability required")
    if sla not in ("immediate", "near_realtime", "async"):
        raise HTTPException(400, "sla must be immediate/near_realtime/async")
    task = make_task(caller, callee, capability, payload.get("payload", {}), sla=sla)
    return {
        "task_id": task.task_id,
        "state": task.state,
        "deadline": task.deadline(),
        "sla_seconds": SLA_SECONDS[sla],
        **PREVIEW_META,
    }


@router.get("/sla")
def get_sla():
    """SLA segments (v3.6 §9.3 line 487)."""
    return {"sla_seconds": SLA_SECONDS, **PREVIEW_META}


@router.get("/federation/list")
def federation_list():
    """List federated tenants (v0.1 in-memory)."""
    return {
        "peers": [
            {
                "tenant_did": e.tenant_did,
                "label": e.tenant_label,
                "capabilities": e.public_capabilities,
            }
            for e in _REGISTRY.all()
        ],
        **PREVIEW_META,
    }


@router.post("/federation/register")
def federation_register(payload: dict):
    """Register a tenant in the federation (v0.1 stub · in-memory)."""
    tenant_did = payload.get("tenant_did", "")
    label = payload.get("tenant_label", "")
    contact = payload.get("contact_email", "")
    caps = payload.get("public_capabilities") or []
    if not tenant_did or not label:
        raise HTTPException(400, "tenant_did + tenant_label required")
    entry = FederationEntry(
        tenant_did=tenant_did,
        tenant_label=label,
        contact_email=contact,
        public_capabilities=list(caps),
    )
    added = _REGISTRY.register(entry)
    return {"added": added, "tenant_did": tenant_did}


# ── /.well-known/agent-card.json (A2A v1.0 well-known endpoint · separate router)
well_known_router = APIRouter(tags=["a2a"])


@well_known_router.get("/.well-known/agent-card.json")
def agent_card_well_known():
    """A2A v1.0 well-known agent card · v1.1.2 ed25519 signed (P3 #17).

    The agent-card itself is real and shipping; the only `_preview` surface is
    the `federation_preview` block (in-memory registry · real federation in v1.3).
    """
    body = {
        "name": "Ome365",
        "version": "1.1",
        "did": "did:web:omnity.ai:default",
        "protocol": "a2a/1.0",
        # Federation features are still preview · gate them under their own block
        "federation_preview": dict(PREVIEW_META),
        "capabilities": [
            "hike.entities",
            "hike.lookup",
            "hike.asr",
            "share.read",
            "memory.recall",
            "identity.whoami",
        ],
        # v1.1 surface · advertised separately for backward-compat with v0.x clients
        "capabilities_v1_1": {
            "decisions": [
                {"name": "decisions.list",   "endpoint": "GET /api/decision/list",         "tier": "T2"},
                {"name": "decisions.get",    "endpoint": "GET /api/decision/{id}",         "tier": "T2"},
                {"name": "decisions.create", "endpoint": "POST /api/decision/new",         "tier": "T2"},
                {"name": "decisions.close",  "endpoint": "POST /api/decision/{id}/close",  "tier": "T2"},
            ],
            "eval": [
                {"name": "eval.member",            "endpoint": "GET /api/eval/member/{actor}",     "tier": "T3"},
                {"name": "eval.finops.scope",      "endpoint": "GET /api/eval/finops/{scope}",     "tier": "T2"},
                {"name": "eval.finops.dashboard",  "endpoint": "GET /api/eval/finops/dashboard",   "tier": "T2"},
                {"name": "eval.skills",            "endpoint": "GET /api/eval/skills",             "tier": "T1"},
            ],
            "wiki": [
                {"name": "wiki.update", "cli": "ome365 wiki update", "tier": "T2"},
                {"name": "wiki.query",  "cli": "ome365 wiki query 'term'", "tier": "T1"},
            ],
            "trace": [
                {"name": "trace.add",     "cli": "ome365 trace add",      "tier": "T2"},
                {"name": "trace.query",   "cli": "ome365 trace query",    "tier": "T2"},
                {"name": "trace.rollup",  "cli": "ome365 trace rollup",   "tier": "T2"},
            ],
            "archive": [
                {"name": "archive.gzip",   "cli": "ome365 archive",        "tier": "T2"},
                {"name": "archive.recall", "cli": "ome365 archive recall", "tier": "T2"},
            ],
        },
        "compliance": {
            "gdpr_art_22": "human_review_required=True on all eval responses",
            "pipl_art_13_24": "cn-region members must sign notice; opt-out always 403",
            "anti_tokenmaxxing": "scores are value/cost ROI · NOT token leaderboards",
        },
        "auth": {
            "supported_methods": ["bearer", "did-pinned", "tenant-internal"],
            "tier": ["T1", "T2", "T3"],
        },
    }
    # P3 #17 · ed25519 sign in-place (requires `cryptography`)
    try:
        from ome365_signing import sign as _sign
        return _sign(body)
    except Exception:
        # Falls back to unsigned if cryptography unavailable
        body["signature"] = None
        body["signing_alg"] = None
        body["signing_status"] = "unavailable · install cryptography>=41"
        return body
