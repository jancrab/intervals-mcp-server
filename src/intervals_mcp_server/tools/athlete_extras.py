"""
Athlete-extras MCP tools for Intervals.icu.

This module exposes endpoints that round out the athlete surface area:

- Athlete writes: ``update_athlete``, ``update_athlete_plans``,
  ``update_athlete_training_plan``.
- Athlete reads: ``get_athlete_summary`` (json|csv), ``get_athlete_basic_profile``,
  ``get_athlete_settings_for_device``, ``get_athlete_training_plan``.
- Weather: ``get_weather_config``, ``update_weather_config``,
  ``get_weather_forecast``.
- Shared events: ``get_shared_event``.
- OAuth: ``disconnect_app``.

Patterns mirror ``tools/sport_settings.py`` and ``tools/activity_analytics.py``.
The CSV-mode helper for ``get_athlete_summary`` is duplicated locally
(``_fetch_csv``) so this module has zero coupling with concurrently-edited
files.

Body-schema notes:

- ``update_athlete``: the upstream Athlete schema has dozens of fields; we
  expose a focused set (``name``, ``email``, ``weight``, ``height``, ``bio``,
  ``city``, ``country``, ``state``, ``timezone``, ``sex``) plus an
  ``other_fields`` escape hatch. Tighten via ``extra="forbid"`` in v2.
- ``update_athlete_plans``: the underlying API is multi-athlete (``[{athlete_id,
  plan_id, ...}, ...]``). For single-user usage we expose simplified params
  (``new_folder_id``, ``start_date_local``) that we wrap into a single-element
  list keyed on the resolved athlete id. Pass ``raw_body`` to override.
- ``update_athlete_training_plan``: body is a TrainingPlan object — at minimum
  we send ``training_plan_start_date`` and any fields the caller provides;
  the schema is inferred from the GET response (``training_plan_id``,
  ``training_plan_start_date``, ``training_plan_alias``, ``timezone``,
  ``training_plan`` nested).
- ``update_weather_config``: body is ``{"forecasts": [...]}`` — the GET
  response shape is reused for PUT.
- ``disconnect_app``: no body. The auth header identifies the OAuth app for
  session-token auth; for personal-API-key auth this endpoint is essentially
  a no-op.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx  # pylint: disable=import-error

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatters_athlete_extras import (
    format_athlete_basic_profile,
    format_athlete_settings,
    format_athlete_summary,
    format_athlete_update_result,
    format_csv_block,
    format_disconnect_app_result,
    format_shared_event,
    format_training_plan,
    format_training_plan_update_result,
    format_weather_config,
    format_weather_config_update_result,
    format_weather_forecast,
)
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

logger = logging.getLogger("intervals_icu_mcp_server")
config = get_config()

_VALID_DEVICE_CLASSES = ("phone", "tablet", "desktop")
_ATHLETE_FOCUSED_FIELDS = (
    "name",
    "firstname",
    "lastname",
    "email",
    "sex",
    "city",
    "state",
    "country",
    "timezone",
    "weight",
    "height",
    "bio",
    "website",
)


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _is_error(result: Any) -> bool:
    return isinstance(result, dict) and result.get("error") is True


def _error_message(result: dict[str, Any], action: str) -> str:
    return f"Error {action}: {result.get('message', 'Unknown error')}"


def _validate_format(fmt: str) -> str | None:
    if fmt not in ("json", "csv"):
        return f"Error: format must be 'json' or 'csv' (got {fmt!r})."
    return None


async def _fetch_csv(url_path: str, api_key: str | None) -> str:
    """Fetch a CSV endpoint directly (bypasses make_intervals_request, which
    parses JSON). Mirrors the helper in ``tools/activity_analytics.py``."""
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
# Athlete reads
# ===========================================================================


@mcp.tool()
async def get_athlete_basic_profile(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the athlete's basic public profile from ``/athlete/{id}/profile``.

    This is **distinct** from ``get_athlete_profile`` (which calls the bare
    ``/athlete/{id}`` endpoint and returns the full record with bikes,
    sportSettings, zones, etc.). The ``/profile`` endpoint returns only a
    small subset wrapped in ``{athlete, sharedFolders, customItems}`` —
    suitable for surfacing identity to other users (city/country/timezone,
    bio, profile picture) without exposing private fields like email or
    weight.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: The Intervals.icu API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/profile", api_key=api_key
    )
    if _is_error(result):
        return _error_message(result, "fetching basic athlete profile")  # type: ignore[arg-type]
    if not isinstance(result, dict):
        return f"No basic profile found for athlete {athlete_id_to_use}."
    return format_athlete_basic_profile(result)


@mcp.tool()
async def get_athlete_summary(
    athlete_id: str | None = None,
    api_key: str | None = None,
    format: str = "json",  # noqa: A002 - mirrors API param naming
) -> str:
    """Get the athlete's training summary (weekly totals, time-in-zones, by-category).

    Calls ``/athlete/{id}/athlete-summary`` (json) or
    ``/athlete/{id}/athlete-summary.csv`` (csv). The summary is a list of
    weekly buckets with totals (count, time, distance, load), the load model
    (fitness/fatigue/form/ramp), per-zone time, and a per-category breakdown
    (Ride / Run / Workout / etc.).

    Args:
        athlete_id: The Intervals.icu athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: The Intervals.icu API key (optional; defaults to API_KEY env var).
        format: ``"json"`` (default, parsed table) or ``"csv"`` (raw CSV in a code block).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    fmt_err = _validate_format(format)
    if fmt_err:
        return fmt_err

    if format == "csv":
        text = await _fetch_csv(f"/athlete/{athlete_id_to_use}/athlete-summary.csv", api_key)
        if text.startswith("Error"):
            return text
        return format_csv_block(text, f"Athlete summary CSV — {athlete_id_to_use}")

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/athlete-summary", api_key=api_key
    )
    if _is_error(result):
        return _error_message(result, "fetching athlete summary")  # type: ignore[arg-type]
    return format_athlete_summary(result)  # type: ignore[arg-type]


