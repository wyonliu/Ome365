#!/usr/bin/env python3
"""
truthguard · guard against ASR/typo/hallucination contamination.

Usage:
  python3 run.py scan <path>        # report violations (default path: cwd)
  python3 run.py fix  <path>        # autofix unambiguous violations in-place
  python3 run.py lint <path>        # exit 1 if any must-fix; CI gate
  python3 run.py check "<text>"     # validate a string, exit 1 if bad
  python3 run.py list               # show truth.yml contents (human-readable)

Flags:
  --truth <file>       override truth file (default: ./truth.yml next to this script)
  --ext md,json,py     comma-separated extensions to scan (default: md,json,yaml,yml)
  --exclude PAT        glob to exclude (repeatable); defaults cover node_modules, .git, etc.
  --context N          lines of context around each violation (default 0)
  --format text|json   output format (default text)
  --no-color           disable ANSI
  --stdin              read one document from stdin (only with scan/check)

Exit codes:
  0 clean / only info
  1 must-fix violations present (use with lint)
  2 usage error
"""
from __future__ import annotations
import argparse
import fnmatch
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import yaml  # requirement: pyyaml (already in repo requirements.txt)

HERE = Path(__file__).resolve().parent
DEFAULT_TRUTH = HERE / "truth.yml"

# ANSI colors
class C:
    R = "\033[31m"; Y = "\033[33m"; G = "\033[32m"; B = "\033[36m"
    BOLD = "\033[1m"; DIM = "\033[2m"; END = "\033[0m"

def _off():
    for k in ("R","Y","G","B","BOLD","DIM","END"):
        setattr(C, k, "")

# ----------------------------------------------------------------------------
# Truth loader
# ----------------------------------------------------------------------------

@dataclass
class Rule:
    """A single check. One of: alias/pattern/deprecated-label."""
    id: str                    # stable rule id
    kind: str                  # 'alias' | 'pattern' | 'deprecated_label' | 'context'
    pattern: re.Pattern
    canonical: str             # the right spelling (empty if fix is deletion/unknown)
    autofix: bool
    severity: str              # 'must' | 'maybe' | 'info'
    reason: str
    exceptions: list[str] = field(default_factory=list)

# Chinese chars that are NOT allowed to sit next to a 2-char CJK alias —
# if an alias is embedded between CJK chars, it's almost always part of a bigger word.
# We over-approximate: for 2-char CJK aliases, require the neighbor char to be non-CJK
# (whitespace / punctuation / ASCII / line boundary).  4+ char aliases are unique enough
# that we skip this guard.
_CJK = r"\u4e00-\u9fff"
_CJK_EXT = r"\u3400-\u4dbf\U00020000-\U0002a6df"

def _alias_to_pattern(alias: str) -> re.Pattern:
    esc = re.escape(alias)
    # ASCII alias: strict ASCII-word boundary
    if re.match(r"^[A-Za-z0-9 _\-.]+$", alias):
        return re.compile(rf"(?<![A-Za-z0-9]){esc}(?![A-Za-z0-9])")
    # Short CJK alias (2-3 chars): require non-CJK neighbors to avoid substring matches
    #   e.g. 景优 must not match inside 场景优化
    cjk_count = sum(1 for c in alias if "\u4e00" <= c <= "\u9fff")
    if 2 <= cjk_count <= 3 and all("\u4e00" <= c <= "\u9fff" for c in alias):
        return re.compile(rf"(?<![{_CJK}{_CJK_EXT}]){esc}(?![{_CJK}{_CJK_EXT}])")
    return re.compile(esc)

