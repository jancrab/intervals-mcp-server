# Changelog

This fork tracks divergence from upstream `mvilanova/intervals-mcp-server`. See `git log upstream/main..HEAD` for the precise diff.

## [Unreleased]

_Nothing yet._

## [1.3.2] — 2026-04-29 — Sharpened 422 handling on `link_activity_to_event`

### Changed

- **`link_activity_to_event`** now translates HTTP 422 responses to a structured `{"status": "draft_unrecoverable", "message": ...}` shape, mirroring v1.3.0's pattern for `get_activity_intervals` (which uses `"status": "draft"`). The new status is distinct because it's a stronger statement: the activity is past the point where the link endpoint can help. The message includes the activity's web URL and the manual-rename remediation. Other 4xx/5xx responses retain v1.3.1's verbatim-API-message envelope so genuine failures (404, 401, 500, etc.) aren't masked behind the draft-unrecoverable wording.
- **Tool description** for `link_activity_to_event` now explicitly documents the v1.3.2 limit: the link endpoint cannot recover activities in deep pre-normalization (raw integer ID, no `i…` prefix). Such activities require manual save via intervals.icu's web UI.

### Added

- **README troubleshooting entry** documenting the orphan-pre-normalization case, the typical Zwift-built-in-test trigger (Zwift→Strava→intervals.icu sync path appears to bypass normalization), and the manual-save remediation.

### Fixed

- **`get_event_by_id`** rendering: `Date: Unknown` was shown for events that have a `start_date_local` field but no top-level `date` field. The `format_event_details` formatter now uses the same fallback chain as `format_event_summary` (`start_date_local` → `date` → "Unknown"). Aligns the by-id path with the list path.

### Why

Reported on 2026-04-29 after a v1.3.1 smoke test against today's orphan FTP test activity (`18303442074`). The new `link_activity_to_event` tool returned 422; intervals.icu's link endpoint requires the activity to already be normalized (canonical `i…` ID), which is exactly the state we wanted to force. No alternate API path has been verified yet (separate investigation parked); v1.3.2 documents the limit honestly and points users at the manual UI remediation. The `get_event_by_id` Date fix was bundled because it's a one-line align-with-existing-pattern change uncovered while diagnosing.

### Migration

None required. Drop-in upgrade.

## [1.3.1] — 2026-04-29 — `link_activity_to_event` tool + sharpened draft message + `get_event_by_id` fix

### Added

- **`link_activity_to_event(activity_id, event_id)` tool** (lean profile) — write-side tool that links an activity to a planned event on intervals.icu by PUTing `{"paired_event_id": <int>}` to `/activity/{id}`. Use when an activity is stuck in pre-normalization state because of a workout-structure mismatch (typically a Zwift stock workout run instead of the prescribed `.zwo`). Forces normalization on intervals.icu's side; subsequent reads return full power/HR/duration data. Validation: `activity_id` non-empty, `event_id` parses as a positive integer — raises `ValueError` before any API call. Returns a structured JSON envelope (`{"status": "linked", ...}` on success; `{"status": "error", "http_status": <int>, "message": "<API verbatim>"}` on failure). API error wording is preserved verbatim — different 422 reasons exist (already paired, structure mismatch, athlete mismatch) and over-translation loses information.

### Changed

- **Sharpened draft-state remediation message** in `format_activity_summary` (v1.3.0) to distinguish the orphan-Zwift-workout case (resolved by `link_activity_to_event`) from generic stuck uploads (resolved by manual rename + save in the web UI). The URL line and ID line are preserved in their v1.3.0 positions; existing tests for those still pass.

### Fixed

- **`get_event_by_id` 404 bug** — the tool was constructing `/athlete/{id}/event/{eventId}` (singular `event`), which returned 404 for IDs that `get_events` listed cleanly. Aligned with the canonical `/athlete/{id}/events/{eventId}` (plural, per OpenAPI spec). Confirmed today against event ID `107189636`.

### Why

Reported on 2026-04-29 after a Zwift FTP test (activity `18303442074`) landed orphan: user ran Zwift's stock 20-min FTP test instead of the prescribed `.zwo`, the upload couldn't auto-link to the planned event, and even after rename it stayed in pre-normalization state. v1.3.0's "rename and save" guidance does not unstick orphans because intervals.icu treats them as structurally unmatched, not just missing-name. The link tool resolves this case in one call. The sharpened draft message points the model at the tool when an orphan is detected. The `get_event_by_id` 404 was a separate bug uncovered during the same diagnosis (couldn't fetch event detail for the planned FTP test to construct the link call) and was bundled because adjacent.

### Migration

None required. Drop-in upgrade — download `intervals-icu-jan-1.3.1.mcpb`, double-click, restart Claude Desktop / Cowork. Existing config preserved.

