# Ome365 · 企业部署

本文档给出企业场景下的部署姿势：多租户、SSO 登录、session 持久化、反向代理。
如果你是单人 / 家庭用户，用项目根 `./setup.sh` 交互式向导就够了，不需要读这里。

---

## 场景判定

| 你是… | 选哪个 | 对应配置 |
|------|-------|---------|
| 一个人自用 | **solo** | 无认证；`tenant_config.sample.json` 即可 |
| 家里几口人共享 / 小工作室 | **family** | basic 密码 or magic_link |
| 小公司 / 一个部门 | **enterprise (single-tenant)** | OIDC 或企微 SSO |
| 多家公司 / 多部门隔离 | **enterprise (multi-tenant)** | 迁移到多租户布局 + SSO |

---

## 一、认证 Provider 选择

| Provider | 适合 | 配置依赖 |
|----------|-----|---------|
| `none` | 单人 / 内网 / 本地 dev | 无 |
| `basic` | 公开 demo / 家庭 | `users[].password_hash`（argon2/bcrypt/sha256） |
| `magic_link` | 家庭 / 小团队无需记密码 | SMTP 账号 |
| `oidc` | Okta / Azure AD / Auth0 / Keycloak / 企业自建 OIDC | `issuer` / `client_id` / `client_secret` |
| `wecom` | 企业微信自建应用（任意企微生态企业） | `corp_id` / `agent_id` / `secret` |

把选择写进 `$OME365_HOME/tenants/{tid}/tenant_config.json` 的 `auth.provider`。
或用 env var `OME365_AUTH_PROVIDER=xxx` 临时覆盖（调试用）。

### OIDC 示例（Okta / Azure AD / Keycloak / 企业自建）

```json
{
  "auth": {
    "provider": "oidc",
    "protect_api": true,
    "providers": {
      "oidc": {
        "issuer": "https://sso.your-company.com",
        "client_id": "ome365",
        "client_secret_env": "OME365_OIDC_SECRET",
        "redirect_uri": "https://ome.your-company.com/auth/oidc/callback",
        "scopes": ["openid", "profile", "email"],
        "allowed_domains": ["your-company.com"],
        "uid_claim": "preferred_username"
      }
    }
  }
}
```

`OME365_OIDC_SECRET` 放 env（`.env` / docker secret / k8s secret），**不要**写进 `tenant_config.json`。

### 企微示例

```json
{
  "auth": {
    "provider": "wecom",
    "providers": {
      "wecom": {
        "corp_id": "wwxxxxxxxxxxxxxxxx",
        "agent_id": "1000002",
        "secret_env": "OME365_WECOM_SECRET",
        "redirect_uri": "https://ome.your-company.com/auth/wecom/callback",
        "allowlist_userids": ["wyon", "alice"]
      }
    }
  }
}
```

### 一套部署 · 多家企业并存（WeCom 租户 + OIDC 租户）

Ome365 的 Auth 是 **Registry 模式**：一个部署内，每个租户挂自己的 provider，互不串门。HTTP 进来时按 `subdomain / /t/{tid} / X-Ome-Tenant header` 解租户，再取对应 provider 认证。

下面用 `acme`（WeCom 企微扫码）和 `globex`（标准 OIDC）两个占位租户演示——替换成你自己的租户名即可。

**部署拓扑**：
```
ome.acme.com     →  tenant_id=acme    →  WecomProvider(corp_id=wwAcme...)
ome.globex.com   →  tenant_id=globex  →  OIDCProvider(issuer=https://sso.globex.com)
ome.example.com  →  tenant_id=default →  BasicProvider / NoneProvider
```

**目录布局**：
```
$OME365_HOME/
├── sessions.db            # 共享 session（每 session 绑 tenant_id，跨租户 cookie 拒认）
├── oidc_pending.db        # OIDC state/verifier 表
├── wecom_pending.db       # 企微 state 表
└── tenants/
    ├── acme/tenant_config.json      # auth.provider = wecom
    ├── globex/tenant_config.json    # auth.provider = oidc
    └── default/tenant_config.json   # auth.provider = basic
```

**各租户配置示例**（放各自 `tenants/{tid}/tenant_config.json`）：

```jsonc
// tenants/acme/tenant_config.json
{
  "_tenant_id": "acme",
  "brand": { "cockpit_title": "Acme · AI Cockpit" },
  "auth": {
    "provider": "wecom",
    "protect_api": true,
    "providers": {
      "wecom": {
        "corp_id": "wwAcmeCorpId",
        "agent_id": "1000002",
        "secret_env": "OME365_WECOM_ACME_SECRET",
        "redirect_uri": "https://ome.acme.com/auth/wecom/callback",
        "allowlist_userids": ["alice", "bob"]
      }
    }
  }
}
```

```jsonc
// tenants/globex/tenant_config.json
{
  "_tenant_id": "globex",
  "brand": { "cockpit_title": "Globex · AI Navigator" },
  "auth": {
    "provider": "oidc",
    "protect_api": true,
    "providers": {
      "oidc": {
        "issuer": "https://sso.globex.com",
        "client_id": "ome365",
        "client_secret_env": "OME365_OIDC_GLOBEX_SECRET",
        "redirect_uri": "https://ome.globex.com/auth/oidc/callback",
        "scopes": ["openid", "profile", "email"],
        "allowed_domains": ["globex.com"],
        "uid_claim": "preferred_username"
      }
    }
  }
}
```

**env**（`.env` / docker secret / k8s secret）：
```bash
OME365_WECOM_ACME_SECRET=xxx
OME365_OIDC_GLOBEX_SECRET=yyy
# OME365_COOKIE_SECURE 默认 1；仅本地 http dev 需要设 0
# 可选：按租户临时覆盖 provider
# OME365_AUTH_PROVIDER_ACME=wecom
```

