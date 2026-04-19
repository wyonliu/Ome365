#!/usr/bin/env python3
"""ticnote-clean skill · entry point.

Thin wrapper that forwards to the battle-tested .app/ticnote_clean.py shipped
with Ome365. Skill is self-locating: it discovers the underlying cleaner via
(1) OME365_HOME env, (2) walking up from this script, (3) $PWD fallback.

This stays a thin wrapper on purpose — the cleaner has been tuned against
800+ real interview files and we don't want to maintain two copies.
"""
from __future__ import annotations

import argparse
import os
import runpy
import sys
from pathlib import Path


def _locate_cleaner() -> Path | None:
    candidates: list[Path] = []

    # 1) explicit env
    env = os.environ.get("OME365_HOME")
    if env:
        candidates.append(Path(env) / ".app" / "ticnote_clean.py")

    # 2) walk up from this script — handles both dev install (skill lives inside Ome365-git)
    #    and packaged install (skill at $HOME/.claude/skills/ticnote-clean/run.py)
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidates.append(parent / ".app" / "ticnote_clean.py")
        candidates.append(parent / "ticnote_clean.py")

    # 3) common install locations
    candidates.extend([
        Path.home() / "Ome365" / ".app" / "ticnote_clean.py",
        Path.home() / "root" / "Ome365" / ".app" / "ticnote_clean.py",
        Path.home() / "root" / "Ome365-git" / ".app" / "ticnote_clean.py",
    ])

    for c in candidates:
        if c.is_file():
            return c
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ticnote-clean",
        description="Clean a TicNote-exported markdown transcript.",
    )
    parser.add_argument("file", help="Path to the TicNote-exported .md file.")
    parser.add_argument("--participants", default=None,
                        help="Comma-separated names to inject into frontmatter.")
    parser.add_argument("--out", default=None,
                        help="Output path. Defaults to overwriting the input file.")
    parser.add_argument("--cleaner", default=None,
                        help="(advanced) explicit path to ticnote_clean.py.")
    args = parser.parse_args()

    cleaner = Path(args.cleaner) if args.cleaner else _locate_cleaner()
    if cleaner is None or not cleaner.is_file():
        print(
            "[ticnote-clean] ERROR · could not locate ticnote_clean.py.\n"
            "  Set OME365_HOME=/path/to/Ome365 or install the skill next to an Ome365 checkout,\n"
            "  or pass --cleaner /path/to/ticnote_clean.py explicitly.",
            file=sys.stderr,
        )
        return 2

    # Rebuild argv for the underlying script (which uses argparse too)
    argv = [str(cleaner), args.file]
    if args.participants:
        argv.extend(["--participants", args.participants])
    if args.out:
        argv.extend(["--out", args.out])

    sys.argv = argv
    runpy.run_path(str(cleaner), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
