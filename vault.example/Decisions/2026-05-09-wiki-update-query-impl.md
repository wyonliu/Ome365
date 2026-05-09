---
id: 2026-05-09-wiki-update-query-impl
opened: 2026-05-09T05:00:00Z
closed: 2026-05-09T07:00:00Z
status: closed
owner: alice
participants: [bob]
supersedes: null
superseded_by: null
outcome: "ome365.wiki module · scan(rule-based extract from Decisions/Notes) + query(grep over Knowledge/L2-distilled) · CLI ./ome365 wiki update|query · ship pure-stdlib first, semantic via sqlite-vec opt-in"
value_anchors:
  - P              # Hike L4 maintainer Wiki concept productized
  - L              # whole vault becomes the corpus
  - 维护性          # adds wiki module surface
roi_estimated: "Karpathy wiki-as-artifact 真落地·一行 CLI 蒸馏"
roi_actual: null
planned_duration_days: 1
elapsed_days: 1
category: infra
hours_saved: 6
---

# Decision: W6 wiki-update + wiki-query implementation

## ① Problem definition (human · alice)

W1 shipped `Skills/hike-wiki-update.md` and `hike-wiki-query.md` as SKILL.md
spec descriptors but with no Python implementation. Karpathy's "wiki is the
artifact, not the chat" pattern needs:
1. **Maintainer** that scans Decisions/Notes/* and appends `## Pattern · <topic> ·
   <date>` blocks to `Knowledge/L2-distilled/<topic>.md`
2. **Reader** that greps the L2 distilled files for a query
3. **Idempotency** · re-running `wiki update` on unchanged input produces no diff

## ② Data needs (AI)

- Source: `vault/Decisions/*.md` (frontmatter has category + outcome + value_anchors)
- Source: `vault/Notes/*.md` (free-form)
- Sink: `vault/Knowledge/L2-distilled/<category>.md` (one per category)
- Sink lock: each pattern block keys on (decision_id or sha) for dedup

## ③ Models considered (AI)

Pure rule-based v1.1: extract pattern from Decision frontmatter
  · category → topic file
  · outcome + value_anchors → claim
  · id → dedup key

LLM-distilled v1.2: re-summarize body into 5-10 claims (gated behind `OME365_WIKI_LLM=1`)

Semantic search v1.2+: sqlite-vec opt-in (already lazy in W3 design)

## ④ Options (AI)

A. **Rule-based first** ✓ chosen — stdlib only, 0 deps, fully testable
B. **LLM-distilled** — needs API keys, can't run in CI, deferred to v1.2
C. **Vector DB** — adds 2.27GB bge-m3 model, opt-in only

## ⑤ Decision (human · alice · leader)

**Choice A**. v1.1 W6 ships rule-based extractor:
- `wiki_update(vault, source="Decisions")` walks Decisions/, groups by category,
  appends `## Pattern · <id> · <date>` blocks to `Knowledge/L2-distilled/<cat>.md`
- `wiki_query(vault, q)` greps L2 distilled files, returns matched blocks with
  source path + line number
- CLI `./ome365 wiki update [--source S]` and `./ome365 wiki query "term"`
- Idempotent: pattern blocks tagged with `<!-- key: <decision_id> -->` and
  re-runs check for the marker before appending

Rationale: matches v1.1 file-first · no infra · no API keys · CI-runnable ·
ship today.

## ⑥ Reflection (human · alice + bob · leader)

The "wiki is the artifact" point is that the markdown files are version-controlled,
diffable, human-editable. The maintainer adds; humans curate.

Idempotency by `<!-- key: ID -->` HTML comment is invisible in rendered markdown
but greppable. Better than full-content hash because lets the human edit/refine
the pattern body without the maintainer reverting it.

LLM-distilled is the v1.2 evolution; for v1.1 ship boring + correct.

## ⑦ Execution log (AI · append-only)

- 2026-05-09T05:00 · `.app/ome365_wiki.py` · ~200 行 · update + query + cli_main
- 2026-05-09T05:30 · `ome365 wiki update | query` 接入 launcher
- 2026-05-09T06:00 · `tests/test_ome365_wiki.py` · 12 tests
- 2026-05-09T06:30 · 全量回归 225+12=237 tests · pii 0 · push

## ⑧ Feedback (AI · 90 day backfill · pending 2026-08-09)

(empty until 2026-08-09 nightly distill_outcomes)
