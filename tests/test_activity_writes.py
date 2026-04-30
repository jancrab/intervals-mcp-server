"""Unit tests for activity-write MCP tools.

Mirrors `tests/test_wellness_writes.py`: monkeypatches `make_intervals_request`
(or `_put_json_body` for the array-bodied endpoints) and asserts on the body
shape sent to the API and the formatted result string.
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

from intervals_mcp_server.tools.activity_writes import (  # pylint: disable=wrong-import-position
    delete_activity,
    delete_intervals,
    link_activity_to_event,
    split_interval,
    update_activity,
    update_activity_streams,
    update_interval,
    update_intervals,
)


# ---------------------------------------------------------------------------
# update_activity — happy path + body-shape test
# ---------------------------------------------------------------------------


def test_update_activity_happy_path(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["url"] = kwargs.get("url")
        captured["method"] = kwargs.get("method")
        captured["data"] = kwargs.get("data")
        return {"id": "i142786468", **kwargs.get("data", {})}

    monkeypatch.setattr(
        "intervals_mcp_server.tools.activity_writes.make_intervals_request", fake_request
    )
    result = asyncio.run(
        update_activity(
            activity_id="i142786468",
            name="Z2 endurance",
            feel=4,
            athlete_id="i1",
        )
    )
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/activity/i142786468")
    assert "Activity updated" in result
    assert "Z2 endurance" in result


def test_update_activity_body_shape_only_provided_fields(monkeypatch):
    """Only the parameters the caller passed should make it into the JSON body."""
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["data"] = kwargs.get("data")
        return {"id": "i142786468", **kwargs.get("data", {})}

    monkeypatch.setattr(
        "intervals_mcp_server.tools.activity_writes.make_intervals_request", fake_request
    )
    asyncio.run(
        update_activity(
            activity_id="i142786468",
            description="solid Z2 day",
            commute=False,
            athlete_id="i1",
        )
    )
    body = captured["data"]
    assert set(body.keys()) == {"description", "commute"}, f"unexpected keys in body: {body.keys()}"
    assert body["description"] == "solid Z2 day"
    assert body["commute"] is False


def test_update_activity_other_fields_merged(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["data"] = kwargs.get("data")
        return {"id": "i142786468", **kwargs.get("data", {})}

    monkeypatch.setattr(
        "intervals_mcp_server.tools.activity_writes.make_intervals_request", fake_request
    )
    asyncio.run(
        update_activity(
            activity_id="i142786468",
            name="renamed",
            other_fields={"icu_rpe": 7},
            athlete_id="i1",
        )
    )
    assert captured["data"]["icu_rpe"] == 7
    assert captured["data"]["name"] == "renamed"


# ---------------------------------------------------------------------------
# delete_activity — happy + 404 error
# ---------------------------------------------------------------------------


def test_delete_activity_happy(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["url"] = kwargs.get("url")
        captured["method"] = kwargs.get("method")
        return {}

    monkeypatch.setattr(
        "intervals_mcp_server.tools.activity_writes.make_intervals_request", fake_request
    )
    result = asyncio.run(delete_activity(activity_id="i142786468", athlete_id="i1"))
    assert captured["method"] == "DELETE"
    assert captured["url"].endswith("/activity/i142786468")
    assert "Deleted activity" in result
    assert "i142786468" in result


def test_delete_activity_404_user_friendly(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return {
            "error": True,
            "status_code": 404,
            "message": "404 Not Found: The requested endpoint or ID doesn't exist.",
        }

    monkeypatch.setattr(
        "intervals_mcp_server.tools.activity_writes.make_intervals_request", fake_request
    )
    result = asyncio.run(delete_activity(activity_id="i_does_not_exist", athlete_id="i1"))
    assert "Error" in result
    assert "Not Found" in result or "doesn't exist" in result


# ---------------------------------------------------------------------------
# update_activity_streams — happy
# ---------------------------------------------------------------------------


def test_update_activity_streams_dict_input(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_put_json(url, _api_key, body, params=None):
        captured["url"] = url
        captured["body"] = body
        captured["params"] = params
        return body  # echo

    monkeypatch.setattr("intervals_mcp_server.tools.activity_writes._put_json_body", fake_put_json)
    result = asyncio.run(
        update_activity_streams(
            activity_id="i142786468",
            streams={"watts": [100.0, 110.0, 120.0], "heartrate": [120, 121, 122]},
            athlete_id="i1",
        )
    )
    assert captured["url"].endswith("/activity/i142786468/streams")
    assert isinstance(captured["body"], list)
    types = {s["type"] for s in captured["body"]}
    assert types == {"watts", "heartrate"}
    assert "streams updated" in result.lower()


# ---------------------------------------------------------------------------
# update_intervals — happy + body-shape test
# ---------------------------------------------------------------------------


def test_update_intervals_happy(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_put_json(url, _api_key, body, params=None):
        captured["url"] = url
        captured["body"] = body
        return body

    monkeypatch.setattr("intervals_mcp_server.tools.activity_writes._put_json_body", fake_put_json)
    intervals = [
        {
            "label": "WU",
            "type": "WARMUP",
            "start_index": 0,
            "end_index": 600,
            "elapsed_time": 600,
            "distance": 5000,
            "average_watts": 150,
            "average_heartrate": 130,
        },
        {
            "label": "Threshold",
            "type": "WORK",
            "start_index": 600,
            "end_index": 1800,
            "elapsed_time": 1200,
            "distance": 10000,
            "average_watts": 250,
            "average_heartrate": 165,
        },
    ]
    result = asyncio.run(
        update_intervals(activity_id="i142786468", intervals=intervals, athlete_id="i1")
    )
    assert captured["url"].endswith("/activity/i142786468/intervals")
    assert "Intervals updated" in result
    assert "Threshold" in result


def test_update_intervals_body_is_list_of_dicts(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_put_json(_url, _api_key, body, params=None):
        captured["body"] = body
        return body

    monkeypatch.setattr("intervals_mcp_server.tools.activity_writes._put_json_body", fake_put_json)
    intervals = [{"label": "A"}, {"label": "B"}]
    asyncio.run(update_intervals(activity_id="i1", intervals=intervals, athlete_id="i1"))
    body = captured["body"]
    assert isinstance(body, list)
    assert all(isinstance(e, dict) for e in body)
    assert [e["label"] for e in body] == ["A", "B"]


# ---------------------------------------------------------------------------
# update_interval — happy
# ---------------------------------------------------------------------------


def test_update_interval_happy(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["url"] = kwargs.get("url")
        captured["method"] = kwargs.get("method")
        captured["data"] = kwargs.get("data")
        return kwargs.get("data", {})

    monkeypatch.setattr(
        "intervals_mcp_server.tools.activity_writes.make_intervals_request", fake_request
    )
    result = asyncio.run(
        update_interval(
            activity_id="i142786468",
            interval_id="3",
            interval={"label": "VO2 #1", "type": "WORK"},
            athlete_id="i1",
        )
    )
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/activity/i142786468/intervals/3")
    assert "Interval updated" in result
    assert "VO2 #1" in result


# ---------------------------------------------------------------------------
# delete_intervals — happy
# ---------------------------------------------------------------------------


def test_delete_intervals_wraps_ids(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_put_json(url, _api_key, body, params=None):
        captured["url"] = url
        captured["body"] = body
        return []  # remaining intervals

    monkeypatch.setattr("intervals_mcp_server.tools.activity_writes._put_json_body", fake_put_json)
    result = asyncio.run(
        delete_intervals(
            activity_id="i142786468",
            interval_ids=[1, 2, 3],
            athlete_id="i1",
        )
    )
    assert captured["url"].endswith("/activity/i142786468/delete-intervals")
    assert captured["body"] == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert "deleted" in result.lower()
    assert "Requested deletions: 3" in result


# ---------------------------------------------------------------------------
# split_interval — happy (query param, no body)
# ---------------------------------------------------------------------------


def test_split_interval_uses_query_param(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_put_json(url, _api_key, body, params=None):
        captured["url"] = url
        captured["body"] = body
        captured["params"] = params
        return [
            {"label": "first half", "elapsed_time": 600},
            {"label": "second half", "elapsed_time": 600},
        ]

    monkeypatch.setattr("intervals_mcp_server.tools.activity_writes._put_json_body", fake_put_json)
    result = asyncio.run(
        split_interval(activity_id="i142786468", split_at_secs=900, athlete_id="i1")
    )
    assert captured["url"].endswith("/activity/i142786468/split-interval")
    assert captured["body"] is None
    assert captured["params"] == {"splitAt": 900}
    assert "split" in result.lower()
    assert "first half" in result


# ---------------------------------------------------------------------------
# link_activity_to_event (v1.3.1) — orphan-Zwift-workout resolution
# ---------------------------------------------------------------------------


def test_link_activity_to_event_success(monkeypatch):
    """Happy path: 200 with the linked activity payload. Returned dict has
    status=linked + activity_id/event_id correctly populated. URL is the
    activity-scoped PUT and body carries paired_event_id as an int."""
    import json as _json

    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["url"] = kwargs.get("url")
        captured["method"] = kwargs.get("method")
        captured["data"] = kwargs.get("data")
        # Server returns the canonical Activity record on success.
        return {"id": "i999", "paired_event_id": 107189636}

    monkeypatch.setattr(
        "intervals_mcp_server.tools.activity_writes.make_intervals_request", fake_request
    )
    raw = asyncio.run(
        link_activity_to_event(
            activity_id="18303442074",
            event_id="107189636",
            athlete_id="i1",
        )
    )
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/activity/18303442074")
    assert captured["data"] == {"paired_event_id": 107189636}

    payload = _json.loads(raw)
    assert payload["status"] == "linked"
    # On success the canonical i… ID from the response wins.
    assert payload["activity_id"] == "i999"
    assert payload["event_id"] == "107189636"


def test_link_activity_to_event_404(monkeypatch):
    """404 (e.g. activity not found): structured error response, API's
    verbatim message preserved — not remapped to a friendlier wording."""
    import json as _json

    api_msg = "404 Not Found: The requested endpoint or ID doesn't exist."

    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 404, "message": api_msg}

    monkeypatch.setattr(
        "intervals_mcp_server.tools.activity_writes.make_intervals_request", fake_request
    )
    raw = asyncio.run(
        link_activity_to_event(
            activity_id="i_does_not_exist",
            event_id="107189636",
            athlete_id="i1",
        )
    )
    payload = _json.loads(raw)
    assert payload["status"] == "error"
    assert payload["http_status"] == 404
    assert payload["message"] == api_msg


def test_link_activity_to_event_422_returns_draft_unrecoverable(monkeypatch):
    """v1.3.2: 422 from the link endpoint signals the activity is too deep
    in pre-normalization for the link path to resolve (typical Zwift
    built-in test case — uploads via Zwift→Strava→intervals.icu bypass
    normalization). The tool surfaces this as a structured
    `draft_unrecoverable` envelope mirroring v1.3.0's pattern in
    `get_activity_intervals` (which uses `draft`). The message must include
    the activity URL and the manual-rename remediation so the user/model
    has a clear next step."""
    import json as _json

    async def fake_request(*_args, **_kwargs):
        return {
            "error": True,
            "status_code": 422,
            "message": "422 Unprocessable: workout structure does not match planned event",
        }

    monkeypatch.setattr(
        "intervals_mcp_server.tools.activity_writes.make_intervals_request", fake_request
    )
    raw = asyncio.run(
        link_activity_to_event(
            activity_id="18303442074",
            event_id="107189636",
            athlete_id="i1",
        )
    )
    payload = _json.loads(raw)
    assert payload["status"] == "draft_unrecoverable"
    # URL + remediation must be present for the user/model to act.
    assert "https://intervals.icu/activities/18303442074" in payload["message"]
    assert "give the activity a name, and save" in payload["message"]
    # The activity's web URL is rendered with the raw upstream ID verbatim
    # (intervals.icu's web URL accepts both forms).
    assert "18303442074" in payload["message"]
    # No `http_status` key on draft_unrecoverable — that's the v1.3.1
    # generic-error shape, not what we use here.
    assert "http_status" not in payload


def test_link_activity_to_event_other_4xx_unchanged(monkeypatch):
    """v1.3.2: non-422 4xx errors keep the v1.3.1 verbatim-API-message
    envelope. Don't widen the 422 translation to other status codes —
    real failures (404 not found, 401 auth) should NOT be masked behind
    draft-unrecoverable wording."""
    import json as _json

    api_msg = "404 Not Found: The requested endpoint or ID doesn't exist."

    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 404, "message": api_msg}

    monkeypatch.setattr(
        "intervals_mcp_server.tools.activity_writes.make_intervals_request", fake_request
    )
    raw = asyncio.run(
        link_activity_to_event(
            activity_id="i_does_not_exist",
            event_id="107189636",
            athlete_id="i1",
        )
    )
    payload = _json.loads(raw)
    assert payload["status"] == "error"
    assert payload["http_status"] == 404
    assert payload["message"] == api_msg


def test_link_activity_to_event_success_unchanged(monkeypatch):
    """v1.3.2 must not touch the 200 success path. The structured
    {"status": "linked", "activity_id", "event_id"} envelope is unchanged."""
    import json as _json

    async def fake_request(*_args, **_kwargs):
        return {"id": "i142786468", "paired_event_id": 107189636}

    monkeypatch.setattr(
        "intervals_mcp_server.tools.activity_writes.make_intervals_request", fake_request
    )
    raw = asyncio.run(
        link_activity_to_event(
            activity_id="18303442074",
            event_id="107189636",
            athlete_id="i1",
        )
    )
    payload = _json.loads(raw)
    assert payload["status"] == "linked"
    assert payload["activity_id"] == "i142786468"  # canonical i… form from response
    assert payload["event_id"] == "107189636"


def test_link_activity_to_event_validates_activity_id():
    """Empty activity_id raises ValueError before any API call. No mock
    needed — the validation gate must fire before the network hit."""
    import pytest

    with pytest.raises(ValueError, match="activity_id"):
        asyncio.run(
            link_activity_to_event(
                activity_id="",
                event_id="107189636",
            )
        )


def test_link_activity_to_event_validates_event_id():
    """Non-numeric event_id raises ValueError before any API call.
    intervals.icu's event IDs are always positive integers."""
    import pytest

    with pytest.raises(ValueError, match="event_id"):
        asyncio.run(
            link_activity_to_event(
                activity_id="18303442074",
                event_id="not-a-number",
            )
        )


