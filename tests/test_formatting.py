"""
Unit tests for formatting utilities in intervals_mcp_server.utils.formatting.

These tests verify that the formatting functions produce expected output strings for activities, workouts, wellness entries, events, and intervals.
"""

import json
from intervals_mcp_server.utils.formatting import (
    format_activity_summary,
    format_workout,
    format_wellness_entry,
    format_event_summary,
    format_event_details,
    format_intervals,
)
from tests.sample_data import INTERVALS_DATA


def test_format_activity_summary():
    """
    Test that format_activity_summary returns a string containing the activity name and ID.

    Uses an `i`-prefixed string ID per intervals.icu's post-normalization
    convention. (Pre-normalization stubs use unprefixed / int IDs and are
    short-circuited by the draft-detection path; covered by separate tests.)
    """
    data = {
        "name": "Morning Ride",
        "id": "i1",
        "type": "Ride",
        "startTime": "2024-01-01T08:00:00Z",
        "distance": 1000,
        "duration": 3600,
    }
    result = format_activity_summary(data)
    assert "Activity: Morning Ride" in result
    assert "ID: i1" in result


def test_format_workout():
    """
    Test that format_workout returns a string containing the workout name and interval count.
    """
    workout = {
        "name": "Workout1",
        "description": "desc",
        "sport": "Ride",
        "duration": 3600,
        "tss": 50,
        "intervals": [1, 2, 3],
    }
    result = format_workout(workout)
    assert "Workout: Workout1" in result
    assert "Intervals: 3" in result


def test_format_wellness_entry():
    """
    Test that format_wellness_entry returns a string containing the date and fitness (CTL).
    """
    with open("tests/ressources/wellness_entry.json", "r", encoding="utf-8") as f:
        entry = json.load(f)
    result = format_wellness_entry(entry)

    with open("tests/ressources/wellness_entry_formatted.txt", "r", encoding="utf-8") as f:
        expected_result = f.read()
    assert result == expected_result


def test_format_wellness_entry_include_all_fields():
    """
    Test that format_wellness_entry with include_all_fields=True includes additional unknown fields.
    """
    entry = {
        "id": "2024-06-01",
        "ctl": 80,
        "weight": 75,
        "customField1": "hello",
        "customField2": 42,
        "updated": "2024-06-01T10:00:00Z",
    }
    result = format_wellness_entry(entry, include_all_fields=True)
    assert "Date: 2024-06-01" in result
    assert "Fitness (CTL): 80" in result
    assert "Weight: 75 kg" in result
    assert "Other Fields:" in result
    assert "customField1: hello" in result
    assert "customField2: 42" in result
    # "updated" is a known built-in field, should not appear in Other Fields
    assert "updated:" not in result


def test_format_wellness_entry_no_extra_fields_by_default():
    """
    Test that format_wellness_entry without include_all_fields does not include additional fields.
    """
    entry = {
        "id": "2024-06-01",
        "ctl": 80,
        "customField1": "hello",
    }
    result = format_wellness_entry(entry)
    assert "Other Fields:" not in result
    assert "customField1" not in result


def test_format_wellness_entry_macros_populated():
    """
    Test that format_wellness_entry renders native nutrition macros
    (carbohydrates, protein, fatTotal) in grams when present.
    """
    entry = {
        "id": "2026-04-08",
        "carbohydrates": 310,
        "protein": 145,
        "fatTotal": 72,
    }
    result = format_wellness_entry(entry)
    assert "Nutrition & Hydration:" in result
    assert "- Carbohydrates: 310 g" in result
    assert "- Protein: 145 g" in result
    assert "- Fat: 72 g" in result


def test_format_wellness_entry_macros_null_hidden():
    """
    Test that format_wellness_entry hides macro lines when the fields are null,
    preserving backward compatibility with older wellness records.
    """
    entry = {
        "id": "2026-04-08",
        "ctl": 80,
        "carbohydrates": None,
        "protein": None,
        "fatTotal": None,
    }
    result = format_wellness_entry(entry)
    assert "Carbohydrates" not in result
    assert "Protein" not in result
    # "Fat" could legitimately appear inside e.g. "Body Fat" elsewhere, so
    # anchor the negative assertion on the line-prefix form we would emit.
    assert "- Fat:" not in result


