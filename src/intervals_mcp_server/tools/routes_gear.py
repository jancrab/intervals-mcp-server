"""
Routes and gear MCP tools for Intervals.icu.

Adds 13 tools (4 routes + 9 gear) covering:

Routes
------
- ``list_athlete_routes`` — GET /athlete/{id}/routes
- ``get_athlete_route`` — GET /athlete/{id}/routes/{route_id}
- ``update_athlete_route`` — PUT /athlete/{id}/routes/{route_id}  (body: AthleteRoute)
- ``check_route_merge`` — GET /athlete/{id}/routes/{route_id}/similarity/{other_id}

Gear
----
- ``list_gear`` — GET /athlete/{id}/gear{ext}    (json|csv)
- ``create_gear`` — POST /athlete/{id}/gear  (body: Gear)
- ``update_gear`` — PUT /athlete/{id}/gear/{gearId}  (body: Gear)
- ``delete_gear`` — DELETE /athlete/{id}/gear/{gearId}
- ``recalc_gear_distance`` — GET /athlete/{id}/gear/{gearId}/calc
- ``replace_gear`` — POST /athlete/{id}/gear/{gearId}/replace  (body: Gear)
- ``create_gear_reminder`` — POST /athlete/{id}/gear/{gearId}/reminder  (body: GearReminder)
- ``update_gear_reminder`` — PUT /athlete/{id}/gear/{gearId}/reminder/{reminderId}
   (body: GearReminder; query: reset, snoozeDays)
- ``delete_gear_reminder`` — DELETE /athlete/{id}/gear/{gearId}/reminder/{reminderId}

The patterns follow ``tools/sport_settings.py`` and ``tools/activity_analytics.py``:
``make_intervals_request`` for JSON; ``_fetch_csv`` for the CSV mode of
``list_gear``. All bodies are passed through verbatim from caller-provided
dicts so callers can supply any subset of the schema fields.

Body schemas verified against the Intervals.icu OpenAPI spec at
``https://intervals.icu/api/v1/docs`` (operations ``createGear``, ``updateGear``,
``replaceGear``, ``createReminder``, ``updateReminder``, ``updateAthleteRoute``).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx  # pylint: disable=import-error

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatters_routes_gear import (
    format_csv_block,
    format_gear_list,
    format_gear_recalc_result,
    format_gear_reminder_result,
    format_route_detail,
    format_route_list,
    format_route_similarity,
    format_route_update_result,
)
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

logger = logging.getLogger("intervals_icu_mcp_server")
config = get_config()


def _is_error(result: Any) -> bool:
    """True if the API client returned an error dict."""
    return isinstance(result, dict) and result.get("error") is True


def _error_message(result: dict[str, Any], action: str) -> str:
    """Format an API error response as a one-line user message."""
    return f"Error {action}: {result.get('message', 'Unknown error')}"


async def _fetch_csv(url_path: str, api_key: str | None) -> str:
    """Fetch a non-JSON (CSV) endpoint and return its body as text.

    Mirrors ``activity_analytics._fetch_csv``. ``make_intervals_request``
    cannot be used because it parses the response as JSON.
    """
    key_to_use = api_key if api_key is not None else config.api_key
    if not key_to_use:
        return "Error: API key is required. Set API_KEY env var or pass api_key."
    full_url = f"{config.intervals_api_base_url}{url_path}"
    auth = httpx.BasicAuth("API_KEY", key_to_use)
    headers = {"User-Agent": config.user_agent, "Accept": "text/csv"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(full_url, auth=auth, headers=headers, timeout=30.0)
        if response.status_code >= 400:
            logger.error(
                "CSV fetch failed: %s %s — %s",
                response.status_code,
                full_url,
                response.text[:200],
            )
            return f"Error fetching CSV: HTTP {response.status_code}: {response.text[:200]}"
        return response.text
    except httpx.HTTPError as exc:
        logger.error("CSV fetch error: %s", exc)
        return f"Error fetching CSV: {exc}"


def _validate_format(fmt: str) -> str | None:
    if fmt not in ("json", "csv"):
        return f"Error: format must be 'json' or 'csv' (got {fmt!r})."
    return None


# ===========================================================================
# Routes
# ===========================================================================


@mcp.tool()
async def list_athlete_routes(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """List all routes saved by the athlete.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/routes",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching routes")  # type: ignore[arg-type]
    if not isinstance(result, list):
        return "Unexpected response: routes list was not a JSON array."
    if not result:
        return f"No routes found for athlete {athlete_id_to_use}."
    return format_route_list(result)


@mcp.tool()
async def get_athlete_route(
    route_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get a single route by route_id.

    Args:
        route_id: The numeric route ID.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not route_id:
        return "Error: route_id is required."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/routes/{route_id}",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching route")  # type: ignore[arg-type]
    if not isinstance(result, dict):
        return f"No route found for id {route_id}."
    return format_route_detail(result)


