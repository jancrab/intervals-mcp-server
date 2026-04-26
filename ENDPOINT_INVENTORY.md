# intervals.icu API endpoint inventory

Generated 2026-04-26 from `https://intervals.icu/api/v1/docs` (OpenAPI 3.0.1, title "Intervals.icu API", version v1.0.0).

Cross-referenced against the 12 tools shipped in `intervals-icu-mcp` v1.0.

## Summary

- **Total operations**: 144
- **Already covered (v1 tools)**: 7
- **To ADD (in-scope)**: 128
- **Borderline (chat/social — your call)**: 9
- **Defer (webhooks)**: 0
- **Reject (OAuth / coach / admin / multi-tenant)**: 0

### Operations by tag

| Tag | Total | Covered | To add | Borderline | Defer | Reject |
|---|---|---|---|---|---|---|
| Activities | 51 | 2 | 49 | 0 | 0 | 0 |
| Athletes | 8 | 1 | 7 | 0 | 0 | 0 |
| Chats | 9 | 0 | 0 | 9 | 0 | 0 |
| Custom Items | 7 | 0 | 7 | 0 | 0 | 0 |
| Events | 16 | 4 | 12 | 0 | 0 | 0 |
| Gear | 9 | 0 | 9 | 0 | 0 | 0 |
| Library | 19 | 0 | 19 | 0 | 0 | 0 |
| Routes | 4 | 0 | 4 | 0 | 0 | 0 |
| Shared Events | 1 | 0 | 1 | 0 | 0 | 0 |
| Sports | 10 | 0 | 10 | 0 | 0 | 0 |
| Weather | 3 | 0 | 3 | 0 | 0 | 0 |
| Wellness | 6 | 0 | 6 | 0 | 0 | 0 |
| o-auth-server-controller | 1 | 0 | 1 | 0 | 0 | 0 |

## Already covered (v1)

- `delete_event` ← `DELETE /api/v1/athlete/{id}/events/{eventId}`
- `get_activity (also surfaces interval_summary as get_activity_streams)` ← `GET /api/v1/activity/{id}`
- `get_athlete_profile` ← `GET /api/v1/athlete/{id}`
- `list_activities` ← `GET /api/v1/athlete/{id}/activities`
- `list_events` ← `GET /api/v1/athlete/{id}/events`
- `get_event` ← `GET /api/v1/athlete/{id}/events/{eventId}`
- `get_wellness_range (also exposed as get_fitness_curve view)` ← `GET /api/v1/athlete/{id}/wellness`
- `create_event` ← `POST /api/v1/athlete/{id}/events`
- `update_event` ← `PUT /api/v1/athlete/{id}/events/{eventId}`

## To ADD

Each entry: proposed MCP tool name (snake_case), HTTP method+path, and a brief summary. Implementation pattern matches the existing 12 tools (Pydantic input model with `extra="forbid"` → `IntervalsClient` method → markdown/JSON formatter → `@mcp.tool()` registration with `readOnlyHint` / `destructiveHint` annotations).

### Activities