@mcp.tool()
async def get_athlete_settings_for_device(
    device_class: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the athlete's per-device app settings.

    Returns the free-form key→value map of UI/app settings tailored to a
    particular client form factor. Useful for inspecting the same dashboard
    layouts and chart configs that the Intervals.icu web/mobile clients use.

    Args:
        device_class: One of ``"phone"``, ``"tablet"``, or ``"desktop"``.
        athlete_id: The Intervals.icu athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: The Intervals.icu API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if device_class not in _VALID_DEVICE_CLASSES:
        return f"Error: device_class must be one of {_VALID_DEVICE_CLASSES} (got {device_class!r})."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/settings/{device_class}", api_key=api_key
    )
    if _is_error(result):
        return _error_message(result, "fetching device settings")  # type: ignore[arg-type]
    if not isinstance(result, dict):
        return f"No device settings found for {device_class}."
    return format_athlete_settings(result)


@mcp.tool()
async def get_athlete_training_plan(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the athlete's currently assigned training plan (if any).

    Returns the plan id, alias, start date, last-applied timestamp, and the
    nested plan object. If no plan is assigned, all fields are null.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: The Intervals.icu API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/training-plan", api_key=api_key
    )
    if _is_error(result):
        return _error_message(result, "fetching training plan")  # type: ignore[arg-type]
    if not isinstance(result, dict):
        return f"No training plan info found for athlete {athlete_id_to_use}."
    return format_training_plan(result)


# ===========================================================================
# Athlete writes
# ===========================================================================


