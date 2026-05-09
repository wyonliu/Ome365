---
id: 2026-05-09-p1-backup-and-metrics
opened: 2026-05-09T15:00:00Z
closed: 2026-05-09T16:30:00Z
status: closed
owner: alice
participants: [bob]
supersedes: null
superseded_by: null
outcome: "ome365_backup · tar.gz vault snapshot + restore · /metrics Prometheus endpoint with 12 metric families · production-ready operations"
value_anchors:
  - P              # 信任·能拿回数据
  - L              # 触每次部署
  - 维护性
roi_estimated: "团队信任度 · 'data ours' 真兑现 · ops 接入 Grafana 一键"
roi_actual: null
planned_duration_days: 1
elapsed_days: 1
category: ops
hours_saved: 6
---

# Decision: P1 #8 backup/restore + P2 #12 Prometheus metrics

## ① Problem definition (human · alice)

团队 5+ 人部署后 2 个高频问题：
1. "vault 数据怎么备份？怎么还原？"·当前没有 CLI · 用户得自己 tar
2. "怎么接 Grafana 看 metrics？"·没 /metrics endpoint · ops 接不进去

## ② Data needs (AI)

backup CLI:
- `ome365 backup create [--dest /path]` · tar.gz Decisions/ + Trace/ + Skills/ + Knowledge/
- `ome365 backup restore <tarball> [--vault path]` · 安全还原 (备份现有 → restore → verify)
- `ome365 backup list [--dir]` · list 已有 backups (size + date)
- 默认排除 .ome365/notify_webhooks.json (含 secret) · 默认包含 .ome365/eval-config.yml

metrics:
- 12 metric families: decisions_total / closed / open / by_owner_count
  · traces_total / cost_usd_total / value_usd_total / by_actor
  · skills_total / by_author
  · eval_member_calls_total / dashboard_calls_total · last_request_at
- Prometheus text format · GET /metrics

## ③ Models considered (AI)

backup A. tar.gz · stdlib `tarfile` · 0 deps · 简单可靠
metrics A. handwritten Prometheus formatter · 0 deps · 12 metric families

## ④ Options (AI)

A. **stdlib only** ✓ chosen — 0 deps · CI 跑 · 团队自助
B. SDK (prometheus_client) — 多一个 dep · 收益不大
C. JSON `/api/metrics` — 不能直接给 Prom

## ⑤ Decision (human · alice · leader)

A. backup CLI + Prom /metrics · 都用 stdlib · 都 0 deps · 都可在 CI 跑。

## ⑥ Reflection (human · alice + bob · leader)

数据可携带性是 file-first 的核心承诺·必须有真 CLI 兑现。Prom /metrics 是 ops
基础设施·不上 Grafana 等于没 ops 朋友。两个都是"production-ready" 的心理门槛。

## ⑦ Execution log (AI · append-only)

- 2026-05-09T15:00 · `.app/ome365_backup.py` · stdlib tarfile · 3 subcommand
- 2026-05-09T15:30 · `.app/ome365_metrics.py` · Prom text format · 12 family
- 2026-05-09T16:00 · server.py mount /metrics · ome365 launcher add `backup` 子命令
- 2026-05-09T16:30 · 全量 392+ tests · pii 0 · push

## ⑧ Feedback (AI · pending)

(empty)
