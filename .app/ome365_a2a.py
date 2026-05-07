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
]
