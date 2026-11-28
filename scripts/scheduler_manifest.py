#!/usr/bin/env python3
"""Small validated freshness manifest, generated from actual collected snapshots."""
from __future__ import annotations
import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
try:
    from scripts.plan_refresh import GROUPS, SLOW_GROUPS, plan, read_stamp, retry_after, previously_deferred
except ModuleNotFoundError:
    from plan_refresh import GROUPS, SLOW_GROUPS, plan, read_stamp, retry_after, previously_deferred

ROOT = Path(__file__).resolve().parents[1]

def build(data_dir, now, event, run_id, attempt, schedule="", scope="", deferred=None):
    if deferred is None:
        deferred = previously_deferred(data_dir)
    if not isinstance(deferred, (list, set)) or any(not isinstance(g, str) or g not in SLOW_GROUPS for g in deferred):
        raise ValueError("Invalid deferred slow groups")
    due_now = plan(data_dir, "schedule", now=now, respect_backoff=False)
    eligible_now = plan(data_dir, "schedule", now=now)
    # Models are due at most 25 minutes after a successful check. Calculate
    # the earliest due boundary using the existing planner, not a second SLA.
    next_due = now
    for minute in range(31):
        candidate = now + timedelta(minutes=minute)
        if any(plan(data_dir, "schedule", now=candidate).values()):
            next_due = candidate
            break
    else:
        next_due = now + timedelta(minutes=30)
    groups = {}
    for group, inputs in GROUPS.items():
        values = [read_stamp(data_dir, filename, field) for filename, field in inputs]
        retry = retry_after(data_dir, group, now) if due_now[group] and not eligible_now[group] else None
        groups[group] = {
            "oldestSnapshotAt": min(values).isoformat() if all(values) else None,
            "due": due_now[group],
            "eligible": eligible_now[group],
            "retryAfter": retry.isoformat() if retry is not None else None,
        }
    return {"schema":"scheduler-health/v1", "generatedAt":now.isoformat(),
            "nextDueAt":next_due.isoformat(), "trigger":{"event":event,"runId":run_id,
            "attempt":attempt,"schedule":schedule,"scope":scope}, "groups":groups,
            "deferredSlowGroups":sorted(set(deferred)),
            "policy":"Validated snapshot freshness; due is raw staleness, eligible applies bounded retry backoff. Heartbeat is not proof every source succeeded."}

def main():
    data = ROOT / "site/data"
    now = datetime.now(timezone.utc)
    result = build(data, now, os.environ.get("RADAR_EVENT",""), os.environ.get("RADAR_RUN_ID",""),
                   os.environ.get("RADAR_RUN_ATTEMPT",""), os.environ.get("RADAR_SCHEDULE",""),
                   os.environ.get("RADAR_SCOPE",""),
                   json.loads(os.environ["RADAR_DEFERRED_SLOW_GROUPS"]) if os.environ.get("RADAR_DEFERRED_SLOW_GROUPS") else None)
    path = data / "scheduler-health.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)
    print("Scheduler heartbeat:", result["trigger"], "next due:", result["nextDueAt"])

if __name__ == "__main__":
    main()