@mcp.tool()
async def update_athlete(
    athlete_id: str | None = None,
    api_key: str | None = None,
    name: str | None = None,
    email: str | None = None,
    weight: float | None = None,
    height: float | None = None,
    bio: str | None = None,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
    timezone: str | None = None,
    sex: str | None = None,
    other_fields: dict[str, Any] | None = None,
) -> str:
    """Update the athlete record (PUT ``/athlete/{id}``).

    The upstream Athlete schema has dozens of fields. This tool exposes a
    focused set of common fields plus an ``other_fields`` escape hatch for
    rarely-touched keys (e.g. ``measurement_preference``, ``fahrenheit``,
    ``wind_speed``, ``rain``). Only non-None fields are sent; unset fields
    are not modified.

    Note: a future tightening pass will gate writes via Pydantic
    ``extra="forbid"`` once the full Athlete schema is enumerated; for now
    callers can pass arbitrary keys via ``other_fields``.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: The Intervals.icu API key (optional; defaults to API_KEY env var).
        name: Display name.
        email: Email address.
        weight: Weight in kg.
        height: Height in metres.
        bio: Free-text bio.
        city: City of residence.
        state: State or region.
        country: Country.
        timezone: IANA timezone (e.g. ``Europe/Berlin``).
        sex: ``M`` or ``F`` (per the API).
        other_fields: Optional dict merged on top of focused fields.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    if email is not None:
        body["email"] = email
    if weight is not None:
        body["weight"] = weight
    if height is not None:
        body["height"] = height
    if bio is not None:
        body["bio"] = bio
    if city is not None:
        body["city"] = city
    if state is not None:
        body["state"] = state
    if country is not None:
        body["country"] = country
    if timezone is not None:
        body["timezone"] = timezone
    if sex is not None:
        body["sex"] = sex
    if other_fields:
        if not isinstance(other_fields, dict):
            return "Error: 'other_fields' must be a dict if provided."
        body.update(other_fields)

    if not body:
        return (
            "Error: at least one field must be provided to update_athlete (or pass other_fields)."
        )

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}",
        api_key=api_key,
        method="PUT",
        data=body,
    )
    if _is_error(result):
        return _error_message(result, "updating athlete")  # type: ignore[arg-type]
    if not isinstance(result, dict):
        return f"Athlete {athlete_id_to_use} updated."
    # Reduce to focused fields the user is likely to care about
    display = {k: result.get(k) for k in (("id",) + _ATHLETE_FOCUSED_FIELDS) if k in result}
    if "id" not in display:
        display["id"] = athlete_id_to_use
    return format_athlete_update_result(display)


@mcp.tool()
async def update_athlete_plans(
    plan_id: int | str | None = None,
    new_folder_id: int | str | None = None,
    start_date_local: str | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
    raw_body: list[dict[str, Any]] | None = None,
) -> str:
    """Reassign / update the training plan for the resolved athlete.

    Calls PUT ``/athlete-plans``. The endpoint is multi-athlete on the API side
    (the body is a list of ``{athlete_id, plan_id, ...}`` entries). For
    single-user usage we wrap the simplified params into a single-element
    list keyed on the resolved athlete id. Pass ``raw_body`` to send a full
    multi-athlete payload as-is.

    Args:
        plan_id: New training plan id to assign (numeric).
        new_folder_id: New folder id (alternative to ``plan_id`` per upstream).
        start_date_local: Plan start date in ``YYYY-MM-DD``.
        athlete_id: The Intervals.icu athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: The Intervals.icu API key (optional; defaults to API_KEY env var).
        raw_body: Escape hatch — full list payload to send unchanged (overrides
            simplified params).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    if raw_body is not None:
        if not isinstance(raw_body, list):
            return "Error: 'raw_body' must be a list of plan-assignment dicts."
        body: list[dict[str, Any]] = raw_body
    else:
        item: dict[str, Any] = {"athlete_id": athlete_id_to_use}
        if plan_id is not None:
            item["plan_id"] = plan_id
        if new_folder_id is not None:
            item["new_folder_id"] = new_folder_id
        if start_date_local is not None:
            item["start_date_local"] = start_date_local
        if len(item) == 1:
            return (
                "Error: provide at least one of plan_id / new_folder_id / "
                "start_date_local (or pass raw_body)."
            )
        body = [item]

    result = await make_intervals_request(
        url="/athlete-plans",
        api_key=api_key,
        method="PUT",
        data=body,  # type: ignore[arg-type]
    )
    if _is_error(result):
        return _error_message(result, "updating athlete plans")  # type: ignore[arg-type]
    return f"Athlete plans updated for {athlete_id_to_use}."


