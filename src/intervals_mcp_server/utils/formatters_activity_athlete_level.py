"""
Markdown formatters for athlete-level activity tools.

Self-contained on purpose: helpers (date / pace / power formatting) are
duplicated locally so this module has zero coupling with shared formatting
during concurrent edits.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Local helpers (duplicated from utils.formatting on purpose)
# ---------------------------------------------------------------------------


def _fmt_date(value: Any) -> str:
    """Format an ISO-style date/datetime to YYYY-MM-DD HH:MM if datetime, else YYYY-MM-DD."""
    if not value or not isinstance(value, str):
        return "—"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if "T" in value or " " in value:
            return dt.strftime("%Y-%m-%d %H:%M")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return value[:19]


def _fmt_distance_km(meters: Any) -> str:
    """Format meters as km with one decimal."""
    if meters is None:
        return "—"
    try:
        return f"{float(meters) / 1000.0:.1f} km"
    except (TypeError, ValueError):
        return "—"


def _fmt_duration_hms(seconds: Any) -> str:
    """Format seconds as H:MM:SS."""
    if seconds is None:
        return "—"
    try:
        total = int(round(float(seconds)))
    except (TypeError, ValueError):
        return "—"
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _fmt_num(value: Any, decimals: int = 0) -> str:
    if value is None:
        return "—"
    try:
        if decimals == 0:
            return f"{int(round(float(value)))}"
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


# ---------------------------------------------------------------------------
# Activities tables
# ---------------------------------------------------------------------------


def format_activities_summary(activities: list[dict[str, Any]] | Any) -> str:
    """Markdown table summarizing a list of activities."""
    if not activities or not isinstance(activities, list):
        return "No activities found."

    lines = [
        f"## Activities ({len(activities)})",
        "",
        "| Date | Type | Name | Duration | Distance | TSS | IF |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for a in activities:
        if not isinstance(a, dict):
            continue
        date = _fmt_date(a.get("start_date_local") or a.get("start_date"))
        atype = a.get("type") or "—"
        name = (a.get("name") or "—").replace("|", "/")
        duration = _fmt_duration_hms(a.get("moving_time") or a.get("elapsed_time"))
        distance = _fmt_distance_km(a.get("distance") or a.get("icu_distance"))
        tss = _fmt_num(a.get("icu_training_load"))
        intensity = a.get("icu_intensity")
        if intensity is None:
            iff = "—"
        else:
            try:
                iff = f"{float(intensity):.2f}"
            except (TypeError, ValueError):
                iff = "—"
        lines.append(f"| {date} | {atype} | {name} | {duration} | {distance} | {tss} | {iff} |")
    return "\n".join(lines)


def format_activities_csv(text: str | Any) -> str:
    """Wrap raw CSV text in a fenced code block."""
    if text is None or not isinstance(text, str):
        return "No CSV data returned."
    if not text.strip():
        return "Empty CSV response."
    return "```csv\n" + text.rstrip() + "\n```"


# ---------------------------------------------------------------------------
# Search results
# ---------------------------------------------------------------------------


def format_search_results(results: list[dict[str, Any]] | Any, summary: bool = True) -> str:
    """Markdown table for /activities/search and /activities/search-full."""
    if not results or not isinstance(results, list):
        return "No matching activities found."

    title = "Search results (summary)" if summary else "Search results (full)"
    lines = [
        f"## {title} ({len(results)})",
        "",
        "| Date | Type | Name | Distance | Duration |",
        "| --- | --- | --- | --- | --- |",
    ]
    for a in results:
        if not isinstance(a, dict):
            continue
        date = _fmt_date(a.get("start_date_local") or a.get("start_date"))
        atype = a.get("type") or "—"
        name = (a.get("name") or "—").replace("|", "/")
        distance = _fmt_distance_km(a.get("distance"))
        duration = _fmt_duration_hms(a.get("moving_time") or a.get("elapsed_time"))
        lines.append(f"| {date} | {atype} | {name} | {distance} | {duration} |")
    return "\n".join(lines)


def format_interval_search_results(results: list[dict[str, Any]] | Any) -> str:
    """Markdown table of intervals matched by interval-search, with their parent activity."""
    if not results or not isinstance(results, list):
        return "No matching intervals found."

    lines = [
        f"## Interval matches ({len(results)})",
        "",
        "| Activity date | Activity | Type | Interval | Duration | Avg power | Avg HR |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in results:
        if not isinstance(entry, dict):
            continue
        # Each entry is typically an activity dict containing an `intervals`
        # list, but the API also flattens to interval-with-activity records.
        # Handle both shapes.
        intervals = entry.get("intervals")
        if isinstance(intervals, list) and intervals:
            base_date = _fmt_date(entry.get("start_date_local") or entry.get("start_date"))
            base_name = (entry.get("name") or "—").replace("|", "/")
            base_type = entry.get("type") or "—"
            for iv in intervals:
                if not isinstance(iv, dict):
                    continue
                iv_name = (iv.get("name") or iv.get("label") or "—").replace("|", "/")
                duration = _fmt_duration_hms(iv.get("moving_time") or iv.get("elapsed_time"))
                power = _fmt_num(iv.get("average_watts") or iv.get("avg_watts"))
                hr = _fmt_num(iv.get("average_heartrate") or iv.get("avg_hr"))
                lines.append(
                    f"| {base_date} | {base_name} | {base_type} | {iv_name} | "
                    f"{duration} | {power} | {hr} |"
                )
        else:
            # Flat shape — interval fields directly on the entry
            date = _fmt_date(entry.get("start_date_local") or entry.get("start_date"))
            name = (entry.get("activity_name") or entry.get("name") or "—").replace("|", "/")
            atype = entry.get("type") or "—"
            iv_name = (entry.get("interval_name") or entry.get("label") or "—").replace("|", "/")
            duration = _fmt_duration_hms(entry.get("moving_time") or entry.get("elapsed_time"))
            power = _fmt_num(entry.get("average_watts") or entry.get("avg_watts"))
            hr = _fmt_num(entry.get("average_heartrate") or entry.get("avg_hr"))
            lines.append(f"| {date} | {name} | {atype} | {iv_name} | {duration} | {power} | {hr} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def format_activity_tags(tags: list[Any] | Any) -> str:
    """Bullet list of activity tags."""
    if tags is None:
        return "No activity tags."
    if not isinstance(tags, list):
        return "Unexpected response: activity tags was not a list."
    if not tags:
        return "No activity tags applied yet."

    lines = ["## Activity tags", ""]
    for t in tags:
        if isinstance(t, str):
            lines.append(f"- {t}")
        elif isinstance(t, dict):
            label = t.get("name") or t.get("tag") or t.get("id") or "—"
            count = t.get("count")
            if count is not None:
                lines.append(f"- {label} ({count})")
            else:
                lines.append(f"- {label}")
        else:
            lines.append(f"- {t}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Curve aggregation
# ---------------------------------------------------------------------------


_CURVE_FEATURE_DURATIONS = [5, 30, 60, 300, 1200, 3600]
_CURVE_FEATURE_DISTANCES = [100, 400, 1000, 5000, 10000, 21097]


def _extract_curve_lists(curve: dict[str, Any]) -> tuple[list[Any], list[Any], str]:
    """Pull (x_values, y_values, x_label) from a single curve dict.

    intervals.icu uses different shapes per kind: pace curves have ``meters``,
    HR/power curves have ``secs``.
    """
    if "secs" in curve:
        return curve.get("secs") or [], curve.get("values") or [], "Duration"
    if "meters" in curve:
        return curve.get("meters") or [], curve.get("values") or [], "Distance"
    return curve.get("x") or [], curve.get("y") or curve.get("values") or [], "Index"


def _format_x(x_label: str, x: Any) -> str:
    """Format the x-axis tick depending on whether it's seconds or meters."""
    if x_label == "Duration":
        return _fmt_duration_hms(x)
    if x_label == "Distance":
        try:
            v = float(x)
        except (TypeError, ValueError):
            return "—"
        if v >= 1000:
            return f"{v / 1000.0:.2f} km"
        return f"{int(round(v))} m"
    return str(x)


