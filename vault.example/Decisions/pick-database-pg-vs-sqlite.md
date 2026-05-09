---
id: pick-database-pg-vs-sqlite
opened: 2026-02-18T09:00:00Z
closed: 2026-02-23T17:00:00Z
status: closed
owner: alice
participants: [bob, carol]
supersedes: null
superseded_by: null
outcome: "Postgres for v2 multi-tenant · SQLite stays for solo mode"
value_anchors:
  - P
  - L
  - 维护性
roi_estimated: "Multi-tenant unblocked · ~3 day investment"
roi_actual: null
planned_duration_days: 4
elapsed_days: 5
category: infra
---

# Decision: Pick database · PG vs SQLite for v2

## ① Problem definition (human · alice)

Hike v0.1 ships on SQLite. v2 needs RLS + concurrent writes for >5 user tenants. SQLite WAL helps but RLS is PG-only.

## ② Data needs (AI)

Reviewed: similar decisions in vault · industry benchmarks · team capacity ·
input from bob, carol.

## ③ Models considered (AI)

Trade-off framing across 3 dimensions: cost · ship-speed · maintenance.

## ④ Options (AI)

A. PG + RLS (proven, 3-day port)
B. SQLite + app-level tenant filter (ships today, no RLS guarantee)
C. PostgresLite (immature 2026)

## ⑤ Decision (human · alice · leader)

PG via existing dao/__init__.py adapter · keep SQLite for solo mode (zero-config dev)

Rationale: aligns with v1.1 file-first philosophy · revisit at next quarterly retro.

## ⑥ Reflection (human · leader)

Key insight: simpler than initially feared · the boring choice usually wins.

## ⑦ Execution log (AI · append-only)

- 2026-02-18 · kicked off
- 2026-02-20 · midpoint check
- 2026-02-23 · closed · outcome captured

## ⑧ Feedback (AI · 90 day backfill · pending)

(empty until 90-day distill)
