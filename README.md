# Ome365

**AI-native personal OS** — Memory · Reflection · Execution · Persona-growth
**AI 原生个人操作系统** — 记忆 · 反思 · 执行 · 养成

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.1.20-blue" alt="v1.1.20">
  <img src="https://img.shields.io/badge/python-3.9+-blue" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/vue-3.x-green" alt="Vue 3">
  <img src="https://img.shields.io/badge/storage-markdown-orange" alt="Markdown">
  <img src="https://img.shields.io/badge/AI-Omnity--Ome%20SDK-purple" alt="Omnity Ome">
  <img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="Apache 2.0">
</p>

---

## TL;DR (English)

> **Tagline**: Run your company on agents, not org charts.
> **Sub-tagline**: Your AI follows the employee, not the employer.

**Ome365** is **the file-first vault for the Agentic Web** — your team's `SKILL.md` is **spec-compatible** with 32 tools that adopted [Anthropic's open Agent Skills standard](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) (Claude Code · Codex · Cursor · Gemini CLI · JetBrains Junie · AWS Kiro · Block Goose · etc). **Runtime-tested** in CI on 3-4 headless CLIs (Claude Code · Codex CLI · Gemini CLI · Continue.dev) — IDE hosts are community-verified, not CI-gated (we don't pretend to spin up GUIs in GitHub Actions). Multi-tenant Markdown vault · self-learning **Hike** (Hive Intelligence Knowledge Engine · L4 Wiki Maintainer follows [Karpathy's LLM Wiki Pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)) · cross-company portability via W3C DID. FastAPI + Vue 3 CDN (zero build).

> **🚀 v1.1.x ships team-brain + productization (2026-05-09).**
>
> 12 modules · 441 pytest tests · 0 PII · ed25519-signed agent-card · RBAC ·
> i18n · async trace · perf 194× cache speedup proven.
>
> Quick tour:
> ```bash
> ./ome365                 # boot at localhost:3650
> open http://localhost:3650/v1_1.html  # 4-card cockpit (Decisions/Skills/FinOps/Eval)
> ./ome365 status          # one-glance vault overview
> ./ome365 doctor          # 12-check diagnostic + 12 v1.1 module health table
> ./ome365 eval member alice --window-days 90   # CLI 7-dim eval
> ./ome365 verify <agent-card-url>              # ed25519 verify
> ./ome365 wiki update     # Karpathy distill Decisions → Knowledge/L2-distilled/
> ./ome365 backup create   # tar.gz the vault (data-portable)
> ./ome365 audit grep --actor alice  # SOC2/ISO27001-grade audit log
> ```
>
> Read the [HR usage policy](docs/policies/EVAL_USAGE_POLICY.md) before wiring
> eval to compensation; the answer is *"don't · it's a hint, not a verdict."*
> See [TEAM_ONBOARDING.md](docs/TEAM_ONBOARDING.md) for a 5-minute walkthrough.

