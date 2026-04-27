# Changelog

This fork tracks divergence from upstream `mvilanova/intervals-mcp-server`. See `git log upstream/main..HEAD` for the precise diff.

## [Unreleased]

_Nothing yet._

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
