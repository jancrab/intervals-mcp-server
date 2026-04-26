"""
Markdown formatters for the sport-settings tools.

Self-contained on purpose: pace conversions are duplicated from
`utils.formatting` so this module has zero coupling with shared formatting
during concurrent edits.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Local pace helpers (duplicated from utils.formatting on purpose)
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


def _ms_to_sec_per_100m(mps: float | None) -> str:
    """Convert pace in m/s to mm:ss/100m for swim display."""
    if not mps:
        return "—"
    try:
        secs_per_100m = 100.0 / float(mps)
    except (TypeError, ValueError, ZeroDivisionError):
        return "—"
    m, s = divmod(int(round(secs_per_100m)), 60)
    return f"{m}:{s:02d}/100m"


# ---------------------------------------------------------------------------
# Discipline classification
# ---------------------------------------------------------------------------

_RIDE_TYPES = {
    "Ride",
    "VirtualRide",
    "MountainBikeRide",
    "GravelRide",
    "TrackRide",
    "Cyclocross",
    "EBikeRide",
    "Handcycle",
    "Velomobile",
}
_RUN_TYPES = {"Run", "TrailRun", "VirtualRun", "TrackRun"}
_SWIM_TYPES = {"Swim", "OpenWaterSwim"}


def _primary_discipline(types: list[str] | None) -> str:
    """Return canonical discipline label based on the activity types list."""
    if not types:
        return "Other"
    type_set = set(types)
    if type_set & _RIDE_TYPES:
        return "Ride"
    if type_set & _RUN_TYPES:
        return "Run"
    if type_set & _SWIM_TYPES:
        return "Swim"
    return "Other"


def _zone_count(zones: Any) -> int:
    """Count zones from a list-or-None value."""
    if isinstance(zones, list):
        return len(zones)
    return 0


# ---------------------------------------------------------------------------
# Public formatters
# ---------------------------------------------------------------------------


def format_sport_settings_summary(settings: dict[str, Any]) -> str:
    """Format a single sport-settings record as a markdown block."""
    if not isinstance(settings, dict):
        return "Invalid sport-settings record."

    types = settings.get("types") or []
    discipline = _primary_discipline(types)
    settings_id = settings.get("id", "—")
    ftp = settings.get("ftp")
    indoor_ftp = settings.get("indoor_ftp")
    lthr = settings.get("lthr")
    max_hr = settings.get("max_hr")
    threshold_pace = settings.get("threshold_pace")
    w_prime = settings.get("w_prime")

    lines: list[str] = []
    lines.append(f"## Sport settings — {discipline} (id {settings_id})")
    lines.append(f"- **Activity types**: {', '.join(types) if types else '—'}")

    if ftp is not None:
        lines.append(f"- **FTP**: {ftp} W")
    if indoor_ftp is not None:
        lines.append(f"- **Indoor FTP**: {indoor_ftp} W")
    if lthr is not None:
        lines.append(f"- **LTHR**: {lthr} bpm")
    if max_hr is not None:
        lines.append(f"- **Max HR**: {max_hr} bpm")
    if w_prime is not None:
        lines.append(f"- **W'**: {w_prime} J")

    if threshold_pace is not None:
        if discipline == "Run":
            lines.append(
                f"- **Threshold pace**: {_ms_to_min_per_km(threshold_pace)} "
                f"(raw {threshold_pace} m/s)"
            )
        elif discipline == "Swim":
            lines.append(
                f"- **CSS pace**: {_ms_to_sec_per_100m(threshold_pace)} (raw {threshold_pace} m/s)"
            )
        else:
            lines.append(f"- **Threshold pace**: {threshold_pace} m/s")

    pz = _zone_count(settings.get("power_zones"))
    hz = _zone_count(settings.get("hr_zones"))
    paceZ = _zone_count(settings.get("pace_zones"))
    lines.append(f"- **Zones**: {pz} power | {hz} HR | {paceZ} pace")

    if settings.get("default_workout_time") is not None:
        lines.append(f"- **Default workout time**: {settings.get('default_workout_time')} s")

    return "\n".join(lines)


def format_sport_settings_list(settings_list: list[dict[str, Any]]) -> str:
    """Format a list of sport-settings as a compact markdown table."""
    if not settings_list:
        return "No sport settings found."

    rows: list[str] = []
    rows.append("| Discipline | ID | Types | FTP | LTHR | Max HR | Threshold pace |")
    rows.append("|---|---|---|---|---|---|---|")
    for s in settings_list:
        if not isinstance(s, dict):
            continue
        types = s.get("types") or []
        discipline = _primary_discipline(types)
        tp = s.get("threshold_pace")
        if discipline == "Run":
            tp_disp = _ms_to_min_per_km(tp) if tp else "—"
        elif discipline == "Swim":
            tp_disp = _ms_to_sec_per_100m(tp) if tp else "—"
        else:
            tp_disp = f"{tp} m/s" if tp else "—"
        rows.append(
            "| {disc} | {sid} | {types} | {ftp} | {lthr} | {mhr} | {tp} |".format(
                disc=discipline,
                sid=s.get("id", "—"),
                types=", ".join(types) if types else "—",
                ftp=s.get("ftp", "—"),
                lthr=s.get("lthr", "—"),
                mhr=s.get("max_hr", "—"),
                tp=tp_disp,
            )
        )
    return "Sport Settings:\n\n" + "\n".join(rows)


def format_matching_activities(activities: list[dict[str, Any]]) -> str:
    """Format the activities matching a given sport-settings record."""
    if not activities:
        return "No matching activities found."

    lines: list[str] = [f"Matching activities ({len(activities)}):", ""]
    # Cap at 50 to keep output reasonable; report total above.
    capped = activities[:50]
    for a in capped:
        if not isinstance(a, dict):
            continue
        lines.append(
            "- {date} — {type}: {name} (id {aid})".format(
                date=a.get("start_date_local", "—"),
                type=a.get("type", "—"),
                name=a.get("name", "—"),
                aid=a.get("id", "—"),
            )
        )
    if len(activities) > len(capped):
        lines.append(f"- ... ({len(activities) - len(capped)} more)")
    return "\n".join(lines)


def format_pace_distances(payload: dict[str, Any] | list[Any] | None) -> str:
    """Format a pace_distances response.

    The live API returns ``{"defaults": [...] | None, "distances": [<float>...]}``.
    ``distances`` is the available pace-curve distance set in meters.
    ``defaults`` is the per-sport default subset (None for the global endpoint).
    """
    if payload is None:
        return "No pace-distance data."

    # Tolerate a bare list response too.
    if isinstance(payload, list):
        distances = payload
        defaults = None
    elif isinstance(payload, dict):
        distances = payload.get("distances") or []
        defaults = payload.get("defaults")
    else:
        return "Invalid pace_distances payload."

    lines: list[str] = ["## Pace-curve distances"]
    if isinstance(distances, list):
        lines.append(f"- **Available distances**: {len(distances)}")
        if distances:
            preview = distances[:8]
            preview_str = ", ".join(_format_distance(d) for d in preview)
            tail = "..." if len(distances) > len(preview) else ""
            lines.append(f"- **First few**: {preview_str}{(' ' + tail) if tail else ''}")
    if defaults is None:
        lines.append("- **Defaults**: not set (global endpoint or not configured)")
    elif isinstance(defaults, list):
        lines.append(
            "- **Defaults ({n})**: {vals}".format(
                n=len(defaults),
                vals=", ".join(_format_distance(d) for d in defaults),
            )
        )
    elif isinstance(defaults, dict):
        # Defensive: surface keys if the API ever changes.
        lines.append(f"- **Defaults**: {sorted(defaults.keys())}")

    return "\n".join(lines)


def _format_distance(value: Any) -> str:
    """Render a distance value (meters, possibly float) as a short string."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if v >= 1000:
        return f"{v / 1000:.2f} km"
    return f"{v:.1f} m"
