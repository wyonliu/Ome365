# Show HN draft · v0.2 (2026-05-09 · post-v1.1.0)

> v0.1 (2026-05-08) led with v1.0 entity graph + DID + A2A (mostly stubs).
> v0.2 leads with v1.1.0 **Team Brain** — the 8-week build that shipped today.
> Pre-flight checklist at the bottom.

---

## Title (≤80 chars · HN cuts at 80)

**Option A (chosen · v0.2):**
```
Show HN: Ome365 – Cost-per-Outcome team brain, every score traces to a markdown file
```
(81 chars · 1 over · trim "team " → 76 chars)

**Trimmed A:**
```
Show HN: Ome365 – Cost-per-Outcome brain, every score traces to a markdown file
```
(78 chars)

**Option B (more concrete):**
```
Show HN: Ome365 1.1 – decisions, traces and eval scores from plain markdown files
```
(80 chars · exact fit)

**Option C (anti-tokenmaxxing leaning):**
```
Show HN: Ome365 – we measure outcomes not tokens, and prove it with file-first eval
```
(78 chars)

---

## Body (HN allows ~1500 chars · keep under 1200)

```
Hi HN — I just tagged Ome365 1.1.0 ("Team Brain"). Eight weeks ago I had a vault +
share station; today every team-brain score derives from plain markdown.

The thesis is unusual: I built this *against* "enterprise AI platforms" that ship
LLM dashboards measuring tokens-per-employee. Meta killed an internal one in April
2026 after employees gamed it (Fortune covered it). The Pinnacle critique nailed
why: token-leaderboards reward performative AI usage, not work.

So Ome365 is the opposite. Every cost view is per-outcome, not per-token:
- cost_per_resolved_decision  (USD / closed Decisions/<id>.md)
- human_equivalent_hourly      (USD / contractor-hour saved)
- revenue_per_workflow         (tracked roi_actual)

Each score has `human_review_required: true` baked in. The HR-usage policy is
in-repo (docs/policies/EVAL_USAGE_POLICY.md) and explicitly forbids using the
scores as sole basis for hiring/firing/promotion. Region-aware: EU is default-deny
(GDPR Art. 22), CN requires PIPL §13 ack per member. Not policy text — code.

What ships in v1.1 (all file-first, all unit-tested):
- Decisions: 8-step (5 AI + 5 human) lifecycle, value_anchors {P, XL, L, M,
  Revert, 维护性}, .calibration/ AI-vs-human diff capture, git hook enforces every
  code commit cite a [decision: <id>] tag (Kevin "先文件再代码" rule)
- Trace SDK: `with trace.session(actor) as t:` Python ctx mgr auto-extracts
  anthropic/openai usage, append-only Trace/<date>.jsonl, monthly rollup
- Eval: 7 dims (D1-D7) including delivery, cost_per_outcome, ecosystem
  (anti-self-gaming: own × distinct external adopters)
- Wiki maintainer: `ome365 wiki update` rule-based distill of Decisions →
  Knowledge/L2-distilled/<category>.md, idempotent. Karpathy LLM Wiki Pattern.
- Cockpit panel /v1_1.html: 4 cards Vue 3 CDN, role-preset switcher
- Archive: gzip old Trace/<date>.jsonl into per-month .gz buckets (Moxt 95/5)

Spec compatibility: SKILL.md is spec-PASS for the 32-tool open Agent Skills
standard Anthropic published in Dec 2025 (Claude Code, Codex, Cursor, etc).
Runtime-tested in CI on 4 headless CLIs.

Stack: FastAPI + Vue 3 CDN (zero build) + plain markdown. 250/250 pytest tests,
0 PII hits. Apache 2.0, no CLA, no bait-and-switch.

Try without installing:
  curl -fsSL https://raw.githubusercontent.com/wyonliu/Ome365/main/install.sh | sh
  cd Ome365 && ./ome365   # starts at localhost:3650, /v1_1.html for the new panel

I'm one developer. Honest about what's stub (identity ed25519, A2A signing —
v1.2/v1.3) and what's real (everything in the W1-W8 list above). Comments and
roasts welcome.
```

---

## Top-level talking points (for HN comments)

When (not if) someone asks "isn't this just a wiki?":
> The wiki *is* the artifact (Karpathy). What's new is that the artifact is
> queryable + scoreable + region-compliant + audited. `wiki update` is
> idempotent and the score it produces traces back through Knowledge/L2-distilled/
> to the Decision it came from. You can grep for the path of any number on the
> dashboard.

When (not if) someone asks about the eval policy:
> docs/policies/EVAL_USAGE_POLICY.md §2. Eval scores MUST NOT be sole basis for
> hiring/firing/promotion. Sole-basis usage is a violation we'll publicly call
> out. Scores are resource-allocation hints (who has bandwidth, who needs
> learning support) — never a verdict.

When someone challenges the cost-per-outcome math:
> docs/strategy/v1.1-implementation-spec.md §四 4.5. ROI multiple = sum(value) /
> sum(cost) over the window. Score = log10(roi+1) clipped to 0-5. Sample threshold
> default 5; below that returns score=null with reason="insufficient_sample".
> No imputation, no smoothing.

When someone asks why the agent-card doesn't sign:
> Honestly stated as `signed_by: null` in the JSON. Real ed25519 signing lands
> in v1.2 with mindos.protocol integration. I refuse to ship fake signatures.

---

## Pre-flight checklist (copy from v0.1, refresh dates)

- [ ] `./ome365 doctor` shows 12/12 green on a fresh laptop
- [ ] `./ome365` boots, `/v1_1.html` returns 200
- [ ] `python3 -m pytest tests/ -q` shows 250/250 (no flake)
- [ ] `python3 scripts/scan_pii.py` shows 0 hits
- [ ] CHANGELOG.md mentions v1.1.0 with shipping date
- [ ] Tag v1.1.0 visible on https://github.com/wyonliu/Ome365/releases
- [ ] HuggingFace Space sandbox is up and points at v1.1.0
- [ ] `try.omnity.ai` redirects to v1.1.0 demo (or temporarily disabled with note)
- [ ] Twitter/X thread queued (5 tweets) — but expect 403 on tweet 5 (manual fallback)
- [ ] Karma-aware HN account ready (>100 karma so post lands on /newest)
- [ ] Time set: Tue or Wed, 8am PT, 1pm UTC (peak HN traffic)

---

## What changed from v0.1 → v0.2

- Title leads with **Cost-per-Outcome** + **markdown traceability** (specific) rather
  than "open-source enterprise AI platform" (generic).
- Body opens with the **Meta token-dashboard incident** — concrete hook, not abstract
  "thesis" framing.
- Lists v1.1 W1-W7 features that are *real and unit-tested*, not the v1.0 stubs.
- Anti-Tokenmaxxing stance is the lede, not a footnote.
- Comments-prep section anticipates the 4 most likely challenges (just-a-wiki /
  HR usage / cost math / signing) with prepared answers + file paths.
- "I'm one developer" closing — honesty card. HN rewards humility.

v0.1 stays in repo as historical record; v0.2 is the one to actually post.
