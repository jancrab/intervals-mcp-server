"""
Unit tests for the routes + gear MCP tools.

Mirrors tests/test_sport_settings.py: monkeypatch ``make_intervals_request``
in both the api.client and the tools module, then assert on formatted
strings and captured request kwargs.
"""

import asyncio
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.tools.routes_gear import (  # pylint: disable=wrong-import-position
    check_route_merge,
    create_gear,
    create_gear_reminder,
    delete_gear,
    delete_gear_reminder,
    get_athlete_route,
    list_athlete_routes,
    list_gear,
    recalc_gear_distance,
    replace_gear,
    update_athlete_route,
    update_gear,
    update_gear_reminder,
)


# ---------------------------------------------------------------------------
# Sample data (shapes verified against live API)
# ---------------------------------------------------------------------------

SAMPLE_GEAR_BIKE = {
    "id": "b12645089",
    "athlete_id": "i1",
    "type": "Bike",
    "name": "Silver Arrow",
    "purchased": None,
    "notes": None,
    "distance": 1353164.0,
    "time": 109554.0,
    "activities": 22,
    "use_elapsed_time": False,
    "retired": None,
    "component_ids": None,
    "reminders": [],
    "activity_filters": None,
    "component": False,
}

SAMPLE_GEAR_BIKE_2 = {
    "id": "b13469702",
    "athlete_id": "i1",
    "type": "Bike",
    "name": "Green Bullet",
    "distance": 6620508.0,
    "time": 1020818.0,
    "activities": 140,
    "use_elapsed_time": False,
    "retired": None,
    "component_ids": ["c1", "c2"],
    "reminders": [{"id": 1, "name": "Replace chain", "percent_used": 87}],
    "component": False,
}

SAMPLE_ROUTE = {
    "athlete_id": "i1",
    "route_id": 555,
    "name": "Vasa loop",
    "description": "Classic loop along the lake",
    "commute": False,
    "rename_activities": False,
    "tags": ["lake", "easy"],
    "distance": 23400.0,
    "elevation_gain": 145.0,
    "activity_count": 12,
    "latlngs": [[59.3, 18.0], [59.31, 18.01]],
}

SAMPLE_REMINDER = {
    "id": 42,
    "gear_id": "b12645089",
    "name": "Replace chain",
    "distance": 5000000.0,
    "time": None,
    "days": None,
    "activities": None,
    "starting_distance": 0,
    "percent_used": 27.1,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_request(monkeypatch, fake_request):
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.routes_gear.make_intervals_request", fake_request
    )


# ---------------------------------------------------------------------------
# Routes (4)
# ---------------------------------------------------------------------------


def test_list_athlete_routes_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return [SAMPLE_ROUTE]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_athlete_routes(athlete_id="i1"))
    assert "Athlete routes (1)" in out
    assert "Vasa loop" in out
    assert "23.4 km" in out


def test_list_athlete_routes_empty(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return []

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_athlete_routes(athlete_id="i1"))
    assert "No routes found" in out


def test_get_athlete_route_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured["url"] = kwargs.get("url")
        return SAMPLE_ROUTE

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_athlete_route(route_id="555", athlete_id="i1"))
    assert "Vasa loop" in out
    assert "555" in out
    assert captured["url"].endswith("/routes/555")


def test_update_athlete_route_puts_body(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {"route_id": 555, "name": "Vasa loop v2"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        update_athlete_route(
            route_id="555",
            updates={"name": "Vasa loop v2", "tags": ["lake"]},
            athlete_id="i1",
        )
    )
    assert "updated" in out.lower()
    assert "555" in out
    assert captured["method"] == "PUT"
    assert captured["data"]["name"] == "Vasa loop v2"
    assert captured["url"].endswith("/routes/555")


def test_check_route_merge_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured["url"] = kwargs.get("url")
        return {"similarity": 0.92, "can_merge": True}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(check_route_merge(route_id="555", other_id="556", athlete_id="i1"))
    assert "Route similarity" in out
    assert "0.92" in out
    assert captured["url"].endswith("/routes/555/similarity/556")


# ---------------------------------------------------------------------------
# Gear (9)
# ---------------------------------------------------------------------------


def test_list_gear_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return [SAMPLE_GEAR_BIKE, SAMPLE_GEAR_BIKE_2]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_gear(athlete_id="i1"))
    assert "Gear (2)" in out
    assert "Silver Arrow" in out
    assert "Green Bullet" in out
    assert "Bike" in out


