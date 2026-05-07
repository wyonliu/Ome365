# 🏭 Manufacturing · Hike Starter Template

Pre-seeded Hike v2 entities for manufacturing enterprises (PLM/BOM/工艺 knowledge management · cross-factory coordination).

## Stakeholder map

| Role | scope | typical concerns |
|:---|:---|:---|
| Plant Manager | factory | OEE · cycle time · safety incidents |
| Process Engineer | line | spec deviations · rework rate · yield |
| Quality Lead | factory + corp | defect distribution · supplier audit |
| BOM Manager | corp | revision tracking · ECN propagation |
| Supplier QA | extranet | incoming inspection · SCAR |

## Key decision events Hike captures

- **ECN** (Engineering Change Notice) — propagates from CAD/PLM through Quality, Process, Supplier
- **NCM** (Non-Conformance Meeting) — root-cause + 8D + read-across to other factories
- **PPAP** (Production Part Approval Process) — supplier qualification for new SKU/material
- **Annual Capacity Plan** — cross-factory load balancing

## Distilled principles (sample)

See `principles.yml` — built from 12-month decision-chain analysis at design-partner customers.

## Sample entities

- [`entities/Plant-Example.md`](entities/Plant-Example.md) — example factory entity with full schema v0.2
- [`entities/ECN-Process.md`](entities/ECN-Process.md) — process term entity
- [`entities/SupplierA.md`](entities/SupplierA.md) — vendor organization entity

## Industry-specific config

```yaml
# tenant_config.json additions for manufacturing
categories:
  management_prefixes: [Management, Plant, Corporate]
  channel_prefix_patterns: [^Plant, ^Line, ^Cell]
  bu_prefix_root: Operations
  interview_keywords: [supplier-audit, quarterly-review, NCM, MDT, CCB]
  internal_keywords: [PLM, BOM, ECN, PPAP, NCM, 8D, MES, CMMS]

prompts:
  user_bio: "manufacturing plant manager · responsible for OEE and quality"
```

## Cross-BU signals (Hike L6 Swarm auto-discovers)

- "All 4 plants reported same supplier issue last quarter" → escalate to corp procurement
- "Process engineer X mentioned in 6 different ECN reviews" → likely subject-matter authority
- "ECN Y propagation took 90 days (vs 30-day target)" → workflow bottleneck
