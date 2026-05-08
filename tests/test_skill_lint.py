"""
tests/skill_lint.py · Anthropic SKILL.md spec lint (32 tools spec-compatible).

Static frontmatter validator · 100% headless · CI-friendly.
This is the SPEC layer (32/32 tools compatible). Runtime tests live in skill_interop_test.sh.

Spec source: Anthropic Agent Skills open standard (2025-12-18, donated to AAIF)
- name: required, slug-safe string
- description: required, non-empty
- allowed-tools: required, list of strings
- license: optional, SPDX identifier
- model: optional, string
- Custom fields MUST be under "ome365:" namespace (no spec pollution)

Usage:
  python3 tests/skill_lint.py vault/Skills/*.md
  python3 tests/skill_lint.py docs/hike-templates/skills/*.md
  python3 -m pytest tests/skill_lint.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:
    yaml = None

# ── Anthropic spec fields (frozen 2025-12-18) ────────────────────────────────
ANTHROPIC_REQUIRED = {"name", "description"}
ANTHROPIC_OPTIONAL = {"allowed-tools", "license", "model", "version"}
ANTHROPIC_SPEC_FIELDS = ANTHROPIC_REQUIRED | ANTHROPIC_OPTIONAL

# ── Adopters (32 tools as of 2026-03 · for documentation) ────────────────────
ADOPTERS = {
    "headless_cli": [
        "Claude Code", "Codex CLI", "Gemini CLI", "Continue.dev",
    ],
    "ide_plugin": [
        "Cursor", "JetBrains Junie", "VS Code (MS)", "Block Goose",
        "AWS Kiro", "Zed", "Warp",
    ],
    "agent_sdk": [
        "Claude Agent SDK", "OpenAI Agents SDK",
    ],
}


_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$|^[a-z0-9]$")


def parse_frontmatter(text: str) -> dict | None:
    """Return parsed frontmatter dict, or None if missing."""
    m = _FM_RE.match(text)
    if not m:
        return None
    if yaml is None:
        # Minimal fallback parse (only top-level key: value)
        out: dict = {}
        for line in m.group(1).splitlines():
            mm = re.match(r"^([A-Za-z_][\w\-]*)\s*:\s*(.*)$", line)
            if mm:
                out[mm.group(1)] = mm.group(2).strip()
        return out
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None


def lint_skill(path: Path) -> list[str]:
    """Validate a SKILL.md file. Returns list of error messages (empty = pass)."""
    errors: list[str] = []
    try:
        text = path.read_text("utf-8")
    except Exception as e:
        return [f"read failed: {e}"]

    fm = parse_frontmatter(text)
    if fm is None:
        return ["missing or malformed frontmatter (expected `---\\nkey: value\\n---`)"]
    if not isinstance(fm, dict):
        return [f"frontmatter must be a dict, got {type(fm).__name__}"]

    # ── Required fields ──────────────────────────────────────────────────────
    for k in ANTHROPIC_REQUIRED:
        if k not in fm:
            errors.append(f"missing required field: {k!r}")
        elif not isinstance(fm[k], str) or not fm[k].strip():
            errors.append(f"field {k!r} must be non-empty string")

    # ── name format (slug-safe) ──────────────────────────────────────────────
    name = fm.get("name")
    if isinstance(name, str) and not _NAME_RE.match(name):
        errors.append(
            f"name {name!r} must be slug-safe (lowercase / digits / hyphens · "
            "no leading/trailing hyphen)"
        )

    # ── allowed-tools must be list[str] when present ─────────────────────────
    if "allowed-tools" in fm:
        tools = fm["allowed-tools"]
        if not isinstance(tools, list):
            errors.append("allowed-tools must be a list")
        else:
            for i, t in enumerate(tools):
                if not isinstance(t, str):
                    errors.append(f"allowed-tools[{i}] must be string, got {type(t).__name__}")

    # ── description length sanity (Anthropic guideline ≤ 280 chars first line) ─
    desc = fm.get("description")
    if isinstance(desc, str) and "\n" in desc:
        first_line = desc.split("\n", 1)[0]
        if len(first_line) > 280:
            errors.append(
                f"description first line {len(first_line)} chars > 280 "
                "(Anthropic guideline · summary should be brief)"
            )

    # ── Namespace pollution check (anti spec-drift) ──────────────────────────
    # Any non-spec field MUST be under ome365: dict (spec compatibility)
    for k in fm.keys():
        if k in ANTHROPIC_SPEC_FIELDS:
            continue
        if k == "ome365":
            # ome365 namespace · its content is free-form
            if not isinstance(fm[k], dict):
                errors.append("'ome365' namespace must be a dict")
            continue
        errors.append(
            f"non-spec top-level field {k!r} would pollute Anthropic spec; "
            "move it under `ome365:` namespace"
        )

    # ── ome365 namespace shape (recommend role / scope / created etc) ────────
    ome365 = fm.get("ome365") or {}
    if isinstance(ome365, dict):
        role = ome365.get("role")
        if role is not None and not isinstance(role, str):
            errors.append("ome365.role must be string when present")
        scope = ome365.get("scope")
        if scope is not None and scope not in ("tenant", "personal", None):
            errors.append(f"ome365.scope must be 'tenant' or 'personal', got {scope!r}")

    return errors


# ── pytest tests ──────────────────────────────────────────────────────────────

def _find_skill_files() -> list[Path]:
    """Find all SKILL.md files (only files in Skills/ subdirectories · not entity files)."""
    repo_root = Path(__file__).resolve().parent.parent
    candidates: list[Path] = []
    # Only Skills/ subdirs · NOT entity dirs (those have their own schema · see hike_schema.py)
    for base in (repo_root / "vault" / "Skills",
                 repo_root / "vault.example" / "Skills",
                 repo_root / "docs" / "hike-templates" / "skills"):
        if base.exists():
            candidates.extend(base.rglob("*.md"))
    # Also scan any docs/hike-templates/<industry>/skills/ pattern
    ht = repo_root / "docs" / "hike-templates"
    if ht.exists():
        for skills_dir in ht.glob("*/skills"):
            candidates.extend(skills_dir.rglob("*.md"))
    return candidates


def test_skill_files_lint_clean():
    """All SKILL.md files in repo must pass spec lint (CI gate)."""
    files = _find_skill_files()
    if not files:
        pytest.skip("no SKILL.md files found yet (v1.1 will populate vault/Skills/)")
    failures: list[str] = []
    for f in files:
        # Skip non-skill artifacts (README.md / index.md without frontmatter)
        text = f.read_text("utf-8", errors="ignore")[:500]
        if not text.startswith("---"):
            continue
        errors = lint_skill(f)
        if errors:
            for e in errors:
                failures.append(f"{f.relative_to(Path(__file__).resolve().parent.parent)}: {e}")
    assert not failures, "Skill lint failures:\n  " + "\n  ".join(failures)


def test_anthropic_required_fields():
    """Schema test: required fields enforced."""
    bad = """---
