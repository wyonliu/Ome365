---
id: store-example
type: organization
name: Flagship Store (Example)
aliases: [STR-001, 旗舰店]
tenant: default
parent_id: retail-region-east

# Hike v2 schema v0.2
validity_period:
  from: 2017-11-01
  to: null  # active

external_ids:
  internal: STR-001
  pos_terminal_id: POS-EX-001
  geo: 31.2304,121.4737  # lat,lng (示例)

multilingual:
  zh: 旗舰店（示例）
  en: Flagship Store (Example)

disambiguation_hint: "区分 Flagship Store (旗舰·800㎡) 与 Pop-up Store (快闪·30天)"

relations:
  - type: part_of
    target: retail-region-east
  - type: staffed_by
    target: store-manager-role
---

# Flagship Store (Example)

## Profile

- Format: flagship · 800 ㎡ · 2 floors
- Staffing: 18 FTE (manager · 4 supervisors · 13 associates)
- Categories: full assortment · experience zone · ship-from-store
- Hours: 10:00–22:00 daily

## KPIs Hike captures

- traffic / conversion / UPT / ATV
- inventory turn · shrink rate
- NPS · staff engagement
- omnichannel fulfillment SLA (BOPIS / SFS / curbside)

## Auto-extracted decisions (Hike L4)

When district-manager visits or category review meetings mention this store:
- staffing changes (hires / promotions / departures · role-level only)
- assortment localization decisions
- visual merchandising directives
- promo-event compliance findings

## Privacy posture

Hike captures **role-level** staffing + **aggregated** customer metrics. Individual
customer identities and individual employee performance reviews live in HR/CRM
systems with appropriate access controls.
