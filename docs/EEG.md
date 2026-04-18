# Ome365 · Enterprise Entity Graph（EEG · 企业实体知识图谱）

> 2026-04-17 · 船长 & 小安
> 目标：让 Ome365 内部的**企业术语 / 人名 / 组织 / 产品**作为精准常识，任何生成、检索、展示都基于统一事实源。

---

## 一 · 为什么这是 Ome365 的一级能力

通用 LLM 不知道：
- 某个 ASR 误读（如「XX」→「YY」）在企业语境里指谁
- 企业内部缩写（如「C1」「N3」）指哪条业务线，不是通用词
- 同一产品的多个俗称 / 音译变体（「Acme」=「艾克米」=「艾克美」）指同一个
- 口语化人称（「总 / 哥 / 姐」）分别对应谁

**企业智能体要靠谱，第一块必须硬的就是实体层**。否则：
- RAG 检索会漏（搜规范名召回不到 ASR 误读的录音段）
- 生成会错（把误读当作新人另立户头）
- 展示会乱（同一个人出现两个头像卡片）

EEG 把这件事做成 Ome365 平台的**公共基础设施**：单一事实源，所有模块消费。

---

## 二 · 数据模型

### 2.1 实体类型

| 类型 | 示例 | 典型字段 |
|------|------|---------|
| `person` | 示例张三、Alice | name / aliases / company / title / tenant / 关系 |
| `organization` | 示例集团、示例BU | name / aliases / parent / type（航道/BU/部门） |
| `product` | Dify、Claude Code、Vercel | name / aliases / vendor / category |
| `term` | AI、KPI、MVP | name / aliases / definition / scope |
| `abbr` | ARR、NPI、VPS、MAU | name / full_name / domain |

### 2.2 实体文件（源）

每个实体一份 Markdown，frontmatter 承载结构化事实，正文承载自由叙述（与现有 `Contacts/people/*.md` 同构）：

```yaml
---
id: alice_example                      # slug，租户内唯一
type: person
name: Alice Zhang                      # 规范显示名
aliases:                               # 所有别名 / ASR 误读 / 口语化称呼
  - 张三
  - 艾丽丝         # 音译
  - 张总           # 口语
  - Alice.Z        # 英文缩写
tenant: acme                           # 租户 slug
company: Acme Corp
title: CTO
confidence: high
evidence:
  - TicNote/2026-04-08/HR-入职沟通·2026-04-08.md
relations:
  - { type: reports_to, target: ceo_slug }
updated_at: 2026-04-17
---

## 关系背景
⋯（自由叙述）⋯
```

### 2.3 存储位置

```
$VAULT/Knowledge/entities/
├── people/                  # 现有 Contacts/people/ 升级
├── organizations/
├── products/
├── terms/
└── _index.json              # 运行时生成，保留读速度
```

**与现有 `Contacts/people/` 的关系**：向前兼容 — `Contacts/people/*.md` 被视为 `people/` 的一个视图，加载器两处都扫。新实体统一写进 `Knowledge/entities/`。

### 2.4 租户隔离

`tenant` 字段区分实体归属：
- `<tenant-slug>` — 某一家企业租户的全部实体
- `ome365` — Ome365 平台自身术语
- `personal` — 单用户/船长个人
- `public` — 行业通用（DeepSeek、Claude、Figma、GPT 等）

查询时按租户过滤。**这就是企业智能体平台的核心隔离层**。

---

## 三 · 能力 API

```
GET  /api/entities                        # 列表 / 分页 / type/tenant 过滤
GET  /api/entities/{type}/{id}            # 单实体详情
POST /api/entities/resolve                # 别名→规范名：{ text: "X总提了一下" } → { canonical: "—总提了一下", matches: [...] }
GET  /api/entities/asr                    # 所有 ASR 规则（app.js 消费）
GET  /api/entities/search?q=              # 模糊搜索（name + aliases）
POST /api/entities                        # 新增/更新（需审核）
GET  /api/entities/_pending               # 审核队列：pipeline 自动提取的待确认实体
```

`resolve` 是核心 — 任何被送进 LLM / 检索器之前的文本都过一遍规范化。

---