description: only desc, no name
---
"""
    errors = _lint_text(bad)
    assert any("missing required field: 'name'" in e for e in errors)


def test_namespace_pollution_rejected():
    """Custom field outside ome365: namespace is rejected."""
    bad = """---
name: test
description: hello
custom_field: should_be_in_ome365_ns
---
"""
    errors = _lint_text(bad)
    assert any("non-spec top-level field 'custom_field'" in e for e in errors)


def test_ome365_namespace_accepted():
    """Custom fields under ome365: are allowed."""
    good = """---
name: test
description: hello
allowed-tools: [Read]
ome365:
  role: Generic
  scope: personal
---
"""
    errors = _lint_text(good)
    assert errors == []


def test_name_slug_safe():
    """name must be slug-safe."""
    bad = """---
name: Bad Name With Spaces
description: hello
---
"""
    errors = _lint_text(bad)
    assert any("slug-safe" in e for e in errors)


def test_allowed_tools_must_be_list():
    """allowed-tools must be list."""
    bad = """---
name: test
description: hello
allowed-tools: "Read,WebFetch"
---
"""
    errors = _lint_text(bad)
    assert any("allowed-tools must be a list" in e for e in errors)


def _lint_text(text: str) -> list[str]:
    """Helper: lint a text snippet (in-memory, no file)."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(text)
        tmp = Path(f.name)
    try:
        return lint_skill(tmp)
    finally:
        tmp.unlink()


# ── CLI entry point ──────────────────────────────────────────────────────────
def _cli_main() -> int:
    """python3 tests/skill_lint.py path/to/SKILL.md ..."""
    args = sys.argv[1:]
    if not args:
        print("usage: python3 tests/skill_lint.py <skill.md> [<skill.md> ...]")
        print("       python3 -m pytest tests/skill_lint.py")
        return 2
    failures = 0
    for arg in args:
        for path in Path(".").glob(arg) if "*" in arg else [Path(arg)]:
            if not path.exists():
                print(f"SKIP {path} (not found)")
                continue
            errors = lint_skill(path)
            if errors:
                print(f"FAIL {path}")
                for e in errors:
                    print(f"  - {e}")
                failures += 1
            else:
                print(f"PASS {path}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_cli_main())
