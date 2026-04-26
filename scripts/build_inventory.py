"""Build ENDPOINT_INVENTORY.md from intervals.icu's OpenAPI spec.

Run from the project root with the spec already saved to .tmp_spec.json.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

SPEC = Path(".tmp_spec.json")
OUT = Path("ENDPOINT_INVENTORY.md")

# Endpoints we already cover via the 12 v1 tools. Spec-path -> tool name.
ALREADY = {
    ("get",    "/api/v1/athlete/{id}/activities"):   "list_activities",
    ("get",    "/api/v1/activity/{id}"):              "get_activity (also surfaces interval_summary as get_activity_streams)",
    ("get",    "/api/v1/athlete/{id}/events"):        "list_events",
    ("get",    "/api/v1/athlete/{id}/events/{eventId}"): "get_event",
    ("post",   "/api/v1/athlete/{id}/events"):        "create_event",
    ("put",    "/api/v1/athlete/{id}/events/{eventId}"): "update_event",
    ("delete", "/api/v1/athlete/{id}/events/{eventId}"): "delete_event",
    ("get",    "/api/v1/athlete/{id}/wellness"):      "get_wellness_range (also exposed as get_fitness_curve view)",
    ("get",    "/api/v1/athlete/{id}"):               "get_athlete_profile",
}

# Tags / patterns we deliberately reject from single-user scope.
REJECT_TAGS = {
    "OAuth", "OAuth2", "Apps", "Coach", "Coaches",
    "Admin", "Internal", "Billing", "Subscriptions",
    "Webhooks",  # defer
}

# Patterns in the path that suggest we should reject.
REJECT_PATH_RE = re.compile(
    r"/oauth|/admin|/coach|/clients?/|/subscription|/billing|/webhook|/apps?/",
    re.IGNORECASE,
)


def categorize(method: str, path: str, op: dict) -> str:
    """Return one of: covered | in-scope | reject | defer | borderline."""
    key = (method.lower(), path)
    if key in ALREADY:
        return "covered"
    tags = set(op.get("tags") or [])
    if tags & REJECT_TAGS:
        return "defer" if "Webhooks" in tags else "reject"
    if REJECT_PATH_RE.search(path):
        return "reject"
    # Some endpoints may be social/chat-y — let user decide
    if {"Chats", "Messages", "Notifications", "Followers", "Activity feed", "Feed"} & tags:
        return "borderline"
    return "in-scope"


def propose_tool_name(method: str, path: str, op: dict) -> str:
    """Propose a snake_case MCP tool name."""
    op_id = op.get("operationId", "")
    # Convert camelCase operationId to snake_case
    if op_id:
        s = re.sub(r"(?<!^)(?=[A-Z])", "_", op_id).lower()
        s = re.sub(r"_+", "_", s).strip("_")
        # Tighten common patterns
        s = s.replace("by_id", "").rstrip("_")
        return s
    # Fallback: derive from path + method
    return f"{method}_{path.strip('/').replace('/', '_').replace('{', '').replace('}', '')}"


def main() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    paths = spec.get("paths", {})
    info = spec.get("info", {})

    # Walk all (path, method) operations
    ops = []  # (method_upper, path, operation_dict, category)
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            cat = categorize(method, path, op)
            ops.append((method.upper(), path, op, cat))

    total = len(ops)
    counts = Counter(cat for *_, cat in ops)

    # Group by tag for nice presentation
    by_tag: dict[str, list] = defaultdict(list)
    for method, path, op, cat in ops:
        tag = (op.get("tags") or ["(untagged)"])[0]
        by_tag[tag].append((method, path, op, cat))

    # Build markdown
    lines = []
    lines.append("# intervals.icu API endpoint inventory")
    lines.append("")
    lines.append(f"Generated {date.today().isoformat()} from `https://intervals.icu/api/v1/docs` (OpenAPI {spec.get('openapi','?')}, title \"{info.get('title','?')}\", version {info.get('version','?')}).")
    lines.append("")
    lines.append("Cross-referenced against the 12 tools shipped in `intervals-icu-mcp` v1.0.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total operations**: {total}")
    lines.append(f"- **Already covered (v1 tools)**: {counts.get('covered', 0)}")
    lines.append(f"- **To ADD (in-scope)**: {counts.get('in-scope', 0)}")
    lines.append(f"- **Borderline (chat/social — your call)**: {counts.get('borderline', 0)}")
    lines.append(f"- **Defer (webhooks)**: {counts.get('defer', 0)}")
    lines.append(f"- **Reject (OAuth / coach / admin / multi-tenant)**: {counts.get('reject', 0)}")
    lines.append("")

    # Tag-level summary
    lines.append("### Operations by tag")
    lines.append("")
    lines.append("| Tag | Total | Covered | To add | Borderline | Defer | Reject |")
    lines.append("|---|---|---|---|---|---|---|")
    for tag in sorted(by_tag.keys()):
        items = by_tag[tag]
        ccs = Counter(cat for *_, cat in items)
        lines.append(
            f"| {tag} | {len(items)} | {ccs.get('covered', 0)} | "
            f"{ccs.get('in-scope', 0)} | {ccs.get('borderline', 0)} | "
            f"{ccs.get('defer', 0)} | {ccs.get('reject', 0)} |"
        )
    lines.append("")

    # Already covered recap
    lines.append("## Already covered (v1)")
    lines.append("")
    for (mlower, path), tool in sorted(ALREADY.items()):
        lines.append(f"- `{tool}` ← `{mlower.upper()} {path}`")
    lines.append("")

    # To-ADD section, grouped by tag
    lines.append("## To ADD")
    lines.append("")
    lines.append("Each entry: proposed MCP tool name (snake_case), HTTP method+path, and a brief summary. Implementation pattern matches the existing 12 tools (Pydantic input model with `extra=\"forbid\"` → `IntervalsClient` method → markdown/JSON formatter → `@mcp.tool()` registration with `readOnlyHint` / `destructiveHint` annotations).")
    lines.append("")

    for tag in sorted(by_tag.keys()):
        items = [it for it in by_tag[tag] if it[3] == "in-scope"]
        if not items:
            continue
        lines.append(f"### {tag}")
        lines.append("")
        for method, path, op, _ in sorted(items, key=lambda x: (x[1], x[0])):
            tool = propose_tool_name(method, path, op)
            summary = (op.get("summary") or op.get("description") or "").strip().split("\n")[0][:120]
            lines.append(f"- `{tool}` — `{method} {path}` — {summary or '(no summary)'}")
        lines.append("")

    # Borderline
    border = [it for it in ops if it[3] == "borderline"]
    if border:
        lines.append("## Borderline (your call)")
        lines.append("")
        lines.append("Social / chat / feed endpoints. Useful for community features but outside training analysis. Recommend skipping for v1.5.")
        lines.append("")
        for method, path, op, _ in sorted(border, key=lambda x: (x[1], x[0])):
            tag = (op.get("tags") or ["?"])[0]
            summary = (op.get("summary") or "").strip().split("\n")[0][:100]
            lines.append(f"- `{method} {path}` (tag: {tag}) — {summary}")
        lines.append("")

    # Defer (webhooks)
    defer = [it for it in ops if it[3] == "defer"]
    if defer:
        lines.append("## Defer")
        lines.append("")
        lines.append("Push-model endpoints — outside MCP's request/response shape. Re-evaluate as a separate component if you want \"notify me when an activity uploads\".")
        lines.append("")
        for method, path, op, _ in sorted(defer, key=lambda x: (x[1], x[0])):
            summary = (op.get("summary") or "").strip().split("\n")[0][:100]
            lines.append(f"- `{method} {path}` — {summary}")
        lines.append("")

    # Reject — show counts only, not full list (could be huge)
    reject = [it for it in ops if it[3] == "reject"]
    if reject:
        lines.append("## Reject (out of single-user scope)")
        lines.append("")
        rcounts = Counter((op.get("tags") or ["?"])[0] for _, _, op, _ in reject)
        for tag, n in rcounts.most_common():
            lines.append(f"- {tag}: {n} operations")
        lines.append("")
        lines.append(f"_(Full list elided. {len(reject)} operations rejected for OAuth, coach, admin, or webhook-management reasons.)_")
        lines.append("")

    # Quirks summary — derived from method/content-type observations
    lines.append("## Quirks summary")
    lines.append("")
    quirks = []

    # Look for multipart bodies
    multipart_paths = []
    for method, path, op, cat in ops:
        rb = op.get("requestBody", {})
        content = rb.get("content", {}) if isinstance(rb, dict) else {}
        if any("multipart" in ct for ct in content):
            multipart_paths.append((method, path))
    if multipart_paths:
        quirks.append(f"**{len(multipart_paths)} multipart/form-data endpoints** (file upload). Examples: " + ", ".join(f"`{m} {p}`" for m, p in multipart_paths[:3]))

    # Look for binary / non-JSON responses
    binary_paths = []
    for method, path, op, cat in ops:
        responses = op.get("responses", {})
        for status, resp in responses.items():
            if not isinstance(resp, dict):
                continue
            content = resp.get("content", {})
            for ct in content:
                if "octet-stream" in ct or "application/zip" in ct or "application/gzip" in ct:
                    binary_paths.append((method, path, ct))
                    break
    if binary_paths:
        quirks.append(f"**{len(binary_paths)} binary-response endpoints** (file download, gzip). Examples: " + ", ".join(f"`{m} {p}` ({ct})" for m, p, ct in binary_paths[:3]))

    # Look for explicit pagination hints
    paginated = [
        (m, p) for m, p, op, _ in ops
        if any(par.get("name") in {"page", "offset", "limit", "next", "after"}
               for par in (op.get("parameters") or []))
    ]
    if paginated:
        quirks.append(f"**{len(paginated)} potentially paginated endpoints** (have `page`/`offset`/`limit`/`next`/`after` query params).")

    # Date range params (oldest/newest convention)
    range_paths = [
        (m, p) for m, p, op, _ in ops
        if {par.get("name") for par in (op.get("parameters") or [])} & {"oldest", "newest"}
    ]
    if range_paths:
        quirks.append(f"**{len(range_paths)} endpoints use the `oldest`/`newest` date-range convention** (ISO 8601, YYYY-MM-DD). Examples: " + ", ".join(f"`{m} {p}`" for m, p in range_paths[:3]))

    # Bulk write endpoints
    bulk = [(m, p) for m, p, op, _ in ops if "bulk" in p.lower()]
    if bulk:
        quirks.append(f"**{len(bulk)} bulk-write endpoints**: " + ", ".join(f"`{m} {p}`" for m, p in bulk))

    for q in quirks:
        lines.append(f"- {q}")
    lines.append("")
    lines.append("- **Wellness `locked` field**: per the cookbook, wellness writes are silently overwritten by Oura/Garmin sync unless `locked: true` is set in the payload. Skill must echo this.")
    lines.append("- **Athlete-id `0` shortcut**: documented for some GET endpoints, unverified for writes. We use the real numeric ID via required `INTERVALS_ATHLETE_ID` env var.")
    lines.append("- **Auth**: HTTP Basic with username = literal `API_KEY`, password = the user's API key. Same for all endpoints.")
    lines.append("")

    # Recommended order
    lines.append("## Recommended implementation order")
    lines.append("")
    lines.append("Sort by value-to-AITrainer-skills × implementation cost.")
    lines.append("")
    lines.append("**Wave 1 — high value, low cost** (single endpoint, simple JSON, no special handling):")
    lines.append("")

    # Heuristic: in-scope GET endpoints touching workouts / folders / calendars / power-curves
    wave1_tags = {"Workouts", "Folders", "Calendars", "Power-curves", "Power Curves", "Body Measurements", "PowerCurves"}
    for method, path, op, cat in sorted(ops, key=lambda x: (x[1], x[0])):
        if cat != "in-scope":
            continue
        tags = set(op.get("tags") or [])
        if (tags & wave1_tags) and method == "GET":
            tool = propose_tool_name(method, path, op)
            lines.append(f"  - `{tool}` ({method} {path})")
    lines.append("")
    lines.append("**Wave 2 — write extensions** (POST/PUT/DELETE on the same domains, gated by harness `permissions.ask`).")
    lines.append("")
    lines.append("**Wave 3 — file ops** (multipart upload, gzipped download).")
    lines.append("")
    lines.append("**Wave 4 — borderline social** (chat / messages / followers) — only if you want them.")
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")

    # Also produce a one-line summary for the calling assistant
    print(f"WROTE: {OUT.resolve()}")
    print(f"TOTAL_OPS: {total}")
    print(f"COVERED: {counts.get('covered', 0)}")
    print(f"IN_SCOPE: {counts.get('in-scope', 0)}")
    print(f"BORDERLINE: {counts.get('borderline', 0)}")
    print(f"DEFER: {counts.get('defer', 0)}")
    print(f"REJECT: {counts.get('reject', 0)}")


if __name__ == "__main__":
    main()
