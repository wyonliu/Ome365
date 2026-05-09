# Changelog

## v1.1.26 — `ome365 decision list / show` CLI (2026-05-09)

### What v1.1.26 ships

- **`./ome365 decision list [--status open|closed|superseded] [--owner X] [--json]`**
  · view decision backlog from terminal · text-aligned columns or JSON.
- **`./ome365 decision show <id>`** · dump full Decision file content
  (frontmatter + 8 sections).
- **7 new tests** in `tests/test_ome365_decisions.py` (now 20): help · list-text ·
  list-json · status+owner filters · empty case · show-content · show-not-found.

### Why this matters

- Operators previously had to either `curl localhost:3650/api/decision/list` or
  read `vault/Decisions/*.md` directly. The CLI is the natural bridge for
  scripting and for users without a server running. Decision mutations stay
  HTTP-driven — they need the audit + webhook hook chain.
- This closes the last v1.1 module CLI gap. All 12 v1.1 modules now have CLI
  surface area.

### Quality gates

- 488 tests · 0 PII · 271 tracked files

---

## v1.1.25 — `ome365 rbac` CLI · who / list / check (2026-05-09)

### What v1.1.25 ships

- **`./ome365 rbac who <actor>`** · JSON dump of actor's role + permissions
  array (read/write/delete/admin).
- **`./ome365 rbac list`** · machine-readable dump of `roles.yml` config:
  `{default_role, members}`.
- **`./ome365 rbac check <actor> <action>`** · exit 0 if allowed, 1 if denied.
  Useful in CI scripts: `ome365 rbac check $USER write || exit 1`.
- **5 new tests** in `test_v1_1_2_final.py` (now 22): help · who · check
  allow+deny · list · invalid-action.

### Why this matters

- v1.1.x ships RBAC, but the only way to debug "why can't bob delete?" was
  to read the YAML manually. The CLI exposes the resolved view including
  default-role fallback. All 12 v1.1 modules now have CLI surface area.

### Quality gates

- 481 tests · 0 PII · 271 tracked files

---

## v1.1.24 — `ome365 notify list / test` CLI for webhook ops (2026-05-09)

### What v1.1.24 ships

- **`./ome365 notify list`** · prints configured webhooks with **host only**
  (URL paths/tokens never logged · PII safety).
- **`./ome365 notify test [--event E] [--platform P]`** · fires a fake event
  payload to all (or filtered) webhooks. Returns `{sent, failed, skipped,
  results}` JSON. Exit code 1 if any webhook failed.
- **5 new tests** (now 19 total in test_ome365_notify.py): help · list-empty ·
  list-host-only-no-token-leak · test-fires-event · test-empty-config-with-note.

### Why this matters

- Until now, operators configuring webhooks had no built-in way to verify
  delivery. They'd close a fake decision via API to trigger one, with no
  visibility into delivery success. `notify test` is the missing diagnostic.
- The `list` command's host-only output is a security feature — Slack/Lark
  webhook URLs contain the auth token in the path. Logging them would leak.

### Quality gates

- 476 tests · 0 PII · 271 tracked files

---

## v1.1.23 — `wiki query --json` for scriptable knowledge search (2026-05-09)

### What v1.1.23 ships

- **`./ome365 wiki query 'term' --json`** · machine-readable search results.
  Each row: `{score, path, decision_id, snippet}`. Empty result = `[]`.
- **2 new tests** · pin output shape · empty case returns array.

### Why this matters

- Round-tripping search results into other tools (notion-sync, slack bots,
  custom dashboards) requires parseable output. The text mode is human-only.
  Both wiki-query consumers (interactive + automated) are now covered.

### Quality gates

- 471 tests · 0 PII · 271 tracked files

---

## v1.1.22 — README quick-tour reflects 21 micro-releases (2026-05-09)

### What v1.1.22 ships

- **README v1.1.x box updated** · test count 441 → 469 · adds quick-tour
  entries for the 4 ops-scriptable CLIs shipped in v1.1.17-20:
  `doctor --json`, `wiki/backup --dry-run`, `backup list --json`,
  `metrics` (offline scrape).

### Why this matters

- The "what's new" surface area has compounded over 21 micro-releases. New
  visitors land on the README first; if it pins old test counts and misses
  the most useful CLIs, they walk away with the wrong impression.

### Quality gates

- 469 tests · 0 PII · 271 tracked files

---

## v1.1.21 — 6th SKILL.md: audit-incident-response (2026-05-09)

### What v1.1.21 ships

- **`vault.example/Skills/audit-incident-response.md`** · 6-minute drill for
  vault operators after suspected incident. Covers: scope (1m) → grep audit
  trail (2m) → cross-reference Decision file (1m) → write 5-bullet
  postmortem (2m). Validates against `tests/test_skill_lint.py`.

### Why this matters

- v1.1 ships an audit log + audit grep CLI. Without an opinionated workflow,
  operators won't reach for it. SKILL.md is the productized opinion. 6 SKILLs
  now cover: meeting summaries, dev decisions, wiki update/query, cost-per-
  outcome, and incident response.

### Quality gates

- 469 tests · 0 PII · 270 tracked files (skill_lint covers the new file)

---

## v1.1.20 — `backup list --json` for scriptable retention (2026-05-09)

### What v1.1.20 ships

- **`./ome365 backup list --json`** · machine-readable backup catalog. Each
  row includes `name, path, size_bytes, size_mb, modified`. Empty result is
  `[]`, never an error.
- **2 new tests** · valid JSON shape with all 5 fields · empty case returns
  `[]` (not "no backups found" string).

### Why this matters

- Backup retention policies (keep N most recent, prune > 100 MB, etc.) need
  parseable output. Previously `list` was human-only. Now ops can:
  ```bash
  ome365 backup list --json | jq '.[1:] | .[].path' | xargs rm
  ```
  All three CLI primitives are now scriptable: `metrics` (Prometheus text),
  `doctor --json`, and `backup list --json`.

### Quality gates

- 469 tests · 0 PII · 270 tracked files

