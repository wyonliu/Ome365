# Contributing to Ome365

> Tagline: **Run your company on agents, not org charts.**
> Sub: **Your AI follows the employee, not the employer.**

Thanks for your interest in Ome365! This doc is the fast-track for external contributors. If you're the project author, see [`DEV_WORKFLOW.md`](./DEV_WORKFLOW.md) for the dual-repo discipline.

> **v1.1 contributor essentials** (added 2026-05-09 with v1.1.x series):
>
> 1. **Kevin "先文件再代码" rule**: every code commit must cite a Decision via
>    `[decision: <id>]` in the commit message. Create the decision file FIRST in
>    `vault.example/Decisions/<id>.md`, then write code. Hook in `.githooks/`
>    will reject commits without the tag (bypass: `OME365_NO_DECISION=1`).
> 2. **Run `./ome365 doctor`** before opening a PR — it shows all 12 v1.1
>    modules loaded and surfaces any vault state issues.
> 3. **Run `python3 -m pytest tests/ -q`** locally — should be 449/449 green.
>    CI also runs the full suite via `.github/workflows/ci.yml`.
> 4. **Run `python3 scripts/scan_pii.py`** — must be `0 hits`. PII gates the
>    commit; the scanner walks tracked files for leak patterns.
> 5. **Use `--dry-run` flags** when adding mutating CLIs (we have it on
>    `wiki update`, `archive`, `backup create`). It's the team's preferred
>    "preview before commit" pattern.
> 6. **No emojis in committed files** unless explicitly requested. Comments
>    in code: only when the WHY is non-obvious. No "what" comments.

## Project positioning

Ome365 is the **open-source enterprise AI platform** — file-first multi-tenant Markdown vault, self-learning **Hike** (Hive Intelligence Knowledge Engine, see [`docs/hike.md`](./docs/hike.md)) for organizational memory + decision distillation, and cross-company portability via W3C DID.

Core principles:

- **Local-first**: data lives in your filesystem (Markdown + JSON · no DB by default)
- **Default-private LLM**: ships with Ollama-first config; 9 backends opt-in (DeepSeek/OpenAI/Claude/Gemini/Qwen/Doubao/智谱/OpenRouter/Ollama)
- **Multi-tenant**: 5 AuthProvider (none/basic/magic_link/oidc/wecom)
- **Zero-build frontend**: Vue 3 CDN + FastAPI backend
- **Hike v0.1 → v2 roadmap**: schema v0.2 + L2 Event + L4 Cognition + L6 Swarm + UI 4 page (D+1 ~ D+45 alpha)

## Quick start

```bash
# Option A: one-line installer (macOS/Linux/WSL · auto deps + browser)
curl -fsSL https://raw.githubusercontent.com/wyonliu/Ome365/main/install.sh | sh

# Option B: manual clone
git clone git@github.com:wyonliu/Ome365.git
cd Ome365
./ome365 doctor   # check Python ≥ 3.9 / port / config
./ome365          # auto-install deps · boot · open browser

# Option C: dev mode (custom port + vault)
pip install -r requirements.txt
OME365_PORT=3698 OME365_VAULT=/tmp/ome365-test python3 .app/server.py
```

Default settings ship with `.app/tenant_config.sample.json` ("Example Workspace") and `.app/cockpit_config.sample.json` (no PII). The cockpit directory auto-creates at `$OME365_VAULT/Cockpit/`.

## Pre-PR safety check

Before opening a PR, run:

```bash
python3 scripts/scan_pii.py                  # L1+L2+L4 quick scan (should exit 0)
python3 scripts/scan_pii.py --fixtures       # contract test 47/47
bash install.sh --dry-run                    # confirm install plan
```

The pre-commit hook is auto-installed; you can also enable it manually:

```bash
git config core.hooksPath .githooks
```

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

### DCO Sign-Off (Developer Certificate of Origin)

