"""
Markdown formatters for routes and gear MCP tools.

Self-contained — no coupling to shared formatting helpers, mirroring the
approach in `formatters_sport_settings.py`.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _format_distance_m(value: Any) -> str:
    """Render a distance in meters as km if >= 1 km, else m."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if v >= 1000:
        return f"{v / 1000:.1f} km"
    return f"{v:.0f} m"


def _format_time_s(value: Any) -> str:
    """Render seconds as Hh Mm."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    h, rem = divmod(int(v), 3600)
    m = rem // 60
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


# ---------------------------------------------------------------------------
# Route formatters
# ---------------------------------------------------------------------------


def format_route_list(routes: list[dict[str, Any]]) -> str:
    """Format a list of athlete routes as a markdown table."""
    if not routes:
        return "No routes found for athlete."

    rows: list[str] = []
    rows.append("| Route ID | Name | Distance | Elevation | Activities |")
    rows.append("|---|---|---|---|---|")
    for r in routes:
        if not isinstance(r, dict):
            continue
        rows.append(
            "| {rid} | {name} | {dist} | {elev} | {acts} |".format(
                rid=r.get("route_id", r.get("id", "—")),
                name=r.get("name", "—"),
                dist=_format_distance_m(r.get("distance")),
                elev=(
                    f"{r.get('elevation_gain'):.0f} m"
                    if isinstance(r.get("elevation_gain"), (int, float))
                    else "—"
                ),
                acts=r.get("activity_count", r.get("activities", "—")),
            )
        )
    return f"Athlete routes ({len(routes)}):\n\n" + "\n".join(rows)


def format_route_detail(route: dict[str, Any]) -> str:
    """Format a single route record as a markdown block."""
    if not isinstance(route, dict):
        return "Invalid route record."
    rid = route.get("route_id", route.get("id", "—"))
    name = route.get("name", "—")
    lines: list[str] = [f"## Route — {name} (id {rid})"]
    if route.get("description"):
        lines.append(f"- **Description**: {route.get('description')}")
    if route.get("distance") is not None:
        lines.append(f"- **Distance**: {_format_distance_m(route.get('distance'))}")
    if route.get("elevation_gain") is not None:
        lines.append(f"- **Elevation gain**: {route.get('elevation_gain')} m")
    if route.get("commute") is not None:
        lines.append(f"- **Commute**: {route.get('commute')}")
    if route.get("rename_activities") is not None:
        lines.append(f"- **Rename activities**: {route.get('rename_activities')}")
    if route.get("tags"):
        lines.append(f"- **Tags**: {', '.join(route.get('tags') or [])}")
    if route.get("replaced_by_route_id"):
        lines.append(f"- **Replaced by route**: {route.get('replaced_by_route_id')}")
    latlngs = route.get("latlngs")
    if isinstance(latlngs, list):
        lines.append(f"- **Polyline points**: {len(latlngs)}")
    return "\n".join(lines)


def format_route_update_result(route: dict[str, Any]) -> str:
    """Format response from updating a route."""
    if not isinstance(route, dict):
        return "Route updated."
    rid = route.get("route_id", route.get("id", "—"))
    name = route.get("name", "")
    suffix = f" — {name}" if name else ""
    return f"Successfully updated route {rid}{suffix}."


def format_route_similarity(result: dict[str, Any] | Any) -> str:
    """Format the similarity / merge-check result for two routes."""
    if not isinstance(result, dict):
        # API may return a bare number or boolean — render verbatim.
        return f"Route similarity result: {result}"
    lines = ["## Route similarity"]
    score = result.get("similarity") or result.get("score") or result.get("similarity_score")
    if score is not None:
        lines.append(f"- **Similarity score**: {score}")
    can_merge = result.get("can_merge") or result.get("merge")
    if can_merge is not None:
        lines.append(f"- **Can merge**: {can_merge}")
    # Surface any extra fields verbatim
    for key, value in result.items():
        if key in ("similarity", "score", "similarity_score", "can_merge", "merge"):
            continue
        lines.append(f"- **{key}**: {value}")
    if len(lines) == 1:
        # Fallback if the API response is unexpected
        return f"Route similarity result: {result}"
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gear formatters
# ---------------------------------------------------------------------------


def format_gear_list(gear: list[dict[str, Any]]) -> str:
    """Format a list of gear items as a markdown table."""
    if not gear:
        return "No gear found for athlete."

    rows: list[str] = []
    rows.append("| Gear ID | Name | Type | Distance | Activities | Components | Retired |")
    rows.append("|---|---|---|---|---|---|---|")
    for g in gear:
        if not isinstance(g, dict):
            continue
        component_ids = g.get("component_ids") or []
        comp_count = len(component_ids) if isinstance(component_ids, list) else 0
        retired = g.get("retired")
        retired_disp = "yes" if retired else "no"
        rows.append(
            "| {gid} | {name} | {gtype} | {dist} | {acts} | {comp} | {ret} |".format(
                gid=g.get("id", "—"),
                name=g.get("name", "—"),
                gtype=g.get("type", "—"),
                dist=_format_distance_m(g.get("distance")),
                acts=g.get("activities", "—"),
                comp=comp_count,
                ret=retired_disp,
            )
        )
    return f"Gear ({len(gear)}):\n\n" + "\n".join(rows)


def format_gear_detail(gear: dict[str, Any]) -> str:
    """Format a single gear item as a markdown block."""
    if not isinstance(gear, dict):
        return "Invalid gear record."
    gid = gear.get("id", "—")
    name = gear.get("name", "—")
    gtype = gear.get("type", "—")
    lines: list[str] = [f"## Gear — {name} ({gtype}, id {gid})"]
    if gear.get("purchased"):
        lines.append(f"- **Purchased**: {gear.get('purchased')}")
    if gear.get("retired"):
        lines.append(f"- **Retired**: {gear.get('retired')}")
    if gear.get("distance") is not None:
        lines.append(f"- **Total distance**: {_format_distance_m(gear.get('distance'))}")
    if gear.get("time") is not None:
        lines.append(f"- **Total time**: {_format_time_s(gear.get('time'))}")
    if gear.get("activities") is not None:
        lines.append(f"- **Activity count**: {gear.get('activities')}")
    if gear.get("use_elapsed_time") is not None:
        lines.append(f"- **Uses elapsed time**: {gear.get('use_elapsed_time')}")
    if gear.get("component") is not None:
        lines.append(f"- **Is component**: {gear.get('component')}")
    component_ids = gear.get("component_ids") or []
    if isinstance(component_ids, list) and component_ids:
        lines.append(f"- **Components ({len(component_ids)})**: {', '.join(component_ids)}")
    reminders = gear.get("reminders") or []
    if isinstance(reminders, list) and reminders:
        lines.append(f"- **Reminders**: {len(reminders)}")
        for rem in reminders[:5]:
            if not isinstance(rem, dict):
                continue
            lines.append(
                "  - {name} (id {rid}): {pct}% used".format(
                    name=rem.get("name", "—"),
                    rid=rem.get("id", "—"),
                    pct=rem.get("percent_used", "—"),
                )
            )
    if gear.get("notes"):
        lines.append(f"- **Notes**: {gear.get('notes')}")
    return "\n".join(lines)


def format_gear_recalc_result(result: Any) -> str:
    """Format the response from recalc-distance endpoint."""
    if isinstance(result, dict):
        if not result:
            return "Gear distance recalculation requested."
        # Often returns the updated gear object
        if "id" in result and ("distance" in result or "activities" in result):
            return (
                f"Gear {result.get('id')} recalculated — "
                f"distance: {_format_distance_m(result.get('distance'))}, "
                f"activities: {result.get('activities', '—')}, "
                f"time: {_format_time_s(result.get('time'))}."
            )
        return f"Gear recalculation result: {result}"
    if isinstance(result, list):
        return f"Gear recalculation result list ({len(result)} items)."
    return f"Gear recalculation result: {result}"


def format_gear_reminder_result(reminder: dict[str, Any]) -> str:
    """Format a created/updated reminder."""
    if not isinstance(reminder, dict):
        return "Reminder operation completed."
    rid = reminder.get("id", "—")
    name = reminder.get("name", "—")
    parts = [f"Reminder {rid} — {name}"]
    if reminder.get("distance") is not None:
        parts.append(f"distance threshold {_format_distance_m(reminder.get('distance'))}")
    if reminder.get("time") is not None:
        parts.append(f"time threshold {_format_time_s(reminder.get('time'))}")
    if reminder.get("days") is not None:
        parts.append(f"days threshold {reminder.get('days')}")
    if reminder.get("percent_used") is not None:
        parts.append(f"{reminder.get('percent_used')}% used")
    return " — ".join(parts) + "."


def format_csv_block(text: str, label: str) -> str:
    """Wrap raw CSV text in a markdown code block with a header."""
    return f"## {label}\n\n```csv\n{text.strip()}\n```"
