---
name: audit-incident-response
description: |
  Standard incident response playbook for Ome365 vaults · grep the audit log
  + write a 5-line postmortem · 6 minute drill, no longer.
allowed-tools: [Bash, Read, Write]
license: Apache-2.0
ome365:
  author: alice
  created: 2026-05-09
  role: Operator
  scope: tenant
  enforces: post-incident
  code_mode_compatible: false
---

# Skill: audit-incident-response (6-minute drill)

> "Every audit line you didn't read is a postmortem you'll never write."

## When to use

Anytime the team suspects a vault state issue · unexpected deletion · a stale
decision being closed · webhook noise · permission denial on something that
should have worked.

## The 6 minutes

### 1 minute · scope

Define the symptom in one sentence. "On 2026-MM-DD, X said decision Y was
already closed but I just opened it." This is the one fact every audit grep
must be checked against.

### 2 minutes · grep the trail

```bash
# Recent activity, last 7 days, all actors
ome365 audit grep --days 7

# Narrow by actor
ome365 audit grep --actor bob --days 30

# Narrow by target — most useful for "what happened to Decision X?"
ome365 audit grep --target-id 2026-04-15-pick-vendor

# Narrow by action type — see VALID_ACTIONS in ome365_audit.py
ome365 audit grep --action decision.close --days 30
```

Output is JSONL · pipe through `jq` for fancy filtering:

```bash
ome365 audit grep --days 7 | jq 'select(.actor == "bob")'
```

### 1 minute · cross-reference

Open the matching `vault/Decisions/<id>.md` · check whose `owner:` is set,
whose name is in `⑤ Execution log`. Names should match the audit `actor`. If
they don't — that's the smoking gun.

### 2 minutes · write the postmortem

Append to the next decision opened that day, or create
`vault/Decisions/<today>-incident-<short-name>.md`:

```markdown
## Incident: <one-line symptom>
- when: <YYYY-MM-DD HH:MM>
- audit lines:
  - <ts>  <actor>  <action>  <target_id>
  - <ts>  <actor>  <action>  <target_id>
- root cause: <one sentence>
- fix: <one sentence — code change, RBAC tweak, training note>
- followup: <one TODO with owner>
```

Five bullets. Done.

## Why (rationale)

Audit logs are append-only and stay in `vault/Audit/<date>.jsonl` · they're
the cheapest evidence you'll ever have. The temptation is to skip the grep and
"just go fix it" — that's how the same bug ships three more times. Six minutes
buys an artifact you can paste into Slack, attach to a ticket, or mine months
later when a similar symptom recurs.

## Quality gates

- Every incident → at least one audit grep ran (proves you looked)
- Every postmortem → 5 bullets max (long postmortems don't get read)
- Every followup → an owner name (no "we should..." orphans)

## Related

- `ome365 audit grep --help` for full flags
- `tests/test_async_trace_audit.py::test_audit_cli_log_and_grep` for examples
- `ome365_audit.VALID_ACTIONS` for the full action vocabulary
