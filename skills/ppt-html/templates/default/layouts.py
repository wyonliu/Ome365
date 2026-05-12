"""
Default theme · 8 slide layout renderers.

Brand-neutral starter theme: slate + indigo + subtle teal. System fonts only.
Ships without a logo.png by default; renders a typographic wordmark fallback
on the cover when `meta.brand_chip` or `meta.brand_name` is provided.

Each render_<layout>(meta, data) → HTML string for one <section class="ph-slide">.
"""

import html as _h


def esc(s):
    """Lightweight text passthrough — trusted inline tags like <accent>/<strong>/<em>/<br> remain."""
    if s is None:
        return ""
    return str(s)


def attr(s):
    """Attribute-safe escape."""
    return _h.escape(str(s), quote=True)


def notes_block(notes):
    if not notes:
        return ""
    return f'      <div class="notes-source">{esc(notes)}</div>\n'


def _wordmark(meta):
    """Typographic wordmark fallback when no logo.png is bundled."""
    brand = meta.get("brand_name") or meta.get("brand_chip") or ""
    # If brand_chip has a separator like " · ", use the first segment as the name
    if " · " in brand:
        brand = brand.split(" · ", 1)[0]
    if not brand:
        return ""
    return (
        '<span class="vi-wordmark" aria-label="Brand wordmark">'
        '<span class="vi-mark" aria-hidden="true"></span>'
        f'<span class="vi-name">{esc(brand)}</span>'
        '</span>'
    )


def _logo_or_wordmark(meta, css_class="vi-logo-cover"):
    """Render either an inlined logo PNG (if provided) or a typographic wordmark."""
    logo_uri = meta.get("_logo_data_uri", "")
    if logo_uri:
        return f'<img class="{css_class}" src="data:image/png;base64,{logo_uri}" alt="" />'
    return _wordmark(meta)


# ────────────────────────────────────────────────────────────────────────

def render_cover(meta, data):
    """Cover slide. data: title, sub, section, stamp, notes."""
    brand_chip = meta.get("brand_chip", "")
    date_disp = meta.get("date_display", meta.get("date", ""))
    speaker = meta.get("speaker", "")
    role = meta.get("role", "")
    section = esc(data.get("section", ""))
    title = esc(data.get("title", "")).replace("\n", "<br>")
    sub = esc(data.get("sub", ""))
    stamp = esc(data.get("stamp", "Internal draft"))
    chapter = esc(data.get("chapter", "Opening"))
    dtitle = esc(data.get("data_title", "Cover"))

    return f'''    <!-- ════════ COVER ════════ -->
    <section class="ph-slide" data-layout="cover" data-chapter="{attr(chapter)}" data-title="{attr(dtitle)}">
      <div class="cover-noise" aria-hidden="true"></div>
      <div class="cover-wrap">
        <div class="cover-head">
          <div class="cover-brand">{_logo_or_wordmark(meta)}</div>
          <div class="cover-meta">
            <div class="cover-meta-chip"><span class="cover-mark-dot"></span><span>{esc(brand_chip)}</span></div>
            <div class="cover-date">{esc(date_disp)}</div>
          </div>
        </div>

        <div class="cover-body">
          <div class="cover-section-num">{section}</div>
          <h1 class="cover-title">{title}</h1>
          <p class="cover-sub">{sub}</p>
        </div>

        <div class="cover-foot">
          <div class="cover-speaker">
            <div class="cover-speaker-label">Presented by</div>
            <div class="cover-speaker-name">{esc(speaker)}</div>
            <div class="cover-speaker-role">{esc(role)}</div>
          </div>
          <div class="cover-stamp">{stamp}</div>
        </div>
      </div>
{notes_block(data.get("notes"))}    </section>
'''


