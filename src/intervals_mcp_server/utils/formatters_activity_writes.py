"""
Formatters for activity-write MCP tools.

These render markdown summaries for the activity / interval mutation tools
in `tools/activity_writes.py`. The interval rendering logic is intentionally
duplicated here (rather than imported from `utils/formatting.py.format_intervals`)
to keep the write-tool surface decoupled from the read-tool formatter — Wave 3B
only needs the per-interval card and a list-table view, not the wrapping
"Intervals Analysis" header.
"""

from __future__ import annotations

import json
from typing import Any


# ---------------------------------------------------------------------------
# Activity update / delete
# ---------------------------------------------------------------------------


def format_activity_update_result(activity: dict[str, Any]) -> str:
    """Render a confirmation card for a successful activity update.

    Echoes the fields that came back (or were sent) so the caller can
    confirm the write took. Numeric fields cleared with the cookbook's
    sentinel `-1` are surfaced as `(cleared)`.
    """
    if not isinstance(activity, dict):
        return "Activity updated (no body returned)."

    activity_id = activity.get("id") or "—"
    name = activity.get("name") or "—"
    lines = [f"# Activity updated — {activity_id}", "", f"**Name**: {name}", ""]

    field_labels = [
        ("description", "Description"),
        ("commute", "Commute"),
        ("trainer", "Trainer"),
        ("race", "Race"),
        ("perceived_exertion", "Perceived exertion"),
        ("feel", "Feel"),
        ("icu_rpe", "RPE (icu)"),
        ("session_rpe", "Session RPE"),
        ("tags", "Tags"),
        ("gear", "Gear"),
    ]
    rows: list[str] = []
    for key, label in field_labels:
        if key not in activity:
            continue
        val = activity[key]
        if val == -1:
            rows.append(f"- **{label}**: (cleared)")
        elif isinstance(val, (dict, list)):
            rows.append(f"- **{label}**: {json.dumps(val)}")
        else:
            rows.append(f"- **{label}**: {val}")
    if rows:
        lines.append("## Fields written")
        lines.extend(rows)

    return "\n".join(lines)


def format_activity_delete_result(activity_id: str) -> str:
    """Simple confirmation for a delete-activity call."""
    return f"Deleted activity {activity_id}."


# ---------------------------------------------------------------------------
# Streams
# ---------------------------------------------------------------------------


