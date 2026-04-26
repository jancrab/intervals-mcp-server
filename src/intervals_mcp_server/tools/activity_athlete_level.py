"""
Athlete-level activity MCP tools for Intervals.icu.

Covers ranges, search, performance models, and manual activity creation that
operate across an athlete's collection of activities (vs. per-activity tools
in ``tools/activities.py``).

Endpoints (15 reads + 2 writes):

- Multi-fetch / range
  - GET /athlete/{id}/activities/{ids}             — get_activities_by_ids
  - GET /athlete/{id}/activities-around            — list_activities_around
  - GET /athlete/{id}/activities.csv               — get_activities_csv
- Search
  - GET /athlete/{id}/activities/search            — search_for_activities
  - GET /athlete/{id}/activities/search-full       — search_for_activities_full
  - GET /athlete/{id}/activities/interval-search   — search_for_intervals
- Tags
  - GET /athlete/{id}/activity-tags                — list_activity_tags
- Curves (per-activity, athlete-level rollup with optional .csv suffix)
  - GET /athlete/{id}/activity-hr-curves{ext}      — list_activity_hr_curves
  - GET /athlete/{id}/activity-pace-curves{ext}    — list_activity_pace_curves
  - GET /athlete/{id}/activity-power-curves{ext}   — list_activity_power_curves
  - GET /athlete/{id}/hr-curves{ext}               — list_athlete_hr_curves
  - GET /athlete/{id}/pace-curves{ext}             — list_athlete_pace_curves
  - GET /athlete/{id}/power-curves{ext}            — list_athlete_power_curves
- Models
  - GET /athlete/{id}/power-hr-curve               — get_athlete_power_hr_curve
  - GET /athlete/{id}/mmp-model                    — get_athlete_mmp_model
- Writes
  - POST /athlete/{id}/activities/manual           — create_manual_activity
  - POST /athlete/{id}/activities/manual/bulk      — create_multiple_manual_activities
    (upsert on external_id per inventory)

Patterns mirror ``tools/sport_settings.py`` and ``tools/library.py``:
- ``make_intervals_request`` for HTTP (kwarg ``data=`` for JSON bodies).
- ``resolve_athlete_id`` for athlete resolution.
- All tools return a markdown / human-readable string.
- Errors from the API surface as a one-line ``Error ...:`` message.

The ``{ext}`` curve endpoints take a ``format`` parameter (``"json"`` or
``"csv"``) that switches the path suffix. CSV responses are returned as a
fenced code block since they're not JSON-parseable.

The download-FIT endpoint (POST returning a zip) is intentionally deferred
to Wave 5 (file ops).
"""

from __future__ import annotations

from typing import Any

import httpx  # pylint: disable=import-error

from intervals_mcp_server.api.client import (
    _get_httpx_client,  # pylint: disable=protected-access
    _handle_http_status_error,  # pylint: disable=protected-access
    _prepare_request_config,  # pylint: disable=protected-access
    make_intervals_request,
)
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatters_activity_athlete_level import (
    format_activities_csv,
    format_activities_summary,
    format_activity_tags,
    format_bulk_manual_result,
    format_curve_aggregation,
    format_interval_search_results,
    format_manual_activity_result,
    format_mmp_model,
    format_power_hr_curve,
    format_search_results,
)
from intervals_mcp_server.utils.validation import resolve_athlete_id, resolve_date_params

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_error(result: Any) -> bool:
    """True if the API client returned an error dict."""
    return isinstance(result, dict) and result.get("error") is True


def _error_message(result: dict[str, Any], action: str) -> str:
    """Format an API error response as a one-line user message."""
    return f"Error {action}: {result.get('message', 'Unknown error')}"


