---
id: cut-feature-realtime-collab
opened: 2026-04-08T09:00:00Z
closed: 2026-04-09T17:00:00Z
status: closed
owner: carol
participants: [alice]
supersedes: null
superseded_by: null
outcome: "Realtime collab cut · async collab via git workflow"
value_anchors:
  - 维护性
  - M
roi_estimated: "Saves 3 weeks · git is good enough for file-first vault"
roi_actual: null
planned_duration_days: 1
elapsed_days: 1
category: product
---

# Decision: Cut realtime collab from v1.1 · defer to v1.3

## ① Problem definition (human · carol)

v1.1 design proposal had realtime co-editing of decision files (Yjs/CRDT). 3-week investment. Conflicts with markdown-as-source-of-truth philosophy.

## ② Data needs (AI)

Reviewed: similar decisions in vault · industry benchmarks · team capacity ·
input from alice.

## ③ Models considered (AI)

Trade-off framing across 3 dimensions: cost · ship-speed · maintenance.

## ④ Options (AI)

A. Cut · async via git
B. Yjs CRDT · 3 weeks
C. Manual lock file

## ⑤ Decision (human · carol · leader)

A · markdown vault is git-friendly · async collab is the feature, not a workaround

Rationale: aligns with v1.1 file-first philosophy · revisit at next quarterly retro.

## ⑥ Reflection (human · leader)

Key insight: simpler than initially feared · the boring choice usually wins.

## ⑦ Execution log (AI · append-only)

- 2026-04-08 · kicked off
- 2026-04-09 · midpoint check
- 2026-04-09 · closed · outcome captured

## ⑧ Feedback (AI · 90 day backfill · pending)

(empty until 90-day distill)