## [1.3.0] — 2026-04-29 — Pre-normalization stub detection

### Added

- **Draft-state activity detection** in `format_activity_summary`. Activities that are uploaded to intervals.icu but haven't completed normalization (e.g. fresh Zwift uploads sitting in upstream-ID limbo) now render as a 7-line remediation message pointing to the activity's web URL, instead of 60 lines of "N/A" that look like a fetch failure. Detection fires when the activity ID is an int or lacks the `i…` prefix, OR when name/type/start_date_local are all missing.
- **Structured 422 handling** in `get_activity_intervals`. intervals.icu returns 422 Unprocessable on intervals queries against pre-normalization activities; the tool now surfaces this as a structured `{"status": "draft", "message": ...}` response instead of leaking the raw API error. Other 4xx/5xx responses keep their existing wording so real failures aren't masked.

### Why

Reported by `cowork-telegram-mcp` author after a Zwift FTP test on 2026-04-29 returned an empty stub through the MCP while showing full data in the web UI. Cross-checked against eight prior planned-event-paired completions (Apr 1, 3, 6, 9, 12, 15, 17, 19) — all normalized cleanly. Discriminator was the upload's pre-normalization state, not event-pairing. Manual save in the web UI forces normalization. The fork now self-explains this when it sees the signature.

### Migration

None required. Drop-in upgrade — download `intervals-icu-jan-1.3.0.mcpb` from the release, double-click, restart Claude Desktop / Cowork. Existing config preserved.

## [1.2.0] — 2026-04-27

First public release of the fork. MCPB-installable Claude Desktop extension shipped on this tag.

### Added

- **Aggregator tool** `get_activity_full_report` — fetches 8 per-activity endpoints in parallel (details, intervals, messages, power curve, HR curve, best efforts, segments, weather; streams optional) and returns a single consolidated markdown report. Trades one tool's worth of schema (~1.4 k tokens) for ~7 saved tool-call decisions in the post-workout debrief workflow. Per-section failures surface inline as `_(unavailable: ...)_` without cancelling the rest of the report.
- New `tools/aggregators.py` module + an `Aggregators` domain in the inventory table.
- `create_manual_activity` added to `lean` so logging an after-the-fact session works without flipping to `full`.
- **Cycling-coaching gap-fillers in lean (research-driven).** After a skeptical research subagent reviewed Coggan/Friel/TrainingPeaks/Skiba primary sources, 95 % of per-workout coaching scalars (TSS / IF / NP / VI / EF / kJ / decoupling / polarization / CTL / ATL) were confirmed to already be exposed as fields on `get_activity_details` — no extra tools needed. Two genuine gaps filled:
  - `get_athlete_mmp_model` — CP / W' / pMax / FTP estimate from the MMP curve. Single most important capacity-progression signal across a training block.
  - `get_activity_interval_stats` — interval-fade analysis (interval N vs interval 1) for hard sets.

  Dropped from the proposal: `get_activity_time_at_hr` (redundant with `polarization_index` scalar) and `get_activity_power_vs_hr` (redundant with `decoupling` scalar).

### Changed

- Lean profile final state: **30 tools, ~11.5 k tokens** of schema. Full profile: **134 tools, ~43.9 k tokens**. Savings on lean: ~32 k tokens (~74 %) per turn.
- README + manifest + `AITrainer/CLAUDE.md` synced to the final lean list.

### Fixed

- **`format_best_efforts`** — formatter rewritten against the live OpenAPI `Effort` schema (`{ start_index, end_index, average, duration, distance }`). The previous formatter expected `type` / `value` / `watts` / `bpm` / `activity_id` / `time_ago` — none of which the API returns, which is why every field rendered as `—`. Test fixture rewritten to use the real shape; assertions updated. Stream context is now threaded from `find_best_efforts` so the avg-column unit label (W / bpm / m/s / rpm) is correct per stream type.
- **`manifest.json`** — migrated from old `dxt_version: "0.1"` to current `manifest_version: "0.3"` (verified against live spec at https://github.com/modelcontextprotocol/mcpb). Added a `uv` prerequisite paragraph in `long_description` so users know what to install before opening the bundle.
- **MCPB install blocked by Python pre-flight** — initially added `compatibility.runtimes.python: ">=3.12"` per a research subagent's recommendation, but real Desktop install surfaced "Python >=3.12 required" because that field triggers a host-Python pre-flight, which is the wrong target for `uv`-driven bundles (they auto-provision their own Python from `pyproject.toml`'s `requires-python`). Removed the field. Bundle rebuilt; final SHA-256 `fdf56d53...07ca08a`.

## [1.1.0] — 2026-04-27

### Added

