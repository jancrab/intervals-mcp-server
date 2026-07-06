# v1.5.0 — gear-maintenance + FTP-set in lean, `full_toolset` toggle

**2026-07-06**

## Why

The gear-write tools (`create_gear`, `update_gear`, `delete_gear`, `replace_gear`, gear reminders, `recalc_gear_distance`) and the sport-settings write tools (`update_sport_settings`, `create_sport_settings`) already existed — but they were **full-only**. A default (lean) session couldn't see them, so it looked like "the fork can't create gear / can't set FTP." This release surfaces the recurring ones in lean and adds a click-based toggle for the rest.

## Lean profile: 40 → 45 tools (~13.9k → ~14.9k tokens)

Promoted (recurring maintenance + retest ops, so no full escalation mid-flow):

| Tool | Use |
|---|---|
| `update_sport_settings` | Set FTP / LTHR / zones after a retest — `("Ride", {"ftp": 228})` |
| `create_gear` | Add a bike or a component |
| `create_gear_reminder` | Wear reminder ("warn at X km") |
| `replace_gear` | Retire component + swap in a copy (the physical-swap flow) |
| `recalc_gear_distance` | Recompute gear odometer |

Rare/bulk gear ops, all analytics reads, `update_activity`, bulk events, wellness backfill, and the new `get_fitness_model_events` stay **full-only**.

## New: `full_toolset` toggle

A boolean user-config checkbox (**Full toolset (advanced)**) → env `INTERVALS_PROFILE_FULL`.

- OFF (default) = lean (45 tools).
- ON = full (all 136 tools) — for rare ops: initial component setup, bulk events, analytics deep-dives.
- The legacy free-text `INTERVALS_PROFILE=full` still works; the checkbox wins if both are set.
- Flipping the checkbox **relaunches** the extension server, so the fresh connection re-reads the tool list (there is no live mid-session switch). If Claude Desktop doesn't refresh, restart it once.

## New tool

- `get_fitness_model_events` — `GET /athlete/{id}/fitness-model-events` (full-only). The one endpoint from the maintenance batch not already wrapped.

## Verified: gear component → bike attach

Checked live (2026-07-06) against a real bike (`b13469702`, "Green Bullet"): a bike's `component_ids` is **not** a writable attach field — a `PUT` echoes the value back but a fresh `GET` returns `null` (it is read-only / derived). So a component→bike link **cannot be set through the API**. Create the linkage in the intervals.icu web UI (Gear → bike → add component), then manage the existing component via the MCP (`create_gear_reminder`, `replace_gear`, `recalc_gear_distance`, `list_gear`). For a component's odometer to accumulate km, its `activity_filters` must match the bike's rides (also set in the UI). This is documented in the `create_gear` docstring so callers don't guess.

## Compatibility

- No tools removed; no existing tool signatures changed (additive only).
- The `locked`-wellness safety behavior, Strava-restricted handling, and the MMP/CP read tools are untouched.
- **223 tests passing.**

## Install

Download `intervals-icu-jan-1.5.0.mcpb` from the release, drag into Claude Desktop → Settings → Extensions, and **restart Desktop** for the new tools + toggle to take effect.

SHA-256: `9bbf105d5b368b91c8d7f96942fe01a7b63f8265ea70e962b02cee00f1d187aa`
