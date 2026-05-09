"""
ome365.eval · v1.1 派生评估 · pure file-system derivation
GDPR Art. 22 + PIPL §13/§24 compliant · all responses include human_review_required=True
FinOps 2026 aligned · D2 cost_per_outcome / D6 revenue_per_workflow

Pair docs:
  · docs/strategy/v1.1-team-brain-design.md (r2.0 final · 设计层)
  · docs/strategy/v1.1-implementation-spec.md (r1.0 · 含完整公式 + 26 edge cases)

Status: v1.1 W1 first iteration · D1 / D2 真实现 · D3-D7 stub · region check 全实现
"""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from math import log10
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None


# ── Errors ────────────────────────────────────────────────────────────────────

class EvalDisabledForRegion(Exception):
    """Region (e.g. EU) requires explicit enablement."""


class PIPLNotifyRequired(Exception):
    """region=cn member must sign PIPL §13 notice before first eval."""


class EvalOptedOut(Exception):
    """Member exercised PIPL §24 right to refuse · permanently 403."""


# ── Score dataclass ───────────────────────────────────────────────────────────

@dataclass
class Score:
    raw: Optional[float] = None
    score: Optional[float] = None
    n: int = 0
    percentile: Optional[float] = None
    reason: Optional[str] = None


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# ── Frontmatter parser (no yaml dep fallback) ────────────────────────────────

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict:
    m = _FM_RE.match(text)
    if not m:
        return {}
    if yaml:
        try:
            return yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            return {}
    out: dict = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_][\w\-]*)\s*:\s*(.*)$", line)
        if mm:
            out[mm.group(1)] = mm.group(2).strip().strip('"').strip("'")
    return out


# ── Vault scanners (grep_decisions / grep_trace / grep_skills) ────────────────

@dataclass
class DecisionRow:
    id: str
    owner: str
    status: str
    closed_at: Optional[date] = None
    opened_at: Optional[date] = None
    outcome: Optional[str] = None
    superseded_by: Optional[str] = None
    value_anchors: list = field(default_factory=list)
    roi_actual: Optional[float] = None
    planned_duration_days: Optional[int] = None
    elapsed_days: Optional[int] = None


def _parse_iso_date(v) -> Optional[date]:
    if not v:
        return None
    # NOTE: isinstance(datetime, date) is True (datetime extends date) · check datetime FIRST
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None


def grep_decisions_all(vault: Path) -> list[DecisionRow]:
    """Return all Decision rows. Caller filters by date/owner/status."""
    out: list[DecisionRow] = []
    decisions_dir = vault / "Decisions"
    if not decisions_dir.exists():
        return out
    for fp in decisions_dir.glob("*.md"):
        try:
            text = fp.read_text("utf-8")
        except OSError:
            continue
        meta = _parse_frontmatter(text)
        if not meta or not meta.get("id"):
            continue
        opened = _parse_iso_date(meta.get("opened"))
        closed = _parse_iso_date(meta.get("closed"))
        elapsed = (
            (closed - opened).days
            if (opened and closed)
            else meta.get("elapsed_days")
        )
        try:
            roi = float(meta.get("roi_actual")) if meta.get("roi_actual") not in (None, "") else None
        except (ValueError, TypeError):
            roi = None
        try:
            planned = int(meta.get("planned_duration_days")) if meta.get("planned_duration_days") else None
        except (ValueError, TypeError):
            planned = None
        out.append(DecisionRow(
            id=str(meta.get("id")),
            owner=str(meta.get("owner", "")),
            status=str(meta.get("status", "open")),
            closed_at=closed,
            opened_at=opened,
            outcome=meta.get("outcome"),
            superseded_by=meta.get("superseded_by") or None,
            value_anchors=meta.get("value_anchors") or [],
            roi_actual=roi,
            planned_duration_days=planned,
            elapsed_days=elapsed,
        ))
    return out


@dataclass
class TraceRow:
    ts: datetime
    actor: str
    skill: Optional[str]
    decision_id: Optional[str]
    cost_usd: float
    output_value_usd: Optional[float]
    tenant: str


