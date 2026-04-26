"""
Library MCP tools for Intervals.icu.

Covers workout templates and folders/plans:

- Workouts: list / get / create / update / delete / bulk-create / duplicate
- Folders & plans: list / get-via-list / create / update / delete / share / update-plan-workouts
- Aux: list workout-tags, apply current plan changes

The module follows the patterns established in ``tools/sport_settings.py``
and ``tools/events_extras.py``:

- ``make_intervals_request`` for HTTP (kwarg ``data=`` for JSON bodies).
- ``resolve_athlete_id`` for athlete resolution.
- All tools return a markdown / human-readable string.
- Errors from the API surface as a one-line ``Error ...:`` message.

File-op endpoints (``download-workout``, ``import-workout``, ``workouts.zip``)
are intentionally deferred — they require multipart/file handling and are
scheduled for a later wave.
"""

from __future__ import annotations

import json
from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatters_library import (
    format_apply_plan_changes_result,
    format_bulk_workout_create,
    format_duplicate_workouts_result,
    format_folder_detail,
    format_folder_list,
    format_share_list,
    format_share_update,
    format_workout_detail,
    format_workout_list,
    format_workout_tags,
)
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


def _is_error(result: Any) -> bool:
    """True if the API client returned an error dict."""
    return isinstance(result, dict) and result.get("error") is True


def _error_message(result: dict[str, Any], action: str) -> str:
    """Format an API error response as a one-line user message."""
    return f"Error {action}: {result.get('message', 'Unknown error')}"


# ===========================================================================
# Workouts — reads
# ===========================================================================


