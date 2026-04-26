"""
Markdown formatters for the Intervals.icu Library tools.

Covers folders/plans, workouts (templates), workout tags, and share lists.
Each formatter is defensive against ``None``, empty lists, and unexpected
shapes — failures should surface as a short message rather than raise.
"""

from __future__ import annotations

from typing import Any


def _safe_str(value: Any, default: str = "—") -> str:
    """Return ``value`` as a non-empty string, or ``default`` if missing."""
    if value is None or value == "":
        return default
    return str(value)


def _fmt_seconds(seconds: Any) -> str:
    """Format a duration in seconds as ``HH:MM:SS`` or ``MM:SS``.

    Returns ``—`` if seconds is None / non-numeric.
    """
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return "—"
    if s < 0:
        return "—"
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


# ---------------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------------


def format_workout_list(workouts: Any) -> str:
    """Format a list of workouts as a markdown table."""
    if workouts is None:
        return "No workouts returned."
    if not isinstance(workouts, list):
        return (
            f"Unexpected response: workouts payload was not a list (got {type(workouts).__name__})."
        )
    if not workouts:
        return "No workouts found in library."

    lines = [
        f"## Workouts ({len(workouts)})",
        "",
        "| ID | Name | Type | Duration | Target | Folder |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for w in workouts:
        if not isinstance(w, dict):
            continue
        lines.append(
            "| {id} | {name} | {type} | {dur} | {target} | {folder} |".format(
                id=_safe_str(w.get("id")),
                name=_safe_str(w.get("name")),
                type=_safe_str(w.get("type")),
                dur=_fmt_seconds(w.get("moving_time")),
                target=_safe_str(w.get("target")),
                folder=_safe_str(w.get("folder_id")),
            )
        )
    return "\n".join(lines)


def format_workout_detail(workout: Any) -> str:
    """Format a single workout including a brief workout_doc summary."""
    if workout is None:
        return "No workout returned."
    if not isinstance(workout, dict):
        return (
            f"Unexpected response: workout payload was not a dict (got {type(workout).__name__})."
        )

    parts: list[str] = []
    name = _safe_str(workout.get("name"))
    parts.append(f"## Workout: {name}")
    parts.append("")
    parts.append(f"- ID: {_safe_str(workout.get('id'))}")
    parts.append(f"- Type: {_safe_str(workout.get('type'))}")
    parts.append(f"- Sub-type: {_safe_str(workout.get('sub_type'))}")
    parts.append(f"- Folder ID: {_safe_str(workout.get('folder_id'))}")
    parts.append(f"- Day: {_safe_str(workout.get('day'))}")
    parts.append(f"- Duration: {_fmt_seconds(workout.get('moving_time'))}")
    parts.append(f"- Target: {_safe_str(workout.get('target'))}")
    parts.append(f"- Indoor: {_safe_str(workout.get('indoor'))}")
    parts.append(f"- Training load: {_safe_str(workout.get('icu_training_load'))}")
    parts.append(f"- Intensity: {_safe_str(workout.get('icu_intensity'))}")
    parts.append(f"- Hide from athlete: {_safe_str(workout.get('hide_from_athlete'))}")

    tags = workout.get("tags")
    if tags and isinstance(tags, list):
        parts.append(f"- Tags: {', '.join(str(t) for t in tags)}")

    description = workout.get("description")
    if description:
        parts.append("")
        parts.append("### Description")
        parts.append(str(description))

    doc = workout.get("workout_doc")
    if isinstance(doc, dict) and doc:
        parts.append("")
        parts.append("### Structured workout (`workout_doc`)")
        steps = doc.get("steps") or doc.get("intervals") or []
        if isinstance(steps, list):
            parts.append(f"- Steps: {len(steps)}")
        duration = doc.get("duration") or doc.get("moving_time")
        if duration is not None:
            parts.append(f"- Doc duration: {_fmt_seconds(duration)}")
        # Highlight the top-level keys so the user can see the shape
        parts.append(f"- Top-level keys: {', '.join(sorted(doc.keys()))}")

    return "\n".join(parts)


def format_bulk_workout_create(workouts: Any) -> str:
    """Format the result of ``create_multiple_workouts`` as a markdown table."""
    if workouts is None:
        return "Bulk workout creation accepted (no payload returned)."
    if isinstance(workouts, dict) and "workouts" in workouts:
        workouts = workouts.get("workouts")
    if not isinstance(workouts, list):
        return f"Bulk workout creation completed (response shape: {type(workouts).__name__})."
    if not workouts:
        return "Bulk workout creation completed — 0 workouts created."

    lines = [
        f"Created {len(workouts)} workouts:",
        "",
        "| ID | Name | Type | Folder |",
        "| --- | --- | --- | --- |",
    ]
    for w in workouts:
        if not isinstance(w, dict):
            continue
        lines.append(
            f"| {_safe_str(w.get('id'))} | {_safe_str(w.get('name'))} | "
            f"{_safe_str(w.get('type'))} | {_safe_str(w.get('folder_id'))} |"
        )
    return "\n".join(lines)


def format_duplicate_workouts_result(result: Any) -> str:
    """Summarize the response from ``duplicate_workouts``."""
    if result is None:
        return "Duplicate workouts request accepted (no payload returned)."
    if isinstance(result, list):
        ids = [
            str(item.get("id"))
            for item in result
            if isinstance(item, dict) and item.get("id") is not None
        ]
        head = f"Duplicated {len(result)} workouts."
        if ids:
            head += f" New IDs: {', '.join(ids[:20])}"
            if len(ids) > 20:
                head += " …"
        return head
    if isinstance(result, dict):
        count = result.get("count") or result.get("num_copies") or result.get("created")
        if count is not None:
            return f"Duplicated workouts. Count: {count}"
        return "Duplicate workouts request completed."
    return f"Duplicate workouts completed (unexpected response shape: {type(result).__name__})."


def format_apply_plan_changes_result(result: Any) -> str:
    """Summarize the response from ``apply_current_plan_changes``."""
    if result is None or result == {}:
        return "Apply current plan changes — request accepted."
    if isinstance(result, dict):
        msg = result.get("message")
        count = result.get("count") or result.get("applied")
        bits = ["Apply current plan changes — request accepted."]
        if count is not None:
            bits.append(f"Applied: {count}")
        if msg:
            bits.append(f"Message: {msg}")
        return " ".join(bits)
    if isinstance(result, list):
        return f"Apply current plan changes — request accepted. Affected items: {len(result)}"
    return "Apply current plan changes — request accepted."


# ---------------------------------------------------------------------------
# Folders / plans
# ---------------------------------------------------------------------------


def format_folder_list(folders: Any) -> str:
    """Format a list of folders/plans as a markdown table."""
    if folders is None:
        return "No folders returned."
    if not isinstance(folders, list):
        return (
            f"Unexpected response: folders payload was not a list (got {type(folders).__name__})."
        )
    if not folders:
        return "No folders found."

    lines = [
        f"## Folders & Plans ({len(folders)})",
        "",
        "| ID | Name | Type | Workouts | Visibility | Activity types |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for f in folders:
        if not isinstance(f, dict):
            continue
        children = f.get("children") or []
        n = f.get("num_workouts")
        if n is None and isinstance(children, list):
            n = len(children)
        types = f.get("activity_types") or []
        types_str = (
            ", ".join(str(t) for t in types) if isinstance(types, list) else _safe_str(types)
        )
        lines.append(
            f"| {_safe_str(f.get('id'))} | {_safe_str(f.get('name'))} | "
            f"{_safe_str(f.get('type'))} | {_safe_str(n, '0')} | "
            f"{_safe_str(f.get('visibility'))} | {types_str or '—'} |"
        )
    return "\n".join(lines)


def format_folder_detail(folder: Any) -> str:
    """Format a single folder/plan."""
    if folder is None:
        return "No folder returned."
    if not isinstance(folder, dict):
        return f"Unexpected response: folder payload was not a dict (got {type(folder).__name__})."

    parts = [
        f"## Folder: {_safe_str(folder.get('name'))}",
        "",
        f"- ID: {_safe_str(folder.get('id'))}",
        f"- Type: {_safe_str(folder.get('type'))}",
        f"- Visibility: {_safe_str(folder.get('visibility'))}",
        f"- Start (local): {_safe_str(folder.get('start_date_local'))}",
        f"- Duration weeks: {_safe_str(folder.get('duration_weeks'))}",
        f"- Hours/week: {_safe_str(folder.get('hours_per_week_min'))}–{_safe_str(folder.get('hours_per_week_max'))}",
        f"- Workouts: {_safe_str(folder.get('num_workouts'), '0')}",
        f"- Shared with: {_safe_str(folder.get('sharedWithCount'), '0')}",
        f"- Read-only workouts: {_safe_str(folder.get('read_only_workouts'))}",
    ]
    types = folder.get("activity_types")
    if isinstance(types, list) and types:
        parts.append(f"- Activity types: {', '.join(str(t) for t in types)}")
    desc = folder.get("description") or folder.get("blurb")
    if desc:
        parts.append("")
        parts.append("### Description")
        parts.append(str(desc))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def format_workout_tags(tags: Any) -> str:
    """Format the workout-tags response as a bullet list."""
    if tags is None:
        return "No workout tags returned."
    if not isinstance(tags, list):
        return f"Unexpected response: tags payload was not a list (got {type(tags).__name__})."
    if not tags:
        return "No workout tags in library."
    lines = [f"## Workout Tags ({len(tags)})", ""]
    for t in tags:
        if isinstance(t, dict):
            lines.append(f"- {_safe_str(t.get('name') or t.get('tag') or t.get('id'))}")
        else:
            lines.append(f"- {_safe_str(t)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sharing
# ---------------------------------------------------------------------------


def format_share_list(shared_with: Any) -> str:
    """Format the share list for a folder."""
    if shared_with is None:
        return "Folder is not shared."
    if not isinstance(shared_with, list):
        return f"Unexpected response: shared-with payload was not a list (got {type(shared_with).__name__})."
    if not shared_with:
        return "Folder is not shared with anyone."
    lines = [f"## Shared with ({len(shared_with)})", ""]
    for s in shared_with:
        if not isinstance(s, dict):
            lines.append(f"- {_safe_str(s)}")
            continue
        name = _safe_str(s.get("name") or s.get("email") or s.get("id"))
        loc_bits = [str(b) for b in (s.get("city"), s.get("state"), s.get("country")) if b]
        loc = f" — {', '.join(loc_bits)}" if loc_bits else ""
        edit = " (canEdit)" if s.get("canEdit") else ""
        lines.append(f"- {name} (id={_safe_str(s.get('id'))}){loc}{edit}")
    return "\n".join(lines)


def format_share_update(result: Any) -> str:
    """Format the result of an updateFolderSharedWith call."""
    if result is None or result == {}:
        return "Share list updated."
    if isinstance(result, list):
        return f"Share list updated. Folder is now shared with {len(result)} athlete(s)."
    if isinstance(result, dict):
        msg = result.get("message")
        if msg:
            return f"Share list updated: {msg}"
        return "Share list updated."
    return "Share list updated."
