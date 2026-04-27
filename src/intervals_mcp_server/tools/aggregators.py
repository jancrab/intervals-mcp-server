"""
Cross-domain aggregator tools for Intervals.icu MCP Server.

These tools exist to trade wall-clock time (multiple HTTP requests, run
in parallel via `asyncio.gather`) for context-window cost (one tool's
worth of schema instead of 8). They're designed for the lean profile:
"give me everything for this activity in one call" beats the model
deciding to call 8 individual tools sequentially.

Each aggregator:
- Calls the underlying tool functions (which return formatted markdown).
- Wraps each subcall in `_safe` so a single failure surfaces as
  "(unavailable: ...)" inside its own section instead of poisoning the
  whole report.
- Runs all subcalls concurrently — the wall-clock cost is bounded by the
  slowest single endpoint, not the sum.
- Concatenates the per-section markdown into a single response.

Section ordering follows the natural debrief flow: high-level summary
first (details), then structure (intervals), then human context
(messages), then performance (curves, best efforts, segments), then
environment (weather), then optionally raw data (streams).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable

from intervals_mcp_server.mcp_instance import mcp
from intervals_mcp_server.tools.activities import (
    get_activity_details,
    get_activity_intervals,
    get_activity_messages,
    get_activity_streams,
)
from intervals_mcp_server.tools.activity_analytics import (
    find_best_efforts,
    get_activity_hr_curve,
    get_activity_power_curve,
    get_activity_segments,
    get_activity_weather_summary,
)

logger = logging.getLogger("intervals_icu_mcp_server")


async def _safe(label: str, coro: Awaitable[str]) -> str:
    """
    Run a single subcall, return a markdown section.

    Wraps each subcall so a 404 / 500 / parse error in one endpoint
    surfaces as a "(unavailable)" line inside its own section instead of
    cancelling the whole `gather` and losing the other sections.

    The underlying tool functions return strings starting with "Error" on
    soft failures (e.g. permission denied, no data); we treat those the
    same as exceptions for reporting purposes.
    """
    try:
        result = await coro
    except Exception as exc:  # noqa: BLE001  pylint: disable=broad-exception-caught
        logger.exception("Aggregator subcall failed: %s", label)
        return f"### {label}\n_(unavailable: {type(exc).__name__}: {exc})_\n"

    if isinstance(result, str) and result.lstrip().startswith("Error"):
        return f"### {label}\n_(unavailable: {result.strip()})_\n"
    return f"### {label}\n\n{result}\n"


@mcp.tool()
async def get_activity_full_report(  # pylint: disable=too-many-arguments,too-many-locals
    activity_id: str,
    include_streams: bool = False,
    include_segments: bool = True,
    include_weather: bool = True,
    include_best_efforts: bool = True,
    best_effort_duration: int = 300,
    api_key: str | None = None,
) -> str:
    """
    Aggregator: fetch ~all per-activity data in one call.

    Use this in post-workout debrief workflows where you'd otherwise call
    `get_activity_details` + `get_activity_intervals` + `get_activity_messages`
    + `get_activity_power_curve` + `get_activity_hr_curve` +
    `find_best_efforts` + `get_activity_segments` +
    `get_activity_weather_summary` separately. One tool's worth of schema
    cost replaces eight; subcalls run concurrently so wall-clock is bounded
    by the slowest single endpoint.

    Always-included sections (5):
    - **Activity details** — pace, power, HR, TSS, IF, calories, etc.
    - **Intervals** — interval-level breakdown (lap-level if no manual intervals)
    - **Coach messages** — comments and notes on the activity
    - **Power curve** — best-effort power durations across the activity
    - **HR curve** — best-effort HR durations across the activity

    Optional sections (default ON):
    - **Best efforts** — single-window best effort, default `watts` / 5 min
    - **Segments** — segment efforts and PRs hit during the activity
    - **Weather** — weather summary at the activity time/location

    Optional sections (default OFF):
    - **Streams** — raw 1 Hz time-series (power, HR, cadence, pace).
      VERY large response. Only enable if the model needs stream-level
      data for a specific question (e.g. "where exactly did HR drift
      during interval 3?").

    Per-section failures surface as `_(unavailable: ...)_` inside their own
    section without cancelling the rest of the report.

    Args:
        activity_id: intervals.icu activity ID (e.g. `i12345`).
        include_streams: include full 1 Hz time-series. Default `False`
            because streams are large and rarely needed for a debrief.
        include_segments: include segment efforts. Default `True`.
        include_weather: include weather summary. Default `True`.
        include_best_efforts: include best-effort window. Default `True`.
        best_effort_duration: window in seconds for best-effort lookup.
            Default `300` (5 min — common threshold-window benchmark).
            Pass `60` for sprint-power, `1200` for long-effort, etc.
        api_key: optional override; defaults to `API_KEY` env var.
    """
    # Build (label, coroutine) pairs. Mandatory sections always run; the
    # optional ones are conditionally appended.
    tasks: list[tuple[str, Awaitable[str]]] = [
        ("Activity details", get_activity_details(activity_id, api_key=api_key)),
        ("Intervals", get_activity_intervals(activity_id, api_key=api_key)),
        ("Coach messages", get_activity_messages(activity_id, api_key=api_key)),
        ("Power curve", get_activity_power_curve(activity_id, api_key=api_key)),
        ("HR curve", get_activity_hr_curve(activity_id, api_key=api_key)),
    ]

    if include_best_efforts:
        tasks.append(
            (
                f"Best efforts (watts, {best_effort_duration}s)",
                find_best_efforts(
                    activity_id,
                    stream="watts",
                    duration=best_effort_duration,
                    api_key=api_key,
                ),
            )
        )
    if include_segments:
        tasks.append(("Segments", get_activity_segments(activity_id, api_key=api_key)))
    if include_weather:
        tasks.append(
            ("Weather", get_activity_weather_summary(activity_id, api_key=api_key))
        )
    if include_streams:
        tasks.append(("Streams (1 Hz)", get_activity_streams(activity_id, api_key=api_key)))

    sections = await asyncio.gather(*(_safe(label, coro) for label, coro in tasks))

    header = f"# Full report — activity `{activity_id}`\n\n"
    flags = []
    if include_streams:
        flags.append("streams=on")
    if not include_segments:
        flags.append("segments=off")
    if not include_weather:
        flags.append("weather=off")
    if not include_best_efforts:
        flags.append("best_efforts=off")
    if flags:
        header += f"_Flags: {', '.join(flags)}._\n\n"

    return header + "\n".join(sections)
