"""
Wellness-write MCP tools for Intervals.icu.

This module adds the write half of the wellness API to complement
`tools/wellness.py`'s read tool. It exposes:

- `get_wellness_record`           — GET /athlete/{id}/wellness/{date}
- `update_wellness_record`        — PUT /athlete/{id}/wellness/{date}
- `update_wellness_record_today`  — PUT /athlete/{id}/wellness  (date in body's `id` field)
- `update_wellness_records_bulk`  — PUT /athlete/{id}/wellness-bulk
- `upload_wellness_csv`           — POST /athlete/{id}/wellness  (multipart CSV)

CRITICAL: the `locked` field on a wellness record gates whether external
integrations (Oura, Garmin, Whoop, etc.) will silently overwrite it on the
next sync. Per the intervals.icu cookbook, any value written via the API to
a record that another integration also writes WILL be silently reverted on
the next sync UNLESS `locked: true` is set on that record. To protect the
caller, every write tool in this module:

1. Defaults `locked` to `True`.
2. If the caller explicitly passes `locked=False`, surfaces a warning in
   the response text so the caller knows their write may be overwritten.
"""

from __future__ import annotations

import csv as _csv
import io
import logging
from typing import Any

import httpx  # pylint: disable=import-error

from intervals_mcp_server.api.client import (
    _get_httpx_client,  # pylint: disable=protected-access
    _prepare_request_config,  # pylint: disable=protected-access
    _parse_response,  # pylint: disable=protected-access
    _handle_http_status_error,  # pylint: disable=protected-access
    make_intervals_request,
)
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatters_wellness_writes import (
    format_wellness_bulk_confirmation,
    format_wellness_record,
    format_wellness_write_confirmation,
)
from intervals_mcp_server.utils.validation import resolve_athlete_id, validate_date

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

logger = logging.getLogger("intervals_icu_mcp_server")
config = get_config()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _apply_lock_default(record: dict[str, Any], locked: bool) -> dict[str, Any]:
    """Ensure `locked` is set on the record before writing.

    The caller's explicit value on the record always wins; this only fills in
    the default when the field is absent.
    """
    out = dict(record)
    if "locked" not in out:
        out["locked"] = locked
    return out


def _unlocked_warning(locked: bool) -> str:
    if locked:
        return ""
    return (
        "\n\n> WARNING: `locked=False` was used. External integrations "
        "(Oura, Garmin, etc.) may silently overwrite this write on their "
        "next sync. Pass `locked=True` (the default) to protect the value."
    )