- **Wave 5** — File ops (9 tools): multipart uploads (`upload_activity`, `upload_activity_streams_csv`, `import_workout_file`), binary downloads with optional gzip preservation (`download_activity_file`, `download_activity_fit_file`, `download_activity_gpx_file`, `download_activity_fit_files`), and workout-file conversion (`download_workout`, `download_workout_for_athlete`) with Zwift `.zwo` / `.mrc` / `.erg` / `.fit` output.
- **Profile gate** (`INTERVALS_PROFILE` env var) — two profiles to control context-window cost:
  - `lean` (default) — 26 high-value tools sized for the four AI training-partner workflows + Zwift export. **~9.5k tokens** of tool schema in the system prompt.
  - `full` — all 133 tools. **~43k tokens** of tool schema. Use when you want SDK-style coverage.
  - Saves ~33.5k tokens per turn (~78% reduction) for the Claude Desktop default install.
  - Implementation: `tools/profile.py` defines `LEAN_TOOLS` and `apply_profile()`. After every tool module's `@mcp.tool()` decorators run at import time, the server prunes the FastMCP `_tool_manager._tools` registry down to the lean set unless `INTERVALS_PROFILE=full` is set. Anything other than the literal `full` (case-insensitive) is treated as `lean` so a typo can't expand the surface.

### Changed

- `manifest.json`: bumped tool description to "133 tools", added `profile` user-config field (default `lean`), wired `INTERVALS_PROFILE` env var to `${user_config.profile}`.
- README: tool inventory + install paths reflect 133 tools + profile switch.

## [1.0.0] — 2026-04-26

First fork release. Expands upstream's 17 tools to **124 single-user tools** covering effectively the entire personal-scope surface of the intervals.icu API.

### Added

- **3 derived tools** (`get_athlete_profile`, `get_fitness_curve`, `get_ftp_history`) — see commits `5090416`, `f992bc7`. The athlete profile tool parses `sportSettings` for per-discipline FTP / LTHR / max HR / threshold pace / swim CSS, with pace conversion m/s → mm:ss/km|100m.
- **Wave 1** (`de89263`) — Sport settings (10), wellness writes with `locked: true` default (5), event bulk ops (7) = 22 tools.
- **Wave 2** (`f1fa511`) — Library (workout templates + folders) = 16 tools.
- **Wave 3** (`f7f5e4f`) — Per-activity analytics reads (17) + activity/interval mutations (7) + athlete-level views & search & manual creation (17) = 41 tools.
- **Wave 4** (`365067b`) — Routes + Gear + reminders (13) + athlete-extras + weather + shared events + OAuth disconnect (12) = 25 tools.
- **DXT manifest** (`manifest.json`) for one-click Claude Desktop install.

### Fixed

- `find_best_efforts`: live API requires `stream` AND (`duration` or `distance`). Initial brief was wrong; tool was returning 422 on every call. Fixed in `204ffde`. Defaults `stream="watts"` for cycling common case; tool validates one of duration/distance is supplied before hitting the API.

### Architecture

- Each domain lives in its own `tools/{domain}.py` + `utils/formatters_{domain}.py` + `tests/test_{domain}.py` trio. The shared `tools/__init__.py` and `server.py` register everything.
- Multipart uploads bypass `make_intervals_request` (which is JSON-only) and call `httpx` directly, reusing the private `_prepare_request_config` / `_get_httpx_client` / `_parse_response` helpers from `api/client.py`.
- CSV-mode downloads (`format="csv"` on `*_curve` endpoints) follow the same bypass pattern via a local `_fetch_csv` helper.
- Top-level array-body PUTs (intervals updates, wellness bulk writes) go through a thin `_put_json_body` helper.
- Wellness writes always default `locked: true` so external sync (Oura / Garmin / Whoop) doesn't silently overwrite API changes. Surfaces a warning in the response if `locked=False` is opted-in.

### Test coverage

- 179 unit tests via `pytest` + `respx`-style mocks. ~22 tests per wave, covering happy path, error path, edge cases (empty list, 404, malformed body), and body-construction asserts.
- `tests/smoke_test_live.py` — read-only end-to-end against the live API, requires `INTERVALS_API_KEY` + `INTERVALS_ATHLETE_ID` in `.env`.

### Known soft issues

- `format_best_efforts` markdown rendering is incomplete — call succeeds, data is fetched, but the formatter expects a different response shape than the API returns. Most fields show `—`. Harmless; data is in the JSON.
- Em-dash characters in some formatter outputs mojibake on cp1252 Windows consoles. MCP transport is UTF-8 so end users see correct chars.

### Attribution

Forked from `mvilanova/intervals-mcp-server` (235 stars, GPL-3.0). Upstream provides the 17 base tools (activities/events/wellness reads, custom items CRUD), the type system in `utils/types.py`, the formatting helpers in `utils/formatting.py`, the request client in `api/client.py`, and the config + server-setup machinery. This fork is a downstream extension; pull `upstream/main` periodically to stay current.
