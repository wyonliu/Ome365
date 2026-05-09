# Ome365 计划主控 · 一处看全

> **Status**: master index · 2026-05-08 首版
> **Owner**: CTO 办公室
> **Refresh**: 每次大里程碑（v1.0 / v1.1 / v1.2 ship）后更新一次
> **Path**: `docs/strategy/MASTER-PLAN.md`

---

## 〇 · 10 秒 TL;DR

- **现在位置**：v1.0-rc1（24 round 完工）· 5-13 Show HN
- **一句话定位**：Ome365 = the file-first vault for the Agentic Web · 32 工具读同一份 SKILL.md
- **下一站**：v1.1 Team Brain（7-14 ship · 8 周冲刺 · 11 mechanic）
- **核心原语**：`vault/*.md = 数据库`·所有评估 / 决策 / 知识 / Token = 派生 lazy 计算

---

## 〇 · 时间线一张图

```
2026
 │
 │ v0.9.7 ────────● 已 tag · 一行远程安装 · 极简启动器
 │
 │ Round 1-19 ───● 12 round patch r1.0 收口 (LICENSE / embedding / Hike alias / id+a2a stub)
 │ Round 20-24 ─● 5-9 round 加码 (DAO + DR + 24 round 整合 + cost cap + hike schema + ...)
 │
 ▼ 5-08 ─────────● 今天 · 计划文档全套落档 · 真完工
 ▼ 5-09 ~ 5-13 ──┐
 │               │ v1.0 极简化 (4 件事 · 11h 工时)
 ▼               │   砍 stub 暴露面 · README 80 行 · show-hn 终稿 · 录 gif
 │               │
 ▼ 5-12 17:00 ──● Plan B 决策点（gif/视频/部署 < 3 完成 → 推迟 5-20）
 │
 ▼ 5-13 PT 11:00 ● 🚀 Show HN: Ome365 v1.0.0
 │
 │ 5-14 ~ 5-19 ─● Launch 复盘 + 社区反馈
 │
 ▼ 5-20 ────────● 🏁 v1.1 W1 启动
 │
 │ W1 ✅ SKILL.md 32 工具 CI 兼容 + 7-dim ome365_eval.py 骨架
 │ W2 ✅ Decisions 8 步 + value_anchors + Kevin git hook
 │ W3 ✅ Trace SDK (Python ctx mgr + CLI) + monthly rollup
 │ W4 ✅ D4 anchor scoring + Cost-per-Outcome dashboard + /api/eval router
 │ W5 ✅ /v1_1.html 4 cockpit cards + 5 role preset switcher
 │ W6 ✅ Karpathy wiki-update + wiki-query (rule-based · LLM 是 v1.2)
 │ W7 ✅ Moxt 95/5 archive + AAIF agent-card v1.1 surface
 │ W8 ✅ CHANGELOG + EVAL_USAGE_POLICY + version bump + git tag v1.1.0
 │
 ▼ 2026-05-09 ─● 🚀 v1.1.0 release · Team Brain · SHIPPED (250 tests · 0 PII)
 │
 │ 8-15 ~ 8-31 ─● v1.2 启动（ome365.id 真签名 + Hike L4 Wiki Maintainer）
 ▼ 9-01 ────────● 🚀 v1.2.0 release · 身份可携 + 决策蒸馏
 │
 ▼ 11-01 ───────● 🚀 v1.3.0 release · A2A 真联邦
 │
 ▼ Q4 ───────────● 🚀 v2.0.0 GA · 5 行业真 starter + MCP server
2027
```

---

## 一 · 文档地图（13 篇全索引）

### 1.1 策略层（`docs/strategy/`）

| # | 文件 | 行数 | 内容 |
|:---:|:---|:---:|:---|
| 1 | **MASTER-PLAN.md** ⬅ 本档 | ~ | 计划主索引 · 一处看全 |
| 2 | `v1.1-team-brain-design.md` | 574 | r2.0 final · 设计层 · schema/API/边界/8 周计划 |
| 3 | `v1.1-implementation-spec.md` | 816 | r1.0 · 实施层 · 7 维公式/算法/edge/测试矩阵 |
| 4 | `2026-industry-survey.md` | 323 | 月度行业调研活档 · 月度刷新 SOP |

### 1.2 路线层

