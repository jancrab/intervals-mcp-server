"""
Activity-write MCP tools for Intervals.icu.

This module exposes the seven write/mutation endpoints scoped to a single
activity or its intervals:

- `update_activity`           — PUT /activity/{id}             (partial update)
- `delete_activity`           — DELETE /activity/{id}
- `update_activity_streams`   — PUT /activity/{id}/streams
- `update_intervals`          — PUT /activity/{id}/intervals
- `update_interval`           — PUT /activity/{id}/intervals/{intervalId}
- `delete_intervals`          — PUT /activity/{id}/delete-intervals
- `split_interval`            — PUT /activity/{id}/split-interval?splitAt=secs

Conventions (mirrors `tools/wellness_writes.py`):
- Each tool resolves athlete_id for parameter consistency, even though the
  underlying URL is `/activity/{id}/...` and not athlete-scoped.
- For numeric fields on `update_activity`, the cookbook sentinel `-1`
  clears the value on intervals.icu's side (e.g. `feel=-1` removes feel).
- Bodies that are top-level JSON arrays go through `_put_json_body`, which
  wraps a thin direct-httpx call (`make_intervals_request` only accepts
  dict bodies).
"""

from __future__ import annotations

import json as _json
import logging
from typing import Any

import httpx  # pylint: disable=import-error

from intervals_mcp_server.api.client import (
    _get_httpx_client,  # pylint: disable=protected-access
    _prepare_request_config,  # pylint: disable=protected-access
    _parse_response,  # pylint: disable=protected-access
    _handle_http_status_error,  # pylint: disable=protected-access
    make_intervals_request,
)
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatters_activity_writes import (
    format_activity_delete_result,
    format_activity_update_result,
    format_intervals_delete_result,
    format_intervals_update_result,
    format_single_interval_result,
    format_split_interval_result,
    format_streams_update_result,
)
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

logger = logging.getLogger("intervals_icu_mcp_server")
config = get_config()


# ---------------------------------------------------------------------------
# Internal helper for top-level-array PUT bodies
# ---------------------------------------------------------------------------


async def _put_json_body(
    url: str,
    api_key: str | None,
    body: Any,
    params: dict[str, Any] | None = None,
) -> Any:
    """PUT a raw JSON body (dict or list) — `make_intervals_request` only
    accepts dict bodies, so for the array-bodied endpoints we issue a thin
    direct-httpx request, reusing the shared client and config helpers.
    """
    full_url, auth, headers, cfg_err = _prepare_request_config(url, api_key, "PUT")
    if cfg_err:
        return {"error": True, "message": cfg_err}

    try:
        client = await _get_httpx_client()
        kwargs: dict[str, Any] = {
            "method": "PUT",
            "url": full_url,
            "headers": headers,
            "params": params,
            "auth": auth,
            "timeout": 30.0,
        }
        if body is not None:
            kwargs["content"] = _json.dumps(body)
        else:
            # No JSON body — drop the Content-Type so we don't lie to the
            # server about an empty payload being JSON.
            headers.pop("Content-Type", None)
        response = await client.request(**kwargs)
        return _parse_response(response, full_url)
    except httpx.HTTPStatusError as e:
        return _handle_http_status_error(e)
    except httpx.RequestError as e:
        return {"error": True, "message": f"Request error: {e}"}


# ---------------------------------------------------------------------------
# update_activity — PUT /activity/{id}
# ---------------------------------------------------------------------------


