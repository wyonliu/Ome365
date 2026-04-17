# Contributing to Ome365

感谢对 Ome365 感兴趣！本文档是外部贡献者快速上手的入口。如果你是项目作者本人，请先读 [`DEV_WORKFLOW.md`](./DEV_WORKFLOW.md) 了解双仓纪律。

## 项目定位

Ome365 是一个 **AI 原生、本地优先** 的 PKM（Personal Knowledge Management）工具，核心特点：

- 数据全部本地文件系统（Markdown + JSON，无数据库）
- 支持 OpenRouter / Ollama 双模式 AI
- **租户驾舱** 可通过 `tenant_config.json` 完全自定义品牌、分类、目录结构
- 前端 Vue 3 CDN + FastAPI 后端，无构建步骤

## 快速上手

```bash
git clone git@github.com:wyonliu/Ome365.git
cd Ome365
pip install -r requirements.txt
export OME365_VAULT=/path/to/your/vault
cd .app && python3 server.py
# 浏览器打开 http://localhost:3650
```

首次启动会读 `.app/tenant_config.sample.json`（通用 "Example Workspace" 口径），驾舱目录自动建在 `$OME365_VAULT/Cockpit/`。

## 开发前必读

### 1. 代码 vs 数据绝对分离

这是项目最重要的纪律：

- **代码仓**（本仓）只存：Python / JS / HTML / CSS / sample 配置 / 文档 / sample-vault
- **数据仓**（你本地的 `$OME365_VAULT`）只存：个人笔记 / 访谈 / 报告 / live 配置（`*_config.json`）

live 配置永远 gitignored。提交代码时，pre-commit hook 会扫描 PII（邮箱、手机号、租户品牌字符串）并拦截。

### 2. 三件套配置模式

凡租户/个人可变内容（品牌名、分类规则、prompts）都走：

| 层 | 作用 | 示例 |
|---|---|---|
| `.app/xxx.sample.json` | tracked，通用占位 | `.app/tenant_config.sample.json` |
| `.app/xxx.json` | gitignored，真值 | 你本地的 `.app/tenant_config.json` |
| `GET /api/xxx/config` | live→sample fallback | `GET /api/tenant/config` |

新增敏感字段流程见 [`DEV_WORKFLOW.md`](./DEV_WORKFLOW.md)。

### 3. Fresh-clone 自测

改了配置 schema / 前端消费逻辑后，**必须** 用干净目录 clone 跑一遍：

```bash
git clone . /tmp/ome365-test
cd /tmp/ome365-test
OME365_PORT=3698 OME365_VAULT=/tmp/ome365-vault python3 .app/server.py
```

确认：
- `GET /api/tenant/config` 返回 `_source: tenant_config.sample.json`
- 前端不出现任何中文硬编码或租户品牌字符串
- 驾舱/访谈页面不 fatal，空数据优雅降级

## PR 规则

### 会被合并的 PR

- **Bug 修复**：附重现步骤 + 修复前后对比
- **通用能力增强**：新视图、新 AI provider、性能优化、测试补强
- **文档完善**：README / ARCHITECTURE / DEV_WORKFLOW 的澄清与扩展
- **i18n 支持**：把用户可见字符串进一步外抽（目前还有残留中文 UI 文案）

### 会被拒绝的 PR

- **带 PII 或真实租户数据**：邮箱、手机号、公司名、真人名
- **硬编码中文业务术语到源码**：应走 `tenant_config` 三件套
- **用 `--no-verify` 绕过 pre-commit**
- **破坏三件套模式**：live 文件被 tracked / sample 文件被写入真值
- **引入重型依赖**：项目坚持 "无构建前端 + FastAPI" 技术栈，不接受 Vite/Webpack/Next 等迁移 PR（除非作者主动发起）
- **大规模重构未先开 Issue 讨论**

### 分支与 Commit

- 从 `main` 切 feature branch：`feature/xxx` / `fix/xxx` / `docs/xxx`
- Commit message 中文英文都可，主 commit 简述 "what + why"，不要堆实现细节
- PR 描述写清：动机、方案、验证手段、涉及文件
- 一个 PR 聚焦一件事，不要混修多个主题

## Issue 规则

- **Bug report**：OS / Python 版本 / 复现步骤 / 期望 vs 实际
- **Feature request**：先描述场景与痛点，不要直接要求"加个 XX 按钮"
- **Security issue**：不要发 public issue，邮件联系作者

## 不会被接受的改动

以下属于项目作者的个人数据仓范畴，**不要** 发相关 PR：

- 访谈内容 / 诊断报告 / A4S 方案（在 Ome365 数据仓，不在本仓）
- 个人 Journal / Memory / Growth 状态
- 租户品牌文案（作者自用 live 配置里的真实品牌）
- TicNote 自动化里 **作者专属** 的关键词逻辑（通用清洗规则可以改）

## 代码风格

- **Python**：PEP 8，字符串优先双引号，避免引入 black/isort 作为强制（作者自用格式）
- **JavaScript**：2 空格缩进，`const` > `let`，无分号风格已统一
- **不要** 无缘无故重排 import / 加 type hints / 加 docstring 到你没改的代码里（"只改说的那个地方"）

## License

项目当前未明确 LICENSE。在作者添加之前，提交的代码视为贡献者同意后续被纳入作者选定的开源协议（预计 MIT）。

## 联系

- Issues：https://github.com/wyonliu/Ome365/issues
- 作者：wyonliu（GitHub）
