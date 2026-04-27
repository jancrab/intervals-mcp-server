"""
Per-activity analytics MCP tools for Intervals.icu.

All tools in this module are read-only GETs against
``/activity/{activity_id}/...`` endpoints. The activity ID is in the URL
path itself (no athlete ID is needed by the API), but we still accept
``athlete_id`` and ``api_key`` arguments for parameter consistency with
other tools in the server.

The ``{ext}`` endpoints (hr-curve, pace-curve, power-curve, power-curves,
power-vs-hr) accept a ``format="json"|"csv"`` argument. When ``"csv"`` is
passed we append ``.csv`` to the path and return the raw CSV body wrapped
in a markdown code block. CSV mode bypasses ``make_intervals_request``
because that helper assumes JSON.

Patterns mirror ``tools/sport_settings.py`` and ``tools/library.py``.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx  # pylint: disable=import-error

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatters_activity_analytics import (
    format_activity_map,
    format_best_efforts,
    format_csv_block,
    format_gap_histogram,
    format_hr_curve,
    format_hr_histogram,
    format_hr_load_model,
    format_interval_stats,
    format_pace_curve,
    format_pace_histogram,
    format_power_curve,
    format_power_curves_multi,
    format_power_histogram,
    format_power_spike_model,
    format_power_vs_hr,
    format_segments,
    format_time_at_hr,
    format_weather_summary,
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


def _validate_format(fmt: str) -> str | None:
    """Return None if the format is acceptable, else an error string."""
    if fmt not in ("json", "csv"):
        return f"Error: format must be 'json' or 'csv' (got {fmt!r})."
    return None


def _resolve_common(
    activity_id: str,
    athlete_id: str | None,
) -> tuple[str, str | None]:
    """Validate activity_id and resolve athlete_id (athlete_id is unused but
    validated for consistency with other tools).

    Returns ``(athlete_id_or_empty, error_or_none)``.
    """
    if not activity_id:
        return "", "Error: activity_id is required."
    # We don't actually need the athlete_id for these endpoints, but we
    # surface a friendly error if the caller passed neither and there is no
    # default — that mirrors the rest of the server's UX.
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return "", error_msg
    return athlete_id_to_use, None


async def _fetch_csv(url_path: str, api_key: str | None) -> str:
    """Fetch a non-JSON (CSV) endpoint and return its body as text.

    ``make_intervals_request`` cannot be used here because it parses the
    response as JSON. We mirror its auth/header setup directly.
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


# ===========================================================================
# Curve endpoints (json|csv)
# ===========================================================================


