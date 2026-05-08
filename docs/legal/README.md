# Ome365 Legal Templates

This directory contains **template** legal documents for self-host operators of Ome365.

> ⚠️ These are **starting points**, not legal advice. Adapt to your jurisdiction and have your counsel review.

## Documents

| File | Purpose | Audience |
|:---|:---|:---|
| [`DCO.md`](./DCO.md) | Developer Certificate of Origin (contributors) | Anyone sending PRs to Ome365 |
| [`DPA-template.md`](./DPA-template.md) | Data Processing Agreement template | Self-host operators offering Ome365 to enterprise customers |
| [`AGPL-Compliance-Letter.md`](./AGPL-Compliance-Letter.md) | AGPLv3 enterprise legal review primer | Internal legal/compliance teams (especially 央企 / regulated industries) |
| [`BSL-EULA-template.md`](./BSL-EULA-template.md) | Business Source License 1.1 EULA template | Future Ome365 Enterprise tier users |

## License posture (v1.0 · 2026-05-08)

Ome365 v1.0 ships under **Apache License 2.0** (single-license · see top-level [`../../LICENSE`](../../LICENSE) and [`../../NOTICE`](../../NOTICE)).

**Why Apache 2.0 over the previously-considered AGPL+BSL dual-tier**:
- Same license as Mindos / Ome SDK / ome-server / memorybench across the Omnity matrix (one-license policy · zero confusion for contributors)
- Aligned with 2026 Chinese open-source agent ecosystem fact: DeepSeek MIT · Qwen3 Apache · Coze Apache · AgentScope Apache · ModelScope-Agent Apache (BSL has only EMQX adoption in China · and EMQX is MQTT broker not agent/knowledge tool)
- 央企/金融法务零摩擦 (vs AGPL near-zero adoption in 央企)
- HashiCorp pattern (Aug 2023 MPL → BSL): keep main Apache · switch *only Enterprise modules* to BSL **if hyperscaler appropriation becomes a real threat** post-launch

**v1.1+ enterprise track (reserved · not active in v1.0)**:
- The `AGPL-Compliance-Letter.md` and `BSL-EULA-template.md` in this directory are **templates reserved for v1.1+** when/if Ome365 introduces a separate Enterprise tier
- **OSS main will always remain Apache 2.0** — no bait-and-switch
- Enterprise modules (PG+RLS / FinOps / decision-distillation UI / SOC2 / audit) MAY adopt BSL 1.1 with 4-year auto-Apache conversion if needed

See [`AGPL-Compliance-Letter.md`](./AGPL-Compliance-Letter.md) for v1.1+ AGPL legal review (reserved · explains AGPL internal-use freedoms in case future modules adopt copyleft).

## Compliance frameworks aligned

The DPA template aligns with:

- **GDPR** Art. 28-32 (EU/EEA data subjects)
- **PIPL** §38-§47 (mainland China data subjects)
- **CCPA** Service Provider Addendum (California residents)
- **ISO 27701** Privacy Information Management
- **ISO 42001** AI Management System
- **EU AI Act** (high-risk AI system requirements when applicable)
- **SOC 2 Type II** (when Ome365 organization pursues attestation)

## Contributing improvements

These templates are versioned in git. PRs welcome to:
- Add jurisdiction-specific addendums (Brazil LGPD, Canada PIPEDA, India DPDPA, Singapore PDPA, Japan APPI)
- Translate to other languages (currently English with some Chinese terminology)
- Improve technical/organizational measures sections as Ome365 ships new security features

See [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md) for PR guidelines.

## Disclaimer

These documents:
- Are provided **AS IS** without warranty
- **Do NOT constitute legal advice**
- May not satisfy specific regulatory requirements in your jurisdiction
- Should be reviewed by qualified legal counsel before use
- Are not a substitute for proper data protection program implementation