@mcp.tool()
async def update_athlete_training_plan(
    training_plan_start_date: str | None = None,
    training_plan_id: int | str | None = None,
    training_plan_alias: str | None = None,
    timezone: str | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
    other_fields: dict[str, Any] | None = None,
) -> str:
    """Update the athlete's training-plan binding (PUT ``/athlete/{id}/training-plan``).

    The body is a TrainingPlan object. Schema is inferred from the GET
    response: ``training_plan_id``, ``training_plan_start_date``,
    ``training_plan_alias``, ``timezone``, and an embedded ``training_plan``
    object. Only non-None fields are sent.

    Args:
        training_plan_start_date: Plan start date in ``YYYY-MM-DD`` (most
            common field to update — re-anchors the plan calendar).
        training_plan_id: Plan id to bind to.
        training_plan_alias: Plan alias.
        timezone: IANA timezone for the plan.
        athlete_id: The Intervals.icu athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: The Intervals.icu API key (optional; defaults to API_KEY env var).
        other_fields: Extra fields merged on top (escape hatch for rarely-set keys
            like the nested ``training_plan`` object).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    body: dict[str, Any] = {}
    if training_plan_start_date is not None:
        body["training_plan_start_date"] = training_plan_start_date
    if training_plan_id is not None:
        body["training_plan_id"] = training_plan_id
    if training_plan_alias is not None:
        body["training_plan_alias"] = training_plan_alias
    if timezone is not None:
        body["timezone"] = timezone
    if other_fields:
        if not isinstance(other_fields, dict):
            return "Error: 'other_fields' must be a dict if provided."
        body.update(other_fields)

    if not body:
        return (
            "Error: at least one field must be provided to "
            "update_athlete_training_plan (or pass other_fields)."
        )

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/training-plan",
        api_key=api_key,
        method="PUT",
        data=body,
    )
    if _is_error(result):
        return _error_message(result, "updating athlete training plan")  # type: ignore[arg-type]
    if not isinstance(result, dict):
        return f"Training plan updated for athlete {athlete_id_to_use}."
    return format_training_plan_update_result(result)


# ===========================================================================
# Weather
# ===========================================================================


@mcp.tool()
async def get_weather_config(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the athlete's weather configuration (locations + provider).

    Args:
        athlete_id: The Intervals.icu athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: The Intervals.icu API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/weather-config", api_key=api_key
    )
    if _is_error(result):
        return _error_message(result, "fetching weather config")  # type: ignore[arg-type]
    if not isinstance(result, dict):
        return "No weather config available."
    return format_weather_config(result)


@mcp.tool()
async def update_weather_config(
    forecasts: list[dict[str, Any]],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Update the athlete's weather configuration.

    Body shape (inferred from GET): ``{"forecasts": [{"id", "provider",
    "location", "label", "lat", "lon", "enabled"}, ...]}``. Pass the full list
    of locations you want configured (omit a location to remove it).

    Args:
        forecasts: List of forecast-location dicts. Each typically includes
            ``provider``, ``location``, ``label``, ``lat``, ``lon``, and
            ``enabled``. The ``id`` field is server-assigned for new entries.
        athlete_id: The Intervals.icu athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: The Intervals.icu API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not isinstance(forecasts, list):
        return "Error: 'forecasts' must be a list of forecast-location dicts."

    body = {"forecasts": forecasts}
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/weather-config",
        api_key=api_key,
        method="PUT",
        data=body,
    )
    if _is_error(result):
        return _error_message(result, "updating weather config")  # type: ignore[arg-type]
    if not isinstance(result, dict):
        return "Weather config updated."
    return format_weather_config_update_result(result)


@mcp.tool()
async def get_weather_forecast(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the multi-day weather forecast for the athlete's configured locations.

    Returns daily summaries (temp min/max, wind, rain, humidity, description)
    for each enabled location in the weather config.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: The Intervals.icu API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/weather-forecast", api_key=api_key
    )
    if _is_error(result):
        return _error_message(result, "fetching weather forecast")  # type: ignore[arg-type]
    if not isinstance(result, (dict, list)):
        return "No forecast data available."
    return format_weather_forecast(result)


# ===========================================================================
# Shared events
# ===========================================================================


@mcp.tool()
async def get_shared_event(
    event_id: str,
    api_key: str | None = None,
) -> str:
    """Get a shared event by ID.

    Calls ``/shared-event/{id}`` — note this is a **global** endpoint (no
    ``/athlete/{id}/...`` prefix). Useful for inspecting public race or
    event metadata that an athlete or their coach has linked.

    Args:
        event_id: The shared event ID (numeric).
        api_key: The Intervals.icu API key (optional; defaults to API_KEY env var).
    """
    if not event_id:
        return "Error: event_id is required."

    result = await make_intervals_request(url=f"/shared-event/{event_id}", api_key=api_key)
    if _is_error(result):
        return _error_message(result, "fetching shared event")  # type: ignore[arg-type]
    if not isinstance(result, dict):
        return f"Shared event {event_id} not found."
    return format_shared_event(result)


# ===========================================================================
# OAuth — disconnect
# ===========================================================================


@mcp.tool()
async def disconnect_app(
    api_key: str | None = None,
) -> str:
    """Disconnect the athlete from the OAuth app matching the bearer token.

    Calls ``DELETE /disconnect-app``. The endpoint identifies the app via the
    auth header — for OAuth-session auth this revokes the app's grant. For
    personal-API-key auth (which is what this MCP server typically uses)
    this endpoint has no meaningful effect; it tends to either no-op or
    return an error. Calling it via this MCP is safe — but if you're using a
    personal API key, expect an empty / not-applicable response.

    Args:
        api_key: The Intervals.icu API key (optional; defaults to API_KEY env var).
    """
    result = await make_intervals_request(
        url="/disconnect-app",
        api_key=api_key,
        method="DELETE",
    )
    if _is_error(result):
        # Surface the API error as a normal message — this is expected for
        # personal-API-key auth.
        return _error_message(result, "disconnecting app")  # type: ignore[arg-type]
    return format_disconnect_app_result(result if isinstance(result, dict) else None)
