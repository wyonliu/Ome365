#!/usr/bin/env python3
"""
backfill_view_audit.py — 从 nginx access log 回灌历史 view 访问记录到 share_auth.db。

背景
    2026-04-23 之前，未加密分享文档的 GET /api/doc/{user}/{slug} 不写 audit 表。
    Fix5 上线后新访问开始记日志，但历史访问全在 nginx 日志里丢了——
    需要把 nginx access log 里的 /api/doc/* 200 条目回灌成 event='view' 的 audit 行。

使用
    # 远端 10.1.11.144：
    sudo -u lhadmin python3 /data/ome365/scripts/backfill_view_audit.py \
        --db /data/ome365/.app/share_auth.db \
        --log /data/ome365-logs/nginx.access.log \
        --log /data/ome365-logs/nginx.access.log.1 \
        --dry-run

    # 看完 dry-run 数字 OK 再实跑：去掉 --dry-run

    # 也支持 .gz（读 logrotate 归档）：
    python3 backfill_view_audit.py --db ... --log-glob '/data/ome365-logs/nginx.access.log*'

幂等
    按 (user, slug, event='view', ts, ip) 去重；重复跑不会重复插。
    （tail 写 sid=NULL + UA 加前缀 "[nginx-backfill] "，方便事后追溯与区分在线 view。）
"""
import argparse
import gzip
import re
import sqlite3
import sys
from datetime import datetime, timezone
from glob import glob
from pathlib import Path
from typing import List

# nginx combined 默认格式：
#   $remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent
#   "$http_referer" "$http_user_agent"
# time_local 例："23/Apr/2026:10:15:30 +0800"
# 注意：client_real_ip 要从 X-Forwarded-For 解，但 nginx access.log 默认只写 $remote_addr
# （在本站是 10.1.0.50 上游网关 IP）——这是 **nginx 的限制**，无法回溯真实客户 IP。
# 对 total_views 和 last_ts 没影响；unique_ips 会大幅偏低（几乎都是网关 IP），
# 这是可接受的 trade-off，真实 IP 从 Fix5 起上线才精确。

LINE_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ '
    r'\[(?P<ts>[^\]]+)\] '
    r'"(?P<method>[A-Z]+) (?P<path>[^ ]+) HTTP/[0-9.]+" '
    r'(?P<status>\d+) \S+ '
    r'"[^"]*" "(?P<ua>[^"]*)"'
)

DOC_PATH_RE = re.compile(r"^/api/doc/(?P<user>[A-Za-z0-9_-]+)/(?P<slug>[A-Za-z0-9][A-Za-z0-9_-]{0,63})(?:\?|$)")

UA_PREFIX = "[nginx-backfill] "


def parse_ts(s: str) -> str:
    """
    '23/Apr/2026:10:15:30 +0800'  →  '2026-04-23T02:15:30Z' (UTC ISO-8601)
    """
    dt = datetime.strptime(s, "%d/%b/%Y:%H:%M:%S %z")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iter_lines(log_paths):
    for p in log_paths:
        path = Path(p)
        if not path.exists():
            print(f"  [skip] {p} · 文件不存在", file=sys.stderr)
            continue
        opener = gzip.open if path.suffix == ".gz" else open
        try:
            with opener(path, "rt", encoding="utf-8", errors="replace") as f:
                for line in f:
                    yield p, line.rstrip("\n")
        except Exception as e:
            print(f"  [fail] {p}: {e}", file=sys.stderr)


def backfill(db_path: str, log_paths: List[str], dry_run: bool = True) -> dict:
    db = Path(db_path)
    if not db.exists():
        raise SystemExit(f"db 不存在：{db}")

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    stats = {
        "log_lines": 0,
        "doc_hits": 0,
        "inserted": 0,
        "skipped_dup": 0,
        "skipped_nonok": 0,
        "by_slug": {},
    }

    for src, line in iter_lines(log_paths):
        stats["log_lines"] += 1
        m = LINE_RE.match(line)
        if not m:
            continue
        if m.group("method") != "GET":
            continue
        if m.group("status") != "200":
            stats["skipped_nonok"] += 1
            continue
        pm = DOC_PATH_RE.match(m.group("path"))
        if not pm:
            continue
        stats["doc_hits"] += 1
        user = pm.group("user")
        slug = pm.group("slug")
        ip = m.group("ip")
        ua = UA_PREFIX + m.group("ua")
        ts = parse_ts(m.group("ts"))

        dup = cur.execute(
            "SELECT 1 FROM audit WHERE user=? AND slug=? AND event='view' AND ts=? AND ip=? LIMIT 1",
            (user, slug, ts, ip),
        ).fetchone()
        if dup:
            stats["skipped_dup"] += 1
            continue

        if not dry_run:
            cur.execute(
                "INSERT INTO audit(ts,user,slug,event,sid,ip,ua) VALUES(?,?,?,?,NULL,?,?)",
                (ts, user, slug, "view", ip, ua),
            )
        stats["inserted"] += 1
        key = f"{user}/{slug}"
        stats["by_slug"][key] = stats["by_slug"].get(key, 0) + 1

    if not dry_run:
        conn.commit()
    conn.close()
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="share_auth.db 绝对路径")
    ap.add_argument("--log", action="append", default=[], help="nginx access log 路径，可多次")
    ap.add_argument("--log-glob", default=None, help="glob 模式匹配多个日志（含 .gz）")
    ap.add_argument("--dry-run", action="store_true", help="只统计不写库")
    args = ap.parse_args()

    logs = list(args.log)
    if args.log_glob:
        logs.extend(sorted(glob(args.log_glob)))
    if not logs:
        ap.error("至少给一个 --log 或 --log-glob")

    print(f"db      : {args.db}")
    print(f"logs    : {len(logs)} 个 → {', '.join(logs)}")
    print(f"dry-run : {args.dry_run}")
    print()

    st = backfill(args.db, logs, dry_run=args.dry_run)

    print()
    print("=== 结果 ===")
    print(f"  总行数         : {st['log_lines']}")
    print(f"  /api/doc 命中  : {st['doc_hits']}")
    print(f"  非 200 跳过    : {st['skipped_nonok']}")
    print(f"  重复跳过       : {st['skipped_dup']}")
    print(f"  {'[dry] 拟插入' if args.dry_run else '已插入    '} : {st['inserted']}")
    if st["by_slug"]:
        print("  分 slug :")
        for k, v in sorted(st["by_slug"].items(), key=lambda x: -x[1]):
            print(f"    {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
