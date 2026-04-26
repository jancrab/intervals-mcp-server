"""
Markdown formatters for the athlete-extras tools.

Self-contained: no shared formatting helpers are imported, so this module
can be edited concurrently with other formatter modules without conflict.
"""

from __future__ import annotations

import json
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _label(value: Any) -> str:
    """Render a scalar value safely for a labelled bullet line."""
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _kv(label: str, value: Any) -> str:
    return f"- **{label}**: {_label(value)}"


def _truncate(text: str, n: int = 120) -> str:
    if not isinstance(text, str):
        return _label(text)
    return text if len(text) <= n else text[: n - 1] + "…"


def format_csv_block(text: str, title: str | None = None) -> str:
    """Wrap raw CSV text in a fenced code block for chat display."""
    head = f"### {title}\n\n" if title else ""
    return f"{head}```csv\n{text}\n```"


# ---------------------------------------------------------------------------
# Athlete update / profile / summary / settings / training-plan
# ---------------------------------------------------------------------------


def format_athlete_update_result(athlete: dict[str, Any]) -> str:
    """Confirmation card after PUT /athlete/{id}."""
    if not isinstance(athlete, dict) or not athlete:
        return "Athlete update accepted (no body returned)."
    aid = athlete.get("id") or "—"
    name = athlete.get("name") or athlete.get("firstname") or "—"
    lines = [
        f"### Athlete updated — {name} ({aid})",
        "",
        _kv("Email", athlete.get("email")),
        _kv("Sex", athlete.get("sex")),
        _kv("City", athlete.get("city")),
        _kv("Country", athlete.get("country")),
        _kv("Timezone", athlete.get("timezone")),
        _kv("Weight (kg)", athlete.get("weight")),
        _kv("Height (m)", athlete.get("height")),
        _kv("Bio", _truncate(athlete.get("bio") or "")),
    ]
    return "\n".join(lines)


