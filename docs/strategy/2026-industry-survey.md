# 2026 企业 AI 产品形态 · 状态调研 + Ome365 对齐分析

> **Status**: living document · 主动 web search · 2026-05-08 首版
> **Purpose**: 不再"被告知再吸收"·每月扫一次顶级实践·校准 Ome365 设计
> **Next refresh**: 2026-06-08（每月一次）

---

## 〇 · 为什么写这份

之前 v1.1 设计是"基于 vault 已有材料抽取 + 自洽设计"·**没主动调研行业**。CTO 5-8 复盘后要求"主动搜最新更好的实践"。

本档 = 一次性 8 维度真搜索·实际用 8 个 web query·**结果是发现 10 个突发动态我之前不知道**。

---

## 一 · 2026-05-08 真搜索结果 · 10 件大事

### 1.1 Anthropic Agent Skills 已是跨厂商开放标准（震级最大）

> ⚠️ **Spec maturity vs production adoption gap**：以下数字是"声称兼容 spec"·不是
> "production 部署成熟度"。Spec adoption ≠ runtime 可靠性·尤其 IDE 类工具的实际
> SKILL load + execute 流程·**多数没在 GitHub Actions 真跑过**。我们 CI 拆 spec lint
> (32/32) vs runtime test (3-4 headless CLI) 就是为了不混淆这两层（见 Fix 1）。

**Dec 18 2025**：Anthropic 发布 SKILL.md spec
**48 小时内**：Microsoft 集成进 VS Code · OpenAI 集成进 ChatGPT + Codex CLI（spec 接入·非 production GA）
**90 天内 (Mar 2026)**：32 个工具**声称 spec-compatible**·实际生产级稳定运行的是 4-6 个 headless CLI
- Google Gemini CLI
- JetBrains Junie
- AWS Kiro
- Block Goose
- Cursor
- Continue.dev
- 共 32 个

**Anthropic + OpenAI + Block** 合办 **Agentic AI Foundation (AAIF)** · Google/MSFT/AWS 加入。

**Anthropic 把 MCP 捐给 Linux Foundation（Dec 9）**·从公司项目变中立标准。

**对 Ome365 的意义**：
- vault/Skills/ **必须 100% Anthropic SKILL.md spec 兼容**·CI 加 32 工具兼容验证
- 我们不是"做自己的 skill 格式"·**是这个开放生态的 vault 实例**
- 一句话定位升级：**"Ome365 = the file-first vault for the Agentic Web"**

**Sources**:
- https://thenewstack.io/agent-skills-anthropics-next-bid-to-define-ai-standards/
- https://www.paperclipped.de/en/blog/agent-skills-open-standard-interoperability/
- https://venturebeat.com/ai/anthropic-launches-enterprise-agent-skills-and-opens-the-standard

### 1.2 Karpathy LLM Wiki Pattern 已成显学

**核心 insight**：
> **"The wiki is the artifact, not the chat"** — Karpathy

意思：不是用户保养知识库 + 偶尔问 AI · 是 LLM 自己建并保养·**用户只是 viewer**·LLM 是 maintainer。

**已有 OSS 实现**：
- `Ar9av/obsidian-wiki` — Framework for AI agents to build/maintain Obsidian wiki
- `AgriciDaniel/claude-obsidian` — Claude + Obsidian wiki vault
- `Kompl` — provenance tracking + multimodal

**命令模式**（OSS 已统一）：
- `/wiki-update` — 扫项目 · 抽精华 · 写到 vault · 不复制代码 · 蒸馏
- `/wiki-query` — 跨 vault 检索 · 给带 citation 的合成答案

**对 Ome365 的意义**：
- Hike L4 Cognition extraction = `/wiki-update` 的具体实现
- 我们应该**明确借用 Karpathy 术语**·不发明新词
- Skills/ 加两个核心 SKILL：`hike-wiki-update.md` + `hike-wiki-query.md`·向 Karpathy 致敬 + 兼容生态

**Sources**:
- https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- https://www.mindstudio.ai/blog/andrej-karpathy-llm-wiki-knowledge-base-claude-code

### 1.3 Cost per Outcome 已替代 Cost per Token

**最震撼的数据**（2026-04 Salesforce + NavyaAI 报告）：
- **Token 价格降 99.7%**
- **企业 AI 支出 3 倍涨到 $37B**
- **72% 成本不在推理**
- **Agentic workflow 50-500× 用量倍增**

**结论**：**Cost per Token 是错误指标**·Board 已不要 Token spend chart。

**2026 标准**：
- **Cost per Resolved Ticket**（不是 Total Token Spend）
- **Human-Equivalent Hourly Rate**（AI compute vs 人工时薪）
- **Revenue per AI Workflow**（业务产出 vs 推理消耗）