@mcp.tool()
async def list_workouts(
    athlete_id: str | None = None,
    api_key: str | None = None,
    folder_id: int | None = None,
) -> str:
    """List all workouts (templates) in the athlete's library.

    Workouts are reusable structured templates that live inside folders
    (regular folders) or plans (folders with a start date). Use
    ``list_workout_folders`` to discover folder/plan IDs.

    Args:
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
        folder_id: Optional filter — only return workouts inside this folder/plan.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    params: dict[str, Any] = {}
    if folder_id is not None:
        params["folderId"] = folder_id

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/workouts",
        api_key=api_key,
        params=params or None,
    )
    if _is_error(result):
        return _error_message(result, "listing workouts")  # type: ignore[arg-type]
    return format_workout_list(result)


@mcp.tool()
async def get_workout(
    workout_id: int,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get a single workout (template) by ID.

    Args:
        workout_id: The numeric workout ID.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if workout_id is None:
        return "Error: workout_id is required."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/workouts/{workout_id}",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "fetching workout")  # type: ignore[arg-type]
    return format_workout_detail(result)


# ===========================================================================
# Workouts — writes
# ===========================================================================


@mcp.tool()
async def create_workout(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    name: str,
    folder_id: int,
    athlete_id: str | None = None,
    api_key: str | None = None,
    description: str | None = None,
    type_: str | None = None,
    workout_doc: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Create a new workout (template) in a folder or plan.

    Body shape derives from the OpenAPI ``WorkoutEx`` schema. Required for
    practical use: ``name``, ``folder_id``, and either a ``workout_doc``
    structured payload or a free-text ``description``.

    The ``workout_doc`` field is a structured workout document — see the
    Event ``workout_doc`` shape used by ``add_or_update_event``. It contains
    steps/repeats/intervals with target zones. The API validates its inner
    shape; this tool passes it through unchanged.

    Args:
        name: Workout name.
        folder_id: Destination folder or plan ID.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
        description: Optional free-text description.
        type_: Activity type (e.g. ``Ride``, ``Run``, ``Swim``).
        workout_doc: Optional structured-workout dict (steps/intervals/targets).
        extra: Additional WorkoutEx fields to merge into the body
            (e.g. ``{"target": "POWER", "indoor": True, "tags": ["VO2"]}``).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not name:
        return "Error: 'name' is required."
    if folder_id is None:
        return "Error: 'folder_id' is required (use list_workout_folders to find one)."

    body: dict[str, Any] = {"name": name, "folder_id": folder_id}
    if description is not None:
        body["description"] = description
    if type_ is not None:
        body["type"] = type_
    if workout_doc is not None:
        if not isinstance(workout_doc, dict):
            return "Error: 'workout_doc' must be a dict if provided."
        body["workout_doc"] = workout_doc
    if extra:
        if not isinstance(extra, dict):
            return "Error: 'extra' must be a dict if provided."
        body.update(extra)

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/workouts",
        api_key=api_key,
        method="POST",
        data=body,
    )
    if _is_error(result):
        return _error_message(result, "creating workout")  # type: ignore[arg-type]
    if isinstance(result, dict):
        return f"Successfully created workout id: {result.get('id', '—')}"
    return "Workout created."


@mcp.tool()
async def create_multiple_workouts(
    workouts: list[dict[str, Any]],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Create multiple workouts (templates) in bulk.

    The request body is a JSON array of WorkoutEx dicts. Each item should
    include at minimum ``name`` and ``folder_id``; ``workout_doc`` is optional
    structured content. Inner shape is validated by the API.

    Args:
        workouts: Non-empty list of workout dicts to create.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not isinstance(workouts, list) or not workouts:
        return "Error: 'workouts' must be a non-empty list of workout dicts."
    for w in workouts:
        if not isinstance(w, dict):
            return "Error: every entry in 'workouts' must be a dict."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/workouts/bulk",
        api_key=api_key,
        method="POST",
        data=workouts,  # type: ignore[arg-type]
    )
    if _is_error(result):
        return _error_message(result, "bulk-creating workouts")  # type: ignore[arg-type]
    return format_bulk_workout_create(result)


@mcp.tool()
async def update_workout(
    workout_id: int,
    updates: dict[str, Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Update an existing workout (template).

    Pass only the fields to change in ``updates`` — the API treats this as a
    full WorkoutEx body, but unspecified fields are typically left intact.

    Args:
        workout_id: The workout ID to update.
        updates: Fields to change (name, description, workout_doc, target, etc.).
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if workout_id is None:
        return "Error: workout_id is required."
    if not isinstance(updates, dict) or not updates:
        return "Error: 'updates' must be a non-empty dict of fields to change."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/workouts/{workout_id}",
        api_key=api_key,
        method="PUT",
        data=updates,
    )
    if _is_error(result):
        return _error_message(result, "updating workout")  # type: ignore[arg-type]
    if isinstance(result, dict):
        return f"Successfully updated workout id: {result.get('id', workout_id)}"
    return "Workout updated."


@mcp.tool()
async def delete_workout(
    workout_id: int,
    athlete_id: str | None = None,
    api_key: str | None = None,
    others: bool | None = None,
) -> str:
    """Delete a workout (template), optionally cascading on a plan.

    If the workout lives on a plan and you set ``others=True``, the API will
    also delete other workouts on the same plan that share the same name —
    useful for clearing a recurring template across all weeks.

    Args:
        workout_id: The workout ID to delete.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
        others: If True, also delete other identically-named workouts on the
            same plan (cascade). Defaults to None (server-side default).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if workout_id is None:
        return "Error: workout_id is required."

    params: dict[str, Any] = {}
    if others is not None:
        params["others"] = "true" if others else "false"

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/workouts/{workout_id}",
        api_key=api_key,
        method="DELETE",
        params=params or None,
    )
    if _is_error(result):
        return _error_message(result, "deleting workout")  # type: ignore[arg-type]
    if isinstance(result, dict) and result:
        return f"Workout deleted: {json.dumps(result)}"
    return f"Workout {workout_id} deleted."


