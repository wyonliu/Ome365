#!/usr/bin/env bash
# upgrade-share-fix5.sh — 远端 10.1.11.144 上跑，一键升级到 Fix5（访问统计）。
#
# 前提：
#   pwd 就是解压后的 upgrade 目录，里面有：
#     share_routes.py / share_auth.py / backfill_view_audit.py
#   服务已经按 install-remote.sh 装过。
#
# 干的事：
#   1. 备份现有 /data/ome365/.app/{share_routes,share_auth}.py（带时间戳）
#   2. 覆盖成新版本（语法先 py_compile 检查，过不了直接回滚）
#   3. systemctl restart ome365-share
#   4. dry-run backfill（只看数字，不写库）——确认日志行数匹配预期
#   5. 等用户确认 → 实跑 backfill
#   6. curl 本地自检 + 输出远端 info_batch 里 SpatialAI 的访问数

set -euo pipefail

say()  { printf "\033[36m[upgrade]\033[0m %s\n" "$*"; }
warn() { printf "\033[33m[warn]\033[0m %s\n" "$*"; }
die()  { printf "\033[31m[fail]\033[0m %s\n" "$*" >&2; exit 1; }

APP=/data/ome365/.app
LOGDIR=/data/ome365-logs
SERVICE=ome365-share.service

[[ -f share_routes.py && -f share_auth.py && -f backfill_view_audit.py ]] \
  || die "当前目录缺 share_routes.py / share_auth.py / backfill_view_audit.py"

[[ -d "$APP" ]] || die "$APP 不存在 · 该机器没装过 ome365-share？"
[[ -d "$LOGDIR" ]] || warn "$LOGDIR 不存在，无历史日志可回灌（只上线新 view 日志逻辑）"

TS=$(date +%Y%m%d-%H%M%S)

# ── 1. 备份 ──
say "1/6 · 备份现有 .py 到 $APP/.upgrade-backup-$TS/"
sudo mkdir -p "$APP/.upgrade-backup-$TS"
sudo cp -p "$APP/share_routes.py" "$APP/.upgrade-backup-$TS/"
sudo cp -p "$APP/share_auth.py"   "$APP/.upgrade-backup-$TS/"

# ── 2. 写入新版本 ──
say "2/6 · 覆盖新版 share_routes.py / share_auth.py"
sudo cp -p share_routes.py "$APP/share_routes.py"
sudo cp -p share_auth.py   "$APP/share_auth.py"
sudo chown "$(stat -c '%U:%G' "$APP/share_registry.json")" "$APP/share_routes.py" "$APP/share_auth.py" 2>/dev/null || true

# ── 3. 语法检查，失败立即回滚 ──
say "3/6 · py_compile 语法检查"
PY=/data/ome365/.venv/bin/python3
[[ -x "$PY" ]] || PY=$(command -v python3)
if ! sudo "$PY" -m py_compile "$APP/share_routes.py" "$APP/share_auth.py"; then
  warn "语法失败，回滚"
  sudo cp -p "$APP/.upgrade-backup-$TS/share_routes.py" "$APP/share_routes.py"
  sudo cp -p "$APP/.upgrade-backup-$TS/share_auth.py"   "$APP/share_auth.py"
  die "已回滚；请排查新代码再重跑"
fi

# ── 4. 重启服务 ──
say "4/6 · systemctl restart $SERVICE"
sudo systemctl restart "$SERVICE"
sleep 2
sudo systemctl status "$SERVICE" --no-pager -l | head -15

# 健康检查
if ! curl -sS -o /dev/null -w "health %{http_code}\n" http://127.0.0.1:3651/wyon | grep -q "health 2"; then
  curl -sS -o /dev/null -w "health %{http_code}\n" http://127.0.0.1:3651/wyon || true
  warn "服务未正常响应，看 journal"
  sudo journalctl -u "$SERVICE" -n 30 --no-pager
  die "重启后 3651 不通，人工排查"
fi

# ── 5. backfill dry-run ──
say "5/6 · 回灌 nginx 历史访问（先 dry-run）"
LOGS=(
  "$LOGDIR/nginx.access.log"
)
# logrotate 归档也一起扫
for extra in "$LOGDIR"/nginx.access.log.*; do
  [[ -f "$extra" ]] && LOGS+=("$extra")
done

LOG_ARGS=()
for l in "${LOGS[@]}"; do LOG_ARGS+=(--log "$l"); done

DB=$APP/share_auth.db
sudo "$PY" backfill_view_audit.py --db "$DB" "${LOG_ARGS[@]}" --dry-run

echo
read -r -p "上面数字看着 OK 就按 y + enter 实际落库（n 跳过 backfill）: " ans
if [[ "$ans" == "y" || "$ans" == "Y" ]]; then
  say "实跑 backfill（写库）"
  sudo "$PY" backfill_view_audit.py --db "$DB" "${LOG_ARGS[@]}"
else
  warn "跳过 backfill；历史访问不会出现在 chip 里（只有升级后新访问被记）"
fi

# ── 6. 自检 info_batch ──
say "6/6 · 自检：拉 info_batch 看 SpatialAI 的 total_views"
TOKEN=$(sudo cat "$APP/publish_token" 2>/dev/null || echo "")
if [[ -z "$TOKEN" ]]; then
  warn "publish_token 读不到，跳过自检；手动在本地 cockpit 看"
else
  curl -sS -H "X-Publish-Token: $TOKEN" "http://127.0.0.1:3651/api/share/info_batch?user=wyon" \
    | "$PY" -c "
import sys, json
d = json.load(sys.stdin)
items = d.get('items', {})
print()
print('=== 自检结果（关心的是 total_views 非 0 就对了）===')
for slug in sorted(items.keys()):
    info = items[slug]
    tv = info.get('total_views', '<FIELD MISSING>')
    print(f'  {slug:24s}  total_views={tv}  last={info.get(\"last_view\",\"\")[:19]}  uniq_ips={info.get(\"unique_ips\",0)}  protected={info.get(\"protected\")}')
"
fi

echo
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  ✅ Fix5 上线完成                                     ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo
echo "回滚（如有异常）："
echo "  sudo cp $APP/.upgrade-backup-$TS/share_routes.py $APP/share_routes.py"
echo "  sudo cp $APP/.upgrade-backup-$TS/share_auth.py   $APP/share_auth.py"
echo "  sudo systemctl restart $SERVICE"
