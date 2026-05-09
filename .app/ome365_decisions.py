"""
ome365.decisions · v1.1 W2 · Decisions/<id>.md CRUD + lifecycle
8-step (5 AI + 3 human) + value_anchors + .calibration/ + Karpathy distillation.

Pair docs:
  · docs/strategy/v1.1-team-brain-design.md §3.2.3 (8 步范式 + value_anchors)
  · docs/strategy/v1.1-implementation-spec.md §二 (6 阶段 pipeline)

Status: v1.1 W2 stub · 5 endpoints + .calibration/ helper · LLM 蒸馏 W6 集成
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

# Re-use ome365_eval helpers (frontmatter parser + DecisionRow + grep)
from ome365_eval import (
    DecisionRow,
    _parse_frontmatter,
    grep_decisions_all,
)


# Valid value_anchors (5-08 example-vendor范式 · A4S §3.2.3)
VALID_ANCHORS = {"P", "XL", "L", "M", "维护性", "Revert"}


def _vault_root() -> Path:
    """Resolve vault root from env (matches server.py convention)."""
    import os
    return Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()


def _slugify(title: str) -> str:
    """Title → safe slug for filename."""
    s = title.lower().strip()
    s = re.sub(r"[^\w一-鿿\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s[:60] or "untitled"


def make_decision_id(title: str, when: Optional[date] = None) -> str:
    when = when or date.today()
    return f"{when.isoformat()}-{_slugify(title)}"


def decision_path(vault: Path, decision_id: str) -> Path:
    return vault / "Decisions" / f"{decision_id}.md"


def create_decision(
    vault: Path,
    title: str,
    owner: str,
    *,
    participants: Optional[list[str]] = None,
    planned_duration_days: Optional[int] = None,
    category: Optional[str] = None,
    when: Optional[date] = None,
) -> Path:
    """Create a new Decision file with stub 8 sections · status=open."""
    did = make_decision_id(title, when)
    p = decision_path(vault, did)
    if p.exists():
        raise FileExistsError(f"decision {did} already exists")
    p.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    fm_lines = [
        "---",
        f"id: {did}",
        f"opened: {now}",
        "closed: null",
        "status: open",
        f"owner: {owner}",
        f"participants: [{', '.join(participants or [])}]" if participants else "participants: []",
        "supersedes: null",
        "superseded_by: null",
        "outcome: null",
        "value_anchors: []",
        "roi_estimated: null",
        "roi_actual: null",
    ]
    if planned_duration_days is not None:
        fm_lines.append(f"planned_duration_days: {planned_duration_days}")
    if category:
        fm_lines.append(f"category: {category}")
    fm_lines.append("---")
    body = [
        f"# Decision: {title}",
        "",
        "## ① Problem definition (human)",
        "",
        "## ② Data needs (AI)",
        "",
        "## ③ Models considered (AI)",
        "",
        "## ④ Options (AI)",
        "",
        "## ⑤ Decision (human · leader)",
        "",
        "## ⑥ Reflection (human · leader)",
        "",
        "## ⑦ Execution log (AI · append-only)",
        "",
        "## ⑧ Feedback (AI · 90 day backfill · pending)",
        "",
    ]
    p.write_text("\n".join(fm_lines + [""] + body), encoding="utf-8")
    return p


def close_decision(
    vault: Path,
    decision_id: str,
    *,
    outcome: str,
    value_anchors: list[str],
    roi_estimated: Optional[str] = None,
    hours_saved: Optional[int] = None,
) -> Path:
    """Close an open Decision · update frontmatter."""
    p = decision_path(vault, decision_id)
    if not p.exists():
        raise FileNotFoundError(f"decision {decision_id} not found")
    bad_anchors = [a for a in value_anchors if a not in VALID_ANCHORS]
    if bad_anchors:
        raise ValueError(f"invalid anchors: {bad_anchors} · valid set: {sorted(VALID_ANCHORS)}")

    text = p.read_text("utf-8")
    now = datetime.now(timezone.utc).isoformat()

    def _replace_fm(field: str, new_value: str) -> str:
        nonlocal text
        pat = re.compile(rf"^{re.escape(field)}:.*$", re.MULTILINE)
        if pat.search(text):
            text = pat.sub(f"{field}: {new_value}", text, count=1)
        else:
            text = text.replace("---\n\n# ", f"{field}: {new_value}\n---\n\n# ", 1)
        return text

    _replace_fm("closed", now)
    _replace_fm("status", "closed")
    _replace_fm("outcome", f'"{outcome}"')
    _replace_fm("value_anchors", "[" + ", ".join(value_anchors) + "]")
    if roi_estimated:
        _replace_fm("roi_estimated", f'"{roi_estimated}"')
    if hours_saved is not None:
        if "hours_saved:" in text:
            _replace_fm("hours_saved", str(hours_saved))
        else:
            text = text.replace("---\n\n# ", f"hours_saved: {hours_saved}\n---\n\n# ", 1)

    p.write_text(text, "utf-8")

    owner_match = re.search(r"^owner:\s*(\S+)", text, re.MULTILINE)
    actor = owner_match.group(1) if owner_match else "unknown"

    # P0 #5 · Fire decision.closed webhook (best-effort · never raises)
    try:
        from ome365_notify import notify as _notify
        _notify(
            "decision.closed",
            {
                "id": decision_id,
                "owner": actor,
                "outcome": outcome,
                "value_anchors": value_anchors,
                "roi_estimated": roi_estimated,
            },
            vault=vault,
        )
    except Exception:  # noqa: BLE001
        pass

    # P2 #13 · audit log (best-effort)
    try:
        from ome365_audit import log as _audit
        _audit(
            actor=actor,
            action="decision.close",
            target_type="decision",
            target_id=decision_id,
            details={"outcome": outcome, "value_anchors": value_anchors,
                     "roi_estimated": roi_estimated},
            vault=vault,
        )
    except Exception:  # noqa: BLE001
        pass

    return p


def capture_calibration(
    vault: Path,
    decision_id: str,
    ai_draft: str,
    human_final: str,
) -> Path:
    """Capture (AI draft, human edit, diff) for few-shot distillation training."""
    calib_dir = vault / "Decisions" / ".calibration"
    calib_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    p = calib_dir / f"{decision_id}-feedback-{timestamp}.md"

    import difflib
    import hashlib

    def _hash(s: str) -> str:
        return hashlib.sha256(s.encode()).hexdigest()[:12]

    diff = "\n".join(difflib.unified_diff(
        ai_draft.splitlines(),
        human_final.splitlines(),
        fromfile="ai_draft", tofile="human_final", n=2,
    ))

    p.write_text(
        f"---\n"
        f"decision_id: {decision_id}\n"
        f"captured_at: {datetime.now(timezone.utc).isoformat()}\n"
        f"ai_draft_hash: {_hash(ai_draft)}\n"
        f"human_final_hash: {_hash(human_final)}\n"
        f"---\n\n"
        f"## AI Draft\n\n{ai_draft}\n\n"
        f"## Human Final\n\n{human_final}\n\n"
        f"## Diff\n\n```diff\n{diff}\n```\n",
        "utf-8",
    )
    return p


# ── HTTP router (mounted by .app/server.py) ───────────────────────────────────


router = APIRouter(prefix="/api/decision", tags=["decision"])


class DecisionCreateBody(BaseModel):
    title: str
    owner: str
    participants: list[str] = []
    planned_duration_days: Optional[int] = None
    category: Optional[str] = None


class DecisionCloseBody(BaseModel):
    outcome: str
    value_anchors: list[str]
    roi_estimated: Optional[str] = None
    hours_saved: Optional[int] = None


class CalibrationBody(BaseModel):
    ai_draft: str
    human_final: str


@router.get("/list")
def list_decisions(
    status: Optional[str] = Query(None, pattern="^(open|closed|superseded)$"),
    owner: Optional[str] = None,
):
    vault = _vault_root()
    rows = grep_decisions_all(vault)
    if status:
        rows = [r for r in rows if r.status == status]
    if owner:
        rows = [r for r in rows if r.owner == owner]
    return {
        "decisions": [
            {
                "id": r.id, "owner": r.owner, "status": r.status,
                "outcome": r.outcome, "value_anchors": r.value_anchors,
                "roi_actual": r.roi_actual,
                "closed_at": r.closed_at.isoformat() if r.closed_at else None,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.post("/new")
def post_new(body: DecisionCreateBody):
    try:
        p = create_decision(
            _vault_root(), body.title, body.owner,
            participants=body.participants,
            planned_duration_days=body.planned_duration_days,
            category=body.category,
        )
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    return {"path": str(p), "id": p.stem}


@router.post("/{decision_id}/close")
def post_close(decision_id: str, body: DecisionCloseBody):
    try:
        p = close_decision(
            _vault_root(), decision_id,
            outcome=body.outcome,
            value_anchors=body.value_anchors,
            roi_estimated=body.roi_estimated,
            hours_saved=body.hours_saved,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"path": str(p), "id": decision_id, "status": "closed"}


@router.post("/{decision_id}/calibration")
def post_calibration(decision_id: str, body: CalibrationBody):
    p = capture_calibration(_vault_root(), decision_id, body.ai_draft, body.human_final)
    return {"path": str(p), "decision_id": decision_id}


@router.get("/{decision_id}")
def get_decision(decision_id: str):
    p = decision_path(_vault_root(), decision_id)
    if not p.exists():
        raise HTTPException(404, f"decision {decision_id} not found")
    text = p.read_text("utf-8")
    meta = _parse_frontmatter(text)
    return {"id": decision_id, "frontmatter": meta, "body_chars": len(text)}