def load_truth(path: Path) -> list[Rule]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules: list[Rule] = []

    # people: hard aliases (autofix) + soft nicknames (info only)
    for person in data.get("people") or []:
        canon = person["canonical"]
        for a in person.get("aliases") or []:
            rules.append(Rule(
                id=f"person.{canon}.{a}",
                kind="alias",
                pattern=_alias_to_pattern(a),
                canonical=canon,
                autofix=True,
                severity="must",
                reason=f"人名别名 → 正名（{person.get('role','')}）".strip(),
            ))
        for n in person.get("nicknames") or []:
            rules.append(Rule(
                id=f"person.{canon}.nick.{n}",
                kind="alias",
                pattern=_alias_to_pattern(n),
                canonical=canon,
                autofix=False,
                severity="info",
                reason=f"敬称/昵称 ≡ {canon}（{person.get('role','')}）".strip(),
            ))

    # channels: deprecated_labels → canonical label; N3=其他创新 etc.
    for ch in data.get("channels") or []:
        code = ch["code"]
        label = ch.get("label") or ""
        for bad in ch.get("deprecated_labels") or []:
            esc = re.escape(bad)
            rules.append(Rule(
                id=f"channel.{code}.deprecated.{bad}",
                kind="deprecated_label",
                pattern=re.compile(rf"{code}\s*{esc}"),
                canonical=f"{code} {label}".strip(),
                autofix=True,
                severity="must",
                reason=f"航道 {code} 旧标签 → 新标签",
            ))

    # BUs: e.g. OldUnit → NewUnit (with context exceptions)
    for bu in data.get("bus") or []:
        canon = bu["canonical"]
        for a in bu.get("aliases") or []:
            rules.append(Rule(
                id=f"bu.{canon}.{a}",
                kind="alias",
                pattern=_alias_to_pattern(a),
                canonical=canon,
                autofix=bool(bu.get("autofix", False)),
                severity="must" if bu.get("autofix") else "maybe",
                reason=bu.get("rename_rule") or f"{a} → {canon}",
                exceptions=list(bu.get("exceptions") or []),
            ))

    # terms: product/tech aliases
    for t in data.get("terms") or []:
        canon = t["canonical"]
        for a in t.get("aliases") or []:
            rules.append(Rule(
                id=f"term.{canon}.{a}",
                kind="alias",
                pattern=_alias_to_pattern(a),
                canonical=canon,
                autofix=True,
                severity="must",
                reason=f"产品/术语别名 → 正名",
            ))

    # explicit patterns
    for p in data.get("patterns") or []:
        rules.append(Rule(
            id=f"pattern.{p['id']}",
            kind="pattern",
            pattern=re.compile(p["pattern"]),
            canonical=p.get("fix") or "",
            autofix=bool(p.get("autofix", False)),
            severity="must" if p.get("autofix") else "maybe",
            reason=p.get("reason") or "",
        ))

    return rules

# ----------------------------------------------------------------------------
# Scanner
# ----------------------------------------------------------------------------

@dataclass
class Hit:
    file: str
    line: int
    col: int
    matched: str
    rule: Rule
    line_text: str

def _line_has_exception(line: str, rule: Rule) -> bool:
    return any(exc in line for exc in rule.exceptions)

def _is_self_truth_file(p: Path, truth_path: Path) -> bool:
    """Don't flag truth.yml or files inside the skill dir."""
    try:
        return p.resolve() == truth_path.resolve() or truth_path.parent in p.resolve().parents
    except Exception:
        return False

_JSON_REPL_RE = re.compile(r'"(replacement|fix|canonical|to|正名|pattern|alias|from|wrong|误|旧|误写|别名)"\s*:\s*"')
_FRONTMATTER_TAG_RE = re.compile(r"^\s*tags\s*:", re.IGNORECASE)
# YAML list entry under an aliases/nicknames/误 block, e.g.
#   aliases:
#     - Alice     ← should not flag
_YAML_LIST_RE = re.compile(r"^\s*[-*]\s*")
# Documentation-example keywords: if a line mentions any of these AND the alias appears
# inside quotes, treat as info-only (it's documenting the error, not making one).
_DOC_EXAMPLE_KW = re.compile(
    r"ASR|误|例|示例|sample|alias|别名|搜索|搜一下|查找|blacklist|黑名单|反例|"
    r"血泪|教训|真人|错位|错写|召回|找不到|张冠李戴|音同|常误为|校准|Fact.?Check|误转",
    re.IGNORECASE,
)
# "Strong" doc-keywords — their presence alone flags the whole line as info, even without quotes.
_STRONG_DOC_KW = re.compile(
    r"ASR|误为|常误为|误转|错写|别名|音同|校准|blacklist|黑名单|反例|张冠李戴|被当真人",
)
_QUOTED_RE = re.compile(r"""["'"'「『](.+?)["'"'」』]""")

