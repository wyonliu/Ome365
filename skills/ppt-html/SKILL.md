---
name: ppt-html
description: Compile a YAML-flavored Markdown outline into a single self-contained HTML presentation — inline CSS+JS+(optional) base64 logo, zero CDN, runs offline. Theme-pluggable. Keyboard nav, TOC, speaker notes, fullscreen, print-to-PDF.
---

# /ppt-html · Markdown → self-contained HTML deck

Compile one YAML-flavored Markdown file into one HTML file. Open it in any browser
and present. No build step. No CDN. No font fetches. Works fully offline.

## Why

LLM-assisted slide authoring usually outputs Markdown. That's the right source format
(diffable, version-controllable, regenerable). But Markdown alone doesn't *present* —
you need slide chrome, navigation, layouts, brand. `ppt-html` is the rendering layer
that turns Markdown deck specs into something you'd actually show to a customer.

The output is one `.html` file with everything inlined. You can:

- Drop it into any static host (S3, GCS, Cloudflare Pages, Netlify, Vercel, Pages).
- Email it (it's a single file).
- Open it offline on a plane and present.
- Print to PDF with `P`.
- Embed it in a wiki, a doc portal, or your internal tool.

## Quickstart

```bash
# 1) Render an example
python3 render.py examples/sample-deck.md -o /tmp/deck.html

# 2) Open it
open /tmp/deck.html   # macOS · or use your browser

# 3) Present
# ← → / Space / PgUp PgDn   → navigate
# 1-9                         → jump to slide N
# T                           → table of contents
# N                           → speaker notes
# F                           → fullscreen
# P                           → print / export PDF
# B                           → black screen
# Esc                         → close overlay
```

## Markdown DSL

The top of the file is YAML frontmatter for **global** metadata. Then each slide
is `## <layout> :: <data-title> // <data-chapter>` followed by an indented YAML body.

```markdown
---
title: Q3 Strategy Review
subtitle: Product roadmap & investments
speaker: Alice Smith
role: Head of Product · Acme Corp
date: 2026-09-15
brand_chip: Acme · Internal
theme: default
---

## cover :: Cover // Opening
title: |
  One <accent>clear</accent>
  product line per
  customer segment
sub: From enterprise infrastructure to consumer apps · the 2026 plan
stamp: Internal draft · v0.2
notes: 30 sec open. The next 4 slides set the stage; this one is the punch line.

## agenda :: Agenda // Opening
title: Five product lines · one map
lead: We're not adding products. We're collapsing 30+ lines into 5 that can win.
items:
  - Enterprise platform :: B-end fundamentals, retention play
  - SMB self-serve :: Channel-led, fast deploy
  - Agent kernel :: Cross-product runtime
  - Consumer apps :: New growth curve
  - Internal R&D :: Org capability + scaffolding

## section :: Section // Cover
num: "1"
eyebrow: Part 1
title: |
  Where we
  stand today
sub: Numbers, gaps, and the story we tell investors

## bullets :: Title // Chapter
eyebrow: Section eyebrow
title: H1 heading
lead: One-line lead in
items:
  - title: First bullet
    detail: Detail line
    tags: [P0, "teal:agent"]    # tag-teal · tag-orange · (default)
  - title: Second bullet
    detail: Detail line
    tags: [P1]

## two-col :: Title // Chapter
eyebrow: eyebrow
title: H1
lead: Lead in
col1:
  eyebrow: Column 1
  title: Subtitle
  items: [...]
  foot: footnote
col2:
  variant: accent              # accent · warn · (default)
  ...

## matrix :: Title // Chapter
eyebrow: eyebrow
title: H1
lead: lead
hero:
  num: "01"
  title: Hero card
  body: Description
  tags: [P0 · Cash cow]
cells:
  - num: "02"
    title: Second
    body: ...
    tags: [P1]

## kpi :: Title // Chapter
eyebrow: eyebrow
title: H1
lead: lead
kpis:
  - num: "5"
    label: Streams
    foot: Active product lines
  - num: "14"
    unit: days
    label: Cycle time

## close :: Discussion // Wrap
eyebrow: M0 · M3 · M6
title: Decisions we need today
sub: Three open questions
questions:
  - Which 3 lines do we fund?
  - Build the kernel as its own team or grow inside platform?
  - When do we kick off consumer alpha?
```

## Theme system

Each theme lives at `templates/<name>/` and contains:

- `engine.html` — chrome + global CSS + JS (with `{{TITLE}}` and `{{SLIDES}}` placeholders)
- `layouts.py` — exposes `LAYOUTS = {'cover': render_cover, ...}`. Each handler is `(meta, data) → html_string`.
- `logo.png` (optional) — base64-inlined into the output

### Built-in themes

| Theme | Status |
|---|---|
| `default` | Neutral slate/indigo palette · 8 core layouts · brand-agnostic · the starter |

To build your own enterprise VI theme:

1. `cp -r templates/default templates/<your-brand>`
2. Edit `engine.html` (colors, fonts, VI corner marks)
3. Drop your logo PNG in (or remove `logo.png`)
4. Add/extend layouts in `layouts.py`
5. `python3 render.py input.md -o out.html --theme <your-brand>`

Themes are how you keep brand assets private while sharing the engine. Add
`templates/<your-brand>/` to `.gitignore` and the public mirror stays clean.

## CLI

```
python3 render.py <input.md> [-o <output.html>] [--theme <theme-name>]
python3 render.py --list-themes
```

Exits non-zero on missing input, missing theme, or missing engine.html / layouts.py.
Unknown layouts in the deck source print a warning but don't fail (so partial
drafts still render).

## QA / self-check

After rendering, take screenshots via headless Chrome and review each slide:

```bash
mkdir -p /tmp/deck-shots
for n in 1 2 3 4 5 6 7 8 9; do
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --headless=new --disable-gpu --hide-scrollbars \
    --window-size=1920,1080 --virtual-time-budget=4000 \
    --screenshot=/tmp/deck-shots/s${n}.png \
    "file://$(pwd)/out.html#/${n}"
done
```

Look for: nav rail visible · slide chrome consistent · no content overflow ·
logo aspect ratio preserved · all VI elements present per slide.

## File structure

```
ppt-html/
├── SKILL.md              # this file
├── render.py             # theme-agnostic CLI
├── templates/
│   └── default/          # brand-neutral starter theme
│       ├── engine.html
│       ├── layouts.py
│       └── (no logo.png by default)
└── examples/
    └── sample-deck.md    # demo input
```

## Design rules (so themes stay polished)

1. **Rail stays outside the deck** — never let the navigation rail cover slide content.
2. **Logo aspect ratio** — flex containers must use `align-items: flex-start` or images get stretched.
3. **Inline everything** — fonts, logos, icons. A theme that depends on a CDN is a theme that breaks offline.
4. **Test on dark + light** — slide backgrounds vary; chrome should look right against both.
5. **Print path matters** — `@media print` rules need explicit attention. Don't ship a theme that prints garbage.