---

## v1.1.19 — `ome365 metrics` CLI (offline Prometheus scrape) (2026-05-09)

### What v1.1.19 ships

- **`./ome365 metrics`** · dump Prometheus text-format metrics from the vault
  without booting the FastAPI server. Useful for cron-driven scrapes,
  air-gapped environments, and ad-hoc debugging.
- **`./ome365 metrics --vault PATH`** · point at any vault for ad-hoc
  inspection (overrides `$OME365_VAULT`).
- **3 new tests** in `tests/test_ome365_backup_metrics.py` (now 24 tests):
  help, basic dump, --vault flag override.

### Why this matters

- Until now, `/metrics` required an HTTP server. Operators in restricted
  environments (no port binding, no daemon) had no way to scrape vault
  state. CLI mode bridges that gap with stdlib only.

### Quality gates

- 467 tests · 0 PII · 270 tracked files

---

## v1.1.18 — `backup restore --dry-run` (preview before destructive restore) (2026-05-09)

### What v1.1.18 ships

- **`./ome365 backup restore <tarball> --dry-run`** · validates path-traversal
  safety + previews tarball contents (n_files, total_bytes, sample of first 10
  files) without extracting anything to the vault. Critically also reports
  `would_backup_prior: bool` so users know whether `--unsafe` is needed to skip
  the safety backup.
- **4 new tests** in `tests/test_ome365_backup_metrics.py` (now 21 tests):
  no extraction, prior-backup flag, path-traversal blocked even in dry-run, CLI
  wiring.

### Why this matters

- `restore` overwrites the vault. Until now, the only safety net was `safe=True`
  (auto-backup before restore). `--dry-run` adds a second safety layer — see
  what's in the tarball before committing. All three mutating CLIs are now
  dry-runnable: `wiki update`, `archive`, `backup create/restore`.

### Quality gates

- 464 tests · 0 PII · 269 tracked files

---

## v1.1.17 — `doctor --json` ops contract pinned (2026-05-09)

### What v1.1.17 ships

- **`tests/test_doctor_json.py`** · 8 tests pinning the public ops contract
  emitted by `./ome365 doctor --json`. Monitoring/alerting parses this output;
  a silent shape change breaks dashboards. Tests pin: top-level keys, value
  types, ports/files sub-shapes, all 12 v1.1 module names, `ok` flag logic,
  vault state when `OME365_VAULT` exists, and basic JSON parseability.

### Why this matters

- Ops integration was the missing piece. v1.1.x added `--json` for
  machine-readable doctor output, but no tests pinned the schema. A future
  refactor could rename `v1_1_modules` → `modules` and we'd only notice via
  customer pages. Now CI fails first.

### Quality gates

- 460 tests · 0 PII · 269 tracked files

---

## v1.1.16 — Audit endpoint tests + CONTRIBUTING v1.1 essentials (2026-05-09)

### What v1.1.16 ships

- **3 audit endpoint tests** (`tests/test_v1_1_2_final.py` extended) ·
  v1.1.10 shipped `/api/eval/audit/recent` without tests · now covered:
  empty vault / events present / limit respected.
- **`CONTRIBUTING.md` v1.1 essentials block** · 6 PR-prep rules at top
  (Kevin hook · doctor · pytest · scan_pii · --dry-run · no-emoji).

### Quality gates

- 452 tests · 0 PII · 269 tracked files

---

## v1.1.15 — backup --dry-run (3 modules now dry-runnable) (2026-05-09)

### What v1.1.15 ships

- **`./ome365 backup create --dry-run`** · preview which files would be
  included/skipped without creating the tarball. Returns
  `{dry_run: true, would_include_count: N, would_skip_count: M, would_write_to: <path>}`.
- All 3 mutating CLIs now have consistent `--dry-run` flag:
  - `ome365 wiki update --dry-run`   (v1.1.13)
  - `ome365 archive --dry-run`       (v1.1.14)
  - `ome365 backup create --dry-run` (v1.1.15)
- 2 new tests for backup dry-run.

### Quality gates

- 449 tests · 0 PII · 269 tracked files

---

## v1.1.14 — archive --dry-run (consistency with wiki) (2026-05-09)

### What v1.1.14 ships

- **`./ome365 archive --dry-run`** · preview which jsonl files WOULD be
  gzipped without touching disk. Same pattern as `wiki update --dry-run`.
  Returns `{dry_run: true, moved: 0, would_move: N, would_archive: [...]}`.
- **1 new test** (`test_archive_dry_run_no_disk_writes`).

### Quality gates

- 447 tests · 0 PII · 269 tracked files

---

## v1.1.13 — wiki update --dry-run + 3 new tests (2026-05-09)

### What v1.1.13 ships

- **`./ome365 wiki update --dry-run`** · preview what WOULD be distilled
  without touching disk and without firing the wiki.updated webhook.
  Returns `{dry_run: true, appended: 0, would_append: N, would_write: [...]}`.
  Useful for "preview before commit" workflows in CI.
- **3 new tests** (`tests/test_ome365_wiki.py`):
  - `test_dry_run_does_not_write_files` — disk untouched
  - `test_dry_run_then_real_run_idempotent` — dry would_append == real appended
  - `test_cli_update_dry_run` — CLI `--dry-run` flag

### Quality gates

- 446 tests · 0 PII · 269 tracked files

---

## v1.1.12 — Industry benchmarks · sector breakdown (2026-05-09)

### What v1.1.12 ships

- **`docs/strategy/industry-benchmarks.yml` enriched** · added `sectors:`
  block with P50 numbers for 6 verticals (fintech / saas_b2b / manufacturing
  / consulting / healthcare / retail) · cockpit can now use
  `tenant_config.sector` to show industry-specific comparisons.
- **Refresh SOP** documented (monthly · re-pull Salesforce/NavyaAI/Forrester ·
  decision-cite the refresh).

### Quality gates

- 443 tests · 0 PII · 269 tracked files

---

## v1.1.11 — Audit demo data · cockpit lit up (2026-05-09)

