"""
Unit tests for Library MCP tools (workouts, folders, plans, tags, sharing).

Mirrors ``tests/test_sport_settings.py``: monkeypatch ``make_intervals_request``
in both ``api.client`` and the tools module, stub the response, then assert on
the formatted string and (for writes) on the captured kwargs (method + URL +
body shape + query params).
"""

import asyncio
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.tools.library import (  # pylint: disable=wrong-import-position
    apply_current_plan_changes,
    create_multiple_workouts,
    create_workout,
    create_workout_folder,
    delete_workout,
    delete_workout_folder,
    duplicate_workouts,
    get_workout,
    list_folder_shared_with,
    list_workout_folders,
    list_workout_tags,
    list_workouts,
    update_folder_shared_with,
    update_plan_workouts,
    update_workout,
    update_workout_folder,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------


SAMPLE_WORKOUT = {
    "id": 555,
    "athlete_id": "i1",
    "name": "VO2 5x4'",
    "type": "Ride",
    "folder_id": 100,
    "moving_time": 3600,
    "target": "POWER",
    "icu_training_load": 80,
    "icu_intensity": 0.92,
    "indoor": True,
    "tags": ["VO2", "key"],
    "workout_doc": {
        "steps": [{"label": "WU"}, {"label": "Main"}, {"label": "CD"}],
        "duration": 3600,
    },
    "description": "5 x 4 min @ 110% FTP",
}

SAMPLE_WORKOUT_2 = {
    "id": 556,
    "name": "Z2 90'",
    "type": "Ride",
    "folder_id": 100,
    "moving_time": 5400,
    "target": "POWER",
}

SAMPLE_FOLDER = {
    "id": 100,
    "athlete_id": "i1",
    "name": "Workouts",
    "type": "FOLDER",
    "num_workouts": 12,
    "visibility": "PRIVATE",
    "activity_types": ["Ride", "Run"],
    "sharedWithCount": 0,
    "duration_weeks": None,
    "hours_per_week_min": None,
    "hours_per_week_max": None,
}

SAMPLE_PLAN = {
    "id": 200,
    "athlete_id": "i1",
    "name": "Base 1",
    "type": "PLAN",
    "num_workouts": 36,
    "visibility": "PRIVATE",
    "activity_types": ["Ride"],
    "duration_weeks": 6,
    "hours_per_week_min": 8,
    "hours_per_week_max": 12,
    "start_date_local": "2026-01-01",
    "sharedWithCount": 1,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_request(monkeypatch, fake_request):
    """Monkeypatch make_intervals_request in client + library module."""
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr("intervals_mcp_server.tools.library.make_intervals_request", fake_request)


# ---------------------------------------------------------------------------
# Workouts — reads
# ---------------------------------------------------------------------------


def test_list_workouts_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return [SAMPLE_WORKOUT, SAMPLE_WORKOUT_2]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_workouts(athlete_id="i1", folder_id=100))
    assert "## Workouts (2)" in out
    assert "VO2 5x4'" in out
    assert "Z2 90'" in out
    assert captured["url"].endswith("/workouts")
    assert captured["params"] == {"folderId": 100}


def test_get_workout_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_WORKOUT

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_workout(workout_id=555, athlete_id="i1"))
    assert "VO2 5x4'" in out
    assert "Steps: 3" in out
    assert "Description" in out


# ---------------------------------------------------------------------------
# Workouts — writes
# ---------------------------------------------------------------------------


