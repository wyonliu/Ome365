---
id: supplier-a
type: organization
name: Supplier A (Example)
aliases: [SUP-A, 一级供应商A]
tenant: default
parent_id: tier-1-suppliers

# Hike v2 schema v0.2
validity_period:
  from: 2020-06-01
  to: null  # active

external_ids:
  internal: VEND-A001
  duns: 00-000-0000  # placeholder · real DUNS in tenant data

multilingual:
  zh: A级供应商（示例）
  en: Supplier A (Example)

disambiguation_hint: "区分 Supplier A (PCB · tier-1) 与 Supplier A2 (mechanical · tier-2)"

relations:
  - type: supplies
    target: pcb-assemblies
  - type: audited_by
    target: corp-supplier-qa
---

# Supplier A (Example)

Tier-1 PCB vendor · 6 SKU families · single-sourced for 2 critical assemblies.

## Quality history

- 2024-Q4: SCAR opened for solder defect (root: SMT reflow profile drift)
- 2025-Q1: PPAP rev 7 approved · 100k unit production validation
- 2025-Q2: Annual audit score 87/100 · re-audit scheduled 2026-Q1

## Risk profile

- **Single-source**: yes — qualifying alternative (target 2026-Q3)
- **Geo concentration**: single facility · BCP ranks "high"
- **Tier-2 dependency**: copper-clad laminate from one upstream

## Hike auto-populates

When ECN/NCM mentions this supplier, Hike L4 builds decision_chain entries:
ECN-2026-0042 → Supplier A read-across → 8D root cause → corrective action.
