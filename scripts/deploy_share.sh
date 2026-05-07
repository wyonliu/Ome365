#!/usr/bin/env bash
# deploy_share.sh — 把分享站推到 ome365.example.com (10.0.0.144)
#
# 前置条件：
#   1. ~/.ssh/config 里有 ome365-share host（ProxyJump + lhadmin）
#   2. 你已经在另一个终端 `ssh ome365-share` 跑了一次（ControlMaster socket 存活）
#   3. /data/ome365-logs/ 在服务器上已创建且 lhadmin 可写
#
# 用法：
#   scripts/deploy_share.sh                 # 全量：代码 + 最小 vault + 配置
#   scripts/deploy_share.sh --code-only     # 只同步代码（改了 share_routes 时）
#   scripts/deploy_share.sh --vault-only    # 只同步最小 vault（注册了新文档时）
#   scripts/deploy_share.sh --dry-run       # rsync -n 预览
#   scripts/deploy_share.sh --bootstrap     # 首次：安装 python venv + 建目录

set -euo pipefail

HOST="ome365-share"
CODE_SRC="$HOME/root/Ome365-git/.app/"
CODE_DST="/data/ome365/.app/"
STATIC_SRC="$HOME/root/Ome365-git/.app/static/"
STATIC_DST="/data/ome365/.app/static/"
REQS_SRC="$HOME/root/Ome365-git/requirements.txt"
VAULT_STAGING="/tmp/ome365-share-staging"
VAULT_DST="/data/ome365-share-vault/"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

say() { printf "\033[36m[deploy]\033[0m %s\n" "$*"; }
warn() { printf "\033[33m[warn]\033[0m %s\n" "$*"; }
die() { printf "\033[31m[fail]\033[0m %s\n" "$*" >&2; exit 1; }

MODE="full"
DRY=""
BOOTSTRAP=0
for arg in "$@"; do
  case "$arg" in
    --code-only) MODE="code" ;;
    --vault-only) MODE="vault" ;;
    --dry-run) DRY="-n" ;;
    --bootstrap) BOOTSTRAP=1 ;;
    -h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "未知参数: $arg" ;;
  esac
done

# ── 0. 检查 ControlMaster socket 存活 ──
if ! ssh -O check "$HOST" 2>/dev/null; then
  warn "ControlMaster socket 不存在"
  echo "  请在另一个终端执行：ssh $HOST"
  echo "  走完 JumpServer SSO，保持那个窗口不要关，再回来重跑本脚本"
  die "no live ssh session"
fi

# ── 1. Bootstrap（首次部署）──
if [[ $BOOTSTRAP == 1 ]]; then
  say "远端 bootstrap：建目录 + python venv + pip install"
  ssh "$HOST" 'bash -se' <<'REMOTE'
set -euo pipefail
sudo mkdir -p /data/ome365 /data/ome365-share-vault /data/ome365-logs
sudo chown -R lhadmin:lhadmin /data/ome365 /data/ome365-share-vault /data/ome365-logs
# python venv
if [[ ! -x /data/ome365/.venv/bin/python3 ]]; then
  python3 -m venv /data/ome365/.venv || {
    echo "[remote] python3-venv 未装，尝试用系统 pip 安装依赖到 --user 目录"
    mkdir -p /data/ome365/.venv/bin
    ln -sf "$(command -v python3)" /data/ome365/.venv/bin/python3
  }
fi
echo "[remote] /data layout:"
ls -ld /data/ome365 /data/ome365-share-vault /data/ome365-logs
REMOTE
fi

# ── 2. Code sync ──
if [[ "$MODE" == "full" || "$MODE" == "code" ]]; then
  say "rsync 代码: $CODE_SRC → $HOST:$CODE_DST"
  ssh "$HOST" "mkdir -p $CODE_DST $(dirname $CODE_DST)"
  rsync -av $DRY --delete \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' \
    --exclude='auth/sessions.db' --exclude='auth/tenants/' \
    --exclude='claude_session.json' --exclude='reminders.json' \
    --exclude='growth.json' --exclude='special_days.json' \
    --exclude='task_repeats.json' --exclude='life_plan_config.json' \
    --exclude='cockpit_config.json' --exclude='tenant_config.json' \
    --exclude='share_registry.json' --exclude='categories.json' \
    --exclude='contact_categories.json' --exclude='settings.json' \
    --exclude='screen-shot-v8-updates.png' \
    "$CODE_SRC" "$HOST:$CODE_DST"

  say "rsync requirements.txt"
  rsync -av $DRY "$REQS_SRC" "$HOST:/data/ome365/requirements.txt"

  say "远端 pip install（增量）"
  ssh "$HOST" 'bash -se' <<'REMOTE'
