"""
Unit tests for the event-bulk-operation MCP tools in
`intervals_mcp_server.tools.events_extras`.

Patterned after `tests/test_server.py`: each test monkeypatches
`make_intervals_request` (in both `api.client` and the tool module) with a
fake coroutine that records the call and returns a stub response.
"""

import asyncio
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

# pylint: disable=wrong-import-position
from intervals_mcp_server.tools.events_extras import (
    apply_plan,
    create_multiple_events,
    delete_events_bulk,
    duplicate_events,
    list_event_tags,
    mark_event_as_done,
    update_events_in_range,
)


def _patch_request(monkeypatch, fake):
    """Patch make_intervals_request in both the api module and the tool module."""
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake)
    monkeypatch.setattr("intervals_mcp_server.tools.events_extras.make_intervals_request", fake)


def test_mark_event_as_done_returns_activity(monkeypatch):
    """Confirms the response is parsed as a new ACTIVITY (not an event)."""
    captured = {}
    activity = {
        "id": "act-9001",
        "type": "Ride",
        "start_date_local": "2026-04-25T08:00:00",
        "name": "VO2 4x4",
        "moving_time": 3600,
        "distance": 30000,
        "icu_training_load": 75,
    }

    async def fake_request(url, api_key=None, params=None, method="GET", data=None):
        captured["url"] = url
        captured["method"] = method
        return activity

    _patch_request(monkeypatch, fake_request)
    result = asyncio.run(mark_event_as_done(event_id="42", athlete_id="i1"))

    assert "events/42/mark-done" in captured["url"]
    assert captured["method"] == "POST"
    # Activity-shaped output, not event-shaped
    assert "Activity ID: act-9001" in result
    assert "Marked event as done" in result
    assert "Training load: 75" in result


def test_apply_plan_happy_path(monkeypatch):
    """Body shape includes start_date_local + folder_id; response renders as a table."""
    captured = {}

    async def fake_request(url, api_key=None, params=None, method="GET", data=None):
        captured["url"] = url
        captured["method"] = method
        captured["data"] = data
        return [
            {"id": 1, "start_date_local": "2026-05-01", "category": "WORKOUT", "name": "Z2"},
            {"id": 2, "start_date_local": "2026-05-02", "category": "WORKOUT", "name": "Tempo"},
        ]

    _patch_request(monkeypatch, fake_request)
    result = asyncio.run(apply_plan(start_date_local="2026-05-01", folder_id=777, athlete_id="i1"))
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/events/apply-plan")
    assert captured["data"] == {"start_date_local": "2026-05-01", "folder_id": 777}
    assert "Applied plan: 2 event(s) created" in result
    assert "Z2" in result and "Tempo" in result


def test_apply_plan_error_path(monkeypatch):
    """4xx response surfaces as a clean error message instead of crashing."""

    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 422, "message": "folder_id not found"}

    _patch_request(monkeypatch, fake_request)
    result = asyncio.run(
        apply_plan(start_date_local="2026-05-01", folder_id=999_999, athlete_id="i1")
    )
    assert "Error applying plan" in result
    assert "folder_id not found" in result


def test_create_multiple_events_sends_list_body(monkeypatch):
    """Confirms the request body is sent as a LIST of event dicts (not a wrapper)."""
    captured = {}

    async def fake_request(url, api_key=None, params=None, method="GET", data=None):
        captured["data"] = data
        captured["params"] = params
        captured["method"] = method
        captured["url"] = url
        return [
            {"id": 100, "start_date_local": "2026-04-26", "category": "WORKOUT", "name": "A"},
            {"id": 101, "start_date_local": "2026-04-27", "category": "NOTE", "name": "B"},
        ]

    _patch_request(monkeypatch, fake_request)
    events_in = [
        {"start_date_local": "2026-04-26", "category": "WORKOUT", "type": "Ride", "name": "A"},
        {"start_date_local": "2026-04-27", "category": "NOTE", "name": "B"},
    ]
    result = asyncio.run(create_multiple_events(events=events_in, athlete_id="i1"))

    assert captured["method"] == "POST"
    assert captured["url"].endswith("/events/bulk")
    # Body MUST be a list, not a dict wrapper
    assert isinstance(captured["data"], list)
    assert captured["data"] == events_in
    # Query flags forwarded as lowercase strings
    assert captured["params"]["upsert"] == "false"
    assert captured["params"]["upsertOnUid"] == "false"
    assert "Created 2 event(s)" in result


def test_delete_events_bulk_happy_path(monkeypatch):
    """Body shape: list of {id} or {external_id} dicts. Response: {eventsDeleted: N}."""
    captured = {}

    async def fake_request(url, api_key=None, params=None, method="GET", data=None):
        captured["data"] = data
        captured["method"] = method
        captured["url"] = url
        return {"eventsDeleted": 3}

    _patch_request(monkeypatch, fake_request)
    body_in = [{"id": 1}, {"id": 2}, {"external_id": "ext-77"}]
    result = asyncio.run(delete_events_bulk(events=body_in, athlete_id="i1"))

    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/events/bulk-delete")
    assert captured["data"] == body_in
    assert "Deleted 3 event(s)" in result


def test_duplicate_events_happy_path(monkeypatch):
    """Body shape: numCopies, weeksBetween, eventIds. Response: list of new events."""
    captured = {}

    async def fake_request(url, api_key=None, params=None, method="GET", data=None):
        captured["data"] = data
        captured["method"] = method
        captured["url"] = url
        return [
            {"id": 200, "start_date_local": "2026-05-08", "category": "WORKOUT", "name": "Copy 1"},
            {"id": 201, "start_date_local": "2026-05-15", "category": "WORKOUT", "name": "Copy 2"},
        ]

    _patch_request(monkeypatch, fake_request)
    result = asyncio.run(
        duplicate_events(event_ids=[42], num_copies=2, weeks_between=1, athlete_id="i1")
    )
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/duplicate-events")
    assert captured["data"] == {"numCopies": 2, "weeksBetween": 1, "eventIds": [42]}
    assert "Duplicated 2 event(s)" in result


def test_update_events_in_range_happy_path(monkeypatch):
    """Only hide_from_athlete and athlete_cannot_edit are sent, plus oldest/newest params."""
    captured = {}

    async def fake_request(url, api_key=None, params=None, method="GET", data=None):
        captured["data"] = data
        captured["params"] = params
        captured["method"] = method
        captured["url"] = url
        return [{"id": 1, "start_date_local": "2026-05-10", "category": "WORKOUT", "name": "X"}]

    _patch_request(monkeypatch, fake_request)
    result = asyncio.run(
        update_events_in_range(
            start_date="2026-05-01",
            end_date="2026-05-31",
            hide_from_athlete=True,
            athlete_id="i1",
        )
    )
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/events")
    assert captured["data"] == {"hide_from_athlete": True}
    assert captured["params"] == {"oldest": "2026-05-01", "newest": "2026-05-31"}
    assert "Updated 1 event(s)" in result


def test_list_event_tags_happy_path(monkeypatch):
    """The OpenAPI spec returns array<string>; live probe confirmed []."""
    captured = {}

    async def fake_request(url, api_key=None, params=None, method="GET", data=None):
        captured["url"] = url
        captured["method"] = method
        return ["A-race", "recovery", "openers"]

    _patch_request(monkeypatch, fake_request)
    result = asyncio.run(list_event_tags(athlete_id="i1"))

    assert captured["method"] == "GET"
    assert captured["url"].endswith("/event-tags")
    assert "A-race" in result
    assert "recovery" in result
    assert "openers" in result
