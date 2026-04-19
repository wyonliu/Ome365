# ticnote-clean

Anthropic `SKILL.md` package · v0.1.0

A production-grade markdown cleaner for [TicNote](https://ticnote.tencent.com/) transcript exports. Strips UI junk, deduplicates, injects YAML frontmatter.

**Battle-tested:** 800+ real interview files from a CTO research pipeline.

## Install

```bash
# via skills.sh (once published)
skills install ticnote-clean

# local dev (inside this repo)
export OME365_HOME=$(pwd)
python3 skills/ticnote-clean/run.py --help
```

## Use

```bash
# overwrite in place
python3 skills/ticnote-clean/run.py ~/Downloads/export.md

# inject participants into frontmatter
python3 skills/ticnote-clean/run.py ~/Downloads/export.md \
  --participants "Alice,Bob"

# write to new path
python3 skills/ticnote-clean/run.py input.md --out cleaned.md
```

## Inside Claude Code / Claude Desktop

Once installed as a skill, just ask Claude:

> Clean the ticnote export at `~/Downloads/team-sync.md` with participants `Alice, Bob`.

Claude will invoke `ticnote-clean` with the right args.

## What gets cleaned

- `新功能` / `Shadow 2.0` / `思维导图` / `播客` toolbar rows
- Playback-rate lines (`1.0X`, `1.5X`)
- Timestamp lines (`0:00 / 48:27`)
- `内容由 Shadow 生成` duplicated blocks
- Recording-title echo rows / tag rows in summary block
- TicNote cloud-upsell rows

## What gets added

- YAML frontmatter (`title`, `source`, `duration`, `participants`)
- Clean section boundaries (`## 总结` / `## 转录`)

## Maintained by

Part of [Ome365](https://github.com/wyonliu/Ome365). Issues / PRs welcome.
