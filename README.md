# Intervals.icu MCP Server (jancrab fork)

Model Context Protocol (MCP) server for the [intervals.icu](https://intervals.icu) training-platform API. Personal-use scope. Forked from [`mvilanova/intervals-mcp-server`](https://github.com/mvilanova/intervals-mcp-server) (which provides the architectural base + 17 core tools); this fork extends to **134 tools across 17 domains**, covering effectively every read/write the authenticated athlete can perform.

> If you're looking at the upstream's 17 tools and need full coverage of activity analytics, sport settings, gear, routes, weather, athlete updates, workout templates, wellness writes, event bulk ops, and file uploads/downloads — that's what this fork adds. See [`CHANGELOG.md`](./CHANGELOG.md) for the wave-by-wave breakdown.

## Two profiles: `lean` (default) vs `full`

MCP tool catalogs cost context tokens on every turn — the full 134-tool surface is ~44k tokens of schema, which dominates short Claude Desktop sessions. The server therefore ships two profiles, switchable via the `INTERVALS_PROFILE` env var:

| Profile | Tools | Schema tokens (measured) | Use when |
|---|---|---|---|
| **`lean`** (default) | 30 | ~11,561 | You want a working AI training partner without paying 25% of your context window. Covers the four core workflows (daily readiness, weekly planning, post-workout debrief, strength logging), manual activity creation, Zwift workout export, the `get_activity_full_report` aggregator, plus full cycling-coaching coverage (CP/W'/MMP via `get_athlete_mmp_model`, interval-fade via `get_activity_interval_stats`). |
| **`full`** | 134 | ~43,863 | You want SDK-style coverage of every endpoint — bulk imports, gear management, custom dashboard items, weather config, OAuth disconnect, etc. |

**Saving from running lean: ~32,300 tokens (~74%) on every turn.**

Set `INTERVALS_PROFILE=full` in your `.env`, your `.mcp.json`'s `env` block, or the MCPB user-config UI to switch. Anything other than the literal string `full` (case-insensitive) is treated as `lean`, so a typo can't accidentally expose 4-5× the surface area. The server logs the active profile + tool count at startup.

Lean tool list (30): `get_athlete_profile`, `get_athlete_basic_profile`, `get_ftp_history`, **`get_athlete_mmp_model`** (CP / W' / pMax / FTP from MMP curve), `get_wellness_data`, `get_wellness_record`, `update_wellness_record_today`, `get_fitness_curve`, `get_activities`, `get_activity_details` (already exposes TSS / IF / NP / VI / EF / kJ / decoupling / polarization / CTL / ATL as scalar fields), `get_activity_streams`, `get_activity_intervals`, `get_activity_messages`, `add_activity_message`, `search_for_activities`, `list_activities_around`, `create_manual_activity`, `get_activity_power_curve`, `get_activity_hr_curve`, `find_best_efforts`, **`get_activity_interval_stats`** (interval-fade analysis), **`get_activity_full_report`** (8-endpoint parallel aggregator), `get_events`, `get_event_by_id`, `add_or_update_event`, `delete_event`, `mark_event_as_done`, `list_workouts`, `get_workout`, **`download_workout`**. The full set is everything in the inventory table below.

### Fat aggregator: `get_activity_full_report`

A single tool that fetches **8 endpoints in parallel** for one activity and returns a consolidated multi-section markdown report:

- Activity details (pace / power / HR / TSS / IF / etc.)
- Interval breakdown
- Coach messages
- Power curve
- HR curve
- Best efforts (default `watts` / 5 min, configurable)
- Segments (toggleable)
- Weather summary (toggleable)
- 1 Hz streams (off by default — large)

Designed for the post-workout debrief workflow where the model would otherwise call 8 tools sequentially. Trade: one tool's worth of schema cost (~1,400 tokens) for parallel-fetch wall-clock and ~7 saved tool-call decisions per debrief. Per-section failures surface as `_(unavailable: ...)_` inline without poisoning the rest of the report.

## Quick install

Three paths, pick whichever fits your workflow:

### A. Claude Desktop — MCPB one-click (recommended)

The fork ships an [MCPB extension manifest](./manifest.json) (`manifest_version: "0.3"`) so Claude Desktop can install the server with a single double-click. MCPB is the renamed successor to the old DXT format; the file extension is `.mcpb` and the official packager is [`@anthropic-ai/mcpb`](https://www.npmjs.com/package/@anthropic-ai/mcpb).

**Prerequisite: `uv` on PATH.** The bundle launches the server via `uv`, so install it first (see Troubleshooting below if Claude Desktop reports it can't find `uv`).

1. **Download** `intervals-icu-jan-1.2.0.mcpb` from the [v1.2.0 release](https://github.com/jancrab/intervals-mcp-server/releases/tag/v1.2.0) on GitHub.
2. **Double-click** the `.mcpb` file. Claude Desktop opens its install dialog.
3. **Fill the four user-config fields**:
   - `api_key` — your intervals.icu API key (marked sensitive in the UI).
   - `athlete_id` — e.g. `i12345`.
   - `profile` — free-text. Type `lean` (default, 30 tools) or `full` (134 tools). Anything else is treated as `lean`.
   - `log_level` — `INFO`, `DEBUG`, etc.
4. Click **Install**, then **restart Claude Desktop**.

**Verify the install.** Open a new chat and ask:

```
Show me my last activity.
```

Expected: the lean profile is active (30 tools), and `mcp__intervals-icu-jan__get_activities` fires. If you switched to `full` you'll see 134 tools available.

**Switching profile post-install.** Settings → Extensions → `intervals-icu-jan` → **Tool profile** → type EXACTLY `full` (or `lean`) → save → restart Desktop. Tool count jumps 30 → 134 (or back).

> **Credential storage note.** The user-config UI marks `api_key` as sensitive, but the underlying storage backend per OS is not documented in the v0.3 spec. Treat the key as semi-public and rotate it periodically at intervals.icu → Settings → Developer Settings.

#### Troubleshooting

- **`uv` not on PATH.** Claude Desktop fails to launch the server.
  - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows (PowerShell): `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

  Restart Desktop after install so it picks up the new PATH.
- **API key rejected (HTTP 401).** Regenerate the key at intervals.icu → Settings → Developer Settings, then update the value in Settings → Extensions → `intervals-icu-jan` and restart Desktop.
- **Tool count is 134 when you expected 30.** `INTERVALS_PROFILE` is set to `full` in extension settings. Open Settings → Extensions → `intervals-icu-jan` → **Tool profile** → type `lean` → save → restart Desktop.

### B. Claude Code — `.mcp.json` in your project

Drop this into your project's `.mcp.json` (or merge into `~/.claude/settings.json`'s `mcpServers`):

```json
{
  "mcpServers": {
    "intervals-icu-jan": {
      "command": "uv",
      "args": [
        "--directory", "/absolute/path/to/intervals-mcp-server",
        "run", "python", "-m", "intervals_mcp_server.server"
      ],
      "env": {
        "API_KEY":    "${INTERVALS_API_KEY}",
        "ATHLETE_ID": "${INTERVALS_ATHLETE_ID}"
      }
    }
  }
}
```

Then in your shell:

```bash
setx INTERVALS_API_KEY    "your-real-key"          # Windows
setx INTERVALS_ATHLETE_ID "i12345"
# macOS/Linux:  export INTERVALS_API_KEY=... ; add to ~/.zshrc
```

Restart Claude Code. The 30 lean-profile tools become available as `mcp__intervals-icu-jan__*` (or all 134 if you add `"INTERVALS_PROFILE": "full"` to the `env` block above).

For per-tool write confirmations (recommended), add `permissions.ask` rules — the AITrainer repo at `../` ships a complete example covering all 61 write tools (sport-settings writes, wellness writes, event bulk ops, gear writes, athlete updates, etc.).

### C. Claude Desktop — manual `claude_desktop_config.json`

Same shape as the Claude Code path above, with literal env values (`${VAR}` substitution is unreliable on Desktop):

```json
{
  "mcpServers": {
    "intervals-icu-jan": {
      "command": "/Users/<you>/.local/bin/uv",
      "args": [
        "--directory", "/path/to/intervals-mcp-server",
        "run", "python", "-m", "intervals_mcp_server.server"
      ],
      "env": {
        "API_KEY": "sk_live_...",
        "ATHLETE_ID": "i12345"
      }
    }
  }
}
```

File location:
- macOS/Linux: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows (standard): `%APPDATA%\Claude\claude_desktop_config.json`
- Windows (Microsoft Store): `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude_desktop_config.json`

## Tool inventory (134 across 17 domains)

This table lists the **full** profile. The `lean` profile (default) exposes the 30 tools enumerated above.

| Domain | Read tools | Write tools |
|---|---|---|
| **Activities** (per-activity) | `get_activities`, `get_activity_details`, `get_activity_streams`, `get_activity_intervals`, `get_activity_messages` | `add_activity_message`, `update_activity`, `delete_activity`, `update_activity_streams`, `update_intervals`, `update_interval`, `delete_intervals`, `split_interval` |
| **Activity analytics** (per-activity) | `find_best_efforts`, `get_activity_*_curve`, `get_activity_*_histogram`, `get_activity_*_load_model`, `get_activity_interval_stats`, `get_activity_segments`, `get_activity_map`, `get_activity_time_at_hr`, `get_activity_weather_summary`, `get_activity_power_spike_model`, `get_activity_power_vs_hr` (17 total) | — |
| **Athlete-level views** | `get_activities_by_ids`, `list_activities_around`, `get_activities_csv`, `search_for_activities`, `search_for_activities_full`, `search_for_intervals`, `list_activity_tags`, `list_activity_*_curves`, `list_athlete_*_curves`, `get_athlete_power_hr_curve`, `get_athlete_mmp_model` | `create_manual_activity`, `create_multiple_manual_activities` |
| **Events** (planned workouts) | `get_events`, `get_event_by_id`, `list_event_tags` | `add_or_update_event`, `delete_event`, `delete_events_by_date_range`, `delete_events_bulk`, `mark_event_as_done`, `apply_plan`, `create_multiple_events`, `duplicate_events`, `update_events_in_range` |
| **Wellness** | `get_wellness_data`, `get_wellness_record` | `update_wellness_record`, `update_wellness_record_today`, `update_wellness_records_bulk`, `upload_wellness_csv` (all default `locked: true`) |
| **Library** (workout templates) | `list_workouts`, `get_workout`, `list_workout_folders`, `list_folder_shared_with`, `list_workout_tags` | `create_workout`, `update_workout`, `create_multiple_workouts`, `delete_workout`, `create_workout_folder`, `update_workout_folder`, `delete_workout_folder`, `update_folder_shared_with`, `update_plan_workouts`, `apply_current_plan_changes`, `duplicate_workouts` |
| **Sport settings** | `list_sport_settings`, `get_sport_settings`, `list_activities_matching_sport_settings`, `list_pace_distances_for_sport`, `list_pace_distances` | `create_sport_settings`, `update_sport_settings`, `update_sport_settings_multi`, `delete_sport_settings`, `apply_sport_settings_to_activities` |
| **Gear** | `list_gear`, `recalc_gear_distance` | `create_gear`, `update_gear`, `delete_gear`, `replace_gear`, `create_gear_reminder`, `update_gear_reminder`, `delete_gear_reminder` |
| **Routes** | `list_athlete_routes`, `get_athlete_route`, `check_route_merge` | `update_athlete_route` |
| **Athlete profile** | `get_athlete_profile` (full + sportSettings parsed), `get_athlete_basic_profile` (`/profile` subset), `get_athlete_summary`, `get_athlete_settings_for_device`, `get_athlete_training_plan` | `update_athlete`, `update_athlete_plans`, `update_athlete_training_plan` |
| **Derived views** | `get_fitness_curve` (CTL/ATL/form), `get_ftp_history` (change-points) | — |
| **Weather** | `get_weather_config`, `get_weather_forecast` | `update_weather_config` |
| **Custom items** (charts, dashboards) | `get_custom_items`, `get_custom_item_by_id` | `create_custom_item`, `update_custom_item`, `delete_custom_item` |
| **Shared events** | `get_shared_event` | — |
| **OAuth** | — | `disconnect_app` |
| **File ops** (multipart + binary) | `download_activity_file`, `download_activity_fit_file`, `download_activity_gpx_file`, `download_workout`, `download_workout_for_athlete` | `upload_activity`, `upload_activity_streams_csv`, `import_workout_file`, `download_activity_fit_files` (POST-with-body bundle download) |
| **Aggregators** (cross-domain fat-tools) | `get_activity_full_report` (8 parallel subcalls → one consolidated markdown report) | — |

Total: **134 tools** in `full`, **30** in `lean`. Run `INTERVALS_PROFILE=full uv run python -c "from intervals_mcp_server.server import mcp; import asyncio; print(len(asyncio.run(mcp.list_tools())))"` to get the live count.

### Zwift / ERG / MRC workout export

`download_workout` POSTs a workout document to `/download-workout.{ext}` and returns the converted file. Supported formats: `zwo` (Zwift), `mrc`, `erg`, `fit`. This tool is included in the `lean` profile because it's a high-value direct-user request ("export this Z2 ride for Zwift") that would otherwise force users into `full`.

## Authentication

HTTP Basic auth, **literal** username `API_KEY`, password = your generated API key. Both `API_KEY` and `ATHLETE_ID` env vars are required at server startup; the server fails fast with a clear error if either is missing.

Generate the API key at `intervals.icu` → Settings → Developer Settings.
Find your athlete ID at `intervals.icu` → Settings, or in your profile URL (e.g. `i12345`).

## Wellness `locked` default — important

The intervals.icu UI lets external services (Oura, Garmin, Whoop, Strava) overwrite wellness fields on sync. To prevent silent overwrites of API-set values, all `update_wellness_*` and `upload_wellness_csv` tools **default `locked: true`** in the request body. Per-record override is supported but the response surfaces a `> WARNING:` line whenever `locked=False` is used.

## License & attribution

GPL-3.0-only (inherited from upstream). Forked from [`mvilanova/intervals-mcp-server`](https://github.com/mvilanova/intervals-mcp-server). All upstream code is preserved unchanged; this fork's additions live in:

- `tools/{athlete,sport_settings,wellness_writes,events_extras,library,activity_analytics,activity_writes,activity_athlete_level,routes_gear,athlete_extras,file_ops}.py` (11 new modules)
- `utils/formatters_{domain}.py` (9 new formatter modules — duplicated rather than imported from `utils/formatting.py` to avoid concurrency-merge headaches)
- `tests/test_{domain}.py` (~10 new test modules)
- `manifest.json` (DXT one-click install)
- `CHANGELOG.md` (this fork's history)
- `RECON.md`, `ENDPOINT_INVENTORY.md`, `FULL_API_ROADMAP.md`, `ROADMAP.md` (build notes)

The original upstream README sections follow below for users coming from the upstream documentation.

---

## Requirements

- Python 3.12 or higher
- [Model Context Protocol (MCP) Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- httpx
- python-dotenv

## Setup

### 1. Install uv (recommended)

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, find the full path to `uv` — you'll need it later when configuring Claude Desktop:

```powershell
where.exe uv
# Example output: C:\Users\<USERNAME>\.local\bin\uv.exe
```

### 2. Clone this repository

```bash
git clone https://github.com/mvilanova/intervals-mcp-server.git
cd intervals-mcp-server
```

### 3. Create and activate a virtual environment

```bash
# Create virtual environment with Python 3.12
uv venv --python 3.12

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

### 4. Sync project dependencies

```bash
uv sync
```

### 5. Set up environment variables

Make a copy of `.env.example` and name it `.env` by running the following command:

**macOS/Linux:**
```bash
cp .env.example .env
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

Then edit the `.env` file and set your Intervals.icu athlete id and API key:

```
API_KEY=your_intervals_api_key_here
ATHLETE_ID=your_athlete_id_here
```

#### Getting your Intervals.icu API Key

1. Log in to your Intervals.icu account
2. Go to Settings > API
3. Generate a new API key

#### Finding your Athlete ID

Your athlete ID is typically visible in the URL when you're logged into Intervals.icu. It looks like:

- `https://intervals.icu/athlete/i12345/...` where `i12345` is your athlete ID

## Updating

This project is actively developed, with new features and fixes added regularly. To stay up to date, follow these steps:

### 1. Pull the latest changes from `main`

> ⚠️ Make sure you don't have uncommitted changes before running this command.

**macOS/Linux:**
```bash
git checkout main && git pull
```

**Windows (PowerShell):**
```powershell
git checkout main; git pull
```

### 2. Update Python dependencies

Activate your virtual environment and sync dependencies:

**macOS/Linux:**
```bash
source .venv/bin/activate
uv sync
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\activate
uv sync
```

### Troubleshooting

If Claude Desktop fails due to configuration changes, follow these steps:

1. Delete the existing `Intervals.icu` entry in `claude_desktop_config.json`.
2. Reconfigure Claude Desktop from the `intervals-mcp-server` directory.

**macOS/Linux:**
```bash
mcp install src/intervals_mcp_server/server.py --name "Intervals.icu" --with-editable . --env-file .env
```

**Windows:** Re-add the entry manually as described in the [Windows configuration section](#windows).

#### Common errors

**`spawn uv ENOENT`** — Claude Desktop cannot find the `uv` executable. Use the full path to `uv` in the `command` field. Run `which uv` (macOS/Linux) or `where.exe uv` (Windows) to get it.

**`spawn /Users/... ENOENT` on Windows** — The config file contains a macOS/Linux-style path. Replace it with the correct Windows path using backslashes as described in the [Windows configuration section](#windows) below.

**Windows Store install: config changes not taking effect** — You may be editing the wrong config file. Claude Desktop installed from the Microsoft Store reads from `AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`, not `AppData\Roaming\Claude\`.

## Usage with Claude

### 1. Configure Claude Desktop

To use this server with Claude Desktop, you need to add it to your Claude Desktop configuration.

#### macOS/Linux

1. Run the following from the `intervals-mcp-server` directory to configure Claude Desktop:

```bash
mcp install src/intervals_mcp_server/server.py --name "Intervals.icu" --with-editable . --env-file .env
```

2. If you open your Claude Desktop App configuration file `claude_desktop_config.json`, it should look like this:

```json
{
  "mcpServers": {
    "Intervals.icu": {
      "command": "/Users/<USERNAME>/.local/bin/uv",
      "args": [
        "run",
        "--with",
        "mcp[cli]",
        "--with-editable",
        "/path/to/intervals-mcp-server",
        "mcp",
        "run",
        "/path/to/intervals-mcp-server/src/intervals_mcp_server/server.py"
      ],
      "env": {
        "INTERVALS_API_BASE_URL": "https://intervals.icu/api/v1",
        "ATHLETE_ID": "<YOUR_ATHLETE_ID>",
        "API_KEY": "<YOUR_API_KEY>",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Where `/path/to/` is the path to the `intervals-mcp-server` code folder in your system.

#### Windows

The `mcp install` command may fail on Windows due to environment or permission issues. Instead, configure Claude Desktop manually:

1. Find the Claude Desktop config file. If Claude Desktop was installed from the **Microsoft Store**, the config is located at:

   ```
   C:\Users\<USERNAME>\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json
   ```

   If installed via the standard installer, it may be at:

   ```
   C:\Users\<USERNAME>\AppData\Roaming\Claude\claude_desktop_config.json
   ```

   If the file or folder does not exist, create it.

2. Add the following entry to `claude_desktop_config.json`, replacing the placeholders with your actual values:

```json
{
  "mcpServers": {
    "Intervals.icu": {
      "command": "C:\\Users\\<USERNAME>\\.local\\bin\\uv.exe",
      "args": [
        "run",
        "--with",
        "mcp[cli]",
        "--with-editable",
        "C:\\path\\to\\intervals-mcp-server",
        "mcp",
        "run",
        "C:\\path\\to\\intervals-mcp-server\\src\\intervals_mcp_server\\server.py"
      ],
      "env": {
        "INTERVALS_API_BASE_URL": "https://intervals.icu/api/v1",
        "ATHLETE_ID": "<YOUR_ATHLETE_ID>",
        "API_KEY": "<YOUR_API_KEY>",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

- Use double backslashes (`\\`) for all Windows paths in JSON.
- To find the full path to `uv.exe`, run `where.exe uv` in PowerShell.
- To find the full path to the cloned repository, run `pwd` from inside the `intervals-mcp-server` folder.

> **Note for Windows Store installs:** Claude Desktop installed from the Microsoft Store sandboxes its config under `AppData\Local\Packages\...`. Editing `AppData\Roaming\Claude\claude_desktop_config.json` will have no effect — make sure you edit the correct file.

3. Restart Claude Desktop.

### 2. Use the MCP server with Claude

Once the server is running and Claude Desktop is configured, you can use the following tools to ask questions about your past and future activities, events, and wellness data.

- `get_activities`: Retrieve a list of activities
- `get_activity_details`: Get detailed information for a specific activity
- `get_activity_intervals`: Get detailed interval data for a specific activity
- `get_wellness_data`: Fetch wellness data
- `get_events`: Retrieve upcoming events (workouts, races, etc.)
- `get_event_by_id`: Get detailed information for a specific event

## Usage with ChatGPT

ChatGPT’s beta MCP connectors can also talk to this server over the SSE transport.

1. Start the server in SSE mode so it exposes the `/sse` and `/messages/` endpoints:

   ```bash
   export FASTMCP_HOST=127.0.0.1 FASTMCP_PORT=8765 MCP_TRANSPORT=sse FASTMCP_LOG_LEVEL=INFO
   python src/intervals_mcp_server/server.py
   ```

   The startup log prints the full URLs (for example `http://127.0.0.1:8765/sse`). ChatGPT needs that public URL, so forward the port with a tool such as `ngrok http 8765` if you are not exposing the server directly.

2. In ChatGPT, open **Settings → Features → Custom MCP Connectors** and click **Add**. Fill in:

   - **Name**: `Intervals.icu`
   - **MCP Server URL**: `https://<your-public-host>/sse`
   - **Authentication**: leave as _No authentication_ unless you have protected your tunnel.

   You can reuse the same `ngrok http 8765` tunnel URL here; just ensure it forwards to the host/port you exported above.

3. Save the connector and open a new chat. ChatGPT will keep the SSE connection open and POST follow-up requests to the `/messages/` endpoint announced by the server. If you restart the MCP server or tunnel, rerun the SSE command and update the connector URL if it changes.

## Development and testing

Install development dependencies and run the test suite with:

```bash
uv sync --all-extras
pytest -v tests
```

### Running the server locally

To start the server manually (useful when developing or testing), run:

```bash
mcp run src/intervals_mcp_server/server.py
```

#### Enabling debug logging

To capture server logs for debugging, wrap the command in a shell and redirect stderr to a file.

**macOS/Linux** — modify your `claude_desktop_config.json` like this:

```json
{
  "mcpServers": {
    "Intervals.icu": {
      "command": "/bin/bash",
      "args": [
        "-c",
        "/Users/<USERNAME>/.local/bin/uv run --with 'mcp[cli]' --with-editable /path/to/intervals-mcp-server mcp run /path/to/intervals-mcp-server/src/intervals_mcp_server/server.py 2>> /path/to/intervals-mcp-server/mcp-server.log"
      ],
      "env": {
        "INTERVALS_API_BASE_URL": "https://intervals.icu/api/v1",
        "ATHLETE_ID": "<YOUR_ATHLETE_ID>",
        "API_KEY": "<YOUR_API_KEY>",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Then tail the log file to see output in real-time:

```bash
tail -f /path/to/intervals-mcp-server/mcp-server.log
```

**Windows** — modify your `claude_desktop_config.json` like this:

```json
{
  "mcpServers": {
    "Intervals.icu": {
      "command": "powershell",
      "args": [
        "-Command",
        "C:\\Users\\<USERNAME>\\.local\\bin\\uv.exe run --with 'mcp[cli]' --with-editable C:\\path\\to\\intervals-mcp-server mcp run C:\\path\\to\\intervals-mcp-server\\src\\intervals_mcp_server\\server.py 2>> C:\\path\\to\\intervals-mcp-server\\mcp-server.log"
      ],
      "env": {
        "INTERVALS_API_BASE_URL": "https://intervals.icu/api/v1",
        "ATHLETE_ID": "<YOUR_ATHLETE_ID>",
        "API_KEY": "<YOUR_API_KEY>",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Then monitor the log file in real-time using PowerShell:

```powershell
Get-Content C:\path\to\intervals-mcp-server\mcp-server.log -Wait
```

## License

The GNU General Public License v3.0

## Featured

### Glama.ai

<a href="https://glama.ai/mcp/servers/@mvilanova/intervals-mcp-server">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@mvilanova/intervals-mcp-server/badge" alt="Intervals.icu Server MCP server" />
</a>
