---
id: 2026-05-09-p0-1-demo-seed-shock
opened: 2026-05-09T11:30:00Z
closed: 2026-05-09T13:00:00Z
status: closed
owner: alice
participants: [bob]
supersedes: null
superseded_by: null
outcome: "vault.example 升级为 12 真行业 decisions + 30 traces + 5 distilled patterns · 团队装上 3 分钟看到震撼 demo · 不再是 alice/bob hello-world"
value_anchors:
  - P              # 团队第一印象决定能否留住
  - L              # /v1_1.html 4 卡片全数据
  - 维护性          # vault.example 体积小幅上升
roi_estimated: "团队装上 3 min 内看到丰富 demo · 不流失"
roi_actual: null
planned_duration_days: 1
elapsed_days: 1
category: ux
hours_saved: 4
---

# Decision: P0 #1 demo seed 震撼级·12 行业 decisions + 30 traces

## ① Problem definition (human · alice)

爸爸怒问 "震撼级好用 + 团队能用了吗？" — 当前 vault.example：
- 6 个 decision (5 个是 W1-W7 自我引用·1 个 W1 sample)
- 6 trace lines (2026-05-08 一天)
- 4 SKILL.md
- 0 distilled patterns

团队装完 → /v1_1.html → 看到 alice/bob 两个名字 + 6 行 → "哦这是 demo"。
没有"哇真好用"瞬间·**留不住人**。

## ② Data needs (AI)

12 个真行业 decisions 涵盖 5 个真团队场景：
- Eng (3): 选 LLM backend / 数据库 PG vs SQLite / CI 路线图
- PM (3): 定义 v1.1 scope / 客户访谈优先级 / 砍 feature
- Sales (2): 客户分级 ABC / 流失客户挽回流程
- Ops (2): 部署 stack 选型 / on-call 排班轮换
- Mixed (2): 跨 BU 协作 / 团队季度复盘

30 traces 体现真实使用：5 actor (alice/bob/carol/dan/erin) × 多技能调用 ×
3 个月时间线 (2026-03 ~ 05) · 含 cost_usd + output_value_usd 让 D2 不为 0

5 distilled patterns: 蒸馏 Decisions 后 Knowledge/L2-distilled 的真内容 ·
让 wiki query 出真东西

## ③ Models considered (AI)

A. **真行业场景 12 decisions** ✓ chosen — 团队代入感
B. 随机生成 100 假 decisions — 数量大但读起来空洞
C. 只加 1-2 个 — 量不够·D 维度仍 insufficient_sample

## ④ Options (AI)

A 落地：每个 decision 真 8 步（不只是 frontmatter） · 让 reader 看了就理解格式

## ⑤ Decision (human · alice · leader)

A. 12 真行业 decisions + 30 trace × 3 月 + 5 patterns。每个 decision 至少
2-3 段真分析（不是占位符）·让团队看了想"我也能这么写"。

## ⑥ Reflection (human · alice + bob · leader)

Demo 数据是产品的第一印象。alice/bob hello-world 不是 demo·是 placeholder。
真行业场景 + 真团队 + 真时间线 = 团队 3 分钟内代入 → "我们也想这么用"。

## ⑦ Execution log (AI · append-only)

- 2026-05-09T11:30 · 12 decisions ·分 5 类·每个真 8 步内容
- 2026-05-09T12:00 · 30 trace 跨 5 actor × 3 个月·真 cost/value
- 2026-05-09T12:30 · ome365 wiki update → 5 distilled patterns
- 2026-05-09T13:00 · /v1_1.html 真数据·sample_min=5 全部 D 维度有真分

## ⑧ Feedback (AI · pending)

(empty)
