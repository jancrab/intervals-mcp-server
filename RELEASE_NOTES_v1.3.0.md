# intervals-icu-jan v1.3.0 — Pre-normalization stub detection

Drop-in upgrade over v1.2.0. No config migration; existing Claude Desktop / Cowork extension settings (api_key, athlete_id, profile, log_level) are preserved.

## What's new

- **Draft-state activity detection** in `format_activity_summary`. Activities that are uploaded to intervals.icu but haven't completed normalization (typically fresh Zwift uploads sitting in upstream-ID limbo) now render as a 7-line remediation message pointing to the activity's web URL, instead of 60 lines of "N/A" that look like a fetch failure. Detection fires when the activity ID is an int or lacks the `i…` prefix, OR when name/type/start_date_local are all empty.
- **Structured 422 handling** in `get_activity_intervals`. intervals.icu returns 422 Unprocessable on intervals queries against pre-normalization activities; the tool now surfaces a structured `{"status": "draft", "message": ...}` response instead of leaking the raw API error wording. Other 4xx/5xx responses retain their original wording so genuine failures aren't masked.

## Why

A Zwift FTP test on 2026-04-29 returned an empty stub through the MCP while showing full data in the web UI. Cross-checked against eight prior planned-event-paired completions (Apr 1, 3, 6, 9, 12, 15, 17, 19) — all normalized cleanly. The discriminator was the upload's pre-normalization state, not event-pairing. Manual save in the web UI forces normalization. The fork now self-explains the situation when it sees the signature.

The fix lives in the formatter rather than as a new `get_activity_status` tool — the schema cost (~150-250 tokens) wasn't justified when the formatter improvement surfaces the signal inline whenever the model fetches the activity.

## Install

Same flow as v1.2.0. See [README.md](./README.md) Quick install → Path A.

```bash
gh release download v1.3.0 -R jancrab/intervals-mcp-server
# then double-click intervals-icu-jan-1.3.0.mcpb
```

## Compatibility

- macOS / Linux / Windows
- `uv` on PATH (auto-installs Python 3.12+ from `pyproject.toml` requires-python; no host Python requirement)
- MCPB `manifest_version: "0.3"`
- Lean / full profiles unchanged (30 / 134 tools)

## Tests

187 unit tests (179 from v1.2.0 + 8 new for draft detection + 422 handling).

## Checksums

Bundle: `intervals-icu-jan-1.3.0.mcpb` — 234 KB (62 files; verified clean of `.git`, `.venv`, `__pycache__`, `.env*`, `audit.log`, `tests/`).

```
SHA-256: eabbc74e0e42c3b23e66aca815b95cdfe817c13c09f07fa8e909e332c8c0f83c
```

Verify before installing:

```bash
# macOS / Linux
shasum -a 256 intervals-icu-jan-1.3.0.mcpb

# Windows (PowerShell)
Get-FileHash -Algorithm SHA256 intervals-icu-jan-1.3.0.mcpb
```
