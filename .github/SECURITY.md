# Security Policy

Ome365 takes security seriously. Thanks for helping keep users safe.

## Supported versions

We patch security issues on the latest `main` branch and the most recent tagged release. Older releases are best-effort.

| Version | Supported |
|:---|:---:|
| `main` (latest) | ✅ |
| Latest tagged `v1.x` | ✅ |
| Earlier `v0.x` | ⚠️ best-effort |

## Reporting a vulnerability

**Please do not file a public GitHub issue for security problems.**

Use one of these private channels:

1. **GitHub Security Advisories** (preferred): [github.com/wyonliu/Ome365/security/advisories/new](https://github.com/wyonliu/Ome365/security/advisories/new)
2. **Email**: send to the repo owner via the address listed in their GitHub profile

We aim to:
- **Acknowledge** within 72 hours
- **Triage + fix plan** within 7 days for critical issues
- **Patch + advisory** within 30 days for high-severity issues
- Credit you in the advisory unless you prefer to stay anonymous

## Scope

In scope:
- Authentication / authorization bypass (multi-tenant isolation)
- Data exfiltration via share station / A2A endpoints
- RCE / SSRF / path traversal in `.app/server.py` or `.app/share_server.py`
- Cryptographic weaknesses in `share_auth.py` (Fernet / argon2 / passphrase)
- PII leak in default-shipped sample / demo files

Out of scope:
- Issues requiring physical access to the user's machine
- Self-XSS via user's own browser console
- Reports from automated scanners without working PoC
- Attacks requiring rooted server / compromised admin credentials

## Hardening reminders for self-hosters

- Default `LLM_BACKEND=local` (Ollama) — no data leaves your machine unless you opt in
- Run behind reverse proxy (nginx / Caddy) with TLS · template at `infra/nginx-ome365.conf`
- Set `SHARE_USERS` env to whitelist · don't expose internal slugs publicly
- Rotate `master.key` (Fernet) yearly · `chmod 600 master.key`
- Enable `pre-commit` hook (`git config core.hooksPath .githooks`) before pushing forks
- Run `python3 scripts/scan_pii.py --history` before any public push

See [docs/legal/](docs/legal/) for DPA · GDPR · PIPL · ISO 42001 templates (coming D-5).
