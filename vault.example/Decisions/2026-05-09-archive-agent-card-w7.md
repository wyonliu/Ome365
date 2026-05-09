---
id: 2026-05-09-archive-agent-card-w7
opened: 2026-05-09T07:00:00Z
closed: 2026-05-09T08:30:00Z
status: closed
owner: alice
participants: [bob]
supersedes: null
superseded_by: null
outcome: "ome365.archive · gzip 老 Trace/<date>.jsonl 到 Trace/archive/<YYYY-MM>.jsonl.gz (older-than 阈值) · agent-card.json 加 v1.1 capabilities (decisions/eval/finops/wiki/trace)"
value_anchors:
  - P              # AAIF discovery + Moxt 95/5 范式
  - L              # 触每条 trace
  - 维护性          # adds gzip + archive surface
roi_estimated: "hot path Trace/*.jsonl 减 90%+ · agent-card 暴露 v1.1 surface 给 A2A 客户端"
roi_actual: null
planned_duration_days: 1
elapsed_days: 1
category: infra
hours_saved: 5
---

# Decision: W7 nightly archive + AAIF agent-card v1.1 surface

## ① Problem definition (human · alice)

W3 Trace/*.jsonl is append-only · monthly_rollup writes summary · but old per-day
files never get cleaned. Two upgrades:
1. **Moxt 95%/5% archive**: gzip Trace/<old-date>.jsonl into Trace/archive/<YYYY-MM>.jsonl.gz
   keep last 30 days hot · everything else compressed (typical 5-10x reduction)
2. **AAIF agent-card surface**: existing /.well-known/agent-card.json advertises only
   pre-W2 capabilities (hike/share/memory). v1.1 adds decisions/eval/finops/wiki/trace
   — each must be queryable via the agent-card so external A2A clients can discover.

## ② Data needs (AI)

- Trace/<YYYY-MM-DD>.jsonl files older than `older_than_days` (default 30)
- gzip module (stdlib) · no new deps
- Agent-card v1.1 capability list: decisions.list, decisions.create, eval.member,
  eval.finops.dashboard, eval.skills, wiki.update, wiki.query, trace.add, trace.query

## ③ Models considered (AI)

archive(vault, older_than_days=30) → moves matching files into
Trace/archive/<YYYY-MM>.jsonl.gz · concatenates by month bucket · idempotent (skip if
target exists with header marker)

recall(vault, period=YYYY-MM) → opens archive · returns iterable of trace dicts
(symmetry with grep_trace_all)

## ④ Options (AI)

A. **Per-day .gz** — too many small files
B. **Per-month .gz bucket** ✓ chosen — concatenate all days of month into one .gz
C. **SQLite cold store** — over-engineered for v1.1

## ⑤ Decision (human · alice · leader)

**Choice B**. archive() concatenates month into single .gz · removes source files
on success · adds <!-- archived: <date> --> marker (jsonl-comment-line at top) for
idempotency check.

agent-card.json adds 9 v1.1 capability strings · groups them under
`capabilities_v1_1` to keep backward compat with v0.x clients.

Rationale: hot Trace/ stays small · monthly_rollup summary still works (reads .gz
when needed via recall) · AAIF discovery surface complete.

## ⑥ Reflection (human · alice + bob · leader)

Boring infrastructure → file-first wins again. gzip + jsonl is the boring choice
that beats every fancy DB for a 0-1 personal vault.

agent-card capabilities are *advertisements* not *contracts* — clients must still
respect tier auth. v1.1 just lets discovery work.

## ⑦ Execution log (AI · append-only)

- 2026-05-09T07:00 · `.app/ome365_archive.py` · ~120 行 · archive + recall + cli
- 2026-05-09T07:30 · `ome365_a2a.py` agent-card 加 v1.1 capabilities + per-cap auth
- 2026-05-09T08:00 · `ome365 archive` 接入 launcher · `tests/test_ome365_archive.py` 8 tests
- 2026-05-09T08:30 · 全量回归 247+8=255 tests · pii 0 · push

## ⑧ Feedback (AI · 90 day backfill · pending 2026-08-09)

(empty until 2026-08-09 nightly distill_outcomes)