> **Anti-Tokenmaxxing**: Ome365 measures **outcomes**, not tokens. We deliberately avoid token-leaderboard metrics (cf. [Meta 2026-04 incident](https://fortune.com/2026/04/09/meta-killed-employee-ai-token-dashboard/) · [Pinnacle critique](https://www.heypinnacle.com/blog/tokenmaxxing-performative-ai-hr-strategy-2026)) because performative AI usage corrupts the measurement. Member scores use **value/cost ratio** with FinOps-2026-aligned `cost_per_outcome` / `revenue_per_workflow` (see [v1.1 Team Brain design](docs/strategy/v1.1-team-brain-design.md)).

### 💼 How CIOs explain Ome365 to their CEO

Anti-Tokenmaxxing is a stance · here's how it translates to **dollars-out / dollars-in**
language any CFO can sign off on. Compare your team to industry P50 (data:
[`docs/strategy/industry-benchmarks.yml`](docs/strategy/industry-benchmarks.yml) ·
sourced from Salesforce / NavyaAI / Forrester 2026 Q1):

- "Each AI-resolved decision costs **$12** (industry P50: $35) — we save **$XX/month** vs hiring contractors."
- "Each hour our team spends with AI replaces **$80** of contractor time."
- "Each AI workflow generates **$1200** in tracked revenue."

No token leaderboards · no performative AI usage · just a [`cost_per_resolved_decision`](docs/strategy/v1.1-team-brain-design.md) you can put in next quarter's board slide. The cockpit FinOps card shows "your team vs P25/P50/P75" with source citation on hover.

> **🌐 LLM defaults to local Ollama** — DeepSeek / OpenAI / Claude / Gemini / Qwen / Doubao / 智谱 / OpenRouter (9 backends) are opt-in via `.env`. PIPL §38 compliant by default — no data leaves your machine unless you flip the switch.
>
> **🔒 Embedding defaults to local `BAAI/bge-small-zh-v1.5`** (90 MB CPU model) — OpenAI / Cohere / Qwen embeddings are opt-in via `.env`. Embeddings stay on your machine.

```bash
# One-line install (macOS / Linux / WSL):
curl -fsSL https://raw.githubusercontent.com/wyonliu/Ome365/main/install.sh | sh
# or:
git clone https://github.com/wyonliu/Ome365.git && cd Ome365 && ./ome365
```

**What's in the box (v1.0):** annual life-plan reader (10 endpoints) ·
share station with argon2 + Fernet + 3-word access codes + rename-resilient share_id ·
truthguard data-hygiene linter · **Hike v0.1** entity graph (8 entity types · cross-meeting person profiles) ·
GZipped responses · multi-tenant auth (none / basic / magic_link / oidc / wecom) ·
single-binary deploy via systemd / Docker / Compose · ~6000 LOC backend + ~2000 LOC frontend.

**Roadmap (90 days)**: Hike v2 (L2 Event + L4 Wiki Maintainer + L6 Swarm + UI 4 page) · PG+RLS multi-tenant ·
A2A federation (3 tier trust + Signed Agent Card) · ome365.id (tenant DID + 4 Skill VC types).
See [docs/hike.md](docs/hike.md) for the flagship sub-project.

### 🔬 Preview features (mock responses · real implementation in v1.1-v1.3)

We deliberately ship **mock-but-stable contract endpoints** for features whose real
implementation lands in upcoming releases. This lets you integrate against the contract
today without waiting · responses are flagged `_preview: true` so you never confuse
mock with production:

| Endpoint | Real ship | Mock today | Real then |
|:---|:---:|:---|:---|
| `/api/cost/*` (per-tenant LLM budget cap · Cost-per-Outcome FinOps) | **v1.1** (2026-07-14) | in-memory budget + warn/throttle/block enum | real LLM call interception via `LLMBackend` |
| `/api/identity/*` (W3C DID + 4 Skill VC types) | **v1.2** (2026-09-01) | placeholder DIDs + schema | real ed25519 signing + cross-instance verify |
| `/api/a2a/*` (3-tier trust + federation) | **v1.3** (2026-11-01) | trust-tier state machine | real Signed Agent Card + 2-instance demo |

Why we ship preview not vapor: 1238 lines of v0.1 stubs already exist · we mark them
honestly as `_preview` rather than hide them, so v1.2-v1.3 implementers have framework
to build on. See [`docs/strategy/MASTER-PLAN.md`](docs/strategy/MASTER-PLAN.md) for stub policy.

## See it in action

```
$ curl -fsSL https://raw.githubusercontent.com/wyonliu/Ome365/main/install.sh | sh

[install] Platform: macOS (arm64)
[ok] Python 3.11.5
[install] Cloning https://github.com/wyonliu/Ome365.git → ~/Ome365
[install] First run: ./ome365 (installs deps, starts service, opens browser)
✓ Browser opens at http://localhost:3650
✓ Hike entity graph ready (8 entity types · /api/hike/*)
✓ Share station ready (argon2 + Fernet · /share/<user>/<slug>)
✓ ome365.id ready (DID + 4 Skill VC types · /api/identity/*)
✓ ome365.a2a ready (3-tier trust + /.well-known/agent-card.json)
```

**Try without installing**:
- 🤗 [HuggingFace Space sandbox](https://huggingface.co/spaces/wyonliu/ome365-demo) (read-only · resets every restart)
- 🌐 [try.omnity.ai](https://try.omnity.ai) (custom domain · same demo)

**Self-host smoke** (verify your install in 30 seconds):

```bash
./ome365 doctor                              # 12-check diagnostic (platform / deps / config / runtime)
curl -fsS http://localhost:3650/api/dashboard | jq .day  # → today's date
curl -fsS http://localhost:3650/api/hike/entities | jq '. | length'  # → entity count
curl -fsS http://localhost:3650/.well-known/agent-card.json | jq .name  # → "Ome365"
```

**vs Notion / Obsidian / Mem / Logseq:**

| Need | Ome365 | Notion | Obsidian | Logseq | Mem |
|------|--------|--------|----------|--------|-----|
| Local-first .md storage | ✅ | ❌ | ✅ | ✅ | ❌ |
| Self-host | ✅ | ❌ | desktop only | ✅ | ❌ |
| AI features | optional, BYO key | Notion AI | plugins | plugins | core cloud |
| Multi-user share | argon2 + 3-word codes | workspaces | single-vault | — | ✅ |
| Visual cockpit / dashboards | config-driven | databases | plugins | graph | — |
| Data-hygiene lint (truthguard) | ✅ | — | plugins | — | — |
| No-build frontend | ✅ Vue CDN | — | n/a | n/a | — |
| Cross-meeting entity graph (Hike) | ✅ v0.1 / v2 alpha | — | — | partial | — |
| License | Apache 2.0 | proprietary | proprietary | AGPL | proprietary |

### vs Glean / Microsoft Copilot Studio / Cohere North

| Need | Ome365 | Glean | Copilot Studio | Cohere North |
|:---|:---:|:---:|:---:|:---:|
| Self-hosted (your data, your machine) | ✅ | ❌ SaaS | ❌ Azure | ❌ SaaS |
| File-first vault (git-diffable markdown) | ✅ | ❌ vector | ❌ vector | ❌ vector |
| Open source | ✅ Apache 2.0 | ❌ | ❌ | ❌ |
| Personal AI follows employee (W3C DID) | ✅ ome.id | ❌ | ❌ | ❌ |
| Multi-tenant (team / org) | ✅ | ✅ | ✅ | ✅ |
| Cross-org A2A federation | ✅ ome365.a2a (v0.1 stub) | ❌ | ❌ | ❌ |
| Decision distillation (6-stage cognition) | ✅ Hike L4 (v2 alpha) | ❌ retrieval-only | ❌ | ❌ |
| Pricing | Self-host free / ¥10-30 万 enterprise | $40-50/seat/mo | $200/user/mo | $30+/user/mo |

**Why Ome365 over Glean**: Glean optimizes search retrieval; Ome365 optimizes **organizational memory + decision distillation**. Glean's $200M ARR is built on enterprise vector search — but it has no personal layer that follows the employee, no file-first transparency, no cross-org federation, no open source.

**Why Ome365 over Copilot Studio**: Copilot Studio binds to M365 / Azure ecosystem; Ome365 is **vendor-neutral file-first** — your vault lives wherever you put it, your AI runs on your machine, and the protocol is open (W3C DID + A2A v1.0).

---

## 为什么需要 Ome365？

你有 365 天。一年后的你，和现在有什么不同？

Ome365 不是笔记工具。它是一个**会记住你、理解你、帮你执行**的个人操作系统：

- **记忆** — 基于 Omnity-Ome SDK，AI 自动从对话和速记中积累记忆，越用越懂你
- **反思** — 一键生成今日/本周复盘，综合日志、速记、联系人、任务全量数据分析
- **执行** — 365天计划拆解到季→月→周→日，每一天都有明确的下一步
- **养成** — 把 AI 当数字生命养成，4 阶段成长 × 7 级羁绊 × 12 个成就

## v1.0 看点（公开发布）

- **本地优先 · AI 原生 · 零依赖前端** — Markdown + JSON 存储，FastAPI + Vue 3 CDN，无打包步骤
- **零摩擦安装** — `curl -fsSL .../install.sh | sh` 一行装完，或 `git clone && ./ome365` 两步；首跑自动装依赖、复制 `.env`、起服务、开浏览器
- **`./ome365` 极简启动器** — `--port` / `--no-open` / `--setup` / `doctor` 自检，单文件零依赖
- **多场景部署** — `./setup.sh` 向导一键生成 solo / family / demo / enterprise 四种 tenant 配置，Docker / Compose 也开箱即用
- **生活规划阅读器** — `/api/life/plan/*` 把 Markdown 写的年度规划解析成 dashboard / today / week / hero 视图（10 个端点）
- **分享站 + 密码保护** — 三词访问码（wordlist 生成）+ argon2 密码 + master_key/Fernet 可逆加密，文档改名/移动也不丢分享链接
- **truthguard 数据洁癖** — 内置 PII / ASR / hallucination 防污染 lint 工具，CI gate 友好
- **多租户 HTTP 隔离加固** — `/t/{tid}/` path-prefix 正确路由，跨租户 session 被全线拒绝（Basic / Magic Link / OIDC / Wecom）
- **E2E 测试扩至 110 项** — 新增 session GC、cookie Secure、HTTP 多租户、Magic Link 真实链路、OIDC Mock IdP、CLI 冒烟共 6 套

### 历史版本

<details>
<summary>v0.9.6 — AuthProvider 抽象 + 一键部署向导</summary>

- none / basic / magic_link / oidc / wecom 5 种 auth provider
- SQLite session store 可撤销
- `./setup.sh` solo / family / demo / enterprise 场景向导
- Docker compose profile
</details>

<details>
<summary>v0.8 — AI 智能速记</summary>

- 悬浮入口一键跳转速记页，输入任意内容后「速记」直接保存或「⚡ 智能」AI 分析提取
- 独立反思视图 / Ome 记忆 hover 编辑删除 / AI 调用 `asyncio.to_thread()` 非阻塞
</details>

<details>
<summary>v0.6 — Omnity-Ome 智能体接入</summary>

- Ome SDK 驱动的记忆/对话/养成一体化
- 记忆搜索 + 类型筛选
- 成长阶段门控 + 成熟度诊断
</details>

<details>
<summary>v0.5 — 统一清单 + 养成自进化</summary>

- 统一清单视图（今日/明日/本周/本月/日子 Tab 切换）
- 跨天任务可见，养成自进化计数
</details>

<details>
<summary>v0.4 — AI 智能录入</summary>

- 粘贴任意内容，AI 自动提取联系人/事件/待办/笔记
- 养成页双栏重设计，速记单条删除
</details>

<details>
<summary>v0.3 — 养成系统 + 提醒</summary>

- 数字生命养成，闹钟提醒，AI 主动消息
- 时间块管理，记忆增强 AI 对话
</details>

<details>
<summary>v0.2 — 记忆系统</summary>

- 多层记忆，全文搜索，AI 反思
- 心情/能量/专注度追踪，连续打卡
</details>

<details>
<summary>v0.1 — 基础</summary>

- 365天作战地图，日/周任务，速记，决策日志
- 关系网络，重要日子，AI 助手，暗色主题
</details>

## 快速开始

### 极简（一行起步）

```bash
git clone https://github.com/wyonliu/Ome365.git
cd Ome365
./ome365
```

首次运行自动装依赖、复制 `.env`、启服务、打开浏览器。默认 `solo` 模式（单人自用、无认证）。

常用：
- `./ome365 --port 8080` — 换端口
- `./ome365 --no-open` — 不开浏览器（SSH / 服务器）
- `./ome365 doctor` — 自检依赖、端口、配置
- `./ome365 setup` — 进入完整向导（family / demo / enterprise 场景）

### 其它部署场景

```bash
./setup.sh                 # 交互式向导：solo / family / demo / enterprise
./setup.sh --mode family   # 家庭小团队（密码 / magic link）
./setup.sh --mode demo --demo-password mySecret
```

更多场景见 `docs/deploy/`。

### Docker

```bash
docker compose up -d
```

### 配置 AI

在「设置」页面选择模式：

| 模式 | 推荐 | 说明 |
|------|------|------|
| **API** | DeepSeek | 直连快速，中文好，`deepseek-chat` 即可 |
| **API** | OpenRouter | 可切换多家模型，需代理 |
| **Ollama** | llama3.1 | 完全离线，需本地算力 |

> 反思质量与模型强相关。DeepSeek Chat 性价比最高；Claude Sonnet 质量最好。

## 目录结构

```
Ome365/
├── .app/                    # 应用代码
│   ├── server.py            # FastAPI 后端（3000+ 行）
│   └── static/              # 前端 Vue 3 CDN（零构建）
├── Journal/                 # 日记（Daily/Weekly/Monthly/Quarterly）
├── Notes/                   # 速记（每日一文件）
├── Memory/                  # AI 记忆 + 反思洞察
│   ├── insights/            # AI 反思文档（daily/weekly）
│   └── *.md                 # 手动记忆文件
├── Decisions/               # 决策日志
├── Contacts/people/         # 联系人档案
├── 000-365-PLAN.md          # 年度计划
└── CLAUDE.md                # AI 集成桥接
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.9+ / FastAPI / Uvicorn |
| 前端 | Vue 3 CDN + marked.js（零构建） |
| 存储 | Markdown + JSON 文件（本地优先） |
| AI 记忆 | Omnity-Ome SDK（SQLite 向量存储） |
| AI 对话 | OpenAI 兼容 API / Ollama |
| 语音 | faster-whisper（本地转写） |
| 关系图 | force-graph 力导向布局 |

## 设计理念

1. **本地优先** — 数据在你的磁盘上，Markdown 纯文本，永远可读可迁移
2. **零构建** — 前端 Vue CDN，后端单文件 Python，`python3 server.py` 即跑
3. **AI 增强不依赖** — 不配 AI 也能完整使用，配了之后体验指数级提升
4. **记忆驱动** — AI 不是每次从零开始，而是越用越懂你
5. **自进化** — 每个操作都在让系统更了解你，养成数字生命

## License

**Apache License 2.0** — see [`LICENSE`](LICENSE) for the full text and [`NOTICE`](NOTICE) for attribution.

Why Apache 2.0:
- Same license as Mindos / Ome SDK / ome-server / memorybench across the Omnity matrix (one-license policy · zero confusion)
- Aligned with 2026 Chinese open-source agent ecosystem (Coze / AgentScope / ModelScope-Agent / Qwen3 / DeepSeek)
- Patent grant + trademark protection without copyleft burden
- 央企/金融法务零摩擦（vs AGPL 在中国央企采用率几乎 0）

**v1.1+ enterprise track**: Future Enterprise modules (PG+RLS / FinOps / decision-distillation UI / SOC2 / audit) may adopt a separate commercial license (BSL 1.1 → Apache 2.0 4-year auto-conversion · HashiCorp pattern). Templates are reserved at [`docs/legal/`](docs/legal/) for that future track. **The OSS main will always remain Apache 2.0**.

> *Strategy*: open-source main抢心智 (Apache 2.0) → if hyperscaler appropriation becomes a real threat post-launch, switch Enterprise modules to BSL 1.1 (HashiCorp Aug 2023 pattern · 4 years to auto-conversion). Path is open. **No bait-and-switch on the OSS main.**

---

> *"你有365天。每一天都是一次选择的机会。"*