- `delete_activity` — `DELETE /api/v1/activity/{id}` — Delete an activity
- `update_activity` — `PUT /api/v1/activity/{id}` — Update activity
- `find_best_efforts` — `GET /api/v1/activity/{id}/best-efforts` — Find best efforts in the activity
- `delete_intervals` — `PUT /api/v1/activity/{id}/delete-intervals` — Delete intervals
- `download_activity_file` — `GET /api/v1/activity/{id}/file` — Download original activity file, Strava activities not supported
- `download_activity_fit_file` — `GET /api/v1/activity/{id}/fit-file` — Download Intervals.icu generated activity fit file
- `get_gap_histogram` — `GET /api/v1/activity/{id}/gap-histogram` — Get activity gradient adjusted pace histogram
- `download_activity_gpx_file` — `GET /api/v1/activity/{id}/gpx-file` — Download Intervals.icu generated activity gpx file
- `get_activity_h_r_curve` — `GET /api/v1/activity/{id}/hr-curve{ext}` — Get activity heart rate curve in JSON or CSV (use .csv ext) format
- `get_h_r_histogram` — `GET /api/v1/activity/{id}/hr-histogram` — Get activity heart rate histogram
- `get_h_r_training_load_model` — `GET /api/v1/activity/{id}/hr-load-model` — Get activity heart rate training load model
- `get_interval_stats` — `GET /api/v1/activity/{id}/interval-stats` — Return interval like stats for part of the activity
- `get_intervals` — `GET /api/v1/activity/{id}/intervals` — Get activity intervals
- `update_intervals` — `PUT /api/v1/activity/{id}/intervals` — Update intervals for an activity
- `update_interval` — `PUT /api/v1/activity/{id}/intervals/{intervalId}` — Update/create an interval
- `get_activity_map` — `GET /api/v1/activity/{id}/map` — Get activity map data
- `get_activity_pace_curve` — `GET /api/v1/activity/{id}/pace-curve{ext}` — Get activity pace curve in JSON or CSV (use .csv ext) format
- `get_pace_histogram` — `GET /api/v1/activity/{id}/pace-histogram` — Get activity pace histogram
- `list_activity_power_curves_1` — `GET /api/v1/activity/{id}/power-curves{ext}` — Get activity power curves for one or more streams in JSON or CSV (use .csv ext) format
- `get_activity_power_curve` — `GET /api/v1/activity/{id}/power-curve{ext}` — Get activity power curve in JSON or CSV (use .csv ext) format
- `get_power_histogram` — `GET /api/v1/activity/{id}/power-histogram` — Get activity power histogram
- `get_activity_power_spike_model` — `GET /api/v1/activity/{id}/power-spike-model` — Get activity power spike detection model
- `get_power_vs_h_r` — `GET /api/v1/activity/{id}/power-vs-hr{ext}` — Get activity power vs heart rate data in JSON or CSV (use .csv ext) format
- `get_activity_segments` — `GET /api/v1/activity/{id}/segments` — Get activity segments
- `split_interval` — `PUT /api/v1/activity/{id}/split-interval` — Split an interval
- `update_activity_streams` — `PUT /api/v1/activity/{id}/streams` — Update streams for the activity from JSON
- `upload_activity_streams_c_s_v` — `PUT /api/v1/activity/{id}/streams.csv` — Update streams for the activity from CSV
- `get_activity_streams` — `GET /api/v1/activity/{id}/streams{ext}` — List streams for the activity
- `get_time_at_h_r` — `GET /api/v1/activity/{id}/time-at-hr` — Get activity time at heart rate data
- `get_activity_weather_summary` — `GET /api/v1/activity/{id}/weather-summary` — Get activity weather summary information
- `get_activities` — `GET /api/v1/athlete/{athleteId}/activities/{ids}` — Fetch multiple activities by id. Missing activities are ignored
- `upload_activity` — `POST /api/v1/athlete/{id}/activities` — Create new activities from an uploaded file (fit, tcx, gpx or zip or gz of the same) as multipart/form-data
- `list_activities_around` — `GET /api/v1/athlete/{id}/activities-around` — List activities before and after another activity in closest first order
- `download_activities_as_c_s_v` — `GET /api/v1/athlete/{id}/activities.csv` — Download activities as CSV
- `search_for_intervals` — `GET /api/v1/athlete/{id}/activities/interval-search` — Find activities with intervals matching duration and intensity
- `create_manual_activity` — `POST /api/v1/athlete/{id}/activities/manual` — Create a manual activity
- `create_multiple_manual_activities` — `POST /api/v1/athlete/{id}/activities/manual/bulk` — Create multiple manual activities with upsert on external_id
- `search_for_activities` — `GET /api/v1/athlete/{id}/activities/search` — Search for activities by name or tag, returns summary info
- `search_for_activities_full` — `GET /api/v1/athlete/{id}/activities/search-full` — Search for activities by name or tag, returns full activities
- `list_activity_h_r_curves` — `GET /api/v1/athlete/{id}/activity-hr-curves{ext}` — Get best HR for a range of durations for matching activities in the date range
- `list_activity_pace_curves` — `GET /api/v1/athlete/{id}/activity-pace-curves{ext}` — Get best pace for a range of distances for matching activities in the date range
- `list_activity_power_curves` — `GET /api/v1/athlete/{id}/activity-power-curves{ext}` — Get best power for a range of durations for matching activities in the date range
- `list_tags_2` — `GET /api/v1/athlete/{id}/activity-tags` — List all tags that have been applied to the athlete's activities
- `download_activity_fit_files` — `POST /api/v1/athlete/{id}/download-fit-files` — Download zip of Intervals.icu generated activity fit files
- `list_athlete_h_r_curves` — `GET /api/v1/athlete/{id}/hr-curves{ext}` — List best heart rate curves for the athlete
- `get_athlete_m_m_p_model` — `GET /api/v1/athlete/{id}/mmp-model` — Get the power model used to resolve %MMP steps in workouts for the athlete
- `list_athlete_pace_curves` — `GET /api/v1/athlete/{id}/pace-curves{ext}` — List best pace curves for the athlete
- `list_athlete_power_curves` — `GET /api/v1/athlete/{id}/power-curves{ext}` — List best power curves for the athlete
- `get_power_h_r_curve` — `GET /api/v1/athlete/{id}/power-hr-curve` — Get the athlete's power vs heart rate curve for a date range

