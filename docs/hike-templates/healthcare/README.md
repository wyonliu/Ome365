# 🏥 Healthcare · Hike Starter Template

Pre-seeded Hike v2 entities for healthcare (hospitals · clinics · multi-disciplinary teams).

> ⚠️ This template is for non-PHI organizational knowledge management. PHI (Protected Health Information) requires HIPAA-compliant deployment with additional safeguards. **Do not store patient data in default Ome365 install.**

## Stakeholder map

| Role | scope | concerns |
|:---|:---|:---|
| Chief Medical Officer | hospital | clinical quality · safety · accreditation |
| Department Chair | department | research · teaching · clinical excellence |
| Senior Attending | unit | rounds · MDT · resident teaching |
| Nurse Manager | unit | staffing · workflow · safety incidents |
| Quality / IRB Officer | hospital | adverse events · root-cause · IRB review |

## Key decision events Hike captures

- **MDT (Multi-Disciplinary Team) Meeting** — complex case review across 3-5 specialties
- **M&M (Morbidity & Mortality) Conference** — adverse event root-cause + read-across
- **Tumor Board** — oncology case treatment plan review
- **Quality / Safety Huddle** — daily 15-min stand-up on near-misses

## Hike L4 Cognition value

Distill recurring patterns:
- "对xxx条件的患者 · 阶段I/II/III 选择决策的成功率"
- "MDT 推荐方案 vs 实际治疗 偏差分析"
- "Adverse event root-cause 高频原因 top-10"

Built from anonymized case-pattern entities (NOT patient records · which stay in EHR).

## Privacy / HIPAA note

```yaml
# This template does NOT include patient entities
# For HIPAA deployment, ALL these mandatory:
- Encrypt vault at rest (LUKS / FileVault / BitLocker)
- LDAP / SSO with break-glass procedures
- Audit log retention 6 years
- BAA (Business Associate Agreement) with all sub-processors
- LLM_BACKEND=local (Ollama) only · never cloud LLM for PHI
- Separate `phi/` directory · separate sub-tenant · separate backup chain
- Quarterly external penetration test
- Annual HIPAA compliance review by qualified counsel
```

See [`../../legal/DPA-template.md`](../../legal/DPA-template.md) for healthcare-extended DPA.

## Industry-specific config

```yaml
categories:
  management_prefixes: [CMO, Department-Chair, Director]
  channel_prefix_patterns: [^Dept, ^Unit, ^Service]
  bu_prefix_root: Clinical
  interview_keywords: [MDT, M&M, tumor-board, IRB, journal-club, grand-rounds]
  internal_keywords: [HIPAA, IRB, EHR, CDS, MDT, M&M, FDA, CMS, JCAHO, ICD-10, CPT, RVU]

prompts:
  user_bio: "department chair · academic medical center · interested in clinical AI augmentation (NOT diagnosis automation)"
```

## Sample principles (see `principles.yml`)

- M&M finding: 30-day cross-unit read-across mandatory
- New protocol adoption: 3-month sentinel monitoring
- Adverse event report: 24-hour notification + 48-hour full RCA submission