def grep_trace_all(vault: Path) -> list[TraceRow]:
    """Return all Trace rows from Trace/*.jsonl (top-level only · monthly is summary)."""
    out: list[TraceRow] = []
    trace_dir = vault / "Trace"
    if not trace_dir.exists():
        return out
    for fp in trace_dir.glob("*.jsonl"):
        try:
            for line in fp.read_text("utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    j = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts_str = j.get("ts", "")
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    continue
                out.append(TraceRow(
                    ts=ts,
                    actor=str(j.get("actor", "")),
                    skill=j.get("skill"),
                    decision_id=j.get("decision_id"),
                    cost_usd=float(j.get("cost_usd", 0)),
                    output_value_usd=j.get("output_value_usd"),
                    tenant=str(j.get("tenant", "")),
                ))
        except OSError:
            continue
    return out


@dataclass
class SkillRow:
    name: str
    author: str
    created: Optional[date] = None


def grep_skills_all(vault: Path) -> list[SkillRow]:
    out: list[SkillRow] = []
    skills_dir = vault / "Skills"
    if not skills_dir.exists():
        return out
    for fp in skills_dir.glob("*.md"):
        try:
            text = fp.read_text("utf-8")
        except OSError:
            continue
        meta = _parse_frontmatter(text)
        if not meta.get("name"):
            continue
        ome = meta.get("ome365") or {}
        if not isinstance(ome, dict):
            ome = {}
        out.append(SkillRow(
            name=str(meta.get("name")),
            author=str(ome.get("author", "")),
            created=_parse_iso_date(ome.get("created")),
        ))
    return out


# ── 7 维派生函数（FinOps 2026 命名）──────────────────────────────────────────

def D1_delivery(actor: str, since: date, vault: Path, sample_min: int = 5) -> Score:
    """按时闭合率 · planned_duration_days vs elapsed_days"""
    closed = [d for d in grep_decisions_all(vault)
              if d.owner == actor and d.status == "closed"
              and d.closed_at and d.closed_at >= since]
    if len(closed) < sample_min:
        return Score(n=len(closed), reason="insufficient_sample")
    on_time = sum(
        1 for d in closed
        if d.elapsed_days is None
        or d.planned_duration_days is None
        or d.elapsed_days <= d.planned_duration_days
    )
    raw = on_time / len(closed)
    return Score(raw=raw, score=_clip(raw * 5, 0, 5), n=len(closed))


def D2_cost_per_outcome(actor: str, since: date, vault: Path, sample_min: int = 5) -> Score:
    """ROI multiple · sum(value)/sum(cost) · log10 scale 0-5"""
    since_dt = datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc)
    traces = [t for t in grep_trace_all(vault)
              if t.actor == actor and t.ts >= since_dt]
    if len(traces) < sample_min:
        return Score(n=len(traces), reason="insufficient_sample")
    cost = sum(t.cost_usd for t in traces)
    value = sum((t.output_value_usd or 0) for t in traces)
    if cost <= 0:
        return Score(n=len(traces), reason="zero_cost")
    raw = value / cost
    score = _clip(log10(raw + 1), 0, 5)
    return Score(raw=raw, score=score, n=len(traces))


def D3_quality(actor: str, since: date, vault: Path, sample_min: int = 5) -> Score:
    """1 - 被 supersede 比率"""
    decisions = [d for d in grep_decisions_all(vault)
                 if d.owner == actor and d.closed_at and d.closed_at >= since]
    if len(decisions) < sample_min:
        return Score(n=len(decisions), reason="insufficient_sample")
    superseded = sum(1 for d in decisions if d.superseded_by)
    raw = 1 - (superseded / len(decisions))
    return Score(raw=raw, score=_clip(raw * 5, 0, 5), n=len(decisions))