We use [DCO](https://developercertificate.org/) instead of CLA. **Every commit must be signed off**:

```bash
git commit -s -m "your message"
# adds: Signed-off-by: Your Name <you@example.com>
```

By signing off, you certify that:
1. The contribution is your own original work, OR
2. The contribution is licensed under an appropriate open source license that allows you to submit it, OR
3. You received the contribution from someone who has certified (1) or (2)

The DCO bot will check every PR. To fix unsigned commits:

```bash
git rebase --signoff main   # signs all commits between HEAD and main
git push -f origin <branch>
```

CLA is **not** required.

## Issue 规则

- **Bug report**：OS / Python 版本 / 复现步骤 / 期望 vs 实际
- **Feature request**：先描述场景与痛点，不要直接要求"加个 XX 按钮"
- **Security issue**：不要发 public issue，邮件联系作者

## 不会被接受的改动

以下属于项目作者的个人数据仓范畴，**不要** 发相关 PR：

- 访谈内容 / 诊断报告 / 战略方案（在 Ome365 数据仓，不在本仓）
- 个人 Journal / Memory / Growth 状态
- 租户品牌文案（作者自用 live 配置里的真实品牌）
- TicNote 自动化里 **作者专属** 的关键词逻辑（通用清洗规则可以改）

## 代码风格

- **Python**：PEP 8，字符串优先双引号，避免引入 black/isort 作为强制（作者自用格式）
- **JavaScript**：2 空格缩进，`const` > `let`，无分号风格已统一
- **不要** 无缘无故重排 import / 加 type hints / 加 docstring 到你没改的代码里（"只改说的那个地方"）

## License

Ome365 ships under the **MIT License** today (`./LICENSE`). The project is moving toward a **dual-licensing model** to defend against hyperscaler appropriation:

- **OSS main**: MIT → AGPLv3 (target migration ahead of v1.1)
- **Enterprise modules** (PG+RLS / FinOps / SOC2 / decision-distillation UI / audit): planned **BSL 1.1** (4-year automatic transition to Apache 2.0)

By contributing, you agree your code may be relicensed under either OSS or Enterprise tier as the dual model rolls out — this is standard for OSS projects with commercial back-ends (Sentry / GitLab / Elastic / MongoDB).

When the migration happens, contributors will be given 14-day notice and may opt to withdraw their code if they disagree.

## 90-day Roadmap

See [README.md#roadmap](./README.md) for the public 90-day plan. Headline items:

- **Hike v2 alpha** (D+1 ~ D+6 · 2026-05-14 ~ 2026-05-19): schema v0.2 + L2 Event + L4 Cognition + L6 Swarm
- **PG+RLS** (D+1 ~ D+3): import `ome-server` schema · multi-tenant e2e
- **A2A adapter + Signed Agent Card** (D+5 ~ D+12): `mindos.protocol.a2a` interop
- **MemoryBench public leaderboard** (D+5 ~ D+8): HuggingFace Spaces · LoCoMo benchmark

## Issue triage labels

We label issues automatically (Claude AI Reviewer GitHub Action triages on file). The label vocabulary:

- **Priority**: `p0` (security/data-loss) · `p1` (regression/major-feature) · `p2` (nice-to-have)
- **Type**: `bug` · `feature` · `docs` · `question` · `discussion`
- **Area**: `area:hike` · `area:cockpit` · `area:share` · `area:auth` · `area:ticnote` · `area:plan` · `area:memory` · `area:mcp` · `area:cognition-loop`
- **Status**: `good-first-issue` · `help-wanted` · `wontfix` · `needs-info` · `needs-triage`

## Contact

- **GitHub Issues**: https://github.com/wyonliu/Ome365/issues
- **GitHub Discussions** (preferred for Q&A): https://github.com/wyonliu/Ome365/discussions
- **Security** (private): use [GH Security Advisories](https://github.com/wyonliu/Ome365/security/advisories/new) — see [`SECURITY.md`](.github/SECURITY.md)
- **Author**: [@wyonliu](https://github.com/wyonliu)
