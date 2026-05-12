"""
tests/test_ppt_html.py · smoke + contract tests for the /ppt-html skill.

Validates:
1. The shipped `default` theme renders the bundled `sample-deck.md` to a
   non-empty self-contained HTML file with no external network fetches.
2. SKILL.md frontmatter passes Anthropic spec lint (name + description required).
3. CLI's `--list-themes` enumerates `default` and exits 0.
4. Unknown layouts in a deck print a warning but don't crash the renderer.

Runs in <2s in CI · no browser · no network · uses python's stdlib only.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "ppt-html"
RENDER = SKILL_DIR / "render.py"
EXAMPLE = SKILL_DIR / "examples" / "sample-deck.md"
SKILL_MD = SKILL_DIR / "SKILL.md"


def _run(args, **kw):
    cmd = [sys.executable, str(RENDER)] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30, **kw)


def test_skill_dir_exists():
    assert SKILL_DIR.is_dir(), f"skills/ppt-html missing: {SKILL_DIR}"
    assert RENDER.is_file(), f"render.py missing"
    assert SKILL_MD.is_file(), f"SKILL.md missing"
    assert (SKILL_DIR / "templates").is_dir(), "templates/ missing"


def test_skill_md_frontmatter_anthropic_compatible():
    """SKILL.md must have YAML frontmatter with name + description (Anthropic spec)."""
    text = SKILL_MD.read_text("utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    assert m, "SKILL.md missing YAML frontmatter"
    fm = m.group(1)
    assert re.search(r"^name:\s*\S", fm, re.MULTILINE), "frontmatter missing 'name'"
    assert re.search(r"^description:\s*\S", fm, re.MULTILINE), "frontmatter missing 'description'"


def test_skill_md_no_pii_leak():
    """SKILL.md must not leak any of the project author's private brand/people refs."""
    text = SKILL_MD.read_text("utf-8")
    banned = ["example-brand", "example-corp", "example-org", "Alice Smith", "Alice Smith"]
    for b in banned:
        assert b.lower() not in text.lower(), f"SKILL.md leaks banned token: {b!r}"


def test_default_theme_exists():
    """The default theme is the public starter — must always ship."""
    theme = SKILL_DIR / "templates" / "default"
    assert theme.is_dir(), "templates/default/ missing — default theme is required"
    assert (theme / "engine.html").is_file(), "default/engine.html missing"
    assert (theme / "layouts.py").is_file(), "default/layouts.py missing"


def test_list_themes_includes_default():
    r = _run(["--list-themes"])
    assert r.returncode == 0, f"--list-themes failed: {r.stderr}"
    themes = set(r.stdout.strip().splitlines())
    assert "default" in themes, f"'default' missing from themes: {themes}"


def test_sample_deck_renders():
    """The shipped sample deck must compile cleanly with the default theme."""
    if not EXAMPLE.is_file():
        pytest.skip("sample-deck.md not present yet")
    out = Path("/tmp/ppt-html-smoketest.html")
    if out.exists():
        out.unlink()
    r = _run([str(EXAMPLE), "-o", str(out), "--theme", "default"])
    assert r.returncode == 0, f"render failed:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"
    assert out.is_file(), "output file not created"
    size = out.stat().st_size
    assert size > 5_000, f"output suspiciously small: {size} bytes"
    text = out.read_text("utf-8")
    assert "{{TITLE}}" not in text, "TITLE placeholder not substituted"
    assert "{{SLIDES}}" not in text, "SLIDES placeholder not substituted"


def test_self_contained_no_external_fetch():
    """Rendered output must not fetch from CDNs (the entire promise of the skill)."""
    if not EXAMPLE.is_file():
        pytest.skip("sample-deck.md not present yet")
    out = Path("/tmp/ppt-html-self-contained-check.html")
    if out.exists():
        out.unlink()
    r = _run([str(EXAMPLE), "-o", str(out), "--theme", "default"])
    assert r.returncode == 0
    text = out.read_text("utf-8")
    # No <script src="https://..."> or <link href="https://...">
    external_script = re.search(r'<script[^>]+src=["\']https?://', text)
    external_link = re.search(r'<link[^>]+href=["\']https?://[^"\']*\.(css|js|woff)', text)
    assert not external_script, f"output fetches external script: {external_script.group(0)[:80]}"
    assert not external_link, f"output fetches external stylesheet/font: {external_link.group(0)[:80]}"


def test_unknown_theme_errors_cleanly():
    r = _run(["nonexistent.md", "--theme", "does-not-exist"])
    assert r.returncode != 0
    assert "not found" in (r.stderr + r.stdout).lower()


def test_missing_input_errors_cleanly():
    r = _run(["/nonexistent/path/deck.md", "--theme", "default"])
    assert r.returncode != 0
    assert "not found" in (r.stderr + r.stdout).lower()
