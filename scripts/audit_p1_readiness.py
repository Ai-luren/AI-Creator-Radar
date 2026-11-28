"""Evidence-based operational readiness, not a declaration of P1 completion.

Runs before persistence/publication: cannot certify its own deployment or start
the seven-day production clock. Missing measurements are never green.
"""
from collections import Counter
from datetime import datetime, timedelta
from statistics import median

try:
    from scripts.collect_release_recall import url_key
    from scripts.collection_health import incident_summary
except ModuleNotFoundError:
    from collect_release_recall import url_key
    from collection_health import incident_summary

def stamp(value):
    try:
        d=datetime.fromisoformat(str(value or "").replace("Z","+00:00"))
        return d if d.tzinfo is not None else None
    except (TypeError,ValueError):
        return None

def age_hours(value,now):
    d=stamp(value)
    return round((now-d).total_seconds()/3600,2) if d and d<=now else None

def review_fact_sample(data):
    review=data.get("independent_fact_reviews",{})
    rows=review.get("records",[])
    if not rows:
        return None
    versions={(f["id"],v["id"]):v for f in data.get("models",[]) for v in f.get("versions",[])}
    current=[]
    for row in rows:
        ident=(row["modelFamilyId"],row["modelVersionId"])
        version=versions.get(ident,{})
        evidence=version.get("releaseEvidence") or {}
        if row["expectedStage"]=="release":
            aligned=bool(evidence.get("publishedAt")==row["expectedDay"] and evidence.get("evidenceType")=="official-release"
                         and evidence.get("modelName")==row["expectedName"]
                         and evidence.get("sourceUrl")==row["initialObserved"]["url"])
        else:
            aligned=not evidence and not version.get("releaseDate") and any(
                s.get("date")==row["expectedDay"] and s.get("stage")==row["expectedStage"]
                and s.get("sourceUrl") in row["sourceUrls"] and s.get("verifiedAt")
                for s in version.get("historicalMilestones",[]))
        current.append({"id":row["id"],"alignedWithReviewedFact":bool(aligned)})
    total=len(rows)
    initial_identity=sum(r.get("initialIdentityDateCorrect") is True for r in rows)
    initial_full=sum(r.get("initialIdentityDateCorrect") is True and r.get("initialStageCorrect") is True for r in rows)
    return {"reviewedAt":review.get("reviewedAt"),"snapshotCommit":review.get("snapshotCommit"),
            "selection":review.get("selection"),"sampleSize":total,"initialIdentityDateCorrect":initial_identity,
            "initialIdentityDateAndStageCorrect":initial_full,"initialStrictAccuracy":initial_full/total,
            "currentAlignedWithReviewedFacts":sum(r["alignedWithReviewedFact"] for r in current),
            "currentRows":current,"additionalFindingCount":len(review.get("additionalFindings",[])),
            "policy":"Purposive independently reviewed initial snapshot; current alignment is regression checking, not fresh independent re-audit or population accuracy. No claim of 99% coverage."}

def retained_feed_latency(data, now):
    """Retrospective article-observation diagnostic, not event-level SLA.

    Use only explicit publisher feed publication timestamps and recorded first
    observations. Exclude midnight (may be synthesized date-only precision),
    date corrections and ambiguous duplicate publication timestamps. No claim
    that historical backfills were live monitored or missed events observed.
    """
    active={s["id"] for s in data.get("model_source_config",[])
            if s.get("active") is True and s.get("official") is True and s.get("type")=="rss"}
    groups={}
    excluded=Counter()
    for row in data.get("updates",{}).get("items",[]):
        if row.get("sourceId") not in active or row.get("official") is not True or not row.get("modelId"):
            continue
        if row.get("updateType") not in {"announcement","release","model-release"}:
            continue
        if row.get("publicationDateKind")!="feed-published" or row.get("previousSourceDates"):
            excluded["unverified-precision-or-corrected-date"]+=1
            continue
        published=stamp(row.get("publishedAt"))
        first=stamp(row.get("firstSeenAt"))
        observed=stamp(row.get("publicationObservedAt"))
        key=(row["modelId"],url_key(row.get("url")))
        if not published or not first or not observed or not key[1] or not row.get("id"):
            excluded["missing-provenance"]+=1
            continue
        if not published.hour and not published.minute and not published.second:
            excluded["midnight-ambiguous-precision"]+=1
            continue
        if published<now-timedelta(days=30):
            excluded["outside-window"]+=1
            continue
        if not published<=first<=observed<=now:
            excluded["invalid-chronology"]+=1
            continue
        groups.setdefault(key,[]).append((published,first,row["id"]))
    rows=[]
    for (model,url),values in sorted(groups.items()):
        if len({v[0] for v in values})!=1:
            excluded["conflicting-publication-timestamps"]+=1
            continue
        published,first,_=min(values,key=lambda v:v[1])
        rows.append({"modelFamilyId":model,"url":url,"publishedAt":published.isoformat(),
                     "firstRecordedAt":first.isoformat(),"observationLagSeconds":int((first-published).total_seconds()),
                     "recordIds":sorted({v[2] for v in values})})
    seconds=[r["observationLagSeconds"] for r in rows]
    return {"status":"observed-only" if rows else "no-eligible-observations",
            "windowDays":30,"observedArticles":len(rows),
            "withinTwoHours":sum(s<=7200 for s in seconds),
            "medianSeconds":median(seconds) if seconds else None,"maxSeconds":max(seconds,default=None),
            "excluded":dict(sorted(excluded.items())),"rows":rows,
            "policy":"Retained precise official feed article publication to first recorded observation; includes historical backfill, excludes unknown and missed events. Not independent same-stage event latency, live publication time or a two-hour SLA denominator."}


