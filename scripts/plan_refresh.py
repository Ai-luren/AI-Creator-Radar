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
    "models": (("model-monitor-status.json", "checkedAt"), ("chronicle-updates-status.json", "checkedAt"), ("model-releases-30d.json", "updatedAt")),
    "selected": (("aihot-items.json", "fetchedAt"),),
    "aihot_daily": (("aihot-daily.json", "fetchedAt"),),
    "juya_daily": (("juya-daily.json", "fetchedAt"),),
    "resources": (("resource-status.json", "checkedAt"), ("reference-rankings.json", "fetchedAt")),
    "maintenance": (("model-resource-status.json", "checkedAt"), ("creator-link-status.json", "checkedAt"), ("creator-opportunity-discovery.json", "checkedAt")),
}
INTERVAL_MINUTES = {"models": 25, "selected": 25, "aihot_daily": 10, "juya_daily": 10, "resources": 350, "maintenance": 1430}
MANUAL = {
    "all": set(GROUPS),
    "models": {"models", "selected"},
    "resources": {"resources", "aihot_daily", "juya_daily"},
    "maintenance": {"maintenance"},
    "deploy-only": set(),
}


def read_stamp(data_dir, filename, field):
    try:
        value = json.loads((data_dir / filename).read_text(encoding="utf-8")).get(field)
        if not isinstance(value, str) or "T" not in value:
            return None
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


DAILY_HOURS = {"aihot_daily": 8, "juya_daily": 10}
CHINA = timezone(timedelta(hours=8))
MORNING_CRON = "5,15 0,2 * * *"


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


def plan(data_dir, event, scope="", now=None, schedule=""):
    now = now or datetime.now(timezone.utc)
    if event == "workflow_dispatch":
        selected = MANUAL[scope]
        return {group: group in selected for group in GROUPS}
    if event not in {"push", "schedule"}:
        raise ValueError("Unsupported production event")
    result = {}
    for group, inputs in GROUPS.items():
        if event == 'schedule' and schedule == MORNING_CRON and group not in DAILY_HOURS:
            result[group] = False
            continue
        if group in DAILY_HOURS:
            result[group] = daily_due(data_dir, group, now)
            continue
        minutes = INTERVAL_MINUTES[group]
        # A collector/configuration push need not rerun recently attempted fast collectors.
        if event == "push" and group in {"models", "selected"}:
            minutes = 120
        stamps = [read_stamp(data_dir, filename, field) for filename, field in inputs]
        result[group] = any(stamp is None or stamp > now or now - stamp >= timedelta(minutes=minutes) for stamp in stamps)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, choices=("push", "schedule", "workflow_dispatch"))
    parser.add_argument("--scope", default="", choices=("", *MANUAL))
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