### Athletes

- `update_athlete_plans` — `PUT /api/v1/athlete-plans` — Change training plans for a list of athletes
- `update_athlete` — `PUT /api/v1/athlete/{id}` — Update an athlete
- `get_athlete_summary` — `GET /api/v1/athlete/{id}/athlete-summary{ext}` — Summary information for followed athletes
- `get_athlete_profile` — `GET /api/v1/athlete/{id}/profile` — Get athlete profile info
- `get_settings` — `GET /api/v1/athlete/{id}/settings/{deviceClass}` — Get the athlete's settings for phone, tablet or desktop
- `get_athlete_training_plan` — `GET /api/v1/athlete/{id}/training-plan` — Get the athlete's training plan
- `update_athlete_plan` — `PUT /api/v1/athlete/{id}/training-plan` — Change the athlete's training plan

### Custom Items

- `list_custom_items` — `GET /api/v1/athlete/{id}/custom-item` — List custom items (charts, custom fields etc.)
- `create_custom_item` — `POST /api/v1/athlete/{id}/custom-item` — Create a custom item
- `update_custom_item_indexes` — `PUT /api/v1/athlete/{id}/custom-item-indexes` — Re-order custom items
- `delete_custom_item` — `DELETE /api/v1/athlete/{id}/custom-item/{itemId}` — Delete a custom item
- `get_custom_item` — `GET /api/v1/athlete/{id}/custom-item/{itemId}` — Get a custom item
- `update_custom_item` — `PUT /api/v1/athlete/{id}/custom-item/{itemId}` — Update a custom item
- `update_custom_item_image` — `POST /api/v1/athlete/{id}/custom-item/{itemId}/image` — Upload a new image for a custom item as multipart/form-data

### Events

