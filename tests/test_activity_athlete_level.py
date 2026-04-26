"""
Unit tests for athlete-level activity MCP tools.

Mirrors the patterns in tests/test_sport_settings.py: monkeypatch
``make_intervals_request`` in both the api.client and the tools module to
stub responses, then assert on the formatted string and (for writes) on the
captured request kwargs (method + data + URL).
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.tools.activity_athlete_level import (  # pylint: disable=wrong-import-position
    create_manual_activity,
    create_multiple_manual_activities,
    get_activities_by_ids,
    get_activities_csv,
    get_athlete_mmp_model,
    get_athlete_power_hr_curve,
    list_activities_around,
    list_activity_hr_curves,
    list_activity_pace_curves,
    list_activity_power_curves,
    list_activity_tags,
    list_athlete_hr_curves,
    list_athlete_pace_curves,
    list_athlete_power_curves,
    search_for_activities,
    search_for_activities_full,
    search_for_intervals,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_ACTIVITY_A = {
    "id": "i142786468",
    "name": "Zwift - Z2",
    "type": "VirtualRide",
    "start_date_local": "2026-04-25T10:52:20",
    "moving_time": 5234,
    "distance": 13450.9,
    "icu_training_load": 68,
    "icu_intensity": 0.68,
}
SAMPLE_ACTIVITY_B = {
    "id": "i142324120",
    "name": "Outdoor Ride",
    "type": "Ride",
    "start_date_local": "2026-04-23T15:43:08",
    "moving_time": 7800,
    "distance": 60000.0,
    "icu_training_load": 174,
    "icu_intensity": 0.82,
}

SAMPLE_POWER_CURVE_LIST = {
    "list": [
        {
            "id": "1y",
            "label": "1 year",
            "secs": [1, 5, 60, 300, 1200, 3600],
            "values": [1074, 953, 432, 308, 220, 166],
        }
    ]
}

SAMPLE_MMP_MODEL = {
    "type": "FFT_CURVES",
    "criticalPower": 208,
    "wPrime": 16800,
    "pMax": 989,
    "ftp": 212,
    "inputPointIndexes": [80, 89],
}

SAMPLE_POWER_HR_CURVE = {
    "athleteId": "i1",
    "start": "2026-03-25",
    "end": "2026-04-25",
    "minWatts": 20,
    "bucketSize": 5,
    "bpm": [122, 0, 130, 152],
    "cadence": [15, 0, 27, 82],
    "minutes": [1, 0, 3, 47],
    "ftp": 240,
    "lthr": 172,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_request(monkeypatch, fake_request):
    """Monkeypatch make_intervals_request in client + tools module."""
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activity_athlete_level.make_intervals_request",
        fake_request,
    )


def _patch_raw_text(monkeypatch, fake_text):
    """Monkeypatch _fetch_raw_text used for CSV endpoints."""

    async def fake(*args, **kwargs):  # noqa: ARG001
        return fake_text, None

    monkeypatch.setattr("intervals_mcp_server.tools.activity_athlete_level._fetch_raw_text", fake)


# ---------------------------------------------------------------------------
# Multi-fetch / range
# ---------------------------------------------------------------------------


def test_get_activities_by_ids_path_includes_comma(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["url"] = kwargs.get("url")
        return [SAMPLE_ACTIVITY_A, SAMPLE_ACTIVITY_B]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        get_activities_by_ids(activity_ids=["i142786468", "i142324120"], athlete_id="i1")
    )
    assert captured["url"].endswith("/activities/i142786468,i142324120")
    assert "Activities (2)" in out
    assert "Zwift" in out
    assert "Outdoor Ride" in out


def test_list_activities_around(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["params"] = kwargs.get("params")
        captured["url"] = kwargs.get("url")
        return [SAMPLE_ACTIVITY_A]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_activities_around(activity_id="i142786468", days=2, athlete_id="i1"))
    assert captured["params"]["activity_id"] == "i142786468"
    assert captured["params"]["days"] == 2
    assert captured["url"].endswith("/activities-around")
    assert "Activities (1)" in out


def test_get_activities_csv_returns_codeblock(monkeypatch):
    sample_csv = "id,name,type\n1,Z2,Ride\n2,Tempo,Ride"
    _patch_raw_text(monkeypatch, sample_csv)
    out = asyncio.run(
        get_activities_csv(start_date="2026-04-15", end_date="2026-04-25", athlete_id="i1")
    )
    assert out.startswith("```csv")
    assert "id,name,type" in out
    assert out.rstrip().endswith("```")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def test_search_for_activities(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["params"] = kwargs.get("params")
        captured["url"] = kwargs.get("url")
        return [SAMPLE_ACTIVITY_A]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(search_for_activities(query="Zwift", limit=3, athlete_id="i1"))
    assert captured["params"]["q"] == "Zwift"
    assert captured["params"]["limit"] == 3
    assert captured["url"].endswith("/activities/search")
    assert "Search results (summary)" in out


def test_search_for_activities_full(monkeypatch):
    async def fake_request(*_args, **kwargs):
        assert kwargs.get("url", "").endswith("/activities/search-full")
        return [SAMPLE_ACTIVITY_A, SAMPLE_ACTIVITY_B]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(search_for_activities_full(query="Ride", athlete_id="i1"))
    assert "Search results (full)" in out
    assert "VirtualRide" in out


def test_search_for_intervals(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["params"] = kwargs.get("params")
        return [
            {
                "id": "i999",
                "name": "VO2 day",
                "type": "Ride",
                "start_date_local": "2026-04-22T07:00:00",
                "intervals": [
                    {
                        "name": "1 of 5",
                        "moving_time": 360,
                        "average_watts": 285,
                        "average_heartrate": 168,
                    }
                ],
            }
        ]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        search_for_intervals(
            min_secs=300,
            max_secs=600,
            activity_type="Ride",
            athlete_id="i1",
        )
    )
    assert captured["params"]["minSecs"] == 300
    assert captured["params"]["maxSecs"] == 600
    assert captured["params"]["type"] == "Ride"
    assert "Interval matches" in out
    assert "VO2 day" in out


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def test_list_activity_tags_strings(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return ["VO2", "race", "openers"]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_activity_tags(athlete_id="i1"))
    assert "Activity tags" in out
    assert "- VO2" in out
    assert "- race" in out


# ---------------------------------------------------------------------------
# Curves — JSON mode
# ---------------------------------------------------------------------------


def test_list_athlete_power_curves_json(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["url"] = kwargs.get("url")
        captured["params"] = kwargs.get("params")
        return SAMPLE_POWER_CURVE_LIST

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_athlete_power_curves(activity_type="Ride", athlete_id="i1"))
    assert captured["url"].endswith("/power-curves")
    assert captured["params"]["type"] == "Ride"
    assert "Curve aggregation" in out
    assert "1 year" in out


def test_list_activity_power_curves_json(monkeypatch):
    async def fake_request(*_args, **kwargs):
        assert kwargs.get("url", "").endswith("/activity-power-curves")
        return {
            "secs": [1, 60, 300],
            "curves": [{"id": "i142786468", "watts": [303, 192, 170]}],
        }

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_activity_power_curves(activity_type="Ride", athlete_id="i1"))
    assert "Curve aggregation" in out


def test_list_activity_hr_curves_json(monkeypatch):
    async def fake_request(*_args, **kwargs):
        assert kwargs.get("url", "").endswith("/activity-hr-curves")
        return {"list": []}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_activity_hr_curves(activity_type="Ride", athlete_id="i1"))
    assert "No curve data" in out or "Curve aggregation" in out


def test_list_activity_pace_curves_json(monkeypatch):
    async def fake_request(*_args, **kwargs):
        assert kwargs.get("url", "").endswith("/activity-pace-curves")
        return {"list": [{"id": "1y", "meters": [100, 1000, 5000], "values": [3.5, 3.2, 3.0]}]}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_activity_pace_curves(activity_type="Run", athlete_id="i1"))
    assert "Curve aggregation" in out


def test_list_athlete_hr_curves_json(monkeypatch):
    async def fake_request(*_args, **kwargs):
        assert kwargs.get("url", "").endswith("/hr-curves")
        return {"list": [{"id": "1y", "secs": [1, 60, 600], "values": [195, 188, 172]}]}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_athlete_hr_curves(activity_type="Ride", athlete_id="i1"))
    assert "Curve aggregation" in out


def test_list_athlete_pace_curves_json(monkeypatch):
    async def fake_request(*_args, **kwargs):
        assert kwargs.get("url", "").endswith("/pace-curves")
        return {
            "list": [
                {
                    "id": "1y",
                    "meters": [100, 1000, 5000, 10000],
                    "values": [4.5, 4.2, 3.9, 3.7],
                }
            ]
        }

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_athlete_pace_curves(activity_type="Run", athlete_id="i1"))
    assert "Curve aggregation" in out


# ---------------------------------------------------------------------------
# Curves — CSV mode
# ---------------------------------------------------------------------------


def test_list_athlete_power_curves_csv(monkeypatch):
    sample = "secs,1 year\n1,1074\n60,432\n300,308"
    captured: dict[str, Any] = {}

    async def fake_text(url, api_key, params=None):  # noqa: ARG001
        captured["url"] = url
        captured["params"] = params
        return sample, None

    monkeypatch.setattr(
        "intervals_mcp_server.tools.activity_athlete_level._fetch_raw_text", fake_text
    )
    out = asyncio.run(
        list_athlete_power_curves(activity_type="Ride", format="csv", athlete_id="i1")
    )
    assert captured["url"].endswith("/power-curves.csv")
    assert out.startswith("```csv")
    assert "1 year" in out


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


def test_get_athlete_mmp_model(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["params"] = kwargs.get("params")
        captured["url"] = kwargs.get("url")
        return SAMPLE_MMP_MODEL

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_athlete_mmp_model(activity_type="Ride", athlete_id="i1"))
    assert captured["url"].endswith("/mmp-model")
    assert captured["params"]["type"] == "Ride"
    assert "MMP power model" in out
    assert "FFT_CURVES" in out
    assert "208" in out  # CP


def test_get_athlete_power_hr_curve(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["params"] = kwargs.get("params")
        return SAMPLE_POWER_HR_CURVE

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        get_athlete_power_hr_curve(
            activity_type="Ride",
            start_date="2026-03-25",
            end_date="2026-04-25",
            athlete_id="i1",
        )
    )
    assert captured["params"]["start"] == "2026-03-25"
    assert captured["params"]["end"] == "2026-04-25"
    assert captured["params"]["type"] == "Ride"
    assert "Power vs HR" in out


# ---------------------------------------------------------------------------
# Writes — manual activity
# ---------------------------------------------------------------------------


def test_create_manual_activity_posts_body(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {
            "id": "i999",
            "name": "Recovery walk",
            "type": "Walk",
            "start_date_local": "2026-04-25T18:00:00",
            "moving_time": 1800,
            "distance": 2000,
        }

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        create_manual_activity(
            start_date_local="2026-04-25T18:00:00",
            activity_type="Walk",
            name="Recovery walk",
            moving_time=1800,
            distance=2000.0,
            athlete_id="i1",
        )
    )
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/activities/manual")
    assert captured["data"]["start_date_local"] == "2026-04-25T18:00:00"
    assert captured["data"]["type"] == "Walk"
    assert captured["data"]["name"] == "Recovery walk"
    assert captured["data"]["moving_time"] == 1800
    assert captured["data"]["distance"] == 2000.0
    assert "Manual activity created" in out
    assert "i999" in out


def test_create_multiple_manual_activities_body_is_list(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return [
            {
                "id": "i1001",
                "name": "A",
                "type": "Run",
                "start_date_local": "2026-04-20T07:00:00",
                "moving_time": 1800,
            },
            {
                "id": "i1002",
                "name": "B",
                "type": "Run",
                "start_date_local": "2026-04-21T07:00:00",
                "moving_time": 2400,
            },
        ]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        create_multiple_manual_activities(
            activities=[
                {
                    "start_date_local": "2026-04-20T07:00:00",
                    "type": "Run",
                    "name": "A",
                    "moving_time": 1800,
                    "external_id": "ext-a",
                },
                {
                    "start_date_local": "2026-04-21T07:00:00",
                    "type": "Run",
                    "name": "B",
                    "moving_time": 2400,
                    "external_id": "ext-b",
                },
            ],
            athlete_id="i1",
        )
    )
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/activities/manual/bulk")
    assert isinstance(captured["data"], list)
    assert len(captured["data"]) == 2
    assert captured["data"][0]["external_id"] == "ext-a"
    assert "Bulk manual activities" in out
    assert "i1001" in out
    assert "i1002" in out


# ---------------------------------------------------------------------------
# Validation guards
# ---------------------------------------------------------------------------


def test_create_manual_activity_missing_required(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        raise AssertionError("API should not be called when validation fails")

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        create_manual_activity(
            start_date_local="",
            activity_type="Run",
            name="X",
            moving_time=1800,
            athlete_id="i1",
        )
    )
    assert out.lower().startswith("error")
    assert "start_date_local" in out


def test_get_activities_by_ids_empty_list(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        raise AssertionError("API should not be called when validation fails")

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activities_by_ids(activity_ids=[], athlete_id="i1"))
    assert out.lower().startswith("error")


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------


def test_get_athlete_mmp_model_api_error(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 422, "message": "Type required"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_athlete_mmp_model(activity_type="Bogus", athlete_id="i1"))
    assert "Error fetching MMP model" in out
    assert "Type required" in out


def test_search_for_activities_api_error(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 500, "message": "Boom"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(search_for_activities(query="nope", athlete_id="i1"))
    assert "Error searching activities" in out
    assert "Boom" in out
