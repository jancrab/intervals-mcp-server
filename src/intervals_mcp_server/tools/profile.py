"""
Profile gate for the Intervals.icu MCP Server.

Two profiles are supported via the `INTERVALS_PROFILE` env var:

- `lean` (default) — exposes 26 high-value tools chosen to cover the four
  AI training-partner workflows (daily readiness, weekly planning, post-
  workout debrief, strength logging) plus Zwift workout export. Keeps the
  MCP tool catalog small (~10 KB of schema) so it doesn't dominate Claude
  Desktop / DXT context windows.

- `full` — exposes all 133 tools. Useful for power users who want SDK-
  style coverage of the full intervals.icu API surface. Costs ~50 KB of
  schema in the system prompt on every turn.

The profile is applied AFTER all tool modules import. Each tool module
unconditionally calls `@mcp.tool()` at import time; we then walk the
FastMCP tool registry and remove tools that aren't in the lean set.
This keeps the per-module code uncluttered with profile checks.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP  # pylint: disable=import-error

logger = logging.getLogger("intervals_icu_mcp_server")


# ---------------------------------------------------------------------------
# Lean tool set
# ---------------------------------------------------------------------------
#
# Selection criteria: the four AI-training-partner skills (daily-readiness,
# weekly-planning, post-workout-debrief, log-strength-session) must work
# end-to-end on lean. Plus `download_workout` is always included because
# Zwift / ERG / MRC export is a frequent direct-user request.
#
# When adding a tool to lean: ask "would removing this break a skill or
# require a fallback?" If yes, keep it. If no, the user can flip
# INTERVALS_PROFILE=full when they need the long tail.
LEAN_TOOLS: frozenset[str] = frozenset(
    {
        # --- Athlete identity & thresholds --------------------------------
        "get_athlete_profile",          # parses sportSettings → per-discipline thresholds
        "get_athlete_basic_profile",    # cheap /profile call
        "get_ftp_history",              # FTP change-points for power prescription
        # --- Wellness (readiness data) ------------------------------------
        "get_wellness_data",            # range query — daily-readiness, debrief
        "get_wellness_record",          # single date
        "update_wellness_record_today", # log subjective wellness today
        # --- Fitness curve (CTL / ATL / TSB) ------------------------------
        "get_fitness_curve",
        # --- Activities (read) --------------------------------------------
        "get_activities",               # list activities in range
        "get_activity_details",         # single activity full detail
        "get_activity_streams",         # 1Hz time-series (power, HR, cadence, pace)
        "get_activity_intervals",       # interval-level breakdown
        "search_for_activities",        # query by criteria
        "list_activities_around",       # nearby activities by id
        # --- Activity messages (coach comments) ---------------------------
        "get_activity_messages",
        "add_activity_message",
        # --- Activity analytics (high-value for debrief) ------------------
        "get_activity_power_curve",
        "get_activity_hr_curve",
        "find_best_efforts",
        # --- Events (planned workouts, races) -----------------------------
        "get_events",
        "get_event_by_id",
        "add_or_update_event",          # create OR update — single combined tool
        "delete_event",
        "mark_event_as_done",
        # --- Workout library ----------------------------------------------
        "list_workouts",
        "get_workout",
        "download_workout",             # Zwift .zwo / .mrc / .erg / .fit export
    }
)


def apply_profile(mcp: FastMCP, profile: str) -> tuple[int, int]:
    """
    Filter the registered MCP tools according to the active profile.

    Args:
        mcp: The shared FastMCP instance with all tools already registered
            via their @mcp.tool() decorators.
        profile: Either "lean" or "full". Anything other than "full" is
            treated as lean by `config.load_config`.

    Returns:
        (kept, removed) — counts for logging / tests.
    """
    if profile == "full":
        kept = len(mcp._tool_manager._tools)  # pylint: disable=protected-access
        logger.info("Profile=full — exposing all %d tools", kept)
        return kept, 0

    # Lean path: remove anything not in LEAN_TOOLS.
    all_names = list(mcp._tool_manager._tools.keys())  # pylint: disable=protected-access
    removed = 0
    for name in all_names:
        if name not in LEAN_TOOLS:
            mcp._tool_manager.remove_tool(name)  # pylint: disable=protected-access
            removed += 1
    kept = len(mcp._tool_manager._tools)  # pylint: disable=protected-access

    logger.info(
        "Profile=lean — exposing %d/%d tools (removed %d). "
        "Set INTERVALS_PROFILE=full to expose all tools.",
        kept,
        kept + removed,
        removed,
    )

    # Sanity check: every name in LEAN_TOOLS should have actually been
    # registered by some module. If not, a typo in LEAN_TOOLS or a missing
    # module import will silently drop tools — surface that as a warning.
    actual_names = set(mcp._tool_manager._tools.keys())  # pylint: disable=protected-access
    missing = LEAN_TOOLS - actual_names
    if missing:
        logger.warning(
            "Lean profile references %d tools that are not registered: %s. "
            "Check tool module imports and LEAN_TOOLS spellings.",
            len(missing),
            sorted(missing),
        )

    return kept, removed