- `duplicate_events` — `POST /api/v1/athlete/{id}/duplicate-events` — Duplicate one or more events (planned workouts, notes etc.) on the athlete's calendar
- `list_tags_1` — `GET /api/v1/athlete/{id}/event-tags` — List all tags that have been applied to events on the athlete's calendar
- `delete_events` — `DELETE /api/v1/athlete/{id}/events` — Delete a range of events (planned workouts, notes etc.) from the athlete's calendar
- `update_events` — `PUT /api/v1/athlete/{id}/events` — Update all events for a date range at once. Only hide_from_athlete and athlete_cannot_edit can be updated
- `apply_plan` — `POST /api/v1/athlete/{id}/events/apply-plan` — (no summary)
- `create_multiple_events` — `POST /api/v1/athlete/{id}/events/bulk` — Create multiple events (planned workouts, notes etc.) on the athlete's calendar
- `delete_events_bulk` — `PUT /api/v1/athlete/{id}/events/bulk-delete` — Delete events from an athlete's calendar by id or external_id
- `download_workout_1` — `GET /api/v1/athlete/{id}/events/{eventId}/download{ext}` — Download a planned workout in zwo, mrc, erg or fit format
- `mark_event_as_done` — `POST /api/v1/athlete/{id}/events/{eventId}/mark-done` — Create a manual activity to match a planned workout
- `list_events` — `GET /api/v1/athlete/{id}/events{format}` — List events (planned workouts, notes etc.) on the athlete's calendar, add .csv for CSV output
- `list_fitness_model_events` — `GET /api/v1/athlete/{id}/fitness-model-events` — List events that influence the athlete's fitness calculation in ascending date order
- `download_workouts` — `GET /api/v1/athlete/{id}/workouts.zip` — Download one or more workouts from the athlete's calendar in a zip file

### Gear

- `create_gear` — `POST /api/v1/athlete/{id}/gear` — Create a new gear or component
- `delete_gear` — `DELETE /api/v1/athlete/{id}/gear/{gearId}` — Delete a gear or component
- `update_gear` — `PUT /api/v1/athlete/{id}/gear/{gearId}` — Update a gear or component
- `calc_distance_etc` — `GET /api/v1/athlete/{id}/gear/{gearId}/calc` — Recalculate gear stats
- `create_reminder` — `POST /api/v1/athlete/{id}/gear/{gearId}/reminder` — Create a new reminder
- `delete_reminder` — `DELETE /api/v1/athlete/{id}/gear/{gearId}/reminder/{reminderId}` — Delete a reminder
- `update_reminder` — `PUT /api/v1/athlete/{id}/gear/{gearId}/reminder/{reminderId}` — Update a reminder
- `replace_gear` — `POST /api/v1/athlete/{id}/gear/{gearId}/replace` — Retire a component and replace it with a copy with the same reminders etc.
- `list_gear` — `GET /api/v1/athlete/{id}/gear{ext}` — List athlete gear (use .csv for CSV format)

### Library

