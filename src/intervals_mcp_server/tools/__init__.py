"""
MCP tools registry for Intervals.icu MCP Server.

This module registers all available MCP tools with the FastMCP server instance.
"""

from mcp.server.fastmcp import FastMCP  # pylint: disable=import-error

# Import all tools for re-export
# Note: Tools register themselves via @mcp.tool() decorators when imported
from intervals_mcp_server.tools.activities import (  # noqa: F401
    get_activities,
    get_activity_details,
    get_activity_intervals,
    get_activity_streams,
)
from intervals_mcp_server.tools.events import (  # noqa: F401
    add_or_update_event,
    delete_event,
    delete_events_by_date_range,
    get_event_by_id,
    get_events,
)
from intervals_mcp_server.tools.wellness import get_wellness_data  # noqa: F401
from intervals_mcp_server.tools.athlete import (  # noqa: F401
    get_athlete_profile,
    get_fitness_curve,
    get_ftp_history,
)
from intervals_mcp_server.tools.sport_settings import (  # noqa: F401
    apply_sport_settings_to_activities,
    create_sport_settings,
    delete_sport_settings,
    get_sport_settings,
    list_activities_matching_sport_settings,
    list_pace_distances,
    list_pace_distances_for_sport,
    list_sport_settings,
    update_sport_settings,
    update_sport_settings_multi,
)
from intervals_mcp_server.tools.wellness_writes import (  # noqa: F401
    get_wellness_record,
    update_wellness_record,
    update_wellness_record_today,
    update_wellness_records_bulk,
    upload_wellness_csv,
)
from intervals_mcp_server.tools.events_extras import (  # noqa: F401
    apply_plan,
    create_multiple_events,
    delete_events_bulk,
    duplicate_events,
    list_event_tags,
    mark_event_as_done,
    update_events_in_range,
)
from intervals_mcp_server.tools.library import (  # noqa: F401
    apply_current_plan_changes,
    create_multiple_workouts,
    create_workout,
    create_workout_folder,
    delete_workout,
    delete_workout_folder,
    duplicate_workouts,
    get_workout,
    list_folder_shared_with,
    list_workout_folders,
    list_workout_tags,
    list_workouts,
    update_folder_shared_with,
    update_plan_workouts,
    update_workout,
    update_workout_folder,
)


def register_tools(mcp_instance: FastMCP) -> None:
    """
    Register all MCP tools with the FastMCP server instance.

    This function imports all tool modules, which causes their @mcp.tool()
    decorators to register the tools. The tools need access to the mcp instance,
    so they will be imported after the mcp instance is created.

    Args:
        mcp_instance (FastMCP): The FastMCP server instance to register tools with.
    """
    # Tools are registered via decorators when modules are imported above
    # The mcp_instance parameter is kept for future use if needed
    _ = mcp_instance


__all__ = [
    "register_tools",
    "get_activities",
    "get_activity_details",
    "get_activity_intervals",
    "get_activity_streams",
    "get_events",
    "get_event_by_id",
    "delete_event",
    "delete_events_by_date_range",
    "add_or_update_event",
    "get_wellness_data",
    "get_athlete_profile",
    "get_fitness_curve",
    "get_ftp_history",
    # sport_settings
    "list_sport_settings",
    "get_sport_settings",
    "create_sport_settings",
    "update_sport_settings",
    "update_sport_settings_multi",
    "delete_sport_settings",
    "apply_sport_settings_to_activities",
    "list_activities_matching_sport_settings",
    "list_pace_distances_for_sport",
    "list_pace_distances",
    # wellness_writes
    "get_wellness_record",
    "update_wellness_record",
    "update_wellness_record_today",
    "update_wellness_records_bulk",
    "upload_wellness_csv",
    # events_extras
    "mark_event_as_done",
    "apply_plan",
    "create_multiple_events",
    "delete_events_bulk",
    "duplicate_events",
    "update_events_in_range",
    "list_event_tags",
    # library (workout templates + folders)
    "list_workout_folders",
    "create_workout_folder",
    "delete_workout_folder",
    "update_workout_folder",
    "list_folder_shared_with",
    "update_folder_shared_with",
    "update_plan_workouts",
    "list_workout_tags",
    "list_workouts",
    "create_workout",
    "create_multiple_workouts",
    "delete_workout",
    "get_workout",
    "update_workout",
    "apply_current_plan_changes",
    "duplicate_workouts",
]
