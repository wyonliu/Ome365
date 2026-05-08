# ⚖️ Law Firm · Hike Starter Template

Pre-seeded Hike v2 entities for law firms (case × client × legal opinion · cross-attorney coordination).

## Stakeholder map

| Role | scope | concerns |
|:---|:---|:---|
| Managing Partner | firm | revenue · talent · firm strategy |
| Practice Group Lead | practice | case mix · associate development |
| Senior Associate | case | research · drafting · client relationship |
| Junior Associate | case | due diligence · doc review |
| Knowledge Lawyer | firm | precedent library · KM · CLE |

## Key decision events Hike captures

- **Conflicts Check** — pre-engagement screening across all firm clients/cases
- **Pricing Committee** — fee arrangement (hourly vs flat vs success vs blended)
- **Case Strategy Meeting** — multi-counsel case · jurisdiction strategy · settlement vs trial
- **Annual Compensation Review** — performance-based partner promotion / associate bonus

## Knowledge moat (Hike L4 Cognition)

The killer use case: **distilled legal opinions** — Hike turns 10 years of internal memos + opinion letters into a queryable principle library.

```python
hike.distilled_principles(scope="data-protection-china")
# → returns:
# 1. "PIPL §38 跨境传输必经 CAC 安全评估 (案件次数: 23, 信心度: 0.95)"
# 2. "标准合同条款 (SCC) 备案到位前 · 不应启动数据出境 (案件次数: 17)"
# 3. "敏感个人信息处理必须取得单独同意 (案件次数: 31)"
```

This replaces:
- Centralized knowledge databases (used by < 30% of attorneys due to friction)
- Tribal "ask the senior partner" knowledge (siloed)
- External research databases (Westlaw / LexisNexis · expensive · poor for firm-specific moves)

## Privacy: client confidentiality

```yaml
# client matter entity
- id: matter_2024_xyz_corp
  type: organization  # actually a "matter" (case+client) hybrid
  privacy: restricted
  acl:
    public: []                    # outsiders see nothing
    pinned: [matter_id, status]   # shared advisors see metadata only
    internal: [matter_id, status, practice_group, lead_attorney]
    restricted: ALL               # team members only see full
```

## Industry-specific config

```yaml
categories:
  management_prefixes: [Managing-Partner, Practice-Lead, Of-Counsel]
  channel_prefix_patterns: [^Practice, ^Group, ^Office]
  bu_prefix_root: Practice
  interview_keywords: [case-strategy, pitch, conflicts-check, partner-meeting]
  internal_keywords: [PIPL, GDPR, CCPA, M&A, IPO, IP, FDA, NDA]

prompts:
  user_bio: "senior associate · M&A practice · cross-border transactions"
```

## Sample entities

- [`entities/Matter-Example.md`](entities/Matter-Example.md) — engagement term · privilege-aware · phase progression
- [`entities/Conflicts-Clearance-Process.md`](entities/Conflicts-Clearance-Process.md) — pre-engagement screening process · ABA Model Rule 1.7 governance

⚠️ Privileged communication NEVER lives in entity files — only metadata + decision themes.

## Sample principles (see `principles.yml`)

- Pitch acceptance: triple-check fee structure consistency vs precedent
- Cross-border: dual-counsel mandatory in 8 specific jurisdictions
- Internal opinion → external letter: 48h review by senior + KM lawyer
