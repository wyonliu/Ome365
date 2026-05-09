---
id: ci-roadmap-2026q2
opened: 2026-03-08T09:00:00Z
closed: 2026-03-10T17:00:00Z
status: closed
owner: bob
participants: [alice]
supersedes: null
superseded_by: null
outcome: "GitHub Actions · 5 jobs · matrix on macos/ubuntu/wsl"
value_anchors:
  - P
  - M
roi_estimated: "Save 6h/month CI debug time"
roi_actual: null
planned_duration_days: 2
elapsed_days: 2
category: infra
---

# Decision: CI roadmap 2026 Q2 · GitHub Actions vs CircleCI

## ① Problem definition (human · bob)

v1.0 ship needs CI matrix. CircleCI nice but adds vendor; GHA is free + same repo.

## ② Data needs (AI)

Reviewed: similar decisions in vault · industry benchmarks · team capacity ·
input from alice.

## ③ Models considered (AI)

Trade-off framing across 3 dimensions: cost · ship-speed · maintenance.

## ④ Options (AI)

A. GHA matrix + 5 parallel jobs
B. CircleCI orbs (custom pricing)
C. Self-hosted runners (cost too high for OSS)

## ⑤ Decision (human · bob · leader)

GHA · 5 jobs (lint + pytest + pii + docker + integration) · runs on every PR

Rationale: aligns with v1.1 file-first philosophy · revisit at next quarterly retro.

## ⑥ Reflection (human · leader)

Key insight: simpler than initially feared · the boring choice usually wins.

## ⑦ Execution log (AI · append-only)

- 2026-03-08 · kicked off
- 2026-03-09 · midpoint check
- 2026-03-10 · closed · outcome captured

## ⑧ Feedback (AI · 90 day backfill · pending)

(empty until 90-day distill)