def D4_judgment(
    actor: str, since: date, vault: Path,
    sample_min: int = 5,
    anchor_weights: Optional[dict] = None,
) -> Score:
    """
    Judgment quality · weighted score from value_anchors with outcome-string fallback.

    Primary signal (anchor-based · W4):
      score per decision = sum(anchor_weights[a] for a in d.value_anchors)
      Revert (-2.0) and 维护性 (-0.5) drag · P/XL/L/M (+1..+3) lift.
      raw = mean(per-decision score) clipped to 0-5 via (raw + 2) / 5 * 5.

    Secondary signal (W1 fallback):
      If no decision in window has value_anchors, use outcome-string-startswith
      ('ok'/'success'/'成功') as before — preserves W1 contract.
    """
    closed = [d for d in grep_decisions_all(vault)
              if d.owner == actor and d.status == "closed" and d.outcome]
    if len(closed) < sample_min:
        return Score(n=len(closed), reason="insufficient_sample")

    weights = anchor_weights or {
        "P": 2.0, "XL": 3.0, "L": 2.0, "M": 1.0,
        "维护性": -0.5, "Revert": -2.0,
    }
    anchor_decisions = [d for d in closed if d.value_anchors]

    if anchor_decisions:
        per_decision = [
            sum(weights.get(a, 0) for a in d.value_anchors)
            for d in anchor_decisions
        ]
        raw = sum(per_decision) / len(per_decision)
        # raw range ≈ [-2, +3] · normalize to 0-5
        score = _clip((raw + 2) / 5 * 5, 0, 5)
        return Score(raw=raw, score=score, n=len(closed))

    # Fallback to W1 outcome-string heuristic
    ok = sum(
        1 for d in closed
        if d.outcome and d.outcome.lower().startswith(("ok", "success", "成功"))
    )
    raw = ok / len(closed)
    return Score(raw=raw, score=_clip(raw * 5, 0, 5), n=len(closed))


def D5_ecosystem(actor: str, since: date, vault: Path, sample_min: int = 1) -> Score:
    """own skills × distinct adopters · 防自刷"""
    own_skills = [s for s in grep_skills_all(vault)
                  if s.author == actor
                  and (s.created is None or s.created >= since)]
    skill_ids = {s.name for s in own_skills}
    if not skill_ids:
        return Score(raw=0, score=0, n=0)
    since_dt = datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc)
    distinct_adopters = {
        t.actor for t in grep_trace_all(vault)
        if t.skill in skill_ids and t.actor != actor and t.ts >= since_dt
    }
    raw = len(skill_ids) * len(distinct_adopters)
    from math import log2
    score = _clip(log2(raw + 1) - 1, 0, 5)
    return Score(raw=raw, score=score, n=len(skill_ids))


def D6_revenue_per_workflow(
    actor: str, since: date, vault: Path,
    value_anchor_weights: dict, sample_min: int = 3
) -> Score:
    """两阶段：0-90 天用 value_anchors / 90 天后用 roi_actual"""
    decisions = [d for d in grep_decisions_all(vault)
                 if d.owner == actor and d.status == "closed"
                 and d.closed_at and d.closed_at >= since]
    if len(decisions) < sample_min:
        return Score(n=len(decisions), reason="insufficient_sample")
    today = date.today()
    total_usd = 0.0
    anchor_score_sum = 0.0
    anchor_n = 0
    for d in decisions:
        days_since = (today - d.closed_at).days if d.closed_at else 0
        # Review-Fix 8.3: roi_actual=0 means "shipped · no revenue tracked yet" ·
        # treat as null (fall to anchor path)·only positive roi takes USD path
        if days_since >= 90 and d.roi_actual is not None and d.roi_actual > 0:
            total_usd += d.roi_actual
        elif d.value_anchors:
            for a in d.value_anchors:
                anchor_score_sum += value_anchor_weights.get(a, 0)
                anchor_n += 1
    if total_usd > 0:
        return Score(raw=total_usd, score=_clip(log10(total_usd + 1) - 2, 0, 5), n=len(decisions))
    if anchor_n > 0:
        avg_anchor = anchor_score_sum / anchor_n
        return Score(raw=avg_anchor, score=_clip(avg_anchor, 0, 5), n=len(decisions))
    return Score(n=len(decisions), reason="no_roi_data")


