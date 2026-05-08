---
name: meeting-summarize
description: |
  Summarize meeting markdown transcripts into structured action items, decisions, and key risks.
allowed-tools: [Read, Write]
license: Apache-2.0
ome365:
  author: alice
  created: 2026-05-08
  forks_from: null
  role: Generic
  scope: tenant
  code_mode_compatible: true
---

# Skill: meeting-summarize

## When to use

When user pastes a meeting transcript (markdown) and asks for "summary" / "action items" /
"key decisions". Trigger words: 总结 · summarize · action items · 待办 · key takeaways.

## Implementation

1. Read the transcript markdown.
2. Extract sections by heading:
   - Participants (if frontmatter or first ## section)
   - Decisions (look for "决定" / "decided" / "agreed")
   - Action items (look for "待办" / "TODO" / assignee names)
   - Risks (look for "风险" / "concern" / "blocker")
3. Output structured markdown:

```markdown
## Summary
[1-3 sentence overview]

## Decisions
- [decision 1] · owner: X · target: YYYY-MM-DD

## Action items
- [ ] [task] · owner: X · due: YYYY-MM-DD

## Risks / blockers
- [risk] · severity: low/med/high · mitigation owner: X
```

4. If `decision_id` found in frontmatter, link the summary as `Decisions/<id>.md` `## ⑤ Execution log` append.

## Quality gates

- ≥ 1 action item OR ≥ 1 decision OR ≥ 1 risk extracted (else respond "no actionable content found")
- Each action item must have explicit owner (no anonymous "we should…")
- Decisions must have implicit or explicit target date