**FinOps 治理也成主流**：
- 2024 **31%** AI 由 FinOps 管 → 2025 63% → 2026 **98%**
- 78% FinOps 团队向 CTO/CIO 报告

**对 Ome365 的意义**：
- 我们 D2_ai_efficacy = sum(value)/sum(cost) **架构方向是对的**·**but 没用行业术语**
- 必须改：D2 改名 **"Cost per Outcome"**·D6 改名 **"Revenue per Workflow"**
- finops_summary 必须加：cost_per_resolved_decision / human_equivalent_hourly / revenue_per_workflow

**Sources**:
- https://blogs.nvidia.com/blog/lowest-token-cost-ai-factories/
- https://www.navyaai.com/reports/ai-cost-report-token-prices-vs-ai-bill
- https://analyticsweek.com/inference-economics-finops-ai-roi-2026/

### 1.4 MCP Progressive Discovery 已 ship 真功能

**Claude Code 已用**：
- 工具不前置 load·按需 search
- 工具描述 > 10% context window 时自动 defer
- **85% token 节省**

**对 Ome365 的意义**：
- ome365.a2a `/api/a2a/task/create` 应用 progressive discovery
- vault/Skills/ list endpoint 默认只返 metadata·**真定义按需 load**
- 这天然契合我们 lazy 派生哲学

**Sources**:
- https://www.agentic-patterns.com/patterns/progressive-tool-discovery/
- https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/

### 1.5 MCP Code Mode（composable tool execution）

**Anthropic engineering blog 新发**：Code execution with MCP

**模式**：agent 不每个 tool call 一次推理·而是写一段小脚本·一次执行多个 MCP tool

**类比 Shell**：tools 可 pipe + script · MCP tools 提供 structured outputs

**对 Ome365 的意义**：
- LLMBackend 加 code_mode 选项
- vault/Skills/ 里的 SKILL 可声明 code_mode_compatible

**Sources**:
- https://www.anthropic.com/engineering/code-execution-with-mcp

### 1.6 Memory 生态多层栈格局明确

> ⚠️ **adoption maturity caveat**：以下 5 个产品都在 alpha-beta · production GA
> 真正稳定的只有 Letta + Mem0 两家·**SuperLocalMemory / Cognee 是 early adopter
> 阶段·真用 < 100 家**。spec 完成度 ≠ 生产可靠。

**生产 2026 用法**：不是单一架构·是组合栈：
- **Vector layer**（fuzzy recall · sqlite-vec / pgvector / Qdrant）
- **Episodic layer**（短期 coherence · 像我们 Trace/）
- **Graph layer**（实体关系 · 像我们 Hike L1）

**不同产品的占位**：
- **Letta** — OS-inspired pageable in-context · 长跑（数天）唯一选择
- **Mem0** — selective pipeline · **91% 降延迟 / 90% 节省 token**
- **Zep** — graph-based
- **Cognee** — ontology-based
- **SuperLocalMemory** — **local-first**（新盟友！）
- **Supermemory** — 新

**对 Ome365 的意义**：
- Hike 明确定位为 **episodic + graph 双层**·**缺 vector layer**
- v1.1 应加 sqlite-vec 抽 embedding（lazy 触发）
- 跟 SuperLocalMemory 联动 (file-first 同盟)

**Sources**:
- https://hermesos.cloud/blog/ai-agent-memory-systems
- https://mem0.ai/blog/state-of-ai-agent-memory-2026
- https://explore.n1n.ai/blog/ai-agent-memory-comparison-2026-mem0-zep-letta-cognee-2026-04-23

### 1.7 Decision Intelligence 已成 Gartner 大类

> ⚠️ **prediction vs production gap**：Gartner "75% 采纳" 是包括 PoC + 试点·
> 真 production scale-out 估测 < 20%（per Stanford EnterpriseAIPlaybook 2026-03·
> "95% pilots fail to production" 行业数据互证）。"DI 大类已建" ≠ 客户真上线。

**预测**：**75% 企业 2026 采纳 Decision Intelligence**（含 PoC + 试点）

**核心叙事变化**：
- 旧：dashboards need interpretation
- 新：**AI guides decisions**

**Gartner Magic Quadrant 已建**：Aera Technology / Improvado / Tredence / Sendero / Nakisa 等。

**对 Ome365 的意义**：
- 我们 Decisions/ + 6 步范式 + value_anchors = **decision intelligence as markdown**
- 可以 positioning 为 "OSS Decision Intelligence Platform"·**跟 Aera 对垒** but 文件优先 + Apache 2.0
- 文档加 "Decision Intelligence" 标签·进 Gartner 词汇圈

