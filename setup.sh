#!/bin/bash
# Ome365 快速安装脚本

echo "🚀 Ome365 — 365天个人执行面板"
echo "================================"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 需要 Python 3.9+，请先安装"
    exit 1
fi

echo "✅ Python: $(python3 --version)"

# Install deps
echo "📦 安装依赖..."
pip install fastapi uvicorn python-multipart 2>/dev/null || pip3 install fastapi uvicorn python-multipart

# Init vault if empty
if [ ! -f "000-365-PLAN.md" ]; then
    echo "📂 初始化示例数据..."
    cp -r sample-vault/* .
    echo "✅ 已复制示例数据到根目录"
else
    echo "📂 检测到已有数据，跳过初始化"
fi

# Create empty dirs if missing
mkdir -p Journal/{Daily,Weekly,Monthly,Quarterly} Notes Decisions Contacts/people Projects AI-Logs Templates

echo ""
echo "✅ 安装完成！启动方式："
echo "   cd .app && python3 server.py"
echo ""
echo "然后打开 http://localhost:3650"
echo ""
echo "💡 提示：在「设置」页面配置AI助手（支持Claude/GPT/Ollama）"
