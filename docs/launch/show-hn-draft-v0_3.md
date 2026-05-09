# Show HN draft · v0.3 (2026-05-09 · post-v1.1.6)

> v0.2 led with v1.1.0 Team Brain ship.
> v0.3 leads with v1.1.6 enterprise-shippable. We turned the demo into a product
> in seven micro-releases and 0 token-leaderboard pixels.

---

## Title (≤80 chars)

**Option A (chosen):**
```
Show HN: Ome365 1.1 – Cost-per-Outcome team brain · ed25519 signed · 0 deps
```
(78 chars · "ed25519 signed" because real signing is the differentiator vs
every other "AI dashboard" YC posts on a given day)

**Option B (more provocative):**
```
Show HN: Ome365 1.1 – we measure outcomes, not tokens, and prove it in code
```
(76 chars)

---

## Body (under 1500 chars)

```
Hi HN — I tagged Ome365 1.1.6 today after seven micro-releases that turned a
working spec into a product a 5-15 person team can adopt without hand-holding.

The thesis is unusual: I built this AGAINST "enterprise AI dashboards" that ship
LLM token leaderboards. Meta killed an internal one in April after employees
gamed it (Fortune covered it). The Pinnacle critique nailed why.

So Ome365 inverts:
  * Cost-per-Outcome, not cost-per-token (cost_per_resolved_decision /
    human_equivalent_hourly / revenue_per_workflow — three FinOps views, all
    derived from plain markdown files in the vault)
  * 8-step Decision lifecycle (5 AI + 3 human sections) with `value_anchors`
    {P, XL, L, M, Revert, 维护性} — every score traces to a markdown file
  * Karpathy LLM Wiki Pattern: `ome365 wiki update` distills closed Decisions
    into `Knowledge/L2-distilled/<category>.md`. The wiki IS the artifact.
  * ed25519 agent-card (real, not stub): signed `/.well-known/agent-card.json`
    advertises the v1.1 capabilities · `ome365 verify <url>` round-trips.
  * Region-aware compliance (GDPR Art. 22 / PIPL §13/§24) enforced in code,
    not policy. EU default-deny. CN PIPL ack required per member.
  * Anti-Tokenmaxxing in `docs/policies/EVAL_USAGE_POLICY.md` — sole-basis-of-
    HR usage is a documented violation we'll publicly call out.

Stack: FastAPI + Vue 3 CDN (zero build) + plain markdown. 0 deps for the
core path; `requirements-optional.txt` documents the 4 deps for LLM-distill /
semantic search. 441/441 tests pass · 0 PII hits · CI runs full pytest +
ed25519 verify + 10-endpoint smoke.

Try in 60 seconds:
  curl -fsSL https://raw.githubusercontent.com/wyonliu/Ome365/main/install.sh | sh
  cd Ome365 && ./ome365
  → /v1_1.html (cockpit) · ./ome365 status · ./ome365 doctor

I'm one developer · honest about what's stub (still no v1.2 federation real)
and what's real (everything in the v1.1.x series). Apache 2.0, no CLA.
Comments and roasts welcome.
```

---

## Top-level talking points (anticipated comments + prepared answers)

**"Isn't this just a vault with extra steps?"**
The "extra steps" are a 7-dim eval that has `human_review_required: True`
baked in, region-aware compliance enforced in code, and a wiki maintainer
that compounds knowledge across closed decisions. The vault is the
*storage*. Ome365 is the *interpreter*.

**"How is this different from Notion/Obsidian/Linear?"**
None of those measure cost-per-outcome. None of them have a Kevin git hook
that requires every code commit cite a Decision. None of them ship an
ed25519-signed `/.well-known/agent-card.json` for AAIF discovery. The
overlap is "markdown files"; the difference is "every dollar traces to a
markdown file you can grep."

**"194× cache speedup sounds like marketing."**
`scripts/perf_bench.py` produces it. 1000 decisions / 5000 traces / 50
members. Naive `5×eval_member` = 68s. Cached `1×team_distribution` = 0.35s.
Run it yourself.

**"Why ship v1.1.6 in one day?"**
1.1.0 was the design. 1.1.1 was productization. 1.1.2-6 was self-review +
polish + perf invariants + CI hardening + RBAC + i18n + signing. The
cycle was: ship → grep my own work for gaps → ship the gap fix → repeat.
Every commit cites a Decision in `vault.example/Decisions/`.

**"What's NOT in v1.1?"**
LLM-distilled wiki is opt-in (gated by env). Semantic search (sqlite-vec) is
opt-in. Federation real signing is v1.2. Real-time co-edit is permanently
out (git is good enough; the decision file is at
`Decisions/cut-feature-realtime-collab.md`).

**"How does CI actually run on Cursor / Junie / 30 IDEs?"**
It doesn't. We CI-test 4 headless CLIs (Claude Code / Codex / Gemini /
Continue) and statically lint SKILL.md against the Anthropic spec for the
other 28. We're explicit about this in `tests/test_skill_lint.py` and the
README. No CI overstatement.

---

## What changed v0.2 → v0.3

- Title now says "ed25519 signed" — concrete differentiator vs other YC
  AI dashboards
- Body opens with "seven micro-releases" — proof of velocity + discipline
- Lists the 6 mechanic differentiators concretely (each one with a file
  path or env flag)
- 441/441 tests · the version matters because it shows we kept regression
  green through the entire 1.1.x series
- Comments-prep section adds 5 likely challenges with prepared answers

---

## Pre-flight checklist (5-13 launch · refresh from v0.2)

- [ ] `./ome365 doctor` shows "All green · 12/12 v1.1 modules loaded"
- [ ] `./ome365` boots, `/v1_1.html` returns 200 with 4-card cockpit
- [ ] `python3 -m pytest tests/ -q` shows 441/441 (no flake)
- [ ] `python3 scripts/scan_pii.py` shows 0 hits
- [ ] CHANGELOG.md mentions every v1.1.x release with shipping date
- [ ] Tags v1.1.0 through v1.1.6 visible on https://github.com/wyonliu/Ome365/releases
- [ ] HuggingFace Space sandbox is up and points at v1.1.6
- [ ] Twitter/X thread queued (5 tweets) — but expect 403 on tweet 5 (manual fallback)
- [ ] Karma-aware HN account ready (>100 karma so post lands on /newest)
- [ ] Time set: Tue or Wed, 8am PT (peak HN traffic)
- [ ] `ome365 verify` works against the live HN-linked URL — real signature, not mock

---

## Post-launch monitoring

- HN comment volume in first 4 hours predicts /front rank
- Watch for "isn't this just X" pattern · drop the prepared answer + file path
- If anyone asks for a screencast, point them at `/v1_1.html` localhost +
  `./ome365 status` output (we don't ship a hosted demo; everyone runs local)
- Track GitHub stars/clones/installs — Ome365 doesn't phone home
- Aim: 100 stars / day 1, 1000 by week 1

v0.3 is what we'd actually post. v0.2 stays in repo as historical record.