# ---------------------------------------------------------------------------
# GET — single record
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_wellness_record(
    date: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the wellness record for a single ISO-8601 date.

    Calls GET /athlete/{id}/wellness/{date}. Returns a markdown summary that
    includes the `locked` flag — relevant because any subsequent write to
    this record will be silently reverted by external sync (Oura, Garmin,
    etc.) unless `locked=True` is set.

    Args:
        date: ISO-8601 date in YYYY-MM-DD format.
        athlete_id: The Intervals.icu athlete ID (optional; falls back to
            ATHLETE_ID env var).
        api_key: The Intervals.icu API key (optional; falls back to API_KEY
            env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    try:
        date = validate_date(date)
    except ValueError as e:
        return f"Error: {e}"

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/wellness/{date}", api_key=api_key
    )

    if isinstance(result, dict) and result.get("error"):
        return f"Error fetching wellness record: {result.get('message')}"
    if not isinstance(result, dict):
        return f"No wellness record found for athlete {athlete_id_to_use} on {date}."

    return format_wellness_record(result)


# ---------------------------------------------------------------------------
# PUT — dated update
# ---------------------------------------------------------------------------


@mcp.tool()
async def update_wellness_record(
    date: str,
    record: dict[str, Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
    locked: bool = True,
) -> str:
    """Update the wellness record for a specific date.

    Calls PUT /athlete/{id}/wellness/{date} with the supplied record body.

    SAFETY: external integrations (Oura, Garmin, Whoop, etc.) will SILENTLY
    REVERT API writes on their next sync UNLESS `locked: true` is set on the
    record. This tool defaults `locked=True`. If you pass `locked=False`,
    the response will include a warning explaining the overwrite risk.

    Args:
        date: ISO-8601 date (YYYY-MM-DD) of the record to update.
        record: Wellness fields to write (e.g. `{"hrv": 52, "fatigue": 3,
            "comments": "easy day"}`). The `locked` field, if present in the
            record, takes precedence over the `locked` argument.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
        locked: Whether to mark the record locked. Defaults to True. Set to
            False ONLY if you intentionally want external sync to be free
            to overwrite this value (rare).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    try:
        date = validate_date(date)
    except ValueError as e:
        return f"Error: {e}"
    if not isinstance(record, dict):
        return "Error: `record` must be a dict of wellness fields."

    body = _apply_lock_default(record, locked)

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/wellness/{date}",
        api_key=api_key,
        method="PUT",
        data=body,
    )
    if isinstance(result, dict) and result.get("error"):
        return f"Error updating wellness record: {result.get('message')}"

    confirmed = result if isinstance(result, dict) else body
    # If the API returned no record-shape body, fall back to what we sent so
    # the confirmation still reports the locked state and date.
    if "id" not in confirmed:
        confirmed = {**confirmed, "id": date}

    return format_wellness_write_confirmation(confirmed, "updated") + _unlocked_warning(
        body.get("locked", True)
    )


# ---------------------------------------------------------------------------
# PUT — undated (date encoded in record id)
# ---------------------------------------------------------------------------


@mcp.tool()
async def update_wellness_record_today(
    record: dict[str, Any],
    athlete_id: str | None = None,
    api_key: str | None = None,
    locked: bool = True,
) -> str:
    """Update wellness using the no-date PUT endpoint.

    Calls PUT /athlete/{id}/wellness with the record body. The record's `id`
    field (a YYYY-MM-DD string) determines which date is updated; if absent,
    intervals.icu typically applies the write to today's record.

    SAFETY: same `locked` rule as `update_wellness_record` — external
    integrations will silently overwrite an unlocked write on their next
    sync. Defaults `locked=True`. Passing `locked=False` triggers a
    warning in the response.

    Args:
        record: Wellness fields. Set `record["id"] = "YYYY-MM-DD"` to target
            a specific date; omit it to let intervals.icu apply to "today"
            in the athlete's timezone.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
        locked: Defaults to True. See module docstring for the sync gotcha.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not isinstance(record, dict):
        return "Error: `record` must be a dict of wellness fields."

    body = _apply_lock_default(record, locked)

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/wellness",
        api_key=api_key,
        method="PUT",
        data=body,
    )
    if isinstance(result, dict) and result.get("error"):
        return f"Error updating wellness record: {result.get('message')}"

    confirmed = result if isinstance(result, dict) else body
    return format_wellness_write_confirmation(confirmed, "updated") + _unlocked_warning(
        body.get("locked", True)
    )


# ---------------------------------------------------------------------------
# PUT — bulk
# ---------------------------------------------------------------------------


@mcp.tool()
async def update_wellness_records_bulk(
    records: list[dict[str, Any]],
    athlete_id: str | None = None,
    api_key: str | None = None,
    locked: bool = True,
) -> str:
    """Update an array of wellness records in a single call.

    Calls PUT /athlete/{id}/wellness-bulk with `records` as the JSON body.
    Each record should carry an `id` field (YYYY-MM-DD) to identify its
    date.

    SAFETY: the `locked` default is applied to EVERY record that doesn't
    already specify it. External integrations will silently overwrite any
    record that isn't `locked: true`. Per-record `locked` values in the
    input always win over the `locked` argument.

    Args:
        records: List of wellness record dicts.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
        locked: Default lock state applied to records that don't carry their
            own `locked` field. Defaults to True.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not isinstance(records, list) or not records:
        return "Error: `records` must be a non-empty list of wellness record dicts."
    if not all(isinstance(r, dict) for r in records):
        return "Error: every entry in `records` must be a dict."

    body_records = [_apply_lock_default(r, locked) for r in records]

    # The bulk endpoint accepts either a top-level array or an object — we
    # use the array form, which is what the cookbook documents. Our
    # `make_intervals_request` typing accepts a dict; for a top-level list
    # we fall back to a thin direct-httpx path.
    result = await _put_json(
        f"/athlete/{athlete_id_to_use}/wellness-bulk",
        api_key,
        body_records,
    )
    if isinstance(result, dict) and result.get("error"):
        return f"Error updating wellness records: {result.get('message')}"

    returned = result if isinstance(result, list) else body_records
    any_unlocked = any(r.get("locked") is False for r in body_records)
    return format_wellness_bulk_confirmation(returned) + _unlocked_warning(not any_unlocked)


# ---------------------------------------------------------------------------
# POST — multipart CSV upload
# ---------------------------------------------------------------------------


@mcp.tool()
async def upload_wellness_csv(
    file_path: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    locked: bool = True,
) -> str:
    """Upload a wellness CSV via multipart/form-data.

    Calls POST /athlete/{id}/wellness with the file at `file_path` attached
    as multipart form data. The CSV must follow intervals.icu's wellness CSV
    format (header row of column names, one row per date).

    SAFETY: every record loaded from this CSV is subject to the `locked`
    rule. If `locked=True` (the default), this tool ensures a `locked`
    column exists in the CSV (adding one if missing) and sets it to `true`
    for every row that doesn't already specify it. If `locked=False`, the
    CSV is uploaded as-is and the response includes a warning that external
    sync may overwrite the upload.

    Args:
        file_path: Absolute or relative path to the CSV file.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
        locked: Default lock state for rows that don't specify it. Defaults
            to True.
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    try:
        with open(file_path, "rb") as fh:
            raw_bytes = fh.read()
    except FileNotFoundError:
        return f"Error: CSV file not found at {file_path}"
    except OSError as e:
        return f"Error reading CSV file: {e}"

    upload_bytes, locked_added = _ensure_locked_column(raw_bytes, locked)

    full_url, auth, headers, cfg_err = _prepare_request_config(
        f"/athlete/{athlete_id_to_use}/wellness", api_key, "POST"
    )
    if cfg_err:
        return f"Error uploading CSV: {cfg_err}"
    # multipart sets its own Content-Type; httpx adds it from `files=`
    headers.pop("Content-Type", None)

    files = {"file": ("wellness.csv", upload_bytes, "text/csv")}

    try:
        client = await _get_httpx_client()
        response = await client.request(
            method="POST",
            url=full_url,
            headers=headers,
            auth=auth,
            files=files,
            timeout=60.0,
        )
        result = _parse_response(response, full_url)
    except httpx.HTTPStatusError as e:
        result = _handle_http_status_error(e)
    except httpx.RequestError as e:
        return f"Error uploading CSV: {e}"

    if isinstance(result, dict) and result.get("error"):
        return f"Error uploading wellness CSV: {result.get('message')}"

    summary = (
        f"Wellness CSV uploaded from `{file_path}`. Default locked column applied: {locked_added}."
    )
    return summary + _unlocked_warning(locked)


# ---------------------------------------------------------------------------
# Helpers private to this module
# ---------------------------------------------------------------------------


async def _put_json(url: str, api_key: str | None, body: Any) -> Any:
    """PUT a raw JSON body (dict OR list) to the intervals.icu API.

    `make_intervals_request` only accepts dict bodies, so for the bulk
    endpoint — which takes a top-level array — we issue a minimal direct
    request, reusing the shared httpx client and config helpers.
    """
    import json as _json

    full_url, auth, headers, cfg_err = _prepare_request_config(url, api_key, "PUT")
    if cfg_err:
        return {"error": True, "message": cfg_err}

    try:
        client = await _get_httpx_client()
        response = await client.request(
            method="PUT",
            url=full_url,
            headers=headers,
            auth=auth,
            content=_json.dumps(body),
            timeout=30.0,
        )
        return _parse_response(response, full_url)
    except httpx.HTTPStatusError as e:
        return _handle_http_status_error(e)
    except httpx.RequestError as e:
        return {"error": True, "message": f"Request error: {e}"}


def _ensure_locked_column(raw: bytes, locked: bool) -> tuple[bytes, bool]:
    """Ensure the CSV's `locked` column reflects the desired default.

    Returns the (possibly rewritten) CSV bytes and a flag indicating whether
    a `locked` column was added or any row had its `locked` value filled in.

    If `locked=False`, the CSV is returned untouched — the caller has opted
    out and it's their responsibility.
    """
    if not locked:
        return raw, False

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw, False

    reader = _csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return raw, False

    header = rows[0]
    changed = False
    if "locked" not in header:
        header.append("locked")
        for r in rows[1:]:
            r.append("true")
        changed = True
    else:
        idx = header.index("locked")
        for r in rows[1:]:
            while len(r) <= idx:
                r.append("")
            if not r[idx].strip():
                r[idx] = "true"
                changed = True

    if not changed:
        return raw, False

    out = io.StringIO()
    writer = _csv.writer(out)
    writer.writerows(rows)
    return out.getvalue().encode("utf-8"), True
