---
id: mm-review-process
type: term
name: M&M Review
aliases: [Morbidity and Mortality Review, M&M Conference, 死亡及并发症讨论]
tenant: default
parent_id: clinical-governance

definition: >
  Confidential peer-review forum where complications, deaths, and near-misses
  are discussed for systems-level learning. Findings inform protocol updates
  but are NOT individual performance reviews.

scope: clinical · service-line + facility
confidence: high
evidence:
  - "ACGME Common Program Requirements VI.A.1"
  - "Joint Commission MS.06.01.05"

# Hike v2 schema v0.2
external_ids:
  protocol_ref: PROC-MM-2024-R3

multilingual:
  zh: 死亡及并发症讨论
  en: Morbidity and Mortality Review

disambiguation_hint: "区分 M&M (clinical peer review) 与 RCA (systems root-cause)"

relations:
  - type: feeds
    target: clinical-protocol-update
  - type: governed_by
    target: medical-staff-bylaws
---

# M&M Review · Morbidity and Mortality

## What it is

Confidential structured review of adverse outcomes. Goal: improve systems, NOT
assign individual blame. Protected under peer-review privilege in most
jurisdictions (e.g., U.S. patient safety quality improvement laws).

## Privacy posture (CRITICAL)

- Discussion happens in protected forum
- Hike captures: **anonymized themes** (e.g., "communication handoff gap")
- Hike does NOT capture: patient identifiers · individual physician names · case
  details that could re-identify

## Auto-extracted decision themes

When meetings tagged `mm-review` are processed:
- root-cause category (communication / equipment / protocol / training)
- recommended protocol changes
- responsible owner (role, not name)
- target close date
