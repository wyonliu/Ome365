---
id: 2026-05-09-p0-5-notification-webhooks
opened: 2026-05-09T13:30:00Z
closed: 2026-05-09T15:00:00Z
status: closed
owner: alice
participants: [bob]
supersedes: null
superseded_by: null
outcome: "ome365_notify · Slack/飞书/Teams generic webhook · 3 events (decision.closed / wiki.updated / budget.warn) · stdlib only · gitignored config"
value_anchors:
  - P              # 团队协作 · 通知是基础
  - L              # 触每个 close/update/budget 事件
  - 维护性
roi_estimated: "团队 5+ 人协作可见性 · 决策关闭立刻同步"
roi_actual: null
planned_duration_days: 1
elapsed_days: 1
category: infra
hours_saved: 4
---

# Decision: P0 #5 webhook notifications · 3 events · 3 platforms

## ① Problem definition (human · alice)

团队 > 5 人时每天会有多个 decisions 关闭 / wiki 更新 / cost 接近 budget·
当前全部静默。Slack/飞书/Teams 是事实标准·没有它就靠人手动 ping。

## ② Data needs (AI)

3 平台 webhook payload 格式都是 application/json POST · 字段差异：
- Slack: `{text, blocks: []}`
- Lark/飞书: `{msg_type: "text"|"interactive", content: {...}}`
- Teams: `{text}` 或 Adaptive Card

3 关键事件：
- `decision.closed` (W2 close_decision 收尾时)
- `wiki.updated` (W6 wiki_update 写后)
- `budget.warn` (任意 trace cost 累积超 budget · v1.1.x 加)

## ③ Models considered (AI)

A. **Generic webhook + per-platform formatter** ✓ chosen — stdlib `urllib.request`
B. SDK per platform (slack-sdk + lark-oapi + msgraph) — over-deps
C. Email instead — too slow

## ④ Options (AI)

A. ome365_notify.py · format-fn-per-platform · POST 一行
B. 引 3 SDK · 多 deps · CI 慢
C. 跳过 · 团队靠 git push notification — 不够实时

## ⑤ Decision (human · alice · leader)

A. 单文件 ome365_notify.py · 3 formatter (slack/lark/teams + generic) · stdlib only ·
   notify_webhooks.json gitignored 配置 (env override)。
   
   集成点:
   - ome365_decisions.close_decision() 收尾 hook
   - ome365_wiki.update() 收尾 hook
   - ome365_archive.cli_main() rollup 后 hook (可选)

## ⑥ Reflection (human · alice + bob · leader)

webhook 是团队协作的最低门槛。SDK 重·webhook 轻。formatter 把同一事件适配
3 平台·调用方不感知。配置走 gitignored notify_webhooks.json + env var 双备份。

## ⑦ Execution log (AI · append-only)

- 2026-05-09T13:30 · `.app/ome365_notify.py` · 200 行 stdlib
- 2026-05-09T14:00 · 3 集成点 (decisions/wiki/archive)
- 2026-05-09T14:30 · `tests/test_ome365_notify.py` · 12 tests · mock httpd
- 2026-05-09T15:00 · 全量 376/376 · pii 0 · push

## ⑧ Feedback (AI · pending)

(empty)