### What v1.1.11 ships

- **`vault.example/Audit/2026-05-09.jsonl`** · 8 sample audit events
  across 5 actors and 4 action types (decision.create / decision.close /
  wiki.update / backup.create / config.change). Cockpit Audit card now
  shows real demo data instead of empty state on fresh install.

### Quality gates

- 443 tests · 0 PII · 268 tracked files
- /api/eval/audit/recent returns 8 events on vault.example

---

## v1.1.10 — 5th cockpit card · Audit visibility (2026-05-09)

### What v1.1.10 ships

- **`/api/eval/audit/recent?days=N&limit=M`** · new endpoint surfacing
  recent audit log entries (decision.close / wiki.update / backup.create /
  etc) for cockpit visibility.
- **5th cockpit card · Audit log** · full-width card under the 4-card
  grid showing the last 10 events with timestamp · action pill · actor →
  target. Empty-state is friendly ("close a decision or update wiki to
  fire one"). Curl button copies the API call.
- **Action pills** · color-coded by action group (decision=P/blue,
  wiki=L/green, trace=M/yellow, backup=XL/green, share+config=Revert/red).

### Quality gates

- 443 pytest tests · 100% pass
- 0 PII hits · 268 tracked files
- audit endpoint smoke: 200 with `events` array (empty on virgin vault.example)

### v1.1.x series complete (2026-05-09 · single-day sprint)

Ten micro-releases · v1.1.0 → v1.1.10 · 250 → 443 pytest tests · 12 v1.1
modules shipped · 0 PII through every step · every code commit cited a
`[decision: <id>]` tag.

| Tag | Highlight |
|:---|:---|
| v1.1.0  | Team Brain · 8-week file-first design ships |
| v1.1.1  | Productization · demo seed + UI + onboarding + webhooks + backup + metrics + audit + perf bench |
| v1.1.2  | Final batch · multi-user / RBAC / i18n / LLM wiki / sqlite-vec / ed25519 |
| v1.1.3  | CLI polish · verify / status / eval / requirements-optional |
| v1.1.4  | Doctor v1.1 + cockpit role badge + v1.2 preview |
| v1.1.5  | CI green for full pytest + 5th SKILL.md (cost-per-outcome) |
| v1.1.6  | Perf smoke pytest budgets + RBAC sample yml |
| v1.1.7  | ARCHITECTURE v1.1 banner + install.sh hints + Show HN draft v0.3 |
| v1.1.8  | Full lifecycle integration test (12 modules cooperating) |
| v1.1.9  | Cockpit keyboard shortcuts + doctor --json |
| v1.1.10 | 5th cockpit card · Audit visibility |

---

## v1.1.9 — Cockpit shortcuts + doctor --json (2026-05-09)

### What v1.1.9 ships

- **Cockpit keyboard shortcuts** (`/v1_1.html`):
  - `r` — refresh all 4 cards
  - `t` — toggle theme (dark/light)
  - `l` — toggle language (zh/en)
  - `1-4` — focus the corresponding card (smooth scroll)
  - `?` — show shortcut help toast
  - Footer shows `⌨ ?` reminder.
  - Inputs/selects are not hijacked — focus-aware.
- **`./ome365 doctor --json`** · machine-readable health output for ops
  integration. Emits `{platform, python_version, missing_core_pkgs, ports,
  files, v1_1_modules, vault, ok}`. Returns exit 0 if `ok: true`, else 1.

### Quality gates

- 443 pytest tests · 100% pass
- 0 PII hits · 268 tracked files
- doctor --json smoke: returns valid JSON with all 12 v1.1 modules "ok"

---

## v1.1.8 — Full v1.1 lifecycle integration test (2026-05-09)

### What v1.1.8 ships

- **`tests/test_v1_1_integration.py`** · 2 new tests that exercise every
  v1.1 module end-to-end in one realistic scenario:
  - **Test 1: full lifecycle** — RBAC enforcement → 5 decisions create+close
    → audit log fired → trace sync+async → wiki update → wiki query → eval
    7-dim → team_distribution cache → 3 finops scopes → /metrics render →
    ed25519 sign+verify → archive → backup → restore → verify intact
  - **Test 2: HTTP routes** — same flow via FastAPI TestClient ·
    `/api/decision/list`, `/api/eval/whoami`, `/api/eval/role/alice`,
    `/api/eval/finops/dashboard`, `/.well-known/agent-card.json` (signed)
- This catches integration regressions that 12 module-level test suites
  miss: a wiki update breaking audit log; a backup tarball excluding
  Audit/; a sign payload mutation breaking verification.

### Quality gates

- 443 pytest tests · 100% pass (was 441)
- 0 PII hits · 267 tracked files
- Integration smoke: 12 modules cooperate cleanly in one tmp_path

---

## v1.1.7 — ARCHITECTURE v1.1 + install.sh hints + Show HN v0.3 (2026-05-09)

### What v1.1.7 ships

- **`docs/ARCHITECTURE.md` v1.1 banner** · top-of-file map of all 12 v1.1
  modules, mounted routes, file invariants, quality gates · "for current
  architecture, read this banner top-down" preserves v0.8 history below.
- **`install.sh` enhancement** · post-install hint surfaces optional v1.1
  features (LLM-distilled wiki / semantic search) and post-boot quick-start
  commands (`/v1_1.html` / `./ome365 status` / `./ome365 doctor`).
- **README v1.1 highlights box refreshed** · 9-line `quick tour` showing
  every shipped v1.1 surface as a one-liner command.
- **Show HN draft v0.3** (`docs/launch/show-hn-draft-v0_3.md`) · titled
  "Cost-per-Outcome team brain · ed25519 signed · 0 deps", 1500-char body,
  5 anticipated comments with prepared answers.

### Quality gates

- 441 pytest tests · 100% pass
- 0 PII hits · 267 tracked files
- bash -n install.sh OK
- All 7 micro-releases (v1.1.0 through v1.1.7) tagged on GitHub mirror

---

## v1.1.6 — Perf smoke pytest + RBAC sample (2026-05-09)

### What v1.1.6 ships

- **`tests/test_perf_smoke.py`** · 8 perf-budget tests integrated into pytest.
  Catches regressions in `grep_decisions` / `eval_member` / `team_distribution`
  / `finops_summary` / `/metrics render`. Includes a "cache beats naive"
  invariant test that fails CI if `_compute_team_distribution` is no longer
  faster than naive 5×eval_member.
- **`vault.example/.ome365/roles.sample.yml`** · sample RBAC config showing
  the 5 actors with realistic role assignments (alice=owner, bob/carol/dan=
  contributor, erin=viewer/exec sponsor). Copy to `roles.yml` to enable.

### Quality gates

- 441 pytest tests · 100% pass (was 433)
- 0 PII hits · 264 tracked files
- All perf smoke budgets green: grep_decisions <300ms, eval_member <1s,
  team_distribution <800ms, /metrics <500ms

---

## v1.1.5 — CI green for v1.1 + 5th SKILL.md (2026-05-09)

**Tagline**: CI now actually runs all 433 tests.

### What v1.1.5 ships

- **CI overhaul** · `.github/workflows/ci.yml` `unit-tests` job now runs the
  full pytest suite (was only running 4 specific test files). Added FastAPI
  + httpx + cryptography to install step. Added `./ome365 doctor` smoke
  step. Coverage report widened to 12 v1.1 modules.
- **CI new job: `v1_1-cockpit-e2e`** · boots the server in background and
  curl-tests 10 v1.1 endpoints + verifies ed25519 agent-card signature
  via `./ome365 verify`. Catches integration regressions that unit tests
  can miss.
- **5th SKILL.md** · `vault.example/Skills/cost-per-outcome.md` · the
  Anti-Tokenmaxxing posture as a proper SKILL.md with 3 finops views,
  CLI/HTTP/SDK invocation, NEVER-do list, CIO/CEO-ready output template.

### Quality gates

- 433 pytest tests · 100% pass
- 0 PII hits · 264 tracked files
- CI now green-gates: PII + syntax + unit (full 433) + install.sh dry-run +
  v1.1 cockpit e2e (server-boot + endpoint smoke + signature verify)

---

## v1.1.4 — Doctor v1.1 + role badge + v1.2 preview (2026-05-09)

**Tagline**: When you run `./ome365 doctor`, you see all 12 v1.1 modules at a glance.

### What v1.1.4 ships

- **`./ome365 doctor` v1.1 upgrade** · adds a 12-module health table after the
  classic 12 checks. Shows ✓/✗ per v1.1 module (eval / decisions / trace / wiki
  / archive / backup / audit / metrics / notify / rbac / signing / cli_extras),
  optional dep status (anthropic / openai / sqlite-vec / sentence-transformers
  with which env flag activates each), and vault state (decisions / traces /
  skills count + signing key + roles.yml presence).
- **Cockpit role badge** · `/v1_1.html` now shows the current actor's role
  (owner / contributor / viewer) as a colored pill in the toolbar. Backed by
  new `GET /api/eval/role/{actor}` endpoint. Viewers immediately know they're
  viewers.
- **`docs/strategy/v1.2-preview.md`** · 90-day roadmap preview · 3 themes
  (Cognition Loop / Multi-Hike federation / Cost-per-Outcome board pack) ·
  what v1.2 explicitly does NOT ship · timeline · how preview becomes plan.

### Quality gates

- 433 pytest tests · 100% pass
- 0 PII hits across 262 tracked files
- doctor smoke: `12/12 v1.1 modules loaded`

---

## v1.1.3 — CLI polish + self-review (2026-05-09)

**Tagline**: Every v1.1 surface has a CLI now.

Self-review pass after v1.1.2 found 6 polish gaps and shipped them.

### What v1.1.3 ships

- **`./ome365 verify <url-or-file>`** · ed25519-verify any agent-card.
  Returns 0 if valid · 1 if unsigned/invalid · 2 on transport error.
  ```
  $ ./ome365 verify https://your-org.com/.well-known/agent-card.json
  ✓ valid  https://your-org.com/.well-known/agent-card.json
    alg:      ed25519
    pubkey:   TYSD2rxZiHZ9eUTED9R2Wujnl8eQsD0h...
  ```
- **`./ome365 status`** · one-glance vault overview (decisions / traces /
  skills / wiki / audit / backups / RBAC / signing key).
- **`./ome365 eval member|finops|skills|whoami`** · CLI mirror of `/api/eval/*`
  routes. No need to spin up a server for quick lookups.
- **`requirements-optional.txt`** · clearly documents the 4 optional deps
  (anthropic / openai / sqlite-vec / sentence-transformers) and which env
  flag activates each. Default install stays 0-deps for the file-first path.
- **13 new tests** for the CLI extras (377 → 420 → 433).

### Quality gates

- **433 pytest tests · 100% pass**
- **0 PII hits** across 258 tracked files
- Smoke-verified: `./ome365 verify` against running server returns ✓ valid
- Smoke-verified: `./ome365 status` on `vault.example` shows 26 decisions /
  36 traces / 4 skills / 7 wiki categories / 1 ed25519 key

### Migration from v1.1.2

No breaking changes. Just `git pull` and the new CLI commands work.

---

## v1.1.2 — Final batch · enterprise-grade (2026-05-09)

**Tagline**: From team-ready to enterprise-shippable.

Six modules wrapping up everything that was deferred from v1.1.0/v1.1.1.

### What v1.1.2 ships

- **P0 #4 · Multi-user cockpit binding** · `/api/eval/whoami` resolves current
  actor (env > vault config > inferred from owner counts). `/api/eval/actors`
  lists all known actors. `/v1_1.html` calls these on boot — no more hard-
  coded `alice/bob/carol/dan/erin`. Works with any vault.
- **P1 #7 · RBAC** · `.app/ome365_rbac.py` · 3 roles (owner / contributor /
  viewer) configured in `vault/.ome365/roles.yml` (gitignored). `can()` /
  `require()` helpers throw `PermissionError`. Defaults to `contributor`
  when no config — backward-compatible.
