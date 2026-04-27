# intervals-icu-jan v1.2.0

A personal-scope Model Context Protocol server for the [intervals.icu](https://intervals.icu) training-platform API, packaged as a Claude Desktop one-click MCPB extension. This release brings the fork to a stable surface of **134 tools across 17 domains**, with a context-saving lean profile selected by default.

## What's new in 1.2.0 (vs upstream `mvilanova/intervals-mcp-server`)

- **134 tools across 17 domains** covering effectively every read/write the authenticated athlete can perform — activities, intervals, wellness writes (Oura/Garmin-safe), planned events, workout library, sport settings, gear, routes, weather, custom dashboards, athlete updates, and file ops. Upstream ships ~17 base tools; this fork is a downstream extension.
- **Two profiles, switchable via `INTERVALS_PROFILE`.**
  - `lean` (default) — 30 high-value tools, ~11.5k tokens of schema. Sized for the four AI training-partner workflows (daily readiness, weekly planning, post-workout debrief, strength logging) plus manual activity creation, Zwift/ERG/MRC/FIT export, and the `get_activity_full_report` aggregator.
  - `full` — all 134 tools, ~44k tokens of schema. Use for SDK-style coverage (bulk imports, gear management, custom dashboard items, weather config, OAuth disconnect).
  - Net savings on lean: ~32k tokens (~74%) of system-prompt overhead per turn vs full.
- **`get_activity_full_report` aggregator** — one tool, eight parallel sub-fetches (details, intervals, messages, power curve, HR curve, best efforts, segments, weather; streams optional). Returns a consolidated markdown report with per-section failures inlined as `_(unavailable: ...)_` rather than poisoning the rest. Saves ~7 tool-call decisions per post-workout debrief.
- **Cycling-coaching coverage research-validated** against Coggan (TSS/NP/IF), Friel (aerobic decoupling 5%/10% rule), and Skiba (CP/W'). 95% of per-workout coaching scalars (TSS / IF / NP / VI / EF / kJ / decoupling / polarization / CTL / ATL) are exposed as scalar fields on `get_activity_details` — no extra tools needed. Lean adds `get_athlete_mmp_model` (CP / W' / pMax / FTP from MMP curve) and `get_activity_interval_stats` (interval-fade analysis) to fill the two genuine gaps.
- **Wellness writes default `locked: true`** so external sync (Oura, Garmin, Whoop, Strava) doesn't silently overwrite values you just set via the API. `locked=False` is supported but the response surfaces a warning.
- **File ops** — multipart uploads (`upload_activity`, `upload_activity_streams_csv`, `import_workout_file`), gzipped/zip binary downloads (FIT / GPX / streams), and Zwift `.zwo` / `.mrc` / `.erg` / `.fit` workout export via `download_workout`.
- **179 unit tests** (`pytest` + `respx`-style mocks, ~22 per build wave) plus a read-only live-API smoke test.

## Install

See the **Quick install** section in [`README.md`](./README.md). Path A (Claude Desktop MCPB one-click) is the recommended route: download the `.mcpb` from this release, double-click, fill the four user-config fields, restart Desktop.

## Profiles cheat sheet

Pick `lean` if you're using this through Claude Desktop or Claude Code as a daily training partner — you'll keep 32k tokens of context for actual conversation. Pick `full` if you're scripting ad-hoc admin tasks (bulk imports, gear retirement, custom-dashboard authoring, OAuth cleanup) where the extra 100+ tools matter more than the system-prompt cost. Switching is one env var or one extension-setting change away.

## Compatibility

- **OS**: macOS, Linux, Windows.
- **Python**: 3.12 or higher. Auto-resolved by `uv` when launched via the bundle; no manual venv needed.
- **Runtime prerequisite**: `uv` must be on PATH. Install with `curl -LsSf https://astral.sh/uv/install.sh | sh` (macOS / Linux) or `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"` (Windows).
- **MCPB manifest**: `manifest_version: "0.3"` — verified against the live spec at https://github.com/modelcontextprotocol/mcpb.

## Attribution

Forked from [`mvilanova/intervals-mcp-server`](https://github.com/mvilanova/intervals-mcp-server) (GPL-3.0); upstream provides the architectural base and the original 17 tools (the type system in `utils/types.py`, the formatting helpers in `utils/formatting.py`, the request client in `api/client.py`, and the config + server-setup machinery). This fork is a downstream extension — pull `upstream/main` periodically to stay current. License is GPL-3.0-only, inherited.

## Checksums

Bundle: `intervals-icu-jan-1.2.0.mcpb` — 230 KB (62 files; verified clean of `.git`, `.venv`, `__pycache__`, `.env*`, `audit.log`, `tests/`).

```
SHA-256: 03b52444b5b08b18ca08c25d4360e70bf1ba787e3921a2a06f1ab4c89c5a4de2
```

Verify before installing:

```bash
# macOS / Linux
shasum -a 256 intervals-icu-jan-1.2.0.mcpb
# expected: 03b52444b5b08b18ca08c25d4360e70bf1ba787e3921a2a06f1ab4c89c5a4de2

# Windows (PowerShell)
Get-FileHash -Algorithm SHA256 intervals-icu-jan-1.2.0.mcpb
```