def format_athlete_summary(summary: dict[str, Any] | list[Any]) -> str:
    """Format /athlete/{id}/athlete-summary{ext} JSON response.

    The response is typically a list of weekly buckets, each with totals,
    load model, time-in-zones and a per-category breakdown.
    """
    if isinstance(summary, dict):
        summary = [summary]
    if not isinstance(summary, list) or not summary:
        return "No athlete summary available."

    rows = [
        "### Athlete summary",
        "",
        "| Date | Activities | Hours | Distance (km) | Load | Fitness | Fatigue | Form |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for entry in summary:
        if not isinstance(entry, dict):
            continue
        secs = entry.get("time") or 0
        try:
            hours = round(float(secs) / 3600.0, 2)
        except (TypeError, ValueError):
            hours = "—"
        dist = entry.get("distance")
        try:
            dist_km = round(float(dist) / 1000.0, 2) if dist is not None else "—"
        except (TypeError, ValueError):
            dist_km = "—"
        rows.append(
            "| {date} | {n} | {h} | {km} | {load} | {fit} | {fat} | {form} |".format(
                date=entry.get("date", "—"),
                n=entry.get("count", "—"),
                h=hours,
                km=dist_km,
                load=entry.get("training_load", "—"),
                fit=entry.get("fitness", "—"),
                fat=entry.get("fatigue", "—"),
                form=entry.get("form", "—"),
            )
        )

    # Show category breakdown for the most recent entry, if present
    last = summary[-1] if isinstance(summary[-1], dict) else None
    if last:
        cats = last.get("byCategory")
        if isinstance(cats, list) and cats:
            rows.append("")
            rows.append("**By category (latest week)**")
            rows.append("")
            rows.append("| Category | Count | Hours | Load | eFTP |")
            rows.append("|---|---:|---:|---:|---:|")
            for c in cats:
                if not isinstance(c, dict):
                    continue
                t = c.get("time") or 0
                try:
                    h = round(float(t) / 3600.0, 2)
                except (TypeError, ValueError):
                    h = "—"
                rows.append(
                    "| {cat} | {n} | {h} | {ld} | {ftp} |".format(
                        cat=c.get("category", "—"),
                        n=c.get("count", "—"),
                        h=h,
                        ld=c.get("training_load", "—"),
                        ftp=c.get("eftp") or "—",
                    )
                )

    return "\n".join(rows)


def format_athlete_settings(settings: dict[str, Any]) -> str:
    """Format /athlete/{id}/settings/{deviceClass} as labelled bullets.

    The response is a free-form key→value map of UI/app settings. We surface
    the top-level keys with a one-line preview of nested objects.
    """
    if not isinstance(settings, dict) or not settings:
        return "No device settings available."

    rows = [f"### Athlete device settings ({len(settings)} keys)", ""]
    for key in sorted(settings.keys()):
        value = settings[key]
        if isinstance(value, (dict, list)):
            try:
                preview = _truncate(json.dumps(value, ensure_ascii=False), 100)
            except (TypeError, ValueError):
                preview = "<unserializable>"
            rows.append(f"- **{key}**: `{preview}`")
        else:
            rows.append(_kv(key, value))
    return "\n".join(rows)


def format_training_plan(plan: dict[str, Any]) -> str:
    """Format /athlete/{id}/training-plan response."""
    if not isinstance(plan, dict) or not plan:
        return "No training plan currently assigned."

    nested = plan.get("training_plan") if isinstance(plan.get("training_plan"), dict) else None

    rows = ["### Current training plan", ""]
    rows.append(_kv("Athlete", plan.get("athlete_id")))
    rows.append(_kv("Plan id", plan.get("training_plan_id")))
    rows.append(_kv("Alias", plan.get("training_plan_alias")))
    rows.append(_kv("Start date", plan.get("training_plan_start_date")))
    rows.append(_kv("Last applied", plan.get("training_plan_last_applied")))
    rows.append(_kv("Timezone", plan.get("timezone")))

    if nested:
        rows.append("")
        rows.append("**Plan details**")
        rows.append(_kv("Name", nested.get("name")))
        rows.append(_kv("Folder id", nested.get("folder_id")))
        rows.append(_kv("Description", _truncate(nested.get("description") or "")))

    if not plan.get("training_plan_id") and not nested:
        rows.append("")
        rows.append("_(No plan assigned — all fields null.)_")

    return "\n".join(rows)


def format_training_plan_update_result(result: dict[str, Any]) -> str:
    """Confirmation card after PUT /athlete/{id}/training-plan."""
    if not isinstance(result, dict) or not result:
        return "Training plan update accepted (no body returned)."
    rows = ["### Training plan updated", ""]
    rows.append(_kv("Plan id", result.get("training_plan_id")))
    rows.append(_kv("Alias", result.get("training_plan_alias")))
    rows.append(_kv("Start date", result.get("training_plan_start_date")))
    rows.append(_kv("Timezone", result.get("timezone")))
    return "\n".join(rows)


def format_athlete_basic_profile(profile: dict[str, Any]) -> str:
    """Format /athlete/{id}/profile response.

    The endpoint wraps the basic identity in `{athlete, sharedFolders, customItems}`.
    This is a *smaller* response than `/athlete/{id}` (the full record used by
    `get_athlete_profile`) — only public-ish identity fields.
    """
    if not isinstance(profile, dict) or not profile:
        return "No basic profile available."
    inner = profile.get("athlete") if isinstance(profile.get("athlete"), dict) else profile
    rows = ["### Athlete basic profile", ""]
    rows.append(_kv("Id", inner.get("id")))
    rows.append(_kv("Name", inner.get("name")))
    rows.append(_kv("Sex", inner.get("sex")))
    rows.append(_kv("City", inner.get("city")))
    rows.append(_kv("State", inner.get("state")))
    rows.append(_kv("Country", inner.get("country")))
    rows.append(_kv("Timezone", inner.get("timezone")))
    rows.append(_kv("Coach", inner.get("icu_coach")))
    rows.append(_kv("Bio", _truncate(inner.get("bio") or "")))
    rows.append(_kv("Website", inner.get("website")))

    shared = profile.get("sharedFolders")
    if isinstance(shared, list):
        rows.append(_kv("Shared folders", len(shared)))
    custom = profile.get("customItems")
    if isinstance(custom, list):
        rows.append(_kv("Custom items", len(custom)))
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------


def format_weather_config(config: dict[str, Any]) -> str:
    """Format /athlete/{id}/weather-config response."""
    if not isinstance(config, dict) or not config:
        return "No weather config set."
    forecasts = config.get("forecasts")
    if not isinstance(forecasts, list) or not forecasts:
        return "No weather locations configured."
    rows = [f"### Weather config — {len(forecasts)} location(s)", ""]
    for f in forecasts:
        if not isinstance(f, dict):
            continue
        rows.append(f"**{f.get('label') or '—'}** (id={f.get('id', '—')})")
        rows.append(_kv("Provider", f.get("provider")))
        rows.append(_kv("Location", f.get("location")))
        rows.append(_kv("Latitude", f.get("lat")))
        rows.append(_kv("Longitude", f.get("lon")))
        rows.append(_kv("Enabled", f.get("enabled")))
        rows.append("")
    return "\n".join(rows).rstrip()


def format_weather_config_update_result(result: dict[str, Any]) -> str:
    """Confirmation card after PUT /athlete/{id}/weather-config."""
    if not isinstance(result, dict) or not result:
        return "Weather config update accepted (no body returned)."
    forecasts = result.get("forecasts")
    n = len(forecasts) if isinstance(forecasts, list) else 0
    return f"### Weather config updated\n\n- **Locations**: {n}"


def format_weather_forecast(forecast: dict[str, Any] | list[Any]) -> str:
    """Format /athlete/{id}/weather-forecast response (per-location daily forecast)."""
    if isinstance(forecast, dict):
        forecasts = (
            forecast.get("forecasts") if isinstance(forecast.get("forecasts"), list) else [forecast]
        )
    elif isinstance(forecast, list):
        forecasts = forecast
    else:
        return "No forecast data."

    if not forecasts:
        return "No forecast data."

    rows: list[str] = []
    for loc in forecasts:
        if not isinstance(loc, dict):
            continue
        label = loc.get("label") or loc.get("location") or "—"
        rows.append(f"### Forecast — {label}")
        if loc.get("error"):
            rows.append(f"_Error: {loc['error']}_")
            rows.append("")
            continue
        daily = loc.get("daily")
        if not isinstance(daily, list) or not daily:
            rows.append("_No daily forecast available._")
            rows.append("")
            continue
        rows.append("")
        rows.append(
            "| Date | Temp min/max (°C) | Wind (m/s) | Rain (mm) | Humidity (%) | Description |"
        )
        rows.append("|---|---|---:|---:|---:|---|")
        for day in daily:
            if not isinstance(day, dict):
                continue
            temp = day.get("temp") if isinstance(day.get("temp"), dict) else {}
            tmin = temp.get("min")
            tmax = temp.get("max")
            wstr = day.get("weather")
            desc = "—"
            if isinstance(wstr, list) and wstr and isinstance(wstr[0], dict):
                desc = wstr[0].get("description") or wstr[0].get("main") or "—"
            rows.append(
                "| {d} | {tmin}/{tmax} | {w} | {r} | {h} | {desc} |".format(
                    d=day.get("id") or "—",
                    tmin=_label(tmin),
                    tmax=_label(tmax),
                    w=_label(day.get("wind_speed")),
                    r=_label(day.get("rain")),
                    h=_label(day.get("humidity")),
                    desc=_truncate(str(desc), 40),
                )
            )
        rows.append("")
    return "\n".join(rows).rstrip() or "No forecast data."


# ---------------------------------------------------------------------------
# Shared events
# ---------------------------------------------------------------------------


def format_shared_event(event: dict[str, Any]) -> str:
    """Format /shared-event/{id} response (race / event detail card)."""
    if not isinstance(event, dict) or not event:
        return "Shared event not found."
    rows = ["### Shared event", ""]
    rows.append(_kv("Id", event.get("id")))
    rows.append(_kv("Name", event.get("name")))
    rows.append(_kv("Type", event.get("type") or event.get("category")))
    rows.append(_kv("Start", event.get("start_date_local") or event.get("start")))
    rows.append(_kv("End", event.get("end_date_local") or event.get("end")))
    rows.append(_kv("Location", event.get("location")))
    rows.append(_kv("Distance (m)", event.get("distance")))
    rows.append(_kv("Url", event.get("url")))
    rows.append(_kv("Description", _truncate(event.get("description") or "", 200)))
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# OAuth / disconnect
# ---------------------------------------------------------------------------


def format_disconnect_app_result(result: dict[str, Any] | None) -> str:
    """Confirmation card after DELETE /disconnect-app.

    For personal-API-key auth this endpoint is not strictly meaningful (there
    is no OAuth-app session to revoke), so the API may return an empty body
    or a no-op success.
    """
    if result is None or (isinstance(result, dict) and not result):
        return (
            "Disconnect-app request accepted (no body — this is a no-op for personal API-key auth)."
        )
    if isinstance(result, dict) and result.get("error"):
        return f"Error disconnecting app: {result.get('message', 'Unknown error')}"
    return (
        f"### App disconnected\n\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"
    )