def _is_doc_example_quote(line: str, matched: str) -> bool:
    """Detect patterns like:  搜"Alice"找不到 / 误为"X" / sample "X"
    where the alias is quoted inside a documentation line."""
    # Strong doc-keyword on the line → skip every match on this line (it's a correction note)
    if _STRONG_DOC_KW.search(line):
        return True
    if not _DOC_EXAMPLE_KW.search(line):
        return False
    # alias inside any bracket/quote counts as an example
    for m in _QUOTED_RE.finditer(line):
        if matched in m.group(1):
            return True
    # markdown bold/italic: **alias** or *alias*
    if re.search(rf"\*{re.escape(matched)}\*", line):
        return True
    # alias inside (...) or （...） with slash-separated items — e.g. (X / Y / Z)
    paren_contents = re.findall(r"[（(]([^)）]{2,60})[)）]", line)
    for pc in paren_contents:
        if matched in pc and ("/" in pc or "、" in pc or "," in pc or "，" in pc):
            return True
    return False

def scan_text(text: str, rules: list[Rule], *, file: str = "<stdin>") -> list[Hit]:
    hits: list[Hit] = []
    lines = text.splitlines()
    # Detect YAML list entries under an aliases/nicknames/ASR block:
    # track the last "aliases:" / "nicknames:" / "ASR:" key we saw and how indented.
    in_alias_block_indent: int = -1
    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        # enter alias block
        if re.match(r"^(aliases|nicknames|别名|ASR|误写|误为|误转|asr_fixes|误)\s*:\s*$", stripped, re.IGNORECASE):
            in_alias_block_indent = indent
            continue
        # exit alias block when dedented back to or past header indent
        if in_alias_block_indent >= 0 and stripped and indent <= in_alias_block_indent \
                and not _YAML_LIST_RE.match(line):
            in_alias_block_indent = -1
        in_alias_block = (in_alias_block_indent >= 0 and _YAML_LIST_RE.match(line) is not None)

        # Skip lines that are JSON "replacement"/"fix" values — they hold canonical text by design
        skip_json_value = bool(_JSON_REPL_RE.search(line))
        # Skip lines that are frontmatter `tags:` lists — they intentionally archive variant names
        skip_tags = bool(_FRONTMATTER_TAG_RE.match(line))
        for rule in rules:
            for m in rule.pattern.finditer(line):
                if rule.exceptions and _line_has_exception(line, rule):
                    continue
                if skip_json_value or skip_tags or in_alias_block:
                    hits.append(Hit(file, i, m.start()+1, m.group(0),
                                    _as_info(rule), line))
                    continue
                if _is_doc_example_quote(line, m.group(0)):
                    hits.append(Hit(file, i, m.start()+1, m.group(0),
                                    _as_info(rule), line))
                    continue
                # Mapping-table heuristic: alias and canonical co-exist with a separator
                around = line[max(0, m.start()-30): m.end()+30]
                if rule.canonical and rule.canonical in around and \
                   re.search(r"[→\-=|:→\|]|\bto\b", around):
                    hits.append(Hit(file, i, m.start()+1, m.group(0),
                                    _as_info(rule), line))
                    continue
                # Parenthetical disambiguation:  alias（CJK姓名/说明） or alias(text)
                #   e.g. "刘怀阳（—）" means 刘怀阳 is an ASR note for —, not the rule's canonical
                tail = line[m.end(): m.end()+16]
                if re.match(r"^[（(][\u4e00-\u9fff A-Za-z0-9·\-/，,]+[)）]", tail):
                    hits.append(Hit(file, i, m.start()+1, m.group(0),
                                    _as_info(rule), line))
                    continue
                hits.append(Hit(file, i, m.start()+1, m.group(0), rule, line))
    return hits

def _as_info(rule: Rule) -> Rule:
    return Rule(
        id=rule.id, kind=rule.kind, pattern=rule.pattern,
        canonical=rule.canonical, autofix=False,
        severity="info", reason=rule.reason + "（映射表行，跳过自动修）",
        exceptions=rule.exceptions,
    )

# ----------------------------------------------------------------------------
# File walker
# ----------------------------------------------------------------------------

DEFAULT_EXCLUDES = [
    "**/.git/**", "**/node_modules/**", "**/__pycache__/**", "**/.venv/**",
    "**/venv/**", "**/.mypy_cache/**", "**/.pytest_cache/**",
    "**/ai-tmp/**", "**/share_snapshots/**", "**/.app/_dev_cache/**",
    "**/TicNote-*.md",            # raw transcript file naming pattern
    "**/TicNote/**",              # all raw TicNote exports — ASR noise is ground truth, preserve
    "**/tic-note/**",             # variant folder naming
    "**/99-archive/**",           # archived旧版 (historical, preserve verbatim)
    "**/99-audit/**",             # audit logs documenting the errors (contain alias literals by design)
    "**/skills/truthguard/**",    # the skill itself
]

