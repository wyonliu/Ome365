---
name: truthguard
description: Guard docs against ASR mishearings, typos, and LLM hallucinations by enforcing a canonical truth-of-record (people/orgs/products/channels).
version: 0.1.0
author: Ome365
homepage: https://github.com/wyonliu/Ome365
license: MIT
tags: [truth-of-record, asr-correction, lint, ci, data-hygiene]
runtime: python3
entry: ./run.py
inputs:
  - name: command
    type: string
    required: true
    description: One of `scan`, `fix`, `lint`, `check`, `list`.
  - name: target
    type: path
    required: false
    description: File or directory to scan/fix (default — current directory).
  - name: truth
    type: path
    required: false
    description: Path to truth.yml (default — ./truth.yml relative to run.py).
  - name: dry_run
    type: flag
    required: false
    description: For `fix` — preview replacements without writing files.
outputs:
  - description: Grouped violation report (scan/lint) or in-place edits (fix).
---

# truthguard · canonical-truth enforcer

Keeps documents, reports, and memory files aligned with a single source of truth. Built to stop ASR mishearings (`Alice → 用户`, `Carol → Carrol`, `OldUnit → NewUnit`), typos, and LLM hallucinations from contaminating downstream content.

## Commands

```bash
# scan a tree — show all violations grouped by severity
python3 skills/truthguard/run.py scan .

# auto-fix safe violations (only alias rules with autofix=true)
python3 skills/truthguard/run.py fix .
python3 skills/truthguard/run.py fix . --dry-run

# CI gate — non-zero exit if any must-fix remains
python3 skills/truthguard/run.py lint .

# check a single snippet (stdin or arg)
python3 skills/truthguard/run.py check "Alice总昨天说……"

# list what the truth file declares
python3 skills/truthguard/run.py list
```

## Severity levels

| Level | Meaning | CI exit |
|-------|---------|---------|
| `must` | Hard alias (e.g. `Alice → 用户`) — definitely wrong | ❌ fail |
| `maybe` | Deprecated/soft patterns needing human call | ⚠️ warn |
| `info`  | Honorific/nickname or mapping-table rows — fine to leave | ✅ ok |

## What it guards against

1. **ASR homophone errors** — `Alice/Alize/Alise → 用户`, `Boby/Bobi → Bob`, `Claude Code → Claude Code`
2. **Renamed entities** — `OldUnit → NewUnit` (2026-04-16 rename), `OldOrg → NewOrg`
3. **Org structure drift** — C-code / N-code labels reverting to old owners
4. **Typos** — `Carol → Carrol`, `曾辉 → —`

## What it does NOT touch

- `TicNote/**` — raw transcripts are ground-truth recordings
- `99-archive/**`, `99-audit/**` — historical / audit logs legitimately quote wrong spellings
- `skills/truthguard/**` — the rule file itself
- Lines inside YAML alias blocks (`aliases: / - Alice`)
- Lines with strong doc-example keywords (`ASR / 误为 / 血泪 / 召回 / 张冠李戴`)
- Quoted literals / markdown bold / parenthetical disambiguation `刘怀阳（—）`
- JSON fields `"pattern" / "replacement" / "fix"`

## Usage patterns

**Pre-commit hook** — block commits that regress canonical spellings:
```bash
python3 skills/truthguard/run.py lint . || exit 1
```

**ASR ingest gate** — after TicNote export cleaning, before vault write:
```bash
python3 skills/truthguard/run.py fix path/to/fresh-transcript.md
```

**LLM hallucination check** — after any generated report, lint before publish:
```bash
python3 skills/truthguard/run.py lint Projects/Acme/reports/
```
