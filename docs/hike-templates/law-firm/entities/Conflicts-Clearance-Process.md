---
id: conflicts-clearance
type: term
name: Conflicts Clearance
aliases: [Conflicts Check, Conflict-of-Interest Check, 利益冲突筛查]
tenant: default
parent_id: matter-intake

definition: >
  Pre-engagement screening that checks proposed matter against firm's existing
  client base, prior representations, and lawyer-personal relationships to
  identify ABA Model Rule 1.7/1.9/1.10 conflicts. Required BEFORE matter open.

scope: firm-wide
confidence: high
evidence:
  - "ABA Model Rules 1.7 / 1.9 / 1.10"
  - "internal: conflicts-clearance SOP rev 2024-Q4"

# Hike v2 schema v0.2
external_ids:
  protocol_ref: PROC-CONFLICTS-V4
  ethics_committee: ECOM-001

multilingual:
  zh: 利益冲突筛查
  en: Conflicts Clearance

disambiguation_hint: "区分 Conflicts Clearance (matter-pre-open) 与 Ethical Wall (post-open mitigation)"

relations:
  - type: gates
    target: matter-open
  - type: may_require
    target: ethical-wall-implementation
---

# Conflicts Clearance

## Process

1. **Submit conflicts memo** — proposed party names · adverse parties · subject matter
2. **Database search** — current/former clients · related entities · lawyers' personal interests
3. **Lawyer canvass** — broadcast to potentially-affected attorneys (24h response window)
4. **Resolution**:
   - **Clear**: open matter
   - **Waivable**: obtain informed written consent (both clients)
   - **Non-waivable**: decline engagement
   - **Mitigatable**: ethical wall + screening procedures

## Privacy posture

⚠️ Conflicts data itself is **highly confidential** (reveals firm's client list).
Hike entity captures **process metadata** (turnaround time · resolution
distribution) NOT the actual party names checked.

## Hike auto-extraction

When conflicts/intake meetings reference clearance:
- average turnaround (target: 24h)
- waiver rate vs decline rate
- ethical wall frequency
- common conflict patterns (does NOT identify specific clients)
