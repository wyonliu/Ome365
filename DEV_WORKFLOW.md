# DEV_WORKFLOW · 双仓隔离开发纪律

## 两个仓的角色

| 仓 | 路径 | 作用 | Git 行为 |
|---|---|---|---|
| **Ome365-git** | `~/root/Ome365-git` | 纯代码树（public） | `push` 源头 |
| **Ome365** | `~/root/Ome365` | 生活/工作数据 vault + 运行时 live 配置 | 只 `pull`，不 `push` |

**铁律**
1. 代码改动 → 只在 `Ome365-git` 里写 → commit → push
2. 数据（访谈 / 报告 / 记忆 / `*_config.json` live / `_registry.json` live） → 只在 `Ome365` 里，永远不入 git
3. Ome365 同步最新代码：`cd ~/root/Ome365 && git pull`（live 配置全部 gitignored，不会被 pull 覆盖）
4. **pre-commit hook 是守门员**：Ome365-git 根目录有 `.git/hooks/pre-commit`，会拦截 PII / 租户品牌字符串；绝不使用 `--no-verify` 绕过

## 三件套模式（live + sample + /api）

所有租户耦合、PII、业务内容都走这个模式，代码仓只有 sample，Ome365 数据仓存 live：

| 配置文件 | live（Ome365，gitignored） | sample（Ome365-git，tracked） | API |
|---|---|---|---|
| **tenant_config** | `.app/tenant_config.json` | `.app/tenant_config.sample.json` | `GET /api/tenant/config` |
| **cockpit_config** | `.app/cockpit_config.json` | `.app/cockpit_config.sample.json` | `GET /api/cockpit/config` |
| **share_registry** | `.app/share_registry.json` | `.app/share_registry.sample.json` | `GET /api/share/registry`（public 面向 share_server） |

三者都走 **live→sample fallback**：`server.py` 先读 live，缺失才读 sample；返回值带 `_source` 字段标识来源。

## 新敏感字段 / 租户耦合怎么办？

**识别原则**：凡是可能随租户/个人变化的字符串（品牌名、目录名、人名、组织术语、分类规则、prompts 里的 bio）都属于敏感字段，不能硬编码。

1. 从 `.app/server.py` / `.app/share_server.py` / `.app/static/app.js` / `.app/static/index.html` / `.app/static/share.html` 里把字段提出来
2. 写进对应的 **sample** 文件（占位示例，通用 "Example Workspace" 口径）
3. 写进 `~/root/Ome365/.app/*.json` 真值（live，gitignored）
4. 扩展对应 `GET /api/*/config` 端点（server.py）和前端 loader（app.js / share.html）
5. 前端用 `tenantConfig?.brand.xxx ?? 'fallback'` 样式消费，永不硬编码中文/租户名
6. 本地 fresh-clone 自测通过后再 commit

## Fresh-clone 自测（必须通过才能 push）

```bash
# 模拟新同事首次 clone
rm -rf /tmp/ome365-test && git clone ~/root/Ome365-git /tmp/ome365-test
cd /tmp/ome365-test
OME365_PORT=3698 OME365_VAULT=/tmp/ome365-vault python3 .app/server.py &
sleep 2
curl -s http://localhost:3698/api/tenant/config | jq ._source
# 期望：tenant_config.sample.json
curl -s http://localhost:3698/api/cockpit/config | jq ._source
# 期望：cockpit_config.sample.json
```

如果 `_source` 返回 `tenant_config.json`（live 文件），说明代码仓混入了 live，立即排查 `.gitignore` 与文件来源。

## 回流（Ome365 → Ome365-git）

代码/文档如果在 Ome365 里改了（例如热修 bug），必须回流：

```bash
cd ~/root/Ome365
# 确认不是 live 配置、不是数据文件
git diff <file>
# 复制到 Ome365-git
cp .app/xxx.py ~/root/Ome365-git/.app/xxx.py
cd ~/root/Ome365-git && git add .app/xxx.py && git commit -m "..."
git push && cd ~/root/Ome365 && git pull
```

## 常见踩坑

- **pre-commit hook 拦截**：说明代码里混入了 PII / 租户名，按提示把字段外抽到三件套，不要 `--no-verify`
- **fresh-clone 启动后 API 返回 live 源**：live 文件误入代码仓，检查 `.gitignore`
- **前端硬编码中文**：所有用户可见字符串都应 fallback 到 `tenantConfig?.brand.*`
- **sample 文件写了真值**：sample 必须是通用占位（"Example Workspace" / "Cockpit" / "demo@example.com"），严禁真名真术语