- `apply_current_plan_changes` — `PUT /api/v1/athlete/{id}/apply-plan-changes` — Apply any changes from the athlete's current plan to the athlete's calendar
- `download_workout_for_athlete` — `POST /api/v1/athlete/{id}/download-workout{ext}` — Convert a workout to .zwo (Zwift), .mrc, .erg or .fit.
- `duplicate_workouts` — `POST /api/v1/athlete/{id}/duplicate-workouts` — Duplicate workouts on a plan
- `list_folders` — `GET /api/v1/athlete/{id}/folders` — List all the athlete's folders, plans and workouts
- `create_folder` — `POST /api/v1/athlete/{id}/folders` — Create a new workout folder or plan
- `delete_folder` — `DELETE /api/v1/athlete/{id}/folders/{folderId}` — Delete a workout folder or plan including all workouts
- `update_folder` — `PUT /api/v1/athlete/{id}/folders/{folderId}` — Update a workout folder or plan
- `import_workout_file` — `POST /api/v1/athlete/{id}/folders/{folderId}/import-workout` — Create new workout from .zwo, .mrc, .erg or .fit file in a folder
- `list_folder_shared_with` — `GET /api/v1/athlete/{id}/folders/{folderId}/shared-with` — List athletes that the folder or plan has been shared with
- `update_folder_shared_with` — `PUT /api/v1/athlete/{id}/folders/{folderId}/shared-with` — Add/remove athletes from the share list for the folder
- `update_plan_workouts` — `PUT /api/v1/athlete/{id}/folders/{folderId}/workouts` — Update a range of workouts on a plan. Currently only hide_from_athlete can be changed
- `list_tags` — `GET /api/v1/athlete/{id}/workout-tags` — List all tags that have been applied to workouts in the athlete's library
- `list_workouts` — `GET /api/v1/athlete/{id}/workouts` — List all the workouts in the athlete's library
- `create_workout` — `POST /api/v1/athlete/{id}/workouts` — Create a new workout in a folder or plan in the athlete's workout library
- `create_multiple_workouts` — `POST /api/v1/athlete/{id}/workouts/bulk` — Create multiple new workouts in a folder or plan in the athlete's workout library
- `delete_workout` — `DELETE /api/v1/athlete/{id}/workouts/{workoutId}` — Delete a workout (and optionally others added at the same time if the workout is on a plan)
- `show_workout` — `GET /api/v1/athlete/{id}/workouts/{workoutId}` — Get a workout
- `update_workout` — `PUT /api/v1/athlete/{id}/workouts/{workoutId}` — Update a workout
- `download_workout` — `POST /api/v1/download-workout{ext}` — Convert a workout to .zwo (Zwift), .mrc, .erg or .fit

### Routes

- `list_athlete_routes` — `GET /api/v1/athlete/{id}/routes` — List routes for an athlete with activity counts
- `get_athlete_route` — `GET /api/v1/athlete/{id}/routes/{route_id}` — Get a route for an athlete
- `update_athlete_route` — `PUT /api/v1/athlete/{id}/routes/{route_id}` — Update a route for an athlete
- `check_merge` — `GET /api/v1/athlete/{id}/routes/{route_id}/similarity/{other_id}` — How similar is this route to another?

### Shared Events

- `get_shared_event` — `GET /api/v1/shared-event/{id}` — Get a shared event (e.g. race)

### Sports

- `list_settings` — `GET /api/v1/athlete/{athleteId}/sport-settings` — List sport settings for the athlete
- `create_settings` — `POST /api/v1/athlete/{athleteId}/sport-settings` — Create settings for a sport with default values
- `update_settings_multi` — `PUT /api/v1/athlete/{athleteId}/sport-settings` — Update multiple sport settings
- `delete_settings` — `DELETE /api/v1/athlete/{athleteId}/sport-settings/{id}` — Delete sport settings
- `get_settings_1` — `GET /api/v1/athlete/{athleteId}/sport-settings/{id}` — Get sport settings by id or activity type e.g. Run, Ride etc.
- `update_settings` — `PUT /api/v1/athlete/{athleteId}/sport-settings/{id}` — Update sport settings by id or activity type e.g. Run, Ride etc.
- `apply_to_activities` — `PUT /api/v1/athlete/{athleteId}/sport-settings/{id}/apply` — Apply sport settings to matching activities (updates zones), done asynchronously
- `list_matching_activities` — `GET /api/v1/athlete/{athleteId}/sport-settings/{id}/matching-activities` — List activities matching the settings
- `list_pace_distances_for_sport` — `GET /api/v1/athlete/{athleteId}/sport-settings/{id}/pace_distances` — List pace curve distances and best effort defaults for the sport
- `list_pace_distances` — `GET /api/v1/pace_distances` — List pace curve distances

### Weather

- `get_weather_config` — `GET /api/v1/athlete/{id}/weather-config` — Get the athlete's weather forecast configuration
- `update_weather_config` — `PUT /api/v1/athlete/{id}/weather-config` — Update the athlete's weather forecast configuration
- `get_forecast` — `GET /api/v1/athlete/{id}/weather-forecast` — Get weather forecast information

### Wellness