@mcp.tool()
async def update_activity(  # pylint: disable=too-many-arguments,too-many-locals
    activity_id: str,
    name: str | None = None,
    description: str | None = None,
    commute: bool | None = None,
    trainer: bool | None = None,
    race: bool | None = None,
    gear: str | None = None,
    perceived_exertion: float | None = None,
    feel: int | None = None,
    tags: list[str] | None = None,
    other_fields: dict[str, Any] | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Update fields on an existing activity (partial update).

    Calls PUT /activity/{id}. Only the parameters you pass are sent in the
    JSON body — fields left as None are omitted, so the server keeps their
    current values.

    Numeric clear convention: pass `-1` for `feel` or `perceived_exertion`
    to clear the value on intervals.icu (per the cookbook).

    Args:
        activity_id: Intervals.icu activity ID (e.g. "i142786468").
        name: Activity name.
        description: Free-text description.
        commute: True/False — mark as commute.
        trainer: True/False — mark as indoor trainer.
        race: True/False — mark as a race.
        gear: Gear ID string.
        perceived_exertion: RPE 0–10 (decimal allowed). Pass -1 to clear.
        feel: Feel 1–5. Pass -1 to clear.
        tags: List of tag strings.
        other_fields: Escape hatch for any other Activity field not exposed
            as a typed parameter (e.g. `{"icu_rpe": 7}`). Merged into the
            body last.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not activity_id:
        return "Error: No activity ID provided."

    body: dict[str, Any] = {}
    typed = {
        "name": name,
        "description": description,
        "commute": commute,
        "trainer": trainer,
        "race": race,
        "gear": gear,
        "perceived_exertion": perceived_exertion,
        "feel": feel,
        "tags": tags,
    }
    for k, v in typed.items():
        if v is not None:
            body[k] = v

    if other_fields:
        if not isinstance(other_fields, dict):
            return "Error: `other_fields` must be a dict."
        body.update(other_fields)

    if not body:
        return "Error: no fields to update — pass at least one field."

    result = await make_intervals_request(
        url=f"/activity/{activity_id}",
        api_key=api_key,
        method="PUT",
        data=body,
    )
    if isinstance(result, dict) and result.get("error"):
        return f"Error updating activity: {result.get('message')}"

    confirmed = result if isinstance(result, dict) else {**body, "id": activity_id}
    if "id" not in confirmed:
        confirmed = {**confirmed, "id": activity_id}
    # athlete_id_to_use is resolved for parameter consistency; the URL is
    # activity-scoped, not athlete-scoped.
    _ = athlete_id_to_use
    return format_activity_update_result(confirmed)


# ---------------------------------------------------------------------------
# delete_activity — DELETE /activity/{id}
# ---------------------------------------------------------------------------


@mcp.tool()
async def delete_activity(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Delete an activity from intervals.icu.

    Calls DELETE /activity/{id}. Irreversible — the activity and all of its
    streams, intervals, and computed metrics are removed.

    Args:
        activity_id: Intervals.icu activity ID.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not activity_id:
        return "Error: No activity ID provided."
    _ = athlete_id_to_use

    result = await make_intervals_request(
        url=f"/activity/{activity_id}", api_key=api_key, method="DELETE"
    )
    if isinstance(result, dict) and result.get("error"):
        return f"Error deleting activity: {result.get('message')}"
    return format_activity_delete_result(activity_id)


# ---------------------------------------------------------------------------
# update_activity_streams — PUT /activity/{id}/streams
# ---------------------------------------------------------------------------


@mcp.tool()
async def update_activity_streams(
    activity_id: str,
    streams: dict[str, list[float]] | list[dict[str, Any]],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Update streams (samples) for an activity.

    Calls PUT /activity/{id}/streams. The intervals.icu API expects a
    top-level JSON array of `ActivityStream` objects (each `{type, name,
    data, ...}`). For caller convenience this tool also accepts a
    `{stream-name: [samples]}` dict and transforms it into that shape.

    Args:
        activity_id: Intervals.icu activity ID.
        streams: Either a `{name: [values]}` dict, or a list of stream
            dicts in the API's native shape.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not activity_id:
        return "Error: No activity ID provided."
    _ = athlete_id_to_use

    # Normalise to the API's array-of-stream-objects shape
    body_streams: list[dict[str, Any]]
    if isinstance(streams, dict):
        body_streams = [{"type": k, "data": v} for k, v in streams.items()]
    elif isinstance(streams, list):
        body_streams = [s for s in streams if isinstance(s, dict)]
    else:
        return "Error: `streams` must be a dict of {name: [samples]} or a list of stream dicts."

    if not body_streams:
        return "Error: no streams to update."

    result = await _put_json_body(f"/activity/{activity_id}/streams", api_key, body_streams)
    if isinstance(result, dict) and result.get("error"):
        return f"Error updating activity streams: {result.get('message')}"

    return format_streams_update_result(result, sent_streams=body_streams)


# ---------------------------------------------------------------------------
# update_intervals — PUT /activity/{id}/intervals
# ---------------------------------------------------------------------------


@mcp.tool()
async def update_intervals(
    activity_id: str,
    intervals: list[dict[str, Any]],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Replace the interval list for an activity.

    Calls PUT /activity/{id}/intervals with `intervals` as a top-level JSON
    array. Each entry should follow the `Interval` schema — at minimum
    `start_index` and `end_index` (or `elapsed_time` etc. depending on use).

    This call REPLACES the activity's interval list. To add a single
    interval, prefer `update_interval`.

    Args:
        activity_id: Intervals.icu activity ID.
        intervals: List of interval dicts.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not activity_id:
        return "Error: No activity ID provided."
    if not isinstance(intervals, list):
        return "Error: `intervals` must be a list of interval dicts."
    if not all(isinstance(iv, dict) for iv in intervals):
        return "Error: every entry in `intervals` must be a dict."
    _ = athlete_id_to_use

    result = await _put_json_body(f"/activity/{activity_id}/intervals", api_key, intervals)
    if isinstance(result, dict) and result.get("error"):
        return f"Error updating intervals: {result.get('message')}"

    returned = result if isinstance(result, list) else intervals
    return format_intervals_update_result(returned)


# ---------------------------------------------------------------------------
# update_interval — PUT /activity/{id}/intervals/{intervalId}
# ---------------------------------------------------------------------------


@mcp.tool()
async def update_interval(
    activity_id: str,
    interval_id: str,
    interval: dict[str, Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Update or create a single interval on an activity.

    Calls PUT /activity/{id}/intervals/{intervalId} with the interval dict
    as the JSON body.

    Args:
        activity_id: Intervals.icu activity ID.
        interval_id: ID of the interval to update (or new ID to create).
        interval: Interval fields, e.g. `{"label": "Threshold #1",
            "type": "WORK", "start_index": 600, "end_index": 1200}`.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not activity_id or not interval_id:
        return "Error: activity_id and interval_id are required."
    if not isinstance(interval, dict):
        return "Error: `interval` must be a dict."
    _ = athlete_id_to_use

    result = await make_intervals_request(
        url=f"/activity/{activity_id}/intervals/{interval_id}",
        api_key=api_key,
        method="PUT",
        data=interval,
    )
    if isinstance(result, dict) and result.get("error"):
        return f"Error updating interval: {result.get('message')}"

    confirmed = result if isinstance(result, dict) else interval
    return format_single_interval_result(confirmed)


# ---------------------------------------------------------------------------
# delete_intervals — PUT /activity/{id}/delete-intervals
# ---------------------------------------------------------------------------


@mcp.tool()
async def delete_intervals(
    activity_id: str,
    interval_ids: list[Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Delete one or more intervals from an activity.

    Calls PUT /activity/{id}/delete-intervals. Per the OpenAPI spec the body
    is a JSON array of `Interval` objects — but in practice the server
    matches by `id` only, so this tool accepts a simple list of interval
    IDs and wraps each as `{"id": <value>}`. If the caller already has
    full interval dicts, pass those through unchanged (they'll be left
    alone provided each is a dict).

    Args:
        activity_id: Intervals.icu activity ID.
        interval_ids: List of interval IDs to delete (or full interval
            dicts; each must contain an `id` field).
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not activity_id:
        return "Error: No activity ID provided."
    if not isinstance(interval_ids, list) or not interval_ids:
        return "Error: `interval_ids` must be a non-empty list."
    _ = athlete_id_to_use

    body: list[dict[str, Any]] = []
    for entry in interval_ids:
        if isinstance(entry, dict):
            body.append(entry)
        else:
            body.append({"id": entry})

    result = await _put_json_body(f"/activity/{activity_id}/delete-intervals", api_key, body)
    if isinstance(result, dict) and result.get("error"):
        return f"Error deleting intervals: {result.get('message')}"

    return format_intervals_delete_result(result, requested_count=len(body))


# ---------------------------------------------------------------------------
# split_interval — PUT /activity/{id}/split-interval?splitAt=<seconds>
# ---------------------------------------------------------------------------


@mcp.tool()
async def split_interval(
    activity_id: str,
    split_at_secs: int,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Split the interval that contains a given time-offset into two.

    Calls PUT /activity/{id}/split-interval. Per the OpenAPI spec the only
    parameter is `splitAt` (integer seconds, query parameter) — the body
    is empty. The server finds the interval that contains that offset and
    splits it at that point.

    Args:
        activity_id: Intervals.icu activity ID.
        split_at_secs: Time offset in seconds within the activity at which
            to split the surrounding interval.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not activity_id:
        return "Error: No activity ID provided."
    if not isinstance(split_at_secs, int) or split_at_secs < 0:
        return (
            "Error: `split_at_secs` must be a non-negative integer (seconds from activity start)."
        )
    _ = athlete_id_to_use

    # The endpoint accepts the param as a query string; empty body.
    result = await _put_json_body(
        f"/activity/{activity_id}/split-interval",
        api_key,
        body=None,
        params={"splitAt": split_at_secs},
    )
    if isinstance(result, dict) and result.get("error"):
        return f"Error splitting interval: {result.get('message')}"

    return format_split_interval_result(result)
