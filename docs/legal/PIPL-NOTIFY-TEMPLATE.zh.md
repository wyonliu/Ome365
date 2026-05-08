# PIPL 第 24 条自动决策告知模板（中国 region · v1.1 部署必交付）

> **适用范围**：tenant_config.region=cn 时·首次启用 `/api/eval/*` 必须给每位 member
> 一次性签字告知·依据《中华人民共和国个人信息保护法》第 13 / 14 / 24 条。
>
> **签字后**：将 `member_id → ack_date` 写入 `tenant_config.pipl_notify_acknowledged_by`。
> **未签字**：API 返 412 Precondition Required + 告知 link。

---

## 模板（直接打印 / 邮件群发）

亲爱的同事：

公司部署的 Ome365 系统会基于您在 vault 中的工作活动数据·派生 7 维评分（D1-D7）·**仅用于资源分配参考与人才识别·不作为绩效考核或人事决策的唯一依据**。

依据《中华人民共和国个人信息保护法》（PIPL）：

### 一、处理目的（§13）
- 团队资源分配优化
- AI 工作流效能识别
- 跨 BU 协作机会发现

### 二、处理方式（§13）
- 基于 markdown 文件 grep + 派生计算
- **派生评分永不写入磁盘**·实时即算即弃
- 原始数据存储在 `vault/` · 您与团队管理员共同管理
- LLM 调用 trace 记录在 `Trace/<date>.jsonl` · append-only · 您可查阅

### 三、处理种类（§13）
- 您写入 `Decisions/` 的决策档（owner 字段含您 id）
- 您调用 LLM 的 trace 流水（actor 字段含您 id）
- 您发布的 Skills（author 字段含您 id）
- **不处理**：私人通讯 / 健康信息 / 金融 / 宗教 / 行踪轨迹

### 四、保留期限（§13）
- vault 原始数据：由您与团队共同决定·无强制期限
- 派生评分：实时计算·不存盘
- monthly rollup：30 日后归档·原始 jsonl 可压缩

### 五、您的权利（§44-§47）
- **知情权**：随时调用 `/api/eval/member/me?window=30` 查阅自己的评分明细
- **拒绝权**（§24）：联系管理员将您加入 `tenant_config.opted_out_members` 列表·
  自该日起所有 `/api/eval/*` 对您返 403·**不影响您正常使用其他功能**
- **删除权**（§47）：删除 `vault/Trace/<date>.jsonl` 中含您 actor=<your_id> 的行即不再进入派生
- **更正权**（§46）：通过修改 vault 中相关 markdown 文件实现
- **解释权**（§24）：所有评分公式开源（见 `docs/strategy/v1.1-implementation-spec.md` §一）·
  可逐字段追溯·永不黑盒

### 六、不会做什么（CEO 边界铁律）
- ❌ **不进 KPI**·不作为人事决策唯一依据
- ❌ **不公开排行榜**·不向同事展示您的评分
- ❌ **不跨 tenant 传输**·您的评分永不外泄到合作伙伴
- ❌ **不替代人类判断**·所有评分响应强制带 `human_review_required: true`

### 七、合规保障
- 部署符合 PIPL §32 信息技术处理者义务
- 评分系统通过 GDPR Art. 22 自动决策合规审查（双标准对齐）
- 跨境数据传输符合 PIPL §38（默认仅本地处理）

---

## 签字确认

我已阅读上述告知·理解 Ome365 评分系统的处理目的 / 方式 / 我的权利。

我（同意 / 不同意 · 请勾）该系统对我进行评分派生：

- [ ] **同意** · 进入 `tenant_config.pipl_notify_acknowledged_by`
- [ ] **不同意** · 进入 `tenant_config.opted_out_members`（不影响其他功能）

签字：__________   日期：__________   member_id：__________

---

## 管理员操作（部署侧）

收到签字后·更新 `vault/.ome365/eval-config.yml`：

```yaml
region: cn

pipl_notify_acknowledged_by:
  alice@acme.com: 2026-05-08
  bob@acme.com: 2026-05-09

opted_out_members:
  - charlie@acme.com    # 显式拒绝者·永返 403
```

---

**模板版本**：r1.0 · 2026-05-08
**法律审查**：依据 PIPL（2021-11-01 施行）· 适用 2026 现行版本
**Owner**：CTO 办公室 + 部署方法务
**适用版本**：Ome365 v1.1+
