"""Offline production-log timing audit. No collectors, network or data writes."""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

# These are workflow step boundaries, not individual subprocess timestamps.
PHASES = {
    "python scripts/run_collection_batch.py models": "models",
    "python scripts/run_collection_batch.py recovery": "recovery",
    "python scripts/run_collection_batch.py resources": "resources",
    "python scripts/run_collection_batch.py maintenance": "maintenance",
    "python scripts/link_model_records.py": "model_links",
    "python scripts/preflight.py --digest-only --repair-digest": "digest_reconcile",
}
STAMP = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z) (.*)$")


def audit(text):
    phases = []
    active = None
    for line in text.splitlines():
        match = STAMP.match(line)
        if not match:
            continue
        stamp = datetime.fromisoformat(match[1].replace("Z", "+00:00"))
        msg = match[2]
        if msg.startswith("##[group]Run "):
            if active is not None:
                elapsed = (stamp - active.pop("start")).total_seconds()
                active["secondsToNextStep"] = round(elapsed, 3) if elapsed >= 0 else None
                phases.append(active)
                active = None
            command = msg[len("##[group]Run "):].strip()
            if command in PHASES:
                active = {"phase": PHASES[command], "start": stamp,
                          "committedTransactions": 0, "rolledBackTransactions": 0,
                          "budgetSkippedTransactions": 0}
        elif active is not None:
            if msg.startswith("Committed transaction in working tree: "):
                active["committedTransactions"] += 1
            elif msg.startswith("##[warning]Rolled back "):
                active["rolledBackTransactions"] += 1
            elif msg.startswith("##[warning]Collection time budget exhausted before "):
                active["budgetSkippedTransactions"] += 1
    if active is not None:
        active.pop("start")
        active["secondsToNextStep"] = None
        phases.append(active)
    return {"phases": phases, "measurement": "workflow-step-to-next-step",
            "individualTransactionSeconds": None, "networkRequestCount": None,
            "note": "Buffered child logs cannot establish per-transaction duration or complete HTTP request counts. Missing step boundaries remain unknown."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.log.read_text(encoding="utf-8")), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