def D7_learning(actor: str, since: date, vault: Path) -> Score:
    """本期首次用的 skill 数"""
    since_dt = datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc)
    used_in = {t.skill for t in grep_trace_all(vault)
               if t.actor == actor and t.skill and t.ts >= since_dt}
    used_before = {t.skill for t in grep_trace_all(vault)
                   if t.actor == actor and t.skill and t.ts < since_dt}
    new_skills = used_in - used_before
    raw = len(new_skills)
    return Score(raw=raw, score=_clip(raw, 0, 5), n=len(used_in))


# ── Config loader ─────────────────────────────────────────────────────────────

def load_eval_config(cfg_path: Path) -> dict:
    if not cfg_path.exists():
        return {
            "preset": "mixed",
            "weights": {
                "delivery": 0.15, "cost_per_outcome": 0.15, "quality": 0.15,
                "judgment": 0.10, "ecosystem": 0.20,
                "revenue_per_workflow": 0.15, "learning": 0.10,
            },
            "sample_size_min": 5,
            "region": "global",
            "value_anchor_weights": {
                "P": 2.0, "XL": 3.0, "L": 2.0, "M": 1.0,
                "维护性": -0.5, "Revert": -2.0,
            },
        }
    text = cfg_path.read_text("utf-8")
    if yaml:
        return yaml.safe_load(text) or {}
    raise RuntimeError("PyYAML required for eval-config.yml parsing")


# ── eval_member 入口（GDPR Art. 22 + PIPL §13/§24 enforcement）──────────────

def eval_member(
    tenant_vault: Path,
    member_id: str,
    *,
    window_days: int = 30,
    cfg: Optional[dict] = None,
) -> dict:
    """
    Compute 7-dim eval for a member.
    Returns dict with `human_review_required: True` (GDPR Art. 22 enforcement).

    Args:
      tenant_vault: Path to vault root for tenant
      member_id: actor identifier
      window_days: rolling window
      cfg: eval-config dict (auto-loads from vault/.ome365/eval-config.yml if None)

    Raises:
      EvalDisabledForRegion: EU region without eval_enabled_eu=True
      PIPLNotifyRequired: cn region member without PIPL §13 ack
      EvalOptedOut: member opted out via PIPL §24
    """
    cfg = cfg or load_eval_config(tenant_vault / ".ome365" / "eval-config.yml")
    region = cfg.get("region", "global")

    # Region-aware enforcement
    if region == "eu" and not cfg.get("eval_enabled_eu", False):
        raise EvalDisabledForRegion("EU · GDPR Art. 22 · default-deny · set eval_enabled_eu=True")
    if region == "cn":
        ack = cfg.get("pipl_notify_acknowledged_by") or {}
        if member_id not in ack:
            raise PIPLNotifyRequired(
                f"member {member_id} · PIPL §13 告知未签 · "
                f"see docs/legal/PIPL-NOTIFY-TEMPLATE.zh.md"
            )
        if member_id in (cfg.get("opted_out_members") or []):
            raise EvalOptedOut(f"member {member_id} · PIPL §24 拒绝权已行使")

    weights = cfg.get("weights", {})
    anchor_weights = cfg.get("value_anchor_weights", {})
    sample_min = int(cfg.get("sample_size_min", 5))
    since = date.today() - timedelta(days=window_days)

    dims = {
        "D1_delivery":             D1_delivery(member_id, since, tenant_vault, sample_min),
        "D2_cost_per_outcome":     D2_cost_per_outcome(member_id, since, tenant_vault, sample_min),
        "D3_quality":              D3_quality(member_id, since, tenant_vault, sample_min),
        "D4_judgment":             D4_judgment(member_id, since, tenant_vault, sample_min, anchor_weights),
        "D5_ecosystem":            D5_ecosystem(member_id, since, tenant_vault, sample_min=1),
        "D6_revenue_per_workflow": D6_revenue_per_workflow(member_id, since, tenant_vault, anchor_weights, sample_min=3),
        "D7_learning":             D7_learning(member_id, since, tenant_vault),
    }

    # Weighted total (only valid dims)
    valid = {k: v for k, v in dims.items() if v.score is not None}
    if valid:
        weight_sum = sum(weights.get(k.split("_", 1)[1], 0) for k in valid)
        total = sum(v.score * weights.get(k.split("_", 1)[1], 0) for k, v in valid.items()) / max(weight_sum, 1e-9)
    else:
        total = None

    region_warning = {
        "cn": "评分仅供资源分配参考。依据《个人信息保护法》第 24 条·您有权拒绝针对您的自动化决策。",
        "eu": "GDPR Art. 22 · Eval is for resource allocation hint only · NEVER as sole basis for HR decisions.",
        "us": "Use only for resource allocation hints · do NOT use as sole basis for HR decisions.",
        "global": "Eval is for resource allocation hint only · NEVER as sole basis for HR decisions.",
    }.get(region, "Eval is for resource allocation hint only.")

    return {
        "tenant_vault": str(tenant_vault),
        "member_id": member_id,
        "window_days": window_days,
        "region": region,
        "preset": cfg.get("preset"),
        "dimensions": {k: asdict(v) for k, v in dims.items()},
        "total_score": total,
        "weights_used": weights,
        "human_review_required": True,         # GDPR Art. 22 强制
        "warning": region_warning,
        "anti_tokenmaxxing_note": "Score is value/cost ROI · NOT token usage · NOT for token leaderboard",
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


# ── finops_summary (Cost-per-Outcome 三视图) ──────────────────────────────────

def finops_summary(
    tenant_vault: Path,
    *,
    scope: str = "cost_per_resolved_decision",
    since_days: int = 30,
) -> dict:
    """
    scope ∈ {cost_per_resolved_decision, human_equivalent_hourly, revenue_per_workflow}
    Returns dict with `human_review_required: True`.
    """
    since = date.today() - timedelta(days=since_days)
    since_dt = datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc)
    traces = [t for t in grep_trace_all(tenant_vault) if t.ts >= since_dt]
    decisions_closed = [d for d in grep_decisions_all(tenant_vault)
                        if d.status == "closed" and d.closed_at and d.closed_at >= since]
    cost = sum(t.cost_usd for t in traces)
    if scope == "cost_per_resolved_decision":
        n = len(decisions_closed)
        value = cost / max(n, 1)
        unit = "USD per closed decision"
    elif scope == "human_equivalent_hourly":
        # decision frontmatter may carry hours_saved
        hours = sum((d.elapsed_days or 0) * 8 for d in decisions_closed)  # rough proxy
        value = cost / max(hours, 1e-9)
        unit = "USD per human hour saved"
    elif scope == "revenue_per_workflow":
        total_value = sum(d.roi_actual for d in decisions_closed if d.roi_actual)
        value = total_value / max(len(decisions_closed), 1)
        unit = "USD revenue per workflow"
    else:
        raise ValueError(f"unknown scope: {scope}")
    return {
        "scope": scope,
        "value": value,
        "unit": unit,
        "n_decisions_closed": len(decisions_closed),
        "n_traces": len(traces),
        "since_days": since_days,
        "human_review_required": True,
    }


