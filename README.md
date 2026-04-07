# Ome365

**个人超级助手** — AI记忆、Markdown存储、本地优先

<p align="center">
  <img src="https://img.shields.io/badge/version-v0.5-blue" alt="v0.5">
  <img src="https://img.shields.io/badge/python-3.9+-blue" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/vue-3.x-green" alt="Vue 3">
  <img src="https://img.shields.io/badge/storage-markdown-orange" alt="Markdown">
  <img src="https://img.shields.io/badge/AI-DeepSeek%20%7C%20OpenRouter%20%7C%20Ollama-purple" alt="AI">
  <img src="https://img.shields.io/badge/license-MIT-brightgreen" alt="MIT">
</p>

---

## 为什么需要 Ome365？

你有365天。一年后的你，和现在有什么不同？

Ome365 帮你把年度目标拆解为可执行的每日行动，用AI记忆系统越来越懂你，用反思引擎帮你持续进化。

**不是又一个笔记工具。** 是一个会记住你、理解你、帮你执行的个人超级助手。

## 核心特性

### v0.5 新增
- **统一清单视图** — 今日/明日/本周/本月/日子合并为一个视图，Tab切换，不再散落各处
- **跨天任务可见** — 本周添加到指定日期的任务，在所有视图（今日/本周/本月）都能看到
- **日程安排** — "时间块"更名为"日程安排"，更直观，支持`日程`和`时间块`两种markdown标题
- **养成自进化** — 每个操作（添加任务/笔记/联系人/智能录入）自动更新养成计数，每20次自动触发AI进化分析
- **全端口联动** — 所有用户动作自动关联养成系统+记忆系统，真正的自进化生命体感

### v0.4
- **AI智能录入** — 粘贴任意内容（会议记录/聊天/邮件），AI自动提取联系人、事件、待办、笔记并写入系统
- **养成页桌面重设计** — 双栏布局，身份+羁绊并排，数据+阶段并排，更丰富的视觉交互
- **日子时间轴统一** — "全部日子"列表升级为与里程碑一致的时间轴视觉（ms-tl-*）
- **速记单条删除** — hover显示删除按钮，优雅确认后删除单条速记

### v0.3
- **养成系统** — 把AI助手当数字生命养成，4阶段成长 + 7级羁绊 + 12个成就
- **智能体进化** — AI分析互动模式，自动进化个性特征，可视化进化历程
- **闹钟提醒** — 任务/时间块/日子到时自动提醒（浏览器通知+音效），3种音效可选
- **AI主动式** — AI根据时间和任务状态主动发消息（晨间激励/午间提醒/冲刺/复盘）
- **时间块管理** — 可视化添加/编辑/删除时间段规划（如 09-12 深度编程）
- **时间点/时间段** — 任务支持 `[09:00]` 时间点和 `[09:00-12:00]` 时间段两种模式
- **记忆增强AI** — AI对话自动注入用户记忆，真正"越用越懂你"
- **总览重设计** — 主计划卡+心情/活跃一排，今日+本周一排，统一里程碑时间轴

### v0.2
- **记忆系统** — 多层记忆（身份/偏好/目标/技能/洞察），AI越用越懂你
- **全文搜索** — Cmd+K 搜索全部笔记、日志、计划，快速定位
- **AI反思** — 每日/每周深度反思，自动保存洞察到记忆
- **心情/能量/专注度** — 每日状态追踪，可视化趋势
- **连续打卡** — 自动计算连续活跃天数，激励坚持
- **回忆** — "去年今日"功能，回顾同一天的笔记
- **CLAUDE.md桥接** — 外部AI（Claude Code等）可直接接入，理解你的数据

### v0.1 基础
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
├── CLAUDE.md                # AI集成桥接文件 (v0.2)
├── Journal/                 # 日记 (Daily/Weekly/Monthly/Quarterly)
├── Notes/                   # 速记
├── Memory/                  # AI记忆系统 (v0.2)
│   ├── MEMORY.md            # 记忆索引（自动生成）
│   └── insights/            # AI反思洞察
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
| 记忆 | MEMORY.md 索引 + 主题文件 |
| 语音 | faster-whisper（本地转写） |
| 图表 | force-graph（关系网络） |
| 部署 | Docker / 裸机 |

## 设计理念

1. **本地优先** — 数据在你的磁盘上，不依赖任何云服务
2. **Markdown原生** — 所有数据都是纯文本，永远可读
3. **零构建** — 前端用 Vue CDN，不需要 npm/webpack
4. **AI可选** — AI是增强不是依赖，不配置也能完整使用
5. **鲁棒存储** — JSON 文件损坏自动备份恢复，不丢数据
6. **记忆驱动** — AI越用越懂你，不是每次从零开始 (v0.2)

## License

MIT

---

> *"你有365天。每一天都是一次选择的机会。"*
