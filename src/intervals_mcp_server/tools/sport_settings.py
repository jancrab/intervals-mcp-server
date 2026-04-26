"""
Sport-settings MCP tools for Intervals.icu.

Each athlete has multiple sport-settings records (one per discipline group:
Ride, Run, Swim, Other). This module exposes CRUD plus the auxiliary
`apply`, `matching-activities`, and `pace_distances` endpoints.

The module mirrors the patterns used by `tools/wellness.py` and
`tools/events.py`:

- `make_intervals_request` for HTTP
- `resolve_athlete_id` for athlete resolution
- All tools return a markdown / human-readable string
- Errors from the API surface as a one-line ``Error ...:`` message
"""

from __future__ import annotations

import json
from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatters_sport_settings import (
    format_matching_activities,
    format_pace_distances,
    format_sport_settings_list,
    format_sport_settings_summary,
)
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


def _is_error(result: Any) -> bool:
    """True if the API client returned an error dict."""
    return isinstance(result, dict) and result.get("error") is True


def _error_message(result: dict[str, Any], action: str) -> str:
    """Format an API error response as a one-line user message."""
    return f"Error {action}: {result.get('message', 'Unknown error')}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_sport_settings(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """List all sport settings for the athlete.

    Each athlete has one sport-settings record per discipline group
    (Ride, Run, Swim, Other), each with its own FTP, LTHR, max HR,
    threshold pace, and zone definitions.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/sport-settings",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching sport settings")  # type: ignore[arg-type]

    if not isinstance(result, list):
        return "Unexpected response: sport-settings list was not a JSON array."

    if not result:
        return f"No sport settings found for athlete {athlete_id_to_use}."

    return format_sport_settings_list(result)


@mcp.tool()
async def get_sport_settings(
    settings_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get a single sport-settings record by id or activity type.

    Args:
        settings_id: Either the numeric settings record ID, or an activity type
            like ``Run``, ``Ride``, ``Swim``. Activity-type lookups return the
            settings record whose ``types`` list contains that type.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not settings_id:
        return "Error: settings_id is required (numeric id or activity type)."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/sport-settings/{settings_id}",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching sport settings")  # type: ignore[arg-type]
    if not isinstance(result, dict):
        return f"No sport settings found for {settings_id}."

    return format_sport_settings_summary(result)


@mcp.tool()
async def list_activities_matching_sport_settings(
    settings_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """List activities that match a given sport-settings record.

    Useful before calling ``apply_sport_settings_to_activities`` to verify
    which activities would be touched by recomputing zones.

    Args:
        settings_id: The settings record ID or activity type.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not settings_id:
        return "Error: settings_id is required."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/sport-settings/{settings_id}/matching-activities",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching matching activities")  # type: ignore[arg-type]
    if not isinstance(result, list):
        return "No matching activities found."

    return format_matching_activities(result)


@mcp.tool()
async def list_pace_distances_for_sport(
    settings_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """List pace-curve distances and best-effort defaults for a sport.

    Args:
        settings_id: The settings record ID or activity type (e.g. ``Run``).
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not settings_id:
        return "Error: settings_id is required."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/sport-settings/{settings_id}/pace_distances",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching pace distances")  # type: ignore[arg-type]

    return format_pace_distances(result)  # type: ignore[arg-type]


