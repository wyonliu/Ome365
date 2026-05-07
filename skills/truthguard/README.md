# truthguard

**Anti-contamination skill for PKM / research vaults.**
Keeps docs aligned with a canonical `truth.yml` — catches ASR mishearings, typos, renames, and LLM hallucinations before they land.

## The problem

A CTO's vault ingests:
- **ASR transcripts** (TicNote / shadow-mode recorders) — homophones miss names like `Alice` instead of `用户`
- **LLM-generated reports** — models invent plausible-but-wrong names
- **Copy-paste from chat** — `OldUnit` (renamed to `NewUnit` months ago) creeps back
- **Deprecated org labels** — `C3 OldOrg` after the re-org made it `C3 NewOrg`

One wrong name in a report sent upward to the chairman is a real incident.
Manual review does not scale past a few hundred files.

## The design

### 1. Truth-of-record (`truth.yml`)

Single YAML file is the only source of truth. Five sections:

- `people` — `canonical` + `role` + `aliases` (hard, autofix) + `nicknames` (soft, info)
- `channels` — C1-C5 / N1-N3 with owners and `deprecated_labels`
- `bus` — acme BUs with `rename_rule` + `exceptions` (history-safe)
- `terms` — product / tech names (Claude Code, Secondary, Dify…)
- `patterns` — regex-level deprecated phrasings

### 2. Severity-graded enforcement

Not every match is an error. Three tiers:

- **must** — hard aliases, definitely wrong spellings → block commits
- **maybe** — deprecated labels, context-sensitive → warn for review
- **info** — honorifics (`包总`), mapping-table rows, doc examples → do not touch

### 3. Multi-layer false-positive suppression

Chinese text has no `\b`, so naive regex breaks. Suppression stack:

1. **CJK word boundary** — `(?<![\u4e00-\u9fff])X(?![\u4e00-\u9fff])` for 2-3 char aliases, prevents `景优` matching inside `场景优先级`
2. **Path excludes** — `TicNote/**` (raw ground truth), `99-archive/**`, `99-audit/**`
3. **YAML block state machine** — skip list items under `aliases:` / `nicknames:` / `ASR:`
4. **Doc-example keywords** — lines containing `ASR / 误为 / 血泪 / 召回 / 张冠李戴 / 校准` are quoting the problem, not exhibiting it
5. **Quote/bold/paren detection** — `"Alice"` or `**Alice**` or `（—）` signals literal mention
6. **JSON field exclusions** — `"pattern" / "replacement" / "fix"` keys intentionally hold alias text
7. **Mapping-table heuristic** — alias + canonical separated by `→ | - :` on same line → info, never autofix

### 4. Autofix is conservative by default

Only rules explicitly marked `autofix: true` on the rule or container rewrite files. Everything else is report-only. `fix --dry-run` previews before writing.

## Battle results

Initial full-vault scan of a real CTO research vault (Ome365):
- **1183 must-fix** raw violations flagged (naive regex)
- **311 real replacements** applied to **54 files** after 4 rounds of false-positive suppression
- **0 residual must-fix** after autofix
- Remaining 90 info-level hits are all correctly tagged (contact-card alias tables, intentional product alias lists)

High-volume fixed files included:
- `exampleBU-OldUnit-—·大会员平台发展·2026-04-08.md` — 42 fixes (pre-rename artifact)
- `大会员BU·—·处方卡·2026-04-11.md` — 37 fixes

## Integration points

### Pre-commit hook (`.git/hooks/pre-commit`)
```bash
#!/usr/bin/env bash
python3 skills/truthguard/run.py lint . || {
  echo "truthguard found canonical-truth violations — run fix or review."
  exit 1
}
```

### ASR pipeline (after TicNote export)
```bash
# clean → truthguard → write
python3 skills/ticnote-clean/run.py raw.md
python3 skills/truthguard/run.py fix raw.md
mv raw.md TicNote/2026-04-20/finished/
```

### Report generation (gate before publish)
```bash
python3 skills/truthguard/run.py lint Projects/Acme/reports/ || exit 1
```

### Cockpit / editor surface
The `scan` JSON output can feed a red-dot indicator in the driving cockpit — any non-zero `must` count blocks "publish" button.

## Updating the truth file

`truth.yml` is versioned — every change should bump `meta.version` and list a source in `meta.sources`. Rule of thumb:

- **canonical** = the right spelling (only add with a source)
- **aliases** = wrong spellings that unambiguously map to canonical (autofix-safe)
- **nicknames** = honorifics / informal — info-only, never autofix
- **confusables / exceptions** = historical or ambiguous cases — document the reason inline

Every alias decision that was a false positive in v1 (e.g. `金优 ≠ 实例`, `刘怀阳` ambiguous between `—` / `用户`) is recorded in the `notes:` field so the reasoning survives rotation.

## Why not just global find-replace?

- Breaks history (`99-audit/` docs legitimately contain wrong spellings)
- Breaks YAML rule files (recursively rewrites their own alias lists)
- Breaks JSON configs with `"replacement"` fields
- Mangles CJK substrings (`场景优先 → 场景优先`)
- Can't distinguish `包总 (honorific, keep)` from `包伟 (canonical)`

truthguard encodes this judgment once in the rule file + suppression layers, then applies it uniformly.

## License

MIT. Part of the [Ome365](https://github.com/wyonliu/Ome365) project.