**Sources**:
- https://www.gartner.com/reviews/market/decision-intelligence-platforms
- https://improvado.io/blog/what-is-decision-intelligence
- https://www.cio.com/article/4128177/the-rise-of-genai-in-decision-intelligence-trends-and-tools-for-2026-and-beyond.html

### 1.8 Tokenmaxxing 是反例 · 我们的设计天然避开

**Meta 案例（2026-04 Fortune）**：
- 员工搞了个 token 用量 leaderboard
- Zuckerberg **不在前 250 名**（爆梗）
- Meta 重做绩效系统**奖励高 token 用户**
- 员工真的"hire AI agents 跑数小时刷 token"

**反对方（2026-04 Pinnacle）**：
> "Performance frameworks built around AI usage as a metric are measuring the wrong thing — usage is an input, what matters is whether the work is better, faster, or more impactful."

**对 Ome365 的意义**：
- 我们 D2 用 ROI（value/cost）**正好避开 tokenmaxxing**
- 这是真差异化·**应放显著位置 + 反 tokenmaxxing 立场**
- show-hn-draft.md 加一段"Why Ome365 is the anti-tokenmaxxing platform"

**Sources**:
- https://fortune.com/2026/04/09/meta-killed-employee-ai-token-dashboard/
- https://www.heypinnacle.com/blog/tokenmaxxing-performative-ai-hr-strategy-2026
- https://www.axios.com/2026/04/15/tokenmaxxing-ai-roi-metrics

### 1.9 企业 AI 真现实数据（2026 Q1）

**残酷数字**：
- **Gartner**：60% agentic AI projects 2026 fail（data readiness 问题）
- **Stanford Digital Economy**："95% of generative AI pilots fail to reach production"
- **过 90% 公司用 AI · 仅 1/3 scale to functions**

**失败根因**：
- 不是模型质量·是 **workflow integration + organizational incentive misalignment**

**对 Ome365 的意义**：
- file-first + git diff + 1 行 rsync 带走 vault·**正好解决 workflow integration 问题**（vault 跟人走·不跟系统走）
- 我们卖点不是"更聪明的 AI"·是"**更可携的 vault**"

**Sources**:
- https://digitaleconomy.stanford.edu/app/uploads/2026/03/EnterpriseAIPlaybook_PereiraGraylinBrynjolfsson.pdf
- https://www.forrester.com/blogs/google-cloud-next-2026-the-end-of-the-ai-pilot-era/

### 1.10 Moxt EverMemOS · Memory Genesis Competition 2026

**Moxt 2026 新品**：
- **EverMemOS**（powered by EverMind）entering beta · 在新云平台
- **Memory Genesis Competition 2026** 推出

**含义**：Moxt 从 workspace 产品 → memory layer 产品·**也在 memory 主战场**

**对 Ome365 的意义**：
- Memory 战场拥挤·我们不要做 memory layer·**做 vault layer**（一层之上）
- vault/.ome365/index.db 是 cache · 真存储是 markdown · 这是真差异化

---

## 二 · v1.1 设计需要的 6 处 reframe

### Reframe 1: 一句话定位升级

**v1.0 现版**："Ome365 = your team's brain as a folder of markdown files"

**v1.0 升级（吸收 1.1）**：

> **"Ome365 = the file-first vault for the Agentic Web. Read the same SKILL.md that 32 tools read."**

**改动**：突出"32 tools 读同一份"·**接住 Anthropic 标准的红利**·这是 free distribution。

### Reframe 2: D2 / D6 命名对齐 FinOps 行业术语

| 我之前命名 | 改为（行业术语） |
|:---|:---|
| D2_ai_efficacy = value/cost | **D2_cost_per_outcome** |
| D6_business_impact = sum(roi_actual) | **D6_revenue_per_workflow** |
| finops_summary | 加 cost_per_resolved_decision / human_equivalent_hourly / revenue_per_workflow 三视图 |

### Reframe 3: 显式声明"反 Tokenmaxxing 立场"

README 顶部加段（短）：

> Ome365 measures **outcomes**, not tokens. We deliberately avoid token-leaderboard metrics
> (see Meta 2026-04 incident) because performative AI usage corrupts the measurement.
> Every member's score is **value/cost ratio**, with 30-day rolling window and percentile within team.

### Reframe 4: Hike 接 Karpathy LLM Wiki 术语

**改动**：
- Hike L4 Cognition extraction → 改名 **Hike Wiki Maintainer**（致敬 Karpathy）
- 加两个核心 SKILL：
  - vault/Skills/hike-wiki-update.md
  - vault/Skills/hike-wiki-query.md
- 文档明确 cite Karpathy gist + obsidian-wiki repo

### Reframe 5: Memory 多层栈明确化

**v1.1 设计加新章**：Hike 在 memory 生态的占位

