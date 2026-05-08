---
id: matter-example
type: term
name: Matter (Example)
aliases: [Engagement, Case, 案件]
tenant: default
parent_id: matter-management

definition: >
  Discrete client engagement with defined scope, billing arrangement, conflicts
  clearance, and ethical wall (if needed). Container for time entries · documents ·
  decisions · communications.

scope: per-engagement
confidence: high
evidence:
  - "ABA Model Rule 1.7 (conflicts of interest)"
  - "internal: matter-opening SOP rev 2024-Q4"

# Hike v2 schema v0.2
external_ids:
  internal: MTR-EXAMPLE-001
  matter_management_id: MM-EX-001
  billing_code: BILL-EX-001

multilingual:
  zh: 案件（示例）
  en: Matter (Example)

disambiguation_hint: "区分 Matter (engagement-level) 与 Task (matter-internal task)"

relations:
  - type: governed_by
    target: matter-opening-sop
  - type: requires
    target: conflicts-clearance
---

# Matter (Example)

## Lifecycle

1. **Intake** — client request · conflicts check · scope definition
2. **Open** — matter ID assigned · ethical wall (if needed) · billing setup
3. **Active** — work product · time entries · docs · decisions
4. **Closeout** — final invoice · file retention policy · client release

## Privacy posture (CRITICAL)

⚠️ **Matter content is privileged**. Hike entity files capture:
- matter-level metadata (practice area · client industry · scope category)
- decision themes (settled/litigated/closed · NOT specific terms)
- billing patterns (hours by phase · realization rate)

Hike NEVER captures: privileged communications · work product · client identity
unless explicitly marked non-privileged. Privilege protection is per-jurisdiction.

## Auto-extracted (Hike L4)

When matter-team meetings are processed:
- phase progression (intake → discovery → motion → trial → settle → close)
- key decision points (settle vs proceed · summary judgment posture)
- staffing changes (partner / associate handoff · role-level only)
- budget vs actual variance categories
