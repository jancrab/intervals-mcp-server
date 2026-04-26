"""
Unit tests for per-activity analytics MCP tools.

Mirrors the pattern in tests/test_sport_settings.py:
- monkeypatch ``make_intervals_request`` in both api.client and the tools
  module to stub responses
- assert on the formatted output and (where relevant) captured kwargs
- CSV mode is tested by monkeypatching the local ``_fetch_csv`` helper
"""

import asyncio
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.tools.activity_analytics import (  # pylint: disable=wrong-import-position
    find_best_efforts,
    get_activity_gap_histogram,
    get_activity_hr_curve,
    get_activity_hr_histogram,
    get_activity_hr_load_model,
    get_activity_interval_stats,
    get_activity_map,
    get_activity_pace_curve,
    get_activity_pace_histogram,
    get_activity_power_curve,
    get_activity_power_curves_multistream,
    get_activity_power_histogram,
    get_activity_power_spike_model,
    get_activity_power_vs_hr,
    get_activity_segments,
    get_activity_time_at_hr,
    get_activity_weather_summary,
)


# ---------------------------------------------------------------------------
# Sample fixtures (shaped after live API probes)
# ---------------------------------------------------------------------------

SAMPLE_HR_CURVE = {
    "id": "i1",
    "weight": 90.0,
    "training_load": 44,
    "secs": [1, 5, 30, 60, 300, 600],
    "bpm": [142, 142, 141, 138, 134, 132],
    "start_index": [4600, 4600, 4598, 4595, 4500, 4400],
    "end_index": [4601, 4605, 4628, 4655, 4800, 5000],
}

SAMPLE_POWER_CURVE = {
    "id": "i1",
    "weight": 90.0,
    "secs": [1, 5, 30, 60, 300, 600, 1200],
    "watts": [303, 259, 215, 195, 180, 175, 170],
    "start_index": [200, 200, 200, 200, 200, 200, 200],
    "end_index": [201, 205, 230, 260, 500, 800, 1400],
}

SAMPLE_PACE_CURVE = {
    "id": "i1",
    "secs": [1, 5, 30, 60, 300, 600, 1200],
    "mps": [5.5, 5.2, 4.8, 4.5, 4.2, 4.0, 3.8],
}

SAMPLE_POWER_CURVES_MULTI = [
    {**SAMPLE_POWER_CURVE, "label": "All", "filter_label": None},
    {**SAMPLE_POWER_CURVE, "label": "Z2", "filter_label": "Zone 2"},
]

SAMPLE_POWER_VS_HR = {
    "bucketSize": 60,
    "warmup": 1200,
    "cooldown": 600,
    "elapsedTime": 8200,
    "hrLag": 28,
    "powerHr": 1.279,
    "decoupling": 0.978,
    "series": [
        {"start": 0, "secs": 467, "movingSecs": 34, "watts": 93, "hr": 98, "cadence": 62},
        {"start": 467, "secs": 60, "movingSecs": 60, "watts": 112, "hr": 107, "cadence": 69},
    ],
}

SAMPLE_HR_HISTOGRAM = [
    {"min": 70, "max": 74, "secs": 25},
    {"min": 130, "max": 134, "secs": 2447},
    {"min": 135, "max": 139, "secs": 1184},
]

SAMPLE_POWER_HISTOGRAM = [
    {"min": 0, "max": 24, "secs": 3091},
    {"min": 150, "max": 174, "secs": 3609},
    {"min": 200, "max": 224, "secs": 15},
]

SAMPLE_TIME_AT_HR = {
    "min_bpm": 71,
    "max_bpm": 75,
    "secs": [7, 34, 26, 55, 116],
    "cumulative_secs": [7, 41, 67, 122, 238],
}

SAMPLE_HR_LOAD_MODEL = {
    "type": "HRSS",
    "icu_training_load": 44,
    "data": [],
    "resting_hr": 66,
    "lt_hr": 172,
    "max_hr": 186,
    "rSquared": None,
    "trainingDataCount": 100,
}