# ── Team distribution cache (Review-Fix 1 真落地 · 性能边界) ─────────────────


def _compute_team_distribution(
    members: list[str],
    since: date,
    vault: Path,
    *,
    sample_min: int = 5,
    anchor_weights: Optional[dict] = None,
) -> dict[str, list[Score]]:
    """
    Single-pass team distribution. Avoids O(N members × 7 dims) repeated grep.
    Reads vault ONCE → builds dim → list[Score] indexed by member input order.

    Use case: percentile lookup tables for cockpit cards / nightly snapshot job.
    Returns {dim_name: [Score(...) per member in input order]}
    """
    # Single vault scan · cached for the function lifetime
    all_decisions = grep_decisions_all(vault)
    all_traces = grep_trace_all(vault)
    all_skills = grep_skills_all(vault)

    # Index by owner / actor for O(1) lookup per member
    decisions_by_owner: dict[str, list] = defaultdict(list)
    for d in all_decisions:
        decisions_by_owner[d.owner].append(d)

    traces_by_actor: dict[str, list] = defaultdict(list)
    for t in all_traces:
        traces_by_actor[t.actor].append(t)

    skills_by_author: dict[str, list] = defaultdict(list)
    for s in all_skills:
        skills_by_author[s.author].append(s)

    # Pre-build skill_id → adopters set (anti-self-gaming · for D5)
    since_dt = datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc)

    out: dict[str, list[Score]] = {
        "D1_delivery": [],
        "D2_cost_per_outcome": [],
        "D3_quality": [],
        "D4_judgment": [],
        "D5_ecosystem": [],
        "D6_revenue_per_workflow": [],
        "D7_learning": [],
    }

    aw = anchor_weights or {
        "P": 2.0, "XL": 3.0, "L": 2.0, "M": 1.0,
        "维护性": -0.5, "Revert": -2.0,
    }

    for m in members:
        # D1: closed in window with planned vs elapsed
        m_decisions = decisions_by_owner.get(m, [])
        closed = [d for d in m_decisions
                  if d.status == "closed" and d.closed_at and d.closed_at >= since]
        if len(closed) < sample_min:
            out["D1_delivery"].append(Score(n=len(closed), reason="insufficient_sample"))
        else:
            on_time = sum(
                1 for d in closed
                if d.elapsed_days is None or d.planned_duration_days is None
                or d.elapsed_days <= d.planned_duration_days
            )
            raw = on_time / len(closed)
            out["D1_delivery"].append(Score(raw=raw, score=_clip(raw * 5, 0, 5), n=len(closed)))

        # D2: ROI multiple
        m_traces = [t for t in traces_by_actor.get(m, []) if t.ts >= since_dt]
        if len(m_traces) < sample_min:
            out["D2_cost_per_outcome"].append(Score(n=len(m_traces), reason="insufficient_sample"))
        else:
            cost = sum(t.cost_usd for t in m_traces)
            value = sum((t.output_value_usd or 0) for t in m_traces)
            if cost <= 0:
                out["D2_cost_per_outcome"].append(Score(n=len(m_traces), reason="zero_cost"))
            else:
                raw = value / cost
                out["D2_cost_per_outcome"].append(Score(raw=raw, score=_clip(log10(raw + 1), 0, 5), n=len(m_traces)))

        # D3: quality (1 - superseded ratio)
        m_in_window = [d for d in m_decisions if d.closed_at and d.closed_at >= since]
        if len(m_in_window) < sample_min:
            out["D3_quality"].append(Score(n=len(m_in_window), reason="insufficient_sample"))
        else:
            superseded = sum(1 for d in m_in_window if d.superseded_by)
            raw = 1 - (superseded / len(m_in_window))
            out["D3_quality"].append(Score(raw=raw, score=_clip(raw * 5, 0, 5), n=len(m_in_window)))

        # D4: anchor-based judgment
        with_outcome = [d for d in closed if d.outcome]
        if len(with_outcome) < sample_min:
            out["D4_judgment"].append(Score(n=len(with_outcome), reason="insufficient_sample"))
        else:
            anchor_decisions = [d for d in with_outcome if d.value_anchors]
            if anchor_decisions:
                per_d = [sum(aw.get(a, 0) for a in d.value_anchors) for d in anchor_decisions]
                raw = sum(per_d) / len(per_d)
                out["D4_judgment"].append(Score(raw=raw, score=_clip((raw + 2) / 5 * 5, 0, 5), n=len(with_outcome)))
            else:
                ok = sum(1 for d in with_outcome if d.outcome.lower().startswith(("ok", "success", "成功")))
                raw = ok / len(with_outcome)
                out["D4_judgment"].append(Score(raw=raw, score=_clip(raw * 5, 0, 5), n=len(with_outcome)))

        # D5: ecosystem (own × adopters)
        own = [s for s in skills_by_author.get(m, [])
               if s.created is None or s.created >= since]
        skill_names = {s.name for s in own}
        if not skill_names:
            out["D5_ecosystem"].append(Score(raw=0, score=0, n=0))
        else:
            adopters = {t.actor for t in all_traces
                        if t.skill in skill_names and t.actor != m and t.ts >= since_dt}
            raw = len(skill_names) * len(adopters)
            from math import log2
            out["D5_ecosystem"].append(Score(raw=raw, score=_clip(log2(raw + 1) - 1, 0, 5), n=len(skill_names)))

        # D6: revenue (90 day cutover)
        if len(closed) < 3:
            out["D6_revenue_per_workflow"].append(Score(n=len(closed), reason="insufficient_sample"))
        else:
            today_d = date.today()
            total_usd, anchor_sum, anchor_n = 0.0, 0.0, 0
            for d in closed:
                days_since = (today_d - d.closed_at).days if d.closed_at else 0
                if days_since >= 90 and d.roi_actual is not None and d.roi_actual > 0:
                    total_usd += d.roi_actual
                elif d.value_anchors:
                    for a in d.value_anchors:
                        anchor_sum += aw.get(a, 0)
                        anchor_n += 1
            if total_usd > 0:
                out["D6_revenue_per_workflow"].append(Score(raw=total_usd, score=_clip(log10(total_usd + 1) - 2, 0, 5), n=len(closed)))
            elif anchor_n > 0:
                avg = anchor_sum / anchor_n
                out["D6_revenue_per_workflow"].append(Score(raw=avg, score=_clip(avg, 0, 5), n=len(closed)))
            else:
                out["D6_revenue_per_workflow"].append(Score(n=len(closed), reason="no_roi_data"))

        # D7: learning (new skills used)
        used_in = {t.skill for t in m_traces if t.skill}
        used_before = {t.skill for t in traces_by_actor.get(m, []) if t.skill and t.ts < since_dt}
        new_skills = used_in - used_before
        out["D7_learning"].append(Score(raw=len(new_skills), score=_clip(len(new_skills), 0, 5), n=len(used_in)))

    return out