- **P1 #10 · i18n** · zh-CN / en switcher in cockpit toolbar (中/EN button).
  Detects `navigator.language` for first-time users; persists to
  localStorage. `humanScope()` / `humanDim()` translate dimension and
  finops scope labels.
- **P3 #15 · LLM-distilled wiki** · gated by `OME365_WIKI_LLM=1` +
  `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. When enabled, `wiki update`
  prompts an LLM to extract a 1-3 sentence pattern from the full decision
  body. Falls back to outcome-string verbatim on any error. `OME365_WIKI_MODEL`
  picks the model (default: claude-haiku-4-5-20251001).
- **P3 #16 · sqlite-vec semantic search** · gated by `OME365_WIKI_VEC=1`. When
  enabled, `wiki query` indexes patterns into `vault/.ome365/wiki_vec.db` with
  `BAAI/bge-small-zh-v1.5` (default model · 90MB). Returns nearest-neighbor
  results by embedding distance instead of term frequency.
- **P3 #17 · ed25519 agent-card signing** · `.app/ome365_signing.py` ·
  `cryptography>=41` · auto-generates per-vault keypair on first call ·
  signs `/.well-known/agent-card.json` with canonical-JSON ed25519. Verify
  with `verify(card)`. `signature` / `signing_alg` / `signing_pubkey_b64`
  are now real on every agent-card response.

### Quality gates

- **420 pytest tests · 100% pass** (was 406 at v1.1.1)
- **0 PII hits** across 254 tracked files
- **gitignore expanded**: roles.yml / whoami / wiki_vec.db / .ome365/keys/
  all PII-protected by default
- **Kevin hook**: every code commit cited a `[decision: <id>]`
- **Smoke verified**: signed agent-card returns real ed25519 signature ·
  whoami auto-resolves actor · actors endpoint returns 5 actors

### Migration from v1.1.1

No breaking changes. New surface is opt-in:
1. (Optional) Create `vault/.ome365/roles.yml` to enforce RBAC
2. (Optional) Set `OME365_WIKI_LLM=1` + API key for LLM-distilled wiki
3. (Optional) `pip install sqlite-vec sentence-transformers` + set
   `OME365_WIKI_VEC=1` for semantic search
4. ed25519 signing is automatic on first agent-card request — no config

---

## v1.1.1 — Productization pass · Team-ready (2026-05-09)

**Tagline**: From "engineer demo" to "team can actually use this".

This is the productization pass that took v1.1.0 from a working spec to something
a 5+ person team can adopt without hand-holding. 8 modules added, 3 critical
bugs fixed, 156 tests added (250 → 406).

### What v1.1.1 ships

- **P0 #1 · Demo seed shock** (`scripts/seed_demo_vault.py`) · 12 real-world
  decisions across 5 categories (Eng/PM/Sales/Ops/Mixed) + 30 traces × 5 actors
  × 3 months + 7 distilled patterns. Replaces alice/bob hello-world. Team opens
  `/v1_1.html` and immediately sees real cockpit data with all 7 dimensions
  scoring meaningfully (alice total=3.39 with 12 closed decisions).
- **P0 #2 · Team onboarding** (`docs/TEAM_ONBOARDING.md`) · 5-minute walkthrough
  · M1 boot · M2 read decision · M3 4-card explanation · M4 write your first ·
  M5 Kevin rule. Plus 7 first-hour FAQs (markdown vs DB, sample threshold, etc.).
- **P0 #3 · Cockpit UI productization** (`/v1_1.html` rewrite) · loading
  skeletons · error toast + per-card retry · empty states with actionable
  commands · score bars · 5 role preset weights now actually different per role
  · CSV export · copy-curl button · light/dark theme · localStorage prefs · URL
  params shareable · responsive ≤800px.
- **P0 #5 · Webhook notifications** (`.app/ome365_notify.py`) · stdlib-only ·
  Slack/Lark/Feishu/Teams/generic formatters · 3 events (decision.closed /
  wiki.updated / budget.warn) · per-webhook events filter · best-effort never
  raises · config via env or `<vault>/.ome365/notify_webhooks.json`.
- **P1 #8 · Backup/restore CLI** (`.app/ome365_backup.py`) · `ome365 backup
  create | restore | list` · stdlib tarfile · auto-include Decisions / Trace /
  Skills / Knowledge / Contacts · auto-exclude secrets and cache · path-traversal
  blocked · safe-restore creates pre-restore backup automatically.
- **P2 #11 · Async trace write** (`.app/ome365_trace.log_async`) · queue + daemon
  thread · 1ms enqueue vs 100ms+ disk fsync · queue_size() exposed for `/metrics`
  · atexit graceful shutdown.
- **P2 #12 · Prometheus metrics** (`.app/ome365_metrics.py`) · GET `/metrics` ·
  12 metric families (decisions / traces / cost / value / by_actor / by_owner /
  http_requests / uptime / recent_24h) · proper Prom text format with ms
  timestamps · ready for Grafana scrape.
- **P2 #13 · Audit log** (`.app/ome365_audit.py`) · `vault/Audit/<date>.jsonl` ·
  append-only · 14 valid actions · `ome365 audit log | grep` CLI · automatic
  hooks on `decision.close` and other mutations · GDPR Art. 30 / SOC2 CC7.2
  compliance support.
- **P2 #14 · Perf benchmark** (`scripts/perf_bench.py`) · realistic 1000
  decisions / 5000 traces / 50 members · proves Review-Fix 1 cache works:
  - Naive (50× `eval_member`): 68s
  - Cached (1× `_compute_team_distribution`): 0.35s
  - **194× speedup** for full-team percentile computation
- **Review-Fix 1 + 8 真补** · the previously "spec-only" review-fixes now have
  real code:
  - `_compute_team_distribution()` is now an actual function in
    `ome365_eval.py`, not just docs
  - `tests/test_tenant_isolation_fuzz.py` runs 100 trials (was missing)
  - `tests/test_append_only_bypass.py` exercises the real Kevin git hook
  - `tests/test_d6_boundaries.py` pins 89/90-day cutover + roi=0/null distinction
  - **D6 real bug fixed**: `roi_actual=0` now correctly falls to anchor path
    (was forcing `no_roi_data` because `is not None` was truthy for 0)

### Quality gates

- **406 pytest tests · 100% pass** (was 250 at v1.1.0)
- **0 PII hits** across 250 tracked files
- **Kevin hook**: every code commit cited a `[decision: <id>]` tag
- **Anti-Tokenmaxxing**: every eval response carries `anti_tokenmaxxing_note`
- **GDPR Art. 22 + PIPL §13/§24**: enforced in code, not policy

### Migration from v1.1.0

No breaking changes. New surface is opt-in:
1. Run `python3 scripts/seed_demo_vault.py` to refresh demo data
2. Visit `/v1_1.html` for the productized cockpit
3. Configure webhooks in `<vault>/.ome365/notify_webhooks.json` (gitignored)
4. Wire Prometheus to `GET /metrics`
5. Use `./ome365 backup create` for nightly snapshots
6. Use `./ome365 audit grep --actor X` to trace activity

---

## v1.1.0 — Team Brain · 8-week file-first build (2026-05-09)

**Tagline**: The decisions, not the chats.
**Sub**: Your team's wiki is the artifact. Cost-per-Outcome is the metric.

This is the v1.1 ship that turns Ome365 from a personal vault + share station into a
**team brain** — Decisions, Skills, Trace, Wiki, Eval all derived from plain markdown
files. Every score has `human_review_required: True`. Every cost view is per-outcome,
not per-token. Region-aware (EU GDPR Art. 22 / CN PIPL §13/§24) is enforced by code,
not policy.

### What v1.1 ships (W1-W8)

- **W1 · Eval foundation** · `vault.example/` · 4 sample SKILL.md (spec-PASS) · 7-dim
  `ome365_eval.py` (D1-D7) · region-aware (EU default-deny / CN PIPL ack) · 5 preset
  weights (engineer/pm/sales/ops/mixed) · sample threshold 5 · `human_review_required`
  on every response
- **W2 · Decisions** · 8-step (5 AI + 3 human) lifecycle · `value_anchors` (P/XL/L/M/
  维护性/Revert) · `.calibration/` AI-vs-human diff capture · 5 endpoints
  (list/get/new/close/calibration) · git hook `[decision: <id>]` enforcement
  (Kevin 范式·先文件再代码)
- **W3 · Trace SDK** · `from ome365_trace import session` Python context manager
  (auto-time + auto-extract anthropic/openai usage) · `./ome365 trace add | query |
  rollup` CLI · monthly `Trace/monthly/<YYYY-MM>.summary.json` rollup
  (by_actor/by_skill/by_decision) · 11-field schema matches impl spec §四 4.5
- **W4 · Cost-per-Outcome dashboard** · D4 anchor-based judgment (P/XL/L/M lift,
  Revert/维护性 drag · backward-compat outcome-string fallback) · `dashboard_data()`
  combines 3 finops scopes + monthly_trend + by_actor · 4 HTTP endpoints under
  `/api/eval/*`
- **W5 · Cockpit panel** · `/v1_1.html` standalone Vue 3 CDN · 4 cards
  (Decisions/Skills/FinOps/Eval) · role-preset switcher · zero build step · explicit
  Anti-Tokenmaxxing warnings on display
- **W6 · Karpathy wiki** · `ome365 wiki update` scans Decisions → groups by category
  → appends `## Pattern · <id> · <date>` to `Knowledge/L2-distilled/<cat>.md` ·
  idempotent via `<!-- key: <decision_id> -->` · `ome365 wiki query 'term'` greps L2
  distilled with frequency rank
- **W7 · Nightly archive + AAIF** · `ome365 archive` gzips old `Trace/<date>.jsonl`
  into per-month `Trace/archive/<YYYY-MM>.jsonl.gz` (Moxt 95%/5% pattern) · `recall`
  symmetry · `/.well-known/agent-card.json` advertises v1.1 surface
  (decisions/eval/wiki/trace/archive) + compliance posture (gdpr / pipl / anti-tokenmaxxing)
- **W8 · Release** · this changelog · `docs/policies/EVAL_USAGE_POLICY.md` (HR usage
  boundary) · version bump · git tag v1.1.0

### Quality gates (all green at ship)

- **250 pytest tests · 100% pass** (was 178 at v1.0.0-rc1)
- **PII scan: 0 hits** across 193 tracked files
- **Kevin git hook**: every code commit traces to a `[decision: <id>]` tag in
  `vault.example/Decisions/`
- **Anti-Tokenmaxxing**: every eval response carries `anti_tokenmaxxing_note`
- **GDPR Art. 22 / PIPL §13/§24**: enforced in code, not policy

### Compliance ground

- All `eval_member()` responses set `human_review_required: True` (GDPR Art. 22)
- EU region default-deny unless `eval_enabled_eu: true` (config flag)
- CN region requires `pipl_notify_acknowledged_by[member_id]` (template at
  `docs/legal/PIPL-NOTIFY-TEMPLATE.zh.md`)
- Members can opt out via `opted_out_members` (PIPL §24 right) → permanent 403
- Eval scores are **resource-allocation hints**, never sole basis for HR action

### What's NOT in v1.1 (deferred)

- **LLM-distilled wiki**: `ome365 wiki update` is rule-based; LLM mode is v1.2
  (gated by `OME365_WIKI_LLM=1`)
- **Semantic search (sqlite-vec)**: opt-in only, requires bge-m3 (~2.27GB) — deferred
- **A2A signing**: `/.well-known/agent-card.json` advertises capabilities but
  `signed_by: null` until mindos.protocol integration (v1.2~v1.3)
- **Identity ed25519**: still v0.1 stub; v1.2 ships real signing
- **Roles framework UI editor**: v1.1 ships JSON config; visual editor in v1.2

### Migration from v1.0.0-rc1

No breaking changes. Adopting v1.1 surface is opt-in:
1. Run `./ome365 doctor` — should be green
2. Optionally seed `vault.example/` patterns into your real vault
3. Optionally enable the git hook: `git config core.hooksPath .githooks`
4. Visit `/v1_1.html` to see the new cockpit

---

## v1.0.0-rc1 — 顶级企业 AI 平台开源·阶段 1 launch 准备 19-round 收口 (2026-05-07 → 2026-05-08)

**Tagline**: Run your company on agents, not org charts.
**Sub**: Your AI follows the employee, not the employer.

> ⚠️ **诚实表述**: 这是 v3.6 §10 **阶段 1 launch 准备的 19-round 收口**·**不等于 v3.6 整体完工**。阶段 2 alpha (Hike L2 Event / L4 Cognition / L6 Swarm + PG+RLS + ome365.id/a2a 真签名) 计划 D+1 ~ D+45 (5-14 起) 实施。当前 ome365.id / ome365.a2a 是 v0.1 stub (schema + helpers + HTTP 路由 / 无签名 crypto) · 真签名集成与 mindos.protocol.a2a 在 D+5~D+12。

19-round iterative push. Zero regression across 14 GET endpoints + 4 share slugs throughout. **106 pytest tests passing** (was 62 before httpx fix). External AI patch r1.0 review (H1+H2+H4+H5) all addressed in Round 14-19.

### v1.0 ships (today · ready for 5-13 Show HN)
- Markdown vault + multi-tenant + 5 AuthProvider (none/basic/magic_link/oidc/wecom)
- Hike v0.1 entity graph (8 entity types · 9 + 5 alias endpoints · schema v0.2 五字段 forward-compatible)
- Share station with argon2 + Fernet + 3-word access codes + rename-resilient share_id
- ome365.id v0.1 stub (W3C DID + 4 Skill VC types · 6 endpoints · NO signing yet)
- ome365.a2a v0.1 stub (3-tier trust + SLA + Federation · 6 endpoints + /.well-known/agent-card.json · NO signing yet)
- 4 道 PII 防线 + 47-item fixture + GitHub Actions CI 5 jobs
- Apache License 2.0 (single-license · matrix-aligned)
- 4 法务 templates (DCO + DPA + AGPL Letter reserved + BSL EULA reserved)
- 5 行业 Hike starter (manufacturing / insurance / law-firm / retail / healthcare)
- 三平台 install (macOS/Linux/WSL) + --dry-run

### v2 lands (D+1 ~ D+45 · 5-14 ~ 6-30)
- Hike L2 Event Layer (meeting_dedupe_hash + actions)
- Hike L4 Cognition Layer (decision_chains + distilled.principles · 6-stage)
- Hike L6 Swarm (discover→suggest→review→adopt)
- HikeClient SDK + UI 4 page (Review queue / Distillation editor / Person profile / Decision timeline)
- PG+RLS Ome365 (import ome-server schema · multi-tenant e2e)
- ome365.id 真签名 (与 mindos.protocol.a2a 集成 · D+5~D+12)
- ome365.a2a Federation discovery + signed agent card (D+14~D+45)

### Highlights
- **Hike alias** (王牌产品收口): docs/hike.md + server.py docstring + README 顶级定位
- **Hike v2 schema v0.2** 五字段植入 entity_registry (100% backward compatible)
- **PII 4 道防线** scanner + 47-item fixture contract test
- **install.sh 三平台** (macOS/Linux/WSL) + --dry-run 安全模式
- **GitHub Actions CI** 5 jobs (pii-scan/syntax/smoke/install-matrix/unit-tests)
- **ISSUE/PR/Security** 模板套件 + DCO bot
- **CONTRIBUTING.md** + DCO 1.1 + 90-day roadmap + license dual-tier path
- **docs/legal/** 4 模板 (DCO/DPA/AGPL-Letter/BSL-EULA · ~600 行)
- **5 行业 starter** (manufacturing/insurance/law-firm/retail/healthcare)
- **ome365.id v0.1** stub (V1 真空带 · W3C DID + 4 Skill VC types · 220 行)
- **ome365.a2a v0.1** stub (V5 真空带 · 3-tier trust + SLA + Federation · 236 行)
- **62 contract tests** (test_ome365_id 20 + test_ome365_a2a 20 + test_scan_pii 5 + test_share_auth 16)

See README + docs/hike.md for full v2 architecture.
See docs/legal/AGPL-Compliance-Letter.md for enterprise legal review.

---

## v1.0.0-pre — 公开发布筹备 (2026-05-07 morning)

**目标：** 5/13 Show HN 公开发布。本版本是发布前的最后准备 pre-release。

**新增能力（自 v0.9.7 起）**
- **生活规划阅读器** — `.app/life_plan_routes.py` (787 LOC)
  - 把外部 Markdown 写的年度规划（profile / annual goals / weekly / daily / health rules）
    解析成结构化 view，挂在 `/api/life/plan/*` 下 10 个端点
  - 配套 `.app/life-plan-demo/2026/` 8 份 sample plan（Alice Example persona）
  - 用户私有 plan_dir 通过 `life_plan_config.json`（gitignored）配置
- **分享站密码保护** — `.app/share_routes.py` 扩 +545 LOC + `.app/share_auth.py` 420 LOC
  - argon2 密码哈希 + 三词访问码（170+ 词 wordlist）+ Fernet master_key 可逆加密
  - 4 个新端点：`/api/share/password/{enable,rotate,disable,info}`
  - 防文档漂移：`/api/share/by-path` 三层 fallback（path → frontmatter share_id → basename）
  - 文档注册时自动写入 `share_id` 到 frontmatter，改名/移动后仍能反查
- **truthguard 数据洁癖工具** — `skills/truthguard/` 套件 (567 + 871 LOC)
  - 用规则化 truth.yml（人名/组织/产品 canonicals）扫 PKM 仓里的 ASR 错听 / 笔误 / LLM hallucination
  - `scan` / `fix` / `lint` / `check` / `list` 子命令，CI 友好
- **CJK markdown 渲染兜底** — `.app/static/vendor/marked-cjk-fix.js`
  - Proxy 拦截 marked v15 parse，把粘连中文标点的粗体/斜体序列在 post-process 阶段补回 `<strong>` / `<em>`
- **单仓部署套件** — `infra/` (nginx + systemd + logrotate) + `scripts/` 8 个脚本
  - `build_share_vault.py` — 抽出注册过的 doc + 引用图片成最小 vault 子集
  - `deploy_share.sh` / `install-remote.sh` / `publish_to_remote.py` / `publish_static_to_remote.py`
  - `build_deploy_tarball.sh` / `upgrade-share-fix5.sh` / `backfill_view_audit.py`
- **GZipMiddleware** — JSON / HTML 响应自动 gzip，178KB markdown 实测 ~9x 压缩
- **Reports list 健壮化** — assets/ 子树自动跳过（不再把 build artifact 当报告）；
  composite frontmatter section 正则化为 top-level board key
- **/api/reports/file ETag/304** — 大文档重复加载从 ~200ms 降到一个 `If-None-Match` 头