def iter_files(root: Path, exts: list[str], excludes: list[str]) -> Iterable[Path]:
    root = root.resolve()
    ext_set = {e.lower().lstrip(".") for e in exts}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lstrip(".").lower() not in ext_set:
            continue
        rel = str(p.relative_to(root) if root in p.parents or p == root else p)
        full = str(p)
        if any(fnmatch.fnmatch(full, pat) for pat in excludes):
            continue
        yield p

# ----------------------------------------------------------------------------
# Fix
# ----------------------------------------------------------------------------

def fix_text(text: str, rules: list[Rule]) -> tuple[str, int]:
    """Apply autofix rules. Only replaces hits that scan_text would rank 'must'.

    Reuses scan_text's full suppression pipeline (YAML alias block state, JSON
    replacement fields, doc-example keywords, quote/bold/paren detection, mapping
    tables) so that fix NEVER touches anything scan marks info or maybe.
    """
    hits = scan_text(text, rules, file="<fix>")
    # index must-fix hits by (line, col, length) for O(1) lookup during rewrite
    targets: dict[tuple[int, int], tuple[str, str]] = {}
    for h in hits:
        if h.rule.severity != "must":
            continue
        if not h.rule.autofix or not h.rule.canonical:
            continue
        targets[(h.line, h.col)] = (h.match, h.rule.canonical)
    if not targets:
        return text, 0
    # Rewrite line by line to keep columns stable
    lines = text.splitlines(keepends=True)
    n = 0
    for i, raw in enumerate(lines, start=1):
        # Find all target cols on this line, apply right-to-left to preserve col indices
        cols = sorted([c for (ln, c) in targets if ln == i], reverse=True)
        if not cols:
            continue
        new_line = raw
        for col in cols:
            match_str, canonical = targets[(i, col)]
            start = col - 1  # col is 1-indexed
            end = start + len(match_str)
            if new_line[start:end] != match_str:
                # column shifted due to earlier replacement — skip to avoid corruption
                continue
            new_line = new_line[:start] + canonical + new_line[end:]
            n += 1
        lines[i - 1] = new_line
    return "".join(lines), n

# ----------------------------------------------------------------------------
# Reporters
# ----------------------------------------------------------------------------

def print_text_report(hits: list[Hit], *, show_context: int = 0) -> None:
    if not hits:
        print(f"{C.G}✓ no violations{C.END}")
        return
    by_sev = {"must": [], "maybe": [], "info": []}
    for h in hits:
        by_sev.setdefault(h.rule.severity, []).append(h)
    order = [("must", C.R, "A. 必须修"),
             ("maybe", C.Y, "B. 可能要修"),
             ("info",  C.B, "C. 仅提示")]
    for sev, color, title in order:
        group = by_sev.get(sev) or []
        if not group:
            continue
        print(f"\n{color}{C.BOLD}{title}  ({len(group)} 条){C.END}")
        # group by rule.id within severity
        by_rule: dict[str, list[Hit]] = {}
        for h in group:
            by_rule.setdefault(h.rule.id, []).append(h)
        for rid, hs in sorted(by_rule.items(), key=lambda kv: -len(kv[1])):
            r = hs[0].rule
            tgt = f" → {C.BOLD}{r.canonical}{C.END}" if r.canonical else ""
            afx = " [autofix]" if r.autofix else ""
            print(f"  {C.DIM}{rid}{C.END}{tgt}{afx}  {C.DIM}// {r.reason}{C.END}")
            for h in hs[:50]:
                print(f"    {h.file}:{h.line}:{h.col}  {h.matched}")
                print(f"      {C.DIM}{h.line_text.strip()[:160]}{C.END}")
            if len(hs) > 50:
                print(f"    {C.DIM}... +{len(hs)-50} more{C.END}")

    # summary
    must = len(by_sev.get("must") or [])
    maybe = len(by_sev.get("maybe") or [])
    info = len(by_sev.get("info") or [])
    files = len({h.file for h in hits})
    print(f"\n{C.BOLD}== Summary =={C.END}  files: {files}  must: {C.R}{must}{C.END}  maybe: {C.Y}{maybe}{C.END}  info: {C.B}{info}{C.END}")