| # | 文件 | 行数 | 内容 |
|:---:|:---|:---:|:---|
| 5 | `docs/ROADMAP_v1.md` | 140 | v1.0 launch + v1.1-v2.0 6 周 sprint 视图 |
| 6 | `docs/ARCHITECTURE.md` | - | 技术栈 + 4 阶段路线 + 数据流 |

### 1.3 子产品层

| # | 文件 | 行数 | 内容 |
|:---:|:---|:---:|:---|
| 7 | `docs/hike.md` | 144 | Hike (Hive Intelligence Knowledge Engine) v0.1 + v2 路线 |
| 8 | `docs/EEG.md` | - | Hike 前身·历史 reference |

### 1.4 启动层（`docs/launch/`）

| # | 文件 | 行数 | 内容 |
|:---:|:---|:---:|:---|
| 9 | `show-hn-draft.md` | 206 | Show HN 文案 · FAQ Q0-Q10 · pre-flight checklist |

### 1.5 运营层（`docs/operations/`）

| # | 文件 | 行数 | 内容 |
|:---:|:---|:---:|:---|
| 10 | `dr-runbook.md` | 280 | RPO 1h / RTO 4h · 8 章 DR SOP |
| 11 | `sandbox-setup.md` | - | HF Space 部署 + try.omnity.ai DNS |

### 1.6 法律层（`docs/legal/`）

| # | 文件 | 内容 |
|:---:|:---|:---|
| 12 | `DCO.md` / `DPA-template.md` / `AGPL-Compliance-Letter.md` / `BSL-EULA-template.md` | 4 模板 + README · v1.1+ 企业 track 预留 |

### 1.7 仓根

| # | 文件 | 内容 |
|:---:|:---|:---|
| 13 | `README.md` (293 行) / `CHANGELOG.md` (155 行) / `LICENSE` (Apache 2.0) / `NOTICE` | 仓门面 |

---

## 二 · 按读者分流（10 分钟到 2 小时）

### 2.1 🔰 第一次来（10 分钟）

读 3 篇即可：
1. **`README.md`** 顶部 TL;DR — 一句话定位 + Anti-Tokenmaxxing
2. **`docs/ROADMAP_v1.md`** §Sprint table — 12 周路线
3. **本文 §〇** — 时间线 + 当前位置

### 2.2 🧠 CTO / PM 视角（1 小时）

按顺序：
1. 上面 3 篇（10 min）
2. **`v1.1-team-brain-design.md`** r2.0 final（25 min · 设计层）
3. **`2026-industry-survey.md`**（10 min · 行业 10 大动态）
4. **`docs/hike.md`**（5 min · 子产品 Hike）
5. **`launch/show-hn-draft.md`** FAQ（10 min · 对外叙事）

**重点关注**：v1.1 r2.0 的 §一（10 设计原则）+ §五（8 周 11 mechanic）+ §七（永不做清单）

### 2.3 ⚒ 开发者（2 小时 · v1.1 W1 上手前）

按顺序：
1. CTO 视角 5 篇（1h）
2. **`v1.1-implementation-spec.md`** 全篇（45 min · 全代码 / edge case / 测试矩阵）
3. **`docs/ARCHITECTURE.md`**（15 min · 技术栈）

**编码必看**：impl spec 的 §一 7 维派生函数 + §五 20 edge case + §六 测试矩阵 + §八 10 不变式

### 2.4 🤝 Contributor（30 分钟）

1. **`README.md`**（5 min）
2. **`CONTRIBUTING.md`** + **`docs/legal/DCO.md`**（10 min · DCO 1.1 签字流程）
3. **`docs/strategy/v1.1-team-brain-design.md`** §七 永不做清单（5 min · 知道不接受啥 PR）
4. **`docs/hike-templates/`** 任一行业 starter（10 min · 学 SKILL.md 写法）

### 2.5 🚀 Launch ops（5-12 D-1 必读）

1. **`launch/show-hn-draft.md`** 全篇（20 min · 含 pre-flight + posting strategy + plan B）
2. **本文 §〇 时间线**（5 min · 5-13 准点动作）
3. **`operations/sandbox-setup.md`**（10 min · HF Space 实操）

### 2.6 ⚖ Legal / 部署方

1. **`docs/legal/`** 4 模板全读（45 min）
2. **`v1.1-team-brain-design.md`** §八 安全/合规 deployment checklist（10 min）
3. **`v1.1-implementation-spec.md`** §八 10 条不变式（10 min）

