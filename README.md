# Ome365

**365天个人执行面板** — AI原生、Markdown存储、本地优先

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/vue-3.x-green" alt="Vue 3">
  <img src="https://img.shields.io/badge/storage-markdown-orange" alt="Markdown">
  <img src="https://img.shields.io/badge/AI-Claude%20%7C%20GPT%20%7C%20Ollama-purple" alt="AI">
  <img src="https://img.shields.io/badge/license-MIT-brightgreen" alt="MIT">
</p>

---

## 为什么需要 Ome365？

你有365天。一年后的你，和现在有什么不同？

Ome365 帮你把年度目标拆解为可执行的每日行动，用六个维度衡量进度，用AI辅助思考和复盘。

**不是又一个笔记工具。** 是一个执行系统——帮你把「想做」变成「做到」。

## 核心特性

- **365天作战地图** — 年度计划按季度拆解，六维雷达追踪进度
- **今日/本周** — 任务管理，支持重复任务自动生成
- **速记** — 随手记录想法、灵感，支持语音输入和图片
- **决策日志** — 用看板管理重要决策，验证假设
- **关系网络** — 联系人管理 + 可视化关系图 + 保温提醒
- **重要日子** — 生日、纪念日倒计时日历
- **AI助手** — 支持 Claude / GPT / Ollama，内置智能建议
- **Markdown存储** — 所有数据以 `.md` 文件存储，随时迁移
- **暗色主题** — 精心设计的深色界面，长时间使用不伤眼
- **PWA支持** — 可安装到桌面/手机主屏幕

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/wyonliu/Ome365.git
cd Ome365
```

### 2. 初始化数据

```bash
# 用示例数据快速体验
cp -r sample-vault/* .

# 或者从空白开始
mkdir -p Journal/{Daily,Weekly,Monthly,Quarterly} Notes Decisions Contacts/people Projects AI-Logs
```

### 3. 安装依赖 & 启动

```bash
pip install fastapi uvicorn python-multipart

# 启动服务
cd .app && python3 server.py
```

打开浏览器访问 `http://localhost:3650`

### 4. 配置AI（可选）

在「设置」页面选择AI服务商：

| 服务商 | 配置 | 适合场景 |
|--------|------|---------|
| **Anthropic** | API Key | 最佳中文理解 |
| **OpenAI** | API Key + Base URL | 兼容各种代理 |
| **Ollama** | 本地URL + 模型名 | 完全离线/隐私 |

## 目录结构

```
Ome365/
├── .app/                    # 应用代码（不含数据）
│   ├── server.py            # FastAPI 后端
│   └── static/              # 前端 (Vue 3 CDN)
│       ├── index.html
│       ├── app.js
│       └── style.css
├── sample-vault/            # 示例数据（可选复制到根目录）
├── Journal/                 # 日记（Daily/Weekly/Monthly/Quarterly）
├── Notes/                   # 速记
├── Decisions/               # 决策日志
├── Contacts/people/         # 联系人 (.md)
├── 000-365-PLAN.md          # 年度计划（核心文件）
└── 000-DASHBOARD.md         # 仪表盘配置
```

## 数据格式

### 年度计划 (000-365-PLAN.md)

```markdown
## Q1 · 启动期（Week 1-12）
### 职业产出
- [ ] 完成团队1:1摸底
- [x] 输出技术架构全景图

## 里程碑
| 日期 | 事件 |
|------|------|
| 2026-04-08 | 🚀 Day 1 |
```

### 联系人 (Contacts/people/xxx.md)

```markdown
---
name: 张三
company: 示例科技
title: CTO
category: industry
tier: A
met_date: 2026-04-08
last_contact: 2026-04-06
next_followup: 2026-04-20
---
```

### 速记 (Notes/yyyy-mm-dd.md)

```markdown
- 10:30 | 💡 想到一个切入点
- 14:20 | 📌 下周约开会
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python FastAPI |
| 前端 | Vue 3 (CDN, 无构建) |
| 存储 | Markdown 文件 |
| AI | Anthropic SDK / OpenAI API / Ollama |
| 图表 | force-graph (关系网络) |
| 渲染 | marked.js (Markdown) |

## 设计理念

1. **本地优先** — 数据在你的磁盘上，不依赖任何云服务
2. **Markdown原生** — 所有数据都是纯文本，永远可读
3. **零构建** — 前端用 Vue CDN，不需要 npm/webpack
4. **AI可选** — AI是增强，不是依赖。不配置AI也能完整使用
5. **极简依赖** — 后端只需 FastAPI + uvicorn

## 适合谁？

- 程序员 / 技术管理者 — 用代码思维管理人生
- AI从业者 — 内置AI助手，边用边体验
- 善用工具的白领 / 学生 — 比Notion轻，比Todo App强
- 任何想要认真度过未来365天的人

## 路线图

- [ ] 多语言支持 (i18n)
- [ ] 自定义维度配置
- [ ] 数据导入/导出 (Obsidian/Notion)
- [ ] 移动端原生体验优化
- [ ] 插件系统
- [ ] 团队协作模式

## License

MIT

---

> *"你有365天。每一天都是一次选择的机会。"*
