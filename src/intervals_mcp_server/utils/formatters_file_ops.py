"""
Formatters for file-operation MCP tools.

These formatters render markdown confirmations for the file_ops tool family
(uploads, binary downloads, workout-file conversions, bulk zip downloads).
Sizes are rendered human-readably (B / KB / MB / GB).

All formatters are defensive: they accept dict, list, or None for API
responses, and never raise on shape surprises — they fall back to a generic
"no body returned" message.
"""

from __future__ import annotations

from typing import Any


def _human_size(byte_size: int) -> str:
    """Render a byte count as a human-readable string (B / KB / MB / GB).

    Uses 1024-based units. For small files we keep the precision low; for
    larger files we use 1 decimal place for readability.
    """
    if byte_size < 0:
        return f"{byte_size} B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(byte_size)
    unit_idx = 0
    while size >= 1024 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1
    if unit_idx == 0:
        return f"{int(size)} {units[unit_idx]}"
    return f"{size:.1f} {units[unit_idx]}"


def _safe_path(path: str) -> str:
    """Render a filesystem path for display, defensively.

    We don't validate the path — just guard against None/non-string surprises
    so the formatter never crashes mid-render. Path traversal is the caller's
    concern; here we just want a clean display string.
    """
    if not isinstance(path, str):
        return "<invalid path>"
    return path


def format_upload_result(result: Any, file_path: str) -> str:
    """Markdown confirmation for a single-activity upload (POST /activities).

    The API typically returns the parsed Activity dict, OR (for zip-of-files
    bulk imports) a list of activity dicts. We handle both.
    """
    lines = [f"# Uploaded activity from `{_safe_path(file_path)}`", ""]

    if isinstance(result, list):
        lines.append(f"Created **{len(result)}** activities from the upload:")
        lines.append("")
        for item in result:
            if not isinstance(item, dict):
                continue
            aid = item.get("id", "?")
            name = item.get("name") or "(unnamed)"
            atype = item.get("type") or ""
            lines.append(f"- `{aid}` — {name} {f'({atype})' if atype else ''}".strip())
        return "\n".join(lines)

    if isinstance(result, dict):
        aid = result.get("id")
        name = result.get("name") or "(unnamed)"
        atype = result.get("type") or ""
        start = result.get("start_date_local") or result.get("start_date") or ""
        if aid:
            lines.append(f"- **Activity ID**: `{aid}`")
        lines.append(f"- **Name**: {name}")
        if atype:
            lines.append(f"- **Type**: {atype}")
        if start:
            lines.append(f"- **Start**: {start}")
        return "\n".join(lines)

    lines.append("Upload accepted (no activity body returned).")
    return "\n".join(lines)


def format_streams_upload_result(result: dict | list | None, activity_id: str) -> str:
    """Markdown confirmation for a streams CSV upload (PUT /streams.csv)."""
    lines = [f"# Streams uploaded for activity `{activity_id}`", ""]

    if isinstance(result, list):
        lines.append(f"- **Streams written**: {len(result)}")
    elif isinstance(result, dict):
        # The API may return the activity or a status dict.
        if "id" in result:
            lines.append(f"- **Activity ID**: `{result.get('id')}`")
        for k in ("type", "name"):
            if k in result and result[k]:
                lines.append(f"- **{k.title()}**: {result[k]}")
    else:
        lines.append("Streams upload accepted (no body returned).")
    return "\n".join(lines)


def format_workout_import_result(workout: Any) -> str:
    """Markdown confirmation for a workout file imported into a folder.

    Server returns the created `Workout` object (or array, occasionally).
    """
    lines = ["# Workout imported", ""]
    if isinstance(workout, list):
        lines.append(f"Created **{len(workout)}** workouts:")
        for w in workout:
            if not isinstance(w, dict):
                continue
            wid = w.get("id", "?")
            name = w.get("name") or "(unnamed)"
            lines.append(f"- `{wid}` — {name}")
        return "\n".join(lines)
    if isinstance(workout, dict):
        wid = workout.get("id")
        name = workout.get("name") or "(unnamed)"
        folder = workout.get("folder_id") or workout.get("folderId")
        if wid:
            lines.append(f"- **Workout ID**: `{wid}`")
        lines.append(f"- **Name**: {name}")
        if folder:
            lines.append(f"- **Folder ID**: `{folder}`")
        return "\n".join(lines)
    lines.append("Import accepted (no body returned).")
    return "\n".join(lines)


def format_download_result(
    activity_id: str,
    dest_path: str,
    byte_size: int,
    content_type: str,
    was_gzipped: bool,
) -> str:
    """Markdown confirmation card for an activity binary download.

    `was_gzipped` indicates whether the response carried a gzip
    Content-Encoding header — informational only, since httpx
    auto-decompresses transport-level gzip before we see the bytes.
    """
    lines = [
        "# Downloaded activity file",
        "",
        f"- **Activity ID**: `{activity_id}`",
        f"- **Saved to**: `{_safe_path(dest_path)}`",
        f"- **Size**: {_human_size(byte_size)}",
        f"- **Content-Type**: {content_type or '(unknown)'}",
    ]
    if was_gzipped:
        lines.append("- **Server sent**: gzip-encoded (httpx auto-decompressed before save)")
    else:
        lines.append("- **Server sent**: identity (no transport encoding)")
    return "\n".join(lines)


def format_workout_download_result(
    dest_path: str, byte_size: int, format_name: str
) -> str:
    """Markdown confirmation for a workout-file conversion download."""
    return "\n".join(
        [
            f"# Workout converted to `.{format_name}`",
            "",
            f"- **Saved to**: `{_safe_path(dest_path)}`",
            f"- **Size**: {_human_size(byte_size)}",
            f"- **Format**: {format_name}",
        ]
    )


def format_bulk_zip_download_result(dest_path: str, byte_size: int) -> str:
    """Markdown confirmation for a bulk-FIT zip download."""
    return "\n".join(
        [
            "# Bulk activity FIT archive downloaded",
            "",
            f"- **Saved to**: `{_safe_path(dest_path)}`",
            f"- **Size**: {_human_size(byte_size)}",
            "- **Format**: ZIP archive of FIT files",
        ]
    )
