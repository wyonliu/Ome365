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

## License posture

Ome365 currently ships under **MIT License** (see top-level `./LICENSE`).

The project's planned migration ahead of v1.1 is a dual-tier model:

- **OSS main**: AGPLv3 (defends against hyperscaler appropriation)
- **Enterprise modules** (PG+RLS / FinOps / SOC2 / decision-distillation UI / audit): BSL 1.1 (4-year auto-conversion to Apache 2.0)

See [`AGPL-Compliance-Letter.md`](./AGPL-Compliance-Letter.md) for the full rationale and how this affects internal enterprise deployments (spoiler: AGPL doesn't restrict internal use).

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
