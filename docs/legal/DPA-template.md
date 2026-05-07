# Data Processing Agreement (DPA) · Template

> ⚠️ This is a **template** for self-host operators of Ome365 to use when offering services to end-users (e.g. employees of an enterprise tenant). It is provided as a starting point and **does not constitute legal advice**. Have your counsel review and adapt to your jurisdiction.
>
> Aligns with: GDPR Art. 28 · PIPL §38/§40 · CCPA Service Provider Addendum · ISO 27701 · ISO 42001

---

## Parties

This Data Processing Agreement (this "**DPA**") is entered into between:

- **Controller**: [LEGAL ENTITY NAME] ("**Customer**" or "**Controller**")
- **Processor**: [SELF-HOST OPERATOR LEGAL NAME] ("**Operator**" or "**Processor**")

This DPA forms part of the [Master Services Agreement / Subscription Agreement] between the parties (the "**Agreement**") effective as of [DATE].

---

## 1. Purpose of Processing

The Operator processes Personal Data on behalf of the Controller solely for the purposes of:

- Providing the Ome365 enterprise AI platform (file-first knowledge management · cognition layer · share station · A2A federation)
- Delivering features explicitly contracted (e.g. Hike entity graph · multi-tenant auth · audit logging)
- Generating system-improving telemetry **only when Controller has opted in via `LLM_BACKEND` env var**

Outside of these purposes, the Operator shall not process Personal Data without the Controller's prior written instructions.

---

## 2. Sub-processors

The Operator may engage the following Sub-processors. Controller is notified at least 30 days before any addition or change.

| Sub-processor | Purpose | Location | Safeguard |
|:---|:---|:---|:---|
| [LLM Provider, e.g. DeepSeek / OpenAI / Anthropic] | Inference for AI features (only if Controller opted in via `.env`) | [Region] | Standard Contractual Clauses (SCC) + DPA in place |
| [Email Provider, e.g. Mailgun / Postmark] | Transactional email (magic-link auth · alerts) | [Region] | SCC + DPA |
| [Hosting, e.g. AWS / 阿里云 / 腾讯云] | Server hosting (only if Controller chose managed deployment) | [Region] | SCC + DPA + ISO 27001 |

Controller's written objection to a new Sub-processor will result in either: (a) a workaround that avoids the Sub-processor; or (b) Controller's right to terminate without penalty.

---

## 3. Cross-border Data Transfer

For Controllers in jurisdictions that restrict cross-border data flows:

### EU/EEA (GDPR Art. 46-49)
- Standard Contractual Clauses (SCC · 2021/914/EU) apply between Controller and any non-EU Sub-processor
- Operator maintains Transfer Impact Assessment (TIA) documents

### China (PIPL §38-§43)
- For Personal Information of subjects in mainland China:
  - **Default**: All processing within mainland China · `LLM_BACKEND=local` (Ollama)
  - **Cross-border opt-in**: Requires CAC Standard Contract filing + Personal Information Impact Assessment (PIA) — Operator provides PIA template
  - Sensitive PI (financial, health, location, biometric, minor under 14): additional consent required

### Other jurisdictions
- Adequate decision · binding corporate rules · or explicit user consent — case-by-case

---

## 4. Data Subject Rights SLA

The Operator commits to assisting Controller in fulfilling Data Subject Rights within these timeframes:

| Right | Operator response time |
|:---|:---|
| Access (Art. 15 GDPR / §45 PIPL) | 5 business days · provides JSON export via `/api/tenant/{id}/export` |
| Rectification (Art. 16 / §46) | 3 business days · UI-driven correction |
| Erasure / "right to be forgotten" (Art. 17 / §47) | 7 business days · `/api/tenant/{id}/erasure` purges from L0 markdown + L1-L4 caches + 90-day soft-delete then hard delete |
| Portability (Art. 20 / §45) | 7 business days · markdown vault + JSON config exported in standard formats |
| Objection / restriction (Art. 21) | 3 business days |
| Automated decision opt-out (Art. 22 / §24 PIPL) | Immediate · `not_to_be_profiled: true` field in user record disables Hike person-profile aggregation |

---

## 5. Security Measures

The Operator implements at minimum:

- **Encryption at rest**: master.key + Fernet (AES-128-CBC + HMAC-SHA256) for share-station passwords · TDE for PG when Enterprise tier
- **Encryption in transit**: TLS 1.2+ for all HTTP endpoints · enforced in `infra/nginx-ome365.conf` template
- **Authentication**: argon2id password hashing (PHC string format) · 5 AuthProvider modes (none / basic / magic_link / oidc / wecom)
- **Access control**: Field-level RBAC + 3-tier scope (tenant/region/user) for Hike · OAuth2/OIDC for cross-domain
- **Audit logging**: every share-station access · failed login · admin action recorded with timestamp + IP + user
- **Backup & DR**: RPO 1h / RTO 4h · git history versioning + rsync vault + pg_dump cross-region
- **Vulnerability management**: pre-commit `scan_pii.py` 4-layer · GitHub Dependabot · quarterly pen-test
- **Personnel**: Operator employees with access pass background check + sign confidentiality agreement

---

## 6. Breach Notification

Upon discovery of a Personal Data breach, Operator will:

- Notify Controller **within 72 hours** of becoming aware (GDPR Art. 33 timeline)
- Provide: nature of breach · categories of data affected · approximate number of subjects · likely consequences · remediation taken
- Cooperate with Controller in any required notification to supervisory authorities or data subjects

---

## 7. Audit Rights

Controller may, no more than **once per 12 months** (or upon material concern), request:

- Self-audit questionnaire response within 30 days
- Third-party audit report (SOC 2 Type II · ISO 27001) if available
- On-site inspection with 30-day notice (subject to confidentiality and Operator's reasonable security policies)

---

## 8. Termination & Data Return

Upon termination of the Agreement:

- **Within 30 days**: Operator returns all Personal Data to Controller in standard formats (markdown vault + JSON exports)
- **Within 90 days after return confirmation**: Operator securely deletes all copies, including backups (or anonymizes per documented schema)
- **Audit certification**: Operator provides written certification of deletion within 7 days of completion
- **Exception**: Where retention is legally required (e.g. tax records · 7-year financial obligations), Operator retains only what is mandated and returns/deletes the rest

---

## 9. Liability

Liability for breach of this DPA is governed by the indemnification and limitation-of-liability provisions in the Agreement.

---

## 10. Changes & Notice

Operator may update this DPA to reflect legal/regulatory changes; material changes notified at least 30 days in advance. Controller has the right to terminate without penalty if it does not accept material changes.

---

**Signed**:

For Customer: ___________________ Name · Title · Date

For Operator: ___________________ Name · Title · Date

---

## Annex A: Technical & Organizational Measures

- Section 5 above + `docs/operations/dr-runbook.md` (when published)
- ISO 27001 / SOC 2 control mapping (when applicable)
- ISO 42001 AI Management System control mapping (when applicable)