def format_curve_aggregation(curves: list[dict[str, Any]] | dict[str, Any] | Any) -> str:
    """Format athlete- or activity-level curves as a top-entries table per series."""
    if curves is None:
        return "No curve data returned."

    series: list[dict[str, Any]] = []
    if isinstance(curves, dict):
        # Activity-level shape: {"secs": [...], "curves": [{...}, ...]} or single curve dict
        if "list" in curves and isinstance(curves["list"], list):
            series = [s for s in curves["list"] if isinstance(s, dict)]
        elif "curves" in curves and isinstance(curves["curves"], list):
            # Wrap each per-activity curve and reuse the parent x-axis (secs).
            x = curves.get("secs") or curves.get("meters")
            x_key = "secs" if "secs" in curves else "meters"
            for c in curves["curves"]:
                if not isinstance(c, dict):
                    continue
                series.append({**c, x_key: x, "label": c.get("id") or c.get("label")})
        else:
            series = [curves]
    elif isinstance(curves, list):
        series = [s for s in curves if isinstance(s, dict)]
    else:
        return "Unexpected response: curve data was not a list or dict."

    if not series:
        return "No curve data returned."

    out: list[str] = [f"## Curve aggregation ({len(series)} series)", ""]
    for s in series:
        label = s.get("label") or s.get("id") or s.get("name") or "—"
        x_vals, y_vals, x_label = _extract_curve_lists(s)
        if not x_vals or not y_vals:
            out.append(f"### {label}")
            out.append("(no points)")
            out.append("")
            continue
        # Pick feature buckets — duration or distance — and report best at each.
        features = _CURVE_FEATURE_DURATIONS if x_label == "Duration" else _CURVE_FEATURE_DISTANCES
        out.append(f"### {label}")
        out.append("")
        out.append(f"| {x_label} | Best |")
        out.append("| --- | --- |")
        # Find the closest x in the series for each feature value.
        for feat in features:
            best_idx = None
            best_diff = None
            for i, x in enumerate(x_vals):
                try:
                    diff = abs(float(x) - float(feat))
                except (TypeError, ValueError):
                    continue
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_idx = i
            if best_idx is None:
                continue
            actual_x = x_vals[best_idx]
            try:
                y = y_vals[best_idx]
            except IndexError:
                continue
            out.append(f"| {_format_x(x_label, actual_x)} | {_fmt_num(y)} |")
        out.append("")
    return "\n".join(out).rstrip()


