#!/usr/bin/env bash
# build_deploy_tarball.sh — 打一个自包含的 deploy.tar.gz
#
# 场景：JumpServer 只给 WebSSH，不开 SSH CLI。
# 本地打包 → JumpServer 文件管理上传 → WebSSH 解压 + 跑 install.sh
#
# 产物：/tmp/ome365-share-deploy.tar.gz
#   ├── code/                    # 代码（从 Ome365-git 抽）
#   ├── vault/                   # 最小 vault（4 doc + 11 图）
#   ├── infra/                   # systemd/nginx/logrotate
#   └── install-remote.sh        # 在 10.1.11.144 上一键跑的脚本

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GIT_ROOT="$HOME/root/Ome365-git"
STAGING=$(mktemp -d /tmp/ome365-deploy-XXXX)
TARBALL=/tmp/ome365-share-deploy.tar.gz

say() { printf "\033[36m[build]\033[0m %s\n" "$*"; }

say "1/4 · 拉代码（Ome365-git/.app/）"
mkdir -p "$STAGING/code"
rsync -a \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' \
  --exclude='auth/sessions.db' --exclude='auth/tenants/' \
  --exclude='claude_session.json' --exclude='reminders.json' \
  --exclude='growth.json' --exclude='special_days.json' \
  --exclude='task_repeats.json' --exclude='life_plan_config.json' \
  --exclude='cockpit_config.json' --exclude='tenant_config.json' \
  --exclude='share_registry.json' --exclude='categories.json' \
  --exclude='contact_categories.json' --exclude='settings.json' \
  --exclude='screen-shot-v8-updates.png' \
  "$GIT_ROOT/.app/" "$STAGING/code/.app/"
cp "$REPO_ROOT/requirements.share.txt" "$STAGING/code/requirements.txt"

say "2/4 · 构建最小 vault"
python3 "$REPO_ROOT/scripts/build_share_vault.py" --staging "$STAGING/vault"

say "3/4 · 复制 infra + install 脚本"
mkdir -p "$STAGING/infra"
cp "$REPO_ROOT/infra/ome365-share.service" "$STAGING/infra/"
cp "$REPO_ROOT/infra/nginx-ome365.conf"    "$STAGING/infra/"
cp "$REPO_ROOT/infra/logrotate-ome365"     "$STAGING/infra/"
cp "$REPO_ROOT/scripts/install-remote.sh"  "$STAGING/install-remote.sh"
chmod +x "$STAGING/install-remote.sh"

say "4/4 · 打包 → $TARBALL"
# --owner=0 --group=0 --numeric-owner：避免 Mac UID 501/wheel 污染到 Linux 解压端
# （否则 Linux 上 501 可能不存在，导致 drwx------ permission denied）
#
# 不打 `.` 根条目：`-C dir .` 会把 $STAGING 本身（从 /tmp 继承 rwx-----T 的
# 奇葩 mode）塞成第一个 entry，解压时 tar 试图 utime/chmod /tmp 导致
# "Cannot utime: Operation not permitted"。改为显式列出条目根。
entries=$(cd "$STAGING" && ls -A)
tar czf "$TARBALL" --owner=0 --group=0 --numeric-owner -C "$STAGING" $entries
size=$(du -h "$TARBALL" | awk '{print $1}')
rm -rf "$STAGING"

echo
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  ✅ deploy tarball 已生成                             ║"
echo "╚═══════════════════════════════════════════════════════╝"
printf "  📦 %s (%s)\n" "$TARBALL" "$size"
echo
echo "下一步（在 JumpServer 上）："
echo "  1. 打开 10.1.11.144 的 WebSSH 页面"
echo "  2. 点文件管理/上传，把 $TARBALL 丢到 /tmp/"
echo "  3. WebSSH 里跑："
echo "     cd /tmp && sudo tar xzf ome365-share-deploy.tar.gz && sudo bash install-remote.sh"