SAMPLE_POWER_SPIKE_MODEL = {
    "type": "FFT_CURVES",
    "criticalPower": 235,
    "wPrime": 20120,
    "pMax": 828,
    "inputPointIndexes": [149, 200, 350],
    "ftp": 240,
}

SAMPLE_INTERVAL_STATS = [
    {
        "label": "Effort 1",
        "type": "WORK",
        "elapsed_time": 300,
        "moving_time": 300,
        "distance": 1500,
        "average_watts": 250,
        "max_watts": 320,
        "average_heartrate": 165,
        "max_heartrate": 175,
    }
]

SAMPLE_SEGMENTS = [
    {
        "id": 12345,
        "start_index": 799,
        "end_index": 1285,
        "name": "Alpe du Zwift Start to Bend 21",
        "segment_id": 17329459,
        "starred": False,
    },
    {
        "id": 12346,
        "start_index": 1285,
        "end_index": 1728,
        "name": "Alpe du Zwift Bend 21 to 20",
        "segment_id": 17329478,
        "starred": True,
    },
]

SAMPLE_BEST_EFFORTS = [
    {"type": "watts", "duration": 60, "value": 300, "activity_id": "i1", "time_ago": "today"},
    {"type": "watts", "duration": 300, "value": 250, "activity_id": "i1", "time_ago": "today"},
]

SAMPLE_MAP = {
    "bounds": [[-11.688997, 166.90335], [-11.664228, 166.94757]],
    "latlngs": [[-11.664254, 166.94757], [-11.664255, 166.94756], [-11.664253, 166.94751]],
}

SAMPLE_WEATHER = {
    "moving_time": 3600,
    "average_weather_temp": 18.5,
    "min_weather_temp": 15.0,
    "max_weather_temp": 22.0,
    "average_wind_speed": 3.2,
    "average_humidity": 65,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_request(monkeypatch, fake_request):
    """Monkeypatch make_intervals_request in client + tools module."""
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activity_analytics.make_intervals_request", fake_request
    )


# ---------------------------------------------------------------------------
# Curve happy-paths
# ---------------------------------------------------------------------------


def test_get_hr_curve_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return SAMPLE_HR_CURVE

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_hr_curve(activity_id="i1"))
    assert "HR curve" in out
    assert "bpm" in out
    assert captured["url"].endswith("/activity/i1/hr-curve")


def test_get_power_curve_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_POWER_CURVE

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_power_curve(activity_id="i1"))
    assert "Power curve" in out
    assert "303" in out  # peak 1s power


def test_get_pace_curve_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_PACE_CURVE

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_pace_curve(activity_id="i1"))
    assert "Pace curve" in out
    assert "/km" in out


def test_get_power_curves_multistream_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_POWER_CURVES_MULTI

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_power_curves_multistream(activity_id="i1"))
    assert "Power curves" in out
    assert "Stream:" in out


def test_get_power_vs_hr_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_POWER_VS_HR

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_power_vs_hr(activity_id="i1"))
    assert "Power vs HR" in out
    assert "Decoupling" in out
    assert "Buckets" in out


# ---------------------------------------------------------------------------
# Histogram happy-paths
# ---------------------------------------------------------------------------


def test_get_hr_histogram_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_HR_HISTOGRAM

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_hr_histogram(activity_id="i1"))
    assert "HR histogram" in out
    assert "130–134" in out


def test_get_power_histogram_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_POWER_HISTOGRAM

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_power_histogram(activity_id="i1"))
    assert "Power histogram" in out
    assert "150–174" in out


def test_get_pace_histogram_empty(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return []

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_pace_histogram(activity_id="i1"))
    assert "No pace histogram data" in out or "empty" in out.lower()


def test_get_gap_histogram_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return [{"min": 2.5, "max": 3.0, "secs": 100}]

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_gap_histogram(activity_id="i1"))
    assert "histogram" in out.lower()


