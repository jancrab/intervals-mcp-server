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


def test_format_event_details_renders_start_date_local():
    """v1.3.2: get_event_by_id returns events with `start_date_local` (not
    `date`); the previous formatter rendered `Date: Unknown` for every such
    event. The formatter must now fall back through start_date_local → date
    → "Unknown" — same chain `format_event_summary` already uses."""
    event = {
        "id": "107189636",
        "start_date_local": "2026-04-29T00:00:00",
        # Note: no top-level `date` field — this is the by-id endpoint shape.
        "name": "FTP test",
        "description": "20-min test",
    }
    details = format_event_details(event)
    assert "Date: 2026-04-29T00:00:00" in details
    assert "Date: Unknown" not in details


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
    assert "[incomplete-activity]" in out
    # Obsolete transient-state wording must be gone (v1.4.1).
    assert "pre-normalization" not in out


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


# ---------------------------------------------------------------------------
# v1.3.1 — Sharpened draft message (orphan vs save-and-name)
# ---------------------------------------------------------------------------


def test_draft_message_mentions_link_tool():
    """Sharpened message must point at the new write tool by name so the
    model can act when an orphan-Zwift-workout case is detected. Without
    the tool name, the model has no fast path to the canonical fix."""
    out = _format_draft_activity({"id": 18303442074})
    assert "link_activity_to_event" in out


def test_draft_message_keeps_url():
    """The web URL line must survive the v1.3.1 rewrite — older v1.3.0
    tests check for it, and it's still the user's manual fallback when
    no planned event exists for the date."""
    out = _format_draft_activity({"id": 18303442074})
    assert "https://intervals.icu/activities/18303442074" in out


def test_incomplete_message_drops_obsolete_wording():
    """v1.4.1: the non-Strava empty-stub message no longer claims a transient
    pre-normalization state or a guaranteed "rename to fix" — it surfaces the
    [incomplete-activity] label, the URL, and the link tool as a neutral
    pointer, without the obsolete remediation wording."""
    out = _format_draft_activity({"id": 18303442074})
    assert "[incomplete-activity]" in out
    assert "link_activity_to_event" in out
    assert "give the activity a name, and save" not in out
    assert "pre-normalization" not in out
    assert "forces normalization" not in out


# ---------------------------------------------------------------------------
# v1.3.3 — Passthrough + advisory for substantive draft activities
# ---------------------------------------------------------------------------


from intervals_mcp_server.utils.formatting import (  # noqa: E402
    _format_draft_advisory_header,
    _has_substantive_activity_data,
)


def test_has_substantive_activity_data_true_when_name_present():
    """A non-empty name alone is enough — a draft with a typed name has
    something worth rendering."""
    assert _has_substantive_activity_data({"name": "Zwift Stock 20-min FTP"}) is True


def test_has_substantive_activity_data_true_when_power_present():
    """A positive average power means the API gave us real numbers, even
    if other metadata fields are missing."""
    assert _has_substantive_activity_data({"icu_average_watts": 247}) is True


def test_has_substantive_activity_data_true_when_streams_listed():
    """A populated stream_types list signals fetchable curves/streams even
    pre-rename — counts as substantive."""
    assert _has_substantive_activity_data(
        {"stream_types": ["watts", "heartrate"]}
    ) is True


def test_has_substantive_activity_data_false_on_v1_3_0_empty_stub():
    """The canonical v1.3.0 empty-stub shape (just an upstream int id, all
    other fields null) is NOT substantive — must route to the remediation
    message, not the advisory-header path."""
    assert (
        _has_substantive_activity_data(
            {"id": 18303442074, "name": None, "type": None, "duration": 0}
        )
        is False
    )


def test_format_activity_summary_draft_with_data_renders_full_plus_advisory():
    """v1.3.3: when the API returns substantive data on a draft (the case
    a genuinely pre-normalization NON-Strava upload reaches intervals.icu
    with stream_types and average_watts intact), render the full body and
    prepend an advisory header. The data must NOT be withheld.

    NOTE (v1.4.0): the original v1.3.3 fixture used source=STRAVA, but the
    live API never returns substantive data for Strava-sourced activities —
    it returns a 5-key stub (confirmed 2026-05-31). Strava is now routed to
    its own restricted message (tested separately). This test covers the
    real remaining case: a non-Strava draft (e.g. a freshly-uploaded Garmin
    activity not yet assigned its `i`-prefixed id) that carries partial
    data."""
    activity = {
        "id": 18303442074,  # raw upstream id → draft signal
        "name": "Zwift Stock 20-min FTP",
        "type": "VirtualRide",
        "source": "GARMIN",  # non-Strava → advisory path, not restricted path
        "stream_types": ["watts", "heartrate", "cadence"],
        "duration": 1200,
        "distance": 12500,
        "icu_average_watts": 247,
        "average_heartrate": 168,
    }
    out = format_activity_summary(activity)
    # Advisory header is present and identifies the source.
    assert "advisory:" in out
    assert "GARMIN" in out
    assert "watts" in out
    # And the full body is rendered — power data is not withheld.
    assert "Power Data:" in out
    assert "247" in out  # avg power preserved


