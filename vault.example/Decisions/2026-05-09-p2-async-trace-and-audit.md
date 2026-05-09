---
id: 2026-05-09-p2-async-trace-and-audit
opened: 2026-05-09T16:30:00Z
closed: 2026-05-09T18:00:00Z
status: closed
owner: alice
participants: [bob]
supersedes: null
superseded_by: null
outcome: "ome365_trace.log_async() · queue + thread worker · 100ms 写盘 → 1ms enqueue · ome365_audit.log() · who-did-what append-only · 12 操作类型"
value_anchors:
  - P              # 生产可用
  - L              # 触每个 trace + 每个 mutation
  - 维护性
roi_estimated: "trace 不阻塞 server · audit log 满足 SOC2 + ISO27001 数据访问追溯"
roi_actual: null
planned_duration_days: 1
elapsed_days: 1
category: infra
hours_saved: 6
---

# Decision: P2 #11 async trace + P2 #13 audit log

## ① Problem definition (human · alice)

P2 生产部署最后两块：
1. **trace 同步写**·high QPS 时 disk fsync 阻塞 FastAPI worker (100ms+ 一次)
2. **没 audit log**·SOC2 / ISO27001 / GDPR Art. 30 都要求"who-did-what 不可篡改"

## ② Data needs (AI)

async trace:
- queue.Queue + 单 daemon thread 写盘
- 调用方调 log_async() 立返 (1ms enqueue)
- shutdown 时 flush queue (atexit)

audit log:
- vault/Audit/<date>.jsonl · append-only (mode "a")
- schema: ts / actor / action / target_type / target_id / details
- 12 actions: decision.create/close · skill.create/update · trace.log ·
  wiki.update · backup.create/restore · eval.member · share.create/revoke ·
  archive.run

## ③ Models considered (AI)

A. **stdlib queue.Queue + thread worker** ✓ chosen — 0 deps · trivially testable
B. asyncio queue — 限制只在 async ctx 用
C. multiprocessing — overkill

## ④ Options (AI)

A. trace.log_async() 异步入队 · log() 保持同步 (已有 caller 不改)
   audit.log() 同步追加 (无并发瓶颈 · audit 频率远低于 trace)

## ⑤ Decision (human · alice · leader)

A. async trace 加 log_async + thread worker · audit 加 log + grep helper.

Rationale: trace QPS 高·要异步；audit 频率低·同步够。两个都 stdlib · 0 deps。

## ⑥ Reflection (human · alice + bob · leader)

queue.Queue + daemon thread 是 Python "boring async" 范式 · 25 年了仍然能打。
audit log 是 file-first 的合规承诺·同 trace.jsonl 一样 grep-friendly。

## ⑦ Execution log (AI · append-only)

- 2026-05-09T16:30 · ome365_trace.log_async() + _worker_thread + atexit
- 2026-05-09T17:00 · ome365_audit.py · log + grep_recent + cli_main
- 2026-05-09T17:30 · 集成: decisions / wiki / backup 调 audit.log
- 2026-05-09T18:00 · 全量 408+ tests · pii 0 · push

## ⑧ Feedback (AI · pending)

(empty)
