# 🛡 Insurance · Hike Starter Template

Pre-seeded Hike v2 entities for insurance enterprises (合规/风控/精算 multi-stakeholder · regional branches).

## Stakeholder map

| Role | scope | concerns |
|:---|:---|:---|
| Chief Actuary | corporate | reserve adequacy · pricing discipline |
| Compliance Officer | corporate + branch | regulatory filings · sanctions check · KYC/AML |
| Underwriting Manager | branch | risk appetite · case approval velocity |
| Claims Manager | branch | claim ratio · fraud detection |
| Regional VP | region (multi-branch) | premium growth · agent network · rentention |

## Key decision events Hike captures

- **Pricing Committee** — quarterly product pricing review · Hike L4 distills "经验调价 vs 算法调价" 的成功率
- **Claims MDT** (Multi-Disciplinary Team) — high-value/disputed claim · 诊疗 + 合规 + 法律 联审
- **Reserve Adjustment Meeting** — IFRS 17 reserve revisions · audit trail critical
- **Compliance Filing Review** — 银保监 quarterly filings · cross-branch consistency check

## Field-level ACL example (RBAC × privacy)

```yaml
# canonical entity for an actuarial reserve estimate
- id: reserve_q3_2024_product_a
  type: term
  privacy: restricted
  acl:
    public: []                    # external partners see nothing
    pinned: []                    # whitelisted reinsurance partners see nothing
    internal: [scope, period]     # internal employees see scope+period only
    restricted: ALL               # reserve amount · methodology · only Chief Actuary + Compliance
```

## Cross-branch decision propagation

When 银保监 issues a regulatory letter:
1. Compliance Officer creates a `decision_chain` entity
2. Hike L6 Swarm auto-suggests: "this affects branches X, Y, Z" based on past products
3. Each affected branch responds within SLA (Hike tracks)
4. After 30-90 days, Hike L4 distills: "对xxx类型监管要求, 标准响应路径 = 5 人核心团队 + 14 天起草"

## Industry-specific config

```yaml
categories:
  management_prefixes: [Branch-VP, Region-VP, CXO, Compliance, Actuary]
  channel_prefix_patterns: [^Branch, ^Region, ^Bureau]
  bu_prefix_root: Insurance
  interview_keywords: [pricing-committee, claims-MDT, reserve-meeting, compliance-filing]
  internal_keywords: [IFRS-17, IBNR, MCEV, EV, COR, NEP, GWP, KYC, AML]

prompts:
  user_bio: "regional VP at a head life insurer · responsible for premium growth and compliance"
```

## Key principles (sample — see `principles.yml`)

- 银保监 letter: 5-day initial response + 14-day full plan
- Reserve methodology change requires 3-quarter lookback validation
- Claims > X amount: dual-approver mandatory regardless of policy automation
