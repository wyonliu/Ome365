#!/usr/bin/env bash
# Ome365 一键安装脚本 · 支持 4 种部署场景
#
#   solo        单人自用（默认；无认证；$OME365_VAULT 本地目录）
#   family      家庭小团队（多用户 + basic/magic_link 认证）
#   demo        公开 demo（basic 密码登录 + sample-vault）
#   enterprise  企业部署（多租户 + SSO/企微 + 外部 session 存储，需手动配置 tenant_config）
#
# 用法：
#   ./setup.sh                    # 交互式向导
#   ./setup.sh --mode solo        # 静默用默认
#   ./setup.sh --mode demo --port 3650 --demo-password mySecret
#   ./setup.sh --non-interactive  # 不问任何问题，全部默认

set -euo pipefail

MODE=""
PORT=3650
VAULT_PATH=""
DEMO_PASSWORD=""
NON_INTERACTIVE=0

while [[ $# -gt 0 ]]; do
  case $1 in
    --mode) MODE="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --vault) VAULT_PATH="$2"; shift 2 ;;
    --demo-password) DEMO_PASSWORD="$2"; shift 2 ;;
    --non-interactive) NON_INTERACTIVE=1; shift ;;
    -h|--help)
      sed -n '/^# Ome365/,/^$/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "未知参数：$1"; exit 1 ;;
  esac
done

say() { printf "\033[36m[setup]\033[0m %s\n" "$*"; }
warn() { printf "\033[33m[warn]\033[0m %s\n" "$*"; }
die() { printf "\033[31m[fail]\033[0m %s\n" "$*"; exit 1; }
ask() {
  local prompt="$1" default="${2:-}" ans
  if [[ $NON_INTERACTIVE == 1 ]]; then
    echo "$default"
    return
  fi
  if [[ -n "$default" ]]; then
    read -rp "$prompt [$default]: " ans
    echo "${ans:-$default}"
  else
    read -rp "$prompt: " ans
    echo "$ans"
  fi
}

echo "╔════════════════════════════════════════════════╗"
echo "║   Ome365 · 一键安装向导                        ║"
echo "╚════════════════════════════════════════════════╝"
echo

# ── 0. 环境检查 ──
command -v python3 >/dev/null || die "需要 Python 3.9+"
PYVER=$(python3 -c 'import sys; print(".".join(map(str,sys.version_info[:2])))')
say "Python: $PYVER"
[[ "$PYVER" < "3.9" ]] && warn "建议 Python 3.9+"

# ── 1. 选场景 ──
if [[ -z "$MODE" ]]; then
  if [[ $NON_INTERACTIVE == 1 ]]; then
    MODE="solo"
  else
    echo "请选择部署场景："
    echo "  1) solo       单人自用（无认证，默认）"
    echo "  2) family     家庭小团队（密码 / 邮件链接登录）"
    echo "  3) demo       公开 demo（单一 demo 账号）"
    echo "  4) enterprise 企业部署（SSO，需手动配置 tenant_config）"
    CHOICE=$(ask "选择 1-4" "1")
    case "$CHOICE" in
      1|solo) MODE="solo" ;;
      2|family) MODE="family" ;;
      3|demo) MODE="demo" ;;
      4|enterprise) MODE="enterprise" ;;
      *) die "无效选择：$CHOICE" ;;
    esac
  fi
fi
say "场景：$MODE"

# ── 2. 安装依赖 ──
if [[ -f requirements.txt ]]; then
  say "安装 Python 依赖..."
  pip3 install -q -r requirements.txt 2>&1 | tail -3 || pip install -q -r requirements.txt 2>&1 | tail -3
else
  pip3 install -q fastapi uvicorn python-multipart pyyaml || pip install -q fastapi uvicorn python-multipart pyyaml
fi

# ── 3. .env ──
if [[ ! -f .env ]] && [[ -f .env.example ]]; then
  cp .env.example .env
  say "已创建 .env"
fi

# ── 4. git hooks（隐私守门员）──
if [[ -d .git ]] && [[ -d .githooks ]]; then
  git config core.hooksPath .githooks
  say "激活 .githooks/pre-commit（隐私守门员）"
fi

# ── 5. share_registry ──
if [[ ! -f .app/share_registry.json ]] && [[ -f .app/share_registry.sample.json ]]; then
  cp .app/share_registry.sample.json .app/share_registry.json
fi

# ── 6. vault 初始化 ──
if [[ -z "$VAULT_PATH" ]]; then
  if [[ "$MODE" == "demo" ]]; then
    VAULT_PATH="$PWD"
  elif [[ $NON_INTERACTIVE == 1 ]]; then
    VAULT_PATH="$PWD"
  else
    VAULT_PATH=$(ask "vault 根目录" "$PWD")
  fi
fi
mkdir -p "$VAULT_PATH"
cd "$VAULT_PATH"
if [[ ! -f "000-365-PLAN.md" ]] && [[ -d "$OLDPWD/sample-vault" ]]; then
  say "复制 sample-vault → $VAULT_PATH"
  cp -r "$OLDPWD/sample-vault/"* . 2>/dev/null || true
fi
mkdir -p Journal/{Daily,Weekly,Monthly,Quarterly} Notes Decisions Contacts/people Projects AI-Logs Templates
cd "$OLDPWD"

