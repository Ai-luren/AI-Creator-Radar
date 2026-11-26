"""Persist optional-source incidents and emit an alert only on the third failure.

Skipped groups are not failures. Recovery resets the incident. Do not change
the actual snapshot timestamps; this file tracks collection attempts only.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {"aihot-selected": "AIHOT_SELECTED", "aihot-daily": "AIHOT_DAILY", "juya-daily": "JUYA_DAILY"}
THRESHOLD = 3


def update_health(previous, outcomes, now):
    records = dict(previous.get("sources", {}))
    alerts = []
    for source, outcome in outcomes.items():
        if outcome not in {"success", "failure"}:
            continue
        before = records.get(source, {})
        failures = 0 if outcome == "success" else int(before.get("consecutiveFailures", 0)) + 1
        records[source] = {
            "lastAttemptAt": now,
            "lastSuccessAt": now if outcome == "success" else before.get("lastSuccessAt"),
            "status": "healthy" if outcome == "success" else "degraded",
            "consecutiveFailures": failures,
        }
        if failures == THRESHOLD:
            alerts.append(source)
    return {"schemaVersion": 1, "sources": records}, alerts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=ROOT / "site/data/collection-health.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    previous = json.loads(args.path.read_text(encoding="utf-8")) if args.path.exists() else {}
    outcomes = {k: os.environ.get(v, "") for k, v in SOURCES.items()}
    result, alerts = update_health(previous, outcomes, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    if result != previous and any(v in {"success", "failure"} for v in outcomes.values()):
        tmp = args.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(args.path)
    with args.output.open("a", encoding="utf-8") as stream:
        stream.write("notify=" + str(bool(alerts)).lower() + "\n")
    with args.summary.open("a", encoding="utf-8") as stream:
        stream.write("### Optional briefing source health\n")
        for source, record in result["sources"].items():
            stream.write(f"- {source}: {record['status']}; consecutive failures: {record['consecutiveFailures']}\n")
            if outcomes.get(source) == "failure":
                print(f"::warning::{source} failed; retain last valid snapshot.")
        if alerts:
            stream.write("New persistent incidents: " + ", ".join(alerts) + "\n")


if __name__ == "__main__":
    main()