**License + 元信息**
- 新增 `LICENSE`（MIT）— 之前 README badge 标榜 MIT 但仓里无 LICENSE 文件，本次补齐
- 新增 `tests/` (626 LOC) + `requirements.share.txt`（分享站独立依赖）

**全量隐私 + 历史重写**
- pre-launch 走 24 轮 PII 全维度审查，工作树 + git history blob + commit messages 全 0 hits
- `git filter-repo` 重写 80+ commits，去除所有真实公司/产品/人名/家庭信息
- `.gitignore` 加固：`share_auth.db` / `truth.yml` / 内部设计文档全部 gitignored

---

## v0.9.7 — 零摩擦安装 + 多租户隔离加固 (2026-04-18)

**一键装 / 一键起**
- 新增 `install.sh`：`curl -fsSL https://raw.githubusercontent.com/wyonliu/Ome365/main/install.sh | sh` 远程一行装完
- 新增 `./ome365` 极简启动器（Python 单文件，零第三方依赖）
  - `./ome365` — 首跑自动装依赖、复制 `.env`、起服务、开浏览器
  - `./ome365 --port 8080` / `--no-open` / `--setup`
  - `./ome365 doctor` — 自检依赖 / 端口 / tenant 配置
  - `./ome365 setup` — 转交 `setup.sh` 向导（family / demo / enterprise）
