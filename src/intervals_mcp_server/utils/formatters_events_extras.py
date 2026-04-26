"""
Formatters for the event-bulk-operation MCP tools.

These helpers are intentionally self-contained — they duplicate (rather than
import) the per-event field extraction from `utils.formatting.format_event_summary`
to keep zero coupling with the shared formatting module that another concurrent
agent may be modifying.
"""

from __future__ import annotations

import json
from typing import Any


def _summarise_event(event: dict[str, Any]) -> str:
    """Render a single event as a short multi-line summary.

    Mirrors the field-extraction logic of `format_event_summary` in
    `utils/formatting.py` so this module has no cross-import dependency on it.
    """
    event_date = event.get("start_date_local", event.get("date", "Unknown"))
    if event.get("workout"):
        event_type = "Workout"
    elif event.get("race"):
        event_type = "Race"
    else:
        event_type = event.get("category") or "Other"
    event_name = event.get("name", "Unnamed")
    event_id = event.get("id", "N/A")
    event_desc = event.get("description", "No description")
    return (
        f"Date: {event_date}\n"
        f"ID: {event_id}\n"
        f"Type: {event_type}\n"
        f"Name: {event_name}\n"
        f"Description: {event_desc}"
    )


def _events_table(events: list[dict[str, Any]]) -> str:
    """Render a markdown table of events. Falls back to a bullet list when empty."""
    if not events:
        return "_(no events)_"
    lines = [
        "| ID | Date | Category | Type | Name |",
        "|---|---|---|---|---|",
    ]
    for ev in events:
        if not isinstance(ev, dict):
            continue
        eid = ev.get("id", "—")
        date = ev.get("start_date_local") or ev.get("date") or "—"
        cat = ev.get("category") or "—"
        etype = ev.get("type") or "—"
        name = (ev.get("name") or "—").replace("|", "/")
        lines.append(f"| {eid} | {date} | {cat} | {etype} | {name} |")
    return "\n".join(lines)


def format_apply_plan_result(result: Any) -> str:
    """Render the response from POST /events/apply-plan.

    The OpenAPI spec only types the response as a generic object; in practice
    intervals.icu returns either a list of created events or a wrapper dict
    such as `{"events": [...], "count": N}`. We cope with both.
    """
    if isinstance(result, list):
        return f"Applied plan: {len(result)} event(s) created.\n\n{_events_table(result)}"
    if isinstance(result, dict):
        events = result.get("events") if isinstance(result.get("events"), list) else None
        if events is not None:
            count = result.get("count", len(events))
            return f"Applied plan: {count} event(s) created.\n\n{_events_table(events)}"
        # Generic dict — render it as JSON so the user sees what came back.
        return "Applied plan. Response:\n\n```json\n" + json.dumps(result, indent=2) + "\n```"
    return "Applied plan (no detail returned)."


def format_bulk_create_result(events: list[dict[str, Any]]) -> str:
    """Render the response from POST /events/bulk."""
    if not events:
        return "No events created."
    return f"Created {len(events)} event(s):\n\n{_events_table(events)}"


def format_bulk_delete_result(result: Any) -> str:
    """Render the response from PUT /events/bulk-delete.

    The API response is `{"eventsDeleted": N}` per the spec.
    """
    if isinstance(result, dict):
        deleted = result.get("eventsDeleted")
        if deleted is not None:
            return f"Deleted {deleted} event(s)."
        return "Bulk delete response:\n\n```json\n" + json.dumps(result, indent=2) + "\n```"
    if isinstance(result, list):
        return f"Deleted {len(result)} event(s)."
    return "Bulk delete completed."


def format_duplicate_events_result(events: list[dict[str, Any]]) -> str:
    """Render the response from POST /duplicate-events."""
    if not events:
        return "No events duplicated."
    return f"Duplicated {len(events)} event(s):\n\n{_events_table(events)}"


def format_mark_done_result(activity: dict[str, Any]) -> str:
    """Render the activity returned by POST /events/{eventId}/mark-done.

    The endpoint creates a manual *activity* matching the planned event, so the
    response is an activity, not an event. We surface the canonical activity
    fields rather than reusing event formatting.
    """
    if not isinstance(activity, dict):
        return "Marked event as done (no activity detail returned)."
    lines = [
        "Marked event as done. Activity created:",
        "",
        f"- Activity ID: {activity.get('id', 'N/A')}",
        f"- Type: {activity.get('type', 'N/A')}",
        f"- Start: {activity.get('start_date_local', 'N/A')}",
    ]
    for label, key in [
        ("Name", "name"),
        ("Moving time (s)", "moving_time"),
        ("Distance (m)", "distance"),
        ("Average power (W)", "icu_average_watts"),
        ("Training load", "icu_training_load"),
        ("FTP at activity (W)", "icu_ftp"),
    ]:
        v = activity.get(key)
        if v is not None:
            lines.append(f"- {label}: {v}")
    return "\n".join(lines)


def format_bulk_update_result(result: Any) -> str:
    """Render the response from PUT /events (bulk update over a date range).

    The API returns a list of the updated events.
    """
    if isinstance(result, list):
        if not result:
            return "Bulk update: no events matched the date range (0 updated)."
        return f"Updated {len(result)} event(s):\n\n{_events_table(result)}"
    if isinstance(result, dict):
        return "Bulk update response:\n\n```json\n" + json.dumps(result, indent=2) + "\n```"
    return "Bulk update completed."


def format_event_tags(tags: list[Any]) -> str:
    """Render the GET /event-tags response.

    The OpenAPI spec types this as `array<string>`; live probing against an
    empty calendar confirmed `[]`. We also defensively handle the case where
    the API returns objects (`[{"name": "...", ...}, ...]`).
    """
    if not tags:
        return "_(no event tags found)_"
    lines = ["Event tags:", ""]
    for tag in tags:
        if isinstance(tag, str):
            lines.append(f"- {tag}")
        elif isinstance(tag, dict):
            label = tag.get("name") or tag.get("tag") or tag.get("id") or json.dumps(tag)
            lines.append(f"- {label}")
        else:
            lines.append(f"- {tag}")
    return "\n".join(lines)
