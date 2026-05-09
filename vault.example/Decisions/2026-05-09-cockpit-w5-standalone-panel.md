---
id: 2026-05-09-cockpit-w5-standalone-panel
opened: 2026-05-09T03:30:00Z
closed: 2026-05-09T05:00:00Z
status: closed
owner: alice
participants: [bob]
supersedes: null
superseded_by: null
outcome: "Standalone /v1_1.html · 4 cards (Decisions/Skills/FinOps/Eval) · Vue 3 CDN · zero build · roles preset switcher"
value_anchors:
  - P              # CIO-shippable demo surface
  - L              # touches all 4 W2-W4 routers
  - 维护性          # adds one more html file
roi_estimated: "1 page · 4 router · CIO 一键 demo"
roi_actual: null
planned_duration_days: 1
elapsed_days: 1
category: frontend
hours_saved: 4
---

# Decision: W5 standalone v1.1 cockpit panel

## ① Problem definition (human · alice)

W2-W4 shipped 3 routers (decisions / eval / skills) but no front-end. CIO demo
needs a single URL to point at. Two paths:
A. Bolt 4 cards into existing `index.html` (4964 lines, gnarly section taxonomy).
B. Standalone `/v1_1.html` self-contained Vue 3 CDN page · ~300 lines.

## ② Data needs (AI)

4 endpoints already wired in W2-W4:
- GET /api/decision/list?status=closed&owner=alice
- GET /api/eval/finops/dashboard?since_days=30
- GET /api/eval/skills
- GET /api/eval/member/{actor}?window_days=30

5 role presets: engineer / pm / sales / ops / mixed (already in design spec §6).
Each preset has different D1-D7 weights · switcher rotates the eval display.

## ③ Models considered (AI)

Vue 3 CDN reactive page · ESM imports · zero build step (matches existing
`index.html` convention).

## ④ Options (AI)

A. **Bolt onto index.html** — 4 new SECTION_TAXONOMY entries · risk of disturbing
   existing 6 sections · merge conflicts with main repo
B. **Standalone /v1_1.html** ✓ chosen — self-contained · ships independently ·
   easy to delete if wrong direction
C. **Embed in iframe** — UX worse · CSP friction

## ⑤ Decision (human · alice · leader)

**Choice B**. Single file `.app/static/v1_1.html` · Vue 3 CDN · 4 cards arranged
in a 2x2 grid · top-bar shows role preset selector + actor input + window slider.

Rationale: matches v1.1 file-first philosophy · "the page is just a thin read
view of the file system" · no impact on legacy cockpit.

## ⑥ Reflection (human · alice + bob · leader)

Standalone panel = clean evolution path. If v1.1 lands well, v1.2 can promote
selected cards into `index.html` SECTION_TAXONOMY. If not, just delete one file.

Role preset switcher is metadata-only — the eval API returns all 7 dims · the
preset just changes which weights to apply for the displayed total. Server-side
weights flow through `eval-config.yml` · client-side preset is purely UI hint.

## ⑦ Execution log (AI · append-only)

- 2026-05-09T03:30 · `.app/static/v1_1.html` · 4 cards Vue 3 CDN
- 2026-05-09T04:00 · 5 role preset weight maps in JS · client-side
- 2026-05-09T04:30 · 自检：curl /v1_1.html · 200 · 4 fetch 都通
- 2026-05-09T05:00 · regression 225 tests · pii 0 · push

## ⑧ Feedback (AI · 90 day backfill · pending 2026-08-09)

(empty until 2026-08-09 nightly distill_outcomes)
