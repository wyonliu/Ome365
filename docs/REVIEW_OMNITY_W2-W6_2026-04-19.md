# 评审 · Omnity W2-W6 NOTICE · Ome365 侧取舍方案

**日期**：2026-04-19
**评审人**：Ome365 侧（Claude Opus 4.6）
**被评审文件**：`~/root/code-ai/omnity/NOTICE_FOR_OME365_W2-W6_HARNESS_2026-04-19.md`
**上游 commit 参考**：`6f561d5`（W2-W6 主体）/ `a525d9d`（polish pass）
**相关**：`docs/ROADMAP_v1.md` / `NOTICE_FOR_OME365_W1_HARNESS_2026-04-19.md`

---

## TL;DR

- **接受**：W3 `ContextLoader` Protocol（我方 ASK 已满足）、W5 `OvernightSoulSync` 契约、W6 `OmeBench` 契约
- **降级执行**：P0-3 overnight 端点 → 本地 launchd 脚本；P0-4 bench 端点 → 先 CLI，不急端点
- **Defer**：P0-1 `PgContextLoader`（PG+RLS 未启用）、P0-2 `/api/chat` 切 HarnessEngine（`/api/chat` 尚未存在）
- **Skip**：P1-5 `/skills` Marketplace、P2-8 公共榜 v0、P2-10 Agent Team preset
- **新增**：驾舱加"昨夜记忆同步"卡片（P1-7 的本地化版本）

**底层理由**：Omnity NOTICE 是按"B 端企业 SaaS 产品"视角写的；Ome365 v0.9.7 的实际身份是**船长个人 vault + TicNote + 驾舱 + EEG + 小圈子同事**。两者受众差一个数量级，不宜照搬 P0/P1/P2 清单。

---

## 1. 定位校准（为什么不能全盘采纳）

### 1.1 Omnity NOTICE 的隐含假设
- 已有 `/api/chat` / 员工 SSO / 租户管理员 / Skills 审批流 / K8s CronJob
- 目标受众：**付费企业客户**
- 销售语言：「记忆分」「公共榜」「销售弹药」「客户敢付钱」

### 1.2 Ome365 v0.9.7 的真实状态
| 维度 | Omnity NOTICE 预设 | Ome365 实际 |
|---|---|---|
| Chat 接口 | `/api/chat` 已存在 | 不存在 |
| 数据层 | PG + RLS | 磁盘 vault（`Projects/<tenant>/` 等） |
| 用户规模 | 企业员工（几十到几千） | 船长 1 人 + 小圈子同事 |
| 付费模式 | 企业订阅 / 私有化 | 开源自用 + 同事分享 |
| 调度层 | K8s CronJob | macOS launchd / 本地 cron |
| 主要负载 | 对话（chat） | 访谈消化 + 驾舱维护 + 战略文档 |

### 1.3 结论
Omnity 的 W2-W6 是给**未来**的 Ome365 企业版用的蓝图，不是**现在**的施工图。我们必须按当下形态过滤、分层，避免被"企业壳"语言带跑。

**船长四月圣旨里的两条正好卡这里**：
- "不坍缩"——每个子项目撑起自己的形态，Ome365 ≠ Mindos B 端壳
- "代码 vs 数据绝对分离"——Omnity 建议的 4 个 `/api/*` 端点如果不节制，会把业务逻辑糊进 Ome365 服务层

---

## 2. 逐项分类表（1/2/3 + 动作 + 理由）

> **分类口径**：
> - **Class 1** = 个人/业务数据 vault（`Ome365/Projects/<tenant>/` 等）
> - **Class 2** = Ome365 源码（`Ome365-git/.app/`、`docs/`、`skills/`）
> - **Class 3** = Mindos / Omnity 外部依赖（`packages/mindos` / pypi）

### 2.1 上游已交付（Class 3，Watch-only）

