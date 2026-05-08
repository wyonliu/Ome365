---
name: hike-wiki-update
description: |
  Scan vault, distill what's worth keeping into Knowledge/L2-distilled markdown files.
  Implements Karpathy's LLM Wiki Pattern: "the wiki is the artifact, not the chat."
allowed-tools: [Read, Write, Glob]
license: Apache-2.0
ome365:
  author: alice
  created: 2026-05-08
  forks_from: ar9av/obsidian-wiki
  role: Hike
  scope: tenant
  code_mode_compatible: true
---

# Skill: hike-wiki-update

> **Karpathy LLM Wiki Pattern**: instead of asking the LLM the same questions over and
> over, compile knowledge once into interconnected markdown and keep current.
> The Obsidian vault is the viewer; this skill is the maintainer.

## When to use

User says "update the wiki" / "/wiki-update" / "distill" / "extract patterns" / "蒸馏"
on a vault folder.

## Implementation

1. **Scan input scope**: `vault/Knowledge/L1-raw/` OR `vault/Decisions/` OR
   `vault/Notes/` (depending on what user passes).
2. **For each markdown file**:
   - Skip files with `## Pattern · ` already extracted (idempotent)
   - Read full content
   - Extract: 5-10 high-value claims (decisions, lessons, gotchas, references)
3. **Group by category** (auto-cluster):
   - Use existing categories from `vault/Knowledge/L2-distilled/<topic>/` if any
   - Else propose new category·write proposal to `Knowledge/L2-distilled/.proposals/`
4. **Append** (NEVER overwrite):
   ```markdown
   ## Pattern · <category> · 2026-MM-DD

   <distilled claim 1> · source: [<file>](path) · evidence: <quote>
   <distilled claim 2> · ...
   ```

## Quality gates

- Output file count ≤ 1.5 × input file count (no exploding)
- Each pattern entry must have explicit `source: [file](path)` for audit
- No PII leakage·strip emails / phones via `scripts/scan_pii.py`
- Idempotent re-run: same input → no diff (compare hash)

## Citations

- Karpathy LLM Wiki gist: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- Reference implementation: https://github.com/Ar9av/obsidian-wiki
- Hike L4 design: docs/hike.md
