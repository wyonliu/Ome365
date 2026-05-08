---
id: 2026-05-08-pick-llm-backend
opened: 2026-05-08T14:00:00Z
closed: 2026-05-08T16:30:00Z
status: closed
owner: alice
participants: [bob, carol]
supersedes: null
superseded_by: null
outcome: "Anthropic Claude Haiku 4.5 (chat) + BAAI/bge-m3 (embedding · self-host)"
value_anchors:
  - P              # Product growth (faster agents)
  - L              # Large scope (affects all tenants)
  - 维护性          # Adds bge-m3 model dep · ~2.3 GB
roi_estimated: "+40% throughput · -60% cost vs OpenAI baseline"
roi_actual: null   # 90 day backfill via nightly distill_outcomes
planned_duration_days: 1
elapsed_days: 1
category: infra
hours_saved: 8
---

# Decision: Pick LLM backend for v1.1

## ① Problem definition (human · alice)

We need a default LLM backend for v1.1 that:
- Works without API key (local fallback)
- Cost < $0.01 per typical call
- Stable on commodity laptop (8 GB RAM minimum)

## ② Data needs (AI)

Pulled benchmarks: anthropic / openai / qwen / ollama-llama3 throughput + cost
on our 100 sample meeting summarize calls.

## ③ Models considered (AI)

| Backend | $/1M tokens | Latency p50 | Local? | Notes |
|:---|:---:|:---:|:---:|:---|
| anthropic claude-haiku-4.5 | $0.25 / $1.25 | 800ms | ❌ | Best quality / dollar |
| openai gpt-5-mini | $0.40 / $2.00 | 1200ms | ❌ | More expensive |
| qwen3-4b | $0.10 / $0.40 | 600ms | ✅ via DashScope | Mid-quality |
| ollama llama3.2:3b | $0 | 4000ms | ✅ | Slow but free |

## ④ Options (AI)

A. **Anthropic only** — best quality, $0.01/call, requires API key
B. **Ollama only** — zero cost, slow, no API key
C. **Hybrid: Anthropic default + Ollama fallback when key missing** ✓ (chosen)

## ⑤ Decision (human · alice · leader)

**Choice C (hybrid)**. LLM_BACKEND env var:
- `anthropic` (default if API key set)
- `ollama` (fallback if no key)
- `openai` / `qwen` (opt-in)

Rationale: respects file-first / self-host philosophy + good DX out of box.

## ⑥ Reflection (human · alice + bob · leader)

Key insight: don't force a single backend — **let the env decide**. Same pattern
as our DAO layer (sqlite default + PG opt-in). Consistency = predictability.

Open question: should we add cost-cap auto-throttle to fallback? Defer to v1.1 W4.

## ⑦ Execution log (AI · append-only)

- 2026-05-08T14:30 · `feat(llm): LLMBackend protocol with 4 impls` (commit abc123)
- 2026-05-08T15:45 · `feat(llm): default-anthropic + fallback-ollama wiring`
- 2026-05-08T16:30 · merged to main · status=closed

## ⑧ Feedback (AI · 90 day backfill · pending 2026-08-08)

(empty until 2026-08-08 nightly distill_outcomes job runs)