**隔离保证**：
- `acme` 企微扫出来的 userid 只会写进 acme session；中间件每请求都会 `user.tenant_id == ctx.tenant_id` 比对，不一致就拒认。
- redirect_uri 按租户域名分开，企微/OIDC 回来天然落到对的租户。
- `state/nonce/verifier` 单次消费 + 15 分钟 TTL，防 CSRF + 重放。
- `acme` 员工把 cookie 手动复制到 `globex` 子域名，middleware 也会拒。

---

## 二、多租户（多家公司 / 多部门）

### 2.1 启用多用户模式

1. 迁移到多用户布局：
    ```bash
    python3 scripts/migrate_to_multiuser.py --dry-run   # 先看效果
    python3 scripts/migrate_to_multiuser.py             # 正式跑
    ```
   脚本会：
   - 创建 `$OME365_HOME/tenants/default/`
   - 移动 `tenant_config.json / cockpit_config.json / share_registry.json` 进去
   - 创建 `users/captain/profile.json`（`vault_path` = 原 `$OME365_VAULT`，**不搬数据**）
   - 原路径保留软链接，老路径照样能跑（legacy 兼容）
2. 验证：
    ```bash
    curl http://localhost:3650/api/_ctx/healthcheck
    # 看到 "is_multi_user": true 就对了
    ```
3. 回滚（万一）：
    ```bash
    python3 scripts/migrate_to_multiuser.py --rollback
    ```

### 2.2 加租户

每加一家公司 = 加一个 tenant dir：

```bash
mkdir -p $OME365_HOME/tenants/acme/users/alice
cat > $OME365_HOME/tenants/acme/tenant_config.json <<EOF
{
  "_tenant_id": "acme",
  "brand": {
    "cockpit_title": "Acme · AI Navigator",
    "theme": "light",
    "logo": "/brand/acme.png"
  },
  "auth": {
    "provider": "wecom",
    ...
  },
  "cockpit": {
    "dir_name": "Cockpit-Acme",
    "config_file": "cockpit_config.json"
  }
}
EOF

# 用户 profile 指向各自 vault
cat > $OME365_HOME/tenants/acme/users/alice/profile.json <<EOF
{
  "uid": "alice",
  "email": "alice@acme.com",
  "display_name": "Alice",
  "vault_path": "/data/vaults/acme/alice",
  "roles": ["admin"]
}
EOF
```

> vault 可以在任何位置（NFS / S3fs / 本地盘），profile.json 里用绝对路径指过去。

---

## 三、Session 持久化

默认 session 存 `$OME365_HOME/sessions.db`（SQLite）。单节点够用。

**多节点 / K8s 部署**：把 `$OME365_HOME` 挂在共享卷（NFS/EFS），或者替换 `SessionStore` 实现为 Redis/PostgreSQL。接口只有 7 个方法（`create/get/get_user/delete/delete_for_user/gc/count`），换后端改 30 行。

---

## 四、反向代理（nginx 样例）

```nginx
server {
  listen 443 ssl http2;
  server_name ome.your-company.com;

  ssl_certificate      /etc/letsencrypt/live/ome/fullchain.pem;
  ssl_certificate_key  /etc/letsencrypt/live/ome/privkey.pem;

  client_max_body_size 200m;

  location / {
    proxy_pass         http://127.0.0.1:3650;
    proxy_http_version 1.1;
    proxy_set_header   Host $host;
    proxy_set_header   X-Real-IP $remote_addr;
    proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;

    # cookie 需要 Secure flag
    proxy_cookie_flags ome365_sid secure samesite=lax;
  }
}
```

Cookie `Secure` 标志默认 on，生产 HTTPS 无需额外配置。本地 `http://localhost` dev 如果遇到 "登录后 /api/auth/me 仍返回未登录"，设 `OME365_COOKIE_SECURE=0` 即可（浏览器不回传 Secure cookie 到明文连接）。

---

## 五、Docker Compose（生产模板）

```yaml
services:
  ome365:
    image: ome365:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:3650:3650"  # 只绑 localhost，外层 nginx 反代
    volumes:
      - /srv/ome365/data:/data
      - /srv/ome365/home:/home/.ome365
    env_file: /etc/ome365/.env
    environment:
      OME365_COOKIE_SECURE: "1"
    healthcheck:
      test: ["CMD","python3","-c","import urllib.request as u; u.urlopen('http://localhost:3650/api/auth/healthcheck',timeout=3).read()"]
      interval: 30s
      timeout: 5s
      retries: 3
```

备份策略：`/srv/ome365/data` 每晚 rsync 到异机；`/srv/ome365/home/sessions.db` 周备份即可（丢了只是要所有用户重新登录）。

---

## 六、健康检查端点

| 端点 | 作用 |
|------|------|
| `GET /api/auth/healthcheck` | provider 状态 + 配置 issues + 当前 session 数 |
| `GET /api/_ctx/healthcheck` | tenant/user 拓扑自检 |
| `GET /api/tenant/config` | 当前租户品牌/prompts（前端启动拉） |

k8s readiness/liveness 探 `/api/auth/healthcheck` 即可。

---

## 七、CI / 自检

```bash
# 跑 29 项验收测试，涵盖 auth / session / migrate / http E2E
python3 scripts/test_multitenant_e2e.py

# 只跑某一组
python3 scripts/test_multitenant_e2e.py --only ctx,session,providers
```

发布前门禁：`test_multitenant_e2e.py` 必须全绿。
