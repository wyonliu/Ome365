# DEV_WORKFLOW · 双仓隔离开发纪律

## 两个仓的角色

| 仓 | 路径 | 作用 | Git 行为 |
|---|---|---|---|
| **Ome365-git** | `~/root/Ome365-git` | 纯代码树（public-safe） | `push` 源头 |
| **Ome365** | `~/root/Ome365` | 生活/工作数据 vault + 运行时 | 只 `pull`，不 `push` |

**铁律**
1. 代码改动 → 只在 `Ome365-git` 里写 → commit → push
2. 数据（访谈/报告/记忆/cockpit_config.json） → 只在 `Ome365` 里，永远不入 git
3. Ome365 同步最新代码：`cd ~/root/Ome365 && git pull`（`.app/cockpit_config.json` 是 gitignored，不会被动）

## 新敏感字段怎么办？

1. 从 `.app/static/app.js`、`.app/server.py` 里把字段提出来
2. 写进 `.app/cockpit_config.sample.json`（占位示例）
3. 写进 `~/root/Ome365/.app/cockpit_config.json`（真值，gitignored）
4. 扩展 `GET /api/cockpit/config`（server.py）和 `loadCockpitConfig()`（app.js）

## 启动测试（sample-vault）

在 Ome365-git 里 `python3 .app/server.py`，访问 `/api/cockpit/config`，应返回 `_source: cockpit_config.sample.json` 且数据是占位内容。这保证外人 clone 下来也能跑起来看到 demo。
