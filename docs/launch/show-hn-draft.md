# Show HN draft · v0.1 (2026-05-08)

> Target launch: 2026-05-13 (Tue) · 8am PT (1pm UTC)
> Posting account: long-time HN user (need karma > 100 to land)
> Pre-flight checklist at the bottom.

---

## Title (≤80 chars · HN cuts at 80)

**Option A (chosen):**
```
Show HN: Ome365 – open-source enterprise AI platform, file-first multi-tenant
```
(76 chars)

**Option B (backup):**
```
Show HN: Ome365 – your AI follows the employee, not the employer
```
(64 chars · more provocative · use only if A doesn't land)

**Option C (technical-leaning):**
```
Show HN: Ome365 – Markdown vault + DID identity + A2A federation, Apache 2.0
```
(76 chars)

---

## Body (HN allows ~1500 chars · keep under 1200)

```
Hi HN — I've been building Ome365 for the last 90 days as my open-source bet on
how enterprise AI should actually be deployed.

The thesis: most "enterprise AI platforms" assume your data lives in their cloud,
under their schema, in their account. That breaks when (a) you change jobs, (b)
your company has 6 BUs that need different agents, (c) you need to actually own
your knowledge base. So Ome365 inverts it:

  • Markdown-first vault — every entity, decision, journal entry is a .md file
    on your disk. No proprietary schema, no vendor lock-in. Git-friendly.
  • Multi-tenant by design — auth_provider=none|basic|magic_link, per-tenant
    config + vault root, runs on your laptop or SOC2-grade infra.
  • Hike (entity graph) — 8 entity types, schema v0.2, 5 industry starters
    (manufacturing/healthcare/insurance/retail/law-firm). Auto-extracts
    decisions from meetings.
  • ome365.id (DID + 4 Skill VC types) — 3 transferable skills go with you when
    you leave; 1 stays with the employer. W3C did:web compatible.
  • ome365.a2a (Agent-to-Agent v1.0) — 3-tier trust (T1 Public / T2 Pinned /
    T3 Internal), Signed Agent Card, federation via /.well-known/agent-card.json.

Stack: FastAPI + Vue 3 (CDN, zero build) + SQLite/PG/KingbaseES via DAO layer.
Local embeddings default to BAAI/bge-small-zh-v1.5 (no OpenAI key required).
Apache 2.0, no CLA, no bait-and-switch — we explicitly reserve enterprise
features for v1.1+ paid track instead of relicensing core.

Try it:
  curl -fsSL https://raw.githubusercontent.com/wyonliu/Ome365/main/install.sh | sh
or: https://huggingface.co/spaces/wyonliu/ome365-demo (read-only sandbox)

Repo: https://github.com/wyonliu/Ome365
Docs: docs/hike.md (flagship sub-project) · docs/ARCHITECTURE.md · CONTRIBUTING.md (DCO 1.1)

What I'd love feedback on:
  1. The DID + Skill VC split — is "your AI follows the employee" obvious or
     does it need more framing?
  2. The Hike schema v0.2 five fields (parent_id / validity_period /
     external_ids / multilingual / disambiguation_hint) — sufficient for
     cross-system entity reconciliation, or missing something obvious?
  3. The 3-tier A2A trust model — anyone tried this in production yet?

Honest about the v1.0 scope: ome365.id and ome365.a2a are v0.1 stubs (state
machines + endpoints, no signing crypto yet — that lands D+5 to D+12). The Hike
v2 alpha (5 industry starters with real customer data) is D+7 to D+30. Roadmap
in docs/ROADMAP_v1.md.

Happy to answer anything in the comments.
```

---

## FAQ (anticipate top 10 HN comments)

**Q0. What's actually new vs Letta / Mem0 / Coze / Dify / Khoj?**
A: One sentence — **Ome365 is the file-first vault for the Agentic Web**. Three concrete
implications they don't have: (1) every Skill is a `SKILL.md` that 32 tools already read
(Claude Code, Codex CLI, Cursor, Gemini CLI, JetBrains Junie, AWS Kiro, Block Goose, etc
— Anthropic donated Skills to AAIF Dec 2025); (2) member evaluation uses **Cost-per-Outcome**,
not Cost-per-Token (FinOps-2026 aligned · we deliberately reject Tokenmaxxing — see
[Meta's 2026-04 token leaderboard incident](https://fortune.com/2026/04/09/meta-killed-employee-ai-token-dashboard/));
(3) every decision is an 8-step markdown file with `value_anchors` (P/XL/L/M/维护性/Revert)
that you can `git diff` 6 months later — not a black-box memory block.

**Q1. Why not just use Notion / Obsidian / Mem / Logseq?**
A: Those are PKM tools for one person's notes. Ome365 is multi-tenant infrastructure
with identity (DID) + federation (A2A) + entity graph (Hike). Different abstraction
layer. The README has an 8-dimension comparison table.

**Q2. Why not Glean / Copilot Studio / Cohere North?**
A: Those are SaaS-locked enterprise search/copilot platforms. Ome365 is OSS, runs
on your laptop, and your data never leaves your filesystem unless you explicitly
configure a remote vault. Different deployment posture entirely.

**Q3. Apache 2.0 + reserve enterprise features for paid v1.1+? Sounds like a trap.**
A: Fair concern. Three guardrails: (a) no CLA — contributors keep copyright;
(b) Apache 2.0 patent grant means we can't litigate against forks; (c) the v1.1+
features are *new* (audit log archival · federation registry · enterprise SSO
connectors) — we explicitly will NOT relicense core. See LICENSE + NOTICE.

**Q4. "Your AI follows the employee" sounds great but is the employer OK with it?**
A: That's the whole point of the 4-VC split. Skill types a/b/c (technical
transferable knowledge · personal patterns · industry expertise) follow the
employee. Skill type d (firm-specific proprietary) stays with the employer
when they leave. The employee + employer both get a verifiable credential at
issue time so it's auditable.

**Q5. How is this different from EnterpriseGPT / private Anthropic deployments?**
A: Different layer. Those are LLM serving platforms. Ome365 is the *application*
on top — the place your meeting notes, decisions, entity graph, identity, and
agent federation live. We're agnostic to the LLM (anthropic / openai / qwen /
local ollama all configurable).

**Q6. SQLite for enterprise? Really?**
A: SQLite is the default for solo / small-team. We have a DAO abstraction layer
with PostgreSQL (production multi-user) and KingbaseES (中国信创合规) adapters.
Same migrations file format, just `DATABASE_URL=postgres://...` to switch.

**Q7. What happens if I dump my whole Slack into this?**
A: It works (Hike L2 will treat each message as an event), but please don't —
the privacy posture changes. Audit log + rate limit don't yet handle a 10k-msg
import gracefully. v1.1+ will. For now, run the meeting/decision/MDT use case.

**Q8. PIPL / GDPR / HIPAA?**
A: PIPL §38 cross-border + GDPR Art. 28 DPA template ship in `docs/legal/`.
HIPAA needs additional safeguards (encrypted vault + BAA + audit retention) —
see `docs/hike-templates/healthcare/README.md` privacy section. We have a SOC2
Type 1 readiness checklist; actual SOC2 audit pending (D+30 ~ D+60).

**Q9. Why China-friendly out of the box (Qianwen / KingbaseES / Coze references)?**
A: I'm China-based and that's the regulatory environment I know best. The same
principles work globally — we have OpenAI/Anthropic/Cohere adapters and the DAO
runs on Postgres just fine. Apache 2.0 means no jurisdiction is locked out.

**Q10. Roadmap?**
A: docs/ROADMAP_v1.md. Top items: Hike L2 Event layer + L4 Cognition (decision
chain extraction) + 5 industry starters with design-partner data (D+7 ~ D+30).
ome365.id signing crypto + ome365.a2a federation registry (D+14 ~ D+45).

---

## Pre-flight checklist (run morning of 5-13)

```bash
# 1. CI green on main
gh run list --branch=main --limit=1
# expected: ✓ completed

# 2. Demo URL responds
curl -sI https://huggingface.co/spaces/wyonliu/ome365-demo | head -1

# 3. install.sh works on fresh VM (run on a clean Ubuntu)
curl -fsSL https://raw.githubusercontent.com/wyonliu/Ome365/main/install.sh | sh
cd ~/Ome365 && ./ome365 doctor
# expected: 12/12 checks pass

# 4. README.md badges all working
curl -sI https://github.com/wyonliu/Ome365 | grep -i 'status\|location'

# 5. License + DCO + CONTRIBUTING all in place
ls LICENSE NOTICE CHANGELOG.md CONTRIBUTING.md docs/legal/

# 6. Slack/Discord ready for first-comment-burst (need ~30 min monitor)

# 7. Show HN posting account verified · karma > 100
```

## Posting timing strategy

- **8am PT** (Tuesday) = best HN window per pg's data
- **NOT** Monday (low traffic) · **NOT** Friday afternoon (weekend kills momentum)
- Have 3 friends ready to upvote in first 15 min (HN throttles cold posts)
- **Author MUST be in comments first 2 hours** — that's what differentiates
  ranking. Aim for 30+ thoughtful replies in first 4 hours.

## Backup if HN doesn't land

- 1pm PT: cross-post to lobste.rs (smaller but discerning audience)
- next day: r/selfhosted + r/programming
- next week: HN "Tell HN" post about the journey

---

## What we are NOT shipping in v1.0 (be honest)

To preempt nitpicks:
- ❌ Real DID signing crypto (stubs only · D+5)
- ❌ Federation discovery beyond /.well-known (full registry · D+14)
- ❌ Hike L2/L4/L6 (alpha · D+1~D+45)
- ❌ Audit log archival to S3/MinIO (D+30)
- ❌ SOC2 Type 1 audit (Q3 2026)
- ❌ Mobile app (iOS/Android — Q4 2026 if community pulls)
- ❌ Conversational UI (we do CLI + web; chat-style coming v1.2)

Calling these out in the body itself will earn more credibility than hiding them.