# Frozen before the new collector instrumentation; older publications are
# excluded even if re-observed or assigned a precise timestamp later.
PROSPECTIVE_FEED_START="2026-11-28T02:00:38+00:00"


def prospective_feed_latency(data,now):
    """Observed-only forward cohort, not independent event recall or SLA."""
    start=stamp(PROSPECTIVE_FEED_START)
    active={s["id"] for s in data.get("model_source_config",[])
            if s.get("active") is True and s.get("official") is True and s.get("type")=="rss"}
    groups={}
    invalid=Counter()
    for row in data.get("updates",{}).get("items",[]):
        if row.get("sourceId") not in active or row.get("official") is not True or not row.get("modelId"):
            continue
        if row.get("updateType") not in {"announcement","release","model-release"}:
            continue
        published=stamp(row.get("publishedAt"))
        if not published or published<start:
            invalid["historical-or-undated"]+=1
            continue
        if published<now-timedelta(days=30):
            invalid["outside-window"]+=1
            continue
        first=stamp(row.get("firstSeenAt"))
        upper=stamp(row.get("feedTimestampFirstObservedBy"))
        precise=stamp(row.get("preciseFeedPublishedAt"))
        key=(row["modelId"],url_key(row.get("url")))
        if not key[1] or not row.get("id"):
            invalid["missing-identity"]+=1
            continue
        # Group all current candidate timestamps even when one record lacks
        # precise provenance; conflicting duplicates cannot yield a hit.
        value=groups.setdefault(key,{"dates":set(),"rows":[],"blocked":False})
        value["dates"].add(published)
        if row.get("feedTimestampConflict") or row.get("previousSourceDates"):
            value["blocked"]=True
        if (row.get("publicationDateKind")!="feed-published" or precise!=published
                or first is None or upper is None or not start<=first<=upper<=now
                or not published<=upper):
            invalid["missing-precise-post-baseline-observation"]+=1
            continue
        value["rows"].append((upper,row["id"]))
    rows=[]
    for (family,url),value in sorted(groups.items()):
        if value["blocked"] or len(value["dates"])!=1:
            invalid["conflicting-publication-timestamps"]+=1
            continue
        if not value["rows"]:
            continue
        published=next(iter(value["dates"]))
        upper=min(x[0] for x in value["rows"])
        rows.append({"modelFamilyId":family,"url":url,"publishedAt":published.isoformat(),
                     "firstPreciseObservationBy":upper.isoformat(),
                     "observationLagUpperBoundSeconds":int((upper-published).total_seconds()),
                     "recordIds":sorted({x[1] for x in value["rows"]})})
    seconds=[r["observationLagUpperBoundSeconds"] for r in rows]
    return {"status":"observed-only" if rows else "awaiting-new-observations",
            "measurementStart":PROSPECTIVE_FEED_START,"windowDays":30,
            "observedArticles":len(rows),"withinTwoHours":sum(s<=7200 for s in seconds),
            "withinTwoHoursShare":sum(s<=7200 for s in seconds)/len(seconds) if seconds else None,
            "medianUpperBoundSeconds":median(seconds) if seconds else None,
            "maxUpperBoundSeconds":max(seconds,default=None),"excluded":dict(sorted(invalid.items())),
            "rows":rows,"policy":"Only post-baseline official feed model article observations with explicit timezone/seconds and post-read clock. Historical backfill excluded by publication cutoff; observations retained within current 30-day window. Missed events and publisher coverage are not independently measured; not a same-stage event SLA."}


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
        "sameStageEventRecall":report.get("sameStageRecall",{"status":"not-measured","reason":"No independently reviewed same-stage event benchmark and matcher for all eight cases; article and availability samples cannot be added."}),
        "independentFactAccuracy":{"status":"not-measured","reason":"Repository identity observations are not audited release facts; need independently adjudicated positive and negative release events.",
                                   "repositorySamples":ind.get("inScopeRepositorySamples"),
                                   "repositoryExactMatches":ind.get("currentStates",{}).get("exact-catalog-match",0),
                                   "unmatchedRepositories":ind.get("currentStates",{}).get("unmatched-repository",0)},
        "priorityDiscoveryLatency":{"status":"not-measured","reason":"Day-precision article dates do not measure a two-hour SLA; need independently observed event timestamps and first discoveries."},
        "automaticRepairRate":{"status":"not-measured","reason":"Retained evidence counts are not a denominator of recoverable incidents; need incident-level outcomes."},
        "productionPublication":{"status":"external-verification-required","reason":"This audit precedes persistence and Pages deployment; only post-deployment checks may certify published revision."},
        "sevenDayProduction":{"status":"not-started","reason":"Requires all engineering gates and independent persisted production observations, not elapsed time or a pre-deployment audit."}
    }
    gates["priorityDiscoveryLatency"]["retainedFeedDiagnostic"]=retained_feed_latency(data,now)
    gates["priorityDiscoveryLatency"]["prospectiveFeedDiagnostic"]=prospective_feed_latency(data,now)
    gates["automaticRepairRate"]["observedBatchIncidentDiagnostic"]=incident_summary(data.get("health",{}).get("incidents",[]),now)
    fact_review=review_fact_sample(data)
    if fact_review:
        gates["independentFactAccuracy"].update(status="incomplete",reason="Initial independent factual review measured; purposive sample is not representative and does not establish 99% accuracy.",factReview=fact_review)
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
