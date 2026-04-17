# Ome365

**AI 原生个人操作系统** — 记忆 · 反思 · 执行 · 养成

<p align="center">
  <img src="https://img.shields.io/badge/version-v0.8-blue" alt="v0.8">
  <img src="https://img.shields.io/badge/python-3.9+-blue" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/vue-3.x-green" alt="Vue 3">
  <img src="https://img.shields.io/badge/storage-markdown-orange" alt="Markdown">
  <img src="https://img.shields.io/badge/AI-Omnity--Ome%20SDK-purple" alt="Omnity Ome">
  <img src="https://img.shields.io/badge/license-MIT-brightgreen" alt="MIT">
</p>

---

## 为什么需要 Ome365？

你有 365 天。一年后的你，和现在有什么不同？

Ome365 不是笔记工具。它是一个**会记住你、理解你、帮你执行**的个人操作系统：

- **记忆** — 基于 Omnity-Ome SDK，AI 自动从对话和速记中积累记忆，越用越懂你
- **反思** — 一键生成今日/本周复盘，综合日志、速记、联系人、任务全量数据分析
- **执行** — 365天计划拆解到季→月→周→日，每一天都有明确的下一步
- **养成** — 把 AI 当数字生命养成，4 阶段成长 × 7 级羁绊 × 12 个成就

## v0.8 新增

- **AI 智能速记** — 悬浮入口一键跳转速记页，输入任意内容后「速记」直接保存或「⚡ 智能」AI 分析提取联系人/待办/笔记
- **反思视图** — 独立反思页面，历史反思列表可展开，适合截图分享
- **Ome 记忆管理** — 每条 AI 记忆支持 hover 编辑/删除，内联确认不弹窗
- **AI 质量优化** — 结构化提取用 `temperature: 0`，反思用 `temperature: 0.3`；journal 空模板自动剥离；联系人上下文扩充至 1500 字/人；system 和 user prompt 分离
- **任务直删** — 所有视图（今日/明日/本周/本月）每条任务 hover 显示删除按钮，无需进入编辑
- **跨视图编辑** — 周/月视图也有完整的编辑面板（时间/描述/删除）
- **AI 非阻塞** — 所有 AI 调用 `asyncio.to_thread()`，反思/智能录入/对话不再卡死整个界面
- **智能录入升级** — 提取的 summary 才写入 Ome 记忆（不再存原文）；future date 任务自动路由到对应日期文件

### 历史版本

<details>
<summary>v0.6 — Omnity-Ome 智能体接入</summary>

- Ome SDK 驱动的记忆/对话/养成一体化
- 记忆搜索 + 类型筛选
- 成长阶段门控 + 成熟度诊断
</details>

<details>
<summary>v0.5 — 统一清单 + 养成自进化</summary>

- 统一清单视图（今日/明日/本周/本月/日子 Tab 切换）
- 跨天任务可见，养成自进化计数
</details>

<details>
<summary>v0.4 — AI 智能录入</summary>

- 粘贴任意内容，AI 自动提取联系人/事件/待办/笔记
- 养成页双栏重设计，速记单条删除
</details>

<details>
<summary>v0.3 — 养成系统 + 提醒</summary>

- 数字生命养成，闹钟提醒，AI 主动消息
- 时间块管理，记忆增强 AI 对话
</details>

<details>
<summary>v0.2 — 记忆系统</summary>

- 多层记忆，全文搜索，AI 反思
- 心情/能量/专注度追踪，连续打卡
</details>

<details>
<summary>v0.1 — 基础</summary>

- 365天作战地图，日/周任务，速记，决策日志
- 关系网络，重要日子，AI 助手，暗色主题
</details>

## 快速开始

### 本地运行

```bash
git clone https://github.com/wyonliu/Ome365.git
cd Ome365

# 一键初始化（推荐首次运行）
./setup.sh

# 或手动：
pip install -r requirements.txt
cp .env.example .env       # 按需填 AI key
cd .app && python3 server.py
```

打开 `http://localhost:3650`。首次启动会用 `sample-vault/` 作 demo 数据；
替换为真实内容后，删除/覆盖根目录下的 `Journal/` `Notes/` 等即可。

### Docker

```bash
git clone https://github.com/wyonliu/Ome365.git
cd Ome365
docker compose up -d
```

### 配置 AI

在「设置」页面选择模式：

| 模式 | 推荐 | 说明 |
|------|------|------|
| **API** | DeepSeek | 直连快速，中文好，`deepseek-chat` 即可 |
| **API** | OpenRouter | 可切换多家模型，需代理 |
| **Ollama** | llama3.1 | 完全离线，需本地算力 |

> 反思质量与模型强相关。DeepSeek Chat 性价比最高；Claude Sonnet 质量最好。

## 目录结构

```
Ome365/
├── .app/                    # 应用代码
│   ├── server.py            # FastAPI 后端（3000+ 行）
│   └── static/              # 前端 Vue 3 CDN（零构建）
├── Journal/                 # 日记（Daily/Weekly/Monthly/Quarterly）
├── Notes/                   # 速记（每日一文件）
├── Memory/                  # AI 记忆 + 反思洞察
│   ├── insights/            # AI 反思文档（daily/weekly）
│   └── *.md                 # 手动记忆文件
├── Decisions/               # 决策日志
├── Contacts/people/         # 联系人档案
├── 000-365-PLAN.md          # 年度计划
└── CLAUDE.md                # AI 集成桥接
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.9+ / FastAPI / Uvicorn |
| 前端 | Vue 3 CDN + marked.js（零构建） |
| 存储 | Markdown + JSON 文件（本地优先） |
| AI 记忆 | Omnity-Ome SDK（SQLite 向量存储） |
| AI 对话 | OpenAI 兼容 API / Ollama |
| 语音 | faster-whisper（本地转写） |
| 关系图 | force-graph 力导向布局 |

## 设计理念

1. **本地优先** — 数据在你的磁盘上，Markdown 纯文本，永远可读可迁移
2. **零构建** — 前端 Vue CDN，后端单文件 Python，`python3 server.py` 即跑
3. **AI 增强不依赖** — 不配 AI 也能完整使用，配了之后体验指数级提升
4. **记忆驱动** — AI 不是每次从零开始，而是越用越懂你
5. **自进化** — 每个操作都在让系统更了解你，养成数字生命

## License

MIT

---

> *"你有365天。每一天都是一次选择的机会。"*