set -euo pipefail
cd /data/ome365
if [[ -x .venv/bin/pip ]]; then
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements.txt
else
  python3 -m pip install --user --quiet -r requirements.txt
fi
REMOTE
fi

# ── 3. Vault sync（最小集） ──
if [[ "$MODE" == "full" || "$MODE" == "vault" ]]; then
  say "本地构建最小集 vault → $VAULT_STAGING"
  python3 "$REPO_ROOT/scripts/build_share_vault.py" --staging "$VAULT_STAGING"

  say "rsync vault → $HOST:$VAULT_DST"
  ssh "$HOST" "mkdir -p $VAULT_DST"
  rsync -av $DRY --delete "$VAULT_STAGING/" "$HOST:$VAULT_DST"

  say "复制运行时配置到 /data/ome365/.app/（cockpit/tenant/registry）"
  rsync -av $DRY \
    "$VAULT_STAGING/.app/" \
    "$HOST:/data/ome365/.app/"
fi

# ── 4. systemd + nginx 首次安装 ──
if [[ $BOOTSTRAP == 1 ]]; then
  say "上传 systemd unit + nginx conf + logrotate"
  rsync -av $DRY "$REPO_ROOT/infra/ome365-share.service" "$HOST:/tmp/ome365-share.service"
  rsync -av $DRY "$REPO_ROOT/infra/nginx-ome365.conf" "$HOST:/tmp/nginx-ome365.conf"
  rsync -av $DRY "$REPO_ROOT/infra/logrotate-ome365" "$HOST:/tmp/logrotate-ome365"

  ssh "$HOST" 'bash -se' <<'REMOTE'
set -euo pipefail
sudo install -m 644 /tmp/ome365-share.service /etc/systemd/system/ome365-share.service
sudo install -m 644 /tmp/logrotate-ome365 /etc/logrotate.d/ome365
# nginx: 先备份默认站点，再装自定义
if [[ -d /etc/nginx/conf.d ]]; then
  sudo install -m 644 /tmp/nginx-ome365.conf /etc/nginx/conf.d/ome365.conf
elif [[ -d /etc/nginx/sites-available ]]; then
  sudo install -m 644 /tmp/nginx-ome365.conf /etc/nginx/sites-available/ome365
  sudo ln -sf /etc/nginx/sites-available/ome365 /etc/nginx/sites-enabled/ome365
  # 干掉默认站点（如果还挂着）
  sudo rm -f /etc/nginx/sites-enabled/default
fi
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now ome365-share.service
sudo systemctl reload nginx
rm -f /tmp/ome365-share.service /tmp/nginx-ome365.conf /tmp/logrotate-ome365
REMOTE
else
  # 非 bootstrap：只重启服务
  say "重启 ome365-share.service"
  ssh "$HOST" "sudo systemctl restart ome365-share.service && sleep 2 && sudo systemctl status ome365-share.service --no-pager -l | head -20"
fi

# ── 5. 验证 ──
say "远端验证："
ssh "$HOST" 'bash -s' <<'REMOTE'
set +e
echo "--- share_server 端口 ---"
ss -lntp 2>/dev/null | grep ':3651' || netstat -lntp 2>/dev/null | grep ':3651' || echo "3651 未监听"
echo "--- local curl :3651 ---"
curl -sS -o /dev/null -w "HTTP %{http_code} · %{time_total}s\n" http://127.0.0.1:3651/alice
echo "--- registry ---"
cat /data/ome365/.app/share_registry.json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); [print(f"  {u}/{s}") for u,ds in d.items() for s in ds]' 2>/dev/null || echo "(no registry)"
REMOTE

say "本地验证 public URL："
curl -sS -o /dev/null -w "HTTP %{http_code} · %{time_total}s · https://ome365.example.com/alice\n" https://ome365.example.com/alice || warn "外网拉不到（正常：需内网/VPN）"

say "完成"