- README 改用 `./ome365` 作为首选路径，`setup.sh` / Docker 降为"其它场景"

**多租户 HTTP 隔离**
- 修 `/t/{tid}/...` path-prefix 没剥前缀 → 请求落到 `default` 租户的 bug
- `AuthMiddleware` 解析 tenant 后缓存到 `request.state.tenant_id`，`resolve_tenant_id()` 优先读缓存（路径剥掉后不会再误解析）
- `basic_provider` / `magic_link_provider` 补上跨租户 session 拒绝逻辑（`u.tenant_id != self.tenant_id → None`），与 OIDC / Wecom 对齐

**测试**
- E2E 从 75 扩至 **110 项**，新增 6 套：
  - `suite_session_gc` ×5 — SQLite session TTL / 撤销 / 懒 GC
  - `suite_cookie_secure_header` ×3 — Secure flag 默认开 / `OME365_COOKIE_SECURE=0` 覆写 / HttpOnly
  - `suite_http_multitenant` ×14 — 真实起 server，`$OME365_HOME/tenants/{acme,globex}/` 双租户，验证 header / subdomain / path-prefix 三种路由 + 跨租户 cookie 拒绝
  - `suite_http_magic` ×5 — Magic Link 真链路（`OME365_MAGIC_LINK_SINK_FILE` sink + `safe_next_url` 开放跳转防御）
  - `suite_http_oidc` ×4 — stdlib 起 Mock IdP（OIDC discovery / JWKS / Authorization Code + PKCE）
  - `suite_cli_ome365` ×4 — `./ome365` 冒烟（启动 / 端口释放 / `--no-open` / `doctor`）
