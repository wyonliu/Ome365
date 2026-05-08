---
id: hospital-example
type: organization
name: General Hospital (Example)
aliases: [GH, 综合医院]
tenant: default
parent_id: regional-network

# Hike v2 schema v0.2
validity_period:
  from: 1985-01-01
  to: null  # active

external_ids:
  internal: HOSP-001
  npi: 0000000000  # placeholder · real NPI in tenant data
  hipaa_facility_id: FAC-EX-001

multilingual:
  zh: 综合医院（示例）
  en: General Hospital (Example)

disambiguation_hint: "区分 General Hospital (acute care) 与 General Clinic (outpatient only)"

relations:
  - type: part_of
    target: regional-network
  - type: accredited_by
    target: jci-or-equivalent
---

# General Hospital (Example)

400-bed acute-care hospital · Level II trauma · 24-hour ED · 8 surgical suites.

## Service lines

- Cardiology (cath lab · 24/7 STEMI)
- Orthopedics (joint replacement · sports medicine)
- Oncology (medical + radiation)
- Maternity (Level II NICU)

## Hike privacy posture

⚠️ **PHI must NEVER appear in entity files**. Hike entity captures:
- facility-level operational metrics (LOS · readmit rate · surgical volume)
- service-line summaries (no patient identifiers)
- governance / accreditation status

Patient-level data lives only in EHR with HIPAA controls — Hike L1 entities reference
**aggregated metrics** or **role-based contacts**, never PHI.

## Auto-populated by Hike L4

M&M (Morbidity & Mortality) review decisions, IRB approvals, accreditation findings.