def test_create_workout_posts_body(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {"id": 999, "name": "Test"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        create_workout(
            name="Test",
            folder_id=100,
            athlete_id="i1",
            description="warmup",
            type_="Ride",
            workout_doc={"steps": []},
            extra={"target": "POWER"},
        )
    )
    assert "999" in out
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/workouts")
    assert captured["data"]["name"] == "Test"
    assert captured["data"]["folder_id"] == 100
    assert captured["data"]["type"] == "Ride"
    assert captured["data"]["target"] == "POWER"
    assert "workout_doc" in captured["data"]


def test_create_multiple_workouts_sends_array(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return [SAMPLE_WORKOUT, SAMPLE_WORKOUT_2]

    _patch_request(monkeypatch, fake_request)
    payload = [
        {"name": "A", "folder_id": 100},
        {"name": "B", "folder_id": 100},
    ]
    out = asyncio.run(create_multiple_workouts(workouts=payload, athlete_id="i1"))
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/workouts/bulk")
    # Critical: body is a list, not a dict
    assert isinstance(captured["data"], list)
    assert len(captured["data"]) == 2
    assert "Created 2 workouts" in out


def test_update_workout_puts_body(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {"id": 555}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        update_workout(
            workout_id=555,
            updates={"name": "VO2 5x5'", "icu_training_load": 90},
            athlete_id="i1",
        )
    )
    assert "updated" in out.lower()
    assert captured["method"] == "PUT"
    assert captured["data"] == {"name": "VO2 5x5'", "icu_training_load": 90}
    assert captured["url"].endswith("/workouts/555")


def test_delete_workout_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(delete_workout(workout_id=555, athlete_id="i1", others=True))
    assert "deleted" in out.lower()
    assert captured["method"] == "DELETE"
    assert captured["params"] == {"others": "true"}


def test_delete_workout_error(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 404, "message": "Not found"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(delete_workout(workout_id=999, athlete_id="i1"))
    assert "Error deleting workout" in out
    assert "Not found" in out


def test_duplicate_workouts_posts_body(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return [{"id": 1001}, {"id": 1002}]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        duplicate_workouts(
            workout_ids=[555, 556],
            num_copies=2,
            weeks_between=1,
            athlete_id="i1",
        )
    )
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/duplicate-workouts")
    assert captured["data"]["workoutIds"] == [555, 556]
    assert captured["data"]["numCopies"] == 2
    assert captured["data"]["weeksBetween"] == 1
    assert "Duplicated 2 workouts" in out


# ---------------------------------------------------------------------------
# Folders — reads + writes
# ---------------------------------------------------------------------------


def test_list_workout_folders_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return [SAMPLE_FOLDER, SAMPLE_PLAN]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_workout_folders(athlete_id="i1"))
    assert "## Folders & Plans (2)" in out
    assert "Workouts" in out
    assert "Base 1" in out
    assert "PLAN" in out


def test_create_workout_folder_posts_body(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return SAMPLE_PLAN

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        create_workout_folder(
            name="Base 1",
            type_="PLAN",
            athlete_id="i1",
            extra={"start_date_local": "2026-01-01", "duration_weeks": 6},
        )
    )
    assert captured["method"] == "POST"
    assert captured["data"]["name"] == "Base 1"
    assert captured["data"]["type"] == "PLAN"
    assert captured["data"]["duration_weeks"] == 6
    assert "200" in out


def test_update_workout_folder_puts_body(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {"id": 100}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        update_workout_folder(
            folder_id=100,
            updates={"name": "Renamed"},
            athlete_id="i1",
        )
    )
    assert "updated" in out.lower()
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/folders/100")
    assert captured["data"] == {"name": "Renamed"}


def test_delete_workout_folder_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(delete_workout_folder(folder_id=100, athlete_id="i1"))
    assert "deleted" in out.lower()
    assert captured["method"] == "DELETE"
    assert captured["url"].endswith("/folders/100")


def test_delete_workout_folder_error(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 403, "message": "Forbidden"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(delete_workout_folder(folder_id=100, athlete_id="i1"))
    assert "Error deleting folder" in out
    assert "Forbidden" in out


def test_update_plan_workouts_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return [{"id": 1}, {"id": 2}, {"id": 3}]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        update_plan_workouts(
            folder_id=200,
            oldest=0,
            newest=14,
            updates={"hide_from_athlete": True},
            athlete_id="i1",
        )
    )
    assert captured["method"] == "PUT"
    assert captured["params"] == {"oldest": 0, "newest": 14}
    assert captured["data"] == {"hide_from_athlete": True}
    assert "3" in out


def test_update_plan_workouts_error(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 422, "message": "Bad range"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        update_plan_workouts(
            folder_id=200,
            oldest=999,
            newest=0,
            updates={"hide_from_athlete": False},
            athlete_id="i1",
        )
    )
    assert "Error updating plan workouts" in out
    assert "Bad range" in out


# ---------------------------------------------------------------------------
# Sharing
# ---------------------------------------------------------------------------


def test_list_folder_shared_with_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return [
            {"id": "i9000", "name": "Coach Bob", "city": "NYC", "canEdit": True},
            {"id": "i9001", "name": "Athlete Alice"},
        ]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_folder_shared_with(folder_id=200, athlete_id="i1"))
    assert "Shared with (2)" in out
    assert "Coach Bob" in out
    assert "Athlete Alice" in out
    assert "canEdit" in out


def test_update_folder_shared_with_puts_array(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return [{"id": "i9000"}]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        update_folder_shared_with(
            folder_id=200,
            shared_with=[{"id": "i9000", "canEdit": True}],
            athlete_id="i1",
        )
    )
    assert captured["method"] == "PUT"
    assert isinstance(captured["data"], list)
    assert "1 athlete" in out


# ---------------------------------------------------------------------------
# Tags + plan changes
# ---------------------------------------------------------------------------


def test_list_workout_tags_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return [{"name": "VO2"}, {"name": "key"}, {"name": "endurance"}]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(list_workout_tags(athlete_id="i1"))
    assert "Workout Tags (3)" in out
    assert "VO2" in out
    assert "endurance" in out


def test_apply_current_plan_changes_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {"applied": 7}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(apply_current_plan_changes(athlete_id="i1"))
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/apply-plan-changes")
    assert "Applied: 7" in out


def test_apply_current_plan_changes_error(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 500, "message": "Server error"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(apply_current_plan_changes(athlete_id="i1"))
    assert "Error applying current plan changes" in out
    assert "Server error" in out