| Layer | 实现 | 我们位置 |
|:---|:---|:---:|
| Vector | sqlite-vec on bge-m3 embedding | 🟡 v1.1 加 |
| Episodic | Trace/*.jsonl | ✅ v1.1 |
| Graph (entity) | entity_registry.py | ✅ v1.0 已有 |
| Cognition (decision) | Decisions/*.md | ✅ v1.1 |
| OS-pageable in-context | (用户用 Letta 自配) | ❌ 不做 |

### Reframe 6: Positioning 进 Decision Intelligence 类别

vault/Decisions/ + 6 步范式 + value_anchors = **OSS Decision Intelligence**

文档加：
- Comparison table 加 Aera / Improvado / Tredence
- README 加 "OSS Decision Intelligence" 标签
- show-hn-draft.md 加段"Why we're the OSS DI for Agentic Web"

---

## 三 · v1.1 设计应新增的 7 个机制（学行业的）

| # | 新机制 | 学自 | v1.1 加多少代码 |
|:---:|:---|:---:|:---:|
| 1 | **Anthropic SKILL.md 100% 兼容 + 32 工具 CI 验证** | Anthropic 标准 | CI yml ~30 行 + test fixture |
| 2 | **MCP Progressive Discovery 实现** | Claude Code | ~80 行 (server.py 改 list endpoints) |
| 3 | **MCP Code Mode 可选 (LLMBackend.code_mode=True)** | Anthropic engineering | ~60 行 |
| 4 | **Karpathy /wiki-update + /wiki-query 命令** | obsidian-wiki | 2 SKILL.md + ~100 行 worker |
| 5 | **sqlite-vec 向量层接入（lazy build）** | 行业 vector layer 标准 | ~100 行 |
| 6 | **Cost-per-Outcome 三视图仪表盘** | Salesforce + Bessemer | 3 个 cockpit cards (~200 行 Vue) |
| 7 | **vault/.well-known/agent-card.json 接 AAIF 标准** | MCP 2026 roadmap | ~30 行 yaml |

**总增量**：~600 行 · 7 周冲刺正好可装下。

---

## 四 · 直接改动清单（执行级）

| # | 改动 | 文件 | 工时 |
|:---:|:---|:---|:---:|
| 1 | v1.1 design 加 §11 "Industry Alignment" | docs/strategy/v1.1-team-brain-design.md | 30min |
| 2 | README 顶部加"反 tokenmaxxing"段 | README.md | 5min |
| 3 | README 一句话升级 | README.md | 5min |
| 4 | show-hn-draft 加 "Why OSS DI" 段 | docs/launch/show-hn-draft.md | 30min |
| 5 | hike.md 加 Karpathy 致敬章 | docs/hike.md | 20min |
| 6 | docs/hike-templates/ 加两个核心 SKILL | docs/hike-templates/skills/ | 1h |
| 7 | CHANGELOG 加 industry alignment 节 | CHANGELOG.md | 10min |

**v1.0 launch 前能改完的**：1, 2, 3, 4, 7（约 1h）·**改完 v1.0 vs Ome365 立场更清晰**

**v1.1 实施周引入的**：5, 6 + 上面 §三 的 7 个机制

---

## 五 · 调研流程沉淀（自我更新机制）

接下来每月 8 号·主动跑这 8 条 web search·更新本档：

```
1. "AI native enterprise framework <YYYY-MM>"
2. "Anthropic Skills MCP roadmap <YYYY-MM>"
3. "Letta Mem0 production memory architecture <YYYY-MM>"
4. "AI agent FinOps cost per outcome <YYYY-MM>"
5. "decision intelligence platform <YYYY-MM>"
6. "file-first knowledge management markdown <YYYY-MM>"
7. "Moxt OR <new agent product> <YYYY-MM>"
8. "open source enterprise AI tools comparison <YYYY-MM>"
```

**输出格式**：每次更新加一节"§<月份> survey"·新发现 → 改 reframe / 加机制。

**Owner**: CTO 办公室
**SLA**: 每月一次 · 不超过 2 小时 · 必须真搜不靠 LLM 凭空答

---

## 六 · 一句话总结

> 之前 v1.1 设计 "架构对 · 实战 mechanic 缺一块"
> 主动搜后 "实战 mechanic 缺 7 块 + 行业术语没对齐 + 标准红利没接"
> 接下来 v1.1 修订 = **接 Anthropic + AAIF 标准 / 接 Karpathy / 接 FinOps 2026 / 反 Tokenmaxxing**
> 核心架构（file-first / 派生 lazy / GDPR）**不动**·**只是把"我们的好"用行业听得懂的词说出来**

---

**版本**：r1.0 · 2026-05-08 · 8 web search 实做
**下次更新**：2026-06-08 · 月度刷新
**Owner**: CTO 办公室
