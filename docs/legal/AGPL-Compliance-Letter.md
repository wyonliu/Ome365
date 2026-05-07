# AGPLv3 Compliance Letter (for Enterprise Legal Review)

> Audience: Enterprise legal / compliance / IT-security teams reviewing whether to deploy Ome365 internally.
>
> ⚠️ Ome365 currently ships under **MIT License**. This letter documents the planned migration to AGPLv3 + BSL 1.1 ahead of v1.1, and addresses common AGPL concerns from enterprise counsel (especially in 央企 / regulated industries / legal departments unfamiliar with copyleft).

---

## TL;DR for legal review

1. **Internal use is unrestricted**: AGPLv3 has the same internal-use freedoms as Apache 2.0. You can deploy, modify, and use Ome365 inside your enterprise without triggering any source-disclosure obligation.

2. **The "network use" trigger applies only when you offer Ome365-derived service to *external* users over a network**: customers, partners, public APIs. It does NOT apply to internal employees of your enterprise.

3. **Modifications stay private as long as you don't redistribute**: forking Ome365 internally and customizing it for your business does not trigger AGPL distribution obligations.

4. **Enterprise modules use BSL 1.1**: PG+RLS / FinOps / SOC2 / decision-distillation UI / audit middleware are licensed under Business Source License 1.1, which automatically converts to Apache 2.0 after 4 years. BSL prohibits offering Ome365 as a competing managed SaaS for 4 years; otherwise grants Apache-2.0-equivalent freedoms.

---

## 1. License Layer Map

| Layer / Module | License | Internal Use | Modification | Redistribution |
|:---|:---:|:---:|:---:|:---:|
| Ome365 OSS main (`server.py`, `app.js`, `share_*.py`, ...) | **AGPLv3** (target migration) | ✅ unrestricted | ✅ unrestricted | ✅ with source + AGPL preserved |
| Ome365 Enterprise modules (PG+RLS, FinOps, SOC2, audit, decision-distillation UI) | **BSL 1.1** (4-year auto-Apache) | ✅ unrestricted | ✅ unrestricted | ⚠️ except offering competing managed SaaS for 4 years |
| Mindos / Ome / `mindos.protocol.*` | **Apache 2.0** | ✅ unrestricted | ✅ unrestricted | ✅ unrestricted |
| MemoryBench / industry templates / docs | **Apache 2.0** | ✅ unrestricted | ✅ unrestricted | ✅ unrestricted |
| Frontend dependencies (Vue / marked / force-graph) | their own (MIT/BSD) | ✅ unrestricted | ✅ unrestricted | ✅ unrestricted |

---

## 2. AGPLv3 Internal-Use Analysis

### What AGPL requires vs. doesn't

✅ **AGPLv3 does NOT require source disclosure for**:
- Running an unmodified copy of Ome365 inside your firewall
- Running a modified copy inside your firewall (no external "network use")
- Sharing modified binaries with subsidiaries / sister entities under the same legal control
- Using AGPLv3 software to process internal company data
- Internal employees (even via VPN / web portal) using the service — they are within your "user community"

⚠️ **AGPLv3 DOES require source disclosure when**:
- You offer Ome365-derived service over a network to external parties (e.g. allow customers to log in)
- You distribute modified binaries to third parties (vendors, partners, customers)
- The disclosed source must include all your modifications, also under AGPLv3

### How this maps to common enterprise scenarios

| Scenario | AGPL impact | Action required |
|:---|:---|:---|
| Deploy Ome365 internally for HR/CTO use | None | None |
| Customize tenant_config for company branding | None | None |
| Add internal Python connectors | None | Source kept in your private fork |
| Allow employees in 5 BUs to use Ome365 | None (employees ≠ external) | None |
| Allow contractors with company email to use | None (within your user community) | None |
| Open Ome365 to customers as portal / SaaS | **Triggers AGPL** | Disclose source under AGPLv3 |
| Sell modified Ome365 as competing SaaS | **Both AGPL + BSL 1.1 trigger** | Switch to commercial license OR comply with both |

---

## 3. Why AGPLv3 Over MIT/Apache (Strategic Rationale)

**To prevent hyperscaler appropriation**: Without copyleft, AWS / 阿里云 / Azure can fork Ome365, host it as a managed SaaS, and capture the user community without giving back. AGPLv3 ensures any network-exposed derivative must publish source, removing the economic incentive for capture.

**Examples in industry**:
- **MongoDB → SSPL**: MongoDB Inc. moved from AGPL to SSPL in 2018 after AWS launched DocumentDB (a paid MongoDB-compatible service)
- **Elastic → Elastic License + SSPL**: Same story · AWS forked Elasticsearch as OpenSearch
- **Sentry → BSL → Apache**: Functional Source License model where source is open but commercial competition restricted for 3 years

Ome365 chose **AGPLv3 + BSL 1.1** as the gentler version: AGPLv3 is OSI-approved and FSF-recommended; BSL 1.1 has automatic conversion to Apache 2.0 after 4 years.

---

## 4. Common Enterprise Concerns & Responses

> **"AGPL will infect our entire codebase."**

False. AGPL applies to derivative works of Ome365 only. Calling Ome365 from your code (REST API, MCP, A2A) does NOT make your code AGPL. The "viral" concern arises only if you:
- Statically link AGPL code into your own binary
- Modify Ome365 source and redistribute the modification

> **"We can't audit AGPL code."**

You can. AGPLv3 grants the same audit rights as MIT/Apache. The license affects redistribution, not inspection. Your security team has full read access to all `.app/*.py` and `.app/static/app.js`.

> **"AGPL forces us to open-source our customer data."**

False. AGPL governs source code, not data. Your customer data, configuration, and business logic remain entirely yours. Only modifications to Ome365's own source code would be subject to AGPL disclosure if you re-host externally.

> **"We need a commercial license for safety."**

For peace of mind, the Ome365 Enterprise tier (BSL 1.1) provides commercial-grade indemnification. Contact the maintainers for terms. You can self-host the AGPLv3 OSS tier indefinitely; commercial licenses are optional.

---

## 5. Recommended Internal Process

For enterprises evaluating Ome365:

1. **Read both `LICENSE` and `LICENSE-Enterprise.md`** (when present) carefully
2. **Identify which modules you need**: OSS-only (free/AGPL) vs Enterprise (BSL/commercial)
3. **Document your deployment topology**: internal-only vs network-exposed-to-external-users
4. **Internal AGPL training**: 1-page brief for your dev team on do's/don'ts (template available on request)
5. **Audit modifications quarterly**: maintain `MODIFICATIONS.md` listing all changes you made (good practice regardless of license)
6. **Subscribe to security advisories** (`SECURITY.md` in repo)

---

## 6. References

- AGPLv3 full text: <https://www.gnu.org/licenses/agpl-3.0.html>
- BSL 1.1 full text: <https://mariadb.com/bsl11/>
- FSF AGPL FAQ: <https://www.gnu.org/licenses/gpl-faq.html#AGPLv3InteractingRemotely>
- OSI Open Source Definition: <https://opensource.org/osd>
- Linux Foundation guide on copyleft compliance: <https://www.linuxfoundation.org/research/the-2023-state-of-open-source>

---

## 7. Contact

Questions specific to your jurisdiction or deployment: open a GitHub Discussion at <https://github.com/wyonliu/Ome365/discussions>.

For confidential enterprise inquiries (commercial license terms, indemnification): contact via [SECURITY.md private channel](../../.github/SECURITY.md).

---

> *This letter is a starting point. Always engage your own counsel for binding legal advice.*