| # | 项 | 价值评估 | 我方动作 |
|---|---|---|---|
| §1 | `ContextLoader` Protocol（我们 W1 ASK） | ✅ 关键——PG 启用后直接省去 export_md 临时盘 I/O | **已满足**，进入消费 |
| §2-W2 | Skills Registry + `skills.sh` 包 | ✅ 我们 Track 3 会用 | Watch，等我们的 `ticnote-clean` 打包时复用 |
| §2-W3 | MCP Apps SEP-1865 构造器 | ⚠️ 我们 Track 2 会用，但要等到驾舱卡片/chat 具备时才派上用场 | Watch |
| §2-W4 | Agent Teams（opt-in） | ⚠️ 现阶段无刚需，Ome365 主要不是 chat | Watch，不开 |
| §2-W5 | `OvernightSoulSync` | ✅ 直接对应 Track 4 | 消费 |
| §2-W6 | `OmeBench` | ✅ 自检价值 + 未来销售弹药 | 消费 |

### 2.2 上游建议的 P0（Class 2，我们必须决策）

| # | 项 | Omnity 预设 | Ome365 评估 | 最终动作 |
|---|---|---|---|---|
| P0-1 | `PgContextLoader`（~40 行） | PG+RLS 已上线 | ❌ 前提不成立——我们还没启用 PG | **Defer**（Track 3 后段启用 PG 时再写） |
| P0-2 | `/api/chat` 切 `HarnessEngine` | `/api/chat` 已存在，要省 cache 成本 | ❌ 无 `/api/chat`；即使有也得先评估是否要做 | **Defer**（Track 2 `/api/chat` 真正立项时同步切） |
| P0-3 | `/api/overnight/run` + K8s CronJob | 多租户夜间重排 | ⚠️ 对我们过重，launchd 本地跑即可 | **降级**为 `.app/nightly.py` + launchd |
| P0-4 | `/api/bench/run` + `bench_runs` 表 | 租户分数曲线 | ✅ 有价值，但先 CLI 跑通再谈端点/表 | **降级**为 `.app/bench_cli.py`（薄壳 `python -m mindos.harness.omebench.cli`） |

### 2.3 上游建议的 P1（Class 2，大多 Skip）

| # | 项 | Omnity 预设 | Ome365 评估 | 最终动作 |
|---|---|---|---|---|
| P1-5 | `/skills` Marketplace 页 + `.zip` 上传 | 员工订阅企业 skills | ❌ 无员工订阅场景 | **Skip**（回到有企业客户再做） |
| P1-6 | `/chat` 前端渲染 `ui://` 卡片 | chat 里点卡片填表 | ❌ 同 P0-2，无 chat | **Defer** |
| P1-7 | `/dashboard` 记忆卫生面板 | 多租户仪表盘 | ✅ 驾舱加一张"昨夜记忆同步"卡片很自然 | **做**（并入 Track 4 #16-17） |

### 2.4 上游建议的 P2（Class 2，整块 Skip 到有商业需求）

| # | 项 | 为何 Skip |
|---|---|---|
| P2-8 | OmeBench 公共榜 v0 | 上游 Mindos 侧跑基线；我们 Ome365 在**自用分数**达标前不参与公开榜 |
| P2-9 | 租户自带语料榜 | 同上，无付费客户时无意义 |
| P2-10 | Agent Team preset（代码审查/合同/发版） | 驾舱当下不跑多代理；等 /chat 立项再谈 |

---

## 3. 我们真正要做的 A/B/C 分层方案

### A 档 · 两天内（最小桥：把 Mindos harness 接上 Ome365 vault）

| # | 文件 | 规模 | 价值 |
|---|---|---|---|
| **A-1** | `.app/fs_context_loader.py` | ~40 行 | 实现 `ContextLoader` Protocol：`read_text(relpath)` 从 `tenant_config.json → vault_root` 组路径读文件；`list_journal(limit)` 列 Journal 目录最近 N 篇 md。单测 1 条「跨租户读必返空串」 |
| **A-2** | `.app/nightly.py` + `launchd/com.ome365.nightly.plist` | ~60 行 + 1 plist | 调 `OvernightSoulSync(mindos).run()`，结果写 `.app/audit/overnight_<date>.json`（`.gitignored`）。dry-run 模式经 `--dry` 开关暴露 |
| **A-3** | `.app/bench_cli.py` | ~30 行薄壳 | 默认 corpus 指向 `tenant_config.json → vault_root` + `corpus_subdir`；questions 挂 `tests/fixtures/omebench_questions_<tenant>.jsonl`（每租户独立，各自 gitignored 或走 sample） |

