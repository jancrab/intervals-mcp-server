# intervals.icu API recon

Source-grounded notes for Phase 2. Sources:
- [Swagger UI](https://intervals.icu/api/v1/docs/swagger-ui/index.html) — spec exists but the JSON URL is JS-rendered; useful as reference, not for automation.
- [API integration cookbook](https://forum.intervals.icu/t/intervals-icu-api-integration-cookbook/80090) — auth, wellness, activities upload/download, webhooks.
- [API access guide](https://forum.intervals.icu/t/api-access-to-intervals-icu/609) — how to generate a key, base URL, athlete-id 0 = "me".
- [py-intervalsicu source on GitHub](https://github.com/rday/py-intervalsicu/blob/main/src/intervalsicu/api/intervals.py) — concrete URL paths, query params, and field lists.
- Direct probes against `https://intervals.icu/...` distinguishing 401 (exists, needs auth) from 404 (no such endpoint).

## Auth — confirmed

- HTTP Basic
- Username: literal string `API_KEY`
- Password: athlete's API key (intervals.icu → Settings → Developer Settings → generate)
- Athlete ID `0` in path = "me" (the athlete who owns the API key)
- All units metric. Date params: ISO 8601 (`YYYY-MM-DD`) for `oldest`/`newest`.

## Endpoint inventory

### Confirmed (used in py-intervalsicu source)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/athlete/{id}/activities?oldest=DATE&newest=DATE` | List activities (JSON) |
| GET | `/api/v1/activity/{aid}` | Single activity full object |
| PUT | `/api/v1/activity/{aid}` | Update activity fields (PATCH-like; only changed fields) |
| GET | `/api/v1/activity/{aid}/file` | Original FIT/TCX/GPX (gzipped) |
| GET | `/api/v1/activity/{aid}/fit-file` | Intervals-edited FIT (gzipped) |
| GET | `/api/v1/athlete/{id}/events?oldest=DATE&newest=DATE` | List planned events |
| GET | `/api/v1/athlete/{id}/wellness?oldest=DATE&newest=DATE` | Wellness range (returns list) |
| GET | `/api/v1/athlete/{id}/wellness/{date}` | Single-day wellness |
| PUT | `/api/v1/athlete/{id}/wellness/{date}` | Update wellness |
| PUT | `/api/v1/athlete/{id}/wellness-bulk` | Bulk wellness write (cookbook) |
| GET | `/api/v1/athlete/{id}/power-curves` | Power-curves; query params `curves`, `type`, `filters`, `newest`, `includeRanks`, `subMaxEfforts` |

### Confirmed by direct probe (401 = exists, needs auth)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/athlete/{id}/events/{eid}` | Single event by ID |
| GET | `/api/v1/athlete/{id}` | Athlete record (likely the profile) |
| GET | `/api/v1/athlete/{id}/profile` | Likely a richer profile |

### Standard REST (assumed; will verify in smoke test)

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/athlete/{id}/events` | Create planned event |
| PUT | `/api/v1/athlete/{id}/events/{eid}` | Update event |
| DELETE | `/api/v1/athlete/{id}/events/{eid}` | Delete event |

### Confirmed missing (404)

| Path | Implication |
|---|---|
| `/api/v1/activity/{aid}/streams` | **No JSON endpoint for time-series streams.** Use `interval_summary` field on the activity for interval-level data, or download the FIT file and parse client-side (deferred to v2). |
| `/api/v1/activity/{aid}/intervals` | Same — interval data is embedded in the activity, not a separate endpoint. |

## Field-level discoveries

Activity object (88 fields per `Activity.fields`) carries the form/fitness state inline:

- `icu_ctl`, `icu_atl` — chronic / acute training load **per activity**
- `icu_ftp`, `icu_pm_ftp`, `icu_rolling_ftp` — FTP recorded at activity time + rolling FTP estimate
- `icu_training_load`, `icu_intensity`, `decoupling`, `icu_efficiency_factor`
- `icu_zone_times`, `icu_hr_zone_times`, `pace_zone_times`, `gap_zone_times`
- `interval_summary` — **already-parsed interval-level summary** (avg power/HR/duration per interval). This is what we'll surface as `get_activity_streams` v1.
- `start_date_local`, `timezone` — answers the timezone-of-"today" question

Wellness records carry CTL/ATL/form columns by date — so `get_fitness_curve` is a thin view over `get_wellness_range`.

Event object fields include `category`, `type`, `name`, `description`, `start_date_local`, `end_date_local`, `moving_time`, `distance`, `target`, `load_target`, `time_target`, `distance_target`, `workout_doc` (structured-workout payload), `paired_event_id`. Standard activity-`type` enum applies (Ride, Run, Swim, etc.); `WeightTraining` is the value to use for strength sessions.

## Tool→endpoint mapping (final for v1)

| Skill-facing tool | Endpoint(s) | Notes |
|---|---|---|
| `list_activities` | GET `/athlete/0/activities?oldest&newest` | Direct |
| `get_activity` | GET `/activity/{id}` | Direct |
| `get_activity_streams` | GET `/activity/{id}` → `interval_summary` field | **Misnomer**: returns interval-level summary, not raw 1Hz streams. Documented in the tool description. Raw stream support deferred to v2 (parse FIT file). |
| `list_events` | GET `/athlete/0/events?oldest&newest` | Direct |
| `get_event` | GET `/athlete/0/events/{id}` | Direct |
| `create_event` | POST `/athlete/0/events` | Verify in smoke test |
| `update_event` | PUT `/athlete/0/events/{id}` | Verify in smoke test |
| `delete_event` | DELETE `/athlete/0/events/{id}` | Verify in smoke test |
| `get_wellness_range` | GET `/athlete/0/wellness?oldest&newest` | Direct |
| `get_fitness_curve` | GET `/athlete/0/wellness?oldest&newest` → project `id`, `ctl`, `atl`, `(ctl-atl)` | Wellness columns expose CTL/ATL/form |
| `get_ftp_history` | GET `/athlete/0/activities?oldest&newest` → project `(start_date_local, icu_ftp, icu_pm_ftp)` | Sourced from activity series |
| `get_athlete_profile` | GET `/athlete/0` (try `/athlete/0/profile` if needed) | Verify shape in smoke test |

## Open verification items (need live API key)

- Exact response shape of POST/PUT/DELETE `/events`
- Whether `/athlete/0` or `/athlete/0/profile` is the right "rich profile" endpoint
- What event `category` enum values are valid
- Whether `WeightTraining` is the canonical type for strength sessions (vs `Workout`, `Strength`, `Other`)

These get nailed down in Phase 7 (smoke test) and folded into formatter assertions / Pydantic enums in Phase 8.

## Decisions for the implementation

- Sync httpx, not async — simpler for personal use, easy to refactor later if needed.
- Errors: typed exceptions (`AuthError`, `ForbiddenError`, `NotFoundError`, `ValidationError`, `RateLimitError`, `UpstreamError`) all inheriting from `IntervalsAPIError`.
- Athlete-id `0` baked in — no `INTERVALS_ATHLETE_ID` env var needed. Will clean from `AITrainer/.mcp.json` and `SETUP.md` in Phase 8.
- `interval_summary` is what `get_activity_streams` returns; raw streams = v2.
- No `wellness_put` for v1 — too easy to clobber Oura-synced data (the `locked` gotcha from the cookbook). Add later if/when a skill needs it.
