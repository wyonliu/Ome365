"""
ome365.wiki · v1.1 W6 · Karpathy "wiki is the artifact, not the chat"
[decision: 2026-05-09-wiki-update-query-impl]

Two operations:
  · update(vault, source="Decisions")
      Walk source/*.md → group by category → append `## Pattern · <id> · <date>`
      to Knowledge/L2-distilled/<category>.md (idempotent via <!-- key: ID --> tag)

  · query(vault, q)
      Grep L2-distilled/*.md for query term · return [(path, lineno, block)]

stdlib only · CI-runnable · LLM-distilled is the v1.2 path (gated behind env).
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

# Re-use ome365_eval helpers (frontmatter parser + DecisionRow + grep)
try:
    from ome365_eval import _parse_frontmatter, grep_decisions_all
except ImportError:  # pragma: no cover
    _parse_frontmatter = None
    grep_decisions_all = None


def _vault_root(vault: Optional[Path] = None) -> Path:
    if vault:
        return Path(vault).resolve()
    return Path(os.environ.get("OME365_VAULT", Path(__file__).parent.parent)).resolve()


L2_DIR_REL = Path("Knowledge") / "L2-distilled"
KEY_TAG_RE = re.compile(r"<!--\s*key:\s*([^\s>]+)\s*-->")


# ── Pattern block format ────────────────────────────────────────────────────


def _format_pattern_block(decision_id: str, category: str, claim: str,
                          source_rel: str, anchors: list, when: date) -> str:
    """Emit a Knowledge/L2-distilled markdown block. Idempotency-keyed by decision_id."""
    anchor_pills = " ".join(f"`{a}`" for a in (anchors or []))
    return (
        f"\n## Pattern · {category} · {when.isoformat()}\n"
        f"<!-- key: {decision_id} -->\n\n"
        f"{claim}\n\n"
        f"- **Source**: [{source_rel}]({source_rel})\n"
        + (f"- **Value anchors**: {anchor_pills}\n" if anchors else "")
        + f"- **Distilled**: {when.isoformat()}\n"
    )


# ── update · scan Decisions/ → write L2-distilled/<category>.md ─────────────


def update(vault: Optional[Path] = None, source: str = "Decisions") -> dict:
    """
    Walk vault/<source>/*.md, distill into Knowledge/L2-distilled/<category>.md.
    Idempotent: pattern blocks already containing `<!-- key: <id> -->` are skipped.

    Returns:
      {
        "scanned": int, "appended": int, "skipped_dup": int, "skipped_open": int,
        "files_written": [<path>...]
      }
    """
    if grep_decisions_all is None:
        raise RuntimeError("ome365_eval not importable · cannot scan vault")

    v = _vault_root(vault)
    src_dir = v / source
    if not src_dir.exists():
        return {"scanned": 0, "appended": 0, "skipped_dup": 0, "skipped_open": 0,
                "files_written": []}

    l2_dir = v / L2_DIR_REL
    l2_dir.mkdir(parents=True, exist_ok=True)

    decisions = grep_decisions_all(v)
    today = date.today()

    appended = 0
    skipped_dup = 0
    skipped_open = 0
    files_touched: dict[Path, list[str]] = {}

    for d in decisions:
        if d.status != "closed":
            skipped_open += 1
            continue
        # Re-read file to recover category (DecisionRow doesn't carry it)
        fp = src_dir / f"{d.id}.md"
        if not fp.exists():
            continue
        text = fp.read_text("utf-8")
        meta = _parse_frontmatter(text) if _parse_frontmatter else {}
        category = meta.get("category") or "uncategorized"
        category = re.sub(r"[^\w\-]", "_", str(category)).lower()

        out_fp = l2_dir / f"{category}.md"
        existing = out_fp.read_text("utf-8") if out_fp.exists() else ""
        if f"<!-- key: {d.id} -->" in existing:
            skipped_dup += 1
            continue

        claim = (d.outcome or "(no outcome recorded)").strip().strip('"')
        block = _format_pattern_block(
            decision_id=d.id, category=category, claim=claim,
            source_rel=f"../../{source}/{d.id}.md",
            anchors=d.value_anchors,
            when=d.closed_at or today,
        )
        files_touched.setdefault(out_fp, []).append(block)
        appended += 1

    files_written: list[str] = []
    for out_fp, blocks in files_touched.items():
        header_needed = not out_fp.exists()
        with out_fp.open("a", encoding="utf-8") as f:
            if header_needed:
                f.write(f"# {out_fp.stem}\n\n"
                        f"_Auto-distilled by `ome365 wiki update` · "
                        f"Karpathy LLM-Wiki pattern · file-first._\n")
            for b in blocks:
                f.write(b)
        files_written.append(str(out_fp.relative_to(v)))

    return {
        "scanned": len(decisions),
        "appended": appended,
        "skipped_dup": skipped_dup,
        "skipped_open": skipped_open,
        "files_written": files_written,
    }


# ── query · grep over L2-distilled ──────────────────────────────────────────


def query(q: str, vault: Optional[Path] = None, limit: int = 20) -> list[dict]:
    """
    grep L2-distilled/*.md for `q`. Returns block-level matches.
    Each result: {path, decision_id, category, score, snippet}
    """
    v = _vault_root(vault)
    l2_dir = v / L2_DIR_REL
    if not l2_dir.exists():
        return []

    q_lower = q.lower().strip()
    if not q_lower:
        return []

    results: list[dict] = []
    for fp in sorted(l2_dir.glob("*.md")):
        text = fp.read_text("utf-8")
        # Split into pattern blocks (start at "## Pattern ·")
        blocks = re.split(r"^(?=## Pattern · )", text, flags=re.MULTILINE)
        for block in blocks:
            if not block.lstrip().startswith("## Pattern"):
                continue
            block_lower = block.lower()
            score = block_lower.count(q_lower)
            if score == 0:
                continue
            key_m = KEY_TAG_RE.search(block)
            cat_m = re.match(r"## Pattern · ([^\s·]+)", block)
            results.append({
                "path": str(fp.relative_to(v)),
                "decision_id": key_m.group(1) if key_m else None,
                "category": cat_m.group(1) if cat_m else None,
                "score": score,
                "snippet": block.strip()[:400],
            })
    results.sort(key=lambda r: -r["score"])
    return results[:limit]


# ── CLI helper ──────────────────────────────────────────────────────────────


def cli_main(argv: list[str]) -> int:
    """`./ome365 wiki update | query` entry point (called from ome365 launcher)."""
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(
            "usage:\n"
            "  ome365 wiki update [--source Decisions]\n"
            "  ome365 wiki query 'search term' [--limit 20]\n"
        )
        return 0

    cmd = argv[0]
    rest = argv[1:]
    args: dict = {}
    positional: list[str] = []
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok.startswith("--") and i + 1 < len(rest):
            args[tok.lstrip("-").replace("-", "_")] = rest[i + 1]
            i += 2
        else:
            positional.append(tok)
            i += 1

    if cmd == "update":
        result = update(source=args.get("source", "Decisions"))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if cmd == "query":
        if not positional:
            print("ERROR: query needs a term · ome365 wiki query 'term'", flush=True)
            return 2
        q = " ".join(positional)
        limit = int(args.get("limit", "20"))
        rows = query(q, limit=limit)
        for r in rows:
            print(f"[{r['score']}] {r['path']} · {r['decision_id']}")
            print(f"    {r['snippet'].splitlines()[0] if r['snippet'] else ''}")
        print(f"--- {len(rows)} matches", flush=True)
        return 0

    print(f"ERROR: unknown subcommand '{cmd}' (try update | query)", flush=True)
    return 2


__all__ = ["update", "query", "cli_main"]
