# Ome365 · Architecture Review v0.8

> 2026-04-15 · 船长 & 小安
> 目标：把当前单用户私人工具，推进为"同事可装可用"的 AI 原生 PKM 平台。

---

## 一 · 当前架构速览

```
┌──────────────────────────────────────────────────────────────┐
│  Browser (Vue 3 CDN · 单页)                                  │
│  ├─ 12 Views: dashboard/tasks/plan/insights/life/cockpit/    │
│  │            notes/reflections/contacts/memory/growth/      │
│  │            interviews/reports/files/settings              │
│  └─ Theme: dark (default) + light (可按租户换色)             │
├──────────────────────────────────────────────────────────────┤
│  FastAPI :3650  ◀──  server.py（5095 行，121 个 endpoints）  │
│  ├─ Task/Day/Week/Quarter 管理                               │
│  ├─ Contacts + 关系图 + 冷启动提醒                           │
│  ├─ Memory/反思/Growth (Ome 养成)                            │
│  ├─ Insights 综合分析                                         │
│  ├─ Interviews + Reports（驾舱：租户可配置分类/品牌）        │
│  ├─ Life（家庭/仪式/健康）                                   │
│  ├─ AI Proxy (OpenRouter / Ollama)                           │
│  └─ Whisper / OCR / Media upload                             │
├──────────────────────────────────────────────────────────────┤
│  Storage: File System（Markdown + JSON，无数据库）           │
│  ├─ $VAULT/Journal, Notes, Decisions, Contacts...            │
│  ├─ $VAULT/Memory/*.md（Ome 记忆）                           │
│  ├─ $VAULT/TicNote/{date}/*.md（访谈转录）                   │
│  ├─ $VAULT/reports/**（按租户可配置的报告/诊断目录）         │
│  └─ .app/*.json（运行时状态：growth/settings/reminders...）  │
└──────────────────────────────────────────────────────────────┘
```

### 技术栈

| 层 | 选型 | 状态 |
|---|---|---|
| 后端 | FastAPI + uvicorn | ✅ 单文件 5k 行，急需拆分 |
| 前端 | Vue 3 (CDN) + 纯 JS | ✅ 单文件 4.8k 行，无构建 |
| 样式 | 手写 CSS | ✅ 10k 行，双主题 |
| 存储 | 本地 FS + JSON | ✅ 无 DB 即是卖点 |
| AI | OpenRouter (主) / Ollama (备) | ✅ |
| 记忆 | Omnity-Ome SDK | ✅ pip 包 |
| 转录 | Whisper (OpenAI API) | ✅ |
| 访谈 | TicNote + Playwright 自动导出 | ✅ |
| 部署 | Dockerfile + docker-compose | ⚠️ 未验证 |

---

## 二 · 定制化累积的特性地图

**Tier 0 · 通用 PKM 核心**（值得开源）
- 365 天计划拆解（季→月→周→日）
- 任务/速记/反思/日志 CRUD
- 联系人 + 关系图 + 冷启动提醒
- Ome 养成（4 阶段 × 7 级羁绊）
- **Enterprise Entity Graph (EEG)** — 企业术语/人名/组织/产品常识层，见 `docs/EEG.md` · `Knowledge/entities/`

**Tier 1 · 工作上下文特化**（租户驾舱，由 `.app/tenant_config.json` 驱动）
- Interviews 抽屉（TicNote pipeline）
- Reports 驾舱（6 大板块，可按租户裁剪）
- SECTION_TAXONOMY + PERSON_DISPLAY_MAP + 叙事弧
- 可配置浅色主题（`tenant_config.brand.theme_variant_label`）

**Tier 2 · 个人生活特化**
- Life：女儿/周末/仪式/健康记录
- Insights：综合洞察合成

**Tier 3 · 外部依赖脚本**
- TicNote Playwright 自动导出
- ASR 修正字典（ASR_FIXES 55+ 条 · 已归口 EEG，硬编码仅兜底）
- 发布矩阵（CaptainCast 播客：公众号/B 站/视频号/X/小红书）

---

## 三 · 技术债清单（按严重程度）

### 🔴 P0 · 阻挡多用户/同事可用
1. **单用户硬编码**：VAULT 环境变量指向单目录，无用户概念
2. **API key 明文存 settings.json**：无多租户密钥隔离
3. **运行时状态跟代码混放** `.app/*.json`：每用户独立状态无处安放
4. **无认证/授权**：`localhost:3650` 裸奔

### 🟡 P1 · 代码健康度
5. **server.py 5095 行单文件**：亟需拆模块（tasks/memory/reports/interviews/life/growth）
6. **app.js 4858 行单文件**：Vue 模块未拆组件
7. **TicNote export 脚本有 4 个历史版本**：已清，保留 export/clean/rename 三件套
8. **没有测试**：回归风险高

