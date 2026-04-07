# Ome365 v0.2 — AI Integration Bridge

This file enables external AI tools (Claude Code, Cursor, etc.) to understand and work with the Ome365 vault.

## What is Ome365?

A personal super assistant. FastAPI backend + Vue 3 CDN frontend, Markdown-first storage, AI-enhanced.

## Vault Structure

```
Rise365/                    # Project root
├── .app/                   # Application code (DO NOT modify without understanding)
│   ├── server.py           # FastAPI backend (port 3650)
│   ├── settings.json       # User settings (contains API keys - sensitive)
│   ├── static/             # Frontend (Vue 3 CDN, zero build)
│   └── media/              # Uploaded media files
├── Journal/                # Daily/Weekly/Monthly/Quarterly journals
│   ├── Daily/              # YYYY-MM-DD.md files
│   ├── Weekly/             # W01-YYYY-MM-DD.md files
│   └── Quarterly/          # Q1-2026.md etc
├── Notes/                  # Quick notes (YYYY-MM-DD.md, append-only)
├── Memory/                 # AI memory system (v0.2)
│   ├── MEMORY.md           # Auto-generated index
│   ├── identity.md         # User identity/role/values
│   ├── preferences.md      # User preferences/habits
│   ├── goals.md            # Long-term goals
│   ├── skills.md           # Skills & learning
│   └── insights/           # AI-generated reflections (YYYY-MM-DD_type.md)
├── Contacts/people/        # Contact .md files (YAML frontmatter)
├── Decisions/              # Decision log .md files
├── Projects/               # Sub-project tracking
├── Templates/              # File templates
├── 000-365-PLAN.md         # Master 365-day plan (Q1-Q4, 6 dimensions)
└── 000-DASHBOARD.md        # Dashboard config
```

## API Endpoints (localhost:3650)

### Core
- `GET /api/dashboard` — Full dashboard data (day/week/quarter/milestones/streaks)
- `GET /api/today` — Today's journal + tasks
- `PUT /api/today/content` — Update today's journal (body: `{raw: "markdown"}`)
- `GET /api/week` — This week's data
- `GET /api/plan` — 365-day plan (parsed quarters/dimensions/milestones)

### Memory (v0.2)
- `GET /api/memory` — List all memories + index
- `GET /api/memory/{filename}` — Read specific memory
- `POST /api/memory` — Create/update memory (body: `{name, type, description, content, filename?}`)
- `DELETE /api/memory/{filename}` — Delete memory

### Enhanced Daily (v0.2)
- `GET /api/today/meta` — Today's mood/energy/focus
- `PUT /api/today/meta` — Update mood/energy/focus (body: `{mood, energy, focus}`)

### Search & Reflection (v0.2)
- `GET /api/search?q=keyword` — Full-text search across vault
- `POST /api/reflect` — AI reflection (body: `{type: "daily"|"weekly"}`)
- `GET /api/on-this-day` — Historical entries for today's date
- `GET /api/streaks` — Streak data (current/best/total active days)

### Notes & Tasks
- `POST /api/notes` — Quick note (body: `{text, category?}`)
- `GET /api/notes` — All notes grouped by date
- `POST /api/today/add` — Add task (body: `{text, category?, time?, repeat?}`)
- `POST /api/today/toggle` — Toggle task (body: `{text}`)

### Contacts
- `GET /api/contacts` — List contacts
- `POST /api/contacts` — Create contact
- `GET /api/contacts/{slug}` — Contact detail

### AI
- `POST /api/ai` — Ask AI (body: `{prompt, context?}`)
- `GET /api/settings` — Current settings (keys masked)

## Memory File Format

```markdown
---
name: My Career Goals
description: Long-term career vision and milestones
type: goal
---

Content here in markdown...
```

Types: `identity`, `preference`, `goal`, `skill`, `insight`, `general`

## Daily Journal Frontmatter

```yaml
---
date: 2026-04-07
week: W01
mood: 4          # 1-6 scale
energy: 3        # 1-5 scale
focus: 4         # 1-5 scale
tags: [productive, coding]
---
```

## Working with Ome365 from Claude Code

1. **Read user context**: `GET /api/dashboard` + `GET /api/memory` to understand user's goals and state
2. **Add notes/tasks**: `POST /api/notes` or `POST /api/today/add` to capture things
3. **Update memory**: `POST /api/memory` to save long-term learnings
4. **Search**: `GET /api/search?q=...` to find relevant past entries
5. **Direct file access**: All data is in plain `.md` files, readable/writable directly

## Important Notes

- Server runs on `localhost:3650`
- All data is Markdown files — you can read/write them directly without API
- Settings at `.app/settings.json` contain API keys — treat as sensitive
- Memory index (MEMORY.md) is auto-regenerated — don't edit manually
- Daily files are auto-created with templates when accessed
