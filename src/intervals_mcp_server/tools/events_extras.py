"""
Bulk and auxiliary event MCP tools for Intervals.icu.

This module adds tools that operate on multiple events at once, plus a couple
of one-off helpers (`mark_event_as_done`, `list_event_tags`). They complement
the per-event CRUD tools in `events.py`.

Body shapes here were derived from the live OpenAPI spec at
`https://intervals.icu/api/v1/docs` (operationIds: `markEventAsDone`,
`applyPlan`, `createMultipleEvents`, `deleteEventsBulk`, `duplicateEvents`,
`updateEvents`, `listTags_1`).
"""

from __future__ import annotations

from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config

# Import mcp instance from shared module so tool registration happens on import.
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401
from intervals_mcp_server.utils.formatters_events_extras import (
    format_apply_plan_result,
    format_bulk_create_result,
    format_bulk_delete_result,
    format_bulk_update_result,
    format_duplicate_events_result,
    format_event_tags,
    format_mark_done_result,
)
from intervals_mcp_server.utils.validation import resolve_athlete_id, validate_date

config = get_config()

# Mutable fields per the project's endpoint inventory. PUT /events technically
# accepts the full event object, but the inventory restricts bulk updates to
# these flags; keep the wire body tight to avoid accidental clobbering.
_BULK_UPDATE_ALLOWED_FIELDS = {"hide_from_athlete", "athlete_cannot_edit"}


def _error_msg(result: Any, prefix: str) -> str | None:
    """Extract an error message from an API result dict, if present."""
    if isinstance(result, dict) and result.get("error"):
        return f"{prefix}: {result.get('message', 'Unknown error')}"
    return None


@mcp.tool()
async def mark_event_as_done(
    event_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Mark a planned event as done by creating a matching manual activity.

    Calls POST `/athlete/{id}/events/{eventId}/mark-done`. The endpoint takes no
    request body; the response is a newly-created **activity** (not an event)
    that mirrors the planned workout.

    Args:
        event_id: The Intervals.icu event ID to mark done.
        athlete_id: Optional athlete ID (falls back to ATHLETE_ID env var).
        api_key: Optional API key (falls back to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not event_id:
        return "Error: No event ID provided."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events/{event_id}/mark-done",
        api_key=api_key,
        method="POST",
    )
    err = _error_msg(result, "Error marking event as done")
    if err:
        return err
    if not isinstance(result, dict):
        return "Marked event as done, but response was not an activity object."
    return format_mark_done_result(result)


@mcp.tool()
async def apply_plan(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    start_date_local: str,
    folder_id: int,
    athlete_id: str | None = None,
    api_key: str | None = None,
    extra_workouts: list[dict[str, Any]] | None = None,
) -> str:
    """Apply a training plan (a folder of workouts) to the athlete's calendar.

    Calls POST `/athlete/{id}/events/apply-plan`. Body schema (per spec):
        {
          "start_date_local": "<YYYY-MM-DD or full ISO>",
          "folder_id": <int>,
          "extra_workouts": [<Workout>, ...]   # optional
        }

    Args:
        start_date_local: First date the plan should anchor to (YYYY-MM-DD).
        folder_id: ID of the workout folder representing the plan.
        athlete_id: Optional athlete ID (falls back to ATHLETE_ID env var).
        api_key: Optional API key (falls back to API_KEY env var).
        extra_workouts: Optional list of additional Workout dicts to splice in.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    try:
        validate_date(start_date_local[:10])
    except ValueError as e:
        return f"Error: {e}"

    body: dict[str, Any] = {
        "start_date_local": start_date_local,
        "folder_id": folder_id,
    }
    if extra_workouts:
        body["extra_workouts"] = extra_workouts

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events/apply-plan",
        api_key=api_key,
        method="POST",
        data=body,
    )
    err = _error_msg(result, "Error applying plan")
    if err:
        return err
    return format_apply_plan_result(result)


@mcp.tool()
async def create_multiple_events(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    events: list[dict[str, Any]],
    athlete_id: str | None = None,
    api_key: str | None = None,
    upsert: bool = False,
    upsert_on_uid: bool = False,
    update_plan_applied: bool = False,
) -> str:
    """Create multiple planned events on the calendar in one request.

    Calls POST `/athlete/{id}/events/bulk`. The body is a JSON **array** of
    event dicts (NOT wrapped in `{"events": [...]}`). Each event follows the
    same shape as a single-event POST.

    Args:
        events: List of event dicts. Minimum useful keys: `start_date_local`,
            `category` (e.g. "WORKOUT", "NOTE", "RACE_A"), `type`, `name`.
        athlete_id: Optional athlete ID (falls back to ATHLETE_ID env var).
        api_key: Optional API key (falls back to API_KEY env var).
        upsert: If True, insert-or-update by `id`.
        upsert_on_uid: If True, insert-or-update by `uid` (external_id).
        update_plan_applied: Forwarded as a query flag; controls whether a
            plan-applied marker is updated.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not isinstance(events, list) or not events:
        return "Error: events must be a non-empty list of event dicts."

    params: dict[str, Any] = {
        "upsert": str(upsert).lower(),
        "upsertOnUid": str(upsert_on_uid).lower(),
        "updatePlanApplied": str(update_plan_applied).lower(),
    }

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events/bulk",
        api_key=api_key,
        method="POST",
        params=params,
        data=events,  # type: ignore[arg-type]  # client serializes via json.dumps
    )
    err = _error_msg(result, "Error creating events")
    if err:
        return err
    if not isinstance(result, list):
        return "Bulk create succeeded, but response was not a list of events."
    return format_bulk_create_result(result)


