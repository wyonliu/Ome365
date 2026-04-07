#!/bin/bash
# Ome365 · Git自动同步脚本
# 用法: ./sync.sh          — 执行一次同步
#       ./sync.sh watch     — 持续监听文件变化自动同步
#       ./sync.sh cron      — 输出crontab配置（每2分钟同步）

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

sync_once() {
  # Pull远程最新
  git pull --rebase --quiet 2>/dev/null

  # 检查是否有变更
  if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git commit -m "sync: $(date '+%m-%d %H:%M') · $(hostname -s)" --quiet
    git push --quiet 2>/dev/null
    echo "$(date '+%H:%M:%S') ✅ 已同步"
  fi
}

case "${1:-}" in
  watch)
    echo "👁 Ome365 实时同步已启动 ($(hostname -s))"
    echo "   监听: $REPO_DIR"
    echo "   Ctrl+C 停止"
    echo ""
    # 先同步一次
    sync_once
    # 使用fswatch监听文件变化（macOS自带）
    if command -v fswatch &>/dev/null; then
      fswatch -o \
        --exclude '\.git' \
        --exclude '\.app/media' \
        --exclude '__pycache__' \
        "$REPO_DIR/Journal" \
        "$REPO_DIR/Notes" \
        "$REPO_DIR/Decisions" \
        "$REPO_DIR/Contacts" \
        "$REPO_DIR/Projects" \
        "$REPO_DIR/000-365-PLAN.md" \
        2>/dev/null | while read _; do
          sleep 2  # 防抖：等文件写完
          sync_once
        done
    else
      echo "⚠ fswatch未安装，回退到轮询模式（每30秒）"
      echo "  安装fswatch: brew install fswatch"
      while true; do
        sleep 30
        sync_once
      done
    fi
    ;;
  cron)
    echo "# 添加到 crontab -e:"
    echo "*/2 * * * * cd $REPO_DIR && git add -A && git commit -m 'sync: \$(date +\\%H:\\%M)' 2>/dev/null; git pull --rebase && git push 2>/dev/null"
    ;;
  *)
    sync_once
    ;;
esac