async def _fetch_raw_text(
    url: str,
    api_key: str | None,
    params: dict[str, Any] | None = None,
) -> tuple[str | None, dict[str, Any] | None]:
    """GET ``url`` and return the raw response text, or an error dict.

    Used for ``.csv`` endpoints that return non-JSON payloads.
    """
    full_url, auth, headers, cfg_err = _prepare_request_config(url, api_key, "GET")
    if cfg_err:
        return None, {"error": True, "message": cfg_err}
    # We want raw text — don't ask for application/json.
    headers["Accept"] = "text/csv, */*"
    try:
        client = await _get_httpx_client()
        response = await client.request(
            method="GET",
            url=full_url,
            headers=headers,
            params=params,
            auth=auth,
            timeout=60.0,
        )
        response.raise_for_status()
        return response.text, None
    except httpx.HTTPStatusError as e:
        return None, _handle_http_status_error(e)
    except httpx.RequestError as e:
        return None, {"error": True, "message": f"Request error: {e}"}


# ===========================================================================
# Multi-fetch / range
# ===========================================================================


@mcp.tool()
async def get_activities_by_ids(
    activity_ids: list[str],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Fetch multiple activities by ID in one call.

    The Intervals.icu endpoint takes a comma-separated list of activity IDs
    in the path. Per the inventory, missing or unknown IDs are silently
    skipped — the response only includes activities that resolved.

    Args:
        activity_ids: List of activity IDs (e.g. ``["i142786468", "i142324120"]``).
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not isinstance(activity_ids, list) or not activity_ids:
        return "Error: 'activity_ids' must be a non-empty list of activity IDs."

    ids_path = ",".join(str(i) for i in activity_ids)
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activities/{ids_path}",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching activities by ids")  # type: ignore[arg-type]
    if not isinstance(result, list):
        return "Unexpected response: activities-by-ids did not return a list."
    if not result:
        return "No activities found for the provided IDs (missing IDs are silently skipped)."
    return format_activities_summary(result)


@mcp.tool()
async def list_activities_around(
    activity_id: str,
    days: int = 3,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """List activities recorded around a target activity (before + after).

    Args:
        activity_id: The reference activity ID (the "center" of the window).
        days: Number of days before and after to include. Default 3.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not activity_id:
        return "Error: activity_id is required."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activities-around",
        api_key=api_key,
        params={"activity_id": activity_id, "days": days},
    )
    if _is_error(result):
        return _error_message(result, "listing activities around id")  # type: ignore[arg-type]
    if not isinstance(result, list):
        return "Unexpected response: activities-around did not return a list."
    return format_activities_summary(result)


@mcp.tool()
async def get_activities_csv(
    start_date: str | None = None,
    end_date: str | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Bulk-download activities as CSV across a date range.

    The response is wrapped in a fenced ``csv`` code block. Defaults to the
    last 30 days when dates are omitted.

    Args:
        start_date: Oldest date (YYYY-MM-DD). Defaults to 30 days ago.
        end_date: Newest date (YYYY-MM-DD). Defaults to today.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    oldest, newest = resolve_date_params(start_date, end_date, default_start_days_ago=30)

    text, err = await _fetch_raw_text(
        url=f"/athlete/{athlete_id_to_use}/activities.csv",
        api_key=api_key,
        params={"oldest": oldest, "newest": newest},
    )
    if err:
        return _error_message(err, "downloading activities CSV")
    return format_activities_csv(text)


# ===========================================================================
# Search
# ===========================================================================


@mcp.tool()
async def search_for_activities(
    query: str,
    limit: int | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Search activities by name or tag (summary results).

    Args:
        query: Search term (matched against activity name / tags).
        limit: Optional maximum number of results.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not query:
        return "Error: 'query' is required."

    params: dict[str, Any] = {"q": query}
    if limit is not None:
        params["limit"] = limit

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activities/search",
        api_key=api_key,
        params=params,
    )
    if _is_error(result):
        return _error_message(result, "searching activities")  # type: ignore[arg-type]
    if not isinstance(result, list):
        return "Unexpected response: activities/search did not return a list."
    return format_search_results(result, summary=True)


@mcp.tool()
async def search_for_activities_full(
    query: str,
    limit: int | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Search activities by name or tag (full activity dicts).

    Same query parameters as ``search_for_activities`` but returns the full
    activity payload (heavier response). Useful when you need fields beyond
    the summary table (zones, weighted power, etc.).

    Args:
        query: Search term.
        limit: Optional maximum number of results.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not query:
        return "Error: 'query' is required."

    params: dict[str, Any] = {"q": query}
    if limit is not None:
        params["limit"] = limit

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activities/search-full",
        api_key=api_key,
        params=params,
    )
    if _is_error(result):
        return _error_message(result, "searching activities (full)")  # type: ignore[arg-type]
    if not isinstance(result, list):
        return "Unexpected response: activities/search-full did not return a list."
    return format_search_results(result, summary=False)


@mcp.tool()
async def search_for_intervals(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    min_secs: int,
    max_secs: int,
    activity_type: str | None = None,
    min_intensity: float | None = None,
    max_intensity: float | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """Find activities containing intervals matching duration + intensity bounds.

    Args:
        min_secs: Minimum interval duration (seconds).
        max_secs: Maximum interval duration (seconds).
        activity_type: Optional activity type filter (``Ride``, ``Run``, ...).
        min_intensity: Optional minimum interval intensity (IF or %FTP-equivalent).
        max_intensity: Optional maximum interval intensity.
        start_date: Optional oldest date (YYYY-MM-DD).
        end_date: Optional newest date (YYYY-MM-DD).
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
        extra_params: Pass-through dict for other interval-search filters
            documented by the OpenAPI spec.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    params: dict[str, Any] = {"minSecs": min_secs, "maxSecs": max_secs}
    if activity_type is not None:
        params["type"] = activity_type
    if min_intensity is not None:
        params["minIntensity"] = min_intensity
    if max_intensity is not None:
        params["maxIntensity"] = max_intensity
    if start_date or end_date:
        oldest, newest = resolve_date_params(start_date, end_date)
        params["oldest"] = oldest
        params["newest"] = newest
    if extra_params:
        if not isinstance(extra_params, dict):
            return "Error: 'extra_params' must be a dict if provided."
        params.update(extra_params)

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activities/interval-search",
        api_key=api_key,
        params=params,
    )
    if _is_error(result):
        return _error_message(result, "searching for intervals")  # type: ignore[arg-type]
    if not isinstance(result, list):
        return "Unexpected response: interval-search did not return a list."
    return format_interval_search_results(result)