def test_get_time_at_hr_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_TIME_AT_HR

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_time_at_hr(activity_id="i1"))
    assert "Time at HR" in out
    assert "71" in out


# ---------------------------------------------------------------------------
# Model happy-paths
# ---------------------------------------------------------------------------


def test_get_hr_load_model_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_HR_LOAD_MODEL

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_hr_load_model(activity_id="i1"))
    assert "HR load model" in out
    assert "HRSS" in out
    assert "172" in out  # lt_hr


def test_get_power_spike_model_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_POWER_SPIKE_MODEL

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_power_spike_model(activity_id="i1"))
    assert "Power spike model" in out
    assert "235" in out  # criticalPower
    assert "20120" in out  # wPrime


# ---------------------------------------------------------------------------
# Interval-stats / segments / best-efforts
# ---------------------------------------------------------------------------


def test_get_interval_stats_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return SAMPLE_INTERVAL_STATS

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_interval_stats(activity_id="i1", start_index=0, end_index=1000))
    assert "Interval stats" in out
    assert "Effort 1" in out
    assert captured["params"] == {"start_index": 0, "end_index": 1000}


def test_get_segments_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_SEGMENTS

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_segments(activity_id="i1"))
    assert "Segment efforts (2)" in out
    assert "Alpe du Zwift" in out


def test_find_best_efforts_happy(monkeypatch):
    captured = {}

    async def fake_request(*_args, **kwargs):
        captured.update(kwargs)
        return SAMPLE_BEST_EFFORTS

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(find_best_efforts(activity_id="i1", stream="watts"))
    assert "Best efforts (2)" in out
    assert captured["params"] == {"stream": "watts"}


# ---------------------------------------------------------------------------
# Map / weather
# ---------------------------------------------------------------------------


def test_get_map_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_MAP

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_map(activity_id="i1"))
    assert "Activity map" in out
    assert "Coordinate points" in out


def test_get_weather_summary_happy(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return SAMPLE_WEATHER

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_weather_summary(activity_id="i1"))
    assert "Weather summary" in out
    assert "18.5" in out


# ---------------------------------------------------------------------------
# CSV mode
# ---------------------------------------------------------------------------


def test_hr_curve_csv_mode(monkeypatch):
    captured = {}

    async def fake_csv(url, _api_key):
        captured["url"] = url
        return "secs,bpm,start_index,end_index\n1,142,4600,4601\n2,142,4600,4602\n"

    monkeypatch.setattr("intervals_mcp_server.tools.activity_analytics._fetch_csv", fake_csv)
    out = asyncio.run(get_activity_hr_curve(activity_id="i1", format="csv"))
    assert "csv" in out.lower()
    assert "secs,bpm" in out
    assert "```csv" in out
    assert captured["url"].endswith("/activity/i1/hr-curve.csv")


def test_invalid_format(monkeypatch):
    async def fake_request(*_args, **_kwargs):  # should not be called
        raise AssertionError("API should not be called for invalid format")

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_hr_curve(activity_id="i1", format="xml"))
    assert "Error" in out
    assert "json" in out


# ---------------------------------------------------------------------------
# Error / empty paths
# ---------------------------------------------------------------------------


def test_get_segments_404_error(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return {"error": True, "status_code": 404, "message": "Activity not found"}

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_segments(activity_id="bogus"))
    assert "Error fetching segments" in out
    assert "Activity not found" in out


def test_get_segments_empty(monkeypatch):
    async def fake_request(*_args, **_kwargs):
        return []

    _patch_request(monkeypatch, fake_request)
    out = asyncio.run(get_activity_segments(activity_id="i1"))
    assert "No segment efforts" in out


def test_missing_activity_id():
    out = asyncio.run(get_activity_hr_curve(activity_id=""))
    assert out.startswith("Error")
    assert "activity_id" in out
