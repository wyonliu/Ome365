---
name: dev-decision-workflow
description: |
  Force "create-decision-before-code" workflow per Kevin SKILL spec (example-vendor 2026-04 范式).
  Every code commit must cite a Decision via [decision: <id>] in commit message.
allowed-tools: [Bash, Write]
license: Apache-2.0
ome365:
  author: alice
  created: 2026-05-08
  role: Workflow
  scope: tenant
  enforces: pre-commit
  code_mode_compatible: false
---

# Skill: dev-decision-workflow (Kevin 范式)

> "先建文件再改代码" — example-vendor Kevin SKILL 规范，by way of A4S v2.0 §6.3.

## When to use

System-level workflow · runs as `commit-msg` git hook (`.githooks/commit-msg`).
Every code commit (`.app/`, `scripts/`, `tests/*.py`) is checked.

## The 4 rules

1. **Open** a decision FIRST: `./ome365 decision new "Pick vendor for X" --owner you`
   → creates `vault/Decisions/2026-MM-DD-pick-vendor.md` with `status: open`
2. **Code** the change · git commit message must contain `[decision: 2026-MM-DD-pick-vendor]`
3. **Close** the decision after merge: `./ome365 decision close <id> --outcome "X" --value-anchors P,L`
   → fills `outcome` / `value_anchors` / `status: closed`
4. **Backfill** ROI 90 days later (auto via `nightly distill_outcomes`): roi_actual filled

## Bypass rules (legitimate non-decision commits)

The hook auto-skips:
- `chore:` / `docs:` / `merge:` / `revert:` / `fixup:` / `amend:` / `test:` / `ci:` / `build:` / `style:` / `refactor:` 前缀
- Commits with NO `.app/` / `scripts/` / `tests/*.py` files
- `OME365_NO_DECISION=1 git commit ...` (last-resort bypass · use sparingly)

## Quality gates

- All 4 stages must complete · open → code → close → backfill
- `[decision: ID]` must match an actual file in `vault/Decisions/`
- `value_anchors` at close time must be from set: `[P, XL, L, M, 维护性, Revert]`
- Decision file `⑤ Execution log` should reference the commit hash

## Why (rationale)

3 months later, when you (or your successor) reads git log:
- WITHOUT decision tag: "fix(api): correct response format" → no context, mystery
- WITH decision tag: "fix(api): [decision: 2026-05-08-api-v2] correct response format"
  → 1 click to Decision · see ① problem ② data ③ models ④ options ⑤ execution log → full why

This is the foundation of Hike L4 (Wiki Maintainer · Karpathy pattern):
**every code change becomes a queryable knowledge artifact**.
