---
id: deploy-stack-choice
opened: 2026-04-19T09:00:00Z
closed: 2026-04-21T17:00:00Z
status: closed
owner: erin
participants: [alice]
supersedes: null
superseded_by: null
outcome: "Compose for v1.x · k8s only when >100 tenants"
value_anchors:
  - 维护性
  - M
roi_estimated: "Avoid premature complexity · save 2 days/week ops time"
roi_actual: null
planned_duration_days: 2
elapsed_days: 2
category: ops
---

# Decision: Deploy stack · Docker Compose vs k8s

## ① Problem definition (human · erin)

Some users asking k8s manifests. Single-binary + Compose is current. k8s adds 6 components for an app that fits on one host.

## ② Data needs (AI)

Reviewed: similar decisions in vault · industry benchmarks · team capacity ·
input from alice.

## ③ Models considered (AI)

Trade-off framing across 3 dimensions: cost · ship-speed · maintenance.

## ④ Options (AI)

A. Compose only · k8s deferred
B. Both · double maintenance
C. k8s only · scale-up but ops burden

## ⑤ Decision (human · erin · leader)

A · Compose covers 95% of deployments · revisit when single host saturates

Rationale: aligns with v1.1 file-first philosophy · revisit at next quarterly retro.

## ⑥ Reflection (human · leader)

Key insight: simpler than initially feared · the boring choice usually wins.

## ⑦ Execution log (AI · append-only)

- 2026-04-19 · kicked off
- 2026-04-20 · midpoint check
- 2026-04-21 · closed · outcome captured

## ⑧ Feedback (AI · 90 day backfill · pending)

(empty until 90-day distill)
