"""
File-operation MCP tools for Intervals.icu.

This module exposes the nine endpoints that move binary files (FIT, TCX,
GPX, ZWO, MRC, ERG, ZIP) between the local filesystem and intervals.icu:

Multipart uploads (3):
- `upload_activity`               — POST   /athlete/{id}/activities
- `upload_activity_streams_csv`   — PUT    /activity/{id}/streams.csv
- `import_workout_file`           — POST   /athlete/{id}/folders/{folderId}/import-workout

Binary downloads (4):
- `download_activity_file`        — GET    /activity/{id}/file
- `download_activity_fit_file`    — GET    /activity/{id}/fit-file
- `download_activity_gpx_file`    — GET    /activity/{id}/gpx-file
- `download_activity_fit_files`   — POST   /athlete/{id}/download-fit-files

Workout-file conversion (2):
- `download_workout`              — POST   /download-workout.{ext}
- `download_workout_for_athlete`  — POST   /athlete/{id}/download-workout.{ext}

NOTE: these tools touch the local filesystem of wherever the MCP server is
running. `file_path` (uploads) and `dest_path` (downloads) refer to that
machine's filesystem, not the user's. Callers must pass paths that are
valid on the server host.

`make_intervals_request` parses every response as JSON, so for both
multipart uploads and binary downloads we use the lower-level httpx
helpers directly, the same pattern used in `wellness_writes.upload_wellness_csv`
and `activity_writes._put_json_body`.

Read vs. write classification (for permissions/audit):
- WRITES (mutate server state): `upload_activity`,
  `upload_activity_streams_csv`, `import_workout_file`,
  `download_activity_fit_files` (reads server state but POSTs a body — the
  POST body specifies which activities to bundle; idempotent but uses a
  POST verb so we treat it as a write for audit purposes).
- READS: `download_activity_file`, `download_activity_fit_file`,
  `download_activity_gpx_file`, `download_workout`,
  `download_workout_for_athlete`.

The two `download_workout*` tools are POSTs (because the workout document
is the request body), but they don't mutate server state — they're
file-format converters that happen to use POST for body-shape reasons.
They're treated as reads.

Re: gzip — the intervals.icu API returns binary downloads with
`Content-Encoding: gzip` set as a transport-level encoding. httpx
automatically decompresses transport-level gzip before exposing the bytes,
so the bytes our tools save are already decoded (raw FIT / GPX / TCX). The
`keep_gzip` parameter on the activity-file download tools triggers a
re-compression of the bytes and saves them as a `.gz` companion to
preserve a compressed copy on disk.
"""

from __future__ import annotations

import gzip
import json as _json
import logging
import os
from typing import Any, Literal

import httpx  # pylint: disable=import-error

from intervals_mcp_server.api.client import (
    _get_httpx_client,  # pylint: disable=protected-access
    _prepare_request_config,  # pylint: disable=protected-access
    _parse_response,  # pylint: disable=protected-access
    _handle_http_status_error,  # pylint: disable=protected-access
)
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.formatters_file_ops import (
    format_bulk_zip_download_result,
    format_download_result,
    format_streams_upload_result,
    format_upload_result,
    format_workout_download_result,
    format_workout_import_result,
)
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

logger = logging.getLogger("intervals_icu_mcp_server")
config = get_config()


# Allowed workout download formats. Anything outside this set is rejected
# before we hit the API.
WorkoutFormat = Literal["zwo", "mrc", "erg", "fit"]
_ALLOWED_FORMATS: set[str] = {"zwo", "mrc", "erg", "fit"}


# ---------------------------------------------------------------------------
# Local filesystem helpers
# ---------------------------------------------------------------------------


def _content_type_for(filename: str) -> str:
    """Infer a content-type from the filename's extension."""
    lower = filename.lower()
    if lower.endswith(".fit"):
        return "application/octet-stream"
    if lower.endswith(".gpx"):
        return "application/gpx+xml"
    if lower.endswith(".tcx"):
        return "application/vnd.garmin.tcx+xml"
    if lower.endswith(".csv"):
        return "text/csv"
    if lower.endswith(".zip"):
        return "application/zip"
    if lower.endswith(".gz"):
        return "application/gzip"
    if lower.endswith(".zwo"):
        return "application/xml"
    if lower.endswith(".mrc") or lower.endswith(".erg"):
        return "text/plain"
    return "application/octet-stream"


