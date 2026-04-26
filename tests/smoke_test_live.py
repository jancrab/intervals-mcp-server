"""Live-API smoke test (Phase 7).

Read-only sequence against the user's actual intervals.icu account. Confirms
auth, endpoint paths, and response field shapes match what client.py and
formatters.py assume.

Run from project root:
    cd intervals-icu-mcp
    uv run python tests/smoke_test_live.py

Expects credentials in .env (or process env). No writes — does not call
create_event / update_event / delete_event.

Privacy: prints field shapes and counts; redacts numeric values that could be
considered PII (HRV, weight, RHR, FTP) — we want to know "is the field
present and the right type" without dumping the values to the conversation.
"""

from __future__ import annotations

from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv()

from intervals_icu_mcp.client import IntervalsClient  # noqa: E402

# Today is taken from the actual clock so this script remains reusable.
today = date.today()
week_ago = today - timedelta(days=7)
two_weeks_ago = today - timedelta(days=14)
two_weeks_ahead = today + timedelta(days=14)

print(f"today={today.isoformat()}")
print()

with IntervalsClient() as c:
    print(f"client OK, athlete_id={c.athlete_id}")

    # 1. profile
    print("\n[1] get_athlete (profile)")
    try:
        prof = c.get_athlete()
        print(f"  type: {type(prof).__name__}")
        keys = sorted(prof.keys()) if isinstance(prof, dict) else []
        print(f"  field count: {len(keys)}")
        print(f"  first 30 keys: {keys[:30]}")
        # field presence checks (no values printed for sensitive fields)
        for k in ["id", "name", "email", "sex", "timezone", "weight",
                  "icu_ftp", "icu_resting_hr", "icu_lthr",
                  "icu_run_pace_threshold", "icu_swim_pace_threshold"]:
            present = k in prof
            value_kind = type(prof.get(k)).__name__ if present else "—"
            print(f"  has '{k}': {present} ({value_kind})")
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")

    # 2. wellness range
    print("\n[2] get_wellness_range last 7d")
    try:
        w = c.get_wellness_range(week_ago, today)
        print(f"  records: {len(w)}")
        if w:
            first = w[0]
            wkeys = sorted(first.keys())
            print(f"  field count: {len(wkeys)}")
            print(f"  first 30 keys: {wkeys[:30]}")
            for k in ["id", "hrv", "restingHR", "sleepSecs", "weight",
                      "ctl", "atl", "fatigue", "soreness", "mood", "stress"]:
                present = k in first and first.get(k) is not None
                print(f"  '{k}' present and non-null: {present}")
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")

    # 3. activities
    latest_id = None
    print("\n[3] list_activities last 14d")
    try:
        acts = c.list_activities(two_weeks_ago, today)
        print(f"  activities: {len(acts)}")
        if acts:
            latest = acts[0]
            latest_id = latest.get("id")
            akeys = sorted(latest.keys())
            print(f"  field count on first: {len(akeys)}")
            print(f"  first 30 keys: {akeys[:30]}")
            print(f"  latest type: {latest.get('type')}, "
                  f"date: {str(latest.get('start_date_local',''))[:10]}, "
                  f"id: {latest.get('id')}")
            print(f"  has icu_average_watts: {'icu_average_watts' in latest}")
            print(f"  has icu_training_load (TSS): {'icu_training_load' in latest}")
            print(f"  has icu_intensity (IF): {'icu_intensity' in latest}")
            print(f"  has decoupling: {'decoupling' in latest}")
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")

    # 4. single activity (uses latest_id from step 3)
    print("\n[4] get_activity on latest")
    if latest_id is None:
        print("  skipped — no recent activity to inspect")
    else:
        try:
            full = c.get_activity(str(latest_id))
            full_keys = sorted(full.keys())
            print(f"  field count: {len(full_keys)}")
            isum = full.get("interval_summary")
            print(f"  interval_summary present: {isum is not None}")
            if isum:
                print(f"  intervals count: {len(isum)}")
                if len(isum) > 0:
                    ikeys = sorted(isum[0].keys())
                    print(f"  first interval: {len(ikeys)} fields, sample keys: {ikeys[:20]}")
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")

    # 5. events
    print("\n[5] list_events next 14d")
    try:
        evs = c.list_events(today, two_weeks_ahead)
        print(f"  upcoming events: {len(evs)}")
        if evs:
            first = evs[0]
            ekeys = sorted(first.keys())
            print(f"  field count on first: {len(ekeys)}")
            print(f"  first 30 keys: {ekeys[:30]}")
            print(f"  first event type: {first.get('type')}, "
                  f"category: {first.get('category')}, "
                  f"date: {str(first.get('start_date_local',''))[:10]}")
            for k in ["start_date_local", "end_date_local", "type", "category",
                      "name", "load_target", "time_target", "distance_target"]:
                print(f"  has '{k}': {k in first}")
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")

print("\n=== smoke test complete ===")
