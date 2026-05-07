# Hike 5 行业 starter templates

Cold-start templates for Hike v2 — drop-in adoption for the 5 vertical industries we've validated.

## Why these 5?

These are the industries with the highest **decision-distillation density** (lots of meetings, complex stakeholder graphs, repeated cross-BU coordination):

| 行业 | 痛点 | Hike 解决 |
|:---|:---|:---|
| 🏭 [`manufacturing/`](manufacturing/) | PLM/BOM 跨工厂协同 · 工艺知识断代 | 实体图打通 BOM × 工艺 × 供应商 · 决策链路记录工艺改良 |
| 🛡 [`insurance/`](insurance/) | 合规/风控/精算多角色研讨 · 决策依据散落 | RBAC scope 三层（总部/分公司/团队） · 字段级 ACL 隔离精算/合规 |
| ⚖️ [`law-firm/`](law-firm/) | 案件 × 客户 × 法律意见 跨律师协同 | Hike L4 Cognition 蒸馏出"高频争议法律意见库" |
| 🛒 [`retail/`](retail/) | 区域差异 · 季节性运营 · 跨店铺最佳实践 | L6 Swarm 自动发现"跨店铺爆款 SKU"/"区域成功活动模板" |
| 🏥 [`healthcare/`](healthcare/) | 病例 × 诊疗指南 × 多学科会诊 | L2 Event 沉淀 MDT 会诊 + L4 蒸馏诊疗经验 |

## How to adopt

```bash
# 1. Pick your industry (or fork closest one)
cp -r docs/hike-templates/manufacturing/* /your-vault/Knowledge/entities/

# 2. Edit entity placeholders (replace XXX with your tenant terms)
$EDITOR /your-vault/Knowledge/entities/

# 3. Reload Hike
curl http://localhost:3650/api/entities/refresh
```

## Each template includes

- `README.md` — vertical-specific guidance · stakeholder map · decision flow diagram
- `entities/` — 8 entity types pre-seeded with industry stereotypes (CEO/CTO/Compliance/etc · plus a TerminologyExample)
- `events/` — typical event templates (board-meeting, customer-MDT, change-request, etc.)
- `principles.yml` — distilled principles common in this industry

## Schema v0.2 reference

All entity files use Hike v2 schema v0.2:

```yaml
---
id: <slug>
type: person | organization | product | term
name: <display name>
aliases: [<alt-name-1>, <alt-name-2>]
tenant: <tenant-id-or-default>

# Hike v2 schema v0.2 five fields (all optional)
parent_id: <parent-entity-id>
validity_period:
  from: 2024-01-01
  to: null  # or 2025-12-31 if archived
external_ids:
  dingtalk: <id>
  github: <login>
  did: did:web:omnity.ai:<tenant>:member:<slug>
multilingual:
  zh: <Chinese name>
  en: <English name>
disambiguation_hint: "<context to distinguish same-name entities>"
---

<free-form body description>
```

See [`../hike.md`](../hike.md) for full v2 architecture.

## Contributing your industry

PRs welcome to add new verticals (e.g. PE/VC investment · SaaS company · academic research lab · gov-services).

Format guidance:
1. Pick a slug: lowercase-hyphenated (e.g. `pe-investment/`)
2. Include 5-8 representative entities
3. Document stakeholder roles + key decision events
4. Add 3-5 distilled principles in `principles.yml`
5. Test with `python3 scripts/scan_pii.py --fixtures` before PR
