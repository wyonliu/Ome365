"""tests/test_v1_1_i18n.py · v1.1.39 · cockpit i18n key symmetry
[decision: 2026-05-09-v1-1-3-polish]

Static parse of .app/static/v1_1.html · extracts the I18N block · asserts
en/zh have identical key sets. Catches the "added a key only in en" drift
where Chinese users see "scope.cost_per_resolved_decision" raw on the page.
"""
import re
from pathlib import Path

import pytest

V1_1_HTML = Path(__file__).resolve().parent.parent / ".app" / "static" / "v1_1.html"


def _extract_i18n_keys() -> dict[str, set[str]]:
    """Parse the const I18N = { en: {...}, zh: {...} } block.

    Naive enough to be readable, robust enough to find missing keys.
    """
    text = V1_1_HTML.read_text("utf-8")
    # Locate I18N block
    m = re.search(r"const I18N\s*=\s*\{(.*?)\n\};", text, re.DOTALL)
    assert m, "I18N block not found in v1_1.html"
    block = m.group(1)

    out: dict[str, set[str]] = {}
    # Locate each language sub-block: lang_code: { ... },
    for lang_match in re.finditer(r"(\w+):\s*\{(.*?)\}", block, re.DOTALL):
        lang = lang_match.group(1)
        body = lang_match.group(2)
        keys = set(re.findall(r'"([^"]+)"\s*:', body))
        out[lang] = keys
    return out


def test_v1_1_html_exists():
    assert V1_1_HTML.exists(), f"missing {V1_1_HTML}"


def test_i18n_block_has_en_and_zh():
    keys = _extract_i18n_keys()
    assert "en" in keys, "missing 'en' language in I18N"
    assert "zh" in keys, "missing 'zh' language in I18N"


def test_i18n_keys_are_symmetric():
    """Every key must exist in BOTH en and zh.

    Catches: developer adds an English label but forgets the Chinese
    translation — Chinese users see the raw key string on the page.
    """
    keys = _extract_i18n_keys()
    en, zh = keys["en"], keys["zh"]
    only_en = en - zh
    only_zh = zh - en
    assert not only_en, f"keys present in en but missing in zh: {sorted(only_en)}"
    assert not only_zh, f"keys present in zh but missing in en: {sorted(only_zh)}"


def test_i18n_no_empty_translations():
    """No translation should be empty string · indicates a TODO that shipped."""
    text = V1_1_HTML.read_text("utf-8")
    m = re.search(r"const I18N\s*=\s*\{(.*?)\n\};", text, re.DOTALL)
    assert m
    # Look for "key": "" or "key":""
    empties = re.findall(r'"([^"]+)"\s*:\s*""', m.group(1))
    assert not empties, f"i18n has empty values for keys: {empties}"


def test_i18n_dim_keys_match_eval_dimensions():
    """dim.* keys must map 1:1 with the 7 D* dimensions in ome365_eval."""
    keys = _extract_i18n_keys()
    en_dims = {k for k in keys["en"] if k.startswith("dim.")}
    expected = {
        "dim.D1_delivery", "dim.D2_cost_per_outcome", "dim.D3_quality",
        "dim.D4_judgment", "dim.D5_ecosystem",
        "dim.D6_revenue_per_workflow", "dim.D7_learning",
    }
    assert en_dims == expected, \
        f"dim.* set mismatch · only-html={en_dims-expected} · only-spec={expected-en_dims}"