@mcp.tool()
async def duplicate_workouts(
    workout_ids: list[int],
    num_copies: int,
    weeks_between: int = 1,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Duplicate one or more workouts on a plan, spaced N weeks apart.

    Body shape (DuplicateWorkoutsDTO):
        - ``workoutIds``: array of source workout IDs.
        - ``numCopies``: how many copies to make.
        - ``weeksBetween``: spacing between copies in weeks.

    Args:
        workout_ids: Source workout IDs to duplicate.
        num_copies: Number of duplicates to make.
        weeks_between: Spacing in weeks between each copy. Default 1.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not isinstance(workout_ids, list) or not workout_ids:
        return "Error: 'workout_ids' must be a non-empty list of workout IDs."
    if not isinstance(num_copies, int) or num_copies < 1:
        return "Error: 'num_copies' must be a positive integer."

    body = {
        "workoutIds": workout_ids,
        "numCopies": num_copies,
        "weeksBetween": weeks_between,
    }
    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/duplicate-workouts",
        api_key=api_key,
        method="POST",
        data=body,
    )
    if _is_error(result):
        return _error_message(result, "duplicating workouts")  # type: ignore[arg-type]
    return format_duplicate_workouts_result(result)


# ===========================================================================
# Folders / plans — reads
# ===========================================================================