def team_percentile(
    member_id: str,
    members: list[str],
    since: date,
    vault: Path,
    *,
    dim: str = "D2_cost_per_outcome",
    sample_min: int = 5,
) -> Optional[float]:
    """
    Compute percentile of `member_id` within `members` for given `dim` (0-100).
    Single vault scan via _compute_team_distribution. Returns None if member
    not in input or score is None.
    """
    if member_id not in members:
        return None
    dist = _compute_team_distribution(members, since, vault, sample_min=sample_min)
    scores = [s.score for s in dist[dim] if s.score is not None]
    if not scores:
        return None
    my_idx = members.index(member_id)
    my_score = dist[dim][my_idx].score
    if my_score is None:
        return None
    below = sum(1 for s in scores if s < my_score)
    return 100.0 * below / len(scores)


# ── Cost-per-Outcome dashboard (W4) ──────────────────────────────────────────


def dashboard_data(
    tenant_vault: Path,
    *,
    since_days: int = 30,
    months_back: int = 3,
) -> dict:
    """
    Combined Cost-per-Outcome view for cockpit card.
    Reads pre-computed Trace/monthly/<YYYY-MM>.summary.json (W3 rollup) when
    available, plus live finops_summary for the rolling window.

    Returns:
      {
        by_scope: {<scope>: finops_summary_dict},
        monthly_trend: [<summary.json contents>, ...] (newest first),
        by_actor: {actor: {requests, cost_usd, value_usd}} (rolling window),
        since_days, months_back, human_review_required: True
      }
    """
    by_scope = {
        scope: finops_summary(tenant_vault, scope=scope, since_days=since_days)
        for scope in ("cost_per_resolved_decision", "human_equivalent_hourly", "revenue_per_workflow")
    }

    monthly_trend = []
    monthly_dir = tenant_vault / "Trace" / "monthly"
    if monthly_dir.exists():
        files = sorted(monthly_dir.glob("*.summary.json"), reverse=True)[:months_back]
        for fp in files:
            try:
                monthly_trend.append(json.loads(fp.read_text("utf-8")))
            except (OSError, json.JSONDecodeError):
                continue

    since_dt = datetime.combine(date.today() - timedelta(days=since_days),
                                datetime.min.time(), tzinfo=timezone.utc)
    by_actor: dict = defaultdict(lambda: {"requests": 0, "cost_usd": 0.0, "value_usd": 0.0})
    for t in grep_trace_all(tenant_vault):
        if t.ts < since_dt:
            continue
        by_actor[t.actor]["requests"] += 1
        by_actor[t.actor]["cost_usd"] += t.cost_usd
        by_actor[t.actor]["value_usd"] += t.output_value_usd or 0

    return {
        "by_scope": by_scope,
        "monthly_trend": monthly_trend,
        "by_actor": dict(by_actor),
        "since_days": since_days,
        "months_back": months_back,
        "human_review_required": True,
        "anti_tokenmaxxing_note": "Cost-per-Outcome · NOT cost-per-token · resource allocation hint only",
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


# ── HTTP router (mounted by .app/server.py) ──────────────────────────────────


def _vault_root() -> Path:
    """Resolve vault root from env (matches server.py convention)."""
    import os
    return Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()


try:
    from fastapi import APIRouter, HTTPException, Query

    router = APIRouter(prefix="/api/eval", tags=["eval"])

    @router.get("/member/{actor}")
    def http_eval_member(actor: str, window_days: int = Query(30, ge=1, le=365)):
        try:
            return eval_member(_vault_root(), actor, window_days=window_days)
        except EvalDisabledForRegion as e:
            raise HTTPException(403, f"region_disabled: {e}")
        except PIPLNotifyRequired as e:
            raise HTTPException(412, f"pipl_notify_required: {e}")
        except EvalOptedOut as e:
            raise HTTPException(403, f"opted_out: {e}")

    @router.get("/finops/{scope}")
    def http_finops(scope: str, since_days: int = Query(30, ge=1, le=365)):
        if scope == "dashboard":
            return dashboard_data(_vault_root(), since_days=since_days)
        try:
            return finops_summary(_vault_root(), scope=scope, since_days=since_days)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @router.get("/skills")
    def http_skills():
        skills = grep_skills_all(_vault_root())
        return {
            "skills": [
                {"name": s.name, "author": s.author,
                 "created": s.created.isoformat() if s.created else None}
                for s in skills
            ],
            "count": len(skills),
        }

    @router.get("/whoami")
    def http_whoami():
        """P0 #4 · resolve current actor for cockpit auto-select.
        Tries: env OME365_ACTOR · vault/.ome365/whoami · default 'alice'.
        Real auth integration is provided by AuthProvider (v0.9.6) when wired.
        """
        import os
        v = _vault_root()
        # 1. Env var (CI / explicit override)
        actor = os.environ.get("OME365_ACTOR", "").strip()
        if actor:
            return {"actor": actor, "source": "env"}
        # 2. Vault config
        whoami_fp = v / ".ome365" / "whoami"
        if whoami_fp.exists():
            actor = whoami_fp.read_text("utf-8").strip()
            if actor:
                return {"actor": actor, "source": "vault"}
        # 3. List of decision owners (most recent author)
        decisions = grep_decisions_all(v)
        if decisions:
            owners = [d.owner for d in decisions if d.owner]
            from collections import Counter
            most_common = Counter(owners).most_common(1)
            if most_common:
                return {"actor": most_common[0][0], "source": "vault_inferred"}
        return {"actor": "alice", "source": "default"}

    @router.get("/actors")
    def http_actors():
        """List all known actors (decision owners + trace actors + skill authors)."""
        v = _vault_root()
        actors: set[str] = set()
        for d in grep_decisions_all(v):
            if d.owner:
                actors.add(d.owner)
        for t in grep_trace_all(v):
            if t.actor:
                actors.add(t.actor)
        for s in grep_skills_all(v):
            if s.author:
                actors.add(s.author)
        return {"actors": sorted(actors), "count": len(actors)}

except ImportError:
    router = None  # type: ignore


# ── Module exports ────────────────────────────────────────────────────────────

__all__ = [
    "Score",
    "DecisionRow", "TraceRow", "SkillRow",
    "grep_decisions_all", "grep_trace_all", "grep_skills_all",
    "D1_delivery", "D2_cost_per_outcome", "D3_quality",
    "D4_judgment", "D5_ecosystem", "D6_revenue_per_workflow", "D7_learning",
    "load_eval_config",
    "eval_member", "finops_summary", "dashboard_data",
    "_compute_team_distribution", "team_percentile",
    "EvalDisabledForRegion", "PIPLNotifyRequired", "EvalOptedOut",
    "router",
]
