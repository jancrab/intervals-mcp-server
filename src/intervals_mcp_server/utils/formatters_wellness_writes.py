"""
Formatters for wellness-write MCP tools.

These formatters render markdown summaries for the wellness-write tool family
(get/update single, update bulk, upload CSV). They intentionally surface the
`locked` flag explicitly because external integrations (Oura, Garmin, etc.)
will silently overwrite unlocked records on the next sync — surfacing the
state in every confirmation message lets the caller catch a missing lock
before sync clobbers their write.
"""

from __future__ import annotations

import json
from typing import Any


_KNOWN_VITAL_FIELDS: list[tuple[str, str, str]] = [
    ("hrv", "HRV", ""),
    ("hrvSDNN", "HRV SDNN", ""),
    ("restingHR", "Resting HR", "bpm"),
    ("avgSleepingHR", "Avg sleeping HR", "bpm"),
    ("weight", "Weight", "kg"),
    ("bodyFat", "Body fat", "%"),
    ("spO2", "SpO2", "%"),
    ("vo2max", "VO2 Max", "ml/kg/min"),
    ("respiration", "Respiration", "breaths/min"),
    ("bloodGlucose", "Blood glucose", "mmol/L"),
    ("lactate", "Lactate", "mmol/L"),
    ("baevskySI", "Baevsky SI", ""),
]

_KNOWN_SUBJECTIVE_FIELDS: list[tuple[str, str]] = [
    ("fatigue", "Fatigue"),
    ("soreness", "Soreness"),
    ("stress", "Stress"),
    ("mood", "Mood"),
    ("motivation", "Motivation"),
    ("injury", "Injury level"),
    ("readiness", "Readiness"),
    ("sleepQuality", "Sleep quality"),
]


def _locked_status_line(record: dict[str, Any]) -> str:
    """Render the lock status, calling out the sync-overwrite risk if unlocked."""
    if "locked" not in record:
        return "- **Locked**: not specified (default: server may treat as unlocked — external sync may overwrite)"
    if record.get("locked") is True:
        return "- **Locked**: True (protected from external sync overwrite)"
    return (
        "- **Locked**: False — WARNING: external integrations (Oura, Garmin, etc.) "
        "may silently overwrite this record on next sync"
    )


def format_wellness_record(record: dict[str, Any]) -> str:
    """Render a single wellness record as a markdown summary.

    Surfaces HRV, RHR, sleep, weight, fatigue + subjective scores, and `locked`
    state. Only fields actually present in the record are emitted, except for
    the lock status which is always surfaced.
    """
    if not isinstance(record, dict):
        return "_(invalid wellness record)_"

    date = record.get("id") or record.get("date") or "unknown date"
    lines: list[str] = [f"# Wellness record — {date}", ""]

    vitals = []
    for key, label, unit in _KNOWN_VITAL_FIELDS:
        if record.get(key) is not None:
            suffix = f" {unit}" if unit else ""
            vitals.append(f"- **{label}**: {record[key]}{suffix}")
    if vitals:
        lines.append("## Vitals")
        lines.extend(vitals)
        lines.append("")

    sleep_lines: list[str] = []
    if record.get("sleepSecs") is not None:
        sleep_lines.append(f"- **Sleep**: {record['sleepSecs'] / 3600:.2f} h")
    if record.get("sleepScore") is not None:
        sleep_lines.append(f"- **Sleep score**: {record['sleepScore']}/100")
    if sleep_lines:
        lines.append("## Sleep")
        lines.extend(sleep_lines)
        lines.append("")

    subjective = []
    for key, label in _KNOWN_SUBJECTIVE_FIELDS:
        if record.get(key) is not None:
            subjective.append(f"- **{label}**: {record[key]}")
    if subjective:
        lines.append("## Subjective")
        lines.extend(subjective)
        lines.append("")

    training = []
    for key, label in [("ctl", "CTL"), ("atl", "ATL"), ("rampRate", "Ramp rate")]:
        if record.get(key) is not None:
            training.append(f"- **{label}**: {record[key]}")
    if training:
        lines.append("## Training load")
        lines.extend(training)
        lines.append("")

    if record.get("comments"):
        lines.append(f"**Comments**: {record['comments']}")
        lines.append("")

    lines.append("## Status")
    lines.append(_locked_status_line(record))

    return "\n".join(lines)


def format_wellness_write_confirmation(record: dict[str, Any], action: str) -> str:
    """Markdown confirmation for after a successful single-record write.

    Args:
        record: The record as it was sent (or as returned by the API).
        action: Verb describing what happened, e.g. "updated", "created".
    """
    if not isinstance(record, dict):
        return f"Wellness {action} (no record returned)."

    date = record.get("id") or record.get("date") or "unknown date"
    locked = record.get("locked")

    lines = [f"# Wellness {action} — {date}", ""]
    lines.append(_locked_status_line(record))

    if locked is False:
        lines.append("")
        lines.append(
            "> WARNING: `locked` is False. External integrations (Oura, Garmin, etc.) "
            "may silently overwrite this record on their next sync. Set `locked=True` "
            "to protect the values you just wrote."
        )

    # Echo the fields that were actually sent so the caller can confirm
    written_fields = {
        k: v for k, v in record.items() if v is not None and k not in {"id", "date", "updated"}
    }
    if written_fields:
        lines.append("")
        lines.append("## Fields written")
        for k in sorted(written_fields.keys()):
            v = written_fields[k]
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            lines.append(f"- **{k}**: {v}")

    return "\n".join(lines)


def format_wellness_bulk_confirmation(records: list[dict[str, Any]]) -> str:
    """Markdown confirmation for a bulk wellness write.

    Surfaces a count, per-record date and lock status, and a top-line warning
    if any record was written with `locked=False`.
    """
    if not records:
        return "Wellness bulk write returned no records."

    unlocked_dates = [
        (r.get("id") or r.get("date") or "?")
        for r in records
        if isinstance(r, dict) and r.get("locked") is False
    ]

    lines = [f"# Wellness bulk write — {len(records)} record(s)", ""]

    if unlocked_dates:
        lines.append(
            "> WARNING: "
            f"{len(unlocked_dates)} record(s) written with `locked=False`: "
            f"{', '.join(unlocked_dates)}. External sync may overwrite them."
        )
        lines.append("")

    lines.append("| Date | Locked | Fields |")
    lines.append("|---|---|---|")
    for r in records:
        if not isinstance(r, dict):
            continue
        date = r.get("id") or r.get("date") or "—"
        locked = r.get("locked")
        locked_str = "True" if locked is True else ("False" if locked is False else "—")
        field_count = sum(
            1
            for k, v in r.items()
            if v is not None and k not in {"id", "date", "updated", "locked"}
        )
        lines.append(f"| {date} | {locked_str} | {field_count} |")

    return "\n".join(lines)