# ===========================================================================
# Tags
# ===========================================================================


@mcp.tool()
async def list_activity_tags(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """List all tags applied to the athlete's activities.

    Distinct from event tags (`list_event_tags`) and workout tags
    (`list_workout_tags`).

    Args:
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activity-tags",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "listing activity tags")  # type: ignore[arg-type]
    return format_activity_tags(result)


# ===========================================================================
# Curves
# ===========================================================================


def _curve_ext(format_: str) -> tuple[str, bool]:
    """Map ``format`` parameter to the URL suffix and is_csv flag."""
    fmt = (format_ or "json").strip().lower()
    if fmt == "csv":
        return ".csv", True
    return "", False


async def _fetch_curve(
    base_path: str,
    format_: str,
    api_key: str | None,
    params: dict[str, Any] | None,
    action: str,
) -> str:
    """Shared GET for ``*-curves{ext}`` endpoints."""
    ext, is_csv = _curve_ext(format_)
    url = f"{base_path}{ext}"
    if is_csv:
        text, err = await _fetch_raw_text(url, api_key, params=params)
        if err:
            return _error_message(err, action)
        return format_activities_csv(text)
    result = await make_intervals_request(url=url, api_key=api_key, params=params)
    if _is_error(result):
        return _error_message(result, action)  # type: ignore[arg-type]
    return format_curve_aggregation(result)


def _curve_params(
    activity_type: str,
    start_date: str | None,
    end_date: str | None,
    extra: dict[str, Any] | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"type": activity_type}
    oldest, newest = resolve_date_params(start_date, end_date, default_start_days_ago=365)
    params["oldest"] = oldest
    params["newest"] = newest
    if extra:
        params.update(extra)
    return params


@mcp.tool()
async def list_activity_hr_curves(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    activity_type: str = "Ride",
    start_date: str | None = None,
    end_date: str | None = None,
    format: str = "json",  # noqa: A002 - matches API param name
    athlete_id: str | None = None,
    api_key: str | None = None,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """Best HR per duration over a date range, with per-activity rollup.

    Args:
        activity_type: Activity type (``Ride``, ``Run``, ``Swim``, ...).
        start_date: Oldest date (YYYY-MM-DD). Defaults to 365 days ago.
        end_date: Newest date (YYYY-MM-DD). Defaults to today.
        format: ``"json"`` (default) or ``"csv"`` — switches the URL suffix.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
        extra_params: Pass-through dict for other curve filters.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    return await _fetch_curve(
        base_path=f"/athlete/{athlete_id_to_use}/activity-hr-curves",
        format_=format,
        api_key=api_key,
        params=_curve_params(activity_type, start_date, end_date, extra_params),
        action="fetching activity HR curves",
    )


@mcp.tool()
async def list_activity_pace_curves(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    activity_type: str = "Run",
    start_date: str | None = None,
    end_date: str | None = None,
    format: str = "json",  # noqa: A002
    athlete_id: str | None = None,
    api_key: str | None = None,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """Best pace per distance over a date range, with per-activity rollup.

    Args:
        activity_type: Activity type (typically ``Run`` or ``Swim``).
        start_date: Oldest date (YYYY-MM-DD). Defaults to 365 days ago.
        end_date: Newest date (YYYY-MM-DD). Defaults to today.
        format: ``"json"`` (default) or ``"csv"``.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
        extra_params: Pass-through dict for other curve filters.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    return await _fetch_curve(
        base_path=f"/athlete/{athlete_id_to_use}/activity-pace-curves",
        format_=format,
        api_key=api_key,
        params=_curve_params(activity_type, start_date, end_date, extra_params),
        action="fetching activity pace curves",
    )


@mcp.tool()
async def list_activity_power_curves(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    activity_type: str = "Ride",
    start_date: str | None = None,
    end_date: str | None = None,
    format: str = "json",  # noqa: A002
    athlete_id: str | None = None,
    api_key: str | None = None,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """Best power per duration over a date range, with per-activity rollup.

    Args:
        activity_type: Activity type (typically ``Ride`` or ``VirtualRide``).
        start_date: Oldest date (YYYY-MM-DD). Defaults to 365 days ago.
        end_date: Newest date (YYYY-MM-DD). Defaults to today.
        format: ``"json"`` (default) or ``"csv"``.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
        extra_params: Pass-through dict for other curve filters.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    return await _fetch_curve(
        base_path=f"/athlete/{athlete_id_to_use}/activity-power-curves",
        format_=format,
        api_key=api_key,
        params=_curve_params(activity_type, start_date, end_date, extra_params),
        action="fetching activity power curves",
    )


@mcp.tool()
async def list_athlete_hr_curves(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    activity_type: str = "Ride",
    start_date: str | None = None,
    end_date: str | None = None,
    format: str = "json",  # noqa: A002
    athlete_id: str | None = None,
    api_key: str | None = None,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """Athlete-level HR-curve aggregation across multiple time windows.

    Returns one curve per pre-aggregated period (e.g. 1 year, 90 days, 42 days)
    showing best HR per duration.

    Args:
        activity_type: Activity type filter.
        start_date: Oldest date (YYYY-MM-DD). Defaults to 365 days ago.
        end_date: Newest date (YYYY-MM-DD). Defaults to today.
        format: ``"json"`` (default) or ``"csv"``.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
        extra_params: Pass-through dict for other curve filters.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    return await _fetch_curve(
        base_path=f"/athlete/{athlete_id_to_use}/hr-curves",
        format_=format,
        api_key=api_key,
        params=_curve_params(activity_type, start_date, end_date, extra_params),
        action="fetching athlete HR curves",
    )


@mcp.tool()
async def list_athlete_pace_curves(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    activity_type: str = "Run",
    start_date: str | None = None,
    end_date: str | None = None,
    format: str = "json",  # noqa: A002
    athlete_id: str | None = None,
    api_key: str | None = None,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """Athlete-level pace-curve aggregation (best pace per distance).

    Args:
        activity_type: Activity type (typically ``Run`` or ``Swim``).
        start_date: Oldest date (YYYY-MM-DD). Defaults to 365 days ago.
        end_date: Newest date (YYYY-MM-DD). Defaults to today.
        format: ``"json"`` (default) or ``"csv"``.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
        extra_params: Pass-through dict for other curve filters.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    return await _fetch_curve(
        base_path=f"/athlete/{athlete_id_to_use}/pace-curves",
        format_=format,
        api_key=api_key,
        params=_curve_params(activity_type, start_date, end_date, extra_params),
        action="fetching athlete pace curves",
    )


@mcp.tool()
async def list_athlete_power_curves(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    activity_type: str = "Ride",
    start_date: str | None = None,
    end_date: str | None = None,
    format: str = "json",  # noqa: A002
    athlete_id: str | None = None,
    api_key: str | None = None,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """Athlete-level power-curve aggregation (best power per duration).

    Args:
        activity_type: Activity type (typically ``Ride`` or ``VirtualRide``).
        start_date: Oldest date (YYYY-MM-DD). Defaults to 365 days ago.
        end_date: Newest date (YYYY-MM-DD). Defaults to today.
        format: ``"json"`` (default) or ``"csv"``.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
        extra_params: Pass-through dict for other curve filters.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    return await _fetch_curve(
        base_path=f"/athlete/{athlete_id_to_use}/power-curves",
        format_=format,
        api_key=api_key,
        params=_curve_params(activity_type, start_date, end_date, extra_params),
        action="fetching athlete power curves",
    )


# ===========================================================================
# Models
# ===========================================================================


@mcp.tool()
async def get_athlete_power_hr_curve(
    activity_type: str = "Ride",
    start_date: str | None = None,
    end_date: str | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """Aggregated power-vs-HR scatter for the athlete (decoupling baseline).

    The intervals.icu endpoint returns per-watts-bucket arrays of average HR,
    cadence, and minutes spent — useful for spotting aerobic decoupling
    progression.

    Args:
        activity_type: Activity type (typically ``Ride``).
        start_date: Required ``start`` (YYYY-MM-DD). Defaults to 365 days ago.
        end_date: Required ``end`` (YYYY-MM-DD). Defaults to today.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
        extra_params: Pass-through dict for other filters.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    start, end = resolve_date_params(start_date, end_date, default_start_days_ago=365)
    params: dict[str, Any] = {"type": activity_type, "start": start, "end": end}
    if extra_params:
        if not isinstance(extra_params, dict):
            return "Error: 'extra_params' must be a dict if provided."
        params.update(extra_params)

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/power-hr-curve",
        api_key=api_key,
        params=params,
    )
    if _is_error(result):
        return _error_message(result, "fetching power-hr curve")  # type: ignore[arg-type]
    return format_power_hr_curve(result)


@mcp.tool()
async def get_athlete_mmp_model(
    activity_type: str = "Ride",
    athlete_id: str | None = None,
    api_key: str | None = None,
    extra_params: dict[str, Any] | None = None,
) -> str:
    """Get the athlete's power model (used to resolve %MMP step targets).

    Returns CP, W', pMax, and the e-FTP derived from the model. The ``type``
    query param is required by the API.

    Args:
        activity_type: Activity type (the model is per-discipline; default ``Ride``).
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
        extra_params: Pass-through dict for other filters (e.g. ``days``).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    params: dict[str, Any] = {"type": activity_type}
    if extra_params:
        if not isinstance(extra_params, dict):
            return "Error: 'extra_params' must be a dict if provided."
        params.update(extra_params)

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/mmp-model",
        api_key=api_key,
        params=params,
    )
    if _is_error(result):
        return _error_message(result, "fetching MMP model")  # type: ignore[arg-type]
    return format_mmp_model(result)


# ===========================================================================
# Writes — manual activity creation
# ===========================================================================


_MANUAL_ACTIVITY_REQUIRED = ("start_date_local", "type", "name", "moving_time")


def _validate_manual_body(body: dict[str, Any]) -> str | None:
    """Return an error string if a manual-activity body is missing required fields."""
    missing = [k for k in _MANUAL_ACTIVITY_REQUIRED if not body.get(k)]
    if missing:
        return (
            "Error: manual activity is missing required field(s): "
            + ", ".join(missing)
            + ". Required: start_date_local, type, name, moving_time."
        )
    return None


@mcp.tool()
async def create_manual_activity(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    start_date_local: str,
    activity_type: str,
    name: str,
    moving_time: int,
    athlete_id: str | None = None,
    api_key: str | None = None,
    description: str | None = None,
    distance: float | None = None,
    total_elevation_gain: float | None = None,
    icu_training_load: float | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Create a single manual activity.

    Body shape derives from the OpenAPI ``createManualActivity`` schema. The
    Intervals.icu API requires ``start_date_local``, ``type``, ``name`` and
    ``moving_time``; everything else is optional.

    Common optional fields exposed directly: ``description``, ``distance``
    (meters), ``total_elevation_gain`` (meters), ``icu_training_load`` (TSS).
    Pass anything else through ``extra`` (e.g. ``average_heartrate``,
    ``icu_average_watts``, ``trainer``, ``race``, ``tags``).

    Args:
        start_date_local: Local start datetime (ISO 8601, e.g.
            ``2026-04-25T07:00:00``).
        activity_type: Activity type (``Ride``, ``Run``, ``Swim``, ``Workout``...).
        name: Activity name.
        moving_time: Moving time in seconds (required).
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
        description: Optional free-text description.
        distance: Optional distance in meters.
        total_elevation_gain: Optional elevation gain in meters.
        icu_training_load: Optional TSS override.
        extra: Pass-through dict for other manual-activity fields.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    body: dict[str, Any] = {
        "start_date_local": start_date_local,
        "type": activity_type,
        "name": name,
        "moving_time": moving_time,
    }
    if description is not None:
        body["description"] = description
    if distance is not None:
        body["distance"] = distance
    if total_elevation_gain is not None:
        body["total_elevation_gain"] = total_elevation_gain
    if icu_training_load is not None:
        body["icu_training_load"] = icu_training_load
    if extra:
        if not isinstance(extra, dict):
            return "Error: 'extra' must be a dict if provided."
        body.update(extra)

    err = _validate_manual_body(body)
    if err:
        return err

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activities/manual",
        api_key=api_key,
        method="POST",
        data=body,
    )
    if _is_error(result):
        return _error_message(result, "creating manual activity")  # type: ignore[arg-type]
    return format_manual_activity_result(result)


@mcp.tool()
async def create_multiple_manual_activities(
    activities: list[dict[str, Any]],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Create multiple manual activities in one call (upsert on ``external_id``).

    Body is a JSON array of manual-activity dicts. Each item must include the
    same required fields as ``create_manual_activity``: ``start_date_local``,
    ``type``, ``name``, ``moving_time``. Per the inventory, items are upserted
    keyed on the optional ``external_id`` field — passing the same
    ``external_id`` again will update the previously-created activity rather
    than duplicate it. Items without ``external_id`` are inserted fresh.

    Args:
        activities: Non-empty list of manual-activity dicts.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not isinstance(activities, list) or not activities:
        return "Error: 'activities' must be a non-empty list of manual-activity dicts."
    for i, item in enumerate(activities):
        if not isinstance(item, dict):
            return f"Error: every entry in 'activities' must be a dict (index {i})."
        err = _validate_manual_body(item)
        if err:
            return f"Error in activities[{i}]: {err[len('Error: ') :]}"

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activities/manual/bulk",
        api_key=api_key,
        method="POST",
        data=activities,  # type: ignore[arg-type]
    )
    if _is_error(result):
        return _error_message(result, "creating multiple manual activities")  # type: ignore[arg-type]
    return format_bulk_manual_result(result)