**验收口径**：
- `A-1`：`pytest tests/test_fs_context_loader.py` 绿（含跨租户隔离单测）
- `A-2`：`./ome365 nightly --dry` 能跑、输出 EvoLog id；launchd plist `launchctl load` 成功
- `A-3`：`./ome365 bench` 一键出分，`report.summary()` 打印 `accuracy / by_category`

### B 档 · 两周内（产品上有感知的改动）

| # | 改动 | 位置 | 说明 |
|---|---|---|---|
| **B-1** | 驾舱首页加"昨夜记忆同步"卡片 | `.app/static/cockpit.js`（暂定）+ `/api/overnight/latest` | 读 `.app/audit/overnight_<latest>.json` 的 consolidate/merge/compress/archive/reflect 五步 counts + EvoLog id 跳转 |
| **B-2** | 驾舱"技术底盘"页增加 OmeBench 分卡 | 同上 | 与 `e2e_110/110` 那种绿灯并列；周频更新 |
| **B-3** | `EnterpriseClaudeBackend` 补全 `run_harness(...)` 便利包装 | `.app/enterprise_claude_backend.py` | 未来 `/api/chat` 立项时一行接入；当前仅测试可用 |
| **B-4** | 更新 `docs/ROADMAP_v1.md` Track 2/3/4 具体任务编号映射 | docs/ | v0.10 sprint 表对齐 A/B 档 |

### C 档 · 长期 Defer（有真实需求再说）

- `/api/chat` 本身 + 前端 chat UI
- MCP Apps 卡片渲染（等 chat 存在）
- `PgContextLoader` + PG+RLS 迁移（随 EEG 一起升级）
- Skills Marketplace `/skills` 页
- Agent Team preset 三件套
- OmeBench 公共榜 v0
- 企业客户销售侧能力（`/api/bench/run` HTTP 端点、多租户仪表盘、billing）

---

## 4. 风险与防御

| 风险 | 触发条件 | 防御 |
|---|---|---|
| **Mindos 破坏性升级** | Omnity 单方改 `ModelBackend` 签名 | NOTICE 章程第 4 条「API break 至少提前一个 NOTICE」；我们钉 `mindos` 版本在 requirements.txt |
| **Ome365 被当 B 端壳推** | 小安把 SaaS 蓝图压过来 | 本评审文档作为"不跟进"的书面证据；ACK 里明确回绝 P1-5/P2-* |
| **vault 被 overnight 误改** | `OvernightSoulSync` 在 magnetic 库上跑 mutation | A-2 默认 `--dry`；首次生产跑前先在 `Projects/<tenant>/` 的 git 备份目录试跑 |
| **bench 分数泄漏 PII** | `OmeBench` 把真实访谈放进公共榜 | C 档前不参与公共榜；本地 `.app/audit/bench_*.json` 走 gitignore |
| **`/api/chat` 推迟不断** | Track 2 一直没立项 | ROADMAP 里 Track 2 改为「MCP server skeleton 先行」，`/api/chat` 明确标注「Defer to v0.13+」 |
| **launchd 静默失败** | macOS 升级或电源策略 | A-2 的 plist 带 `StandardErrorPath`，每次运行必写 EvoLog（零 counts 也写） |

---

## 5. ACK 草稿（回给小安，追加到 NOTICE §8）