@mcp.tool()
async def delete_events_bulk(
    events: list[dict[str, Any]],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Delete events by id or external_id in one request.

    Calls PUT `/athlete/{id}/events/bulk-delete`. Body schema (per spec):
        [{"id": <int>}, {"external_id": "<string>"}, ...]

    This is distinct from `delete_events_by_date_range` (which deletes
    everything in a window).

    Args:
        events: List of `{"id": ...}` or `{"external_id": ...}` dicts.
        athlete_id: Optional athlete ID (falls back to ATHLETE_ID env var).
        api_key: Optional API key (falls back to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not isinstance(events, list) or not events:
        return "Error: events must be a non-empty list of {id} or {external_id} dicts."
    for ev in events:
        if not isinstance(ev, dict) or not ({"id", "external_id"} & set(ev.keys())):
            return "Error: each entry must contain either 'id' or 'external_id'."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events/bulk-delete",
        api_key=api_key,
        method="PUT",
        data=events,  # type: ignore[arg-type]  # client serializes via json.dumps
    )
    err = _error_msg(result, "Error deleting events")
    if err:
        return err
    return format_bulk_delete_result(result)


@mcp.tool()
async def duplicate_events(
    event_ids: list[int],
    num_copies: int = 1,
    weeks_between: int = 1,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Duplicate one or more events on the athlete's calendar.

    Calls POST `/athlete/{id}/duplicate-events`. Body schema (per spec):
        {
          "numCopies": <int>,
          "weeksBetween": <int>,
          "eventIds": [<int>, ...]
        }

    Args:
        event_ids: IDs of events to duplicate.
        num_copies: Number of copies to make of each event.
        weeks_between: Spacing in weeks between successive copies.
        athlete_id: Optional athlete ID (falls back to ATHLETE_ID env var).
        api_key: Optional API key (falls back to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not isinstance(event_ids, list) or not event_ids:
        return "Error: event_ids must be a non-empty list of integers."

    body = {
        "numCopies": num_copies,
        "weeksBetween": weeks_between,
        "eventIds": list(event_ids),
    }
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/duplicate-events",
        api_key=api_key,
        method="POST",
        data=body,
    )
    err = _error_msg(result, "Error duplicating events")
    if err:
        return err
    if not isinstance(result, list):
        return "Duplicate succeeded, but response was not a list of events."
    return format_duplicate_events_result(result)


@mcp.tool()
async def update_events_in_range(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    start_date: str,
    end_date: str,
    hide_from_athlete: bool | None = None,
    athlete_cannot_edit: bool | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Bulk-update events for a date range.

    Calls PUT `/athlete/{id}/events?oldest=...&newest=...`. The OpenAPI spec
    types the body as the full event object, but the project's endpoint
    inventory restricts mutable fields to `hide_from_athlete` and
    `athlete_cannot_edit`. Only those two are forwarded.

    Args:
        start_date: Start of range (YYYY-MM-DD).
        end_date: End of range (YYYY-MM-DD).
        hide_from_athlete: Optional flag to hide matching events from the athlete.
        athlete_cannot_edit: Optional flag to lock matching events for the athlete.
        athlete_id: Optional athlete ID (falls back to ATHLETE_ID env var).
        api_key: Optional API key (falls back to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    try:
        validated_start = validate_date(start_date)
        validated_end = validate_date(end_date)
    except ValueError as e:
        return f"Error: {e}"

    body: dict[str, Any] = {}
    if hide_from_athlete is not None:
        body["hide_from_athlete"] = hide_from_athlete
    if athlete_cannot_edit is not None:
        body["athlete_cannot_edit"] = athlete_cannot_edit
    if not body:
        return (
            "Error: at least one of `hide_from_athlete` or `athlete_cannot_edit` "
            "must be provided (only those fields are mutable in bulk)."
        )
    # Defence in depth — if a future caller manages to slip something else in,
    # filter it before we send the payload.
    body = {k: v for k, v in body.items() if k in _BULK_UPDATE_ALLOWED_FIELDS}

    params = {"oldest": validated_start, "newest": validated_end}
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events",
        api_key=api_key,
        method="PUT",
        params=params,
        data=body,
    )
    err = _error_msg(result, "Error updating events")
    if err:
        return err
    return format_bulk_update_result(result)


@mcp.tool()
async def list_event_tags(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """List all tags applied to events on the athlete's calendar.

    Calls GET `/athlete/{id}/event-tags`. Per the live API (probed
    against an empty calendar) and the spec, the response is `array<string>`.
    We also handle a defensive fallback for `array<object>`.

    Args:
        athlete_id: Optional athlete ID (falls back to ATHLETE_ID env var).
        api_key: Optional API key (falls back to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/event-tags",
        api_key=api_key,
    )
    err = _error_msg(result, "Error fetching event tags")
    if err:
        return err
    tags = result if isinstance(result, list) else []
    return format_event_tags(tags)