### 2.7 💼 投资人 / 战略外脑

1. **本文 §〇**（10 sec）
2. **`README.md`** TL;DR（2 min）
3. **`2026-industry-survey.md`** 全篇（15 min · 含 10 大动态 + 6 处 reframe）
4. **`v1.1-team-brain-design.md`** §0 + §10 一句话定位（5 min）

---

## 三 · 版本路线图（12 个月）

| 版本 | 日期 | 主题 | 关键交付 |
|:---:|:---:|:---|:---|
| v0.9.7 | ✅ 已 ship | 一行远程安装 + 极简启动器 | install.sh + ome365 launcher |
| v1.0.0-rc1 | ✅ 5-08 | 24 round 收口 | Hike v0.1 + Apache 2.0 + ome365.id/a2a stub + DAO + Cost Cap stub |
| **v1.0.0** | **5-13 / 5-20** | **极简版 Show HN** | **80 行 README + ASCII demo + HF Space + Anti-Tokenmaxxing 立场** |
| v1.1.0 | **7-14** | **Team Brain** | **Skills + Decisions + Trace + Eval · Cost-per-Outcome · Karpathy /wiki-update** |
| v1.2.0 | 9-01 | 身份可携 + 决策蒸馏 | ome365.id 真签名 + Hike L4 Wiki Maintainer · 4 Skill VC types |
| v1.3.0 | 11-01 | A2A 真联邦 | 两实例互调 + DID verify + audit log · 真 federation registry |
| v2.0.0 | Q4 | 5 行业真 starter + MCP server | 50+ entity per industry · MCP server v1 · OIDC SSO |

---

## 四 · 当前完成度（5-08 实测）

### 4.1 ✅ 已完成（24 round + 计划文档 + Review-Fix r2.1）

```
代码:
  · server.py:           6126 行
  · ome365_id.py:         357 行 PREVIEW (v0.1 mock · _preview=True · v1.2 真签名)
  · ome365_a2a.py:        358 行 PREVIEW (v0.1 mock · _preview=True · v1.3 真联邦)
  · ome365_cost.py:       234 行 PREVIEW (v0.1 mock · _preview=True · v1.1 真拦截)
  · hike_schema.py:       227 行 validator
  · dao/__init__.py:      289 行 (SQLite + PG/Kingbase 适配)
  · skill_lint.py:        ~250 行 (Anthropic SKILL.md spec 静态校验 · 32 tools 兼容)
  · 测试:                161+ passed (含 5 skill lint)

stub 政策（5-08 r2.1 拍板·方案 A 保留 mock 化）：
  · 所有 stub endpoint 返 `_preview: true` + `_real_in_version` + `_real_ship_date`
  · README 加 "Preview features" 段·不藏 stub
  · 1238 行 stub 不浪费·v1.1-v1.3 实施有 contract framework

数据:
  · PII scan:            0 hits / 149 tracked files
  · CHANGELOG:           19-round 完整
  · LICENSE:             Apache 2.0 + NOTICE
  · DCO 1.1:             已配置

行业 starter:
  · manufacturing/healthcare/insurance/retail/law-firm
  · 11 entity files · 全过 hike_schema 验证

文档:
  · v1.1-team-brain-design.md (574 行 r2.0)
  · v1.1-implementation-spec.md (816 行)
  · 2026-industry-survey.md (323 行)
  · MASTER-PLAN.md (本档)
  · 跨档同步: README + show-hn + hike.md
```

### 4.2 ⏳ v1.0 ship 前（5-09 ~ 5-13 · 11h 工时）

| Day | 任务 | 工时 | 责任 |
|:---:|:---|:---:|:---:|
| 5-09 | **stub 政策方案 A**（mock 化保留 · 不藏 · 标 _preview）+ README 加 "Preview features" 段（已落 5-08 r2.1） + README 主体瘦身 60% | 3h | AI |
| 5-10 | 5 行业 starter 合并 vault.example/ 1 文件夹 + doctor 12 → 4 check | 2h | AI |
| 5-11 | show-hn-draft v0.2 重写"folder of markdown files"（保留反 Tokenmaxxing 段）| 2h | AI |
| 5-12 | fresh ubuntu + Mac + WSL 装 install.sh + 60s 启动验证 + 录 gif | 4h | **爸爸 + AI** |
| 5-13 | tag v1.0.0 + push GitHub release + 8am PT Show HN | — | 爸爸 |

