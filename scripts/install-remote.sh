#!/usr/bin/env bash
# install-remote.sh — 在 10.0.0.144 上跑
#
# 前提：此脚本已经随 deploy.tar.gz 解压到当前目录，且 pwd 包含
# code/ vault/ infra/ 三个子目录。
#
# 权限：需要 sudo（建 /data 子目录、装 systemd unit、写 nginx conf）

set -euo pipefail

say() { printf "\033[36m[install]\033[0m %s\n" "$*"; }
warn() { printf "\033[33m[warn]\033[0m %s\n" "$*"; }
die() { printf "\033[31m[fail]\033[0m %s\n" "$*" >&2; exit 1; }

[[ -d code && -d vault && -d infra ]] || die "pwd 缺 code/ vault/ infra/，先 tar xzf ome365-share-deploy.tar.gz"

USER="${SUDO_USER:-$(whoami)}"
[[ "$USER" == "lhadmin" ]] || warn "当前 SUDO_USER=$USER（期望 lhadmin）"

# ── 1. 目录 ──
say "1/7 · 建 /data/ome365/ + /data/ome365-share-vault/ + /data/ome365-logs/"
sudo mkdir -p /data/ome365 /data/ome365-share-vault /data/ome365-logs
sudo chown -R "$USER":"$USER" /data/ome365 /data/ome365-share-vault /data/ome365-logs

# ── 2. 代码 ──
say "2/7 · 铺代码到 /data/ome365/"
# --delete 会扫掉 tarball 没带的文件；publish_token 是运行时生成的、不在 tarball，
# 必须 exclude，否则每次升级都把 token 删掉，下一步判"不存在"就重新生成——
# 结果是每次 install 都换一次 token，脚本表面幂等实际不幂等。
sudo rsync -a --delete --exclude='/.app/publish_token' code/ /data/ome365/
sudo chown -R "$USER":"$USER" /data/ome365

# ── 3. venv + pip ──
say "3/7 · python venv + pip install"
if command -v python3 >/dev/null; then
  PY=$(command -v python3)
else
  die "需要 python3（Python 3.9+）"
fi

if ! $PY -c 'import venv' 2>/dev/null; then
  warn "python3-venv 未装，降级到系统 pip --user"
  if command -v pip3 >/dev/null; then
    pip3 install --user -r /data/ome365/requirements.txt
  else
    die "pip3 也没有，请运维装 python3-pip"
  fi
else
  if [[ ! -x /data/ome365/.venv/bin/python3 ]]; then
    $PY -m venv /data/ome365/.venv
  fi
  /data/ome365/.venv/bin/pip install --quiet --upgrade pip
  /data/ome365/.venv/bin/pip install --quiet -r /data/ome365/requirements.txt
fi

# ── 4. Vault ──
say "4/7 · 铺最小 vault 到 /data/ome365-share-vault/"
sudo rsync -a --delete vault/ /data/ome365-share-vault/
# vault/.app/* 里的 registry/tenant/cockpit 配置也要进 /data/ome365/.app/
sudo cp -f vault/.app/share_registry.json /data/ome365/.app/share_registry.json
sudo cp -f vault/.app/tenant_config.json  /data/ome365/.app/tenant_config.json
[[ -f vault/.app/cockpit_config.json ]] && sudo cp -f vault/.app/cockpit_config.json /data/ome365/.app/cockpit_config.json
sudo chown -R "$USER":"$USER" /data/ome365 /data/ome365-share-vault

# ── 5a. publish_token（HTTPS 推文件通道鉴权）──
say "5/8 · 生成 publish_token"
PUBLISH_TOKEN_FILE=/data/ome365/.app/publish_token
if [[ ! -s "$PUBLISH_TOKEN_FILE" ]]; then
  # 32 bytes → 64 hex chars
  sudo sh -c "head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > $PUBLISH_TOKEN_FILE"
  sudo chown "$USER":"$USER" "$PUBLISH_TOKEN_FILE"
  sudo chmod 600 "$PUBLISH_TOKEN_FILE"
  NEW_TOKEN=1
else
  say "publish_token 已存在，保留"
  NEW_TOKEN=0
fi
TOKEN_VAL=$(sudo cat "$PUBLISH_TOKEN_FILE")

# ── 5b. systemd ──
say "6/8 · systemd unit"
sudo install -m 644 infra/ome365-share.service /etc/systemd/system/ome365-share.service
sudo systemctl daemon-reload
sudo systemctl enable ome365-share.service
sudo systemctl restart ome365-share.service
sleep 2
sudo systemctl status ome365-share.service --no-pager -l | head -15 || true