@mcp.tool()
async def update_athlete_route(
    route_id: str,
    updates: dict[str, Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Update an athlete's route record.

    Body fields supported by ``AthleteRoute`` schema (verified):
    ``name``, ``description``, ``commute``, ``rename_activities``, ``tags``
    (list of strings), ``replaced_by_route_id``, ``latlngs`` (list of
    ``[lat, lng]`` pairs).

    Args:
        route_id: The route ID to update.
        updates: Partial AthleteRoute body — only fields you want to change.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not route_id:
        return "Error: route_id is required."
    if not isinstance(updates, dict) or not updates:
        return "Error: 'updates' must be a non-empty dict of route fields."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/routes/{route_id}",
        api_key=api_key,
        method="PUT",
        data=updates,
    )
    if _is_error(result):
        return _error_message(result, "updating route")  # type: ignore[arg-type]
    if not isinstance(result, dict):
        return f"Route {route_id} updated."
    return format_route_update_result(result)


@mcp.tool()
async def check_route_merge(
    route_id: str,
    other_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Check whether two routes look similar enough to merge.

    Args:
        route_id: First route ID.
        other_id: Second route ID to compare against.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not route_id or not other_id:
        return "Error: both route_id and other_id are required."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/routes/{route_id}/similarity/{other_id}",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "checking route similarity")  # type: ignore[arg-type]
    return format_route_similarity(result)  # type: ignore[arg-type]


# ===========================================================================
# Gear
# ===========================================================================


@mcp.tool()
async def list_gear(
    athlete_id: str | None = None,
    api_key: str | None = None,
    format: str = "json",  # noqa: A002 - mirrors API param naming
) -> str:
    """List gear (bikes, shoes, components, etc.) for an athlete.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
        format: ``"json"`` (default) for a parsed table, or ``"csv"`` for the
            raw CSV body in a code block.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    fmt_err = _validate_format(format)
    if fmt_err:
        return fmt_err

    if format == "csv":
        text = await _fetch_csv(f"/athlete/{athlete_id_to_use}/gear.csv", api_key)
        if text.startswith("Error"):
            return text
        return format_csv_block(text, f"Gear CSV — athlete {athlete_id_to_use}")

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/gear",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching gear")  # type: ignore[arg-type]
    if not isinstance(result, list):
        return "Unexpected response: gear list was not a JSON array."
    if not result:
        return f"No gear found for athlete {athlete_id_to_use}."
    return format_gear_list(result)


@mcp.tool()
async def create_gear(
    gear: dict[str, Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Create a new gear item.

    Body fields (Gear schema, verified):
        ``type`` (required, enum: Bike, Shoes, Wetsuit, RowingMachine, Skis,
            Snowboard, Boat, Board, Equipment, Accessories, Apparel,
            Computer, Light, Battery, Brake, BrakePads, Rotor, Drivetrain,
            BottomBracket, Cassette, Chain, Chainrings, Crankset, Derailleur,
            Pedals, Lever, Cable, Frame, Fork, Handlebar, Headset, Saddle,
            Seatpost, Shock, Stem, Axel, Hub, Trainer, Tube, Tyre, Wheel,
            Wheelset, PowerMeter, Cleats, CyclingShoes, Paddle),
        ``name``, ``purchased`` (date string), ``notes``, ``distance``
        (float meters), ``time`` (float seconds), ``activities`` (int),
        ``use_elapsed_time`` (bool), ``retired`` (date string),
        ``component_ids`` (list of gear ids), ``component`` (bool — is this a
        component of another gear).

    Args:
        gear: Gear body.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not isinstance(gear, dict) or not gear:
        return "Error: 'gear' must be a non-empty dict."
    if not gear.get("type"):
        return "Error: gear 'type' is required (e.g. 'Bike', 'Shoes')."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/gear",
        api_key=api_key,
        method="POST",
        data=gear,
    )
    if _is_error(result):
        return _error_message(result, "creating gear")  # type: ignore[arg-type]
    if isinstance(result, dict):
        return f"Successfully created gear id: {result.get('id', '—')} ({result.get('name', '')})"
    return "Gear created."


@mcp.tool()
async def update_gear(
    gear_id: str,
    gear: dict[str, Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Update an existing gear item.

    Body fields are the same as ``create_gear`` (Gear schema). Pass only the
    fields you want to change.

    Args:
        gear_id: The gear ID to update.
        gear: Partial Gear body.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not gear_id:
        return "Error: gear_id is required."
    if not isinstance(gear, dict) or not gear:
        return "Error: 'gear' must be a non-empty dict of fields to update."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/gear/{gear_id}",
        api_key=api_key,
        method="PUT",
        data=gear,
    )
    if _is_error(result):
        return _error_message(result, "updating gear")  # type: ignore[arg-type]
    if isinstance(result, dict):
        return f"Successfully updated gear id: {result.get('id', gear_id)}"
    return "Gear updated."


@mcp.tool()
async def delete_gear(
    gear_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Delete a gear item.

    Args:
        gear_id: The gear ID to delete.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not gear_id:
        return "Error: gear_id is required."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/gear/{gear_id}",
        api_key=api_key,
        method="DELETE",
    )
    if _is_error(result):
        return _error_message(result, "deleting gear")  # type: ignore[arg-type]
    return f"Gear {gear_id} deleted."


@mcp.tool()
async def recalc_gear_distance(
    gear_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Recalculate aggregated distance/time/activity counts for a gear item.

    GET endpoint — Intervals.icu sums activity totals server-side and returns
    the refreshed gear record.

    Args:
        gear_id: The gear ID to recalc.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not gear_id:
        return "Error: gear_id is required."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/gear/{gear_id}/calc",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "recalculating gear distance")  # type: ignore[arg-type]
    return format_gear_recalc_result(result)


@mcp.tool()
async def replace_gear(
    gear_id: str,
    replacement: dict[str, Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Replace a gear item with a new one.

    Body schema is ``Gear`` (verified) — pass the new component as a Gear
    body. Behavior on the API side typically marks the old gear as retired
    and points the replacement at it.

    Args:
        gear_id: The gear ID being replaced.
        replacement: New Gear body (see ``create_gear`` for fields).
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not gear_id:
        return "Error: gear_id is required."
    if not isinstance(replacement, dict) or not replacement:
        return "Error: 'replacement' must be a non-empty Gear dict."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/gear/{gear_id}/replace",
        api_key=api_key,
        method="POST",
        data=replacement,
    )
    if _is_error(result):
        return _error_message(result, "replacing gear")  # type: ignore[arg-type]
    if isinstance(result, dict):
        return f"Gear {gear_id} replaced — new id {result.get('id', '—')}"
    return f"Gear {gear_id} replacement request accepted."


@mcp.tool()
async def create_gear_reminder(
    gear_id: str,
    reminder: dict[str, Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Create a maintenance reminder on a gear item.

    Body fields (GearReminder schema, verified):
        ``name`` (e.g. "Replace chain"), ``distance`` (float meters threshold),
        ``time`` (float seconds threshold), ``days`` (int days threshold),
        ``activities`` (int activity-count threshold),
        ``starting_distance``, ``starting_time``, ``starting_activities``
        (baseline at reminder creation), ``last_reset`` (ISO datetime),
        ``snoozed_until`` (ISO datetime).

    Args:
        gear_id: The gear ID to attach the reminder to.
        reminder: GearReminder body.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not gear_id:
        return "Error: gear_id is required."
    if not isinstance(reminder, dict) or not reminder:
        return "Error: 'reminder' must be a non-empty dict."
    if not reminder.get("name"):
        return "Error: reminder 'name' is required."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/gear/{gear_id}/reminder",
        api_key=api_key,
        method="POST",
        data=reminder,
    )
    if _is_error(result):
        return _error_message(result, "creating gear reminder")  # type: ignore[arg-type]
    if isinstance(result, dict):
        return format_gear_reminder_result(result)
    return "Reminder created."


@mcp.tool()
async def update_gear_reminder(
    gear_id: str,
    reminder_id: str,
    reminder: dict[str, Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
    reset: bool = False,
    snooze_days: int = 0,
) -> str:
    """Update a gear reminder.

    The Intervals.icu API requires two query params on this endpoint
    (verified): ``reset`` (bool) — if true, resets the reminder's tracking
    baseline to "now"; ``snoozeDays`` (int) — number of days to snooze the
    reminder.

    Body schema is ``GearReminder`` — pass the fields you want to change.

    Args:
        gear_id: The gear ID.
        reminder_id: The reminder ID to update.
        reminder: Partial GearReminder body.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
        reset: If True, reset the reminder's baseline counters.
        snooze_days: Number of days to snooze (0 = no snooze).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not gear_id or not reminder_id:
        return "Error: both gear_id and reminder_id are required."
    if not isinstance(reminder, dict):
        return "Error: 'reminder' must be a dict (use {} to only apply reset/snooze)."

    params = {
        "reset": "true" if reset else "false",
        "snoozeDays": int(snooze_days),
    }

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/gear/{gear_id}/reminder/{reminder_id}",
        api_key=api_key,
        method="PUT",
        params=params,
        data=reminder,
    )
    if _is_error(result):
        return _error_message(result, "updating gear reminder")  # type: ignore[arg-type]
    if isinstance(result, dict):
        return format_gear_reminder_result(result)
    return f"Reminder {reminder_id} updated."


@mcp.tool()
async def delete_gear_reminder(
    gear_id: str,
    reminder_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Delete a gear reminder.

    Args:
        gear_id: The gear ID.
        reminder_id: The reminder ID to delete.
        athlete_id: The Intervals.icu athlete ID (optional, defaults to ATHLETE_ID env var)
        api_key: The Intervals.icu API key (optional, defaults to API_KEY env var)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not gear_id or not reminder_id:
        return "Error: both gear_id and reminder_id are required."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/gear/{gear_id}/reminder/{reminder_id}",
        api_key=api_key,
        method="DELETE",
    )
    if _is_error(result):
        return _error_message(result, "deleting gear reminder")  # type: ignore[arg-type]
    return f"Reminder {reminder_id} deleted from gear {gear_id}."
