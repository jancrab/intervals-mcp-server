# intervals-icu-mcp — Comprehensive coverage roadmap

## Goal

Expand from the **12 tools** that cover the AITrainer skill needs (shipped — see `ROADMAP.md`) to **full coverage of every intervals.icu API endpoint relevant to a single authenticated athlete**.

## Scope

**In scope** (single authenticated athlete):
- Every CRUD operation on the user's own activities, events (planned workouts), wellness, workout templates, folders, calendars
- Every read endpoint for the user's own training data
- File operations (upload activity, download FIT)
- Power curves, fitness/training-load views, athlete-profile mutations
- Settings and preferences the API allows the user to read/update

**Out of scope** (deferred or rejected):
- OAuth app management (registering apps, managing tokens) — personal API key only
- Multi-athlete / followed-athlete queries — single athlete via `INTERVALS_ATHLETE_ID`
- Coach / client management endpoints
- Webhook subscriptions — push model, doesn't fit MCP request/response. Re-evaluate after Phase A inventory.
- HTTP/SSE transport — stdio only

## Status

| Phase | Status |
|---|---|
| 0–7 (base server, 12 tools, smoke-tested) | ✅ done — see `ROADMAP.md` |
| **A. Comprehensive endpoint inventory** | 🔄 **in flight via subagent** — output to `ENDPOINT_INVENTORY.md` |
| B. Scope confirmation | ⏳ waits for Phase A |
| C. Read-only tool expansion | ⏳ |
| D. Write tool expansion | ⏳ |
| E. File operations (multipart upload, gzipped download) | ⏳ |
| F. Webhooks decision | ⏳ |
| G. Test suite | ⏳ |
| H. End-to-end integration verification | ⏳ |
| I. Documentation + version tag | ⏳ |

## Phase detail

### Phase A — Comprehensive endpoint inventory (subagent task)

Subagent fetches `https://intervals.icu/api/v1/docs/v3/api-docs` (returned `200` in probes — the actual OpenAPI JSON spec, not the JS-rendered Swagger UI). Parses every path, categorizes, cross-references with the existing 12 tools, and produces:

```
intervals-icu-mcp/ENDPOINT_INVENTORY.md
├── ## Already covered (the 12 v1 tools, recap)
├── ## To ADD (per endpoint: proposed snake_case MCP tool name, HTTP method+path,
│              summary, params, response shape, single-user relevance, gotchas)
├── ## To SKIP (per endpoint: reason — multi-tenant, OAuth-only, etc.)
└── ## Quirks summary (gzip, multipart, pagination, rate limits, etc.)
```

No destructive API calls. No live user data accessed. Spec parsing only.

### Phase B — Scope confirmation

User reviews `ENDPOINT_INVENTORY.md`. Decisions to make:
1. Anything in "To ADD" that we should drop?
2. Anything in "To SKIP" that we should reconsider (esp. webhooks)?
3. Implementation order — alphabetical, or by dependency / value?

### Phase C — Read-only tool expansion

Each new GET tool gets:
- Method on `IntervalsClient` (client.py)
- Pydantic input model with `extra="forbid"` (models.py)
- Markdown formatter + JSON passthrough (formatters.py)
- `@mcp.tool()` registration with snake_case name + `readOnlyHint=True` (server.py)

**Likely candidates from the inventory** (subagent confirms):
- `list_workouts`, `get_workout` (workout templates, separate from events)
- `list_folders`, `get_folder` (organize templates)
- `list_calendars`
- `get_power_curve` (probed — `/athlete/0/power-curves` returns 422 on missing params)
- `download_activity_file`, `download_activity_fit_file` (gzipped binary — see Phase E)
- Any other GET endpoint the inventory surfaces

### Phase D — Write tool expansion

Standard pattern: POST/PUT/DELETE method on client, Pydantic model, formatter, server registration.

**Likely candidates**:
- `create_workout`, `update_workout`, `delete_workout` (templates)
- `create_folder`, `update_folder`, `delete_folder`
- `update_activity` (PATCH-style edits — descriptions, RPE, etc.)
- `update_wellness`, `update_wellness_bulk` (with the `locked: true` gotcha from cookbook)
- `update_athlete_profile` (settings, sport zones, etc. — depends on what API allows)