def _read_local_file(file_path: str) -> tuple[bytes | None, str | None]:
    """Read a file from disk, returning `(bytes, error)`.

    On error (path empty, file missing, unreadable), returns `(None, "msg")`
    with a friendly message. On success, returns `(bytes, None)`.
    """
    if not isinstance(file_path, str) or not file_path.strip():
        return None, "Error: file_path is empty."
    if not os.path.exists(file_path):
        return None, f"Error: file not found at `{file_path}`."
    if not os.path.isfile(file_path):
        return None, f"Error: `{file_path}` is not a regular file."
    try:
        with open(file_path, "rb") as fh:
            return fh.read(), None
    except OSError as e:
        return None, f"Error reading `{file_path}`: {e}"


def _validate_dest_path(dest_path: str) -> str | None:
    """Validate a destination path (parent dir must exist).

    Returns an error message or None if valid. We deliberately do NOT
    auto-create parent directories — that would be magical and might write
    to unexpected locations.
    """
    if not isinstance(dest_path, str) or not dest_path.strip():
        return "Error: dest_path is empty."
    parent = os.path.dirname(os.path.abspath(dest_path))
    if not os.path.isdir(parent):
        return (
            f"Error: parent directory `{parent}` does not exist. Create it before "
            "downloading (this tool does not auto-create directories)."
        )
    return None


def _write_local_file(dest_path: str, data: bytes) -> str | None:
    """Write bytes to disk, returning an error message or None."""
    try:
        with open(dest_path, "wb") as fh:
            fh.write(data)
    except OSError as e:
        return f"Error writing `{dest_path}`: {e}"
    return None


# ---------------------------------------------------------------------------
# Direct-httpx helpers for multipart and binary
# ---------------------------------------------------------------------------


async def _multipart_request(
    method: str,
    url: str,
    api_key: str | None,
    files: dict[str, tuple[str, bytes, str]],
    form_fields: dict[str, str] | None = None,
    timeout: float = 120.0,
) -> Any:
    """Send a multipart/form-data request and parse JSON.

    Mirrors the pattern in `wellness_writes.upload_wellness_csv`: bypass the
    JSON-only `make_intervals_request` and call httpx directly with a
    `files=` payload.
    """
    full_url, auth, headers, cfg_err = _prepare_request_config(url, api_key, method)
    if cfg_err:
        return {"error": True, "message": cfg_err}
    # multipart sets its own Content-Type with boundary; strip ours.
    headers.pop("Content-Type", None)

    try:
        client = await _get_httpx_client()
        response = await client.request(
            method=method,
            url=full_url,
            headers=headers,
            auth=auth,
            files=files,
            data=form_fields or None,
            timeout=timeout,
        )
        return _parse_response(response, full_url)
    except httpx.HTTPStatusError as e:
        return _handle_http_status_error(e)
    except httpx.RequestError as e:
        return {"error": True, "message": f"Request error: {e}"}


async def _binary_get(
    url: str, api_key: str | None, timeout: float = 120.0
) -> dict[str, Any]:
    """GET a binary resource. Returns a dict:

      {"error": False, "bytes": <bytes>, "content_type": str,
       "content_encoding": str | None, "filename": str | None}

    On error: {"error": True, "message": "..."} (matching the shape used by
    other tools in this codebase).

    Note: httpx auto-decompresses transport-level gzip before exposing
    `.content`. The `content_encoding` field surfaces what the server
    declared, for the formatter to mention.
    """
    full_url, auth, headers, cfg_err = _prepare_request_config(url, api_key, "GET")
    if cfg_err:
        return {"error": True, "message": cfg_err}
    # We're not expecting JSON — let the server pick.
    headers["Accept"] = "*/*"

    try:
        client = await _get_httpx_client()
        response = await client.request(
            method="GET",
            url=full_url,
            headers=headers,
            auth=auth,
            timeout=timeout,
        )
        if response.status_code >= 400:
            return _handle_http_status_error(
                httpx.HTTPStatusError(
                    "binary download failed", request=response.request, response=response
                )
            )
        # Filename from Content-Disposition, if any.
        cd = response.headers.get("content-disposition", "") or ""
        filename: str | None = None
        if "filename=" in cd:
            filename = cd.split("filename=", 1)[1].strip().strip('"').strip(";").strip()
        return {
            "error": False,
            "bytes": response.content,
            "content_type": response.headers.get("content-type") or "",
            "content_encoding": response.headers.get("content-encoding"),
            "filename": filename,
        }
    except httpx.HTTPStatusError as e:
        return _handle_http_status_error(e)
    except httpx.RequestError as e:
        return {"error": True, "message": f"Request error: {e}"}


