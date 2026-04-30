# intervals-icu-jan v1.3.2 — Sharpened 422 handling on `link_activity_to_event`

Drop-in upgrade over v1.3.1. No config migration; existing Claude Desktop / Cowork extension settings (api_key, athlete_id, profile, log_level) are preserved.

## What's new

### Changed

- **`link_activity_to_event`** now translates HTTP 422 responses to a structured `{"status": "draft_unrecoverable", "message": ...}` shape, mirroring v1.3.0's pattern for `get_activity_intervals` (which uses `"status": "draft"`). The new status is distinct because it's a stronger statement: the activity is past the point where the link endpoint can help. The message embeds the activity's web URL and the manual-rename remediation. Other 4xx/5xx responses retain v1.3.1's verbatim-API-message envelope so genuine failures (404, 401, 500, etc.) aren't masked.
- **Tool description** for `link_activity_to_event` documents the v1.3.2 limit: the link endpoint cannot recover activities in deep pre-normalization (raw integer ID, no `i…` prefix). Such activities require manual save via intervals.icu's web UI.

### Added

- **README troubleshooting entry** documenting the orphan-pre-normalization case, the typical Zwift-built-in-test trigger (Zwift→Strava→intervals.icu sync path appears to bypass normalization), and the manual-save remediation.

### Fixed

- **`get_event_by_id` `Date: Unknown` rendering bug.** `format_event_details` previously only checked `event.get("date")`, while the by-id endpoint returns events with a `start_date_local` field instead. Aligned with `format_event_summary`'s existing fallback chain (`start_date_local` → `date` → "Unknown"). One-line fix; no behavioral change for events that already carry `date`.

## Why

A v1.3.1 smoke test against today's orphan FTP test activity (`18303442074`) hit `link_activity_to_event` and returned 422. intervals.icu's link endpoint requires the activity to already be in canonical `i…`-prefixed ID space — which is exactly the state we wanted to force. The pre-normalization activities still hold their upstream raw integer ID, so the link endpoint refuses them.

Whether intervals.icu's API exposes any other endpoint capable of forcing normalization on these activities is a separate, currently parked investigation. v1.3.2 documents the limit honestly and points the user at the manual UI remediation rather than ship a tool whose error messages mislead.

The `get_event_by_id` Date fix was uncovered while diagnosing — bundled because it's a one-line change to align with an existing fallback pattern.

## Install

Same flow as v1.3.0/v1.3.1. See [README.md](./README.md) Quick install → Path A.

```bash
gh release download v1.3.2 -R jancrab/intervals-mcp-server
# then double-click intervals-icu-jan-1.3.2.mcpb
```

## Compatibility

- macOS / Linux / Windows
- `uv` on PATH (auto-installs Python 3.12+ from `pyproject.toml` requires-python; no host Python requirement)
- MCPB `manifest_version: "0.3"`
- Lean profile unchanged at **31 tools**. Full unchanged at **135 tools**.

## Tests

199 unit tests passing (was 196 in v1.3.1). Replaced the v1.3.1 422-preserves-message test (no longer applies — 422 has its own draft_unrecoverable path) with three new tests: 422 returns draft_unrecoverable, 404 keeps the verbatim envelope (un-widened), 200 success path unchanged. Plus one new `format_event_details` test pinning the `start_date_local` fallback.

## Checksums

Bundle: `intervals-icu-jan-1.3.2.mcpb` — 239 KB (62 files).

```
SHA-256: d584c493647a65710456f20a052e0457e8884545d25f941dde444d710ca98801
```

Verify before installing:

```bash
# macOS / Linux
shasum -a 256 intervals-icu-jan-1.3.2.mcpb

# Windows (PowerShell)
Get-FileHash -Algorithm SHA256 intervals-icu-jan-1.3.2.mcpb
```