def format_streams_update_result(
    result: Any, sent_streams: list[dict[str, Any]] | None = None
) -> str:
    """Confirmation for an activity-streams update.

    The intervals.icu API returns the updated stream list (or an empty body).
    Falls back to summarising what was sent when nothing comes back.
    """
    streams = result if isinstance(result, list) else (sent_streams or [])
    count = len(streams) if isinstance(streams, list) else 0

    lines = [f"# Activity streams updated — {count} stream(s)", ""]
    if not streams:
        return "Activity streams updated (no body returned)."

    lines.append("| Stream | Samples |")
    lines.append("|---|---|")
    for s in streams:
        if not isinstance(s, dict):
            continue
        name = s.get("type") or s.get("name") or "—"
        data = s.get("data")
        n = len(data) if isinstance(data, list) else "—"
        lines.append(f"| {name} | {n} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Intervals — per-interval rendering (duplicated from utils.formatting)
# ---------------------------------------------------------------------------


def _render_interval_card(interval: dict[str, Any], idx: int | None = None) -> str:
    """Per-interval markdown card.

    Mirrors the per-interval section emitted by
    `utils.formatting.format_intervals` for the icu_intervals list.
    """
    label = interval.get("label", f"Interval {idx}" if idx is not None else "Interval")
    type_ = interval.get("type", "Unknown")
    head = f"[{idx}] {label} ({type_})" if idx is not None else f"{label} ({type_})"

    return f"""{head}
Duration: {interval.get("elapsed_time", 0)} seconds (moving: {interval.get("moving_time", 0)} seconds)
Distance: {interval.get("distance", 0)} meters
Start-End Indices: {interval.get("start_index", 0)}-{interval.get("end_index", 0)}

Power Metrics:
  Average Power: {interval.get("average_watts", 0)} watts ({interval.get("average_watts_kg", 0)} W/kg)
  Max Power: {interval.get("max_watts", 0)} watts ({interval.get("max_watts_kg", 0)} W/kg)
  Weighted Avg Power: {interval.get("weighted_average_watts", 0)} watts
  Intensity: {interval.get("intensity", 0)}
  Training Load: {interval.get("training_load", 0)}
  Power Zone: {interval.get("zone", "N/A")} ({interval.get("zone_min_watts", 0)}-{interval.get("zone_max_watts", 0)} watts)
  W' Balance: Start {interval.get("wbal_start", 0)}, End {interval.get("wbal_end", 0)}

Heart Rate & Metabolic:
  Heart Rate: Avg {interval.get("average_heartrate", 0)}, Min {interval.get("min_heartrate", 0)}, Max {interval.get("max_heartrate", 0)} bpm
  Decoupling: {interval.get("decoupling", 0)}

Speed & Cadence:
  Speed: Avg {interval.get("average_speed", 0)}, Max {interval.get("max_speed", 0)} m/s
  Cadence: Avg {interval.get("average_cadence", 0)}, Max {interval.get("max_cadence", 0)} rpm
"""


def format_intervals_update_result(intervals: Any) -> str:
    """Render a table summary of all updated intervals.

    Surfaces label, type, duration, distance, and key power/HR metrics
    without the heavy per-card output.
    """
    if not isinstance(intervals, list) or not intervals:
        return "Intervals updated (no intervals returned)."

    lines = [f"# Intervals updated — {len(intervals)} interval(s)", ""]
    lines.append("| # | Label | Type | Duration (s) | Distance (m) | Avg W | Avg HR |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, iv in enumerate(intervals, 1):
        if not isinstance(iv, dict):
            continue
        lines.append(
            f"| {i} | {iv.get('label', '—')} | {iv.get('type', '—')} | "
            f"{iv.get('elapsed_time', 0)} | {iv.get('distance', 0)} | "
            f"{iv.get('average_watts', 0)} | {iv.get('average_heartrate', 0)} |"
        )
    return "\n".join(lines)


def format_single_interval_result(interval: Any) -> str:
    """Render a single interval as a detail card (full per-interval block)."""
    if not isinstance(interval, dict):
        return "Interval updated (no body returned)."
    return "# Interval updated\n\n" + _render_interval_card(interval)


def format_intervals_delete_result(result: Any, requested_count: int | None = None) -> str:
    """Confirmation for delete-intervals.

    The endpoint typically returns the *remaining* intervals after the
    deletion. We show how many came back and, when known, how many were
    requested for deletion.
    """
    remaining = len(result) if isinstance(result, list) else None
    lines = ["# Intervals deleted", ""]
    if requested_count is not None:
        lines.append(f"- Requested deletions: {requested_count}")
    if remaining is not None:
        lines.append(f"- Remaining intervals on activity: {remaining}")
    if remaining is None and requested_count is None:
        lines.append("(API returned no body)")
    return "\n".join(lines)


def format_split_interval_result(intervals: Any) -> str:
    """Confirmation for split-interval.

    The endpoint returns the new full interval list for the activity. We
    surface a header plus the same table as `format_intervals_update_result`.
    """
    if not isinstance(intervals, list) or not intervals:
        return "Interval split (no body returned)."

    lines = [f"# Interval split — activity now has {len(intervals)} interval(s)", ""]
    lines.append("| # | Label | Type | Duration (s) | Distance (m) | Avg W | Avg HR |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, iv in enumerate(intervals, 1):
        if not isinstance(iv, dict):
            continue
        lines.append(
            f"| {i} | {iv.get('label', '—')} | {iv.get('type', '—')} | "
            f"{iv.get('elapsed_time', 0)} | {iv.get('distance', 0)} | "
            f"{iv.get('average_watts', 0)} | {iv.get('average_heartrate', 0)} |"
        )
    return "\n".join(lines)
