#!/usr/bin/env python3
"""
/ppt-html · Markdown → self-contained HTML deck.

Renders a YAML-flavored Markdown outline into a single, dependency-free HTML
presentation: inline CSS + JS + (optional) base64-embedded logo. No CDN, no
build step, no runtime fonts.

Layouts are theme-pluggable: drop a directory under templates/<theme>/ with
engine.html + layouts.py + (optional) logo.png. The shipped `default` theme
is brand-neutral; clone it to build your own enterprise VI theme.

Usage
-----
  python3 render.py <input.md> [-o <output.html>] [--theme default]

Input format: see SKILL.md.  Slides separated by `## <layout> :: <data-title>
// <data-chapter>` headers, each followed by an indented YAML body.
"""

from __future__ import annotations

import argparse
import base64
import pathlib
import re
import sys

THIS_DIR = pathlib.Path(__file__).resolve().parent
TEMPLATES_DIR = THIS_DIR / "templates"

# Avoid hard dependency on PyYAML — use a tiny built-in parser for the subset
# we emit. If PyYAML is installed it takes over (handles edge cases better).
try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def parse_yaml(text: str):
    """Parse YAML; fall back to a minimal parser when PyYAML is missing."""
    if HAS_YAML:
        return yaml.safe_load(text) or {}
    return _mini_yaml(text)


def _mini_yaml(text: str):
    """Minimal YAML subset: mappings, lists of strings/mappings, scalars
    (incl. | block scalars). Indent = 2 spaces."""
    lines = []
    for ln in text.splitlines():
        # Skip pure-comment lines (we don't emit inline # in slide bodies).
        if ln.lstrip().startswith("#"):
            continue
        lines.append(ln.rstrip())

    pos = [0]

    def peek():
        while pos[0] < len(lines) and lines[pos[0]].strip() == "":
            pos[0] += 1
        return lines[pos[0]] if pos[0] < len(lines) else None

    def indent_of(s):
        return len(s) - len(s.lstrip(" "))

    def parse_block(base_indent):
        result = None
        while True:
            line = peek()
            if line is None:
                return result
            ind = indent_of(line)
            if ind < base_indent:
                return result
            stripped = line.strip()
            if stripped.startswith("- "):
                if result is None:
                    result = []
                if not isinstance(result, list):
                    return result
                pos[0] += 1
                val_part = stripped[2:].strip()
                if val_part == "":
                    sub = parse_block(ind + 2)
                    result.append(sub if sub is not None else "")
                elif ":" in val_part and not val_part.startswith(("\"", "'")):
                    # mapping in a list item
                    pos[0] -= 1
                    lines[pos[0]] = " " * (ind + 2) + stripped[2:]
                    sub = parse_block(ind + 2)
                    result.append(sub)
                else:
                    result.append(_scalar(val_part))
            elif ":" in stripped:
                if result is None:
                    result = {}
                if not isinstance(result, dict):
                    return result
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                pos[0] += 1
                if val == "|":
                    # block scalar
                    block_lines = []
                    block_indent = None
                    while pos[0] < len(lines):
                        nxt = lines[pos[0]]
                        if nxt.strip() == "":
                            block_lines.append("")
                            pos[0] += 1
                            continue
                        ni = indent_of(nxt)
                        if block_indent is None:
                            block_indent = ni
                        if ni < block_indent or ni <= ind:
                            break
                        block_lines.append(nxt[block_indent:])
                        pos[0] += 1
                    result[key] = "\n".join(block_lines).rstrip("\n")
                elif val == "":
                    sub = parse_block(ind + 2)
                    result[key] = sub if sub is not None else ""
                elif val.startswith("[") and val.endswith("]"):
                    inner = val[1:-1]
                    result[key] = [_scalar(x.strip()) for x in _split_flow(inner)] if inner.strip() else []
                else:
                    result[key] = _scalar(val)
            else:
                pos[0] += 1
        return result

    return parse_block(0) or {}


def _split_flow(s):
    """Split a flow-style YAML list: handles quoted strings with commas."""
    out, cur, q = [], "", None
    for c in s:
        if q:
            cur += c
            if c == q:
                q = None
        elif c in ('"', "'"):
            q = c
            cur += c
        elif c == ",":
            out.append(cur)
            cur = ""
        else:
            cur += c
    if cur:
        out.append(cur)
    return out


def _scalar(v: str):
    """Coerce a YAML scalar."""
    if v == "":
        return ""
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if v.lower() == "null":
        return None
    try:
        if "." in v:
            return float(v)
        return int(v)
    except ValueError:
        return v


# ──────────────────────────────────────────────────────────────

