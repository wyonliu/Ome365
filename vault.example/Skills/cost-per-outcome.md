---
name: cost-per-outcome
description: |
  Generate the FinOps board pack from vault Trace + Decisions data.
  Translates "AI usage cost" into board-ready dollars-out / dollars-in language
  for CIO + CFO conversations. NEVER produces token-leaderboards.
allowed-tools: [Read, Bash, Glob]
license: Apache-2.0
ome365:
  author: alice
  created: 2026-05-09
  role: Finance/Ops
  scope: tenant
  code_mode_compatible: true
---

# Skill: cost-per-outcome

> **Stance**: Cost-per-Outcome > Cost-per-Token. We measure dollars-out vs
> dollars-in, not API call volume. Reference: Meta 2026-04 token-dashboard
> incident · Pinnacle critique on performative AI usage.

## When to use

User says "monthly cost report" / "FinOps board pack" / "show me ROI by team" /
"how much did AI save us this quarter" / "我们 AI 投入产出比怎么样".

## Three views (file-first · all from `vault/Trace/*.jsonl` + `vault/Decisions/*.md`)

### View 1 · cost_per_resolved_decision
```
sum(trace.cost_usd) / count(decisions where status="closed")
```
What it answers: "How much did we spend per resolved Decision file?"
Compare against `docs/strategy/industry-benchmarks.yml` P25/P50/P75 numbers.

### View 2 · human_equivalent_hourly
```
sum(trace.cost_usd) / sum(decision.elapsed_days × 8h)
```
What it answers: "What's our $/hour of contractor-equivalent work?"

### View 3 · revenue_per_workflow
```
sum(decision.roi_actual) / count(decisions with roi_actual)
```
What it answers: "Each AI workflow tracked, how much revenue did it generate?"

## How to invoke

CLI:
```bash
./ome365 eval finops dashboard --window-days 90
```

HTTP:
```bash
curl -s http://localhost:3650/api/eval/finops/dashboard?since_days=90 | jq
```

Python SDK:
```python
from ome365_eval import dashboard_data
d = dashboard_data(vault_path, since_days=90)
print(d["by_scope"])    # 3 view dicts
print(d["by_actor"])    # per-actor breakdown
print(d["monthly_trend"])  # last 3 months from Trace/monthly/*.summary.json
```

## What this Skill MUST NOT do

- ❌ Rank employees by token usage
- ❌ Surface any "AI seat utilization" leaderboard
- ❌ Suggest cost-per-token as a primary metric
- ❌ Be used as the sole basis for budget cuts targeting individuals

See `docs/policies/EVAL_USAGE_POLICY.md` for the complete usage policy.

## Output format · CIO/CEO ready

```markdown
## Q2 2026 · AI Cost-per-Outcome (window: 90 days)

### Per-decision cost
| Team       | $/decision | vs P50 | save |
|------------|-----------:|-------:|-----:|
| eng        |       $12  |   $35  |  65% |
| product    |       $18  |   $35  |  49% |
| sales-eng  |        $9  |   $35  |  74% |

### Per-hour equivalent
- $50/hour vs industry P50 $80/hour → save 38%

### Revenue per tracked workflow
- $1200/workflow (P50: $1100) → +9%

Source: vault/Trace + vault/Decisions · auto-refreshed daily
Anti-Tokenmaxxing: scores derived from value/cost, not token volume.
```

## Citations

- FinOps Foundation 2026 Q1 report · Cost-per-Outcome > Cost-per-Token
- Salesforce / NavyaAI / Forrester benchmarks (`industry-benchmarks.yml`)
- v1.1 Team Brain design · `docs/strategy/v1.1-team-brain-design.md` §3.7
- Anti-Tokenmaxxing rationale · `README.md` (top section)
