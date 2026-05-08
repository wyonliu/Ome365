---
id: underwriter-example
type: person
name: Senior Underwriter (Example)
aliases: [SR-UW-01]
tenant: default
title: Senior Underwriter · Commercial Lines
company: Acme Insurance (Example)
parent_id: commercial-lines-team

# Hike v2 schema v0.2
validity_period:
  from: 2019-08-01
  to: null  # active

external_ids:
  internal: UW-2019-001
  policy_admin_login: sruw01  # placeholder · real login in tenant data

multilingual:
  zh: 高级核保员（示例）
  en: Senior Underwriter (Example)

disambiguation_hint: "区分 Senior UW (commercial lines · 100k+ premium) 与 Junior UW (auto/personal)"

relations:
  - type: reports_to
    target: commercial-lines-vp
  - type: authorizes
    target: large-account-binding
---

# Senior Underwriter · Commercial Lines (Example)

## Authority limits

- Single-account premium: up to $5M
- Aggregate book: $80M
- Risk class: A-rated commercial property + GL

## Decision patterns Hike L4 captures

- declination reasons (loss history · construction class · location risk)
- referral triggers (when escalates to chief underwriter)
- pricing exception approvals
- ceded reinsurance recommendations

## Privacy posture

⚠️ Hike never captures **policy-holder PII** in entity files. Insured-party data
stays in the policy admin system; entity layer references **roles + decision
patterns** only.

## Auto-populated by Hike L4

Underwriting committee decisions, exception approvals, declination categories.
