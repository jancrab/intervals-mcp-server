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
| A. Comprehensive endpoint inventory | ✅ done — see `ENDPOINT_INVENTORY.md` |
| B. Scope confirmation | ✅ done |
| C. Read-only tool expansion | ✅ done — Waves 1–4 (commits `de89263`, `f1fa511`, `f7f5e4f`, `365067b`) |
| D. Write tool expansion | ✅ done — same waves |
| E. File operations (multipart upload, gzipped download) | ✅ done — Wave 5 (`19e920e`) |
| F. Webhooks decision | ✅ skipped (out of scope, documented in `ENDPOINT_INVENTORY.md`) |
| G. Test suite | ✅ done — 179 unit tests passing |
| H. End-to-end integration verification | ✅ done — skills + permissions.ask + audit hook wired |
| I. Documentation + version tag | ✅ done — README, CHANGELOG, tagged v1.2.0 |
| **J. Profile gate (lean / full) + aggregator fat-tools** | ✅ done — commits `19e920e` (profile gate), `a4d0c2e` (`get_activity_full_report`) |
| **K. DXT packaging + Claude Desktop one-click install** | 🔄 **in flight** — manifest exists; need `.dxt` build + verify |

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

### Phase J — Profile gate + aggregator fat-tools (✅ done)

Recognized that 134 tools × ~330 tokens of schema each = ~44 k tokens locked into the system prompt on every turn — a quarter of a Claude Desktop context window before "hello." Two layered solutions, both shipped:

**Profile gate** (`tools/profile.py`, `INTERVALS_PROFILE` env var):
- `lean` (default) — 28 high-value tools, ~10.9 k tokens of schema
- `full` — all 134 tools, ~43.9 k tokens
- Switching: edit env, restart MCP host. DXT user-config UI exposes a `profile` dropdown so non-CLI users don't edit JSON.
- Anything other than the literal `"full"` (case-insensitive) falls back to lean — typo-resistant.

**Aggregator fat-tools** (`tools/aggregators.py`):
- `get_activity_full_report` — one tool, eight parallel `asyncio.gather` subcalls (details, intervals, messages, power curve, HR curve, best efforts, segments, weather; streams toggleable). Per-section failures surface inline; one bad endpoint doesn't poison the report.
- Replaces ~7 sequential tool calls in the post-workout-debrief workflow with one parallel fetch. ~1.4 k tokens of schema cost vs the model deciding to call 8 tools individually.

Pattern is reusable: future aggregators (`get_weekly_summary` for weekly-planning, `get_readiness_snapshot` for daily-readiness) can follow the same shape.

### Phase K — DXT packaging + Claude Desktop one-click install (in flight)

**Goal**: ship a single `.dxt` file users (incl. you on a clean machine, or a friend you hand the fork to) can double-click in Claude Desktop to get the MCP installed and configured — no manual `claude_desktop_config.json` editing, no env-var setup, no `uv sync` from a terminal.

**Manifest** (✅ done, in `manifest.json`):
- DXT v0.1 schema, version `1.2.0`, GPL-3.0-only
- Server type `python`, runs `uv --directory ${__dirname} run python -m intervals_mcp_server.server`
- User-config fields: `api_key` (sensitive, required), `athlete_id` (required), `profile` (default `lean`, optional), `log_level` (default `INFO`, optional)
- `compatibility.platforms`: `darwin`, `linux`, `win32`
- All env vars wired from `${user_config.*}` → `mcp_config.env`

**Remaining work** (do this in one focused session):

