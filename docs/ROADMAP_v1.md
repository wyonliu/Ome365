# Ome365 v1.0 Roadmap · 2026 Q2 → 2026 Q4

**Status:** Draft · 2026-04-19
**Current version:** v0.9.7 (multi-tenant + zero-friction install, 2026-04-18)
**Target:** v1.0 GA · 2026 Q4

**Guiding principle — the 2026 Q1 consensus:**
1. `Agent = Model + Harness` (Hashimoto, Feb 2026)
2. Multi-agent is back — Opus 4.6 Agent Teams, GitHub Copilot Swarm (Q1)
3. Skills > plugins — skills.sh 91k installs in Q1
4. MCP Apps > custom UI — Anthropic + OpenAI joint spec, Jan 2026
5. File system > memory-layer — Google Context Repositories, Apr 2026
6. Sleep-time compute — ICLR 2026 workshop

---

## Four tracks to v1.0

### Track 1 · Agent Teams for the cockpit

The cockpit today has one assistant. v1.0 gives it a team.

- **#1 · `scribe` sub-agent** — captures every 1:1 / meeting summary into Journal/Notes
- **#2 · `analyst` sub-agent** — reads reports, updates cockpit evidence + KPI trend
- **#3 · `scout` sub-agent** — watches competitors, briefs the CTO weekly
- **#4 · `executor` sub-agent** — drafts PRs / issue responses from cockpit intent
- **#5 · Team orchestration UI** — `/t/{tid}/team` panel showing each agent's queue and output
- **#6 · File-system workspace** — `/agent-workspace/<task-id>/` convention (no in-memory queue; human-inspectable)

### Track 2 · MCP Apps Layer

Make Ome365 a first-class citizen in Claude Desktop / Cursor / Zed / Warp.

- **#7 · MCP server skeleton** — `packages/ome365-mcp/` exposing `today`, `recall`, `capture`, `ask`
- **#8 · MCP App renderer** — cockpit cards as inline HTML in chat clients
- **#9 · `@ome365 cockpit`** — render cockpit section inline on demand
- **#10 · Auth passthrough** — OIDC / magic-link reused via MCP

### Track 3 · Skills & Harness integration

Turn the working cleaners / exporters into distributable skills.

- **#11 · `ticnote-clean` published to skills.sh** — first pilot (skeleton already in `skills/ticnote-clean/`)
- **#12 · `interview-to-cockpit` skill** — ingests a TicNote export, extracts evidence, updates cockpit yaml
- **#13 · `report-fact-check` skill** — runs the FACT-CHECK audit pass
- **#14 · `journal-weekly-summary` skill** — Sunday consolidation
- **#15 · Harness engine adoption** — migrate our server-side agent calls to depend on `mindos.harness` (via `packages/mindos` or pypi pin) — see [Ome / Mindos dev guidance](../Projects/Ome/architecture-2026-04-19.md) for the shared kernel contract.

### Track 4 · Sleep-time consolidation

Nightly jobs that keep the vault healthy without the user doing anything.

- **#16 · Scheduler** — cron-like dispatcher inside `.app/sleep_scheduler.py`
- **#17 · Weekly summary job** — Journal/Notes → `Insights/weekly-<YYYY-Www>.md`
- **#18 · Persona-delta job** — extract incremental user insights
- **#19 · Skill-suggestion job** — recommend skills based on last 7 days
- **#20 · Context Repositories compliance** — every vault directory carries `INDEX.md` + `.meta.json`

---

## Non-goals (explicit avoid list)

- No custom memory layer (Letta / Mem0 compete here — we win with file system + skills + harness)
- No custom plugin format (SKILL.md is the standard, we are a citizen)
- No AI hardware bet (Humane dead, Limitless acquired, Rabbit R2 slipped)
- No coding agent (saturated by Claude Code / Cursor / Devin)
- No "AI for everything" platform (Gartner: 40% of agentic projects canceled by 2027)

---

## Ome365 ↔ Ome / Mindos — strict decoupling contract

Shared kernel (upstream: Omnity main repo):
- File System Memory spec (directory + INDEX.md + .meta.json)
- SKILL.md spec (Anthropic)
- MCP Apps renderer spec (Anthropic + OpenAI)
- Harness Engine core interface

Diverged shells:
- Ome365 owns: cockpit UI, multi-tenant, AuthProvider, pre-commit blocklist, enterprise install (curl|sh)
- Ome / Mindos owns: personal CLI, chat UI, iOS, MR, harness/agent-team/sleep-time implementation

Rule: Ome365 never forks kernel code. Bugs → upstream PRs. Version pins via `requirements.txt`.

Full contract in [Projects/Ome/architecture-2026-04-19.md](../Projects/Ome/architecture-2026-04-19.md) and the Omnity sibling doc.

---

## Sequencing proposal (6-week sprints)

| Sprint | Weeks | Focus |
|---|---|---|
| v0.10 | W1–W2 (04-20 → 05-03) | `ticnote-clean` skill publish · MCP server skeleton · Track 3 #11 / Track 2 #7 |
| v0.11 | W3–W4 (05-04 → 05-17) | `scribe` sub-agent + workspace convention · Track 1 #1 / #6 |
| v0.12 | W5–W6 (05-18 → 05-31) | MCP Apps renderer + `@ome365 today` / `cockpit` · Track 2 #8 / #9 |
| v0.13 | W7–W8 (06-01 → 06-14) | Sleep-time scheduler + weekly summary · Track 4 #16 / #17 |
| v0.14 | W9–W10 (06-15 → 06-28) | `analyst` + `scout` sub-agents · Track 1 #2 / #3 |
| v0.15 | W11–W12 (06-29 → 07-12) | Harness engine adoption (consume upstream) · Track 3 #15 |
| v1.0 GA | Q4 | Polish, docs, enterprise onboarding playbook, case study |

---

## Open questions (to resolve before v1.0)

1. **Packaging:** `skills/` ships inside Ome365-git, or moves to a separate repo published to skills.sh?
2. **Upstream dependency:** Does Ome365 pull `mindos` as a git submodule, a pypi package, or a vendored copy?
3. **Multi-agent billing:** Per-call metering or flat enterprise subscription?
4. **MCP Apps security model:** How does Ome365 enforce tenant isolation when rendered inside Claude Desktop?
5. **Kimi K2 / Qwen3 backend support:** Priority vs staying Anthropic-only for v1.0?

---

## References

- [Mitchell Hashimoto — Harness Engineering (Feb 2026)](https://mitchellh.com/writing/harness-engineering)
- [Anthropic — Claude Opus 4.6 + Agent Teams (Feb 2026)](https://www.anthropic.com/news)
- [Anthropic + OpenAI — MCP Apps Extension (Jan 2026)](https://modelcontextprotocol.io)
- [Vercel — skills.sh launched (Jan 2026)](https://vercel.com/blog)
- [Google DeepMind — Context Repositories (Apr 2026)](https://deepmind.com/research)
- Companion doc: [`Projects/Ome/architecture-2026-04-19.md`](../Projects/Ome/architecture-2026-04-19.md) (in the data vault)
- Omnity dev guidance: `~/root/code-ai/omnity/OME_MINDOS_HARDCORE_DEV_GUIDANCE_2026-04-19.md`
