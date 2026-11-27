"""Persist optional-source incidents and emit an alert only on the third failure.

Skipped groups are not failures. Recovery resets the incident. Do not change
the actual snapshot timestamps; this file tracks collection attempts only.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {"aihot-selected": "AIHOT_SELECTED", "aihot-daily": "AIHOT_DAILY", "juya-daily": "JUYA_DAILY"}
CRITICAL_BATCHES = {"models-batch": "MODEL_BATCH", "recovery-batch": "RECOVERY_BATCH", "resources-batch": "RESOURCES_BATCH", "maintenance-batch": "MAINTENANCE_BATCH"}
SOURCES.update(CRITICAL_BATCHES)
THRESHOLD = 3


def incident_summary(history, now):
    """Count observed batch incidents, not hypothetical recoverable failures.

    Recovery trigger provenance is explicit; dispatch/push cannot prove an
    autonomous scheduled repair. Legacy outages are left-censored and
    excluded from the measurable cohort.
    """
    cohort = [r for r in history if r.get("origin") == "observed-failure"]
    closed = [r for r in cohort if r.get("closedAt")]
    opened = [r for r in cohort if not r.get("closedAt")]
    automatic = [r for r in closed if r.get("recoveryTrigger") == "schedule"]
    other = [r for r in closed if r.get("recoveryTrigger") != "schedule"]
    durations = []
    for row in closed:
        try:
            start = datetime.fromisoformat(row["openedAt"])
            end = datetime.fromisoformat(row["closedAt"])
            seconds = (end-start).total_seconds()
            if seconds >= 0:
                durations.append(seconds)
        except (ValueError,TypeError,KeyError):
            pass
    return {"observedIncidents":len(cohort),"openIncidents":len(opened),
            "closedIncidents":len(closed),"scheduledRecoveries":len(automatic),
            "otherOrUnknownTriggerRecoveries":len(other),
            "leftCensoredIncidents":sum(r.get("origin")=="legacy-open-unknown-start" for r in history),
            "scheduledRecoveryShareOfClosed":len(automatic)/len(closed) if closed else None,
            "durationMeasured":len(durations),"maxRecoverySeconds":max(durations,default=None),
            "policy":"Observed workflow-level failure episodes only. A scheduled successful run proves scheduled recovery, not that the root cause was repaired without human intervention. Dispatch/push excluded from scheduled numerator; no denominator of independently adjudicated recoverable failures. Empty cohort is not 100%."}


def update_incidents(previous, records, outcomes, now, run_id, trigger, attempt):
    history = [dict(r) for r in previous.get("incidents",[])]
    active = {}
    seen_ids=set()
    for row in history:
        if row.get("id") in seen_ids:
            raise ValueError("Duplicate incident identity")
        seen_ids.add(row.get("id"))
        if not row.get("closedAt"):
            if row["source"] in active:
                raise ValueError("Duplicate open source incident")
            active[row["source"]]=row
    if not run_id:
        return history
    for source,outcome in outcomes.items():
        if outcome not in {"success","failure"}:
            continue
        before=previous.get("sources",{}).get(source,{})
        row=active.get(source)
        if row is None and (outcome=="failure" or before.get("status")=="degraded"):
            # The old schema may already contain an outage. Do not invent
            # the original onset or count it as newly observed.
            legacy=before.get("status")=="degraded"
            opened=before.get("lastAttemptAt") if legacy else now
            key=hashlib.sha256(f"{source}|{run_id}|{attempt}|{opened}".encode()).hexdigest()
            row={"id":"incident-"+key,"source":source,"openedAt":opened,
                 "origin":"legacy-open-unknown-start" if legacy else "observed-failure",
                 "firstObservedRunId":run_id,"firstObservedTrigger":trigger,
                 "failedRunIds":[],"failedAttempts":[],"closedAt":None}
            history.append(row)
            active[source]=row
        if row is None:
            continue
        if outcome=="failure":
            failures=list(row.get("failedRunIds",[]))
            attempts=list(row.get("failedAttempts",[]))
            entry={"runId":run_id,"runAttempt":attempt,"trigger":trigger}
            if run_id not in failures:
                failures.append(run_id)
            if entry not in attempts:
                attempts.append(entry)
            row.update(failedRunIds=failures,failedAttempts=attempts,lastFailedAt=now)
        else:
            row.update(closedAt=now,recoveryRunId=run_id,recoveryRunAttempt=attempt,
                       recoveryTrigger=trigger)
    return history


def update_health(previous, outcomes, now, run_id=None, trigger=None, attempt=None):
    records = dict(previous.get("sources", {}))
    alerts = []
    for source, outcome in outcomes.items():
        if outcome not in {"success", "failure"}:
            continue
        before = records.get(source, {})
        seen = list(before.get("failureRunIds", []))
        duplicate = outcome == "failure" and bool(run_id) and run_id in seen
        failures = 0 if outcome == "success" else int(before.get("consecutiveFailures", 0)) + (0 if duplicate else 1)
        records[source] = {
            "lastAttemptAt": now,
            "lastSuccessAt": now if outcome == "success" else before.get("lastSuccessAt"),
            "status": "healthy" if outcome == "success" else "degraded",
            "consecutiveFailures": failures,
        }
        if outcome == "failure" and run_id:
            if not duplicate:
                seen.append(run_id)
            records[source]["failureRunIds"] = seen[-20:]
        if failures == THRESHOLD and not duplicate:
            alerts.append(source)
    result={"schemaVersion":1,"sources":records}
    # Backward-compatible unit tests and invocations without run provenance
    # cannot manufacture production incidents.
    if run_id and trigger in {"schedule","push","workflow_dispatch"}:
        history=update_incidents(previous,records,outcomes,now,run_id,trigger,attempt)
        result["incidents"]=history
        result["incidentMeasurementStartedAt"]=previous.get("incidentMeasurementStartedAt") or now
        result["incidentSummary"]=incident_summary(history,now)
    elif "incidents" in previous:
        for key in ("incidents","incidentMeasurementStartedAt","incidentSummary"):
            if key in previous:
                result[key]=previous[key]
    return result,alerts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=ROOT / "site/data/collection-health.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--critical-output", action="store_true")
    args = parser.parse_args()
    previous = json.loads(args.path.read_text(encoding="utf-8")) if args.path.exists() else {}
    outcomes = {k: os.environ.get(v, "") for k, v in SOURCES.items()}
    result, alerts = update_health(previous, outcomes, datetime.now(timezone.utc).isoformat(timespec="seconds"), os.environ.get("RADAR_RUN_ID") or None,
                                    os.environ.get("RADAR_EVENT") or None,os.environ.get("RADAR_RUN_ATTEMPT") or None)
    if result != previous and any(v in {"success", "failure"} for v in outcomes.values()):
        tmp = args.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(args.path)
    with args.output.open("a", encoding="utf-8") as stream:
        stream.write("notify=" + str(bool(alerts)).lower() + "\n")
        if args.critical_output:
            stream.write("critical_incident=" + str(any(s in CRITICAL_BATCHES for s in alerts)).lower() + "\n")
    with args.summary.open("a", encoding="utf-8") as stream:
        stream.write("### Optional briefing source health\n")
        for source, record in result["sources"].items():
            stream.write(f"- {source}: {record['status']}; consecutive failures: {record['consecutiveFailures']}\n")
            if outcomes.get(source) == "failure":
                print(f"::warning::{source} failed; retain last valid snapshot.")
        if alerts:
            stream.write("New persistent incidents: " + ", ".join(alerts) + "\n")
            print("::warning::Persistent optional-source incident: " + ", ".join(alerts) + "; last valid snapshots retained. See collection-health.json.")


if __name__ == "__main__":
    main()
