# 🛒 Retail · Hike Starter Template

Pre-seeded Hike v2 entities for retail / chain operations (region differences · seasonal ops · cross-store best practices).

## Stakeholder map

| Role | scope | concerns |
|:---|:---|:---|
| Regional Manager | region (multi-store) | regional revenue · staff turnover · store-mix |
| Store Manager | single store | OPS · staffing · NPS · daily/weekly KPI |
| Category Manager | corp + region | SKU mix · pricing · promo calendar |
| Marketing Lead | corp + channel | campaign ROI · social/CRM · brand consistency |
| Loss Prevention | corp + store | shrinkage · audit · cash management |

## Key decision events Hike captures

- **Weekly Regional Review** — same-store sales · staffing · escalation
- **Quarterly Category Review** — SKU rationalization · promo calendar lock
- **New Store Opening Committee** — site selection · GTM playbook
- **Promotion Post-Mortem** — campaign result + lessons learned

## Killer feature: L6 Swarm cross-store discovery

```python
hike.detect_cross_bu_signals(threshold=0.7)
# → returns auto-discovered patterns:
# 1. "5/8 stores in East region report supplier X stockout last month"
# 2. "SKU Y outperforms forecast +200% in stores with Manager Z's signature merchandising layout"
# 3. "Promo template Q3-15 used by 4 stores · all hit > 120% target · should be corp standard"
```

This converts **tribal store-manager knowledge** → corporate playbook automatically.

## Industry-specific config

```yaml
categories:
  management_prefixes: [Regional, Store-Manager, District, Corp]
  channel_prefix_patterns: [^Store, ^District, ^Region]
  bu_prefix_root: Operations
  interview_keywords: [weekly-review, category-review, promo-postmortem, store-opening]
  internal_keywords: [SKU, ASP, GMV, CAC, NPS, OOS, on-shelf, planogram]

prompts:
  user_bio: "regional ops manager · 38 stores in East region"
```

## Sample principles (see `principles.yml`)

- OOS > 5%: same-week category review · cross-store check
- Manager promotion: 6-month sustainable performance vs single-quarter spike
- New SKU launch: 4-store pilot before regional rollout