- `upload_wellness` — `POST /api/v1/athlete/{id}/wellness` — Upload wellness records in CSV format as multipart/form-data
- `update_wellness_1` — `PUT /api/v1/athlete/{id}/wellness` — Update a wellness record, id is the day (ISO-8601)
- `update_wellness_bulk` — `PUT /api/v1/athlete/{id}/wellness-bulk` — Update an array of wellness records all for the same athlete
- `get_record` — `GET /api/v1/athlete/{id}/wellness/{date}` — Get wellness record for date (local ISO-8601 day)
- `update_wellness` — `PUT /api/v1/athlete/{id}/wellness/{date}` — Update the wellness record for the date (ISO-8601)
- `list_wellness_records` — `GET /api/v1/athlete/{id}/wellness{ext}` — List wellness records for date range (use .csv for CSV format)

### o-auth-server-controller

- `disconnect_app` — `DELETE /api/v1/disconnect-app` — Disconnect the athlete from the app matching the bearer token

## Borderline (your call)

Social / chat / feed endpoints. Useful for community features but outside training analysis. Recommend skipping for v1.5.

- `GET /api/v1/activity/{id}/messages` (tag: Chats) — List all messages (comments) for the activity
- `POST /api/v1/activity/{id}/messages` (tag: Chats) — Add a message (comment) to an activity
- `GET /api/v1/athlete/{id}/chats` (tag: Chats) — List chats for the athlete, most recently active first
- `POST /api/v1/chats/send-message` (tag: Chats) — Send a message
- `GET /api/v1/chats/{id}` (tag: Chats) — Get a chat by id
- `GET /api/v1/chats/{id}/messages` (tag: Chats) — List messages for the chat, most recent first
- `DELETE /api/v1/chats/{id}/messages/{msgId}` (tag: Chats) — Delete a message
- `PUT /api/v1/chats/{id}/messages/{msgId}` (tag: Chats) — Update a message
- `PUT /api/v1/chats/{id}/messages/{msgId}/seen` (tag: Chats) — Update last seen message for the chat

## Quirks summary

- **2 multipart/form-data endpoints** (file upload). Examples: `PUT /api/v1/activity/{id}/streams.csv`, `POST /api/v1/athlete/{id}/activities`
- **8 potentially paginated endpoints** (have `page`/`offset`/`limit`/`next`/`after` query params).
- **13 endpoints use the `oldest`/`newest` date-range convention** (ISO 8601, YYYY-MM-DD). Examples: `PUT /api/v1/athlete/{id}/folders/{folderId}/workouts`, `PUT /api/v1/athlete/{id}/events`, `DELETE /api/v1/athlete/{id}/events`
- **5 bulk-write endpoints**: `PUT /api/v1/athlete/{id}/wellness-bulk`, `PUT /api/v1/athlete/{id}/events/bulk-delete`, `POST /api/v1/athlete/{id}/workouts/bulk`, `POST /api/v1/athlete/{id}/events/bulk`, `POST /api/v1/athlete/{id}/activities/manual/bulk`

- **Wellness `locked` field**: per the cookbook, wellness writes are silently overwritten by Oura/Garmin sync unless `locked: true` is set in the payload. Skill must echo this.
- **Athlete-id `0` shortcut**: documented for some GET endpoints, unverified for writes. We use the real numeric ID via required `INTERVALS_ATHLETE_ID` env var.
- **Auth**: HTTP Basic with username = literal `API_KEY`, password = the user's API key. Same for all endpoints.

## Recommended implementation order

Sort by value-to-AITrainer-skills × implementation cost.

**Wave 1 — high value, low cost** (single endpoint, simple JSON, no special handling):


**Wave 2 — write extensions** (POST/PUT/DELETE on the same domains, gated by harness `permissions.ask`).

**Wave 3 — file ops** (multipart upload, gzipped download).

**Wave 4 — borderline social** (chat / messages / followers) — only if you want them.
