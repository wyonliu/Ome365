---
id: auto-comprehensive
type: term
name: Comprehensive Coverage (Auto)
aliases: [Other-Than-Collision, OTC, 综合险]
tenant: default
parent_id: auto-coverage-types

definition: >
  Auto insurance coverage for non-collision losses: theft · vandalism · weather
  (hail/flood) · falling objects · animal collision. Subject to deductible.
  Excludes wear-and-tear and mechanical breakdown.

scope: personal-lines + commercial-fleet
confidence: high
evidence:
  - "ISO Personal Auto Policy form PP-00-01"
  - "internal: coverage spec sheet rev 2024-Q3"

# Hike v2 schema v0.2
external_ids:
  iso_form: PP-00-01
  product_code: AUTO-COMP-V3

multilingual:
  zh: 综合险（车险）
  en: Comprehensive Coverage
  ja: 車両保険（一般条件）

disambiguation_hint: "区分 Comprehensive (OTC · 非碰撞) 与 Collision (碰撞), 分别两种 deductible"

relations:
  - type: paired_with
    target: auto-collision-coverage
  - type: governed_by
    target: state-insurance-regulation
---

# Comprehensive Coverage (Auto)

## Coverage scope

- Theft of vehicle / parts
- Vandalism
- Weather (hail · flood · windstorm)
- Falling objects (tree · building debris)
- Animal collision (deer / livestock)
- Glass breakage (often $0 deductible · separate sub-limit)

## Exclusions

- Wear and tear
- Mechanical / electrical breakdown
- Damage during racing
- Intentional damage by insured

## Hike auto-extraction

When claims meetings reference comprehensive losses:
- catastrophe code (HAIL · FLOOD · THEFT-V · etc.)
- aggregate loss reserve impact
- subrogation potential
- third-party recovery status
