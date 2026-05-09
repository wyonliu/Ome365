---
id: 2026-05-09-eval-w4-d4-and-dashboard
opened: 2026-05-09T01:30:00Z
closed: 2026-05-09T03:00:00Z
status: closed
owner: alice
participants: [bob]
supersedes: null
superseded_by: null
outcome: "D4 anchor-scored (P/XL/L/M positive minus Revert/维护性) · dashboard_data combines 3 scopes + monthly trend + by_actor · HTTP router 5 endpoints"
value_anchors:
  - P              # FinOps dashboard productizes
  - L              # touches every closed decision
  - 维护性          # adds router surface
roi_estimated: "Cost-per-Outcome dashboard fully wired · CIO-shippable"
roi_actual: null
planned_duration_days: 1
elapsed_days: 1
category: infra
hours_saved: 6
---

# Decision: W4 D4 anchor scoring + Eval HTTP router + dashboard_data

## ① Problem definition (human · alice)

W1 shipped D1/D2 fully and D3-D7 as functional but-rough implementations.
W4 must:
1. **Upgrade D4 judgment**: current `outcome.startswith('OK'/'success'/'成功')` is too
   brittle — most decisions don't start with those literal strings, so D4 silently
   returns false-zero. Move signal to `value_anchors` (P/XL/L/M = good · Revert = bad).
2. **Cost-per-Outcome dashboard**: spec calls for a single endpoint returning all 3
   `finops_summary` scopes + monthly trend + per-actor breakdown. Currently each
   scope is one call, no aggregation.
3. **HTTP wiring**: `ome365_eval.py` exposes pure functions but no router. CIO
   demo needs `GET /api/eval/finops/dashboard` to render the cockpit card.

## ② Data needs (AI)

- D4 alternative signals already in vault: `value_anchors: [P, L, 维护性]` per
  closed decision. Revert/维护性 are signed-negative in the anchor weight map.
- Monthly trend: `Trace/monthly/<YYYY-MM>.summary.json` already exists (W3 rollup).
- by_actor breakdown: `monthly.summary.by_actor` already keyed by actor.

## ③ Models considered (AI)

D4 = (positive_anchor_count − revert_count) / total_anchor_count, normalized 0-5.
Backward compat: if no anchors found, fall back to old outcome-string match.

dashboard_data: composite dict
  {
    by_scope: {cost_per_resolved_decision, human_equivalent_hourly, revenue_per_workflow},
    monthly_trend: [{period, totals, by_actor, by_skill}],
    by_actor: {actor: {requests, cost_usd, value_usd}},
    human_review_required: True,
  }

## ④ Options (AI)

A. **Compute dashboard live** every call (re-rolls all jsonl) — simple but slow at scale.
B. **Cache via monthly_rollup** — read pre-computed `Trace/monthly/*.summary.json` ✓ chosen.
C. **SQLite materialized view** — over-engineered for v1.1.

## ⑤ Decision (human · alice · leader)

**Choice B**. Dashboard reads `Trace/monthly/*.summary.json` (W3 already produces
these) and concatenates by period. Live recompute only the current month.

D4 changes:
- Primary: anchor-based ratio (P/XL/L/M = +1 each, Revert = −2, 维护性 = −0.5)
- Secondary: outcome-string fallback (preserves W1 behavior when no anchors)
- Sample threshold unchanged (sample_min default 5)

Rationale: file-first · monthly summaries are the source of truth, dashboard is
just a read-aggregate. D4 anchor-based is reuse of W1 anchor weights — no new
schema needed.

## ⑥ Reflection (human · alice + bob · leader)

Key insight: W3's `monthly_rollup` was designed for this — by_actor + by_skill +
by_decision keys are exactly what the dashboard needs. The "boring" jsonl + summary
pattern is paying off · 0 schema migration in W4.

D4 anchor scoring is a graceful degradation: still works on outcome-string-only
decisions but rewards anchor-tagged ones. No breaking change.

`include_router(eval_router)` mount must be tolerant of missing yaml — wrap the
import like the other routers in server.py.

## ⑦ Execution log (AI · append-only)

- 2026-05-09T01:30 · `.app/ome365_eval.py` D4 重写 + dashboard_data() + APIRouter
- 2026-05-09T02:00 · `.app/server.py` include_router(eval_router) tolerant import
- 2026-05-09T02:30 · `tests/test_ome365_eval.py` +8 tests · D4 anchor / dashboard / router
- 2026-05-09T03:00 · 全量回归 217+8=225 tests green · pii scan 0 hits

## ⑧ Feedback (AI · 90 day backfill · pending 2026-08-09)

(empty until 2026-08-09 nightly distill_outcomes)
