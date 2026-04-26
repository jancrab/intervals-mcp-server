"""
Unit tests for athlete-extras MCP tools.

Mirrors patterns in tests/test_sport_settings.py: monkeypatch
``make_intervals_request`` in both the api.client module and the tools
module to stub responses, then assert on the formatted string and (for
writes) on captured kwargs (method + data + URL).

CSV-mode for ``get_athlete_summary`` is tested by stubbing the local
``_fetch_csv`` helper in the tools module — that mirrors how
test_activity_analytics.py exercises the same pattern.
"""

import asyncio
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.tools.athlete_extras import (  # pylint: disable=wrong-import-position
    disconnect_app,
    get_athlete_basic_profile,
    get_athlete_settings_for_device,
    get_athlete_summary,
    get_athlete_training_plan,
    get_shared_event,
    get_weather_config,
    get_weather_forecast,
    update_athlete,
    update_athlete_plans,
    update_athlete_training_plan,
    update_weather_config,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_PROFILE = {
    "athlete": {
        "id": "i1",
        "name": "Test Athlete",
        "city": "Bochum",
        "state": "NRW",
        "country": "Germany",
        "timezone": "Europe/Berlin",
        "sex": "M",
        "icu_coach": False,
        "bio": "Cyclist and runner.",
        "website": None,
    },
    "sharedFolders": [],
    "customItems": [{"id": 1}],
}

SAMPLE_SUMMARY = [
    {
        "count": 6,
        "time": 38473,
        "distance": 181876.25,
        "training_load": 513,
        "fitness": 53.85,
        "fatigue": 79.48,
        "form": -25.62,
        "date": "2026-04-20",
        "byCategory": [
            {"category": "Ride", "count": 3, "time": 28937, "training_load": 513, "eftp": 219.86},
            {"category": "Workout", "count": 3, "time": 9536, "training_load": 0, "eftp": None},
        ],
    }
]

SAMPLE_DEVICE_SETTINGS = {
    "App.mini": False,
    "i18nOptions": {"dev": False},
    "PowerView.options": {"curves": {"normal": True}},
}

SAMPLE_TRAINING_PLAN = {
    "athlete_id": None,
    "training_plan_id": None,
    "training_plan_start_date": None,
    "timezone": None,
    "training_plan_last_applied": None,
    "training_plan": None,
    "training_plan_alias": None,
}

SAMPLE_TRAINING_PLAN_ASSIGNED = {
    "athlete_id": "i1",
    "training_plan_id": 42,
    "training_plan_start_date": "2026-05-01",
    "timezone": "Europe/Berlin",
    "training_plan_alias": "Spring base",
    "training_plan": {"id": 42, "name": "Base 4 weeks", "folder_id": 7},
}

SAMPLE_WEATHER_CONFIG = {
    "forecasts": [
        {
            "id": 1,
            "provider": "OPEN_WEATHER",
            "location": "Bochum,NRW,DE",
            "label": "Bochum",
            "lat": 51.48,
            "lon": 7.21,
            "enabled": True,
        }
    ]
}

SAMPLE_FORECAST = {
    "forecasts": [
        {
            "id": 1,
            "provider": "OPEN_WEATHER",
            "location": "Bochum,NRW,DE",
            "label": "Bochum",
            "lat": 51.48,
            "lon": 7.21,
            "error": None,
            "daily": [
                {
                    "id": "2026-04-26",
                    "humidity": 46.0,
                    "wind_speed": 3.13,
                    "rain": 0.0,
                    "temp": {"min": 3.56, "max": 16.38},
                    "weather": [{"description": "Mostly cloudy", "main": "Clouds"}],
                },
                {
                    "id": "2026-04-27",
                    "humidity": 36.0,
                    "wind_speed": 3.25,
                    "rain": 0.0,
                    "temp": {"min": 3.86, "max": 17.3},
                    "weather": [{"description": "Overcast", "main": "Clouds"}],
                },
            ],
        }
    ]
}

SAMPLE_SHARED_EVENT = {
    "id": 1234,
    "name": "City Marathon",
    "type": "Race",
    "start_date_local": "2026-05-15T08:00:00",
    "end_date_local": "2026-05-15T13:00:00",
    "location": "Berlin",
    "distance": 42195.0,
    "description": "Annual road marathon.",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_request(monkeypatch, fake_request):
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.athlete_extras.make_intervals_request", fake_request
    )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def test_get_athlete_basic_profile_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return SAMPLE_PROFILE

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_athlete_basic_profile(athlete_id="i1"))
    assert "Athlete basic profile" in out
    assert "Bochum" in out
    assert "Test Athlete" in out
    assert captured["url"].endswith("/athlete/i1/profile")


def test_get_athlete_summary_json_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_SUMMARY

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_athlete_summary(athlete_id="i1"))
    assert "Athlete summary" in out
    assert "2026-04-20" in out
    # Distance converted to km
    assert "181.88" in out
    # By-category breakdown rendered
    assert "Ride" in out


