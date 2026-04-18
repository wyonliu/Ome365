#!/usr/bin/env bash
# Ome365 · 远程一行安装
#
# 用法：
#   curl -fsSL https://raw.githubusercontent.com/wyonliu/Ome365/main/install.sh | sh
#
# 可选 env：
#   OME365_DIR       安装目录（默认 ~/Ome365）
#   OME365_REPO      Git 仓库（默认 https://github.com/wyonliu/Ome365.git）
#   OME365_BRANCH    分支（默认 main）
#   OME365_NO_START  设为 1 时只克隆不启动（CI / 只装不跑）
#
# 做什么：
#   1. 检查 git / python3
#   2. 克隆或 pull 更新到 $OME365_DIR
#   3. 执行 ./ome365（首跑自动装依赖 + 起服务 + 开浏览器）

set -euo pipefail

DIR="${OME365_DIR:-$HOME/Ome365}"
REPO="${OME365_REPO:-https://github.com/wyonliu/Ome365.git}"
BRANCH="${OME365_BRANCH:-main}"
NO_START="${OME365_NO_START:-0}"

say() { printf "\033[36m[install]\033[0m %s\n" "$*"; }
warn() { printf "\033[33m[warn]\033[0m %s\n" "$*"; }
die() { printf "\033[31m[fail]\033[0m %s\n" "$*" >&2; exit 1; }

# 1. 前置检查
command -v git >/dev/null 2>&1 || die "需要 git（macOS: 'xcode-select --install'；Linux: 'apt install git' / 'dnf install git'）"
command -v python3 >/dev/null 2>&1 || die "需要 Python 3.9+（见 https://www.python.org/downloads/）"
PY_VER=$(python3 -c 'import sys; print("{}.{}".format(*sys.version_info[:2]))')
case "$PY_VER" in
  3.9|3.1[0-9]) ;;
  *) warn "检测到 Python ${PY_VER}；建议 3.9+，低版本可能跑不起来" ;;
esac

# 2. 克隆或更新
if [ -d "$DIR/.git" ]; then
  say "检测到已有仓库：${DIR}，拉取更新"
  git -C "$DIR" fetch --quiet origin "$BRANCH" || warn "fetch 失败，离线继续用本地版本"
  # 只在工作区干净时 fast-forward
  if git -C "$DIR" diff --quiet && git -C "$DIR" diff --cached --quiet; then
    git -C "$DIR" checkout --quiet "$BRANCH" || true
    git -C "$DIR" merge --ff-only --quiet "origin/$BRANCH" 2>/dev/null || warn "无法 ff-only（本地分支领先？），跳过更新"
  else
    warn "$DIR 有未提交改动，跳过 pull（保护你的工作）"
  fi
elif [ -e "$DIR" ]; then
  die "${DIR} 已存在但不是 git 仓库；请挪开或设 OME365_DIR 到别的位置"
else
  say "克隆 ${REPO} → ${DIR}（branch: ${BRANCH}）"
  git clone --quiet --branch "$BRANCH" --depth 1 "$REPO" "$DIR"
fi

# 3. 入口
cd "$DIR"
if [ ! -x ./ome365 ]; then
  chmod +x ./ome365 2>/dev/null || true
fi

if [ "$NO_START" = "1" ]; then
  say "已安装到 $DIR"
  say "启动：cd $DIR && ./ome365"
  exit 0
fi

# 4. 起服务（交给 ome365；它首跑会装依赖、起服务、开浏览器）
say "首跑 ./ome365（会装依赖、起服务、打开浏览器）"
exec ./ome365
