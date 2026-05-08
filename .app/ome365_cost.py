"""
ome365.cost · Cost Cap · per-tenant LLM budget + usage tracking + enforcement
patch r1.0 §六 D-2 · v3.6 §十二 line 612 · 企业必备硬上限

v0.1 stub: in-memory budget store, alert thresholds, policy enum.
Real provider plumbing (anthropic/openai/qwen meter hooks) integrates D+14~D+45.

Endpoints (mounted at /api/cost by .app/server.py):
  GET  /api/cost/budget?tenant=<slug>          — current month budget + remaining
  GET  /api/cost/usage?tenant=<slug>           — token / request / dollar counters
  GET  /api/cost/alerts?tenant=<slug>          — threshold list + last-fired
  POST /api/cost/policy                        — set enforcement (warn/throttle/block)

Status: v0.1 stub · policy state machine + threshold compute · no real meter yet
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field, asdict
from typing import Literal, Optional


# ── Policy enum (v3.6 §十二 line 612) ─────────────────────────────────────────
EnforcePolicy = Literal["warn", "throttle", "block"]

POLICY_DEFINITIONS = {
    "warn": {
        "label": "Warn",
        "behavior": "log + email · request still goes through",
        "use_case": "default · early detection · no user impact",
    },
    "throttle": {
        "label": "Throttle",
        "behavior": "delay non-critical requests · prefer cache · downgrade model",
        "use_case": "spike protection · cost-aware fallback",
    },
    "block": {
        "label": "Block",
        "behavior": "reject new LLM calls with HTTP 429 + budget-exceeded",
        "use_case": "hard cap · billing-month boundary · prepaid",
    },
}

# Default alert thresholds (% of monthly budget)
DEFAULT_THRESHOLDS = [50, 80, 100]


# ── Budget + Usage (v0.1 in-memory · v1.x Postgres-backed) ───────────────────
@dataclass
class TenantBudget:
    tenant_slug: str
    monthly_usd: float = 0.0
    policy: EnforcePolicy = "warn"
    thresholds_pct: list[int] = field(default_factory=lambda: list(DEFAULT_THRESHOLDS))
    fired_thresholds: list[int] = field(default_factory=list)  # already-alerted
    period_start: float = field(default_factory=time.time)


@dataclass
class TenantUsage:
    tenant_slug: str
    tokens_in: int = 0
    tokens_out: int = 0
    requests: int = 0
    dollars_spent: float = 0.0
    last_call_at: Optional[float] = None


# Process-singleton stores (replace with DAO-backed storage in v1.x)
_BUDGETS: dict[str, TenantBudget] = {}
_USAGE: dict[str, TenantUsage] = {}


def _get_or_init_budget(slug: str) -> TenantBudget:
    if slug not in _BUDGETS:
        _BUDGETS[slug] = TenantBudget(tenant_slug=slug)
    return _BUDGETS[slug]


def _get_or_init_usage(slug: str) -> TenantUsage:
    if slug not in _USAGE:
        _USAGE[slug] = TenantUsage(tenant_slug=slug)
    return _USAGE[slug]


def set_budget(slug: str, monthly_usd: float, policy: EnforcePolicy = "warn") -> TenantBudget:
    if monthly_usd < 0:
        raise ValueError("monthly_usd must be >= 0")
    if policy not in ("warn", "throttle", "block"):
        raise ValueError(f"policy must be warn/throttle/block, got {policy!r}")
    b = _get_or_init_budget(slug)
    b.monthly_usd = float(monthly_usd)
    b.policy = policy
    return b


def record_usage(slug: str, tokens_in: int = 0, tokens_out: int = 0, dollars: float = 0.0) -> TenantUsage:
    u = _get_or_init_usage(slug)
    u.tokens_in += int(tokens_in)
    u.tokens_out += int(tokens_out)
    u.dollars_spent += float(dollars)
    u.requests += 1
    u.last_call_at = time.time()
    return u


def compute_pct(slug: str) -> float:
    """Return current spend as % of monthly budget (0..inf)."""
    b = _get_or_init_budget(slug)
    u = _get_or_init_usage(slug)
    if b.monthly_usd <= 0:
        return 0.0
    return round(100.0 * u.dollars_spent / b.monthly_usd, 2)


def check_alerts(slug: str) -> list[dict]:
    """Return alerts that *should* fire now (threshold crossed and not yet fired)."""
    b = _get_or_init_budget(slug)
    pct = compute_pct(slug)
    fresh = []
    for t in b.thresholds_pct:
        if pct >= t and t not in b.fired_thresholds:
            fresh.append({"threshold_pct": t, "current_pct": pct, "policy": b.policy})
            b.fired_thresholds.append(t)
    return fresh


def is_request_allowed(slug: str) -> tuple[bool, str]:
    """Check if a new LLM request is allowed under current policy."""
    b = _get_or_init_budget(slug)
    pct = compute_pct(slug)
    if pct < 100:
        return True, f"under budget · {pct}%"
    if b.policy == "warn":
        return True, f"over budget {pct}% · warn-only · allowed"
    if b.policy == "throttle":
        # Throttle decision left to caller (downgrade model / cache / delay)
        return True, f"over budget {pct}% · throttle · caller should downgrade"
    if b.policy == "block":
        return False, f"over budget {pct}% · block policy · 429"
    return True, "unknown policy · default-allow"


def reset_period(slug: str) -> None:
    """Reset usage + fired thresholds for a new billing month."""
    if slug in _USAGE:
        _USAGE[slug] = TenantUsage(tenant_slug=slug)
    if slug in _BUDGETS:
        _BUDGETS[slug].fired_thresholds = []
        _BUDGETS[slug].period_start = time.time()


# ── HTTP router (mounted by .app/server.py) ───────────────────────────────────
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/cost", tags=["cost"])


@router.get("/budget")
def get_budget(tenant: str = "default"):
    b = _get_or_init_budget(tenant)
    pct = compute_pct(tenant)
    return {
        "tenant": tenant,
        "monthly_usd": b.monthly_usd,
        "policy": b.policy,
        "thresholds_pct": b.thresholds_pct,
        "current_pct": pct,
        "remaining_usd": max(0.0, b.monthly_usd - _get_or_init_usage(tenant).dollars_spent),
        "period_start": b.period_start,
        "version": "0.1-stub",
    }


@router.post("/budget")
def post_budget(payload: dict):
    tenant = payload.get("tenant", "default")
    monthly_usd = payload.get("monthly_usd")
    policy = payload.get("policy", "warn")
    if monthly_usd is None:
        raise HTTPException(400, "monthly_usd required")
    try:
        b = set_budget(tenant, float(monthly_usd), policy)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"tenant": tenant, "monthly_usd": b.monthly_usd, "policy": b.policy, "version": "0.1-stub"}


@router.get("/usage")
def get_usage(tenant: str = "default"):
    u = _get_or_init_usage(tenant)
    return {
        "tenant": tenant,
        "tokens_in": u.tokens_in,
        "tokens_out": u.tokens_out,
        "requests": u.requests,
        "dollars_spent": u.dollars_spent,
        "last_call_at": u.last_call_at,
        "current_pct": compute_pct(tenant),
        "version": "0.1-stub",
    }


@router.get("/alerts")
def get_alerts(tenant: str = "default"):
    b = _get_or_init_budget(tenant)
    return {
        "tenant": tenant,
        "thresholds_pct": b.thresholds_pct,
        "fired_thresholds": b.fired_thresholds,
        "current_pct": compute_pct(tenant),
        "version": "0.1-stub",
    }


@router.post("/policy")
def post_policy(payload: dict):
    tenant = payload.get("tenant", "default")
    policy = payload.get("policy")
    if policy not in ("warn", "throttle", "block"):
        raise HTTPException(400, "policy must be warn/throttle/block")
    b = _get_or_init_budget(tenant)
    b.policy = policy
    return {
        "tenant": tenant,
        "policy": b.policy,
        "definitions": POLICY_DEFINITIONS,
        "version": "0.1-stub",
    }


@router.get("/policy/definitions")
def get_policy_definitions():
    """Reference: 3 enforcement policies + when to use each."""
    return {"policies": POLICY_DEFINITIONS, "version": "0.1-stub"}