def format_power_hr_curve(data: list[Any] | dict[str, Any] | Any) -> str:
    """Format power-vs-HR aggregated data."""
    if data is None:
        return "No power-vs-HR data."

    if isinstance(data, dict):
        bpm = data.get("bpm") or []
        cadence = data.get("cadence") or []
        minutes = data.get("minutes") or []
        min_w = data.get("minWatts")
        bucket = data.get("bucketSize") or data.get("bucket_size")
        ftp = data.get("ftp")
        lthr = data.get("lthr")
        if not bpm:
            return "No power-vs-HR data."
        rows = [
            f"## Power vs HR (bucket {bucket} W, FTP {ftp}, LTHR {lthr})",
            "",
            "| Watts (low) | Avg HR (bpm) | Avg cadence | Minutes |",
            "| --- | --- | --- | --- |",
        ]
        try:
            base = int(min_w) if min_w is not None else 0
            step = int(bucket) if bucket is not None else 5
        except (TypeError, ValueError):
            base, step = 0, 5
        for i, hr in enumerate(bpm):
            mins = minutes[i] if i < len(minutes) else 0
            cad = cadence[i] if i < len(cadence) else 0
            if not hr and not mins:
                continue
            rows.append(
                f"| {base + i * step} | {_fmt_num(hr)} | {_fmt_num(cad)} | {_fmt_num(mins)} |"
            )
        return "\n".join(rows)

    if isinstance(data, list):
        if not data:
            return "No power-vs-HR data."
        rows = [
            f"## Power vs HR ({len(data)} points)",
            "",
            "| Watts | HR (bpm) |",
            "| --- | --- |",
        ]
        for p in data:
            if isinstance(p, dict):
                rows.append(
                    f"| {_fmt_num(p.get('watts'))} | {_fmt_num(p.get('bpm') or p.get('hr'))} |"
                )
            elif isinstance(p, list) and len(p) >= 2:
                rows.append(f"| {_fmt_num(p[0])} | {_fmt_num(p[1])} |")
        return "\n".join(rows)

    return "Unexpected response shape for power-vs-HR data."


