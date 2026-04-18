# Changelog

## v0.9.7 — 零摩擦安装 + 多租户隔离加固 (2026-04-18)

**一键装 / 一键起**
- 新增 `install.sh`：`curl -fsSL https://raw.githubusercontent.com/wyonliu/Ome365/main/install.sh | sh` 远程一行装完
- 新增 `./ome365` 极简启动器（Python 单文件，零第三方依赖）
  - `./ome365` — 首跑自动装依赖、复制 `.env`、起服务、开浏览器
  - `./ome365 --port 8080` / `--no-open` / `--setup`
  - `./ome365 doctor` — 自检依赖 / 端口 / tenant 配置
  - `./ome365 setup` — 转交 `setup.sh` 向导（family / demo / enterprise）
- README 改用 `./ome365` 作为首选路径，`setup.sh` / Docker 降为"其它场景"

**多租户 HTTP 隔离**
- 修 `/t/{tid}/...` path-prefix 没剥前缀 → 请求落到 `default` 租户的 bug
- `AuthMiddleware` 解析 tenant 后缓存到 `request.state.tenant_id`，`resolve_tenant_id()` 优先读缓存（路径剥掉后不会再误解析）
- `basic_provider` / `magic_link_provider` 补上跨租户 session 拒绝逻辑（`u.tenant_id != self.tenant_id → None`），与 OIDC / Wecom 对齐

**测试**
- E2E 从 75 扩至 **110 项**，新增 6 套：
  - `suite_session_gc` ×5 — SQLite session TTL / 撤销 / 懒 GC
  - `suite_cookie_secure_header` ×3 — Secure flag 默认开 / `OME365_COOKIE_SECURE=0` 覆写 / HttpOnly
  - `suite_http_multitenant` ×14 — 真实起 server，`$OME365_HOME/tenants/{acme,globex}/` 双租户，验证 header / subdomain / path-prefix 三种路由 + 跨租户 cookie 拒绝
  - `suite_http_magic` ×5 — Magic Link 真链路（`OME365_MAGIC_LINK_SINK_FILE` sink + `safe_next_url` 开放跳转防御）
  - `suite_http_oidc` ×4 — stdlib 起 Mock IdP（OIDC discovery / JWKS / Authorization Code + PKCE）
  - `suite_cli_ome365` ×4 — `./ome365` 冒烟（启动 / 端口释放 / `--no-open` / `doctor`）
- CI：`scripts/test_multitenant_e2e.py` 110 / 110 绿

**修掉的坑**
- macOS / BSD 端口 TIME_WAIT 让 CLI 重启立挂 → `SO_REUSEADDR`
- 系统代理截 127.0.0.1 OIDC mock → `NO_PROXY=localhost,127.0.0.1`
- bash UTF-8 全角括号邻接变量名 → `${VAR}` 花括号包住（install.sh）

## v0.9.6 — AuthProvider 抽象 + 一键部署向导 (2026-04-18)

- none / basic / magic_link / oidc / wecom 5 种 auth provider
- SQLite session store（可撤销 / TTL / 懒 GC）
- `./setup.sh` 交互向导：solo / family / demo / enterprise 四场景
- Docker compose profile
- 29 项 E2E 全绿

## v0.9.5 — 完全多租户抽象 (2026-04-18)

- 去业务耦合：模版占位符替换真实租户名
- tenant_config 三件套（live / sample / fallback）
- 4 条 cockpit 路由跨租户可用
- 默认主题改回通用 `light`

## v0.9.4 — 同事可用性 + 数据仓重构 (2026-04-17)

- requirements / .env.example / mcp / share / hook / PORT 补齐
- vault 根目录 + TicNote 归位，53 访谈零破坏

## v0.9.3 — 隐私清理事件 (2026-04-17)

- 47 项 PII 清理，filter-repo B 方案
- 双仓重构：`Ome365-git`（源码）/ `Ome365`（数据 vault）

## v0.9 — Enterprise Entity Graph (2026-04)

- 企业实体图一级能力
- ASR / RAG / Memory / 驾舱共用事实源

## v0.8 — AI 智能速记

见 README 展开项。
