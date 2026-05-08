# Business Source License 1.1 — End User License Agreement (Template)

> **🔄 Status (2026-05-08)**: Ome365 v1.0 ships under **Apache License 2.0** single-license. This BSL 1.1 template is **reserved for v1.1+ enterprise track** if/when Ome365 introduces a separate commercial Enterprise tier (PG+RLS / FinOps / decision-distillation UI / SOC2 / audit modules). HashiCorp pattern: BSL → 4-year auto-Apache for Enterprise modules only · **OSS main always Apache 2.0**.

> ⚠️ This is a **template** for the planned Ome365 Enterprise modules. The current Ome365 release ships under MIT (`./LICENSE`); this document describes the license that will apply to specific Enterprise-only modules (PG+RLS / FinOps / decision-distillation UI / SOC2 / audit) once that tier is published.
>
> Aligned with: BSL 1.1 (MariaDB Corporation Ab) · pattern used by Sentry / GitLab / CockroachDB / Couchbase / Materialize.

---

## License grant header (file-level annotation)

Every Enterprise-tier source file will carry this header:

```
Licensed under the Business Source License 1.1 (the "License").
You may not use this file except in compliance with the License.
You may obtain a copy of the License at:
https://github.com/wyonliu/Ome365/blob/main/LICENSE-Enterprise

Change Date:    2030-05-13
Change License: Apache License 2.0
```

**What this means**:
- The file is source-available today (you can read, modify, and use it under restrictions below)
- On the Change Date (4 years after publication), the license **automatically converts** to Apache 2.0 — fully open source

---

## License terms (BSL 1.1 standardized)

### License Grant

Licensor: **[OME365 MAINTAINERS / LEGAL ENTITY]**

The Licensor hereby grants you the right to copy, modify, create derivative works, redistribute, and make non-production use of the Licensed Work. The Licensor may make an Additional Use Grant, above, permitting limited production use.

### Additional Use Grant

You may make production use of the Licensed Work, **provided that** you do not provide a commercial service to third parties that competes with the Licensor by:

- Offering Ome365 (or a derivative work) as a hosted/managed service for which fees are charged
- Marketing such a service to entities other than your own organization or its subsidiaries

You may use the Licensed Work in production for your own internal business operations, including providing services to your own employees, contractors, or affiliated entities.

### Change Date

**Four (4) years from the date the Licensed Work is publicly available** under this License (which we'll set per Enterprise module · header `Change Date` field).

### Change License

Apache License, Version 2.0 (<http://www.apache.org/licenses/LICENSE-2.0>).

### Termination

If you violate the license terms, your rights under this License terminate automatically. To reinstate, you must:
- Cure the violation within 30 days of becoming aware
- Provide written notice to the Licensor
- Pay any commercial license fees if applicable

### No Warranty

THE LICENSED WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.

### Notice

If you redistribute the Licensed Work in source or binary form, you must include:
- The complete License text (this document)
- Acknowledgment of original Licensor
- Notification to recipients of license terms

---

## What you can do (BSL 1.1 plain English)

| Use case | Allowed? |
|:---|:---:|
| Read, study, audit the source code | ✅ |
| Modify for your own internal use | ✅ |
| Run modified Ome365 Enterprise modules in production for your company | ✅ |
| Share modifications back as PRs to the upstream project | ✅ |
| Distribute Ome365 Enterprise to your own employees/contractors | ✅ |
| Use for academic research / personal exploration | ✅ |
| Embed in your internal tools without paying anything | ✅ |
| **Offer Ome365 Enterprise as a managed SaaS for fees** | ❌ (until Change Date) |
| **Compete with Ome365 maintainers' commercial offering** | ❌ (until Change Date) |
| Use after Change Date under Apache 2.0 | ✅ unrestricted |

---

## When you might need a commercial license

Contact the Licensor for a commercial license if you want to:

- Offer Ome365 Enterprise modules as a managed SaaS to third parties
- Embed Ome365 Enterprise in a product you sell as a service competitor
- Get formal indemnification, SLA, dedicated support
- Use OEM-style branding rights

Contact: GitHub Issues with label `enterprise-license-inquiry` or via private channel listed in `SECURITY.md`.

---

## Compatibility with OSS Ome365 (AGPLv3 main)

Ome365 ships in **two tiers**:

1. **OSS main** (`AGPLv3`): all functionality except Enterprise modules · self-host indefinitely · no commercial restrictions for non-SaaS
2. **Enterprise modules** (`BSL 1.1` → Apache 2.0 after 4 years): PG+RLS · FinOps · audit middleware · decision-distillation UI · SOC2

You can run **OSS main alone** without the Enterprise modules — full functionality minus enterprise-grade scaling/auditing/cost-controls. You can pull in Enterprise modules under BSL 1.1 for free for non-competing internal use.

---

## What is NOT under BSL

The following Ome365 components remain under their respective licenses, never BSL:

- **OSS main** (`AGPLv3`): `.app/server.py` core · `.app/static/app.js` UI · `share_*.py` · `entity_registry.py` · `tenant/auth/*`
- **Mindos / Ome / `mindos.protocol.*`** (`Apache 2.0`): SDK + protocol adapters
- **MemoryBench** (`Apache 2.0`): public benchmark
- **5 industry templates** (`Apache 2.0`): `docs/hike-templates/{manufacturing,insurance,...}`
- **Frontend dependencies** (their own licenses): Vue 3 (MIT) · marked (MIT) · force-graph (MIT)

The Enterprise tier is opt-in and has clear file-level annotations.

---

## FAQ

### Q: Can my legal team trust BSL 1.1?

Yes. BSL 1.1 is a published, well-understood license used by:
- **MariaDB Corporation** (the originators)
- **Sentry** (error tracking)
- **CockroachDB** (distributed SQL)
- **Couchbase** (NoSQL)
- **HashiCorp Terraform** (recently)

Many enterprise legal teams have BSL precedent. The 4-year auto-Apache provision provides a clear "open source eventually" guarantee.

### Q: What happens after the Change Date?

The file becomes Apache 2.0 — fully open source, no restrictions. You can:
- Fork it without limits
- Build commercial products on it
- Combine with any other code
- Redistribute under any compatible license

### Q: Why not just use AGPLv3 for everything?

AGPLv3 is harder to swallow for some enterprise legal teams (esp. in 央企, regulated industries). BSL 1.1 is friendlier:
- Source-available
- Internal use unrestricted
- Auto-conversion to Apache 2.0 after 4 years

This is a deliberate compromise to maximize adoption while still defending against hyperscaler appropriation in the short term.

### Q: I'm a startup, can I use Enterprise modules?

Yes. BSL 1.1 only restricts you from offering Ome365 Enterprise as a competing managed SaaS. Building your own product that uses Ome365 internally is fine.

---

## References

- BSL 1.1 official text: <https://mariadb.com/bsl11/>
- MariaDB Foundation explanation: <https://mariadb.com/about/business-source-license/>
- Sentry on choosing BSL: <https://blog.sentry.io/2019/11/06/relicensing-sentry/>
- HashiCorp on BSL: <https://www.hashicorp.com/license-faq>

---

> *This template will become a binding `LICENSE-Enterprise.md` once Ome365 publishes the Enterprise tier. Today, the entire Ome365 codebase ships under MIT (`./LICENSE`).*
