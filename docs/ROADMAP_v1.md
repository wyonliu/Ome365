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

### Track 4 · Nightly consolidation (Overnight Soul Sync · downstream)

Nightly jobs that keep the vault healthy without the user doing anything. Core reranking/scoring/merging lives in **Mindos EvoLog (Overnight Soul Sync)** — Ome365 runs its tenant-side equivalent on top of that contract.

> **Naming note (2026-04-19):** we previously called this "Sleep-time consolidation". That collides with Letta's "Sleep-time Compute" brand, so upstream Mindos renamed its nightly pass to **Overnight Soul Sync** (a sub-feature of EvoLog, not a new subsystem). Ome365 follows the upstream name.

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

**Alignment with upstream (Omnity/Mindos W1-W6):** the Mindos side owns the shared kernel (Harness runtime / Skills registry / MCP Apps core / Overnight Soul Sync / OmeBench); Ome365 owns the enterprise shell (connectors / multi-tenant / Agent Studio / audit / SSO / on-prem). Full split in `NOTICE_FOR_OME365_W1_HARNESS_2026-04-19.md`.

| Sprint | Weeks | Ome365 focus | Mindos counterpart |
|---|---|---|---|
| v0.10 | W1–W2 (04-20 → 05-03) | **A 档**：`FsContextLoader` + `nightly.py` + `bench_cli.py`（详见 `REVIEW_OMNITY_W2-W6_2026-04-19.md` §3）· `ticnote-clean` published to skills.sh · MCP server skeleton | Skills Registry + first skills.sh publish |
| v0.11 | W3–W4 (05-04 → 05-17) | **B 档**：驾舱加 Overnight + Bench 卡片 · `scribe` sub-agent on `/agent-workspace/`（本地文件夹约定，不起 Agent Studio UI）| MCP Apps (SEP-1865) · Agent Teams unlock (W4) |
| v0.12 | W5–W6 (05-18 → 05-31) | **SSO/LDAP/OIDC hardening**（需商业化触发）· MCP Apps renderer (@ome365 today / cockpit) | Overnight Soul Sync (EvoLog nightly rerank/score/merge) |
| v0.13 | W7–W8 (06-01 → 06-14) | **Pilot-customer 端到端部署**（端到端联调 HarnessEngine 进 tenant 管线，需商业化触发）| OmeBench 公开榜（tenant-owner 语料样本） |
| v0.14 | W9–W10 (06-15 → 06-28) | **私有化部署包**（央企/金融，需商业化触发）· `analyst` + `scout` sub-agents | Kimi K2 Thinking real transport · Qwen3 backend |
| v0.15 | W11–W12 (06-29 → 07-12) | Harness engine adoption — depend on `mindos.harness` (pypi/submodule pin) | API 稳定化，SemVer 1.0 |
| v1.0 GA | Q4 | Polish, docs, enterprise onboarding playbook, case study | — |

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
- Omnity W1 notice (consumer contract): `~/root/code-ai/omnity/NOTICE_FOR_OME365_W1_HARNESS_2026-04-19.md`
