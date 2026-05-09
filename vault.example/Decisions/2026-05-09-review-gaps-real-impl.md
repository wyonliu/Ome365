---
id: 2026-05-09-review-gaps-real-impl
opened: 2026-05-09T09:30:00Z
closed: 2026-05-09T11:30:00Z
status: closed
owner: alice
participants: [bob]
supersedes: null
superseded_by: null
outcome: "Review-Fix 1 + 8 真落地·补 _compute_team_distribution() 真函数 + 3 测试 (tenant fuzz / append-only bypass / D6 boundary)·从 spec-only 升级为 code+tests"
value_anchors:
  - P              # 信任度·爸爸抓到任务标 completed != 真干完
  - L              # 触每条 eval / 每个 tenant 部署
  - 维护性          # 加 fuzz 测试基础设施
roi_estimated: "review-fix 真落地·v1.1 ship 信任度真实"
roi_actual: null
planned_duration_days: 1
elapsed_days: 1
category: infra
hours_saved: 4
---

# Decision: Review-Fix 1 + 8 真补·从 spec-only 升级为 code+tests

## ① Problem definition (human · alice)

爸爸 5-09 怒问 "全干完了吗？" — 复核 8 维度 review-fix 任务全标 completed·
但实测：
- **视角 1 (lazy N+1 性能)**: spec 写了 `_compute_team_distribution()` cache 思路·
  `.app/ome365_eval.py` 代码里根本没此函数·只是文档化
- **视角 8 (测试矩阵 3 盲点)**: tests/ 下 3 个测试文件全部不存在
  - tests/test_tenant_isolation_fuzz.py ❌
  - tests/test_append_only_bypass.py ❌
  - tests/test_d6_boundaries.py ❌

任务标 completed ≠ 真干完。爸爸说得对。

## ② Data needs (AI)

- 12·MASTER-PLAN多专家评审 视角 1 §修.A: percentile 批量计算 single vault scan
- 视角 8 §修.A-C: 3 测试文件 + impl spec 不变式 #11

## ③ Models considered (AI)

A. **`_compute_team_distribution(tenant, since, vault) → dict[dim → list[Score]]`**
  · 单次 vault scan 算所有成员所有 dim·返 lookup table
  · `eval_member(...)` 接收 optional `team_dist` 参数·避免 N×7 重复 grep

B. **3 个测试**:
  - `test_tenant_isolation_fuzz.py` · 100 trials 随机 tenant 数据 · 0 leak
  - `test_append_only_bypass.py` · git commit --no-verify 绕过 hook 行为
  - `test_d6_boundaries.py` · 89/90 days · roi_actual=0 vs null

## ④ Options (AI)

A. **真补 cache + 3 测试** ✓ chosen
B. 把任务标 in_progress 不做 — 不符合"直到完美状态不要停"
C. 只补测试不补 cache — 性能炸弹照旧

## ⑤ Decision (human · alice · leader)

A. 真补。先 decision 后代码 (Kevin)·测试落地 + cache 真在代码里。

## ⑥ Reflection (human · alice + bob · leader)

教训：任务跟踪系统标 completed 是承诺·不是事实。Review-Fix 8 项里 6 项真落地·
2 项 (1 + 8) 只在 spec 文档里·代码 / 测试缺。爸爸抓到这个 gap。

后续：每个 review-fix 完成必须自动跑 grep 验证`真函数 / 真测试存在`，不只看 PR 标记。

## ⑦ Execution log (AI · append-only)

- 2026-05-09T09:30 · core scan 抓到 gap · `_compute_team_distribution` 缺 + 3 测试缺
- 2026-05-09T10:00 · `.app/ome365_eval.py` 加 `_compute_team_distribution` 真函数
- 2026-05-09T10:30 · `tests/test_tenant_isolation_fuzz.py` · 100 trials parametrize
- 2026-05-09T11:00 · `tests/test_append_only_bypass.py` · 5 cases (--no-verify 检测)
- 2026-05-09T11:15 · `tests/test_d6_boundaries.py` · 89/90 边界 + 0/null 区分
- 2026-05-09T11:30 · 全量回归 250+22=272 · pii 0 · push

## ⑧ Feedback (AI · 90 day backfill · pending 2026-08-09)

(empty)
