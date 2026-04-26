# intervals-icu-mcp — Build Roadmap

## Goal

Ship a minimal, personal-use Python MCP server that wraps the intervals.icu REST API and exposes the 12 tools the AITrainer skill set already references. Match the design layer's expectations on tool names (snake_case), env vars (`INTERVALS_API_KEY` only), and entry point (`uv run intervals-icu-mcp`). Don't build for multi-tenancy or third-party redistribution — this is one athlete's local tool.

## Recon results (already done)

- **Auth**: HTTP Basic, username = literal string `API_KEY`, password = generated API key from `intervals.icu/settings → Developer Settings`. **Correction to earlier wiring**: `INTERVALS_ATHLETE_ID` env var is **not** needed; athlete-id `0` in paths means "me".
- **Base URL**: `https://intervals.icu/api/v1/`
- **Date format**: ISO 8601 (`2026-04-25`).
- **Path conventions**: `/athlete/0/activities?oldest=DATE&newest=DATE`, `/athlete/0/wellness?oldest=DATE&newest=DATE`, `/activity/{id}/file`, etc.
- **Endpoints confirmed in cookbook**: list activities, upload activity, fetch activity file, read/write wellness, webhooks.
- **Endpoints inferred but not yet verified**: get-one activity, activity streams, events CRUD, fitness curve, FTP history, athlete profile. Will discover via Swagger UI hitting the live API in Phase 2.
- **Quirks**:
  - Wellness fields synced from external services (Oura, etc.) revert unless `locked: true` is set. Skills should not write wellness; if they do, set `locked` explicitly and confirm.
  - Some endpoints return gzipped bodies.
  - All units metric.
  - Athlete `0` resolves to the authenticated user.
- **Rate limits**: not documented in the cookbook or forum guide. Will add a simple in-memory throttle later if needed.
- **OAuth**: irrelevant for personal use. Skip.

## Phase plan

### Phase 0 — Recon (✅ done in this turn)
Done. Findings above are the basis for the rest of the plan.

### Phase 1 — Scaffolding (✅ done in this turn)
- Repo at `AITrainer/intervals-icu-mcp/` with `git init` (local-only — push to GitHub when explicitly asked).
- `pyproject.toml` declaring deps (`mcp`, `httpx`, `pydantic`), `requires-python >= 3.11`, entry script `intervals-icu-mcp`.
- Package skeleton: `intervals_icu_mcp/{__init__,client,models,formatters,server}.py` with module docstrings and `TODO(phase-N)` markers.
- `tests/`, `.gitignore`, `.python-version`, `README.md`, this `ROADMAP.md`.
- First commit: `scaffold: project skeleton + roadmap`.

### Phase 2 — Live-API endpoint discovery (~30 min, requires INTERVALS_API_KEY)
- With a real API key, hit each suspected endpoint via `curl -u API_KEY:$KEY` to confirm path, query params, and response shape.
- Capture sample responses to `tests/fixtures/` (sanitized — strip personal IDs).
- Write `RECON.md` documenting actual endpoints + payload shapes.
- **Output**: deterministic endpoint list with payload schemas. No code yet.

### Phase 3 — Client layer (~1 hour)
- `client.py`: `IntervalsClient(api_key)` using `httpx.Client(auth=("API_KEY", api_key), base_url="https://intervals.icu/api/v1/")`.
- One method per endpoint group, returning parsed JSON.
- Error mapping: 401 → `AuthError`, 403 → `ForbiddenError`, 404 → `NotFoundError`, 429 → `RateLimitError`, 5xx → `UpstreamError`. All inherit from `IntervalsAPIError`.
- Sync methods for v1 — async adds complexity without real benefit for one user.
- Unit tests: mock httpx via `respx`, verify auth header + URL construction + error mapping.

### Phase 4 — Models layer (~30 min)
- `models.py`: one Pydantic v2 `BaseModel` per tool input. `model_config = ConfigDict(extra="forbid")`.
- Date fields typed as `datetime.date` with ISO-8601 validation.
- Enums for event `type` and `category` once Phase 2 confirms the allowed values.

### Phase 5 — Formatters (~30 min)
- `formatters.py`: per-response-shape Markdown formatters + JSON passthrough.
- **Critical**: `format_activity_streams` must downsample by default (e.g., 5-second buckets) to fit Claude's context budget. Raw stream available with `format="json"`.

### Phase 6 — Server (~1 hour)
- `server.py`: one `@mcp.tool()` per tool, decorated with proper `readOnlyHint` / `destructiveHint`.
- Read-only (9): `list_activities`, `get_activity`, `get_activity_streams`, `list_events`, `get_event`, `get_wellness_range`, `get_fitness_curve`, `get_ftp_history`, `get_athlete_profile`.
- Write (2, neither read nor destructive): `create_event`, `update_event`.
- Destructive (1): `delete_event`.
- Each tool: validate input via Pydantic → call client → format response.
- `main()` initializes the server and starts stdio transport.

### Phase 7 — Smoke test with live API (~15 min)
- `uv run intervals-icu-mcp` launches the server.
- Pipe `tools/list` JSON-RPC request — confirm 12 tools registered with correct annotations.
- Call `get_athlete_profile` — confirm auth works, response parses.
- Call `list_activities` with `limit=1` — confirm date-range filter and paging work.
- **No write tools called in smoke test.** Writes go through the harness `permissions.ask` gate.

