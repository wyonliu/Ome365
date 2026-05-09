---
id: 2026-05-09-trace-sdk-design
opened: 2026-05-09T00:00:00Z
closed: 2026-05-09T01:00:00Z
status: closed
owner: alice
participants: [bob]
supersedes: null
superseded_by: null
outcome: "Python SDK (context manager) + CLI (./ome365 trace add) + monthly rollup nightly · sqlite-vec optional"
value_anchors:
  - P              # Product growth (FinOps actionable)
  - L              # Large scope (every LLM call passes through)
  - 维护性          # Adds sqlite-vec optional dep
roi_estimated: "Cost-per-Outcome dashboard data source · 0→1 capability"
roi_actual: null
planned_duration_days: 1
elapsed_days: 1
category: infra
hours_saved: 4
---

# Decision: Trace SDK design (W3)

## ① Problem definition (human · alice)

We have `Trace/<date>.jsonl` schema (W1 spec) but no SDK to write·no CLI to query·
no monthly rollup. Cost-per-Outcome dashboard (FinOps Fix 4) needs real Trace data.

## ② Data needs (AI)

Looked at: Helicone SDK · Langfuse SDK · OpenTelemetry semantic conventions for LLM.
All use context manager pattern · auto-extract usage · attach metadata.

## ③ Models considered (AI)

Trace SDK + CLI + rollup pattern.

## ④ Options (AI)

A. **Heavy SDK** (mimic Langfuse fully · spans · sub-traces · OTEL export) — too much
B. **Minimal SDK** (`with trace.session(...)` context manager · auto-write jsonl) ✓ chosen
C. **CLI only** (no Python integration · users build their own) — too friction

## ⑤ Decision (human · alice · leader)

**Choice B**. Minimal SDK = `from ome365 import trace; with trace.session(...) as t:`
auto-writes jsonl on exit · plus CLI `./ome365 trace add` for shell integration.

Rationale: matches file-first philosophy · jsonl is the SoT · SDK is just sugar.

## ⑥ Reflection (human · alice + bob · leader)

Key insight: SDK should not own the jsonl format. The schema lives in
`docs/strategy/v1.1-implementation-spec.md` and is also written by hand · CLI · cron.
SDK is one of many writers · all converge on append-only jsonl.

sqlite-vec is gated behind opt-in · because bge-m3 model is 2.27 GB.

## ⑦ Execution log (AI · append-only)

- 2026-05-09T00:30 · `.app/ome365_trace.py` 250 行 · session() ctx mgr + log() + monthly_rollup()
- 2026-05-09T00:45 · `./ome365 trace add/query/rollup` CLI 3 subcommand
- 2026-05-09T01:00 · `tests/test_ome365_trace.py` 15 tests · 全过

## ⑧ Feedback (AI · 90 day backfill · pending 2026-08-09)

(empty until 2026-08-09 nightly distill_outcomes)