@mcp.tool()
async def list_workout_folders(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """List the athlete's folders, plans, and (nested) workouts.

    A folder with ``type == "PLAN"`` is a structured plan (has start date,
    duration); a regular folder is a flat container.

    Args:
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/folders",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "listing folders")  # type: ignore[arg-type]
    return format_folder_list(result)


# ===========================================================================
# Folders / plans — writes
# ===========================================================================


@mcp.tool()
async def create_workout_folder(
    name: str,
    type_: str = "FOLDER",
    athlete_id: str | None = None,
    api_key: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Create a new workout folder or plan.

    Body shape derives from CreateFolderDTO. For a regular folder, ``type``
    is ``"FOLDER"``. For a plan, set ``type_="PLAN"`` and pass ``extra`` with
    plan-specific fields (e.g. ``start_date_local``, ``duration_weeks``,
    ``hours_per_week_min/max``, ``activity_types``).

    Args:
        name: Folder/plan name.
        type_: ``"FOLDER"`` (default) or ``"PLAN"``.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
        extra: Additional CreateFolderDTO fields to merge into the body.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not name:
        return "Error: 'name' is required."

    body: dict[str, Any] = {"name": name, "type": type_}
    if extra:
        if not isinstance(extra, dict):
            return "Error: 'extra' must be a dict if provided."
        body.update(extra)

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/folders",
        api_key=api_key,
        method="POST",
        data=body,
    )
    if _is_error(result):
        return _error_message(result, "creating folder")  # type: ignore[arg-type]
    if isinstance(result, dict):
        return (
            f"Successfully created folder id: {result.get('id', '—')}\n\n"
            + format_folder_detail(result)
        )
    return "Folder created."


@mcp.tool()
async def update_workout_folder(
    folder_id: int,
    updates: dict[str, Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Update a workout folder or plan.

    Body is a Folder dict — pass only the fields you want to change in
    ``updates``.

    Args:
        folder_id: The folder/plan ID to update.
        updates: Fields to change (name, description, start_date_local, etc.).
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if folder_id is None:
        return "Error: folder_id is required."
    if not isinstance(updates, dict) or not updates:
        return "Error: 'updates' must be a non-empty dict of fields to change."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/folders/{folder_id}",
        api_key=api_key,
        method="PUT",
        data=updates,
    )
    if _is_error(result):
        return _error_message(result, "updating folder")  # type: ignore[arg-type]
    if isinstance(result, dict):
        return f"Successfully updated folder id: {result.get('id', folder_id)}"
    return "Folder updated."


@mcp.tool()
async def delete_workout_folder(
    folder_id: int,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Delete a workout folder or plan, including all its workouts.

    DESTRUCTIVE: cascades to every workout inside. Confirm with the user
    before invoking.

    Args:
        folder_id: The folder/plan ID to delete.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if folder_id is None:
        return "Error: folder_id is required."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/folders/{folder_id}",
        api_key=api_key,
        method="DELETE",
    )
    if _is_error(result):
        return _error_message(result, "deleting folder")  # type: ignore[arg-type]
    if isinstance(result, dict) and result:
        return f"Folder deleted: {json.dumps(result)}"
    return f"Folder {folder_id} deleted (including its workouts)."


@mcp.tool()
async def update_plan_workouts(
    folder_id: int,
    oldest: int,
    newest: int,
    updates: dict[str, Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Update a range of workouts on a plan.

    Per the endpoint inventory, only ``hide_from_athlete`` is mutable across
    a range — pass ``{"hide_from_athlete": True}`` to hide every workout in
    days [oldest, newest]; ``False`` to unhide. The Workout body schema
    technically allows other fields, but the API constrains this endpoint
    to that one toggle. Body shape inferred — verify other fields with a
    manual write test before relying on this.

    Args:
        folder_id: The plan ID containing the workouts.
        oldest: Earliest day index in the range (required query param).
        newest: Latest day index in the range (required query param).
        updates: Fields to change. In practice, ``{"hide_from_athlete": bool}``.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if folder_id is None:
        return "Error: folder_id is required."
    if oldest is None or newest is None:
        return "Error: 'oldest' and 'newest' are required query params (day indices)."
    if not isinstance(updates, dict) or not updates:
        return "Error: 'updates' must be a non-empty dict (typically {'hide_from_athlete': bool})."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/folders/{folder_id}/workouts",
        api_key=api_key,
        method="PUT",
        params={"oldest": oldest, "newest": newest},
        data=updates,
    )
    if _is_error(result):
        return _error_message(result, "updating plan workouts")  # type: ignore[arg-type]
    if isinstance(result, list):
        return f"Updated {len(result)} workouts on plan {folder_id}."
    return f"Plan {folder_id} workouts updated for range [{oldest}, {newest}]."


# ===========================================================================
# Folder sharing
# ===========================================================================


@mcp.tool()
async def list_folder_shared_with(
    folder_id: int,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """List the athletes a folder/plan is shared with.

    Args:
        folder_id: The folder/plan ID.
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if folder_id is None:
        return "Error: folder_id is required."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/folders/{folder_id}/shared-with",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "listing folder share list")  # type: ignore[arg-type]
    return format_share_list(result)


@mcp.tool()
async def update_folder_shared_with(
    folder_id: int,
    shared_with: list[dict[str, Any]],
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Add or remove athletes from a folder/plan's share list.

    The body is a JSON array of SharedWith dicts representing the new full
    share state — each entry needs at minimum ``id`` (athlete id) and may
    include ``canEdit``. To remove someone, omit them from the list.

    Args:
        folder_id: The folder/plan ID.
        shared_with: New full share list (array of SharedWith dicts).
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if folder_id is None:
        return "Error: folder_id is required."
    if not isinstance(shared_with, list):
        return "Error: 'shared_with' must be a list (possibly empty) of SharedWith dicts."
    for s in shared_with:
        if not isinstance(s, dict):
            return "Error: every entry in 'shared_with' must be a dict."

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/folders/{folder_id}/shared-with",
        api_key=api_key,
        method="PUT",
        data=shared_with,  # type: ignore[arg-type]
    )
    if _is_error(result):
        return _error_message(result, "updating folder share list")  # type: ignore[arg-type]
    return format_share_update(result)


# ===========================================================================
# Tags
# ===========================================================================


@mcp.tool()
async def list_workout_tags(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """List all tags applied to workouts in the athlete's library.

    Distinct from event tags (`list_event_tags`).

    Args:
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/workout-tags",
        api_key=api_key,
    )
    if _is_error(result):
        return _error_message(result, "listing workout tags")  # type: ignore[arg-type]
    return format_workout_tags(result)


# ===========================================================================
# Plan changes
# ===========================================================================


@mcp.tool()
async def apply_current_plan_changes(
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Apply pending changes from the athlete's current plan to the calendar.

    Distinct from ``apply_plan`` (which applies a saved plan/folder to the
    calendar fresh). This endpoint propagates edits made to the *currently
    active* plan into already-scheduled events.

    Per the OpenAPI spec, this PUT takes no request body. Body shape inferred
    — verify with a manual write test before relying on it.

    Args:
        athlete_id: Override INTERVALS_ATHLETE_ID env var if provided.
        api_key: Override INTERVALS_API_KEY env var if provided.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/apply-plan-changes",
        api_key=api_key,
        method="PUT",
    )
    if _is_error(result):
        return _error_message(result, "applying current plan changes")  # type: ignore[arg-type]
    return format_apply_plan_changes_result(result)