# ── 6. nginx（装到 144 本地，SSL 由 10.0.0.50 终结）──
say "7/8 · nginx 本地反代 ome365.example.com → 127.0.0.1:3651"
# 共享机安全：只新建 ome365.conf，不碰 skill-hub.conf 等同事文件
if [[ -f /etc/nginx/conf.d/ome365.conf ]]; then
  warn "已存在 /etc/nginx/conf.d/ome365.conf，覆盖为新版（备份到 .bak）"
  sudo cp /etc/nginx/conf.d/ome365.conf /etc/nginx/conf.d/ome365.conf.bak.$(date +%s)
fi
sudo install -m 644 infra/nginx-ome365.conf /etc/nginx/conf.d/ome365.conf

# reload 前先 nginx -t，失败立即回滚（保护同事的 skill-hub.conf 不被 reload 误伤）
if sudo nginx -t 2>&1 | grep -q "successful"; then
  sudo systemctl reload nginx
  say "✅ nginx reload OK · 同事的 skill-hub.conf 未动"
else
  warn "⚠️  nginx -t 失败，回滚 ome365.conf 以免 reload 时破坏同事服务"
  sudo nginx -t || true
  sudo rm -f /etc/nginx/conf.d/ome365.conf
  warn "已回滚；请排查后手动处理。共用机 nginx 保持旧状态未 reload"
fi

# ── 7. logrotate ──
say "8/8 · logrotate"
sudo install -m 644 infra/logrotate-ome365 /etc/logrotate.d/ome365

# ── 验证 ──
echo
echo "=== 自检 ==="
if ss -lntp 2>/dev/null | grep -q ':3651'; then
  echo "✅ 3651 已监听（0.0.0.0）"
else
  warn "3651 未监听，看日志：tail -50 /data/ome365-logs/share.err.log"
fi

curl -sS -o /dev/null -w "✅ 127.0.0.1:3651/alice → %{http_code} (%{time_total}s)\n" \
  http://127.0.0.1:3651/alice || warn "内部 curl 失败"

LAN_IP=$(ip -4 addr show 2>/dev/null | awk '/inet 10\.1\.11\.144/ {print $2}' | cut -d/ -f1)
if [[ -n "$LAN_IP" ]]; then
  curl -sS -o /dev/null -w "✅ ${LAN_IP}:3651/alice → %{http_code} (%{time_total}s, 这个是 10.0.0.50 要打到的目标)\n" \
    "http://${LAN_IP}:3651/alice" || warn "内网 IP 自身 curl 失败（可能防火墙拦了 3651）"
else
  warn "未探测到 10.0.0.144 本机 IP；若防火墙阻 3651 对 10.0.0.50 开放，让 10.0.0.50 无法打到这里"
fi

echo
echo "=== publish_token（只显示一次！立刻复制到本地 tenant_config.json） ==="
if [[ $NEW_TOKEN == 1 ]]; then
  echo
  echo "  新生成 token："
  echo "    $TOKEN_VAL"
  echo
  echo "  本地 Mac 上操作："
  echo "  在 ~/root/Ome365/.app/tenant_config.json 加一段（与 brand/cockpit 同级）："
  echo
  cat <<JSON
  "remote": {
    "base_url": "https://ome365.example.com",
    "token": "$TOKEN_VAL"
  },
JSON
  echo
  echo "  之后本地 cockpit 点「分享」按钮会自动把文档 + 图推到 ome365.example.com。"
else
  echo "  token 已存在（保留不动）。如忘记，服务器上看 $PUBLISH_TOKEN_FILE"
  echo "  如需轮换：sudo rm $PUBLISH_TOKEN_FILE && sudo bash install-remote.sh"
fi

echo
echo "=== 下一步 ==="
echo "  本机 144：uvicorn on 127.0.0.1:3651 + nginx server_name ome365.example.com → 3651 均已装"
echo "  验证链路："
echo "    1) 144 本地：curl -I -H 'Host: ome365.example.com' http://127.0.0.1"
echo "       期望：Server: uvicorn（不是 3952 字节欢迎页）"
echo "    2) Mac 外部：curl -I https://ome365.example.com/alice/demoSlug"
echo "       期望：200 OK"
echo "       若 502 → 10.0.0.50 网关没配 ome365 转发（参考 ai-hub.example.com 同模板加转发）"