def test_format_event_summary():
    """
    Test that format_event_summary returns a string containing the event date and type.
    """
    event = {
        "start_date_local": "2024-01-01",
        "id": "e1",
        "name": "Event1",
        "description": "desc",
        "race": True,
    }
    summary = format_event_summary(event)
    assert "Date: 2024-01-01" in summary
    assert "Type: Race" in summary


def test_format_event_details():
    """
    Test that format_event_details returns a string containing event and workout details.
    """
    event = {
        "id": "e1",
        "date": "2024-01-01",
        "name": "Event1",
        "description": "desc",
        "workout": {
            "id": "w1",
            "sport": "Ride",
            "duration": 3600,
            "tss": 50,
            "intervals": [1, 2],
        },
        "race": True,
        "priority": "A",
        "result": "1st",
        "calendar": {"name": "Main"},
    }
    details = format_event_details(event)
    assert "Event Details:" in details
    assert "Workout Information:" in details


def test_format_intervals():
    """
    Test that format_intervals returns a string containing interval analysis and the interval label.
    """
    result = format_intervals(INTERVALS_DATA)
    assert "Intervals Analysis:" in result
    assert "Rep 1" in result


# ---------------------------------------------------------------------------
# v1.3.0 — Pre-normalization stub detection
# ---------------------------------------------------------------------------

from intervals_mcp_server.utils.formatting import (  # noqa: E402  (after-fixture import is intentional)
    _format_draft_activity,
    _is_draft_activity,
)


def test_is_draft_activity_detects_int_id():
    """An int id is a clear pre-normalization signal — intervals.icu uses
    `i…`-prefixed string IDs only after normalization."""
    assert _is_draft_activity({"id": 18303442074}) is True


def test_is_draft_activity_detects_unprefixed_str_id():
    """Some upstream IDs (e.g. Garmin / Strava activity IDs) come back as
    raw numeric strings before normalization assigns the `i…` form."""
    assert _is_draft_activity({"id": "18303442074"}) is True


def test_is_draft_activity_detects_empty_metadata():
    """Even with a properly-prefixed id, an activity with all of name,
    type, and start_date_local missing is a stub. The web UI still renders
    it (from the upload payload) but the API exposes nothing."""
    assert (
        _is_draft_activity(
            {
                "id": "i12345",
                "name": None,
                "type": None,
                "start_date_local": None,
            }
        )
        is True
    )


def test_is_draft_activity_passes_normal_activity():
    """A fully-populated activity must NOT be flagged. False positives
    here would short-circuit real data through the remediation message."""
    assert (
        _is_draft_activity(
            {
                "id": "i142786468",
                "name": "Z2 movie maker",
                "type": "VirtualRide",
                "start_date_local": "2026-04-25T08:52:20",
            }
        )
        is False
    )


def test_format_draft_activity_includes_url():
    """The remediation message must include a clickable web URL using the
    raw activity ID — intervals.icu's web URL accepts both upstream and
    `i…`-prefixed IDs, so no munging needed."""
    out = _format_draft_activity({"id": 18303442074})
    assert "https://intervals.icu/activities/18303442074" in out


def test_format_activity_summary_short_circuits_on_draft():
    """The short-circuit must replace the entire 60-line N/A block with
    the remediation message. No `Power Data:` heading should appear."""
    draft = {"id": 18303442074, "name": None, "type": None}
    out = format_activity_summary(draft)
    assert "Power Data:" not in out
    assert "pre-normalization" in out


def test_format_activity_summary_renders_normal_activity_unchanged():
    """A fully-populated activity must render via the existing pipeline,
    including the `Power Data:` section header. This guards against
    accidental over-eager draft detection."""
    activity = {
        "name": "Tempo Ride",
        "id": "i142786468",
        "type": "Ride",
        "start_date_local": "2026-04-25T08:52:20",
        "startTime": "2026-04-25T08:52:20Z",
        "distance": 30000,
        "duration": 3600,
        "icu_average_watts": 220,
    }
    out = format_activity_summary(activity)
    assert "Power Data:" in out
    assert "pre-normalization" not in out