def json_report(hits: list[Hit]) -> str:
    return json.dumps([
        {
            "file": h.file, "line": h.line, "col": h.col,
            "matched": h.matched,
            "rule_id": h.rule.id,
            "severity": h.rule.severity,
            "autofix": h.rule.autofix,
            "fix": h.rule.canonical,
            "reason": h.rule.reason,
            "line_text": h.line_text,
        } for h in hits
    ], ensure_ascii=False, indent=2)

# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------

def cmd_scan(args) -> int:
    rules = load_truth(Path(args.truth))
    truth_path = Path(args.truth)
    exts = [e.strip() for e in args.ext.split(",") if e.strip()]
    excludes = list(DEFAULT_EXCLUDES) + (args.exclude or [])

    if args.stdin:
        text = sys.stdin.read()
        hits = scan_text(text, rules, file="<stdin>")
    else:
        root = Path(args.path).resolve()
        if root.is_file():
            targets = [root]
        else:
            targets = list(iter_files(root, exts, excludes))
        hits = []
        for p in targets:
            if _is_self_truth_file(p, truth_path):
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            hits.extend(scan_text(text, rules, file=str(p)))

    if args.format == "json":
        print(json_report(hits))
    else:
        print_text_report(hits)
    must = sum(1 for h in hits if h.rule.severity == "must")
    return 1 if (args.lint and must) else 0

def cmd_lint(args) -> int:
    args.lint = True
    return cmd_scan(args)

def cmd_fix(args) -> int:
    rules = load_truth(Path(args.truth))
    truth_path = Path(args.truth)
    exts = [e.strip() for e in args.ext.split(",") if e.strip()]
    excludes = list(DEFAULT_EXCLUDES) + (args.exclude or [])

    root = Path(args.path).resolve()
    targets = [root] if root.is_file() else list(iter_files(root, exts, excludes))

    total = 0
    touched = 0
    for p in targets:
        if _is_self_truth_file(p, truth_path):
            continue
        try:
            original = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        new, n = fix_text(original, rules)
        if n == 0:
            continue
        total += n
        touched += 1
        if args.dry_run:
            print(f"{C.Y}[dry]{C.END} {p}  {n} fixes")
        else:
            p.write_text(new, encoding="utf-8")
            print(f"{C.G}[fix]{C.END} {p}  {n} fixes")
    tag = "would fix" if args.dry_run else "fixed"
    print(f"\n{C.BOLD}{tag}{C.END}: {total} replacements across {touched} files")
    return 0

def cmd_check(args) -> int:
    rules = load_truth(Path(args.truth))
    hits = scan_text(args.text, rules, file="<arg>")
    if args.format == "json":
        print(json_report(hits))
    else:
        print_text_report(hits)
    must = sum(1 for h in hits if h.rule.severity == "must")
    return 1 if must else 0

def cmd_list(args) -> int:
    data = yaml.safe_load(Path(args.truth).read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    print(f"{C.BOLD}truthguard truth.yml v{meta.get('version')}{C.END}  ({meta.get('updated')})")
    print(f"  people: {len(data.get('people') or [])}")
    print(f"  channels: {len(data.get('channels') or [])}")
    print(f"  bus: {len(data.get('bus') or [])}")
    print(f"  terms: {len(data.get('terms') or [])}")
    print(f"  patterns: {len(data.get('patterns') or [])}")
    print(f"\n{C.DIM}sources:{C.END}")
    for s in meta.get("sources") or []:
        print(f"  - {s}")
    return 0

# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="truthguard", description=__doc__)
    ap.add_argument("--truth", default=str(DEFAULT_TRUTH))
    ap.add_argument("--ext", default="md,json,yaml,yml,py,html,js")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--stdin", action="store_true")

    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("scan")
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--lint", action="store_true")
    sp.set_defaults(func=cmd_scan)

    lp = sub.add_parser("lint")
    lp.add_argument("path", nargs="?", default=".")
    lp.set_defaults(func=cmd_lint)

    fp = sub.add_parser("fix")
    fp.add_argument("path", nargs="?", default=".")
    fp.add_argument("--dry-run", action="store_true")
    fp.set_defaults(func=cmd_fix)

    cp = sub.add_parser("check")
    cp.add_argument("text")
    cp.set_defaults(func=cmd_check)

    lsp = sub.add_parser("list")
    lsp.set_defaults(func=cmd_list)

    return ap

def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.no_color or not sys.stdout.isatty():
        _off()
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