HEADER_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _parse_header(text: str):
    """Parse one header content (after `## `). Returns (layout, data_title, chapter).
    Format: layout [:: data-title] [// chapter]"""
    chapter = ""
    if " // " in text:
        text, chapter = text.rsplit(" // ", 1)
        chapter = chapter.strip()
    layout = text
    data_title = ""
    if "::" in text:
        layout, data_title = text.split("::", 1)
        layout = layout.strip()
        data_title = data_title.strip()
    return layout.strip(), data_title, chapter


def parse_doc(md_text: str):
    """Split into (frontmatter dict, [(layout, data_title, chapter, body_text), ...])."""
    fm = {}
    body = md_text

    if md_text.startswith("---"):
        end = md_text.find("\n---", 3)
        if end > 0:
            fm_text = md_text[3:end].strip()
            fm = parse_yaml(fm_text)
            body = md_text[end + 4:].lstrip("\n")

    slides = []
    matches = list(HEADER_RE.finditer(body))
    for i, m in enumerate(matches):
        layout, data_title, chapter = _parse_header(m.group(1))
        start = m.end()
        stop = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        slide_body = body[start:stop].strip("\n")
        slides.append((layout, data_title, chapter, slide_body))
    return fm, slides


def list_themes():
    """Return available theme directory names, sorted."""
    if not TEMPLATES_DIR.is_dir():
        return []
    return sorted(p.name for p in TEMPLATES_DIR.iterdir() if p.is_dir() and (p / "engine.html").is_file())


def render(input_path: pathlib.Path, output_path: pathlib.Path, theme: str = "default"):
    theme_dir = TEMPLATES_DIR / theme
    if not theme_dir.is_dir():
        avail = ", ".join(list_themes()) or "(none)"
        sys.exit(f"theme {theme!r} not found at {theme_dir}\navailable: {avail}")

    engine_path = theme_dir / "engine.html"
    logo_path = theme_dir / "logo.png"
    layouts_module_path = theme_dir / "layouts.py"

    if not engine_path.is_file() or not layouts_module_path.is_file():
        sys.exit(f"theme {theme!r} is missing engine.html or layouts.py")

    # Load layouts module
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"_layouts_{theme}", layouts_module_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    LAYOUTS = mod.LAYOUTS

    logo_b64 = base64.b64encode(logo_path.read_bytes()).decode() if logo_path.is_file() else ""

    md_text = input_path.read_text(encoding="utf-8")
    fm, slides = parse_doc(md_text)

    meta = dict(fm or {})
    meta["_logo_data_uri"] = logo_b64

    # Default date display = date if not given
    if "date_display" not in meta and "date" in meta:
        d = str(meta["date"])
        if re.match(r"\d{4}-\d{2}-\d{2}", d):
            meta["date_display"] = d.replace("-", " · ")
        else:
            meta["date_display"] = d

    rendered = []
    skipped = []
    for layout, data_title, chapter, body in slides:
        if layout not in LAYOUTS:
            skipped.append(layout)
            continue
        data = parse_yaml(body) or {}
        if data_title:
            data["data_title"] = data_title
        if chapter:
            data["chapter"] = chapter
        rendered.append(LAYOUTS[layout](meta, data))

    if skipped:
        print(f"warning: skipped {len(skipped)} unknown layout(s): {sorted(set(skipped))}", file=sys.stderr)

    # Compose final HTML
    engine = engine_path.read_text(encoding="utf-8")
    title = meta.get("title", "Deck")
    if meta.get("subtitle"):
        title = f"{title} · {meta['subtitle']}"
    final = engine.replace("{{TITLE}}", title).replace("{{SLIDES}}", "\n".join(rendered))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(final, encoding="utf-8")
    print(f"OK · {len(rendered)} slides · {output_path}")
    print(f"    size: {len(final):,} bytes  · theme: {theme}")


def main():
    ap = argparse.ArgumentParser(description="Render Markdown deck spec to self-contained HTML.")
    ap.add_argument("input", nargs="?", help="Path to input .md file (omit with --list-themes)")
    ap.add_argument("-o", "--output", help="Output .html path (default: same name + .html)")
    ap.add_argument("--theme", default="default",
                    help="Theme name (default: 'default'; run --list-themes to see installed)")
    ap.add_argument("--list-themes", action="store_true", help="List available themes and exit")
    args = ap.parse_args()

    if args.list_themes:
        themes = list_themes()
        if themes:
            for t in themes:
                print(t)
        else:
            print("(no themes installed)")
        return

    if not args.input:
        ap.error("input is required (or pass --list-themes)")

    inp = pathlib.Path(args.input).expanduser().resolve()
    if not inp.is_file():
        sys.exit(f"input not found: {inp}")
    out = pathlib.Path(args.output).expanduser().resolve() if args.output else inp.with_suffix(".html")
    render(inp, out, args.theme)


if __name__ == "__main__":
    main()