### 4.3 🟡 真阻塞（爸爸亲自做）

| # | 任务 | 备注 |
|:---:|:---|:---|
| 1 | 录 demo.gif | OBS / Kap 录屏·30 秒不剪辑 |
| 2 | 录 YouTube 3 min 介绍视频 | 可选·Plan B 跳过 |
| 3 | HF Space push Dockerfile 部署 | 0.5h（Dockerfile 已 ready）|
| 4 | try.omnity.ai DNS CNAME | 控制台 5 min |
| 5 | 三平台 staging 装 | Mac + Ubuntu + WSL VM |
| 6 | KOL outreach 5 邮件 | AI 起草模板·爸爸填地址发 |
| 7 | 国内 14 天首发渠道 | 爸爸定 |
| 8 | CTO 终审 sign-off | 爸爸 |

---

## 五 · 关键决策点 + 里程碑

### 5.1 🔴 5-12 17:00 · Plan B 决策

**触发条件**（任一为真）：
- demo gif/视频/部署 < 3 完成
- 24 轴 PII 任一 FAIL
- install.sh 三平台装不上

**决策**：5-13 推迟到 5-20 与 Mindos 同发

**Owner**: 爸爸

### 5.2 🚀 5-13 11:00 PT (北京 5-14 02:00) · Show HN

**posting account**: 长期 HN 用户 · karma > 100

**前 4 小时必须**：
- 30+ thoughtful 评论回复
- 3 友人 first 15 min upvote
- 监控 Slack/Discord 突发

### 5.3 📅 6-08 · 月度行业调研 SOP 启动

CTO 办公室主动跑 8 条 web search · 更新 `2026-industry-survey.md` · SLA 2h · **必须真搜不靠 LLM 凭空答**。

8 条 query 模板见 industry survey §五。

### 5.4 🏁 7-14 · v1.1.0 ship

12 项质量门必过（v1.1 design §六）：CI green / pytest 220+ / PII 0 hits / 32 工具兼容 / GDPR enforce / EU 拦截 / append-only / snapshot / 文件夹零强制 / 归档 95%/5% / Progressive Discovery 85% 节省 / fresh install 60s。

---

## 六 · 文档维护规约

### 6.1 谁负责什么

| 文档 | Owner | 刷新节奏 |
|:---|:---|:---|
| MASTER-PLAN.md | CTO 办公室 | 每次大 ship 后 |
| v1.1-team-brain-design.md | CTO 办公室 | 实施回顾后 → r2.1 |
| v1.1-implementation-spec.md | 开发 lead | 实施过程发现 edge case 时 |
| 2026-industry-survey.md | CTO 办公室 | 月度（每月 8 号 SLA 2h） |
| ROADMAP_v1.md | CTO 办公室 | 季度刷新 |
| README.md | CTO 办公室 | 大 ship 时 |
| show-hn-draft.md | CTO 办公室 | launch 前 D-2 终稿 |
| dr-runbook.md | 部署方 | 演练后 |
| legal/ 4 模板 | legal 顾问 | 法律变动时 |

### 6.2 修订流程

```
小改        → 直接 commit · message [docs: <doc>] <change>
中等改      → PR · 1 reviewer · CTO 办公室 sign-off
大改 (新章/废章) → r{X+1} 升版 · 修订历史表加一行 · 通知所有 reviewer
```

### 6.3 内部一致性铁律

- 任何"新机制"必须在 design 层 + impl spec 层 + 实施周计划三处都出现
- 命名一旦确定（如 `D2_cost_per_outcome`）·不允许私自改名·要改走 r{X+1}
- 数字（行数 / 测试 / 周数）变化必须同步到 MASTER-PLAN §四

---

## 七 · FAQ（10 问）

**Q1. v1.0 vs v1.1 边界为什么这么严？**
v1.1 用户零迁移 + v1.0 已承诺的不能砍。新功能必须是纯加法·4 文件夹全可选。

**Q2. 为什么 v1.1 不接 LLM 端到端？**
LLM 默认关·见 `LLM_BACKEND=disabled`。v1.1 只做 vault 派生层·不强制用户买 API key。

**Q3. ome365.id / a2a / cost 是 v0.1 stub·什么时候变真？**
- ome365.id 真签名: v1.2 (9-01)
- ome365.a2a 真联邦: v1.3 (11-01)
- ome365.cost 真拦截: v1.1 (跟 LLMBackend 一起)

