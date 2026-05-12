---
title: Q3 Product Strategy Review
subtitle: Five lines, one map
speaker: Alice Smith
role: Head of Product · Acme Corp
date: 2026-09-15
brand_chip: Acme Corp · Internal
brand_name: Acme Corp
theme: default
---

## cover :: Cover // Opening
section: Q3 · 2026
title: |
  One <accent>clear</accent>
  product line per
  customer segment
sub: From enterprise infrastructure to consumer apps · the 2026 plan.
stamp: Internal draft · v0.2
notes: 30-second open. The next four slides set the stage; this one is the punch line. Pause after the title.

## agenda :: Agenda // Opening
title: Five product lines · one map
lead: We are not adding products. We are collapsing thirty-plus initiatives into five lines that can win.
items:
  - Where we stand :: Numbers, gaps, the investor story
  - Five lines :: One product per segment
  - Bets we make :: H2 investments and trade-offs
  - Risks and unknowns :: What can break the plan
  - Decisions today :: What we need from this room

## section :: Where we stand // Chapter 1
num: "1"
eyebrow: Part 1 · Today
title: |
  Where we
  stand today
sub: Numbers, gaps, and the story we tell investors this quarter.

## kpi :: Today in numbers // Chapter 1
eyebrow: Q2 2026 · trailing
title: A healthy core, a noisy edge
lead: Strong renewal and retention. Too many small lines diluting the roadmap.
kpis:
  - num: "31"
    label: Active product lines
    foot: Across all BUs, including pilots
  - num: "94"
    unit: "%"
    label: Enterprise NRR
    foot: Trailing 12 months
  - num: "5"
    label: Lines proposed
    foot: Target after consolidation
  - num: "14"
    unit: days
    label: Median cycle time
    foot: Idea to first customer
note:
  eyebrow: Caveat
  body: NRR is healthy but masks line-level churn in SMB tier. Headline numbers should not lull the room.

## bullets :: Gaps we cannot ignore // Chapter 1
eyebrow: Diagnosis
title: Three structural gaps
lead: The portfolio runs because operators carry it. The structure does not.
items:
  - title: Too many small lines
    detail: Below-threshold lines consume 38 percent of engineering hours for 6 percent of revenue.
    tags: [P0, "orange:cost"]
  - title: No shared runtime
    detail: Every line reinvents auth, billing, and agent plumbing. Cross-product reuse is below 20 percent.
    tags: [P0, "teal:platform"]
  - title: Consumer story is missing
    detail: We have enterprise muscle and no consumer surface. Growth curve flattens in 2027 without one.
    tags: [P1]

## section :: Five lines // Chapter 2
num: "2"
eyebrow: Part 2 · The plan
title: |
  Five product
  lines, one map
sub: One product per customer segment. Cross-segment reuse via a shared agent kernel.

## matrix :: The portfolio at a glance // Chapter 2
eyebrow: Five lines · 2027 horizon
title: The portfolio at a glance
lead: One hero line funds the rest. Four supporting lines specialize by segment and channel.
hero:
  num: "01"
  title: Enterprise platform
  body: B-end fundamentals. Retention play. The cash engine and the moat. Everything else compounds against it.
  tags: [P0 · Cash cow, "Funded"]
cells:
  - num: "02"
    title: SMB self-serve
    body: Channel-led, fast deploy.
    tags: [P1, Growth]
  - num: "03"
    title: Agent kernel
    body: Cross-product runtime.
    tags: [P0, Platform]
  - num: "04"
    title: Consumer apps
    body: New growth curve.
    tags: [P2, Bet]
  - num: "05"
    title: Internal R&D
    body: Org capability and scaffolding.
    tags: [P1, Enabler]

## two-col :: Build vs. buy // Chapter 2
eyebrow: Make-or-buy
title: Where we build · where we partner
lead: We build the kernel and what touches customer trust. We partner everywhere else to preserve speed.
col1:
  eyebrow: Build
  title: Owned by us
  items:
    - Agent kernel and shared runtime
    - Enterprise identity and audit trail
    - Customer data plane and consent
    - Pricing, billing, and metering
  foot: Build list locked at end of Q3. No additions without exec approval.
col2:
  variant: accent
  eyebrow: Partner
  title: Bought or integrated
  items:
    - Foundation models (multi-vendor)
    - Observability and tracing
    - Email, comms, payments rails
    - Document storage and search index
  foot: Partner contracts re-bid annually. No vendor over 35 percent of spend in any layer.

## section :: Bets and risks // Chapter 3
num: "3"
eyebrow: Part 3 · Trade-offs
title: |
  The bets
  we make
sub: Where we invest now, and what we accept may go wrong.

## bullets :: H2 investments // Chapter 3
eyebrow: Funding pattern
title: Three bets, three constraints
lead: Each bet has a defined kill-criterion. Nothing is open-ended.
items:
  - title: Double down on the kernel
    detail: Move 18 engineers off retired SMB lines to the kernel team by Oct 1. Target M3 cross-product reuse above 60 percent.
    tags: [P0, "teal:platform"]
  - title: Consumer alpha
    detail: "Closed alpha by Dec 15 with 200 users. Kill criterion: under 25 percent week-2 retention or cost-per-active above 8 USD."
    tags: [P2, "orange:risk"]
  - title: Enterprise renewal motion
    detail: Pre-renewal QBR program covering top 80 accounts. Target plus 4 points to gross retention by Q4.
    tags: [P0]

## close :: Decisions we need today // Wrap
eyebrow: M0 · M3 · M6
title: Decisions today
sub: Three open questions. We leave this room with answers, or we leave with another meeting on the calendar.
questions:
  - Which three lines do we fully fund through 2027?
  - Build the agent kernel as its own team, or grow it inside the platform?
  - When do we kick off the consumer alpha, and who owns it end-to-end?
notes: Push for written commitments, not nods. If we cannot decide today, we name the decider and the deadline before we leave.
