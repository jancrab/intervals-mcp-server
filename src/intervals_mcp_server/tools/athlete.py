"""
Athlete-related MCP tools for Intervals.icu.

This module contains derived/extended tools that aren't shipped by the upstream
mvilanova fork but are needed by the AITrainer skill set:

- get_athlete_profile: athlete record with sportSettings parsed into per-discipline
  thresholds (bike FTP/LTHR/maxHR, run threshold pace, swim CSS).
- get_fitness_curve: CTL/ATL/form (TSB) projection over wellness records.
- get_ftp_history: FTP change-points extracted from the activities feed.
"""

from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatting import (
    format_athlete_profile,
    format_fitness_curve,
    format_ftp_history,
)
from intervals_mcp_server.utils.validation import resolve_athlete_id, resolve_date_params

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


@mcp.tool()
async def get_athlete_profile(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the athlete profile from Intervals.icu, including per-discipline thresholds.

    Surfaces identity (name, email, sex, timezone, etc.) plus thresholds parsed from
    sportSettings: bike FTP/LTHR/maxHR, run threshold pace + LTHR/maxHR, swim CSS,
    and other-sport LTHR/maxHR. Pace fields are converted from m/s to mm:ss/km
    (run) or mm:ss/100m (swim).

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}", api_key=api_key
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching athlete profile: {result.get('message')}"

    if not result or not isinstance(result, dict):
        return f"No athlete profile found for athlete {athlete_id_to_use}."

    return format_athlete_profile(result)


@mcp.tool()
async def get_fitness_curve(
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Get the fitness (CTL), fatigue (ATL), and form (TSB = CTL - ATL) curve.

    Derived from /athlete/{id}/wellness — projects per-day CTL, ATL, and computed form.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to 28 days ago)
        end_date: End date in YYYY-MM-DD format (optional, defaults to today)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    start_date, end_date = resolve_date_params(
        start_date, end_date, default_start_days_ago=28
    )

    params = {"oldest": start_date, "newest": end_date}

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/wellness", api_key=api_key, params=params
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching fitness curve: {result.get('message')}"

    records: list[dict[str, Any]] = []
    if isinstance(result, list):
        records = [r for r in result if isinstance(r, dict)]
    elif isinstance(result, dict):
        for date_str, data in result.items():
            if isinstance(data, dict):
                if "id" not in data and "date" not in data:
                    data = {**data, "id": date_str}
                records.append(data)

    if not records:
        return (
            f"No fitness data found for athlete {athlete_id_to_use} "
            "in the specified date range."
        )

    # Sort ascending by date for stable output
    records.sort(key=lambda r: r.get("id") or r.get("date") or "")

    return format_fitness_curve(records)


@mcp.tool()
async def get_ftp_history(
    athlete_id: str | None = None,
    api_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """Get the athlete's FTP change history from Intervals.icu.

    Derived from /athlete/{id}/activities — extracts dates where icu_ftp changed,
    sorted ascending. Consecutive same-FTP entries are deduped.

    Args:
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
        start_date: Start date in YYYY-MM-DD format (optional, defaults to 365 days ago)
        end_date: End date in YYYY-MM-DD format (optional, defaults to today)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    start_date, end_date = resolve_date_params(
        start_date, end_date, default_start_days_ago=365
    )

    params = {"oldest": start_date, "newest": end_date}

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activities",
        api_key=api_key,
        params=params,
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching FTP history: {result.get('message')}"

    activities: list[dict[str, Any]] = []
    if isinstance(result, list):
        activities = [a for a in result if isinstance(a, dict)]
    elif isinstance(result, dict):
        for _key, value in result.items():
            if isinstance(value, list):
                activities = [a for a in value if isinstance(a, dict)]
                break

    if not activities:
        return (
            f"No activities found for athlete {athlete_id_to_use} "
            "in the specified date range."
        )

    return format_ftp_history(activities)
