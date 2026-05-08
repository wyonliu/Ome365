---
name: hike-wiki-query
description: |
  Query distilled knowledge in vault/Knowledge/L2/ and L3/, return synthesized answer with citations.
  Karpathy LLM Wiki: "compile once, query forever."
allowed-tools: [Read, Glob, Grep]
license: Apache-2.0
ome365:
  author: alice
  created: 2026-05-08
  role: Hike
  scope: tenant
  code_mode_compatible: true
---

# Skill: hike-wiki-query

## When to use

User asks "what does my wiki say about X" / "/wiki-query <topic>" / "我之前是怎么想的".

## Implementation

1. Search vault/Knowledge/L2-distilled/ + L3-diagnostic/ for keyword match (regex + semantic)
2. Read top 5 matched markdown files
3. Synthesize answer with explicit citations:

```markdown
## Answer
<2-3 paragraph synthesis>

## Sources
- [topic-A.md](Knowledge/L2-distilled/topic-A.md) · `## Pattern · 2026-04-15`
- [topic-B.md](Knowledge/L3-diagnostic/topic-B.md) · `## Implementation note`
```

4. If 0 hits in L2/L3, fallback to grep L1-raw/ + flag "L2 distillation gap · run /wiki-update"

## Quality gates

- Every claim in answer must trace to a citation (`[file](path)`)
- ≥ 2 sources cited (else flag "weak evidence·only 1 source")
- No hallucination of source files (must exist on disk)
- Response < 500 tokens unless user explicitly asks for "full"
