---
id: auth-provider-strategy
opened: 2026-03-17T09:00:00Z
closed: 2026-03-20T17:00:00Z
status: closed
owner: alice
participants: [dan]
supersedes: null
superseded_by: null
outcome: "5-tier abstraction (none / basic / magic_link / oidc / wecom)"
value_anchors:
  - P
  - XL
roi_estimated: "Solo + family + enterprise all served from one binary"
roi_actual: null
planned_duration_days: 3
elapsed_days: 3
category: infra
---

# Decision: AuthProvider · 5 modes for v0.9.6

## ① Problem definition (human · alice)

v0.9.5 only had basic auth. Family wants no auth; enterprise wants OIDC.

## ② Data needs (AI)

Reviewed: similar decisions in vault · industry benchmarks · team capacity ·
input from dan.

## ③ Models considered (AI)

Trade-off framing across 3 dimensions: cost · ship-speed · maintenance.

## ④ Options (AI)

A. 5-tier provider abstraction (one binary, env-config switches)
B. 3 separate builds
C. Single-tier; defer enterprise

## ⑤ Decision (human · alice · leader)

5-tier abstraction · solo skips auth · enterprise picks OIDC · WeChat Work for cn region

Rationale: aligns with v1.1 file-first philosophy · revisit at next quarterly retro.

## ⑥ Reflection (human · leader)

Key insight: simpler than initially feared · the boring choice usually wins.

## ⑦ Execution log (AI · append-only)

- 2026-03-17 · kicked off
- 2026-03-18 · midpoint check
- 2026-03-20 · closed · outcome captured

## ⑧ Feedback (AI · 90 day backfill · pending)

(empty until 90-day distill)
