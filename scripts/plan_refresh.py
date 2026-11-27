"""Plan overdue collectors from persisted timestamps, not the cron string.

GitHub schedules are best effort. A missed tick is recovered by a later
scheduled run or a collector/configuration push. No source timestamp is rewritten here.
"""
import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "models": (("model-monitor-status.json", "checkedAt"), ("chronicle-updates-status.json", "checkedAt"), ("model-releases-30d.json", "updatedAt"), ("cross-platform-discovery.json", "checkedAt"), ("lead-resolution.json", "checkedAt"), ("model-intake.json", "checkedAt"), ("release-recall-status.json", "checkedAt"), ("model-release-verification-status.json", "checkedAt"), ("event-reconciliation.json", "checkedAt"), ("product-state.json", "checkedAt"), ("source-search.json", "checkedAt"), ("event-claims.json", "checkedAt"), ("independent-coverage.json", "checkedAt"), ("historical-evidence.json", "checkedAt")),
    "selected": (("aihot-items.json", "fetchedAt"),),
    "aihot_daily": (("aihot-daily.json", "fetchedAt"),),
    "juya_daily": (("juya-daily.json", "fetchedAt"),),
    "resources": (("resource-status.json", "checkedAt"), ("reference-rankings.json", "fetchedAt"), ("maomu-rankings.json", "checkedAt"), ("unified-rankings.json", "calculatedAt"), ("aipick-data.json", "fetchedAt"), ("social-trends.json", "fetchedAt")),
    "maintenance": (("model-resource-status.json", "checkedAt"), ("creator-link-status.json", "checkedAt"), ("creator-opportunity-discovery.json", "checkedAt"), ("model-evaluations.json", "generatedAt")),
}
INTERVAL_MINUTES = {"models": 25, "selected": 25, "aihot_daily": 10, "juya_daily": 10, "resources": 350, "maintenance": 1430}
MANUAL = {
    "all": set(GROUPS),
    "models": {"models", "selected"},
    "resources": {"resources", "aihot_daily", "juya_daily"},
    "maintenance": {"maintenance"},
    "deploy-only": set(),
}


def last_model_success(data):
    """A failed check never makes the last successful read newer."""
    if "lastSuccessfulCheckAt" in data:
        return data["lastSuccessfulCheckAt"]
    if data.get("successSources") == 0:
        return max((s["lastSuccessAt"] for s in data.get("sources", [])
                    if isinstance(s.get("lastSuccessAt"), str)), default=None)
    return data.get("checkedAt")


def model_check_stamps(previous, now, success_count, total):
    complete = previous.get("lastCompleteCheckAt")
    if "lastCompleteCheckAt" not in previous and previous.get("successSources", 0) > 0 and previous.get("failedSources") == 0:
        complete = previous.get("checkedAt")
    return {
        "lastSuccessfulCheckAt": now if success_count else last_model_success(previous),
        "lastCompleteCheckAt": now if total and success_count == total else complete,
    }


def read_stamp(data_dir, filename, field):
    try:
        data = json.loads((data_dir / filename).read_text(encoding="utf-8"))
        value = last_model_success(data) if filename == "model-monitor-status.json" and field == "checkedAt" else data.get(field)
        # A successful conditional 304 validates the existing representation.
        # Only selected news supports this field; never reinterpret daily issue dates.
        if filename == "aihot-items.json" and field == "fetchedAt" and isinstance(data.get("items"), list):
            try:
                downloaded = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                checked = datetime.fromisoformat(str(data.get("checkedAt")).replace("Z", "+00:00"))
                if downloaded.tzinfo and checked.tzinfo and checked >= downloaded:
                    value = data["checkedAt"]
            except (ValueError, TypeError):
                pass
        if not isinstance(value, str) or "T" not in value:
            return None
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


DAILY_HOURS = {"aihot_daily": 8, "juya_daily": 10}
CHINA = timezone(timedelta(hours=8))
MORNING_CRON = "5,15 0,2 * * *"  # old workflow attempts may still be rerun
MORNING_CRONS = {MORNING_CRON, "15,25 0,2 * * *"}