@mcp.tool()
async def list_pace_distances(
    api_key: str | None = None,
) -> str:
    """List the global pace-curve distances (sport-agnostic).

    The Intervals.icu pace_distances endpoint without an athlete in the path
    returns the global set of available distances and (typically) ``null``
    defaults — defaults are configured per sport.

    Args:
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    result = await make_intervals_request(
        url="/pace_distances",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching global pace distances")  # type: ignore[arg-type]

    return format_pace_distances(result)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_sport_settings(
    types: list[str],
    athlete_id: str | None = None,
    api_key: str | None = None,
    settings: dict[str, Any] | None = None,
) -> str:
    """Create a new sport-settings record with default values.

    Intervals.icu seeds the record with sensible defaults for the chosen
    activity types. Pass extra fields via ``settings`` to override defaults
    (e.g., ``{"ftp": 280, "lthr": 168}``).

    Args:
        types: List of activity types to associate with the record (e.g.
            ``["Run", "TrailRun"]``).
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
        settings: Optional additional fields to merge into the body (FTP, LTHR,
            zones, etc.).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not types or not isinstance(types, list):
        return "Error: 'types' must be a non-empty list of activity types."

    body: dict[str, Any] = {"types": types}
    if settings:
        if not isinstance(settings, dict):
            return "Error: 'settings' must be a dict if provided."
        body.update(settings)

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/sport-settings",
        api_key=api_key,
        method="POST",
        data=body,
    )
    if _is_error(result):
        return _error_message(result, "creating sport settings")  # type: ignore[arg-type]
    if isinstance(result, dict):
        return f"Successfully created sport settings id: {result.get('id', '—')}"
    return "Sport settings created."


@mcp.tool()
async def update_sport_settings(
    settings_id: str,
    settings: dict[str, Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Update a single sport-settings record by id or activity type.

    Args:
        settings_id: The settings record ID or activity type (e.g. ``Run``).
        settings: Fields to update (e.g. ``{"ftp": 285, "lthr": 169}``).
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not settings_id:
        return "Error: settings_id is required."
    if not isinstance(settings, dict) or not settings:
        return "Error: 'settings' must be a non-empty dict of fields to update."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/sport-settings/{settings_id}",
        api_key=api_key,
        method="PUT",
        data=settings,
    )
    if _is_error(result):
        return _error_message(result, "updating sport settings")  # type: ignore[arg-type]
    if isinstance(result, dict):
        return f"Successfully updated sport settings id: {result.get('id', settings_id)}"
    return "Sport settings updated."


@mcp.tool()
async def update_sport_settings_multi(
    updates: list[dict[str, Any]],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Update multiple sport-settings records in one call (bulk).

    Each item in ``updates`` should contain at minimum an ``id`` field
    identifying which record to update, plus the fields to change.

    Args:
        updates: List of partial sport-settings dicts, each with an ``id``.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not isinstance(updates, list) or not updates:
        return "Error: 'updates' must be a non-empty list of sport-settings dicts."
    for item in updates:
        if not isinstance(item, dict):
            return "Error: every entry in 'updates' must be a dict."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/sport-settings",
        api_key=api_key,
        method="PUT",
        data=updates,  # type: ignore[arg-type]
    )
    if _is_error(result):
        return _error_message(result, "bulk-updating sport settings")  # type: ignore[arg-type]
    if isinstance(result, list):
        return f"Successfully updated {len(result)} sport-settings records."
    if isinstance(result, dict):
        return "Successfully updated sport settings (bulk)."
    return "Sport settings bulk update completed."


@mcp.tool()
async def delete_sport_settings(
    settings_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Delete a sport-settings record.

    Args:
        settings_id: The settings record ID to delete.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not settings_id:
        return "Error: settings_id is required."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/sport-settings/{settings_id}",
        api_key=api_key,
        method="DELETE",
    )
    if _is_error(result):
        return _error_message(result, "deleting sport settings")  # type: ignore[arg-type]
    if isinstance(result, dict) and result:
        return f"Sport settings deleted: {json.dumps(result)}"
    return f"Sport settings {settings_id} deleted."


@mcp.tool()
async def apply_sport_settings_to_activities(
    settings_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Apply a sport-settings record to all matching activities (recomputes zones).

    This is an asynchronous operation on the Intervals.icu side; the API
    accepts the request and processes activities in the background. Use
    ``list_activities_matching_sport_settings`` first to preview which
    activities will be touched.

    Args:
        settings_id: The settings record ID or activity type.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not settings_id:
        return "Error: settings_id is required."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/sport-settings/{settings_id}/apply",
        api_key=api_key,
        method="PUT",
    )
    if _is_error(result):
        return _error_message(result, "applying sport settings to activities")  # type: ignore[arg-type]
    return (
        f"Apply request accepted for sport-settings {settings_id}. "
        "Intervals.icu is recomputing zones for matching activities asynchronously."
    )