1. **Validate manifest against the DXT JSON-Schema.**
   - Pull the latest published schema from the Anthropic DXT spec (URL in DXT docs — fetch fresh, don't trust memory).
   - Run `npx -y @anthropic/dxt-validator manifest.json` (or the equivalent — confirm the package name when fetching docs).
   - Fix any field-shape errors. Common ones: `dxt_version` mismatch, `mcp_config.env` value types, `user_config` enum vs free-text mismatch.

2. **Build the `.dxt` archive.**
   - DXT is a renamed `.zip` of the package directory. Decide what to bundle:
     - **MUST include**: `manifest.json`, `pyproject.toml`, `uv.lock`, `src/`, `README.md`, `LICENSE`, `CHANGELOG.md`
     - **SHOULD exclude**: `.git/`, `tests/`, `.venv/`, `__pycache__/`, `.env*`, `audit.log`, `*.dxt`, `dist/`, `RECON.md`, `ENDPOINT_INVENTORY.md` (internal-only), `FULL_API_ROADMAP.md` (this file)
   - Add a `.dxtignore` (mirror `.gitignore` patterns) and a `Makefile` target / `pyproject.toml` script:
     ```
     uv run python -c "import zipfile, pathlib; ..."  # or just call zip with explicit excludes
     ```
   - Output: `dist/intervals-icu-jan-1.2.0.dxt`. Size sanity check: <5 MB excluding `.venv/`.

3. **Smoke install on a clean Claude Desktop profile.**
   - macOS: drag `.dxt` onto Claude Desktop. Confirm it surfaces:
     - Display name "intervals.icu (jan fork)"
     - User-config dialog with API-key (masked), athlete-ID, profile dropdown, log-level dropdown
     - "Install" button completes without error
   - Verify DXT writes correct `claude_desktop_config.json` entry (literal env values, not `${...}` placeholders — Desktop on Windows is unreliable with substitution).
   - Restart Desktop. Confirm `intervals-icu-jan` appears in the MCP list, status `connected`.
   - Run a smoke prompt: "show my last activity" → expect `get_activities` (lean) to fire and return data.
   - Flip profile dropdown to `full` in Settings → Extensions → restart → confirm tool count jumps from 28 to 134.

4. **Windows + Linux equivalent smoke** (lower priority — fork is Windows-primary, but at least confirm the manifest's `platforms` declaration isn't lying).

5. **Document the install flow in README.md.**
   - Currently the README has placeholder DXT install steps. Replace with:
     - Where to download the `.dxt` (GitHub Releases attachment on the v1.2.0 tag)
     - Exact double-click flow + screenshot of the user-config dialog
     - How to flip profile post-install (Settings → Extensions → intervals-icu-jan → "Tool profile")
     - Troubleshooting: "uv not on PATH" (DXT needs the host `uv`; mention `pipx install uv` or homebrew), "API key rejected" (regenerate at intervals.icu Settings → Developer Settings).

6. **Cut a GitHub release.**
   - Tag `v1.2.0` on `main`.
   - Attach the `.dxt` file + signed checksum (`shasum -a 256`).
   - Release notes pulled from `CHANGELOG.md` v1.2.0 section.

**Open questions** to resolve before/during this phase:
- Does DXT bundle the Python interpreter, or rely on host `uv` + system Python? Manifest currently assumes host `uv`. Confirm vs the DXT spec; if it bundles, package size jumps significantly and we may need a separate `python.bundled: true` mode.
- Does the user-config UI render `enum` for the profile dropdown, or just free-text? Manifest currently uses `type: "string"` with a description — may need `enum: ["lean", "full"]` for a true dropdown. Test in step 3.
- Sensitive-field handling on Windows — does DXT use Credential Manager, or write the API key to plaintext in `claude_desktop_config.json`? If plaintext, document the risk in README.

**Definition of done**: a clean-machine user installs by double-clicking the `.dxt`, fills three fields, clicks Install, restarts Desktop, asks "what's my FTP?" and gets an answer. No terminal touched.

## Effort estimate

| Phase | Estimate | Status | Notes |
|---|---|---|---|
| A. Inventory | 30 min subagent runtime + 10 min review | ✅ done | Mostly automated |
| B. Scope confirmation | 15 min | ✅ done | User decision |
| C. Read tools | ~2h | ✅ done | Shipped: ~75 read tools across waves 1–4 + base |
| D. Write tools | ~2h | ✅ done | Shipped: ~50 write tools across waves 1–4 |
| E. File ops | ~1h | ✅ done | Wave 5 — multipart upload + binary download (9 tools) |
| F. Webhooks decision | ~15 min if defer | ✅ skipped | Out of scope for personal use |
| G. Tests | ~3h | ✅ done | 179 unit tests passing |
| H. Integration | 1h | ✅ done | Skills + permissions.ask + audit hook wired |
| I. Docs + tag | 30 min | ✅ done | README, CHANGELOG, v1.2.0 |
| J. Profile gate + aggregator fat-tools | ~2h | ✅ done | Driven by context-cost realization mid-build |
| K. DXT packaging + Desktop install | ~2h | 🔄 in flight | Manifest done; build + smoke + release pending |
| **Total** | **~14h actual** | ~12h done, ~2h remaining | DXT packaging is the last lap |

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