- CI：`scripts/test_multitenant_e2e.py` 110 / 110 绿

**修掉的坑**
- macOS / BSD 端口 TIME_WAIT 让 CLI 重启立挂 → `SO_REUSEADDR`
- 系统代理截 127.0.0.1 OIDC mock → `NO_PROXY=localhost,127.0.0.1`
- bash UTF-8 全角括号邻接变量名 → `${VAR}` 花括号包住（install.sh）

## v0.9.6 — AuthProvider 抽象 + 一键部署向导 (2026-04-18)

- none / basic / magic_link / oidc / wecom 5 种 auth provider
- SQLite session store（可撤销 / TTL / 懒 GC）
- `./setup.sh` 交互向导：solo / family / demo / enterprise 四场景
- Docker compose profile
- 29 项 E2E 全绿

## v0.9.5 — 完全多租户抽象 (2026-04-18)

- 去业务耦合：模版占位符替换真实租户名
- tenant_config 三件套（live / sample / fallback）
- 4 条 cockpit 路由跨租户可用
- 默认主题改回通用 `light`

## v0.9.4 — 同事可用性 + 数据仓重构 (2026-04-17)

- requirements / .env.example / mcp / share / hook / PORT 补齐
- vault 根目录 + TicNote 归位，53 访谈零破坏

## v0.9.3 — 隐私清理事件 (2026-04-17)

- 47 项 PII 清理，filter-repo B 方案
- 双仓重构：`Ome365-git`（源码）/ `Ome365`（数据 vault）

## v0.9 — Enterprise Entity Graph (2026-04)

- 企业实体图一级能力
- ASR / RAG / Memory / 驾舱共用事实源

## v0.8 — AI 智能速记

见 README 展开项。
