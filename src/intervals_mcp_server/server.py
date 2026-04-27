"""
Intervals.icu MCP Server

This module implements a Model Context Protocol (MCP) server for connecting
Claude with the Intervals.icu API. It provides tools for retrieving and managing
athlete data, including activities, events, workouts, and wellness metrics.

Main Features:
    - Activity retrieval and detailed analysis
    - Event management (races, workouts, calendar items)
    - Wellness data tracking and visualization
    - Error handling with user-friendly messages
    - Configurable parameters with environment variable support

Usage:
    This server is designed to be run as a standalone script and exposes several MCP tools
    for use with Claude Desktop or other MCP-compatible clients. The server loads configuration
    from environment variables (optionally via a .env file) and communicates with the Intervals.icu API.

    To run the server:
        $ python src/intervals_mcp_server/server.py

    MCP tools provided:
        - get_activities
        - get_activity_details
        - get_activity_intervals
        - get_activity_streams
        - get_activity_messages
        - add_activity_message
        - get_events
        - get_event_by_id
        - add_or_update_event
        - delete_event
        - delete_events_by_date_range
        - get_wellness_data
        - get_custom_items
        - get_custom_item_by_id
        - create_custom_item
        - update_custom_item
        - delete_custom_item

    See the README for more details on configuration and usage.
"""

import logging

# Import API client and configuration
from intervals_mcp_server.api.client import (
    httpx_client,  # Re-export for backward compatibility with tests
    make_intervals_request,
)
from intervals_mcp_server.config import get_config
from intervals_mcp_server.mcp_instance import mcp

# Import types and validation
from intervals_mcp_server.server_setup import setup_transport, start_server
from intervals_mcp_server.utils.validation import validate_athlete_id

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("intervals_icu_mcp_server")

# Get configuration instance
config = get_config()