# ---------------------------------------------------------------------------
# MMP model
# ---------------------------------------------------------------------------


def format_mmp_model(model: dict[str, Any] | Any) -> str:
    """Format the athlete's power model (FFT / CP / W' / pMax / eFTP)."""
    if not model:
        return "No MMP model available."
    if not isinstance(model, dict):
        return "Unexpected response: MMP model was not a dict."

    mtype = model.get("type") or "—"
    cp = model.get("criticalPower")
    wprime = model.get("wPrime")
    pmax = model.get("pMax")
    ftp = model.get("ftp")
    inputs = model.get("inputPointIndexes")

    lines = [
        "## MMP power model",
        "",
        f"- Type: **{mtype}**",
        f"- Critical Power (CP): {_fmt_num(cp)} W",
        f"- W' (anaerobic capacity): {_fmt_num(wprime)} J",
        f"- pMax (max sprint power): {_fmt_num(pmax)} W",
        f"- e-FTP (estimated FTP from model): {_fmt_num(ftp)} W",
    ]
    if inputs:
        lines.append(f"- Input point indexes: {inputs}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Manual activity create
# ---------------------------------------------------------------------------


def format_manual_activity_result(activity: dict[str, Any] | Any) -> str:
    """Confirmation card for a created manual activity."""
    if not isinstance(activity, dict):
        return "Manual activity created."
    aid = activity.get("id", "—")
    name = activity.get("name", "—")
    atype = activity.get("type", "—")
    date = _fmt_date(activity.get("start_date_local") or activity.get("start_date"))
    duration = _fmt_duration_hms(activity.get("moving_time"))
    distance = _fmt_distance_km(activity.get("distance"))
    tss = _fmt_num(activity.get("icu_training_load"))
    return (
        f"## Manual activity created\n\n"
        f"- ID: **{aid}**\n"
        f"- Name: {name}\n"
        f"- Type: {atype}\n"
        f"- Start: {date}\n"
        f"- Duration: {duration}\n"
        f"- Distance: {distance}\n"
        f"- TSS: {tss}"
    )


def format_bulk_manual_result(activities: list[dict[str, Any]] | Any) -> str:
    """Markdown table summarizing a bulk manual-activity create response."""
    if not activities:
        return "No manual activities created."
    if not isinstance(activities, list):
        return "Bulk manual activities upserted."

    lines = [
        f"## Bulk manual activities ({len(activities)})",
        "",
        "| ID | Date | Type | Name | Duration | Distance |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for a in activities:
        if not isinstance(a, dict):
            continue
        aid = a.get("id", "—")
        date = _fmt_date(a.get("start_date_local") or a.get("start_date"))
        atype = a.get("type") or "—"
        name = (a.get("name") or "—").replace("|", "/")
        duration = _fmt_duration_hms(a.get("moving_time"))
        distance = _fmt_distance_km(a.get("distance"))
        lines.append(f"| {aid} | {date} | {atype} | {name} | {duration} | {distance} |")
    return "\n".join(lines)