def test_list_gear_csv_mode(monkeypatch):
    """list_gear in csv mode must hit _fetch_csv (not the JSON helper)."""

    async def fake_csv(url_path, _api_key):
        assert url_path.endswith("/gear.csv")
        return "id,type,name\nb1,Bike,Silver Arrow\n"

    async def fake_request(*_args, **_kwargs):
        raise AssertionError("make_intervals_request should not be called in CSV mode")

    monkeypatch.setattr("intervals_mcp_server.tools.routes_gear._fetch_csv", fake_csv)
    _patch_request(monkeypatch, fake_request)

    out = asyncio.run(list_gear(athlete_id="i1", format="csv"))
    assert "```csv" in out
    assert "Silver Arrow" in out


def test_create_gear_posts_body(monkeypatch):
    """create_gear must POST a Gear-shaped body."""
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {"id": "b999", "name": "New Bike", "type": "Bike"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        create_gear(
            gear={"type": "Bike", "name": "New Bike", "purchased": "2026-04-26"},
            athlete_id="i1",
        )
    )
    assert "b999" in out
    assert captured["method"] == "POST"
    assert captured["data"]["type"] == "Bike"
    assert captured["data"]["name"] == "New Bike"
    assert captured["url"].endswith("/gear")


def test_create_gear_requires_type(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        raise AssertionError("API should not be called when validation fails")

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(create_gear(gear={"name": "no type"}, athlete_id="i1"))
    assert out.lower().startswith("error")
    assert "type" in out.lower()


def test_update_gear_puts_body(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {"id": "b12645089", "name": "Silver Arrow Mk2"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        update_gear(
            gear_id="b12645089",
            gear={"name": "Silver Arrow Mk2"},
            athlete_id="i1",
        )
    )
    assert "updated" in out.lower()
    assert captured["method"] == "PUT"
    assert captured["data"] == {"name": "Silver Arrow Mk2"}


def test_delete_gear_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(delete_gear(gear_id="b13212807", athlete_id="i1"))
    assert "deleted" in out.lower()
    assert captured["method"] == "DELETE"


def test_delete_gear_error(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 404, "message": "Not found"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(delete_gear(gear_id="bogus", athlete_id="i1"))
    assert "Error deleting gear" in out
    assert "Not found" in out


def test_recalc_gear_distance_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {
            "id": "b13469702",
            "distance": 6620508.0,
            "time": 1020818.0,
            "activities": 140,
        }

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(recalc_gear_distance(gear_id="b13469702", athlete_id="i1"))
    assert "b13469702" in out
    assert "recalculated" in out.lower() or "6620.5 km" in out or "6620.5" in out
    assert captured["url"].endswith("/gear/b13469702/calc")
    # Default GET — `method` arg may be absent for GETs in some helpers
    assert captured.get("method") in (None, "GET")


def test_replace_gear_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {"id": "b14621952", "type": "Bike", "name": "Golden Arrow"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        replace_gear(
            gear_id="b13212807",
            replacement={"type": "Bike", "name": "Golden Arrow"},
            athlete_id="i1",
        )
    )
    assert "replaced" in out.lower()
    assert captured["method"] == "POST"
    assert captured["data"]["type"] == "Bike"
    assert captured["url"].endswith("/gear/b13212807/replace")


def test_create_gear_reminder_posts_body(monkeypatch):
    """create_gear_reminder must POST a GearReminder-shaped body."""
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return SAMPLE_REMINDER

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        create_gear_reminder(
            gear_id="b12645089",
            reminder={"name": "Replace chain", "distance": 5000000.0},
            athlete_id="i1",
        )
    )
    assert "Reminder" in out
    assert "Replace chain" in out
    assert captured["method"] == "POST"
    assert captured["data"]["name"] == "Replace chain"
    assert captured["data"]["distance"] == 5000000.0
    assert captured["url"].endswith("/gear/b12645089/reminder")


def test_create_gear_reminder_requires_name(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        raise AssertionError("API should not be called when validation fails")

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        create_gear_reminder(
            gear_id="b12645089",
            reminder={"distance": 1000000.0},
            athlete_id="i1",
        )
    )
    assert out.lower().startswith("error")


def test_update_gear_reminder_includes_query(monkeypatch):
    """update_gear_reminder must pass reset+snoozeDays as query params."""
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return SAMPLE_REMINDER

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        update_gear_reminder(
            gear_id="b12645089",
            reminder_id="42",
            reminder={"name": "Replace chain v2"},
            athlete_id="i1",
            reset=True,
            snooze_days=7,
        )
    )
    assert "Reminder" in out
    assert captured["method"] == "PUT"
    assert captured["params"]["reset"] == "true"
    assert captured["params"]["snoozeDays"] == 7
    assert captured["url"].endswith("/gear/b12645089/reminder/42")


def test_delete_gear_reminder_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(delete_gear_reminder(gear_id="b12645089", reminder_id="42", athlete_id="i1"))
    assert "deleted" in out.lower()
    assert captured["method"] == "DELETE"
    assert captured["url"].endswith("/gear/b12645089/reminder/42")