def render_agenda(meta, data):
    """Agenda slide. data: title, lead, items (list of strings or {title,sub}).

    Strings may use 'Title :: subtitle' to inline a subtitle. PyYAML parses
    `- Foo :: Bar` as `{'Foo :': 'Bar'}`, so we normalise that here too."""
    items = data.get("items", []) or []
    item_html = ""
    for i, it in enumerate(items, 1):
        t, sub = "", ""
        if isinstance(it, str):
            if "::" in it:
                t, sub = it.split("::", 1)
                t, sub = t.strip(), sub.strip()
            else:
                t, sub = it.strip(), ""
        elif isinstance(it, dict):
            if "title" in it or "sub" in it:
                t, sub = it.get("title", ""), it.get("sub", "")
            elif len(it) == 1:
                # PyYAML's parse of `Foo :: Bar` → {'Foo :': 'Bar'}
                k, v = next(iter(it.items()))
                t = str(k).rstrip(":").strip()
                sub = str(v).strip() if v is not None else ""
            else:
                t = it.get("title", "")
                sub = it.get("sub", "")
        item_html += f'''          <div class="agenda-item">
            <span class="agenda-num">{i:02d}</span>
            <div class="agenda-text">
              <div class="agenda-title">{esc(t)}</div>
              <div class="agenda-sub">{esc(sub)}</div>
            </div>
          </div>
'''
    title = esc(data.get("title", "Agenda"))
    lead = esc(data.get("lead", ""))
    chapter = esc(data.get("chapter", "Opening"))
    dtitle = esc(data.get("data_title", "Agenda"))
    return f'''    <!-- ════════ AGENDA ════════ -->
    <section class="ph-slide" data-layout="agenda" data-chapter="{attr(chapter)}" data-title="{attr(dtitle)}">
      <div class="slide-eyebrow"><span>Agenda</span></div>
      <div class="slide-body">
        <h2 class="t-display-3">{title}</h2>
        <p class="t-lead" style="margin-top: 1.5cqh; max-width: 78%">{lead}</p>
        <div class="agenda-grid">
{item_html}        </div>
      </div>
{notes_block(data.get("notes"))}    </section>
'''


def render_section(meta, data):
    """Section divider. data: num, eyebrow, title, sub."""
    num = esc(data.get("num", ""))
    eyebrow = esc(data.get("eyebrow", ""))
    title = esc(data.get("title", "")).replace("\n", "<br>")
    sub = esc(data.get("sub", ""))
    chapter = esc(data.get("chapter", ""))
    dtitle = esc(data.get("data_title", chapter or "Section"))
    return f'''    <!-- ════════ SECTION ════════ -->
    <section class="ph-slide" data-layout="section" data-chapter="{attr(chapter)}" data-title="{attr(dtitle)}">
      <div class="section-wrap">
        <div class="section-num-bg">{num}</div>
        <div class="section-inner">
          <div class="section-eyebrow">{eyebrow}</div>
          <h2 class="section-title">{title}</h2>
          <p class="section-sub">{sub}</p>
        </div>
      </div>
{notes_block(data.get("notes"))}    </section>
'''


def _bull_tags(tags):
    """Tags can be ['P0', 'teal:agent'] or [{name, variant}]. Variants: teal, orange (default = indigo)."""
    if not tags:
        return ""
    out = '<div class="bull-tags">'
    for t in tags:
        if isinstance(t, str):
            if ":" in t:
                variant, name = t.split(":", 1)
                out += f'<span class="bull-tag tag-{attr(variant)}">{esc(name)}</span>'
            else:
                out += f'<span class="bull-tag">{esc(t)}</span>'
        else:
            v = t.get("variant", "")
            cls = f' tag-{attr(v)}' if v else ""
            out += f'<span class="bull-tag{cls}">{esc(t.get("name",""))}</span>'
    out += '</div>'
    return out


