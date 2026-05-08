---
id: sku-family-example
type: product
name: SKU Family · Example Apparel
aliases: [SKU-FAM-A, 商品族-A]
tenant: default
parent_id: apparel-category
vendor: Brand-Example
category: apparel

# Hike v2 schema v0.2
validity_period:
  from: 2024-02-01
  to: null  # in-season

external_ids:
  internal: SKU-FAM-A
  upc_root: 0123456789  # placeholder
  erp_category_id: APP-001

multilingual:
  zh: 商品族·示例服饰
  en: SKU Family · Example Apparel

disambiguation_hint: "区分 SKU Family-A (春夏) 与 SKU Family-A2 (秋冬), 季节不同"

relations:
  - type: replenished_by
    target: dc-east
  - type: planogram_governed_by
    target: visual-merch-team
---

# SKU Family · Example Apparel

## Family structure

- 4 styles · 6 colors · 5 sizes = ~120 SKUs in family
- Master style: ART-EX-001
- Lifecycle: 18 weeks (intro → peak → markdown → exit)

## Auto-tracked metrics (Hike L4)

When weekly merchandise reviews reference this family:
- sell-through % vs plan
- markdown cadence
- size curve performance (over/under-sized colors)
- region-level localization gaps (which stores under-perform · why)

## Replenishment + allocation

- DC: dc-east (primary) · dc-west (backup for high-demand regions)
- Allocation: 70% size-curve algorithm + 30% manual seasonal overlay
- Auto-replen trigger: store-on-hand < 50% target

## Hike L6 cross-store signals

- "Top-3 stores hit 90% sell-through · bottom-3 still at 30%" → reallocate
- "Color X selling 2x in north region · 0.5x in south" → regional buy adjust
