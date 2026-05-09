# Ome365 Eval Usage Policy

**Version**: v1.1.0 · **Effective**: 2026-05-09 · **Owner**: maintainers

This policy governs how the Ome365 `eval_member()` outputs may and may not be used by
adopting organizations. It is a contractual constraint on the cockpit's intent, not
just a UX hint. All `eval_member()` responses carry `human_review_required: True` and
an `anti_tokenmaxxing_note` because of the rules in this document.

---

## 1. What Ome365 Eval is

Ome365 Eval derives 7 dimensions (D1-D7) from plain markdown files in a vault:

| Dim | Name | Source signal |
|-----|------|--------------|
| D1 | delivery | `closed_at` ≤ `opened_at + planned_duration_days` ratio |
| D2 | cost_per_outcome | `sum(output_value_usd) / sum(cost_usd)` (FinOps 2026) |
| D3 | quality | `1 - superseded_by ratio` over closed decisions |
| D4 | judgment | `value_anchors` weighted (P/XL/L/M lift · Revert/维护性 drag) |
| D5 | ecosystem | `own skills × distinct external adopters` (anti-self-gaming) |
| D6 | revenue_per_workflow | `roi_actual` (≥ 90 days) or `value_anchors` (< 90 days) |
| D7 | learning | new skills used in window |

Each dimension returns a `Score(raw, score, n, percentile, reason)` with explicit
sample size. When `n < sample_size_min` (default 5), the score is `None` and reason
is `"insufficient_sample"`.

---

## 2. What Ome365 Eval IS NOT

Ome365 Eval **MUST NOT** be the sole basis for any of the following:

- Hiring decisions
- Termination decisions
- Promotion decisions
- Compensation determinations
- Performance Improvement Plans (PIPs)
- Visa or immigration recommendations
- Layoff prioritization

Adopters who use the scores as the *sole* decision input for any of the above are
**violating this policy** and should not deploy Ome365 in their organization. The
maintainers reserve the right to publicly call out adopters known to violate the
policy.

---

## 3. What Ome365 Eval CAN be used for

The intended uses are *resource allocation hints*:

- Identifying who has bandwidth (low D1+D7) for a new project
- Spotting skill gaps in a team (D5 ecosystem map)
- Prioritizing FinOps optimization targets (D2 cost-per-outcome by team)
- 1:1 conversation prompts (e.g., "your D7 has dropped — what would help?")
- Annual / quarterly review *inputs* (alongside human judgment, never replacing it)

---

## 4. Region-aware enforcement (in code, not just policy)

The code enforces three legal regimes:

| Region | Default | Override mechanism | Code path |
|--------|---------|---------------------|-----------|
| EU     | **DENY** (GDPR Art. 22 — solely automated decisions about persons forbidden) | `eval_enabled_eu: true` in `eval-config.yml` (forces `human_review_required: True` warning visible) | `EvalDisabledForRegion` exception at `eval_member()` entry |
| CN     | **NOTIFY-FIRST** (PIPL §13 — informed consent) | `pipl_notify_acknowledged_by: {<member>: <date>}` per-member ack | `PIPLNotifyRequired` exception |
| US     | OPEN with warning | (no override needed) | warning text only |
| global | OPEN with warning | (no override needed) | warning text only |

Members in any region may exercise PIPL §24 / GDPR Art. 22 right of refusal by being
listed in `opted_out_members: [...]` — `eval_member()` then raises `EvalOptedOut`
permanently.

The notice template for CN deployments is at `docs/legal/PIPL-NOTIFY-TEMPLATE.zh.md`.

---

## 5. Anti-Tokenmaxxing stance

This is a hard line: **Ome365 Eval scores measure value/cost ratio, not token usage**.

We deliberately exclude any leaderboard surface that ranks by:
- token count
- chat count
- API call count
- LLM session length
- "AI usage" volume

Background: Meta in April 2026 publicly killed an internal token leaderboard after
employees gamed it by generating verbose / circular AI conversations to inflate
their numbers. The Pinnacle critique ("performative AI usage") and FinOps Foundation
2026 report (Cost-per-Outcome > Cost-per-Token) align with our position.

If your AI cockpit ranks employees by tokens, the maintainers consider that a defect.
File a bug with `cost-per-outcome` in the title.

---

## 6. Enforcement against adopter violations

If we learn an adopter is using Ome365 Eval as the sole basis for one of the
prohibited decisions in §2, the maintainers will:

1. Issue a `truthguard violation` notice via `truthguard.violations` registry
2. Refuse to merge contributions from the violating organization until corrective
   action is documented
3. Optionally publish the violation in the project README under "Known misuses"

This is a community trust mechanism, not a legal enforcement mechanism. Adopters
remain solely responsible for compliance with their own jurisdiction's labor and
data-protection law.

---

## 7. How to comply (5-line checklist)

1. ☐ Wire `eval-config.yml` to your org's region (`eu` / `cn` / `us` / `global`)
2. ☐ Set `human_review_required: true` is the default — do not strip it from the UI
3. ☐ Display the `anti_tokenmaxxing_note` verbatim near every score
4. ☐ Build any HR workflow such that scores are *one input* alongside human review
5. ☐ Provide a documented opt-out path for every member (PIPL §24 / GDPR Art. 22)

---

## 8. Review and updates

This policy is versioned with the codebase. Material changes ship as a new minor
version (v1.1.x → v1.2.0) and will be highlighted in CHANGELOG.

Last reviewed: 2026-05-09 (v1.1.0 release)