def render_bullets(meta, data):
    """Bullets list. data: eyebrow, title, lead, items=[{title, detail, tags?}] or [str].

    Strings may use 'Title :: detail'."""
    items = data.get("items", []) or []
    li = ""
    for i, it in enumerate(items, 1):
        if isinstance(it, str):
            t, d = it.split("::", 1) if "::" in it else (it, "")
            li += f'''          <li>
            <span class="bull-num">{i:02d}</span>
            <div class="bull-body">
              <div class="bull-title">{esc(t.strip())}</div>
              <div class="bull-detail">{esc(d.strip())}</div>
            </div>
          </li>
'''
        elif isinstance(it, dict):
            # Detect PyYAML's misparse of `Title :: detail` → {'Title :': 'detail'}
            if "title" not in it and "detail" not in it and "tags" not in it and len(it) == 1:
                k, v = next(iter(it.items()))
                t = str(k).rstrip(":").strip()
                d = str(v).strip() if v is not None else ""
                li += f'''          <li>
            <span class="bull-num">{i:02d}</span>
            <div class="bull-body">
              <div class="bull-title">{esc(t)}</div>
              <div class="bull-detail">{esc(d)}</div>
            </div>
          </li>
'''
            else:
                tags = _bull_tags(it.get("tags"))
                li += f'''          <li>
            <span class="bull-num">{i:02d}</span>
            <div class="bull-body">
              <div class="bull-title">{esc(it.get("title",""))}</div>
              <div class="bull-detail">{esc(it.get("detail",""))}</div>
              {tags}
            </div>
          </li>
'''
    chapter = esc(data.get("chapter", ""))
    dtitle = esc(data.get("data_title", data.get("title", "")))
    return f'''    <!-- ════════ BULLETS ════════ -->
    <section class="ph-slide" data-layout="bullets" data-chapter="{attr(chapter)}" data-title="{attr(dtitle)}">
      <div class="slide-eyebrow"><span>{esc(data.get("eyebrow",""))}</span></div>
      <div class="slide-body">
        <h2 class="t-h1">{esc(data.get("title",""))}</h2>
        <p class="t-lead bullets-lead">{esc(data.get("lead",""))}</p>
        <ol class="bullets">
{li}        </ol>
      </div>
{notes_block(data.get("notes"))}    </section>
'''


def _col(col):
    variant = col.get("variant", "")
    cls = f" col-{variant}" if variant else ""
    items = "".join(
        f'              <li class="col-list-item">{esc(it)}</li>\n'
        for it in (col.get("items") or [])
    )
    foot = col.get("foot", "")
    foot_html = f'            <div class="col-foot">{esc(foot)}</div>' if foot else ""
    return f'''          <div class="col{cls}">
            <div class="col-eyebrow">{esc(col.get("eyebrow",""))}</div>
            <div class="col-title">{esc(col.get("title",""))}</div>
            <ul class="col-list">
{items}            </ul>
{foot_html}
          </div>
'''


def render_two_col(meta, data):
    """Two-column. data: eyebrow, title, lead, col1{...}, col2{...}.

    Each col supports: eyebrow, title, items=[str], foot, variant=(accent|warn)."""
    c1 = _col(data.get("col1", {}) or {})
    c2 = _col(data.get("col2", {}) or {})
    chapter = esc(data.get("chapter", ""))
    dtitle = esc(data.get("data_title", data.get("title", "")))
    return f'''    <!-- ════════ TWO-COL ════════ -->
    <section class="ph-slide" data-layout="two-col" data-chapter="{attr(chapter)}" data-title="{attr(dtitle)}">
      <div class="slide-eyebrow"><span>{esc(data.get("eyebrow",""))}</span></div>
      <div class="slide-body">
        <h2 class="t-h1">{esc(data.get("title",""))}</h2>
        <p class="t-lead bullets-lead">{esc(data.get("lead",""))}</p>
        <div class="cols-2">
{c1}{c2}        </div>
      </div>
{notes_block(data.get("notes"))}    </section>
'''


