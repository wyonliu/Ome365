# Team Onboarding · 5-minute walkthrough

> Audience: a teammate who has just been told "we're trying Ome365 for our team brain."
> Goal: in 5 minutes, this teammate has the cockpit open, understands what each
> card means, and has written one Decision file.

---

## Minute 1 · Get the cockpit running

```bash
git clone https://github.com/wyonliu/Ome365.git
cd Ome365 && ./ome365
```

That's it. The `./ome365` launcher handles dependency install (Python 3.9+),
copies `.env`, and opens `http://localhost:3650`. If anything fails, run:

```bash
./ome365 doctor   # 12-check diagnostic
```

Visit **http://localhost:3650/v1_1.html** — that's the v1.1 Team Brain cockpit.

You should see 4 cards with **real demo data** (alice / bob / carol / dan / erin).
This is from `vault.example/` — your seed material.

---

## Minute 2 · Read one Decision file

The cockpit's left card lists Decisions. Click any one — it's a plain markdown
file. For example, `vault.example/Decisions/v1-1-scope-team-brain.md`:

```yaml
---
id: v1-1-scope-team-brain
opened: 2026-03-30T09:00:00Z
closed: 2026-04-08T17:00:00Z
status: closed
owner: carol
participants: [alice, bob]
outcome: "8-week file-first build · ship 2026-05-09 · 0 token leaderboards"
value_anchors: [P, XL, L]
---
# Decision: v1.1 scope · Team Brain layer (W1-W8)

## ① Problem definition (human · carol)
v1.0 is a personal vault + share station...
```

Eight sections: problem → data-needs → options → decision → reflection →
execution log → 90-day feedback. **5 sections AI drafts, 3 sections humans
write.** This is the unit of work in Ome365.

---

## Minute 3 · Understand the 4 cards

### ① Decisions (left top)
Every team decision lives as a `Decisions/<id>.md` file. The card lists recent
ones with their **value_anchors** (`P` = Product growth, `XL/L/M` = scope size,
`Revert` = rolled back, `维护性` = maintenance). Click any decision to read the
full 8-section markdown.

### ② Skills (right top)
SKILL.md files compatible with [Anthropic's open spec](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills).
Each skill has an author and ecosystem. The card shows total + by author.

### ③ Cost-per-Outcome (left bottom)
The **opposite of token leaderboards**. Three rows:
- `cost_per_resolved_decision` — USD per closed Decision file
- `human_equivalent_hourly` — USD per contractor-hour saved
- `revenue_per_workflow` — tracked `roi_actual` per workflow

Plus per-actor breakdown for the rolling window.

### ④ Member Eval (right bottom)
7 dimensions (D1-D7) for the chosen actor. Every score has
`human_review_required: True` baked in. **Do not use these as the sole basis
for HR decisions** — see [`docs/policies/EVAL_USAGE_POLICY.md`](policies/EVAL_USAGE_POLICY.md).

The role-preset switcher (engineer / pm / sales / ops / mixed) changes the
weights used to display the total — the source data is unchanged.

---

## Minute 4 · Write your first Decision

Open a terminal in the project root:

```bash
./ome365 decision new "Pick our team's first agent" --owner you
```

This creates `Decisions/2026-MM-DD-pick-our-teams-first-agent.md` with the
8-section template. Fill in:

1. **Problem** — what are you actually deciding?
2. **Options** — list 2-3 with trade-offs
3. **Decision** — pick one + write the rationale

Then close it:

```bash
./ome365 decision close <id> --outcome "we picked Codex CLI" \
    --value-anchors P,L
```

Refresh `/v1_1.html` — your decision appears in card ①.

---

## Minute 5 · The Kevin "先文件再代码" rule

Once you start writing code on this repo, the git hook enforces:

> Every code commit must cite a Decision via `[decision: <id>]` in the commit
> message.

Why: 6 months from now, your replacement should be able to git-blame any line
of code → find the commit → read the linked Decision → understand *why*.

Bypass for emergency: `OME365_NO_DECISION=1 git commit ...`. The hook auto-
skips `chore:`, `docs:`, `merge:`, `revert:` prefixes.

---

## What to do next

- **Read** `docs/strategy/MASTER-PLAN.md` — the 12-month roadmap
- **Read** `docs/policies/EVAL_USAGE_POLICY.md` — how eval scores can/can't be used
- **Subscribe** to `vault/Trace/<date>.jsonl` updates if you want raw events
- **Run** `./ome365 wiki update` — distill last-90-day Decisions into
  `Knowledge/L2-distilled/<category>.md` (Karpathy LLM Wiki Pattern)

---

## Common questions in the first hour

**Q: Why markdown files instead of a database?**
A: Git-friendly, grep-friendly, AI-friendly, regulator-friendly (auditors can
read source-of-truth without a query tool). Performance is fine through ~1k
decisions; we ship a `team-distribution.json` cache for larger.

**Q: Why does my eval score show "insufficient_sample"?**
A: Each dimension needs ≥5 closed decisions in the window. Either widen the
window (`window_days=365`) or close more decisions. Statistically, fewer than
5 samples is noise.

**Q: Where do I put non-decision notes?**
A: Whatever `Notes/<date>.md` convention works for your team. Ome365 doesn't
opinion on those — only Decisions / Skills / Trace are evaluated.

**Q: Can I bring my own LLM key?**
A: Yes. Set `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / etc in `.env`. Defaults
are Ollama local + bge-small-zh-v1.5 local embedding. PIPL §38 default-compliant.

**Q: What's NOT in v1.1?**
A: LLM-distilled wiki (rule-based for now), semantic search (sqlite-vec opt-in),
real ed25519 signing on agent-card. All in v1.2 roadmap.

---

## Help

- 🐛 [Report a bug](https://github.com/wyonliu/Ome365/issues)
- 💬 [Discussion](https://github.com/wyonliu/Ome365/discussions)
- 📋 [Eval Usage Policy](policies/EVAL_USAGE_POLICY.md)
- 🛣️ [Master Plan](strategy/MASTER-PLAN.md)