### 🟢 P2 · 可逐步演进
9. **依赖文档缺**：`requirements.txt`、`pyproject.toml` 不完整
10. **数据迁移脚本缺**：升级时无 schema migration
11. **Docker 未验证**：Dockerfile 存在但未确认能跑
12. **Settings UI 不完整**：很多配置项要改 JSON

---

## 四 · 同事可用版本 · 开发方案

### Phase 0 · 可分享的私有版（本次交付）
> **目标**：把工程代码推到 GitHub，同事 clone 后改 settings.example.json 就能本地起
- ✅ .gitignore 严格化，敏感数据隔离
- ✅ settings.example.json 模板
- ✅ README 更新同事 setup 步骤
- ⏳ Dockerfile 验证
- 预计工期：今天

### Phase 1 · Onboarding 体验（1 周）
> **目标**：同事 clone 后 3 分钟能跑起来
- [ ] `setup.sh` 一键安装（venv + pip + 首次配置向导）
- [ ] **首次启动向导**：Web 引导 → 填 name/goal/OpenRouter key → 选 vault 目录
- [ ] `.env.example` 标准化所有配置（VAULT/PORT/AI_MODE/API_KEY）
- [ ] `requirements.txt` 完整锁定版本
- [ ] `docker-compose.yml` 验证 + 说明文档
- 产出：v0.9 "Solo Ready"

### Phase 2 · Multi-User（2-3 周）
> **目标**：一台机器多人同时用（家庭/小团队）
- [ ] 引入 `User` 概念：`users/{uid}/settings.json` + `users/{uid}/vault/`
- [ ] 简单认证：BasicAuth / magic-link（不上 OAuth）
- [ ] 路由改造：`/api/{uid}/...` 或 session-based
- [ ] 前端登录页 + user switcher
- [ ] 数据迁移脚本：把当前 vault → `users/captain/vault/`
- 产出：v1.0 "Family Ready"

### Phase 3 · 代码健康度（持续）
> **目标**：工程师可读可改
- [ ] server.py 拆模块：`routers/{tasks,memory,reports,interviews,life,growth,ai}.py`
- [ ] app.js 拆组件：`components/{dashboard,cockpit,interviews,...}.js`（或迁移 Vite + SFC）
- [ ] pytest 测试套件（至少 API 烟雾测试）
- [ ] GitHub Actions CI

### Phase 4 · 开源化（可选）
> **目标**：Tier 0 核心开源，Tier 1/2 做成 plugin
- [ ] 抽出 `ome365-core`：Tier 0 + 插件系统
- [ ] `ome365-tenant-pack`：驾舱、TicNote、Reports（由 `tenant_config.json` 驱动）
- [ ] `ome365-life-plugin`：Life、Growth 深度特性
- [ ] MIT license + 文档网站

---

## 五 · 同事试用快速路径（MVP）

**本次推送后，同事只需**：

```bash
# 1. Clone
git clone git@github.com:wyonliu/Ome365.git && cd Ome365

# 2. 装依赖
pip install -r requirements.txt
pip install omnity-ome  # Ome SDK

# 3. 起 vault（任选目录）
export OME365_VAULT=/Users/xxx/MyVault

# 4. 配置
cp .app/settings.example.json .app/settings.json
# 编辑 settings.json 填入自己的 OpenRouter key

# 5. 起服务
cd .app && python3 server.py
# 浏览器打开 http://localhost:3650
```

**局限**：
- 驾舱/Interviews/Reports 依赖 `tenant_config.json` + 租户数据，新装时为空
- Life/Growth 要从 0 养
- 所有数据在本地，不要写公司机密

---

## 六 · 本次推送的边界（数据安全）

**会推送**：
- `.app/server.py`, `.app/static/*`（纯代码）
- `.app/ticnote_export.py`, `ticnote_clean.py`, `ticnote_rename.py`（工具脚本）
- `.app/settings.example.json`（模板）
- `README.md`, `Dockerfile`, `docker-compose.yml`, `setup.sh`
- `docs/ARCHITECTURE.md`（本文）
- `sample-vault/`（示例数据）

**绝不推送**（已 .gitignore）：
- 租户 vault 数据目录（驾舱目录、`TicNote/`, `Hiring/`, `Life/`, `Insights/`, `Projects/`）
- `Memory/`, `Journal/`, `Notes/`, `Decisions/`, `Contacts/`（个人 vault）
- `.app/settings.json`（含 API key）
- `.app/growth.json`, `.app/reminders.json`, `.app/media/`（个人状态）
- `.env`, `.cursor/`, `.claude/`, `.obsidian/`