def render_matrix(meta, data):
    """5-cell matrix with hero. data: eyebrow, title, lead, hero{num,title,body,tags}, cells=[...]."""
    hero = data.get("hero", {}) or {}
    hero_tags = "".join(f'<span class="mc-tag">{esc(t)}</span>' for t in (hero.get("tags") or []))
    hero_html = f'''          <div class="matrix-cell is-hero">
            <div>
              <div class="mc-num">{esc(hero.get("num",""))}</div>
              <div class="mc-title">{esc(hero.get("title",""))}</div>
              <div class="mc-body">{esc(hero.get("body",""))}</div>
            </div>
            <div class="mc-foot">{hero_tags}</div>
          </div>
'''
    cells_html = ""
    for cell in (data.get("cells") or []):
        tags = "".join(f'<span class="mc-tag">{esc(t)}</span>' for t in (cell.get("tags") or []))
        cells_html += f'''          <div class="matrix-cell">
            <div>
              <div class="mc-num">{esc(cell.get("num",""))}</div>
              <div class="mc-title">{esc(cell.get("title",""))}</div>
              <div class="mc-body">{esc(cell.get("body",""))}</div>
            </div>
            <div class="mc-foot">{tags}</div>
          </div>
'''
    chapter = esc(data.get("chapter", "Overview"))
    dtitle = esc(data.get("data_title", data.get("title", "")))
    return f'''    <!-- ════════ MATRIX ════════ -->
    <section class="ph-slide" data-layout="matrix" data-chapter="{attr(chapter)}" data-title="{attr(dtitle)}">
      <div class="slide-eyebrow"><span>{esc(data.get("eyebrow",""))}</span></div>
      <div class="slide-body">
        <h2 class="t-h1">{esc(data.get("title",""))}</h2>
        <p class="t-lead bullets-lead">{esc(data.get("lead",""))}</p>
        <div class="matrix">
{hero_html}{cells_html}        </div>
      </div>
{notes_block(data.get("notes"))}    </section>
'''


def render_kpi(meta, data):
    """KPI tiles. data: eyebrow, title, lead, kpis=[{num,unit?,label,foot}], note?{eyebrow,body}"""
    kpis = data.get("kpis", []) or []
    kpi_html = ""
    for k in kpis:
        unit = k.get("unit", "")
        unit_html = f'<span class="kpi-unit">{esc(unit)}</span>' if unit else ""
        kpi_html += f'''          <div class="kpi">
            <div class="kpi-num">{esc(k.get("num",""))}{unit_html}</div>
            <div class="kpi-label">{esc(k.get("label",""))}</div>
            <div class="kpi-foot">{esc(k.get("foot",""))}</div>
          </div>
'''
    note = data.get("note")
    note_html = ""
    if note:
        note_html = f'''        <div class="org-note">
          <div class="col-eyebrow">{esc(note.get("eyebrow",""))}</div>
          <p>{esc(note.get("body",""))}</p>
        </div>
'''
    chapter = esc(data.get("chapter", "Overview"))
    dtitle = esc(data.get("data_title", data.get("title", "")))
    return f'''    <!-- ════════ KPI ════════ -->
    <section class="ph-slide" data-layout="kpi" data-chapter="{attr(chapter)}" data-title="{attr(dtitle)}">
      <div class="slide-eyebrow"><span>{esc(data.get("eyebrow",""))}</span></div>
      <div class="slide-body">
        <h2 class="t-h1">{esc(data.get("title",""))}</h2>
        <p class="t-lead bullets-lead">{esc(data.get("lead",""))}</p>
        <div class="kpi-grid">
{kpi_html}        </div>
{note_html}      </div>
{notes_block(data.get("notes"))}    </section>
'''


def render_close(meta, data):
    """Close. data: eyebrow, title, sub, questions=[str]."""
    qs = ""
    for i, q in enumerate(data.get("questions", []) or [], 1):
        num = "①②③④⑤⑥⑦⑧⑨"[i-1] if i <= 9 else f"{i}"
        qs += f'          <div class="close-q"><span class="close-q-num">{num}</span><span>{esc(q)}</span></div>\n'
    chapter = esc(data.get("chapter", "Wrap"))
    dtitle = esc(data.get("data_title", "Discussion"))
    return f'''    <!-- ════════ CLOSE ════════ -->
    <section class="ph-slide" data-layout="close" data-chapter="{attr(chapter)}" data-title="{attr(dtitle)}">
      <div class="close-wrap">
        <div class="close-eyebrow">{esc(data.get("eyebrow",""))}</div>
        <h2 class="close-title">{esc(data.get("title","Discussion"))}</h2>
        <p class="close-sub">{esc(data.get("sub",""))}</p>
        <div class="close-questions">
{qs}        </div>
      </div>
{notes_block(data.get("notes"))}    </section>
'''


LAYOUTS = {
    "cover":   render_cover,
    "agenda":  render_agenda,
    "section": render_section,
    "bullets": render_bullets,
    "two-col": render_two_col,
    "two_col": render_two_col,
    "matrix":  render_matrix,
    "kpi":     render_kpi,
    "close":   render_close,
}
