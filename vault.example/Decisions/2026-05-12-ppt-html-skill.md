---
id: 2026-05-12-ppt-html-skill
opened: 2026-05-12T18:00:00Z
closed: 2026-05-12T20:00:00Z
status: closed
owner: alice
participants: []
supersedes: null
superseded_by: null
outcome: "Ship /ppt-html as a built-in skill: Markdown → self-contained HTML deck, theme-pluggable, brand-neutral default theme, comprehensive smoke tests."
value_anchors:
  - P              # Product surface (new skill that teams will actually use)
  - L              # Larger scope (touches CI tests, README, docs)
  - 维护性          # Theme-pluggable architecture keeps brand assets out of public repo
roi_estimated: "Cuts presentation authoring loop from 30+ minutes per deck (slide tool) to 30 seconds (markdown edit + render). For an exec team producing 1-2 decks/week, ~50 hours/year per author."
roi_actual: null   # Track via teams adopting and feedback
planned_duration_days: 1
elapsed_days: 1
category: skill
hours_saved: 50
---

# Decision: Add /ppt-html skill to Ome365 public skill set

## ① Problem definition

Teams that author internal strategy decks today face two costs that compound:
(a) the slide-tool tax — every minute spent dragging boxes is a minute not spent
on the actual thinking; (b) the brand drift cost — every author re-implements
VI rules slightly differently, so deck-to-deck consistency is a permanent fight.

LLM-assisted authoring outputs Markdown, which is the right source format
(diffable, regenerable). But Markdown alone doesn't present. The gap is a
*deterministic, theme-pluggable* renderer that takes Markdown spec → polished
self-contained HTML deck.

## ② Options considered

1. **External slide tools (Slidev, Marp, reveal.js)**: powerful but brings a
   build chain, package deps, CDN fonts, and forces a specific Markdown dialect
   per tool. None ship a brand-private theme story for a public repo.
2. **In-house renderer with theme-pluggable architecture**: 100% offline
   (CDN-free), theme dir is just `engine.html + layouts.py + (optional) logo`,
   `.gitignore` keeps private brand themes out of the public mirror.
3. **Status quo**: every team continues fighting slide tools.

## ③ Choice

Option 2. The `default` theme (brand-neutral slate/indigo) ships in the public
mirror as the starter. Private brand themes live as additional theme dirs
that are `.gitignore`d. This pattern reuses the same code/data separation
discipline we already use for `cockpit_config.json` and `truth.yml`.

## ④ Implementation surface

- `skills/ppt-html/render.py` — CLI (theme-agnostic)
- `skills/ppt-html/SKILL.md` — Anthropic-spec compatible frontmatter
- `skills/ppt-html/templates/default/{engine.html,layouts.py}` — public theme
- `skills/ppt-html/examples/sample-deck.md` — 11-slide demo using all 8 layouts
- `tests/test_ppt_html.py` — smoke + contract tests (9 new tests)

## ⑤ Acceptance

- All 9 ppt-html tests green
- 533/533 full suite green (was 524 + 9 new)
- `scan_pii.py`: 0 hits clean
- Rendered demo deck is 56 KB, self-contained, opens offline in any browser
- Headless screenshots of 11 slides reviewed: typography polished, nav rail
  visible, no overflow, all 8 layouts render correctly

## ⑥ Followups

- Document "fork → customize theme" recipe more explicitly in SKILL.md
- Consider adding a second public theme (e.g. a "minimal" / "dark" variant)
  if there's user demand
- Build-time check that brand themes are gitignored before shipping (currently
  manual)