def daily_due(data_dir, group, now):
    filename, field = GROUPS[group][0]
    local = now.astimezone(CHINA)
    expected = local.date() if (local.hour, local.minute) >= (DAILY_HOURS[group], 5) else local.date() - timedelta(days=1)
    try:
        data = json.loads((data_dir / filename).read_text(encoding="utf-8"))
        text = str(data.get("title") or "")
        match = re.search(r"(20\d{2})\s*[-年]\s*(\d{1,2})\s*[-月]\s*(\d{1,2})", text)
        from datetime import date
        issue = date(*map(int, match.groups())) if match else None
    except (OSError, ValueError, AttributeError, TypeError):
        issue = None
    stamp = read_stamp(data_dir, filename, field)
    if issue is not None and expected <= issue <= local.date() and stamp is not None and stamp <= now and stamp.astimezone(CHINA).date() >= issue:
        return False
    if stamp is None or stamp > now:
        return True
    return now - stamp >= timedelta(minutes=10)


# Delay only a group with a recorded failure, never unrelated collectors.
# Keep the cap within the existing 30-minute scheduler heartbeat horizon.
HEALTH_SOURCE = {"models": "models-batch", "selected": "aihot-selected",
                 "aihot_daily": "aihot-daily", "juya_daily": "juya-daily",
                 "resources": "resources-batch", "maintenance": "maintenance-batch"}


def retry_after(data_dir, group, now):
    try:
        state = json.loads((data_dir / "collection-health.json").read_text(encoding="utf-8"))
        record = state["sources"][HEALTH_SOURCE[group]]
        count = record["consecutiveFailures"]
        if record["status"] != "degraded" or type(count) is not int or count < 1:
            return None
        attempt = datetime.fromisoformat(record["lastAttemptAt"].replace("Z", "+00:00"))
        if attempt.tzinfo is None or attempt > now:
            return None
        return attempt + timedelta(minutes=15 if count == 1 else 30)
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        # Missing or invalid health metadata must not hide overdue snapshots.
        return None


def plan(data_dir, event, scope="", now=None, schedule="", respect_backoff=True):
    now = now or datetime.now(timezone.utc)
    if event == "workflow_dispatch" and scope == "due":
        event = "schedule"
    if event == "workflow_dispatch":
        selected = MANUAL[scope]
        return {group: group in selected for group in GROUPS}
    if event not in {"push", "schedule"}:
        raise ValueError("Unsupported production event")
    result = {}
    for group, inputs in GROUPS.items():
        if event == 'schedule' and schedule in MORNING_CRONS and group not in DAILY_HOURS:
            result[group] = False
            continue
        if group in DAILY_HOURS:
            result[group] = daily_due(data_dir, group, now)
            continue
        minutes = INTERVAL_MINUTES[group]
        # Production pushes are restricted to collector/config/workflow paths.
        # Always exercise the model transaction on these changes: a green
        # validation-only run must not masquerade as a production smoke test.
        if event == "push" and group == "models":
            result[group] = True
            continue
        if event == "push" and group == "selected":
            minutes = 120
        stamps = [read_stamp(data_dir, filename, field) for filename, field in inputs]
        result[group] = any(stamp is None or stamp > now or now - stamp >= timedelta(minutes=minutes) for stamp in stamps)
    if respect_backoff:
        for group, due in result.items():
            if not due or (event == "push" and group == "models"):
                continue
            retry = retry_after(data_dir, group, now)
            if retry is not None and now < retry:
                result[group] = False
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, choices=("push", "schedule", "workflow_dispatch"))
    parser.add_argument("--scope", default="", choices=("", "due", *MANUAL))
    parser.add_argument("--schedule", default="")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "site" / "data")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = plan(args.data_dir, args.event, args.scope, schedule=args.schedule)
    result["collect"] = any(result.values())
    with args.output.open("a", encoding="utf-8") as stream:
        for key, value in result.items():
            stream.write(f"{key}={str(value).lower()}\n")
    print("Collector plan:", json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
