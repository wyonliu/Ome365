---
id: ecn-process
type: term
name: ECN
aliases: [Engineering Change Notice, 工程变更通知]
tenant: default
parent_id: change-management

definition: >
  Formal document propagating an engineering change from PLM/CAD through Quality,
  Process, Manufacturing, and Supplier. Each ECN carries: change scope · effective
  date · disposition (rework / scrap / use-as-is) · cross-factory read-across.

scope: corp + factory + supplier
confidence: high
evidence:
  - "ISO 9001:2015 §8.5.6 Control of Changes"
  - "internal: ECN propagation SOP rev. 4 (2024-Q3)"

# Hike v2 schema v0.2
external_ids:
  internal: PROC-ECN-V4

multilingual:
  zh: 工程变更通知
  en: Engineering Change Notice
  ja: 設計変更通知

disambiguation_hint: "区分 ECN (corp-level engineering) 与 PCN (production-line tweak)"

relations:
  - type: governs
    target: bom-revision
  - type: triggers
    target: ppap-recheck
---

# ECN · Engineering Change Notice

## What it is

Formal change-control artifact. Originates in CAD/PLM after a design or material
change, and **propagates** through Quality (FAI / FMEA update), Process (work-instruction
revision), Manufacturing (line setup), and Supplier (PPAP recheck if upstream).

## Lifecycle states

1. `draft` — engineer files change in PLM
2. `review` — CCB (Change Control Board) reviews impact
3. `approved` — disposition signed off
4. `propagating` — read-across rolling out to plants
5. `closed` — all sites confirm implementation

## Hike auto-extracted fields (when meetings reference ECN)

- effective date
- impact factories (cross-plant read-across)
- supplier impact (yes/no — gates PPAP)
- root cause category (design / material / process / supplier)
