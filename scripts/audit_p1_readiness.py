"""Evidence-based operational readiness, not a declaration of P1 completion.

Runs before persistence/publication: cannot certify its own deployment or start
the seven-day production clock. Missing measurements are never green.
"""
from collections import Counter
from datetime import datetime, timedelta

def stamp(value):
    try:
        d=datetime.fromisoformat(str(value or "").replace("Z","+00:00"))
        return d if d.tzinfo is not None else None
    except (TypeError,ValueError):
        return None

def age_hours(value,now):
    d=stamp(value)
    return round((now-d).total_seconds()/3600,2) if d and d<=now else None

def measure(data,report,now):
    monitor=data.get("monitor",{})
    recall=data.get("recall",{})
    sample=recall.get("allSample",{})
    availability=report.get("publisherStatementAudit",{}).get("availabilitySample",{})
    independent=data.get("independent",{})
    ind=independent.get("summary",{})
    reconciliation=data.get("reconciliation",{})
    old_states={"article-date-observed","articles-excluded","repository-identity-matched",
                "repository-auxiliary-classified","catalog-evidence-present","no-longer-in-current-input"}
    open_tasks=[t for t in reconciliation.get("tasks",[]) if t.get("state") not in old_states]
    age=[a for t in open_tasks for a in [age_hours(t.get("firstDetectedAt"),now)] if a is not None]
    scheduled=[];unscheduled=[]
    for task in open_tasks:
        # Prefer explicit retry timestamps; a context pointer does not prove a
        # successful retry or close a gap. Missing schedule remains visible.
        stamps=[stamp(task.get("nextAttemptAt")),
                stamp((task.get("historicalRepair") or {}).get("nextAttemptAt")),
                stamp((task.get("sourceSearch") or {}).get("nextAttemptAt"))]
        due=[d for d in stamps if d is not None]
        if due:
            scheduled.append((task,min(due)))
        else:
            unscheduled.append(task)
    overdue=[t for t,d in scheduled if d<=now]
    health=data.get("health",{}).get("sources",{})
    critical=[key for key,s in health.items() if s.get("consecutiveFailures",0)>=3]
    per_source=[]
    for s in monitor.get("sources",[]):
        if not s.get("active") or not s.get("official"):
            continue
        per_source.append({"id":s["id"],"lastSuccessAt":s.get("lastSuccessAt"),
                           "ageHours":age_hours(s.get("lastSuccessAt"),now),
                           "error":s.get("error"),"deferred":bool(s.get("deferred")),
                           "matchedFamilies":len(s.get("matchedModelFamilyIds",[]))})
    source_count=len(per_source)
    source_fresh=sum(s["ageHours"] is not None and s["ageHours"]<=2 for s in per_source)
    historical=data.get("historical",{}).get("summary",{})
    # Preserve distinct denominators. Repository coverage and dated statements
    # do not independently establish release accuracy or same-stage recall.
    gates={
        "structuralIntegrity":{"status":"pass" if not report.get("errors") else "blocked",
                               "errors":len(report.get("errors",[]))},
        "negativeControls":{"status":"pass" if report.get("negativeControls",{}).get("checked")==3 and report["negativeControls"].get("incorrectConfirmed")==0 else "blocked",
                            **report.get("negativeControls",{})},
        "fixedArticleRecall":{"status":"pass" if sample.get("events")==8 and sample.get("endToEndDated")==8 and sample.get("dateConflicts")==0 else "incomplete",
                              "matched":sample.get("endToEndDated"),"events":sample.get("events"),
                              "missingIds":[r["id"] for r in recall.get("events",[]) if not r.get("endToEndDated")]},
        "availabilityStatementPilot":{"status":"pass" if availability.get("events")==2 and availability.get("matched")==2 else "incomplete",
                                     "matched":availability.get("matched"),"events":availability.get("events")},
        "sameStageEventRecall":{"status":"not-measured","reason":"No independently reviewed same-stage event benchmark and matcher for all eight cases; article and availability samples cannot be added."},
        "independentFactAccuracy":{"status":"not-measured","reason":"Repository identity observations are not audited release facts; need independently adjudicated positive and negative release events.",
                                   "repositorySamples":ind.get("inScopeRepositorySamples"),
                                   "repositoryExactMatches":ind.get("currentStates",{}).get("exact-catalog-match",0),
                                   "unmatchedRepositories":ind.get("currentStates",{}).get("unmatched-repository",0)},
        "priorityDiscoveryLatency":{"status":"not-measured","reason":"Day-precision article dates do not measure a two-hour SLA; need independently observed event timestamps and first discoveries."},
        "automaticRepairRate":{"status":"not-measured","reason":"Retained evidence counts are not a denominator of recoverable incidents; need incident-level outcomes."},
        "productionPublication":{"status":"external-verification-required","reason":"This audit precedes persistence and Pages deployment; only post-deployment checks may certify published revision."},
        "sevenDayProduction":{"status":"not-started","reason":"Requires all engineering gates and independent persisted production observations, not elapsed time or a pre-deployment audit."}
    }
    return {"schema":"p1-readiness/v1","checkedAt":now.isoformat(),
            "gates":gates,"engineeringReady":False,
            "blockingGates":[k for k,v in gates.items() if v["status"]!="pass" and k not in {"fixedArticleRecall","sevenDayProduction"}],
            "sourceHealth":{"officialSources":source_count,"successfulWithinTwoHours":source_fresh,
                            "unmeasuredSuccessAge":sum(s["ageHours"] is None for s in per_source),
                            "sources":per_source,"persistentBatchIncidents":critical,
                            "batchStates":{k:s.get("status") for k,s in health.items()}},
            "queue":{"openTasks":len(open_tasks),"byState":dict(sorted(Counter(t.get("state") or "unknown" for t in open_tasks).items())),
                     "oldestHours":max(age,default=None),"olderThan24Hours":sum(a>24 for a in age),
                     "unmeasuredAge":len(open_tasks)-len(age),"scheduled":len(scheduled),
                     "dueRetries":len(overdue),"missingRetrySchedule":len(unscheduled),
                     "dueRetryIds":[t["id"] for t in overdue],"unscheduledIds":[t["id"] for t in unscheduled]},
            "historicalContext":{"formalReleaseGaps":historical.get("activeTasks"),
                                 "tasksWithPlatformChangelogEvidence":historical.get("tasksWithPlatformChangelogEvidence"),
                                 "datedArticleRecords":historical.get("datedArticleRecords")},
            "policy":"Operational readiness diagnostics only. Unknowns remain blockers to engineering acceptance, not publication failures. Historical factual gaps remain tracked; no invented dates, release recall or success rate."}
