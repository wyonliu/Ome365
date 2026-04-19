---
name: ticnote-clean
description: Clean a TicNote-exported markdown transcript — strip UI junk, dedupe, add YAML frontmatter, optional participant injection.
version: 0.1.0
author: Ome365
homepage: https://github.com/wyonliu/Ome365
license: MIT
tags: [transcription, markdown, pkm, tic-note, interview]
runtime: python3
entry: ./run.py
inputs:
  - name: file
    type: path
    required: true
    description: Path to the TicNote-exported .md file (will be rewritten in-place unless --out is given).
  - name: participants
    type: string
    required: false
    description: Comma-separated participant names to inject into frontmatter (e.g. "Alice,Bob").
  - name: out
    type: path
    required: false
    description: Output path. If omitted, the input file is overwritten.
outputs:
  - path: "{{ file }}"
    description: Cleaned markdown (frontmatter + normalized body).
---

# ticnote-clean · TicNote transcript cleaner

**Battle-tested on 800+ real interview transcripts** from a CTO's research pipeline.

## What it does

Takes a raw markdown file exported from TicNote (tencent/xiaomi shadow-mode note app) and:

1. **Strips UI junk** — `新功能` / `Shadow 2.0` / `思维导图` / playback-rate lines (`1.0X`), timestamps (`0:00 / 48:27`), tool toolbars, cloud upsell rows.
2. **Deduplicates** — removes repeated content after "内容由 Shadow 生成".
3. **Keeps the summary & transcript clean** — drops recording title / timestamp lines / tag rows from the summary block.
4. **Adds YAML frontmatter** — `title` / `source: ticnote` / `exported_at` / `participants` (if given) — so the file is ingestable by downstream PKM tools (Obsidian, Ome365, Mindos, etc.).

## Why this matters

TicNote export is messy: each markdown file has 30-50 lines of UI junk, duplicated transcript blocks, and embedded controls — making downstream parsing fragile. This skill is the **exact cleaner** used to process 800+ real interview files in a production cockpit system.

## Usage

```bash
# Claude Code / Claude Desktop (once skill is installed):
Use skill ticnote-clean on ~/Downloads/meeting-export.md with participants "Alice,Bob"

# CLI (direct invocation):
python3 skills/ticnote-clean/run.py ~/Downloads/meeting-export.md --participants "Alice,Bob"
```

## Example

**Before** (excerpt of TicNote raw export):
```
新功能
Shadow 2.0
思维导图
编辑
总结
0:00 / 48:27
1.0X
## 会议要点
- ...
```

**After**:
```markdown
---
title: 会议要点
source: ticnote
exported_at: 2026-04-19
participants: [Alice, Bob]
---

## 会议要点
- ...
```

## License

MIT. Maintained as part of the [Ome365](https://github.com/wyonliu/Ome365) project.
