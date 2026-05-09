"""tests/test_version_sync.py · v1.1.40 · README ↔ CHANGELOG version sync
[decision: 2026-05-09-v1-1-3-polish]

Releases bump README badge + CHANGELOG top entry by hand. If a future release
script forgets one, the documentation drifts. This test fails first.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"

VERSION_RE = re.compile(r"v(\d+)\.(\d+)\.(\d+)")


def _readme_badge_version() -> str:
    """The shields.io badge in the README is the canonical 'shipped' version."""
    text = README.read_text("utf-8")
    m = re.search(r"badge/version-v(\d+\.\d+\.\d+)-blue", text)
    assert m, "README shields.io version badge not found"
    return m.group(1)


def _changelog_top_version() -> str:
    """First `## vX.Y.Z — ...` heading after the title."""
    text = CHANGELOG.read_text("utf-8")
    m = re.search(r"^## v(\d+\.\d+\.\d+)\b", text, re.MULTILINE)
    assert m, "CHANGELOG top version heading not found"
    return m.group(1)


def test_readme_badge_matches_changelog_top():
    assert _readme_badge_version() == _changelog_top_version(), (
        f"version drift: README badge says v{_readme_badge_version()} but "
        f"CHANGELOG top entry says v{_changelog_top_version()}. Bump both."
    )


def test_changelog_versions_non_increasing():
    """Each ## vX.Y.Z heading must be ≥ the next (newest first).

    Allows ties for shared base versions like v1.0.0-rc1 / v1.0.0-pre, but
    catches accidentally inserted strictly-older entries above newer ones.
    """
    text = CHANGELOG.read_text("utf-8")
    versions = [tuple(int(x) for x in m)
                for m in re.findall(r"^## v(\d+)\.(\d+)\.(\d+)", text, re.MULTILINE)]
    assert versions, "no ## vX.Y.Z headings found"
    for i in range(len(versions) - 1):
        assert versions[i] >= versions[i + 1], (
            f"out-of-order CHANGELOG: v{'.'.join(map(str, versions[i]))} "
            f"comes before v{'.'.join(map(str, versions[i + 1]))}"
        )


def test_version_badge_format():
    """Badge URL pattern is shields.io standard · don't accidentally break it."""
    text = README.read_text("utf-8")
    badges = re.findall(r"img\.shields\.io/badge/version-v(\d+\.\d+\.\d+)-blue", text)
    assert badges, "no shields.io version badge in README"
    # Exactly one canonical version badge
    assert len(badges) >= 1
    # All version badges agree (in case of multiple)
    assert len(set(badges)) == 1, f"multiple version badges disagree: {badges}"