# Import tool modules to register them (tools register themselves via @mcp.tool() decorators)
# Import tool functions for re-export
from intervals_mcp_server.tools.activities import (  # pylint: disable=wrong-import-position  # noqa: E402
    add_activity_message,
    get_activities,
    get_activity_details,
    get_activity_intervals,
    get_activity_messages,
    get_activity_streams,
)
from intervals_mcp_server.tools.events import (  # pylint: disable=wrong-import-position  # noqa: E402
    add_or_update_event,
    delete_event,
    delete_events_by_date_range,
    get_event_by_id,
    get_events,
)
from intervals_mcp_server.tools.wellness import get_wellness_data  # pylint: disable=wrong-import-position  # noqa: E402
from intervals_mcp_server.tools.custom_items import (  # pylint: disable=wrong-import-position  # noqa: E402
    create_custom_item,
    delete_custom_item,
    get_custom_item_by_id,
    get_custom_items,
    update_custom_item,
)
from intervals_mcp_server.tools.athlete import (  # pylint: disable=wrong-import-position  # noqa: E402
    get_athlete_profile,
    get_fitness_curve,
    get_ftp_history,
)
from intervals_mcp_server.tools.sport_settings import (  # pylint: disable=wrong-import-position  # noqa: E402
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
from intervals_mcp_server.tools.wellness_writes import (  # pylint: disable=wrong-import-position  # noqa: E402
    get_wellness_record,
    update_wellness_record,
    update_wellness_record_today,
    update_wellness_records_bulk,
    upload_wellness_csv,
)
from intervals_mcp_server.tools.events_extras import (  # pylint: disable=wrong-import-position  # noqa: E402
    apply_plan,
    create_multiple_events,
    delete_events_bulk,
    duplicate_events,
    list_event_tags,
    mark_event_as_done,
    update_events_in_range,
)
from intervals_mcp_server.tools.library import (  # pylint: disable=wrong-import-position  # noqa: E402
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
from intervals_mcp_server.tools.activity_analytics import (  # pylint: disable=wrong-import-position  # noqa: E402
    find_best_efforts,
    get_activity_gap_histogram,
    get_activity_hr_curve,
    get_activity_hr_histogram,
    get_activity_hr_load_model,
    get_activity_interval_stats,
    get_activity_map,
    get_activity_pace_curve,
    get_activity_pace_histogram,
    get_activity_power_curve,
    get_activity_power_curves_multistream,
    get_activity_power_histogram,
    get_activity_power_spike_model,
    get_activity_power_vs_hr,
    get_activity_segments,
    get_activity_time_at_hr,
    get_activity_weather_summary,
)
from intervals_mcp_server.tools.activity_writes import (  # pylint: disable=wrong-import-position  # noqa: E402
    delete_activity,
    delete_intervals,
    split_interval,
    update_activity,
    update_activity_streams,
    update_interval,
    update_intervals,
)
from intervals_mcp_server.tools.activity_athlete_level import (  # pylint: disable=wrong-import-position  # noqa: E402
    create_manual_activity,
    create_multiple_manual_activities,
    get_activities_by_ids,
    get_activities_csv,
    get_athlete_mmp_model,
    get_athlete_power_hr_curve,
    list_activities_around,
    list_activity_hr_curves,
    list_activity_pace_curves,
    list_activity_power_curves,
    list_activity_tags,
    list_athlete_hr_curves,
    list_athlete_pace_curves,
    list_athlete_power_curves,
    search_for_activities,
    search_for_activities_full,
    search_for_intervals,
)
from intervals_mcp_server.tools.routes_gear import (  # pylint: disable=wrong-import-position  # noqa: E402
    check_route_merge,
    create_gear,
    create_gear_reminder,
    delete_gear,
    delete_gear_reminder,
    get_athlete_route,
    list_athlete_routes,
    list_gear,
    recalc_gear_distance,
    replace_gear,
    update_athlete_route,
    update_gear,
    update_gear_reminder,
)
from intervals_mcp_server.tools.athlete_extras import (  # pylint: disable=wrong-import-position  # noqa: E402
    disconnect_app,
    get_athlete_basic_profile,
    get_athlete_settings_for_device,
    get_athlete_summary,
    get_athlete_training_plan,
    get_shared_event,
    get_weather_config,
    get_weather_forecast,
    update_athlete,
    update_athlete_plans,
    update_athlete_training_plan,
    update_weather_config,
)
from intervals_mcp_server.tools.file_ops import (  # pylint: disable=wrong-import-position  # noqa: E402
    download_activity_file,
    download_activity_fit_file,
    download_activity_fit_files,
    download_activity_gpx_file,
    download_workout,
    download_workout_for_athlete,
    import_workout_file,
    upload_activity,
    upload_activity_streams_csv,
)
from intervals_mcp_server.tools.profile import apply_profile  # pylint: disable=wrong-import-position  # noqa: E402

# Apply profile gate AFTER all tool modules have registered their tools.
# Lean (default) keeps ~26 tools; full keeps all 133. See tools/profile.py.
apply_profile(mcp, config.profile)

# Re-export make_intervals_request and httpx_client for backward compatibility
# pylint: disable=duplicate-code  # This __all__ list is intentionally similar to tools/__init__.py
__all__ = [
    "make_intervals_request",
    "httpx_client",  # Re-exported for test compatibility
    "add_activity_message",
    "get_activities",
    "get_activity_details",
    "get_activity_intervals",
    "get_activity_messages",
    "get_activity_streams",
    "get_events",
    "get_event_by_id",
    "delete_event",
    "delete_events_by_date_range",
    "add_or_update_event",
    "get_wellness_data",
    "get_custom_items",
    "get_custom_item_by_id",
    "create_custom_item",
    "update_custom_item",
    "delete_custom_item",
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
    # activity_analytics
    "find_best_efforts",
    "get_activity_gap_histogram",
    "get_activity_hr_curve",
    "get_activity_hr_histogram",
    "get_activity_hr_load_model",
    "get_activity_interval_stats",
    "get_activity_map",
    "get_activity_pace_curve",
    "get_activity_pace_histogram",
    "get_activity_power_curve",
    "get_activity_power_curves_multistream",
    "get_activity_power_histogram",
    "get_activity_power_spike_model",
    "get_activity_power_vs_hr",
    "get_activity_segments",
    "get_activity_time_at_hr",
    "get_activity_weather_summary",
    # activity_writes
    "update_activity",
    "delete_activity",
    "update_activity_streams",
    "update_intervals",
    "update_interval",
    "delete_intervals",
    "split_interval",
    # activity_athlete_level
    "get_activities_by_ids",
    "list_activities_around",
    "get_activities_csv",
    "search_for_activities",
    "search_for_activities_full",
    "search_for_intervals",
    "list_activity_tags",
    "list_activity_hr_curves",
    "list_activity_pace_curves",
    "list_activity_power_curves",
    "list_athlete_hr_curves",
    "list_athlete_pace_curves",
    "list_athlete_power_curves",
    "get_athlete_power_hr_curve",
    "get_athlete_mmp_model",
    "create_manual_activity",
    "create_multiple_manual_activities",
    # routes_gear (Wave 4A)
    "list_athlete_routes",
    "get_athlete_route",
    "update_athlete_route",
    "check_route_merge",
    "list_gear",
    "create_gear",
    "update_gear",
    "delete_gear",
    "recalc_gear_distance",
    "replace_gear",
    "create_gear_reminder",
    "update_gear_reminder",
    "delete_gear_reminder",
    # athlete_extras (Wave 4B)
    "update_athlete",
    "update_athlete_plans",
    "get_athlete_summary",
    "get_athlete_settings_for_device",
    "get_athlete_training_plan",
    "update_athlete_training_plan",
    "get_athlete_basic_profile",
    "get_weather_config",
    "update_weather_config",
    "get_weather_forecast",
    "get_shared_event",
    "disconnect_app",
    # file_ops (Wave 5)
    "upload_activity",
    "upload_activity_streams_csv",
    "import_workout_file",
    "download_activity_file",
    "download_activity_fit_file",
    "download_activity_gpx_file",
    "download_activity_fit_files",
    "download_workout",
    "download_workout_for_athlete",
]


# Run the server
if __name__ == "__main__":
    # Validate ATHLETE_ID when server starts (not at import time to allow tests)
    validate_athlete_id(config.athlete_id)

    # Setup transport and start server
    selected_transport = setup_transport()
    start_server(mcp, selected_transport)
