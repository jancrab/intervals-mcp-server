# intervals-icu-jan v1.3.1 — `link_activity_to_event` + sharpened draft message + `get_event_by_id` fix

Drop-in upgrade over v1.3.0. No config migration; existing Claude Desktop / Cowork extension settings (api_key, athlete_id, profile, log_level) are preserved.

## What's new

### Added

- **`link_activity_to_event(activity_id, event_id)` tool** (lean profile). Write-side tool that links an activity to a planned event on intervals.icu by PUTing `{"paired_event_id": <int>}` to `/activity/{id}`. Use when an activity is stuck in pre-normalization state because of a workout-structure mismatch (typically a Zwift stock workout run instead of the prescribed `.zwo`). Forces normalization on intervals.icu's side; subsequent reads return full power/HR/duration data.
  - Validates `activity_id` non-empty and `event_id` parses as positive integer — raises `ValueError` before any API call.
  - Returns structured JSON: `{"status": "linked", "activity_id": "<canonical i… form>", "event_id": "..."}` on success; `{"status": "error", "http_status": <int>, "message": "<API verbatim>"}` on failure. API error wording is preserved verbatim (different 422 reasons exist; over-translation loses information).

### Changed

- **Sharpened draft-state remediation message** (`format_activity_summary`, v1.3.0+). Now distinguishes the orphan-Zwift-workout case (resolved by `link_activity_to_event`) from generic stuck uploads (resolved by manual rename + save). URL line and ID line preserved in their v1.3.0 positions.

### Fixed

- **`get_event_by_id` 404 bug.** The tool was constructing `/athlete/{id}/event/{eventId}` (singular `event`) and 404'd for IDs that `get_events` listed cleanly. Aligned with the canonical `/athlete/{id}/events/{eventId}` (plural, per OpenAPI spec). Confirmed against the planned event for the 2026-04-29 FTP test diagnosis.

## Why

A Zwift FTP test on 2026-04-29 (activity ID `18303442074`) landed orphan because Zwift's stock 20-min FTP test was run instead of the prescribed `.zwo`. v1.3.0's "rename and save" guidance does not unstick orphans — intervals.icu treats them as structurally unmatched, not just missing-name. The link tool resolves this case in one call by writing `paired_event_id` directly into the Activity record via the existing PUT endpoint. The sharpened draft message points the model at the tool when an orphan is detected. The `get_event_by_id` 404 was a separate bug uncovered during the same diagnosis (couldn't fetch event detail to construct the link call) and was bundled because adjacent.

## Install

Same flow as v1.3.0. See [README.md](./README.md) Quick install → Path A.

```bash
gh release download v1.3.1 -R jancrab/intervals-mcp-server
# then double-click intervals-icu-jan-1.3.1.mcpb
```

## Compatibility

- macOS / Linux / Windows
- `uv` on PATH (auto-installs Python 3.12+ from `pyproject.toml` requires-python; no host Python requirement)
- MCPB `manifest_version: "0.3"`
- Lean profile: now **31 tools** (was 30; `link_activity_to_event` added). Full profile: **135 tools** (was 134).

## Tests

196 unit tests (187 from v1.3.0 + 5 link-tool tests + 3 sharpened-message tests + 1 `get_event_by_id` URL test).

## Checksums

Bundle: `intervals-icu-jan-1.3.1.mcpb` — 237 KB (62 files; verified clean).

```
SHA-256: bb2c2fd4feb72c5aefb5198731ca01a8ac779e7bfd15fc65a79b8d57486c56a8
```

Verify before installing:

```bash
# macOS / Linux
shasum -a 256 intervals-icu-jan-1.3.1.mcpb

# Windows (PowerShell)
Get-FileHash -Algorithm SHA256 intervals-icu-jan-1.3.1.mcpb
```