async def _binary_post(
    url: str,
    api_key: str | None,
    body: Any,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """POST a JSON body and receive a binary response. Same return shape as `_binary_get`."""
    full_url, auth, headers, cfg_err = _prepare_request_config(url, api_key, "POST")
    if cfg_err:
        return {"error": True, "message": cfg_err}
    headers["Accept"] = "*/*"
    headers["Content-Type"] = "application/json"

    try:
        client = await _get_httpx_client()
        response = await client.request(
            method="POST",
            url=full_url,
            headers=headers,
            auth=auth,
            content=_json.dumps(body) if body is not None else None,
            timeout=timeout,
        )
        if response.status_code >= 400:
            return _handle_http_status_error(
                httpx.HTTPStatusError(
                    "binary download failed", request=response.request, response=response
                )
            )
        cd = response.headers.get("content-disposition", "") or ""
        filename: str | None = None
        if "filename=" in cd:
            filename = cd.split("filename=", 1)[1].strip().strip('"').strip(";").strip()
        return {
            "error": False,
            "bytes": response.content,
            "content_type": response.headers.get("content-type") or "",
            "content_encoding": response.headers.get("content-encoding"),
            "filename": filename,
        }
    except httpx.HTTPStatusError as e:
        return _handle_http_status_error(e)
    except httpx.RequestError as e:
        return {"error": True, "message": f"Request error: {e}"}


def _save_with_optional_gzip(
    dest_path: str, raw_bytes: bytes, was_gzipped: bool, keep_gzip: bool
) -> str | None:
    """Write bytes to disk, optionally re-gzipping them.

    httpx already decoded transport-level gzip, so `raw_bytes` is the
    decoded payload. If the caller wants to retain a `.gz` on disk
    (`keep_gzip=True` AND the server sent gzip), we re-compress the bytes
    before writing.
    """
    if keep_gzip and was_gzipped:
        return _write_local_file(dest_path, gzip.compress(raw_bytes))
    return _write_local_file(dest_path, raw_bytes)


# ===========================================================================
# Multipart uploads
# ===========================================================================


@mcp.tool()
async def upload_activity(  # pylint: disable=too-many-arguments
    file_path: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    name: str | None = None,
    description: str | None = None,
    external_id: str | None = None,
) -> str:
    """Upload a FIT, TCX, GPX (or zip/gz of same) as a new activity.

    Calls POST /athlete/{id}/activities with the file at `file_path`
    attached as multipart/form-data, plus optional form fields `name`,
    `description`, `external_id`.

    LOCAL-FS: `file_path` is read from the filesystem of wherever the MCP
    server is running. Pass an absolute path you know is reachable from
    that machine.

    Args:
        file_path: Path to the activity file to upload.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
        name: Optional display name to apply to the new activity.
        description: Optional description text.
        external_id: Optional caller-supplied identifier (used for
            de-duplication on subsequent uploads).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    raw, read_err = _read_local_file(file_path)
    if read_err:
        return read_err
    assert raw is not None  # narrowed by read_err check

    filename = os.path.basename(file_path) or "upload.bin"
    files = {"file": (filename, raw, _content_type_for(filename))}
    form: dict[str, str] = {}
    if name is not None:
        form["name"] = name
    if description is not None:
        form["description"] = description
    if external_id is not None:
        form["external_id"] = external_id

    result = await _multipart_request(
        "POST",
        f"/athlete/{athlete_id_to_use}/activities",
        api_key,
        files=files,
        form_fields=form or None,
    )
    if isinstance(result, dict) and result.get("error"):
        return f"Error uploading activity: {result.get('message')}"

    return format_upload_result(result, file_path)


@mcp.tool()
async def upload_activity_streams_csv(
    activity_id: str,
    file_path: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Upload a CSV stream file to overwrite an activity's streams.

    Calls PUT /activity/{id}/streams.csv with the CSV at `file_path`
    attached as multipart/form-data. The CSV must follow intervals.icu's
    streams CSV format.

    LOCAL-FS: `file_path` is read from the MCP server's filesystem.

    Args:
        activity_id: Intervals.icu activity ID.
        file_path: Path to the CSV file to upload.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not activity_id:
        return "Error: No activity ID provided."
    _ = athlete_id_to_use  # this URL is activity-scoped

    raw, read_err = _read_local_file(file_path)
    if read_err:
        return read_err
    assert raw is not None

    filename = os.path.basename(file_path) or "streams.csv"
    files = {"file": (filename, raw, "text/csv")}

    result = await _multipart_request(
        "PUT",
        f"/activity/{activity_id}/streams.csv",
        api_key,
        files=files,
    )
    if isinstance(result, dict) and result.get("error"):
        return f"Error uploading streams CSV: {result.get('message')}"

    return format_streams_upload_result(result, activity_id)


@mcp.tool()
async def import_workout_file(
    folder_id: str,
    file_path: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Import a workout file (.zwo / .mrc / .erg / .fit) into a folder.

    Calls POST /athlete/{id}/folders/{folderId}/import-workout with the
    file at `file_path` attached as multipart/form-data. Creates a new
    workout in the named folder.

    LOCAL-FS: `file_path` is read from the MCP server's filesystem.

    Args:
        folder_id: Workout-folder ID to import into.
        file_path: Path to the .zwo / .mrc / .erg / .fit file.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if not folder_id:
        return "Error: folder_id is required."

    raw, read_err = _read_local_file(file_path)
    if read_err:
        return read_err
    assert raw is not None

    filename = os.path.basename(file_path) or "workout.bin"
    files = {"file": (filename, raw, _content_type_for(filename))}

    result = await _multipart_request(
        "POST",
        f"/athlete/{athlete_id_to_use}/folders/{folder_id}/import-workout",
        api_key,
        files=files,
    )
    if isinstance(result, dict) and result.get("error"):
        return f"Error importing workout file: {result.get('message')}"

    return format_workout_import_result(result)


# ===========================================================================
# Binary downloads
# ===========================================================================


@mcp.tool()
async def download_activity_file(
    activity_id: str,
    dest_path: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    keep_gzip: bool = False,
) -> str:
    """Download the original activity file (FIT/TCX/GPX) for a single activity.

    Calls GET /activity/{id}/file. The server typically declares
    `Content-Encoding: gzip` as a transport-level encoding. httpx
    auto-decompresses that, so by default we write the **decoded** bytes
    (a usable raw FIT/TCX/GPX file).

    NOTE: Strava-imported activities don't have an original file and will
    return a 404.

    LOCAL-FS: writes to `dest_path` on the MCP server's filesystem. The
    parent directory must already exist (we don't auto-create).

    Args:
        activity_id: Intervals.icu activity ID.
        dest_path: Local filesystem path to save to.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
        keep_gzip: If True AND the server sent `Content-Encoding: gzip`,
            re-compress the decoded bytes and save them as gzip — useful
            if the caller wants a `.gz` companion. Defaults to False.
    """
    if dst_err := _validate_dest_path(dest_path):
        return dst_err
    if not activity_id:
        return "Error: No activity ID provided."
    # athlete_id is accepted for parameter consistency; URL is activity-scoped.
    _athlete_id, _err = resolve_athlete_id(athlete_id, config.athlete_id)

    result = await _binary_get(f"/activity/{activity_id}/file", api_key)
    if result.get("error"):
        return f"Error downloading activity file: {result.get('message')}"

    raw_bytes: bytes = result["bytes"]
    was_gzipped = (result.get("content_encoding") or "").lower() == "gzip"
    write_err = _save_with_optional_gzip(dest_path, raw_bytes, was_gzipped, keep_gzip)
    if write_err:
        return write_err

    saved_size = len(gzip.compress(raw_bytes)) if (keep_gzip and was_gzipped) else len(raw_bytes)
    return format_download_result(
        activity_id=activity_id,
        dest_path=dest_path,
        byte_size=saved_size,
        content_type=result.get("content_type") or "",
        was_gzipped=was_gzipped,
    )


@mcp.tool()
async def download_activity_fit_file(
    activity_id: str,
    dest_path: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    keep_gzip: bool = False,
) -> str:
    """Download intervals.icu's regenerated FIT for an activity.

    Calls GET /activity/{id}/fit-file. Unlike `download_activity_file`,
    this is intervals.icu's own FIT (always available, includes any power
    corrections / smoothing applied on the server). Server sends with
    `Content-Encoding: gzip`; httpx auto-decompresses, so we save raw FIT
    by default. Set `keep_gzip=True` to retain a gzip-compressed copy.

    LOCAL-FS: writes to `dest_path`. Parent directory must exist.

    Args:
        activity_id: Intervals.icu activity ID.
        dest_path: Local filesystem path to save to.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
        keep_gzip: Save as `.gz` if the server sent gzip-encoded content.
            Defaults to False (save raw FIT).
    """
    if dst_err := _validate_dest_path(dest_path):
        return dst_err
    if not activity_id:
        return "Error: No activity ID provided."
    _athlete_id, _err = resolve_athlete_id(athlete_id, config.athlete_id)

    result = await _binary_get(f"/activity/{activity_id}/fit-file", api_key)
    if result.get("error"):
        return f"Error downloading FIT file: {result.get('message')}"

    raw_bytes: bytes = result["bytes"]
    was_gzipped = (result.get("content_encoding") or "").lower() == "gzip"
    write_err = _save_with_optional_gzip(dest_path, raw_bytes, was_gzipped, keep_gzip)
    if write_err:
        return write_err

    saved_size = len(gzip.compress(raw_bytes)) if (keep_gzip and was_gzipped) else len(raw_bytes)
    return format_download_result(
        activity_id=activity_id,
        dest_path=dest_path,
        byte_size=saved_size,
        content_type=result.get("content_type") or "",
        was_gzipped=was_gzipped,
    )


@mcp.tool()
async def download_activity_gpx_file(
    activity_id: str,
    dest_path: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
    keep_gzip: bool = False,
) -> str:
    """Download intervals.icu's regenerated GPX for an activity.

    Calls GET /activity/{id}/gpx-file. May 404 for activities without GPS
    data (indoor rides, virtual rides, lap-pool swims). Same gzip
    semantics as the FIT downloads.

    LOCAL-FS: writes to `dest_path`. Parent directory must exist.

    Args:
        activity_id: Intervals.icu activity ID.
        dest_path: Local filesystem path to save to.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
        keep_gzip: Save as `.gz` if the server sent gzip-encoded content.
            Defaults to False (save raw GPX/XML).
    """
    if dst_err := _validate_dest_path(dest_path):
        return dst_err
    if not activity_id:
        return "Error: No activity ID provided."
    _athlete_id, _err = resolve_athlete_id(athlete_id, config.athlete_id)

    result = await _binary_get(f"/activity/{activity_id}/gpx-file", api_key)
    if result.get("error"):
        return f"Error downloading GPX file: {result.get('message')}"

    raw_bytes: bytes = result["bytes"]
    was_gzipped = (result.get("content_encoding") or "").lower() == "gzip"
    write_err = _save_with_optional_gzip(dest_path, raw_bytes, was_gzipped, keep_gzip)
    if write_err:
        return write_err

    saved_size = len(gzip.compress(raw_bytes)) if (keep_gzip and was_gzipped) else len(raw_bytes)
    return format_download_result(
        activity_id=activity_id,
        dest_path=dest_path,
        byte_size=saved_size,
        content_type=result.get("content_type") or "",
        was_gzipped=was_gzipped,
    )


@mcp.tool()
async def download_activity_fit_files(
    activity_ids: list[Any],
    dest_path: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Bulk-download regenerated FIT files for multiple activities, as a ZIP.

    Calls POST /athlete/{id}/download-fit-files with a JSON body listing
    the activity IDs to bundle. Server returns `application/zip`; we save
    the bytes verbatim — ZIP is its own format and isn't gzip-decoded.

    LOCAL-FS: writes a ZIP archive to `dest_path`. Parent directory must
    exist.

    Args:
        activity_ids: List of activity IDs (strings like `"i12345"` or
            ints — both forms are accepted; the server matches by ID).
        dest_path: Local filesystem path for the resulting ZIP file.
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if dst_err := _validate_dest_path(dest_path):
        return dst_err
    if not isinstance(activity_ids, list) or not activity_ids:
        return "Error: `activity_ids` must be a non-empty list."

    body = {"activity_ids": activity_ids}
    result = await _binary_post(
        f"/athlete/{athlete_id_to_use}/download-fit-files", api_key, body
    )
    if result.get("error"):
        return f"Error downloading bulk FIT zip: {result.get('message')}"

    raw_bytes: bytes = result["bytes"]
    write_err = _write_local_file(dest_path, raw_bytes)
    if write_err:
        return write_err

    return format_bulk_zip_download_result(dest_path, len(raw_bytes))


# ===========================================================================
# Workout-file conversion (POST → binary)
# ===========================================================================


def _validate_format(fmt: str) -> str | None:
    if not isinstance(fmt, str) or fmt.lower() not in _ALLOWED_FORMATS:
        return f"Error: format must be one of {sorted(_ALLOWED_FORMATS)}; got `{fmt}`."
    return None


@mcp.tool()
async def download_workout(
    workout: dict[str, Any],
    dest_path: str,
    format: str = "zwo",  # pylint: disable=redefined-builtin
    api_key: str | None = None,
) -> str:
    """Convert a workout document (POST body) to a workout-file format.

    Calls POST /download-workout.{format} (global path — no athlete prefix).
    The `workout` dict is the request body. Supported `format` values:
    "zwo", "mrc", "erg", "fit".

    LOCAL-FS: writes the converted file to `dest_path`. Parent directory
    must exist.

    Args:
        workout: A Workout document dict (steps / intervals / metadata).
            Shape per intervals.icu's Workout schema. The simplest form is
            `{"name": "...", "steps": [...]}`.
        dest_path: Local filesystem path for the resulting file.
        format: One of "zwo" | "mrc" | "erg" | "fit". Defaults to "zwo".
        api_key: API key (optional; defaults to API_KEY env var).
    """
    if fmt_err := _validate_format(format):
        return fmt_err
    if dst_err := _validate_dest_path(dest_path):
        return dst_err
    if not isinstance(workout, dict):
        return "Error: `workout` must be a dict (Workout document)."

    fmt = format.lower()
    result = await _binary_post(f"/download-workout.{fmt}", api_key, workout)
    if result.get("error"):
        return f"Error converting workout: {result.get('message')}"

    raw_bytes: bytes = result["bytes"]
    # Most workout formats aren't transport-encoded gzip, but if they are,
    # let httpx have done its job; we save the decoded bytes.
    write_err = _write_local_file(dest_path, raw_bytes)
    if write_err:
        return write_err

    return format_workout_download_result(dest_path, len(raw_bytes), fmt)


@mcp.tool()
async def download_workout_for_athlete(
    workout: dict[str, Any],
    dest_path: str,
    format: str = "zwo",  # pylint: disable=redefined-builtin
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Convert a workout to a file for a specific athlete (uses athlete settings).

    Calls POST /athlete/{id}/download-workout.{format}. Same body and
    formats as `download_workout`, but the athlete-scoped variant uses
    that athlete's FTP/zones/sport-settings to resolve any percentage
    targets in the workout.

    Body shape: pass a Workout document (typically the same shape returned
    by `get_workout`). To convert by ID, fetch the workout first via
    `get_workout` and pass the resulting dict.

    LOCAL-FS: writes the converted file to `dest_path`. Parent directory
    must exist.

    Args:
        workout: Workout document dict (or `{"id": <int>}` — the server
            also accepts an ID-only body for some formats).
        dest_path: Local filesystem path for the resulting file.
        format: One of "zwo" | "mrc" | "erg" | "fit". Defaults to "zwo".
        athlete_id: Athlete ID (optional; defaults to ATHLETE_ID env var).
        api_key: API key (optional; defaults to API_KEY env var).
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    if fmt_err := _validate_format(format):
        return fmt_err
    if dst_err := _validate_dest_path(dest_path):
        return dst_err
    if not isinstance(workout, dict):
        return "Error: `workout` must be a dict (Workout document or {'id': <int>})."

    fmt = format.lower()
    result = await _binary_post(
        f"/athlete/{athlete_id_to_use}/download-workout.{fmt}", api_key, workout
    )
    if result.get("error"):
        return f"Error converting workout for athlete: {result.get('message')}"

    raw_bytes: bytes = result["bytes"]
    write_err = _write_local_file(dest_path, raw_bytes)
    if write_err:
        return write_err

    return format_workout_download_result(dest_path, len(raw_bytes), fmt)
