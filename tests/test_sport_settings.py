"""
Unit tests for sport-settings MCP tools.

Mirrors the patterns in tests/test_server.py: monkeypatch
``make_intervals_request`` in both the api.client and the tools module to
stub responses, then assert on the formatted string and (for writes) on the
captured request kwargs (method + data + URL).
"""

import asyncio
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.tools.sport_settings import (  # pylint: disable=wrong-import-position
    apply_sport_settings_to_activities,
    create_sport_settings,
    delete_sport_settings,
    get_sport_settings,
    list_activities_matching_sport_settings,
    list_pace_distances,
    list_pace_distances_for_sport,
    list_sport_settings,
    update_sport_settings,
    update_sport_settings_multi,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_RIDE = {
    "id": 100,
    "athlete_id": "i1",
    "types": ["Ride", "VirtualRide", "MountainBikeRide"],
    "ftp": 280,
    "indoor_ftp": 275,
    "lthr": 165,
    "max_hr": 188,
    "threshold_pace": None,
    "w_prime": 22000,
    "power_zones": [55, 75, 90, 105, 120, 150],
    "hr_zones": [115, 140, 155, 165, 175],
    "pace_zones": None,
    "default_workout_time": 3600,
}
SAMPLE_RUN = {
    "id": 101,
    "athlete_id": "i1",
    "types": ["Run", "TrailRun"],
    "ftp": None,
    "lthr": 170,
    "max_hr": 192,
    "threshold_pace": 4.0,  # m/s, ~4:10/km
    "power_zones": None,
    "hr_zones": [120, 145, 160, 170, 180],
    "pace_zones": [3.0, 3.5, 4.0, 4.5, 5.0],
}
SAMPLE_SWIM = {
    "id": 102,
    "athlete_id": "i1",
    "types": ["Swim", "OpenWaterSwim"],
    "lthr": None,
    "max_hr": None,
    "threshold_pace": 1.25,  # m/s, ~1:20/100m
    "power_zones": None,
    "hr_zones": None,
    "pace_zones": [1.0, 1.1, 1.25, 1.4, 1.6],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_request(monkeypatch, fake_request):
    """Monkeypatch make_intervals_request in client + tools module."""
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.sport_settings.make_intervals_request", fake_request
    )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def test_list_sport_settings_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return [SAMPLE_RIDE, SAMPLE_RUN, SAMPLE_SWIM]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_sport_settings(athlete_id="i1"))
    assert "Sport Settings" in out
    assert "| Ride |" in out
    assert "| Run |" in out
    assert "| Swim |" in out
    assert "280" in out  # FTP shown
    # Run threshold pace converted to mm:ss/km
    assert "/km" in out


def test_get_sport_settings_by_type(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured["url"] = kwargs.get("url")
        return SAMPLE_RUN

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_sport_settings(settings_id="Run", athlete_id="i1"))
    assert "Run" in out
    assert "Threshold pace" in out
    assert "/km" in out
    assert captured["url"].endswith("/sport-settings/Run")


def test_list_activities_matching(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return [
            {"id": 1, "name": "Tempo", "type": "Run", "start_date_local": "2026-04-22T07:00:00"},
            {"id": 2, "name": "Long", "type": "Run", "start_date_local": "2026-04-23T08:00:00"},
        ]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_activities_matching_sport_settings(settings_id="101", athlete_id="i1"))
    assert "Matching activities (2)" in out
    assert "Tempo" in out
    assert "Long" in out


def test_list_pace_distances_for_sport(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return {"defaults": [400.0, 1000.0, 5000.0], "distances": [100.0, 200.0, 400.0, 1000.0]}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_pace_distances_for_sport(settings_id="Run", athlete_id="i1"))
    assert "Pace-curve distances" in out
    assert "Available distances" in out
    assert "Defaults" in out


def test_list_pace_distances_global(monkeypatch):
    async def fake_request(*_args, **kwargs):
        # Global endpoint: no athlete in path
        assert kwargs.get("url") == "/pace_distances"
        return {"defaults": None, "distances": [50.0, 100.0, 200.0]}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_pace_distances())
    assert "Pace-curve distances" in out
    assert "Defaults" in out
    assert "not set" in out


# ---------------------------------------------------------------------------
# Writes — happy path with kwarg capture
# ---------------------------------------------------------------------------


def test_create_sport_settings_posts_body(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {"id": 999, "types": ["Run"]}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        create_sport_settings(
            types=["Run", "TrailRun"],
            athlete_id="i1",
            settings={"ftp": 0, "lthr": 170},
        )
    )
    assert "999" in out
    assert captured["method"] == "POST"
    assert captured["data"]["types"] == ["Run", "TrailRun"]
    assert captured["data"]["lthr"] == 170


def test_update_sport_settings_puts_body(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {"id": 101}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        update_sport_settings(
            settings_id="101",
            settings={"ftp": 285, "lthr": 169},
            athlete_id="i1",
        )
    )
    assert "updated" in out.lower()
    assert captured["method"] == "PUT"
    assert captured["data"] == {"ftp": 285, "lthr": 169}
    assert captured["url"].endswith("/sport-settings/101")


def test_update_sport_settings_multi(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return [{"id": 100}, {"id": 101}]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        update_sport_settings_multi(
            updates=[
                {"id": 100, "ftp": 285},
                {"id": 101, "lthr": 170},
            ],
            athlete_id="i1",
        )
    )
    assert captured["method"] == "PUT"
    assert isinstance(captured["data"], list)
    assert len(captured["data"]) == 2
    assert "2" in out


# ---------------------------------------------------------------------------
# Writes — error / destructive paths
# ---------------------------------------------------------------------------


def test_delete_sport_settings_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(delete_sport_settings(settings_id="101", athlete_id="i1"))
    assert "deleted" in out.lower()
    assert captured["method"] == "DELETE"


def test_delete_sport_settings_error(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 404, "message": "Not found"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(delete_sport_settings(settings_id="999", athlete_id="i1"))
    assert "Error deleting sport settings" in out
    assert "Not found" in out


def test_apply_sport_settings_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(apply_sport_settings_to_activities(settings_id="101", athlete_id="i1"))
    assert "Apply request accepted" in out
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/sport-settings/101/apply")


def test_apply_sport_settings_error(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 422, "message": "Settings record invalid"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(apply_sport_settings_to_activities(settings_id="bogus", athlete_id="i1"))
    assert "Error applying sport settings" in out
    assert "Settings record invalid" in out


# ---------------------------------------------------------------------------
# Validation guards
# ---------------------------------------------------------------------------


def test_create_requires_types(monkeypatch):
    async def fake_request(*_args, **_kwargs):  # should not be called
        raise AssertionError("API should not be called when validation fails")

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(create_sport_settings(types=[], athlete_id="i1"))
    assert out.lower().startswith("error")


def test_update_requires_settings(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        raise AssertionError("API should not be called when validation fails")

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(update_sport_settings(settings_id="101", settings={}, athlete_id="i1"))
    assert out.lower().startswith("error")
