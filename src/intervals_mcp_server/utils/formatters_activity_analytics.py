"""
Markdown formatters for the per-activity analytics tools.

Self-contained on purpose: helpers (pace conversion, table rendering) are
duplicated rather than imported from `utils.formatting` so this module has
zero coupling with shared formatting during concurrent edits.

Response shapes were confirmed against the live Intervals.icu API
(GET /activity/{id}/...). Notable shapes:

- Curve responses (hr-curve, power-curve, pace-curve): single dict with
  parallel arrays ``secs``, ``bpm``/``watts``/``mps``, ``start_index``,
  ``end_index``. NOT a list of {duration,value,...} as some docs imply.
- ``power-curves`` (multi): list of those curve dicts.
- ``power-vs-hr``: dict with summary fields plus a ``series`` of
  ``{start, secs, movingSecs, watts, hr, cadence}`` buckets.
- Histograms (hr-histogram, power-histogram, gap-histogram, pace-histogram):
  list of ``{min, max, secs}``.
- ``time-at-hr``: dict with ``min_bpm``, ``max_bpm``, parallel arrays
  ``secs`` (per-bin) and ``cumulative_secs``.
- ``segments``: list of ``{id, start_index, end_index, name, segment_id,
  starred}``.
- ``best-efforts``: requires a ``stream`` query param at the API level;
  returns 422 if missing.
- ``interval-stats``: requires ``start_index``/``end_index`` query params;
  returns 422 if missing.
- ``map``: dict with ``bounds: [[lat,lng],[lat,lng]]`` and ``latlngs``.
- ``weather-summary``: dict; many fields are ``null`` for indoor activities.
- ``hr-load-model`` / ``power-spike-model``: small dicts.
"""

from __future__ import annotations

from typing import Any

# Cap how many rows we render in tables to keep MCP responses lean.
_MAX_TABLE_ROWS = 20


# ---------------------------------------------------------------------------
# Pace helpers (duplicated from utils.formatting on purpose)
# ---------------------------------------------------------------------------


def _ms_to_min_per_km(mps: float | None) -> str:
    """Convert pace in m/s to mm:ss/km for display."""
    if not mps:
        return "—"
    try:
        secs_per_km = 1000.0 / float(mps)
    except (TypeError, ValueError, ZeroDivisionError):
        return "—"
    m, s = divmod(int(round(secs_per_km)), 60)
    return f"{m}:{s:02d}/km"


def _fmt_secs(s: Any) -> str:
    """Format a seconds count as h:mm:ss / mm:ss / Ns."""
    try:
        n = int(round(float(s)))
    except (TypeError, ValueError):
        return str(s)
    if n < 60:
        return f"{n}s"
    if n < 3600:
        m, sec = divmod(n, 60)
        return f"{m}:{sec:02d}"
    h, rem = divmod(n, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}"


def _fmt_num(v: Any, suffix: str = "", default: str = "—") -> str:
    if v is None:
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f.is_integer():
        return f"{int(f)}{suffix}"
    return f"{f:.2f}{suffix}"


# ---------------------------------------------------------------------------
# CSV passthrough
# ---------------------------------------------------------------------------


def format_csv_block(csv_text: str, title: str) -> str:
    """Wrap a CSV body in a fenced markdown block with a header line."""
    if not csv_text:
        return f"{title}: no CSV data."
    text = csv_text.lstrip("﻿")
    line_count = text.count("\n")
    return f"## {title}\n({line_count} lines, raw CSV)\n\n```csv\n{text}\n```"


# ---------------------------------------------------------------------------
# Curve formatters
# ---------------------------------------------------------------------------