# ── 7. tenant_config（按场景生成）──
TC=".app/tenant_config.json"
if [[ ! -f "$TC" ]] || [[ "$MODE" != "solo" ]]; then
  case "$MODE" in
    solo)
      # 单人自用：tenant_config.sample 即可
      say "solo 模式：用 tenant_config.sample.json 兜底"
      ;;

    demo)
      if [[ -z "$DEMO_PASSWORD" ]]; then
        if [[ $NON_INTERACTIVE == 1 ]]; then
          DEMO_PASSWORD="ome365-demo"
        else
          DEMO_PASSWORD=$(ask "demo 密码（用户名 demo）" "ome365-demo")
        fi
      fi
      HASH=$(python3 -c "import sys; sys.path.insert(0,'.app'); from auth.providers.basic_provider import hash_sha256; print(hash_sha256('$DEMO_PASSWORD'))")
      cat > "$TC" <<EOF
{
  "_tenant_id": "default",
  "brand": {"cockpit_title": "Ome365 Demo"},
  "auth": {
    "provider": "basic",
    "protect_api": true,
    "providers": {
      "basic": {
        "users": [
          {"uid": "demo", "display": "Demo", "password_hash": "$HASH", "roles": ["admin"]}
        ]
      }
    }
  }
}
EOF
      say "生成 demo tenant_config（用户名 demo / 密码 ${DEMO_PASSWORD}）"
      ;;

    family)
      USERNAME=$(ask "管理员用户名" "captain")
      PW=$(ask "管理员密码（回车跳过则用 magic link）" "")
      if [[ -n "$PW" ]]; then
        HASH=$(python3 -c "import sys; sys.path.insert(0,'.app'); from auth.providers.basic_provider import hash_sha256; print(hash_sha256('$PW'))")
        cat > "$TC" <<EOF
{
  "_tenant_id": "default",
  "brand": {"cockpit_title": "Ome365 (Family)"},
  "auth": {
    "provider": "basic",
    "protect_api": true,
    "providers": {
      "basic": {
        "users": [
          {"uid": "$USERNAME", "display": "$USERNAME", "password_hash": "$HASH", "roles": ["admin"]}
        ]
      }
    }
  }
}
EOF
        say "生成 family tenant_config（basic 密码登录）"
      else
        EMAIL=$(ask "允许登录的邮箱（逗号分隔）" "")
        SMTP_HOST=$(ask "SMTP host（回车跳过，稍后编辑 $TC）" "")
        cat > "$TC" <<EOF
{
  "_tenant_id": "default",
  "brand": {"cockpit_title": "Ome365 (Family)"},
  "auth": {
    "provider": "magic_link",
    "protect_api": true,
    "providers": {
      "magic_link": {
        "allowlist": [$(echo "$EMAIL" | awk -F',' '{for(i=1;i<=NF;i++){gsub(/^ +| +$/,"",$i);printf (i>1?",":"")"\""$i"\""}}')],
        "smtp": {
          "host": "$SMTP_HOST",
          "port": 587,
          "username": "",
          "password_env": "OME365_SMTP_PASSWORD",
          "from": "Ome365 <noreply@$SMTP_HOST>",
          "starttls": true
        },
        "token_ttl_minutes": 15
      }
    }
  }
}
EOF
        say "生成 family tenant_config（magic_link 登录）"
        warn "记得 export OME365_SMTP_PASSWORD=你的SMTP密码"
      fi
      ;;

    enterprise)
      cat > "$TC" <<'EOF'
{
  "_tenant_id": "default",
  "brand": {"cockpit_title": "Ome365 Enterprise"},
  "auth": {
    "provider": "oidc",
    "protect_api": true,
    "providers": {
      "oidc": {
        "__COMMENT__": "Phase 2c 实现；请参考 docs/deploy/enterprise.md 配置 client_id/secret/issuer",
        "client_id": "",
        "client_secret_env": "OME365_OIDC_SECRET",
        "issuer": "https://sso.your-company.example.com",
        "redirect_uri": "https://ome.your-company.example.com/auth/oidc/callback"
      },
      "wecom": {
        "__COMMENT__": "或用企微扫码",
        "corp_id": "",
        "agent_id": "",
        "secret_env": "OME365_WECOM_SECRET"
      }
    }
  }
}
EOF
      say "生成 enterprise tenant_config 模板；需手动填 SSO 凭据"
      warn "SSO provider (oidc/wecom) 尚在 Phase 2c 实现中；先用 basic 测试可登录后再切"
      ;;
  esac
fi

# ── 8. 自检 ──
say "自检..."
PY_CHECK=$(cd .app && OME365_COMPAT_LEGACY=1 python3 -c "
import sys; sys.path.insert(0,'.')
import json
from ctx import healthcheck
print(json.dumps(healthcheck(), ensure_ascii=False))
" 2>&1 || true)
echo "  ctx healthcheck: $PY_CHECK"

# ── 9. 启动提示 ──
echo
echo "╔════════════════════════════════════════════════╗"
echo "║   ✅ 安装完成                                  ║"
echo "╚════════════════════════════════════════════════╝"
echo
echo "启动方式："
echo "  cd .app && OME365_PORT=$PORT python3 server.py"
echo
echo "浏览器访问："
echo "  http://localhost:$PORT"
if [[ "$MODE" == "demo" ]]; then
  echo
  echo "demo 登录：用户名 demo / 密码 $DEMO_PASSWORD"
elif [[ "$MODE" == "family" ]]; then
  echo
  echo "登录页：http://localhost:$PORT/auth/login"
fi
echo