def test_get_athlete_summary_csv_mode(monkeypatch):
    captured = {}

    async def fake_csv(url_path, _api_key):
        captured["url"] = url_path
        return "Week,Athlete,Hours\n2026-04-20,i1,10.69\n"

    monkeypatch.setattr("intervals_mcp_server.tools.athlete_extras._fetch_csv", fake_csv)
    out = asyncio.run(get_athlete_summary(athlete_id="i1", format="csv"))
    assert "```csv" in out
    assert "Week,Athlete,Hours" in out
    assert captured["url"].endswith("/athlete-summary.csv")


def test_get_athlete_settings_for_device_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return SAMPLE_DEVICE_SETTINGS

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_athlete_settings_for_device(device_class="desktop", athlete_id="i1"))
    assert "device settings" in out.lower()
    assert "App.mini" in out
    assert captured["url"].endswith("/settings/desktop")


def test_get_athlete_settings_validates_device_class(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        raise AssertionError("API should not be called when validation fails")

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_athlete_settings_for_device(device_class="watch", athlete_id="i1"))
    assert out.lower().startswith("error")


def test_get_athlete_training_plan_unassigned(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_TRAINING_PLAN

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_athlete_training_plan(athlete_id="i1"))
    assert "training plan" in out.lower()
    assert "No plan assigned" in out


def test_get_athlete_training_plan_assigned(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_TRAINING_PLAN_ASSIGNED

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_athlete_training_plan(athlete_id="i1"))
    assert "Spring base" in out
    assert "2026-05-01" in out
    assert "Base 4 weeks" in out


def test_get_weather_config_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_WEATHER_CONFIG

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_weather_config(athlete_id="i1"))
    assert "Weather config" in out
    assert "Bochum" in out
    assert "OPEN_WEATHER" in out


def test_get_weather_forecast_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_FORECAST

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_weather_forecast(athlete_id="i1"))
    assert "Forecast" in out
    assert "2026-04-26" in out
    assert "Mostly cloudy" in out


def test_get_shared_event_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured["url"] = kwargs.get("url")
        return SAMPLE_SHARED_EVENT

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_shared_event(event_id="1234"))
    assert "City Marathon" in out
    assert "Berlin" in out
    assert captured["url"].endswith("/shared-event/1234")


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def test_update_athlete_puts_body(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {"id": "i1", "name": "Test Athlete", "weight": 81.5}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(update_athlete(athlete_id="i1", weight=81.5, bio="Updated bio"))
    assert captured["method"] == "PUT"
    assert captured["data"]["weight"] == 81.5
    assert captured["data"]["bio"] == "Updated bio"
    assert captured["url"].endswith("/athlete/i1")
    assert "Athlete updated" in out


def test_update_athlete_requires_at_least_one_field(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        raise AssertionError("API should not be called when validation fails")

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(update_athlete(athlete_id="i1"))
    assert out.lower().startswith("error")


def test_update_athlete_plans_puts_list(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        update_athlete_plans(plan_id=42, start_date_local="2026-05-01", athlete_id="i1")
    )
    assert captured["method"] == "PUT"
    assert captured["url"] == "/athlete-plans"
    assert isinstance(captured["data"], list)
    assert captured["data"][0]["athlete_id"] == "i1"
    assert captured["data"][0]["plan_id"] == 42
    assert "updated" in out.lower()


def test_update_athlete_training_plan_puts_body(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {
            "training_plan_id": 42,
            "training_plan_start_date": "2026-05-01",
            "training_plan_alias": "Spring base",
            "timezone": "Europe/Berlin",
        }

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        update_athlete_training_plan(
            training_plan_start_date="2026-05-01",
            training_plan_id=42,
            athlete_id="i1",
        )
    )
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/athlete/i1/training-plan")
    assert captured["data"]["training_plan_start_date"] == "2026-05-01"
    assert "Training plan updated" in out


def test_update_weather_config_puts_body(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return SAMPLE_WEATHER_CONFIG

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(
        update_weather_config(
            forecasts=SAMPLE_WEATHER_CONFIG["forecasts"],
            athlete_id="i1",
        )
    )
    assert captured["method"] == "PUT"
    assert captured["data"]["forecasts"][0]["label"] == "Bochum"
    assert "Weather config updated" in out


def test_disconnect_app_no_op_for_api_key(monkeypatch):
    """For personal-API-key auth this endpoint typically returns empty/no-op."""
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return {}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(disconnect_app())
    assert captured["method"] == "DELETE"
    assert captured["url"] == "/disconnect-app"
    assert "no-op" in out.lower() or "accepted" in out.lower()


def test_disconnect_app_error_path(monkeypatch):
    """API may return an error for personal-API-key auth — surface it cleanly."""

    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 404, "message": "Not applicable"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(disconnect_app())
    assert "Error disconnecting app" in out
    assert "Not applicable" in out