**Q4. 32 工具 SKILL.md 兼容怎么测？**
CI shell test (`tests/skill_interop_test.sh`) 真在 Claude Code + Codex CLI + Cursor + Gemini CLI 4 host 跑通至少 1 个 SKILL · 失败阻塞合入。

**Q5. 评分能用作 KPI 吗？**
**永不**。GDPR Art. 22 + CEO 边界铁律 + Pinnacle 反 Tokenmaxxing 立场。每次 API 响应必含 `human_review_required: true` + warning。

**Q6. 跨 tenant Decisions 共享怎么办？**
v1.1 不解决·v1.2 a2a 真联邦时落地。privacy=public/pinned 的可跨·internal/sensitive 永不跨。

**Q7. Hike 跟 Letta/Mem0 抢吗？**
不抢。Letta/Mem0 是 memory layer。Hike 是 vault layer + entity graph + decision distillation。**一层之上**。

**Q8. 离职员工评分怎么处理？**
employment_history.to ≠ null 时·窗口自动 clip 到 employed 期间·派生函数处理。

**Q9. 月度行业调研发现新对手怎么办？**
更新 `2026-industry-survey.md`·若是大动态触发 reframe → 升 v1.1-team-brain-design.md r{X+1}。

**Q10. v1.0 launch 翻车怎么办？**
5-12 17:00 plan B 决策点·任一硬阻塞 → 5-13 推迟到 5-20 与 Mindos 同发。**主动延比仓促发翻车强**。

---

## 附录 A · 数字概览

```
代码 (Ome365-git):
  · 总 commits:                81
  · server.py:               6126 lines
  · 测试:                    161 passed
  · 测试目标 v1.1:            220+ (新增 ~109)
  · PII scan:                0 hits / 149 tracked files

文档:
  · 策略层:                 4 篇 / 1713 行（含本档）
  · 路线层:                 2 篇
  · 子产品层:               2 篇
  · 启动层:                 1 篇 / 206 行
  · 运营层:                 2 篇
  · 法律层:                 4 模板
  · 总策略相关:             ~3000 行

行业 starter:
  · 行业:                   5（manufacturing/healthcare/insurance/retail/law-firm）
  · 实体:                   11 文件 · 100% hike_schema 验证

时间:
  · v1.0 ship:              5-13 (Plan B: 5-20)
  · v1.1 实施周:             5-20 ~ 7-14（8 周）
  · v1.1 ship:              7-14
  · v1.2 ship:              9-01
  · v1.3 ship:              11-01
  · v2.0 GA:                Q4

距离:
  · 距 v1.0 launch:         5 天
  · 距 v1.1 ship:           67 天
  · 距 v2.0 GA:             ~210 天
```

## 附录 B · 关键命令速查

```bash
# 起服务
./ome365                                    # 自动启动 cockpit + 浏览器
./ome365 doctor                             # 12 项健康检查
./ome365 init team-brain                    # v1.1 启用 4 文件夹

# v1.1 (规划)
./ome365 decision new "<title>" --owner alice
./ome365 decision close <id> --outcome "..." --value-anchors P,L
./ome365 trace add --actor alice --skill X --tokens 2400/800 --cost 0.012
./ome365 finops --scope cost_per_resolved_decision --since 2026-04-01
./ome365 eval snapshot --period 2026-Q2

# 测试
python3 -m pytest tests/                    # 当前 161 / 目标 v1.1 220+
python3 scripts/scan_pii.py                 # 必须 0 hits
bash tests/skill_interop_test.sh            # v1.1 W1 加 · 32 工具兼容

# Git
git pull --ff-only origin main              # 主仓 fast-forward
cd /Users/wyon/root/code-ai/Ome365-git && git push origin main  # 镜像 push 源
```

## 附录 C · 修订历史

| 版本 | 日期 | 内容 |
|:---:|:---|:---|
| r1.0 | 2026-05-08 | 首版 · 把 13 篇规划文档汇总到一处 · 7 章 + 3 附录 |

---

**版本**：MASTER-PLAN-r1.0 · 2026-05-08
**Owner**：CTO 办公室
**入库路径**：`docs/strategy/MASTER-PLAN.md`
**前置依赖**：本档读完即可串起所有 13 篇规划文档
