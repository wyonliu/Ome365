# Sandbox Setup · HuggingFace Space + try.omnity.ai

> Goal: lift `try.omnity.ai` (or equivalent demo URL) so HN visitors can click and try without installing.
>
> Last updated: 2026-05-08 · v1.0-rc1

---

## 0 · Why a sandbox

Show HN traffic spike: 50% click but only 5% will `git clone && ./ome365`. A 30-second hosted demo dramatically increases the "I get it" rate.

## 1 · HuggingFace Space (recommended · free tier)

### 1.1 Create Space

```
https://huggingface.co/new-space
  Owner:           wyonliu (or your HF account)
  Space name:      ome365-demo
  License:         Apache 2.0
  SDK:             Docker (custom Dockerfile · most flexible)
  Hardware:        CPU basic (free)
  Visibility:      Public
```

### 1.2 Push Dockerfile + sample-vault

Use the Dockerfile shipped at [`infra/Dockerfile.demo`](../../infra/Dockerfile.demo) (created in this repo).

```bash
# Clone HF Space repo
git clone https://huggingface.co/spaces/wyonliu/ome365-demo
cd ome365-demo

# Copy Dockerfile + minimal demo content
cp /path/to/Ome365/infra/Dockerfile.demo Dockerfile
cp /path/to/Ome365/infra/space-README.md README.md

# Push to HF
git add Dockerfile README.md
git commit -m "Initial Ome365 demo Space"
git push
```

HF Spaces will build the image (~5 min first time) and assign URL `https://huggingface.co/spaces/wyonliu/ome365-demo`.

### 1.3 Demo restrictions (DO NOT skip)

To avoid abuse and protect privacy:

- `LLM_BACKEND=disabled` — no external LLM calls (avoid cost spikes)
- `OME365_VAULT=/tmp/demo-vault` — ephemeral storage · resets on restart
- `OME365_AUTH_PROVIDER=none` — no login (read-only demo)
- Add a banner: "This is a demo · data resets every restart · do not store real PII"

## 2 · try.omnity.ai (custom domain)

If you own `omnity.ai` (or want vanity URL):

### 2.1 DNS setup

```
CNAME try.omnity.ai → wyonliu-ome365-demo.hf.space
```

DNS propagation: 1-6 hours globally.

### 2.2 Verify

```bash
curl -sI https://try.omnity.ai | head -1
# expected: HTTP/2 200 (or 302 to login)
```

## 3 · Alternative: Replicate / Modal / Fly.io

If HF Space free tier insufficient (e.g. need GPU for Hike L2 vector layer demo):

| Provider | Free tier | Setup | Best for |
|:---|:---|:---|:---|
| HF Space | Yes (CPU basic) | Dockerfile push | **default · recommended** |
| Replicate | $0.0001/s · pay-as-go | API + Docker image | GPU workloads |
| Modal | $30/mo free credits | Python decorator | High-traffic spike protection |
| Fly.io | Yes (256MB shared) | flyctl deploy | Persistent demo with users |

For 5-13 Show HN, HF Space is sufficient (CPU · stateless · free).

## 4 · Smoke tests after deploy

```bash
# Demo URL responds
curl -fsS https://huggingface.co/spaces/wyonliu/ome365-demo/api/dashboard | jq .day

# Custom domain (if set)
curl -fsS https://try.omnity.ai/ | grep -q "Ome365"

# Demo banner visible
curl -s https://try.omnity.ai/ | grep -q "demo · data resets"
```

## 5 · Monitoring

Set up simple uptime check:
- HF Space: check `https://huggingface.co/api/spaces/wyonliu/ome365-demo/runtime` every 5 min
- Custom domain: UptimeRobot free tier (50 monitors · 5-min interval)

Alert if down > 15 min during launch period.

## 6 · Demo content curation

Ship a curated `Knowledge/entities/` with pre-seeded stories so visitors see immediate value:

- 5-10 sample entity files (Alice / Bob / sample-org / sample-product)
- 3 sample meetings (frontmatter complete · narrative readable)
- Pre-built decision_chain showing how Hike connects entities + meetings

Sample content lives in [`docs/hike-templates/manufacturing/`](../hike-templates/manufacturing/) · curated for demo.

## 7 · After Show HN

Post-launch, evaluate whether to:
- Keep the demo running indefinitely (community goodwill · ~$0/mo on HF)
- Retire after 30 days (focus on self-host adoption metric)
- Upgrade to persistent (paid tier) if engagement justifies

Decision criteria: `share_clicks_on_demo > 100/week` for 4 consecutive weeks → keep.
