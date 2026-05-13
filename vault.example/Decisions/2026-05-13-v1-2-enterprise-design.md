---
id: 2026-05-13-v1-2-enterprise-design
opened: 2026-05-13T00:00:00Z
closed: 2026-05-13T08:00:00Z
status: closed
owner: alice
participants: []
supersedes: null
superseded_by: null
outcome: "Ship v1.2 enterprise-AI-platform design doc r4.0-final · 10-round multi-expert iteration · 17 sub-agents engaged · 54 design deltas accepted · 1 ICP / 1 cockpit / 1 HRIS / 1 region / 8-week scope confirmed."
value_anchors:
  - P              # Product surface (positions Ome365 as governance substrate vs HR/search/memory/GRC categories)
  - L              # Larger scope (downstream affects every v1.2 code change for next 8 weeks)
  - 维护性          # Anti-stances and de-scope log become contributor-onboarding artifacts
roi_estimated: "Documents the 8 testable differentiators that anchor pricing and sales conversations; cuts buyer-conversation discovery loop from ~3 weeks (custom slide decks per ICP) to one shared canonical doc."
roi_actual: null
planned_duration_days: 1
elapsed_days: 1
category: design
hours_saved: 0
---

# Decision: ship v1.2 enterprise-AI-platform design r4.0-final

## ① Problem definition

Ome365 v1.1 shipped (12 modules, 533/533 tests, Hike v0.1, file-first
vault). The next 8 weeks need a *buyer-defensible* product story that:
(a) names a buyer ICP we can win in 2026; (b) survives stress tests
from CHRO / DPO / CFO / CISO / regulator-counsel personas; (c)
de-scopes honestly to one ship target rather than a 12-week wishlist.

v1 of this doc (270 lines) was 5-of-5 refused under panel critique.
v2 (450 lines) recovered but Round 4 added ~50 more issues. The
remaining work was to land a v3 → v4 → final ship doc that 10 named
personas would say yes to.

## ② Options considered

1. **Author single-shot v4 from existing v2**: fastest but loses the
   multi-perspective rigor that surfaced 23 deltas in Round 3.
2. **Multi-round multi-expert iteration with sub-agent personas**:
   slower per round but builds documented critique-log that becomes
   contributor onboarding material. Cap rounds at 10; back-port the
   stress-test findings into v1.2 scope where severe.
3. **Outsource to a hired design consultancy**: months, no Apache 2.0
   license-compatibility on output artifacts.

## ③ Choice

Option 2. 10 rounds executed:
- Rounds 1, 3, 5, 8 = author-driven synthesis
- Rounds 2, 4, 6, 7 = parallel sub-agent expert panels
- Rounds 9, 10 = roadmap + ship

17 sub-agents across the 4 panel rounds (5 + 5 + 4 + 3). Two stress-
test findings (vault-tar exfil; KMS single-root-of-trust) back-ported
into v1.2 W7 rather than deferred.

## ④ Implementation surface

- `docs/strategy/v1.2-enterprise-ai-platform-design.md` — 890 lines,
  13 sections, 8 differentiators table, compliance matrix (13
  regimes), 8-week roadmap, v1.3 / v1.4 / v1.5 deferral plan.
- No code changes in this Decision. The implementation of W1-W8 is
  governed by 8 future Decision files (one per week), each with its
  own code commits.

## ⑤ Acceptance

- 10 of 10 named personas vote yes on r4.0-final (§十三).
- PII scan: 0 hits.
- Doc is self-contained: anyone can read it cold and understand v1.2
  scope, buyer wedge, anti-stances, and roadmap without prior
  context.
- Decision-log discipline: this Decision file precedes the doc
  commit per `.githooks/pre-commit` rule.

## ⑥ Followups

- Engage EU-qualified counsel for AI Act 2027 mapping review (Q13
  in §九 open questions). Budget estimate needed.
- Recruit n ≥ 5 design partners for cost-per-business-outcome
  counterfactual methodology (Q11). v1.3 design-partner program
  charter to follow.
- W1 starts when v1.1.x stabilization is complete + this design
  doc is referenced by the W1 implementation Decision file.
- v1.2 r4.0-final → r4.1+ revisions go in `docs/strategy/v1.2-r*-log.md`
  rather than overwriting the canonical doc.