def _format_curve_dict(curve: dict[str, Any], value_key: str, value_label: str, unit: str) -> str:
    """Format a single curve dict (hr/power/pace) as a sampled table."""
    secs = curve.get("secs") or []
    values = curve.get(value_key) or []
    start_idx = curve.get("start_index") or []
    end_idx = curve.get("end_index") or []
    n = min(len(secs), len(values))
    if n == 0:
        return "No curve data."

    # Sample down to a reasonable number of representative durations.
    # Pick a spread of durations including the standard ones if present.
    targets = [1, 5, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600, 5400]
    sampled_indices: list[int] = []
    secs_lookup = {int(s): i for i, s in enumerate(secs[:n]) if s is not None}
    for t in targets:
        if t in secs_lookup:
            sampled_indices.append(secs_lookup[t])
    # If we got few hits, fall back to evenly spaced.
    if len(sampled_indices) < 5:
        step = max(1, n // 12)
        sampled_indices = list(range(0, n, step))[:_MAX_TABLE_ROWS]

    lines: list[str] = []
    weight = curve.get("weight")
    header_extra = []
    if weight is not None:
        header_extra.append(f"weight {weight} kg")
    if curve.get("training_load") is not None:
        header_extra.append(f"training_load {curve['training_load']}")
    extra = f" — {', '.join(header_extra)}" if header_extra else ""
    lines.append(f"## {value_label} curve (id {curve.get('id', '—')}){extra}")
    lines.append(f"({n} duration buckets)")
    lines.append("")
    lines.append(f"| Duration | {value_label} ({unit}) | start_index | end_index |")
    lines.append("|---|---|---|---|")
    for i in sampled_indices:
        try:
            sec = secs[i]
        except IndexError:
            continue
        val = values[i] if i < len(values) else None
        si = start_idx[i] if i < len(start_idx) else "—"
        ei = end_idx[i] if i < len(end_idx) else "—"
        lines.append(f"| {_fmt_secs(sec)} | {_fmt_num(val)} | {si} | {ei} |")
    return "\n".join(lines)


def format_hr_curve(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "No HR curve data."
    return _format_curve_dict(payload, value_key="bpm", value_label="HR", unit="bpm")


def format_power_curve(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "No power curve data."
    return _format_curve_dict(payload, value_key="watts", value_label="Power", unit="W")


def format_pace_curve(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "No pace curve data."
    # Pace curves use mps; convert to min/km in a custom render.
    secs = payload.get("secs") or []
    mps = payload.get("mps") or payload.get("values") or []
    n = min(len(secs), len(mps))
    if n == 0:
        return "No pace curve data."
    targets = [1, 5, 15, 30, 60, 120, 300, 600, 1200, 1800, 3600]
    secs_lookup = {int(s): i for i, s in enumerate(secs[:n]) if s is not None}
    indices = [secs_lookup[t] for t in targets if t in secs_lookup]
    if len(indices) < 5:
        step = max(1, n // 12)
        indices = list(range(0, n, step))[:_MAX_TABLE_ROWS]

    lines: list[str] = [
        f"## Pace curve (id {payload.get('id', '—')})",
        f"({n} duration buckets)",
        "",
        "| Duration | Pace (m/s) | Pace (min/km) |",
        "|---|---|---|",
    ]
    for i in indices:
        sec = secs[i]
        v = mps[i] if i < len(mps) else None
        lines.append(f"| {_fmt_secs(sec)} | {_fmt_num(v)} | {_ms_to_min_per_km(v) if v else '—'} |")
    return "\n".join(lines)


def format_power_curves_multi(payload: Any) -> str:
    """Format a list of power curves (multistream / faceted)."""
    if not isinstance(payload, list) or not payload:
        return "No multistream power curves."
    parts: list[str] = [f"## Power curves — {len(payload)} stream(s)", ""]
    for curve in payload[:6]:  # cap to keep response lean
        if not isinstance(curve, dict):
            continue
        label = curve.get("label") or curve.get("filter_label") or "(no label)"
        parts.append(f"### Stream: {label}")
        parts.append(_format_curve_dict(curve, value_key="watts", value_label="Power", unit="W"))
        parts.append("")
    if len(payload) > 6:
        parts.append(f"... ({len(payload) - 6} more streams omitted)")
    return "\n".join(parts)


def format_power_vs_hr(payload: Any) -> str:
    """Format power-vs-hr summary + bucket series."""
    if not isinstance(payload, dict):
        return "No power-vs-HR data."
    lines: list[str] = ["## Power vs HR"]
    summary_keys = [
        ("powerHr", "Power/HR ratio"),
        ("powerHrFirst", "First-half ratio"),
        ("powerHrSecond", "Second-half ratio"),
        ("decoupling", "Decoupling"),
        ("powerHrZ2", "Z2 power/HR"),
        ("hrLag", "HR lag (s)"),
        ("bucketSize", "Bucket size (s)"),
        ("warmup", "Warmup (s)"),
        ("cooldown", "Cooldown (s)"),
        ("elapsedTime", "Elapsed (s)"),
    ]
    for key, label in summary_keys:
        if key in payload and payload[key] is not None:
            lines.append(f"- **{label}**: {_fmt_num(payload[key])}")

    series = payload.get("series") or []
    if isinstance(series, list) and series:
        lines.append("")
        lines.append(f"### Buckets ({len(series)})")
        lines.append("| Start (s) | Duration | Watts | HR | Cadence |")
        lines.append("|---|---|---|---|---|")
        for b in series[:_MAX_TABLE_ROWS]:
            if not isinstance(b, dict):
                continue
            lines.append(
                "| {st} | {sec} | {w} | {hr} | {c} |".format(
                    st=_fmt_num(b.get("start")),
                    sec=_fmt_secs(b.get("secs", 0)),
                    w=_fmt_num(b.get("watts")),
                    hr=_fmt_num(b.get("hr")),
                    c=_fmt_num(b.get("cadence")),
                )
            )
        if len(series) > _MAX_TABLE_ROWS:
            lines.append(f"... ({len(series) - _MAX_TABLE_ROWS} more buckets)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Histogram formatters
# ---------------------------------------------------------------------------


def _format_histogram(payload: Any, value_label: str, bin_unit: str, value_unit: str = "s") -> str:
    """Format a list of {min,max,secs} histogram bins."""
    if payload is None:
        return f"No {value_label.lower()} histogram data."
    if not isinstance(payload, list):
        return f"Invalid {value_label.lower()} histogram payload."
    if not payload:
        return f"No {value_label.lower()} histogram data (empty)."

    total_secs = 0
    for b in payload:
        if isinstance(b, dict):
            try:
                total_secs += int(b.get("secs") or 0)
            except (TypeError, ValueError):
                pass

    lines: list[str] = [
        f"## {value_label} histogram",
        f"({len(payload)} bins, total {_fmt_secs(total_secs)} accumulated)",
        "",
        f"| Bin ({bin_unit}) | Time | % |",
        "|---|---|---|",
    ]
    for b in payload[:_MAX_TABLE_ROWS]:
        if not isinstance(b, dict):
            continue
        lo = b.get("min")
        hi = b.get("max")
        secs = b.get("secs") or 0
        pct = (secs / total_secs * 100.0) if total_secs else 0.0
        lines.append(f"| {_fmt_num(lo)}–{_fmt_num(hi)} | {_fmt_secs(secs)} | {pct:.1f}% |")
    if len(payload) > _MAX_TABLE_ROWS:
        lines.append(f"... ({len(payload) - _MAX_TABLE_ROWS} more bins)")
    return "\n".join(lines)


def format_hr_histogram(payload: Any) -> str:
    return _format_histogram(payload, "HR", "bpm")


def format_power_histogram(payload: Any) -> str:
    return _format_histogram(payload, "Power", "W")


def format_pace_histogram(payload: Any) -> str:
    return _format_histogram(payload, "Pace", "m/s")


def format_gap_histogram(payload: Any) -> str:
    return _format_histogram(payload, "Grade-adjusted pace", "m/s")


def format_time_at_hr(payload: Any) -> str:
    """time-at-hr returns parallel arrays + min/max bpm."""
    if not isinstance(payload, dict):
        return "No time-at-HR data."
    secs = payload.get("secs") or []
    cum = payload.get("cumulative_secs") or []
    min_bpm = payload.get("min_bpm")
    max_bpm = payload.get("max_bpm")
    if not isinstance(secs, list) or not secs:
        return "No time-at-HR data (empty)."

    lines: list[str] = [
        "## Time at HR",
        f"- **HR range**: {_fmt_num(min_bpm)} – {_fmt_num(max_bpm)} bpm",
        f"- **Bins**: {len(secs)}",
        "",
        "| HR (bpm) | Time | Cumulative |",
        "|---|---|---|",
    ]
    try:
        start_bpm = int(min_bpm) if min_bpm is not None else 0
    except (TypeError, ValueError):
        start_bpm = 0
    for i, s in enumerate(secs[:_MAX_TABLE_ROWS]):
        bpm = start_bpm + i
        c = cum[i] if i < len(cum) else None
        lines.append(f"| {bpm} | {_fmt_secs(s)} | {_fmt_secs(c) if c is not None else '—'} |")
    if len(secs) > _MAX_TABLE_ROWS:
        lines.append(f"... ({len(secs) - _MAX_TABLE_ROWS} more bins)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Model formatters
# ---------------------------------------------------------------------------


def format_hr_load_model(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "No HR load model data."
    lines = ["## HR load model"]
    label_map = [
        ("type", "Model type"),
        ("icu_training_load", "ICU training load"),
        ("resting_hr", "Resting HR (bpm)"),
        ("lt_hr", "Lactate threshold HR (bpm)"),
        ("max_hr", "Max HR (bpm)"),
        ("rSquared", "R²"),
        ("trainingDataCount", "Training data count"),
    ]
    for key, label in label_map:
        if key in payload:
            lines.append(f"- **{label}**: {_fmt_num(payload[key])}")
    data = payload.get("data")
    if isinstance(data, list):
        lines.append(f"- **Fit data points**: {len(data)}")
    return "\n".join(lines)


def format_power_spike_model(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "No power spike model data."
    lines = ["## Power spike model"]
    label_map = [
        ("type", "Model type"),
        ("criticalPower", "Critical power (W)"),
        ("wPrime", "W' (J)"),
        ("pMax", "P-max (W)"),
        ("ftp", "FTP (W)"),
    ]
    for key, label in label_map:
        if key in payload:
            lines.append(f"- **{label}**: {_fmt_num(payload[key])}")
    spikes = payload.get("inputPointIndexes")
    if isinstance(spikes, list):
        preview = ", ".join(str(s) for s in spikes[:10])
        more = f" ... (+{len(spikes) - 10} more)" if len(spikes) > 10 else ""
        lines.append(f"- **Input point indexes ({len(spikes)})**: {preview}{more}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Interval-stats / segments / best-efforts
# ---------------------------------------------------------------------------


def format_interval_stats(payload: Any) -> str:
    """Format interval stats; mirror format_intervals from upstream."""
    if payload is None:
        return "No interval stats."
    # The endpoint may return a dict with icu_intervals, or a bare list.
    intervals: list[dict[str, Any]]
    if isinstance(payload, dict):
        intervals = payload.get("icu_intervals") or payload.get("intervals") or []
        if not intervals and any(k in payload for k in ("average_watts", "average_heartrate")):
            # Single interval object.
            intervals = [payload]
    elif isinstance(payload, list):
        intervals = payload
    else:
        return "Invalid interval-stats payload."

    if not intervals:
        return "No interval stats."

    lines: list[str] = [f"## Interval stats ({len(intervals)})"]
    lines.append("")
    lines.append("| # | Label | Type | Duration | Distance | Avg W | Max W | Avg HR | Max HR |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for i, interval in enumerate(intervals[:_MAX_TABLE_ROWS], 1):
        if not isinstance(interval, dict):
            continue
        lines.append(
            "| {n} | {label} | {type} | {dur} | {dist} m | {aw} | {mw} | {ah} | {mh} |".format(
                n=i,
                label=interval.get("label") or f"Interval {i}",
                type=interval.get("type", "—"),
                dur=_fmt_secs(interval.get("elapsed_time") or interval.get("moving_time") or 0),
                dist=_fmt_num(interval.get("distance"), default="—"),
                aw=_fmt_num(interval.get("average_watts")),
                mw=_fmt_num(interval.get("max_watts")),
                ah=_fmt_num(interval.get("average_heartrate")),
                mh=_fmt_num(interval.get("max_heartrate")),
            )
        )
    if len(intervals) > _MAX_TABLE_ROWS:
        lines.append(f"... ({len(intervals) - _MAX_TABLE_ROWS} more)")
    return "\n".join(lines)


def format_segments(payload: Any) -> str:
    if payload is None:
        return "No segment efforts."
    if not isinstance(payload, list):
        return "Invalid segments payload."
    if not payload:
        return "No segment efforts found."

    lines = [f"## Segment efforts ({len(payload)})", ""]
    lines.append("| ID | Name | Segment ID | start_index | end_index | Starred |")
    lines.append("|---|---|---|---|---|---|")
    for s in payload[:_MAX_TABLE_ROWS]:
        if not isinstance(s, dict):
            continue
        lines.append(
            "| {id} | {name} | {sid} | {si} | {ei} | {star} |".format(
                id=s.get("id", "—"),
                name=s.get("name", "—"),
                sid=s.get("segment_id", "—"),
                si=s.get("start_index", "—"),
                ei=s.get("end_index", "—"),
                star="yes" if s.get("starred") else "no",
            )
        )
    if len(payload) > _MAX_TABLE_ROWS:
        lines.append(f"... ({len(payload) - _MAX_TABLE_ROWS} more)")
    return "\n".join(lines)


def format_best_efforts(payload: Any, stream: str | None = None) -> str:
    """
    Render the response from `GET /activity/{id}/best-efforts`.

    The live OpenAPI `Effort` schema (verified 2026-04-27) is:
    `{ start_index: int, end_index: int, average: float,
       duration: int (seconds), distance: float (meters) }`
    Wrapped in `{ "efforts": [Effort, ...] }`.

    `average`'s units depend on the queried `stream`:
    - `watts` → W   (cycling power)
    - `heartrate` → bpm
    - `pace` → m/s  (we display as min/km in addition for legibility)
    - `cadence` → rpm
    - `velocity_smooth` → m/s

    The earlier formatter expected `type` / `value` / `watts` / `bpm` /
    `activity_id` / `time_ago` — none of which the API returns. Fixed here.

    Args:
        payload: Raw API response. Either a dict with `efforts` key, or
            a bare list (defensive — earlier intervals.icu versions returned
            the bare list).
        stream: Optional. The stream name passed to `find_best_efforts`
            (`watts`, `heartrate`, `pace`, etc.). Used to label units.
            If omitted, the formatter falls back to a generic header.
    """
    if payload is None:
        return "No best-effort data."
    if isinstance(payload, dict):
        items = payload.get("efforts") or payload.get("data") or []
    elif isinstance(payload, list):
        items = payload
    else:
        return "Invalid best-efforts payload."

    if not items:
        return "No best-effort data."

    # Pick the unit label for the `average` column based on the stream.
    stream_norm = (stream or "").strip().lower()
    unit_map = {
        "watts": "W",
        "power": "W",
        "heartrate": "bpm",
        "hr": "bpm",
        "cadence": "rpm",
        "pace": "m/s",
        "velocity_smooth": "m/s",
        "speed": "m/s",
    }
    unit = unit_map.get(stream_norm, "")
    avg_label = f"Avg ({unit})" if unit else "Avg"
    stream_label = stream or "stream"

    lines = [f"## Best efforts — {stream_label} ({len(items)})", ""]
    lines.append(f"| Duration | Distance (m) | {avg_label} | Start idx | End idx |")
    lines.append("|---|---|---|---|---|")
    for e in items[:_MAX_TABLE_ROWS]:
        if not isinstance(e, dict):
            continue
        duration = e.get("duration")
        distance = e.get("distance")
        average = e.get("average")
        start_idx = e.get("start_index")
        end_idx = e.get("end_index")
        lines.append(
            "| {d} | {dist} | {avg} | {si} | {ei} |".format(
                d=_fmt_secs(duration) if duration is not None else "—",
                dist=_fmt_num(distance) if distance is not None else "—",
                avg=_fmt_num(average) if average is not None else "—",
                si=start_idx if start_idx is not None else "—",
                ei=end_idx if end_idx is not None else "—",
            )
        )
    if len(items) > _MAX_TABLE_ROWS:
        lines.append(f"... ({len(items) - _MAX_TABLE_ROWS} more)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Map / weather
# ---------------------------------------------------------------------------


def format_activity_map(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "No map data."
    bounds = payload.get("bounds")
    latlngs = payload.get("latlngs") or payload.get("polyline") or []
    lines = ["## Activity map"]
    if isinstance(bounds, list) and len(bounds) == 2:
        try:
            sw, ne = bounds
            lines.append(f"- **Bounds (SW)**: {sw[0]:.5f}, {sw[1]:.5f}")
            lines.append(f"- **Bounds (NE)**: {ne[0]:.5f}, {ne[1]:.5f}")
        except (TypeError, IndexError, ValueError):
            lines.append(f"- **Bounds**: {bounds}")
    if isinstance(latlngs, list):
        lines.append(f"- **Coordinate points**: {len(latlngs)}")
        if latlngs:
            try:
                first = latlngs[0]
                last = latlngs[-1]
                lines.append(f"- **First point**: {first[0]:.5f}, {first[1]:.5f}")
                lines.append(f"- **Last point**: {last[0]:.5f}, {last[1]:.5f}")
            except (TypeError, IndexError, ValueError):
                pass
    elif isinstance(latlngs, str):
        lines.append(f"- **Encoded polyline**: {len(latlngs)} chars")
    lines.append("")
    lines.append("_Use Claude's plotting tools to visualize the route._")
    return "\n".join(lines)


def format_weather_summary(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "No weather summary."
    label_map = [
        ("average_temp", "Avg device temp", "°C"),
        ("min_temp", "Min temp", "°C"),
        ("max_temp", "Max temp", "°C"),
        ("average_weather_temp", "Avg weather temp", "°C"),
        ("min_weather_temp", "Min weather temp", "°C"),
        ("max_weather_temp", "Max weather temp", "°C"),
        ("average_feels_like", "Avg feels-like", "°C"),
        ("min_feels_like", "Min feels-like", "°C"),
        ("max_feels_like", "Max feels-like", "°C"),
        ("average_wind_speed", "Avg wind", " m/s"),
        ("min_wind_speed", "Min wind", " m/s"),
        ("max_wind_speed", "Max wind", " m/s"),
        ("wind_speed", "Wind", " m/s"),
        ("wind_gust", "Wind gust", " m/s"),
        ("apparent_wind_speed", "Apparent wind", " m/s"),
        ("apparent_wind_gust", "Apparent gust", " m/s"),
        ("prevailing_wind_deg", "Prevailing wind", "°"),
        ("headwind_percent", "Headwind", "%"),
        ("tailwind_percent", "Tailwind", "%"),
        ("crosswind_percent", "Crosswind", "%"),
        ("average_humidity", "Avg humidity", "%"),
        ("conditions", "Conditions", ""),
    ]
    lines = ["## Weather summary"]
    rendered_any = False
    for key, label, unit in label_map:
        if key in payload and payload[key] is not None:
            v = payload[key]
            if isinstance(v, (int, float)):
                lines.append(f"- **{label}**: {_fmt_num(v)}{unit}")
            else:
                lines.append(f"- **{label}**: {v}{unit}")
            rendered_any = True
    moving_time = payload.get("moving_time")
    if moving_time:
        lines.append(f"- **Moving time covered**: {_fmt_secs(moving_time)}")
        rendered_any = True
    if not rendered_any:
        lines.append("- (All weather fields null — likely an indoor activity.)")
    return "\n".join(lines)