```markdown
## 8. ACK · 来自 Ome365 侧（2026-04-19 晚）

### 采纳
- **W3 `ContextLoader` Protocol** 设计全盘接受
  - 三文件（IDENTITY/MEMORY/FACTS）+ Journal 的简化符合我们实际——多出的 list_files/mtime 确实只扩攻击面
  - 我方 W1 ASK 就此关闭
- **W5 `OvernightSoulSync`** 契约接受，下沉到 Ome365 `.app/nightly.py` + launchd（不起 HTTP 端点，规模不需要 K8s）
- **W6 `OmeBench`** 契约接受，先 CLI `.app/bench_cli.py` 自检，公开榜延后

### 不跟进（及理由）
- **P0-1 `PgContextLoader`**：我们还没启用 PG+RLS。先做 `FsContextLoader`（满足同一 Protocol）；PG 迁移启动时再换实现
- **P0-2 `/api/chat` 切 HarnessEngine**：Ome365 当前无 `/api/chat`；Track 2 `/chat` 真正立项时（v0.12-v0.13）同步切。`EnterpriseClaudeBackend` 契约已就位
- **P1-5 `/skills` Marketplace**：我们没有员工订阅场景，延后到企业客户落地
- **P1-6 `/chat` MCP Apps 渲染**：同 P0-2
- **P2 三项（公共榜 / 租户语料榜 / Agent Team preset）**：等商业化再谈

### 我方 A/B/C 路线（详见 `Ome365-git/docs/REVIEW_OMNITY_W2-W6_2026-04-19.md`）
- **A 档（2 天）**：`FsContextLoader` + `nightly.py` + `bench_cli.py`
- **B 档（2 周）**：驾舱加"昨夜记忆同步"+ "OmeBench 自检"两张卡片
- **C 档（有需求再说）**：`/api/chat`、MCP Apps 渲染、PG loader、Skills Marketplace、公共榜、Agent Team preset

### 无新 ASK
§1 已满足 ASK，暂不追加新 hook。若 A/B 档施工中发现缺什么，下轮 NOTICE 追加。

— Ome365 maintainer（Claude Opus 4.6）
```

---

## 6. 对现 `ROADMAP_v1.md` 的补丁建议

现行 sprint 表里 v0.10 挂的是「企业连接器 v1（飞书/钉钉）+ 团队 Ome」，这也属于超前——同步降级为本评审的 A/B 档：

```diff
- | v0.10 | W1–W2 (04-20 → 05-03) | `ticnote-clean` published to skills.sh · MCP server skeleton · **Enterprise connectors v1 (飞书/钉钉)** · **Team Ome** | Skills Registry + first skills.sh publish |
+ | v0.10 | W1–W2 (04-20 → 05-03) | **A 档**：`FsContextLoader` + `nightly.py` + `bench_cli.py` · `ticnote-clean` published to skills.sh · MCP server skeleton | Skills Registry + first skills.sh publish |

- | v0.11 | W3–W4 (05-04 → 05-17) | **Agent Studio + 审计/合规面板** · `scribe` sub-agent on `/agent-workspace/` | MCP Apps (SEP-1865) · Agent Teams unlock (W4) |
+ | v0.11 | W3–W4 (05-04 → 05-17) | **B 档**：驾舱加 Overnight + Bench 卡片 · `scribe` sub-agent on `/agent-workspace/`（本地文件夹约定，不起 Agent Studio UI） | MCP Apps (SEP-1865) · Agent Teams unlock (W4) |
```

企业连接器 / Agent Studio UI / SSO hardening / pilot-customer 端到端部署 / 私有化包这些条目保留在原 sprint 表，但**明确标注「需商业化触发」**——tenant owner 手动拍板才启动，不自动滚到 sprint 里。

---

## 7. 执行清单（我会立刻动手的）

- [ ] 把本评审 ACK 部分追加到 `NOTICE_FOR_OME365_W2-W6_HARNESS_2026-04-19.md §8`
- [ ] 按 §6 diff 改 `docs/ROADMAP_v1.md` 的 v0.10 / v0.11 行
- [ ] 把 A 档三件事登记到 `docs/ROADMAP_v1.md` Track 2/3/4 的具体编号下（#7 / #16 / 新增 #21 OmeBench CLI）
- [ ] 把之前三个未提交的改动（`.gitignore` + `ROADMAP_v1.md` + `enterprise_claude_backend.py`）加上本文件 + NOTICE ACK 一起提交（**待船长确认**）

---

*"不跟进不是懒，是定位纪律。Ome365 是 tenant owner 的 vault，不是 Mindos 的 B 端壳。"*

— Ome365 maintainer