### Phase 8 — Tests + integration with AITrainer (~1 hour)
- pytest unit suite (client, models, formatters) — ~25 tests, fully mocked, fast.
- Integration tests gated on `INTERVALS_API_KEY` env var, read-only.
- Update `AITrainer/CLAUDE.md` `## MCP Tool Index` to reflect any tool-name corrections discovered in Phase 2.
- Update `AITrainer/SETUP.md` to drop `INTERVALS_ATHLETE_ID` env var (not needed).
- Update `AITrainer/.mcp.json` to drop `INTERVALS_ATHLETE_ID` from the `intervals-icu-jan` env block.
- Verify end-to-end from a fresh Claude Code session: `/mcp` shows `intervals-icu-jan` connected, `daily-readiness` skill invokes successfully.

## Self-critique — does this plan actually achieve what we want?

### What I'm worried about

1. **`get_fitness_curve` may not be a single endpoint.** CTL/ATL/TSB are usually computed from training history. If intervals.icu doesn't expose a dedicated curve endpoint, this tool becomes a wrapper around `/wellness?cols=ctl,atl,form,...` (the cookbook hints wellness has these columns). Either way, the tool surface stays the same; the implementation may differ from a simple GET. **Acceptable risk.**

2. **Activity stream size.** intervals.icu can have multi-hour activities with 1Hz streams = thousands of points × ~5 fields. Returning raw to Claude blows context. Fix: downsample by default in `format_activity_streams`. **Designed for; not a real risk.**

3. **Event `type` field values.** The cookbook didn't list them. If intervals.icu rejects `WeightTraining` (the type my `log-strength-session` skill uses), the strength→intervals.icu mirror breaks. Fix: Phase 2 enumerates allowed values; if `WeightTraining` isn't valid, fall back to `Other` and document.

4. **Date timezone.** intervals.icu uses athlete-local time. "Today" from Claude's perspective = UTC midnight, which can be off-by-one. Fix: Phase 6 reads timezone from `get_athlete_profile` once at server start, applies to date math.

5. **Sync vs async.** I chose sync for v1 simplicity. If the user later runs many MCP queries in parallel, this becomes a bottleneck. **Acceptable for personal use.** Refactor only if it bites.

6. **Wellness `locked` gotcha.** If a future skill writes wellness and the user has Oura syncing, the write will silently revert. Out of scope for v1 (no skill writes wellness yet), but worth flagging when it comes up.

7. **No telemetry / Sentry.** Deliberate — security review on Hevy MCP showed Sentry as a privacy risk. This server ships zero telemetry. **Documented in README.**

8. **`update_event` and `delete_event` are scoped in but no skill currently uses them.** Including them costs ~20 lines each but pre-builds the surface for `weekly-planning v2` (revising a planned week). The harness `permissions.ask` already gates them. **Worth including.**

9. **One developer, no peer review.** Mirrors the design-layer build risk. Mitigation: smoke test with live API in Phase 7 before claiming done. Let the user catch what I miss.

10. **Scope creep risk: webhooks.** The cookbook covers webhooks for receiving events from intervals.icu. They're outside MCP's request-response model. Skipping in v1 — if the user later wants "notify me when an activity uploads", that's a separate component, not an MCP tool. **Out of scope.**

### What this plan does *not* do (deliberately)

- No OAuth — personal API key only.
- No multi-tenant — single athlete ID resolved once via `GET /athlete/0` and cached, or read from `INTERVALS_ATHLETE_ID` if set.
- No HTTP/SSE transport — stdio only.
- No webhooks.
- No wellness writes (skills don't need them yet).
- No structured-workout file (.fit / .zwo) generation — `create_event` accepts free-text descriptions. Structured workouts deferred to v2 if needed.
- No caching layer in v1. Add only if rate limits bite.

## Open questions for you

1. **GitHub or local-only?** The repo is currently local. Push to a private GitHub repo, or stay on disk? (Default: local-only; you can `gh repo create` later.)
2. ~~**Drop `INTERVALS_ATHLETE_ID` everywhere?**~~ **Resolved**: required. First pass tried lazy auto-discovery via `GET /athlete/0` — user (correctly) pushed back that the response shape was unverified, so we'd be shipping unproven code on a path the writes depend on. Switched to required-at-startup. py-intervalsicu does the same. Server fails fast with a clear message if missing.
3. **Activity stream downsampling default rate** — 5-second buckets feels right for a multi-hour ride. Faster (1s) blows context; slower (30s) loses interval-level detail. Default 5s? You can override per-call.
4. **`WeightTraining` event type** — confirm this is the actual intervals.icu enum value. (I'll verify in Phase 2; flagging now in case you know.)

## What I'll do next if you approve

Phase 2 — live-API discovery. I'll need `INTERVALS_API_KEY` set in the environment. Set it via `setx INTERVALS_API_KEY "..."` in your terminal (don't paste it in chat) and let me know it's set; I'll run a series of read-only `curl` calls and write up `RECON.md` with the actual endpoint shapes. After that I move on to Phase 3 (client implementation).

If anything in this plan looks wrong, push back before I start Phase 2 — easier to change scope now than after I've written code against the wrong assumptions.