**Defense-in-depth** is already in place upstream:
- Skill-level confirmation gates (echo + "yes")
- `permissions.ask` rules in `~/.claude/settings.json` for `create_*` / `update_*` / `delete_*`
- `PostToolUse` audit hook writes JSONL to `AITrainer/audit.log`

For **wellness writes specifically**: every write must explicitly set `locked: true` in the payload, and the formatter that echoes the structure to the user must surface this clearly. Otherwise Oura/Garmin sync will overwrite the API change minutes later.

### Phase E — File operations

Two distinct shapes:

**Multipart upload** — `POST /athlete/0/activities` with `multipart/form-data`. Accepts FIT/TCX/GPX (or zipped). Tool would be `upload_activity(file_path, name?, description?, external_id?)`. Skill-level question: does Claude have a use case here, or is this a CLI-only convenience? Probably skip unless inventory suggests otherwise.

**Gzipped download** — `GET /activity/{id}/file` and `/activity/{id}/fit-file` return gzipped FIT/TCX/GPX. Tools: `download_activity_file(activity_id, dest_path)` writes the file to disk. Useful for raw-stream parsing (the deferred v2 of `get_activity_streams`).

### Phase F — Webhooks decision

Re-evaluate after Phase A inventory. Webhook subscriptions are admin operations, not training operations, so they likely don't belong in an MCP that's primarily about reasoning over training data. Tentative: **skip**, document as out of scope.

### Phase G — Test suite

Targets:
- Unit tests via `respx` (mocked httpx) — cover every client method, every error path, every formatter against fixture responses
- Models tests — `extra="forbid"` rejection, date parsing, enum validation
- Integration tests gated on `INTERVALS_API_KEY` env var, read-only only
- One controlled write-cycle integration test: `create_event` → assert it appears in `list_events` → `delete_event` → assert it's gone. Gated behind a more explicit `INTERVALS_ALLOW_WRITE_TESTS=1` env var.

Coverage target: 80%+. Tests run in <5s for the unit suite.

### Phase H — End-to-end integration

Fresh Claude Code session inside `AITrainer/`. Verify:
- `/mcp` lists `intervals-icu-jan` connected with all tools (12 → ~30+)
- `daily-readiness` skill auto-invokes on "should I train today?", produces 5-line verdict
- `weekly-planning` proposes a markdown table, prompts for confirmation, harness `permissions.ask` fires per write, audit.log captures each
- `log-strength-session` round-trip: parse → confirm → harness ask → Hevy create-workout → harness ask → intervals.icu `create_event` mirror
- `post-workout-debrief` against the user's most recent ride

If any tool name in `AITrainer/CLAUDE.md` `## MCP Tool Index` doesn't match what the server now exposes, update the index — that's the single source of truth the skills cite.

### Phase I — Documentation + version tag

- `README.md` — full tool inventory in a table, organized by domain
- `AITrainer/CLAUDE.md` `## MCP Tool Index` — sync to actual exposed tools
- `CHANGELOG.md` — record what changed from v1.0
- Git tag `v1.5.0` (or `v2.0.0` if API breaks)

## Effort estimate

| Phase | Estimate | Notes |
|---|---|---|
| A. Inventory | 30 min subagent runtime + 10 min review | Mostly automated |
| B. Scope confirmation | 15 min | User decision |
| C. Read tools | ~2h | ~10 new tools likely |
| D. Write tools | ~2h | ~10 new tools likely |
| E. File ops | ~1h | Multipart + gzip handling |
| F. Webhooks decision | ~15 min if defer, +2h if implement | Probably defer |
| G. Tests | ~3h | The biggest single chunk |
| H. Integration | 1h | Real-world exercise |
| I. Docs + tag | 30 min | |
| **Total** | **~10h focused work** | Spread over multiple sessions |

## Hard blockers from earlier (subsumed by this plan)

The three blockers I flagged previously:
1. Verify write endpoints actually work — covered by Phase G's controlled write-cycle test
2. Unit tests for current 12 tools — covered by Phase G
3. End-to-end Claude Code integration — covered by Phase H

So this plan supersedes the earlier "what's left for v1 final" list. Everything still gets done, just rolled into the broader expansion.

## Decision points along the way

1. After Phase A: confirm scope (drop anything? add anything?)
2. After Phase D: do we want webhooks or skip?
3. After Phase H: any field-name truths discovered that require formatter updates?
4. Before Phase I: bump to v1.5 or v2.0?