@mcp.tool()
async def get_activity_hr_curve(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    format: str = "json",  # noqa: A002 - mirrors API param naming
) -> str:
    """Get the heart-rate curve (best HR over each duration) for an activity.

    Args:
        activity_id: The Intervals.icu activity ID (with or without ``i`` prefix).
        athlete_id: Ignored; kept for parameter consistency with other tools.
        api_key: Override INTERVALS_API_KEY env var if provided.
        format: ``"json"`` (default) for a parsed table, or ``"csv"`` for the
            raw CSV body in a code block.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    fmt_err = _validate_format(format)
    if fmt_err:
        return fmt_err

    if format == "csv":
        text = await _fetch_csv(f"/activity/{activity_id}/hr-curve.csv", api_key)
        if text.startswith("Error"):
            return text
        return format_csv_block(text, f"HR curve CSV — {activity_id}")

    result = await make_intervals_request(
        url=f"/activity/{activity_id}/hr-curve",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching HR curve")  # type: ignore[arg-type]
    return format_hr_curve(result)


@mcp.tool()
async def get_activity_power_curve(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    format: str = "json",  # noqa: A002
) -> str:
    """Get the power curve (best W over each duration) for an activity.

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
        format: ``"json"`` or ``"csv"``.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    fmt_err = _validate_format(format)
    if fmt_err:
        return fmt_err

    if format == "csv":
        text = await _fetch_csv(f"/activity/{activity_id}/power-curve.csv", api_key)
        if text.startswith("Error"):
            return text
        return format_csv_block(text, f"Power curve CSV — {activity_id}")

    result = await make_intervals_request(
        url=f"/activity/{activity_id}/power-curve",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching power curve")  # type: ignore[arg-type]
    return format_power_curve(result)


@mcp.tool()
async def get_activity_pace_curve(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    format: str = "json",  # noqa: A002
) -> str:
    """Get the pace curve (best m/s over each duration) for an activity.

    Pace curves are only generated for run/swim/walk-style activities; for
    cycling activities the API returns 404.

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
        format: ``"json"`` or ``"csv"``.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    fmt_err = _validate_format(format)
    if fmt_err:
        return fmt_err

    if format == "csv":
        text = await _fetch_csv(f"/activity/{activity_id}/pace-curve.csv", api_key)
        if text.startswith("Error"):
            return text
        return format_csv_block(text, f"Pace curve CSV — {activity_id}")

    result = await make_intervals_request(
        url=f"/activity/{activity_id}/pace-curve",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching pace curve")  # type: ignore[arg-type]
    return format_pace_curve(result)


@mcp.tool()
async def get_activity_power_curves_multistream(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    format: str = "json",  # noqa: A002
) -> str:
    """Get multiple power curves for an activity (one per filter/stream).

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
        format: ``"json"`` or ``"csv"``.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    fmt_err = _validate_format(format)
    if fmt_err:
        return fmt_err

    if format == "csv":
        text = await _fetch_csv(f"/activity/{activity_id}/power-curves.csv", api_key)
        if text.startswith("Error"):
            return text
        return format_csv_block(text, f"Power curves CSV — {activity_id}")

    result = await make_intervals_request(
        url=f"/activity/{activity_id}/power-curves",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching multistream power curves")  # type: ignore[arg-type]
    return format_power_curves_multi(result)


@mcp.tool()
async def get_activity_power_vs_hr(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    format: str = "json",  # noqa: A002
) -> str:
    """Get power-vs-HR analysis (decoupling, power/HR ratio per bucket) for an activity.

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
        format: ``"json"`` or ``"csv"``.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    fmt_err = _validate_format(format)
    if fmt_err:
        return fmt_err

    if format == "csv":
        text = await _fetch_csv(f"/activity/{activity_id}/power-vs-hr.csv", api_key)
        if text.startswith("Error"):
            return text
        return format_csv_block(text, f"Power vs HR CSV — {activity_id}")

    result = await make_intervals_request(
        url=f"/activity/{activity_id}/power-vs-hr",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching power-vs-hr")  # type: ignore[arg-type]
    return format_power_vs_hr(result)


# ===========================================================================
# Histogram endpoints (json only)
# ===========================================================================


@mcp.tool()
async def get_activity_hr_histogram(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the HR histogram (time spent in each bpm bin) for an activity.

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/hr-histogram",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching HR histogram")  # type: ignore[arg-type]
    return format_hr_histogram(result)


@mcp.tool()
async def get_activity_power_histogram(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the power histogram (time spent in each watt bin) for an activity.

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/power-histogram",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching power histogram")  # type: ignore[arg-type]
    return format_power_histogram(result)


@mcp.tool()
async def get_activity_pace_histogram(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the pace histogram (time spent in each m/s bin) for an activity.

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/pace-histogram",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching pace histogram")  # type: ignore[arg-type]
    return format_pace_histogram(result)


@mcp.tool()
async def get_activity_gap_histogram(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the grade-adjusted-pace histogram for an activity.

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/gap-histogram",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching GAP histogram")  # type: ignore[arg-type]
    return format_gap_histogram(result)


@mcp.tool()
async def get_activity_time_at_hr(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get time-at-HR distribution (per-bpm seconds) for an activity.

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/time-at-hr",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching time-at-HR")  # type: ignore[arg-type]
    return format_time_at_hr(result)


# ===========================================================================
# Model endpoints
# ===========================================================================


@mcp.tool()
async def get_activity_hr_load_model(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the HR-load model fit for an activity (HRSS, LT/max-HR estimates).

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/hr-load-model",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching HR load model")  # type: ignore[arg-type]
    return format_hr_load_model(result)


@mcp.tool()
async def get_activity_power_spike_model(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the power spike / critical-power model fit for an activity.

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/power-spike-model",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching power spike model")  # type: ignore[arg-type]
    return format_power_spike_model(result)


# ===========================================================================
# Interval stats / segments / best-efforts
# ===========================================================================


@mcp.tool()
async def get_activity_interval_stats(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_index: int | None = None,
    end_index: int | None = None,
) -> str:
    """Get interval-stats summary for an activity.

    The Intervals.icu API requires ``start_index`` and ``end_index`` query
    parameters; if they are omitted the API returns 422. Pass them when you
    want stats for a specific stream slice.

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
        start_index: Required by the API — start sample index of the slice.
        end_index: Required by the API — end sample index of the slice.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    params: dict[str, Any] = {}
    if start_index is not None:
        params["start_index"] = start_index
    if end_index is not None:
        params["end_index"] = end_index

    result = await make_intervals_request(
        url=f"/activity/{activity_id}/interval-stats",
        api_key=api_key,
        params=params or None,
    )
    if _is_error(result):
        return _error_message(result, "fetching interval stats")  # type: ignore[arg-type]
    return format_interval_stats(result)


@mcp.tool()
async def get_activity_segments(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get segment efforts (Strava-style segments matched on this activity).

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/segments",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching segments")  # type: ignore[arg-type]
    return format_segments(result)


@mcp.tool()
async def find_best_efforts(
    activity_id: str,
    stream: str = "watts",
    duration: int | None = None,
    distance: float | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Find best efforts within an activity for a stream + duration/distance.

    Live API requires **all of**: ``stream`` (always) AND one of ``duration`` or
    ``distance``. Defaults assume cycling power: ``stream="watts"``, supply
    ``duration`` for a time-based effort.

    Examples:
        find_best_efforts(activity_id="i123", duration=300)               # best 5-min watts
        find_best_efforts(activity_id="i123", stream="heartrate", duration=60)
        find_best_efforts(activity_id="i123", stream="pace", distance=1000)

    Args:
        activity_id: The Intervals.icu activity ID.
        stream: Stream to search; common values ``watts``, ``heartrate``, ``pace``.
        duration: Effort duration in seconds (one of duration/distance required).
        distance: Effort distance in meters (one of duration/distance required).
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    if not stream:
        return "Error: `stream` is required (e.g. 'watts', 'heartrate', 'pace')."
    if duration is None and distance is None:
        return (
            "Error: one of `duration` (seconds) or `distance` (meters) is required."
        )

    params: dict[str, str | int | float] = {"stream": stream}
    if duration is not None:
        params["duration"] = duration
    if distance is not None:
        params["distance"] = distance

    result = await make_intervals_request(
        url=f"/activity/{activity_id}/best-efforts",
        api_key=api_key,
        params=params,
    )
    if _is_error(result):
        return _error_message(result, "fetching best efforts")  # type: ignore[arg-type]
    return format_best_efforts(result, stream=stream)


# ===========================================================================
# Map / weather
# ===========================================================================


@mcp.tool()
async def get_activity_map(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the map (bounds + lat/lng polyline) for an activity.

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/map",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching map")  # type: ignore[arg-type]
    return format_activity_map(result)


@mcp.tool()
async def get_activity_weather_summary(
    activity_id: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get weather summary (temperature, wind, humidity) for an activity.

    Indoor activities will return mostly null fields; the formatter
    surfaces that explicitly.

    Args:
        activity_id: The Intervals.icu activity ID.
        athlete_id: Ignored; kept for parameter consistency.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    _, error = _resolve_common(activity_id, athlete_id)
    if error:
        return error
    result = await make_intervals_request(
        url=f"/activity/{activity_id}/weather-summary",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching weather summary")  # type: ignore[arg-type]
    return format_weather_summary(result)