# ---------------------------------------------------------------------------
# v1.4.0 — Strava-source restriction (the real root cause)
# ---------------------------------------------------------------------------


from intervals_mcp_server.utils.formatting import _is_strava_restricted  # noqa: E402


def test_is_strava_restricted_on_source_field():
    """source==STRAVA is the primary signal."""
    assert _is_strava_restricted({"id": "18728161934", "source": "STRAVA"}) is True


def test_is_strava_restricted_on_note_field():
    """The _note string is the secondary signal (belt and suspenders)."""
    assert (
        _is_strava_restricted(
            {"id": "x", "_note": "STRAVA activities are not available via the API"}
        )
        is True
    )


def test_is_strava_restricted_false_for_normal_activity():
    """Non-Strava sources must not trip the restriction path."""
    assert _is_strava_restricted({"id": "i152673908", "source": "WAHOO"}) is False


def test_format_activity_summary_strava_restricted_real_stub():
    """The exact 5-key stub shape the live API returns for a Strava-sourced
    activity (confirmed 2026-05-31) must render a compact honest message:
    no Power-Data wall, a [strava-restricted] marker, the real cause, and
    the non-Strava remediation. Not a pre-normalization message — Strava
    restriction is permanent."""
    stub = {
        "id": "18728161934",
        "icu_athlete_id": "i141174",
        "start_date_local": "2026-05-31T12:40:44",
        "source": "STRAVA",
        "_note": "STRAVA activities are not available via the API",
    }
    out = format_activity_summary(stub)
    assert "[strava-restricted]" in out
    assert "Power Data:" not in out  # no N/A wall
    assert "Garmin" in out  # non-Strava remediation surfaced
    assert "non-Strava" in out
    # Must NOT use the pre-normalization wording — different cause.
    assert "hasn't completed normalization" not in out
    assert "link_activity_to_event" not in out
    # Compact, not a wall.
    assert len(out.splitlines()) <= 5


def test_format_activity_summary_draft_empty_keeps_remediation():
    """v1.3.3 guard: the empty-stub path (no substantive data, NON-Strava)
    must still return the v1.3.0 remediation message, NOT a 60-line N/A
    wall with an advisory header tacked on top."""
    stub = {"id": 18303442074, "name": None, "type": None}
    out = format_activity_summary(stub)
    assert "Power Data:" not in out
    assert "[incomplete-activity]" in out
    assert "pre-normalization" not in out
    # The remediation path uses _format_draft_activity, not the advisory
    # header — the literal "advisory:" prefix must not appear here.
    assert "advisory:" not in out


def test_format_draft_advisory_header_surfaces_source_and_streams():
    """The advisory header must surface the fields a coach/model needs to
    decide what to fetch next: source (lineage), whether analysis ran,
    available stream types, and the web URL for the manual remediation."""
    activity = {
        "id": 18303442074,
        "source": "STRAVA",
        "icu_intervals": [],  # not yet analyzed
        "stream_types": ["watts", "heartrate"],
    }
    out = _format_draft_advisory_header(activity)
    assert "source=STRAVA" in out
    assert "analyzed=False" in out
    assert "watts" in out and "heartrate" in out
    assert "https://intervals.icu/activities/18303442074" in out


def test_format_activity_summary_non_draft_unchanged():
    """v1.3.3 must not touch the non-draft path. Existing v1.3.0 test
    (test_format_activity_summary_renders_normal_activity_unchanged)
    covers this for normalized activities; this is the explicit guard
    that the advisory header does NOT leak into non-draft output."""
    activity = {
        "name": "Normal Ride",
        "id": "i142786468",
        "type": "Ride",
        "start_date_local": "2026-05-31T08:52:20",
        "startTime": "2026-05-31T08:52:20Z",
        "duration": 3600,
        "icu_average_watts": 220,
    }
    out = format_activity_summary(activity)
    assert "advisory:" not in out
    assert "Power Data:" in out
