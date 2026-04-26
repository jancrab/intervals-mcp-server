"""Unit tests for wellness-write MCP tools.

Mirrors patterns in tests/test_server.py: monkeypatches `make_intervals_request`
to mock API responses and asserts the formatted output strings.
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

from intervals_mcp_server.tools.wellness_writes import (  # pylint: disable=wrong-import-position
    get_wellness_record,
    update_wellness_record,
    update_wellness_record_today,
    update_wellness_records_bulk,
    upload_wellness_csv,
)


# ---------------------------------------------------------------------------
# get_wellness_record — happy path
# ---------------------------------------------------------------------------


def test_get_wellness_record_returns_formatted(monkeypatch):
    sample = {
        "id": "2026-04-25",
        "hrv": 52,
        "restingHR": 48,
        "fatigue": 3,
        "locked": True,
    }

    async def fake_request(*_args, **_kwargs):
        return sample

    monkeypatch.setattr(
        "intervals_mcp_server.tools.wellness_writes.make_intervals_request", fake_request
    )
    result = asyncio.run(get_wellness_record(date="2026-04-25", athlete_id="i1"))
    assert "Wellness record" in result
    assert "2026-04-25" in result
    assert "Locked" in result
    assert "True" in result


# ---------------------------------------------------------------------------
# update_wellness_record — happy + locked default + locked=False warning
# ---------------------------------------------------------------------------


def test_update_wellness_record_defaults_locked_true(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["data"] = kwargs.get("data")
        captured["method"] = kwargs.get("method")
        captured["url"] = kwargs.get("url")
        return {"id": "2026-04-25", **kwargs.get("data", {})}

    monkeypatch.setattr(
        "intervals_mcp_server.tools.wellness_writes.make_intervals_request", fake_request
    )
    result = asyncio.run(
        update_wellness_record(
            date="2026-04-25",
            record={"hrv": 55, "fatigue": 2},
            athlete_id="i1",
        )
    )
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/wellness/2026-04-25")
    assert captured["data"]["locked"] is True, "locked should default to True"
    assert captured["data"]["hrv"] == 55
    assert "updated" in result
    assert "True" in result


def test_update_wellness_record_explicit_locked_false_warns(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["data"] = kwargs.get("data")
        return {"id": "2026-04-25", **kwargs.get("data", {})}

    monkeypatch.setattr(
        "intervals_mcp_server.tools.wellness_writes.make_intervals_request", fake_request
    )
    result = asyncio.run(
        update_wellness_record(
            date="2026-04-25",
            record={"hrv": 55},
            athlete_id="i1",
            locked=False,
        )
    )
    assert captured["data"]["locked"] is False
    assert "WARNING" in result
    assert "overwrite" in result.lower()


# ---------------------------------------------------------------------------
# update_wellness_record_today — happy
# ---------------------------------------------------------------------------


def test_update_wellness_record_today_uses_undated_url(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_request(*_args, **kwargs):
        captured["data"] = kwargs.get("data")
        captured["url"] = kwargs.get("url")
        captured["method"] = kwargs.get("method")
        return {"id": "2026-04-25", "fatigue": 4, "locked": True}

    monkeypatch.setattr(
        "intervals_mcp_server.tools.wellness_writes.make_intervals_request", fake_request
    )
    result = asyncio.run(
        update_wellness_record_today(
            record={"id": "2026-04-25", "fatigue": 4},
            athlete_id="i1",
        )
    )
    # Undated URL: ends in /wellness, NOT /wellness/<date>
    assert captured["url"].endswith("/wellness")
    assert not captured["url"].endswith("2026-04-25")
    assert captured["method"] == "PUT"
    assert captured["data"]["locked"] is True
    assert "updated" in result


# ---------------------------------------------------------------------------
# update_wellness_records_bulk — happy
# ---------------------------------------------------------------------------


def test_update_wellness_records_bulk(monkeypatch):
    captured: dict[str, Any] = {}

    async def fake_put_json(url, _api_key, body):
        captured["url"] = url
        captured["body"] = body
        return body

    monkeypatch.setattr("intervals_mcp_server.tools.wellness_writes._put_json", fake_put_json)
    result = asyncio.run(
        update_wellness_records_bulk(
            records=[
                {"id": "2026-04-23", "hrv": 50},
                {"id": "2026-04-24", "hrv": 51},
            ],
            athlete_id="i1",
        )
    )
    assert captured["url"].endswith("/wellness-bulk")
    assert all(r["locked"] is True for r in captured["body"]), (
        "every record should default locked=True"
    )
    assert "2 record" in result
    assert "2026-04-23" in result
    assert "2026-04-24" in result


# ---------------------------------------------------------------------------
# upload_wellness_csv — multipart, ensures locked column
# ---------------------------------------------------------------------------


def test_upload_wellness_csv_multipart(monkeypatch, tmp_path):
    csv_path = tmp_path / "wellness.csv"
    csv_path.write_text("date,hrv,fatigue\n2026-04-25,52,3\n", encoding="utf-8")

    captured: dict[str, Any] = {}

    class FakeResponse:
        status_code = 200
        content = b"{}"

        @staticmethod
        def json():
            return {}

        @staticmethod
        def raise_for_status():
            return None

    class FakeClient:
        is_closed = False

        async def request(self, **kwargs):
            captured["method"] = kwargs.get("method")
            captured["url"] = kwargs.get("url")
            captured["files"] = kwargs.get("files")
            return FakeResponse()

    async def fake_get_client():
        return FakeClient()

    monkeypatch.setattr(
        "intervals_mcp_server.tools.wellness_writes._get_httpx_client", fake_get_client
    )

    result = asyncio.run(upload_wellness_csv(file_path=str(csv_path), athlete_id="i1"))

    assert captured["method"] == "POST"
    assert captured["url"].endswith("/athlete/i1/wellness")
    files = captured["files"]
    assert files is not None
    # The uploaded payload should include the locked column we injected.
    file_tuple = files["file"]
    uploaded_bytes = file_tuple[1]
    assert b"locked" in uploaded_bytes
    assert b"true" in uploaded_bytes
    assert "uploaded" in result.lower()


# ---------------------------------------------------------------------------
# Error path
# ---------------------------------------------------------------------------


def test_update_wellness_record_http_error_message(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 422, "message": "422 Unprocessable Entity: bad field"}

    monkeypatch.setattr(
        "intervals_mcp_server.tools.wellness_writes.make_intervals_request", fake_request
    )
    result = asyncio.run(
        update_wellness_record(
            date="2026-04-25",
            record={"hrv": "not-a-number"},
            athlete_id="i1",
        )
    )
    assert "Error" in result
    assert "Unprocessable" in result or "bad field" in result


# ---------------------------------------------------------------------------
# Bonus: bulk with locked=False propagates warning
# ---------------------------------------------------------------------------


def test_bulk_locked_false_warning(monkeypatch):
    async def fake_put_json(_url, _api_key, body):
        return body

    monkeypatch.setattr("intervals_mcp_server.tools.wellness_writes._put_json", fake_put_json)
    result = asyncio.run(
        update_wellness_records_bulk(
            records=[{"id": "2026-04-23", "hrv": 50}],
            athlete_id="i1",
            locked=False,
        )
    )
    assert "WARNING" in result