## 四 · 生态位：谁消费 EEG

| 消费者 | 用法 |
|--------|------|
| **TicNote 清洗管线** | 清洗时直接 `resolve()` 规范化转录，不再靠前端 ASR_FIXES 补丁 |
| **驾舱前端 app.js** | 启动时 `GET /api/entities/asr` 加载规则，`KNOWN_SPEAKER_MAPS` 改为动态 |
| **RAG 检索** | 查询前 `resolve()` 查询词；索引构建时扩展别名形成多路召回 |
| **Memory 层** | 记忆里存 `entity_id` 而非字面名字，跨会话不漂 |
| **Insights 合成** | 生成摘要前 canonicalize，避免「X和—是两个人」 |
| **Reports/驾舱可视化** | PERSON_DISPLAY_MAP 统一成 EEG 的 `name` 字段 |

---

## 五 · 吸收新实体的三种方式（由严到松）

1. **人工录入**（当前）：直接编辑 `Knowledge/entities/xxx.md`，`updated_at` 自动打点。
2. **TicNote 管线抽取**（半自动）：清洗脚本在文本里命名实体识别，命中新名字放入 `_pending/`，Web UI 出现审核卡片，船长一键 Approve/Reject。
3. **对话原位提取**（最松）：AI Chat 中船长随口说「—就是集团研发设计负责人」，系统自动 diff 现有实体并问「要不要更新 `—.md`？」。

**P0 只做 1+2**，3 属于 v1.1+。

---

## 六 · 置信度治理

每条事实（别名、关系、头衔）独立打置信度：

| level | 来源 | 策略 |
|-------|------|------|
| `high` | frontmatter 明写 / 本人自我介绍 / 3+ 处交叉印证 | 直接采信 |
| `medium` | 单次第三方提及 + 角色自洽 | 采信但记录 `source` |
| `low` | 单次提及 + 存在歧义 | 不写入 aliases，只进 `_notes` |

**血泪教训**：2026-04-17 前，「X」被当真人三次。所以：
- `aliases` 里每个条目必须有 `evidence` 指向至少 1 个文件；无证据不进。
- 若某别名在 N 个文件里同时指多个真实实体，该别名永远不进 aliases（属于歧义词）。

---

## 七 · 交付路线

### Phase 0 · 脚手架（本次提交）
- ✅ `docs/EEG.md` 本文件
- ✅ `Knowledge/entities/people/—.md` 等 12 个种子实体（从 TicNote 全量审计抽取）
- ✅ `Knowledge/entities/products/` + `Knowledge/entities/terms/`
- ✅ `server.py`: `/api/entities`, `/api/entities/resolve`, `/api/entities/asr`
- ✅ `app.js`: `ASR_FIXES` 启动时向 `/api/entities/asr` 热加载（保留硬编码兜底）
- ✅ `seed_entities.py`: 从 `Contacts/people/` + 租户术语参考文档一次性播种

### Phase 1 · 审核队列（下周）
- [ ] TicNote 清洗管线抽取人名到 `_pending/`
- [ ] Web 审核 UI：一行一条，Approve/Reject/Merge
- [ ] 合并冲突解决：两份实体如何合一

### Phase 2 · RAG 前置（两周）
- [ ] Whisper/转录后自动 `resolve()` 一遍
- [ ] 搜索/Chat 前自动 `resolve()` 查询词
- [ ] `entity_id` 回写到 Memory，跨会话稳定

### Phase 3 · 多租户 SaaS（与 v1.0 合并）
- [ ] `/users/{uid}/tenants/{tid}/entities/`
- [ ] 实体级访问控制（员工看不到董事长关系等）

---

## 八 · 这条路为什么能赢

Glean / Mem / Notion AI 的共同短板：它们的"企业知识"= 文档全文索引 + 向量检索。没有**实体层**，所以：
- 问「谁负责 C1 供应链？」得搜「C1 供应链」关键词，再让 LLM 从搜到的段落里猜
- 同一个人换了称呼（— / X / 杨总）召回就断

**Ome365 的差异化 = 显式 Enterprise Entity Graph**。搜索/生成/记忆都挂在这一层之上，召回率和准确率都会跳一档。
