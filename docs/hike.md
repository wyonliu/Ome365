# Hike · Hive Intelligence Knowledge Engine

> Ome365 王牌子项目·组织记忆 + 决策蒸馏 + 组织智能 三位一体。
>
> Hike 是 EEG（Enterprise Entity Graph·v0.1 已 ship）的演进路径名。从 v1.1 起 EEG → Hike v2 完整升级。

---

## What is Hike?

Hike turns your team's **markdown vault** into a self-learning knowledge engine.

- **Organizational memory** — every meeting, decision, and document becomes a queryable entity
- **Decision distillation** — 6-stage cognition loop converts one-time experiments into reusable principles
- **Hive intelligence** — cross-meeting person profiles, decision chains, and BU协同 signals emerge automatically

---

## v0.1 (already shipped) → v2 roadmap

### v0.1 ground truth (in production today as `EEG`)

```
.app/entity_registry.py   # entity resolution
Knowledge/entities/        # markdown source-of-truth (8 entity types)
9 endpoints                # /api/entities/*
47 ASR rules               # via skills/truthguard
26 cockpit ASR_FIXES       # via .app/cockpit_config.json
```

### v2 (D+1 ~ D+45 · alpha)

| Layer | v0.1 (EEG) | v2 upgrade |
|:---:|:---|:---|
| **L1·Entity** | 8 types · markdown SoT | + schema v0.2 fields: `parent_id` / `validity_period` / `external_ids` / `multilingual` / `disambiguation_hint` |
| **L2·Event** | (none) | 🆕 meetings / decisions / milestones / actions · `meeting_dedupe_hash` |
| **L3·Rule** | 47 ASR rules | + `persona_playbook` 7-step speaker identification |
| **L4·Cognition** | (none) | 🆕 `decision_chains` + `distilled.principles` + `reflections`（replaces standalone `DISTILL`）|
| **L5·Graph** | `entity_registry.resolve(text)` | + cross-meeting timeline + `cross_bu_signals` |
| **L6·Swarm** | (none) | 🆕 `discover → suggest → review → adopt` |

---

## Hike API (v2)

```python
from hike import HikeClient

hike = HikeClient(tenant_id=ctx.tenant_id, member_id=ctx.member_id)

# Entity recognition
hits = hike.lookup("Alice mentioned the AI cost reduction project")

# Cross-meeting person profile (RBAC + scope filtered)
profile = hike.get_person_profile("Alice", scope="bu", time_range="last_year")

# Decision chain tracing
chain = hike.get_decision_chain("AI cost reduction Q3 pilot")

# Distilled principles
principles = hike.distilled_principles(scope="property AI transformation")

# Cross-BU signals
signals = hike.detect_cross_bu_signals(threshold=0.7)
```

---

## Hybrid Storage (4 layers · re-uses ome-server v0.2.0)

| Layer | Storage | Purpose | Trigger |
|:---:|:---|:---|:---|
| **L0·Source of Truth** | YAML / markdown · git-diffable | Single source · never changes | always on |
| **L1·Fast Path** | SQLite FTS5 build artifact | `lookup` / `fix_asr` queries · O(log n) | fsnotify rebuild on file change |
| **L2·Vector** | pgvector + HNSW (Enterprise) | Semantic search / `suggest_new_terms` | Enterprise tier |
| **L3·Graph** | LightRAG / GraphRAG (on-demand) | Cross-entity reasoning | High-ACV customers |

**Iron rule**: file is SoT · SQLite/PG/vector/graph are all projections · 1k+ tenants cannot all-in single shape.

---

## 4 essential UI pages (v2)

| UI | Purpose | Role |
|:---|:---|:---|
| **Review queue** | Approve swarm-suggested candidates | admin / scope owner |
| **Distillation editor** | Edit distilled principles | scope owner / regular employee |
| **Person profile viewer** | Cross-meeting person profile | RBAC scope |
| **Decision timeline** | Decision chain timeline | scope members |

---

## 5 industry templates (cold-start · D+7 ~ D+30)

`docs/hike-templates/{manufacturing, insurance, law-firm, retail, healthcare}/` — customers can drop-in adopt without manual entity setup.

---

## 3-tier scope (RBAC × tenant)

```
tenant (e.g. "acme-corp")
  └── region (e.g. "engineering-bu" / "sales-q3-project")
       └── user (e.g. "alice@acme-corp")
```

Field-level ACL example:

```yaml
- id: term_jane_doe
  canonical: Jane Doe
  privacy: internal              # public / internal / restricted
  acl:
    public:    [canonical, role]                    # external partners
    pinned:    [canonical, role, responsibilities]  # whitelisted partners
    internal:  ALL                                  # internal employees
    restricted: []                                  # exec-only
```

---

## Why Hike (vs Glean / Mem0 / Notion)

| Need | Hike | Glean | Mem0 | Notion AI |
|:---|:---:|:---:|:---:|:---:|
| File-first markdown SoT | ✅ | ❌ SaaS-only | ❌ | ❌ |
| Self-host · own data 100% | ✅ | ❌ | ❌ | ❌ |
| Cross-meeting person profile | ✅ | ✅ | ❌ | ❌ |
| Decision distillation 6-stage | ✅ | ❌ | ❌ | ❌ |
| Cross-org A2A federation (schema-only) | ✅ | ❌ | ❌ | ❌ |
| 5-industry cold-start templates | ✅ | partial | ❌ | ❌ |
| BSL 1.1 enterprise / AGPLv3 OSS | ✅ | proprietary | proprietary | proprietary |

---

## Status

- **v0.1** — shipped 2026-04-17 as `EEG` (Enterprise Entity Graph)
- **v2 schema v0.2** — alpha 2026-05-14 ~ 2026-05-19
- **v2 L2/L4/L6 + UI** — D+1 ~ D+45
- **v2 5 industry templates** — D+7 ~ D+30
- **v2 SCIM 2.0 connector** — D+30 ~ D+60

See `Projects/Omnity/10·Ome365·顶级企业AI平台开源·全量方案·2026-05-07.md` for full roadmap.
