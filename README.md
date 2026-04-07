# Ome365

**365天个人执行面板** — AI原生、Markdown存储、本地优先

<p align="center">
  <img src="https://img.shields.io/badge/version-v0.1-blue" alt="v0.1">
  <img src="https://img.shields.io/badge/python-3.9+-blue" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/vue-3.x-green" alt="Vue 3">
  <img src="https://img.shields.io/badge/storage-markdown-orange" alt="Markdown">
  <img src="https://img.shields.io/badge/AI-DeepSeek%20%7C%20OpenRouter%20%7C%20Ollama-purple" alt="AI">
  <img src="https://img.shields.io/badge/license-MIT-brightgreen" alt="MIT">
</p>

---

## 为什么需要 Ome365？

你有365天。一年后的你，和现在有什么不同？

Ome365 帮你把年度目标拆解为可执行的每日行动，用六个维度衡量进度，用AI辅助思考和复盘。

**不是又一个笔记工具。** 是一个执行系统——帮你把「想做」变成「做到」。

## 核心特性

- **365天作战地图** — 年度计划按季度拆解，里程碑时间轴实时倒计时
- **今日/本周** — 任务管理，支持重复任务自动生成
- **速记** — 随手记录想法、灵感，支持语音转文字（本地Whisper）和图片
- **决策日志** — 用看板管理重要决策，验证假设
- **关系网络** — 联系人管理 + 力导向关系图 + 保温提醒
- **重要日子** — 生日、纪念日日历，支持年/月重复
- **AI助手** — 支持 DeepSeek / OpenRouter / OpenAI / Ollama，内置智能建议
- **代理开关** — 右上角一键切换网络代理，解决国内API访问问题
- **Markdown存储** — 所有数据以 `.md` 文件存储，随时可读可迁移
- **暗色主题** — Linear/Raycast 风格深色界面，毛玻璃质感
- **PWA支持** — 可安装到桌面/手机主屏幕
- **Docker部署** — 一行命令启动，数据卷挂载

## 快速开始

### 方式一：本地运行

```bash
git clone https://github.com/wyonliu/Ome365.git
cd Ome365

# 用示例数据快速体验
cp -r sample-vault/* .

# 安装依赖 & 启动
pip install fastapi uvicorn python-multipart
cd .app && python3 server.py
```

打开浏览器访问 `http://localhost:3650`

### 方式二：Docker

```bash
git clone https://github.com/wyonliu/Ome365.git
cd Ome365
docker compose up -d
```

数据持久化在 `./data/` 目录，容器删了数据还在。

### 配置AI（可选）

在「设置」页面选择AI模式：

| 模式 | 服务商 | 说明 |
|------|--------|------|
| **API** | DeepSeek / OpenRouter / OpenAI / Anthropic | 填 Base URL + Key + 模型名，preset 一键填充 |
| **Ollama** | 本地模型 | 完全离线，需先安装 [Ollama](https://ollama.ai) |

> 国内用户推荐 DeepSeek（直连无需代理）或 OpenRouter + `deepseek/deepseek-chat`

## 目录结构

```
Ome365/
├── .app/                    # 应用代码
│   ├── server.py            # FastAPI 后端
│   └── static/              # 前端 (Vue 3 CDN, 零构建)
├── sample-vault/            # 示例数据
├── Journal/                 # 日记 (Daily/Weekly/Monthly/Quarterly)
├── Notes/                   # 速记
├── Decisions/               # 决策日志
├── Contacts/people/         # 联系人
├── 000-365-PLAN.md          # 年度计划（核心文件）
├── Dockerfile               # Docker 构建
└── docker-compose.yml       # Docker Compose
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.9+ / FastAPI |
| 前端 | Vue 3 CDN（无构建步骤） |
| 存储 | Markdown + JSON 文件 |
| AI | OpenAI 兼容 API / Ollama |
| 语音 | faster-whisper（本地转写） |
| 图表 | force-graph（关系网络） |
| 部署 | Docker / 裸机 |

## 设计理念

1. **本地优先** — 数据在你的磁盘上，不依赖任何云服务
2. **Markdown原生** — 所有数据都是纯文本，永远可读
3. **零构建** — 前端用 Vue CDN，不需要 npm/webpack
4. **AI可选** — AI是增强不是依赖，不配置也能完整使用
5. **鲁棒存储** — JSON 文件损坏自动备份恢复，不丢数据

## v0.1 特性清单

- [x] 总览仪表盘（进度环、里程碑时间轴、热力图、AI建议）
- [x] 365天作战地图（四季度 × 六维度，任务勾选）
- [x] 今日/本周任务管理（添加、编辑、勾选、重复任务）
- [x] 速记系统（文本/语音/图片，分类，AI处理）
- [x] 决策日志（看板 + 状态流转）
- [x] 关系网络（联系人CRUD、关系图、保温提醒）
- [x] 重要日子日历（倒计时、年/月重复）
- [x] 文件浏览器（Vault 全文件树）
- [x] AI 多模式（API / Ollama / 关闭）
- [x] 代理开关（右上角一键切换）
- [x] 语音转文字（本地 faster-whisper）
- [x] PWA 支持
- [x] Docker 部署
- [x] 响应式设计（桌面 + 移动端）

## License

MIT

---

> *"你有365天。每一天都是一次选择的机会。"*
