#!/usr/bin/env python3
"""Read the existing system audit; do not create new facts or another database."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def acceptance(report):
    if report.get("schema") != "radar-system-audit/v1":
        raise ValueError("Unsupported system audit")
    readiness = report["p1Readiness"]
    if readiness.get("schema") != "p1-readiness/v1":
        raise ValueError("Unsupported readiness schema")
    gates = readiness["gates"]
    stage = gates["sameStageEventRecall"]
    if stage != report.get("sameStageRecall"):
        raise ValueError("Same-stage audit and readiness disagree")
    article = gates["fixedArticleRecall"]
    blockers = readiness["blockingGates"]
    if not isinstance(blockers,list) or len(blockers)!=len(set(blockers)):
        raise ValueError("Invalid blocker list")
    expected = {k for k,v in gates.items() if v.get("status")!="pass"
                and k not in {"fixedArticleRecall","sevenDayProduction"}}
    if set(blockers)!=expected:
        raise ValueError("Readiness blockers disagree with gate states")
    missing_article = article.get("missingIds",[])
    if not isinstance(missing_article,list) or len(missing_article)!=len(set(missing_article)):
        raise ValueError("Invalid fixed-article missing IDs")
    stage_missing = None
    article_only = None
    if stage.get("status") in {"pass","incomplete"}:
        rows = stage["rows"]
        ids = [row["id"] for row in rows]
        if len(ids)!=8 or len(set(ids))!=8 or stage.get("events")!=8:
            raise ValueError("Invalid fixed same-stage denominator")
        for row in rows:
            if type(row.get("matched")) is not bool:
                raise ValueError("Missing explicit same-stage decision")
            hit = row["matched"]
            if hit and (row.get("dateConflict") is not False or not (
                    row.get("originalArticleMatched") is True or
                    (row.get("alternateStatementMatched") is True and row.get("alternateEvidenceIds")))):
                raise ValueError("Same-stage hit lacks valid evidence")
        stage_missing = sorted(r["id"] for r in rows if not r["matched"])
        if sorted(stage["missingIds"])!=stage_missing or stage["matched"]!=8-len(stage_missing):
            raise ValueError("Same-stage totals disagree with per-event decisions")
        if (stage["status"]=="pass") != (not stage_missing):
            raise ValueError("Same-stage pass contradicts missing events")
        article_only = sorted(set(missing_article)-set(stage_missing))
        if not set(missing_article)<=set(ids):
            raise ValueError("Article gap outside fixed event identities")
    return {"auditCheckedAt":report.get("checkedAt"),
            "sameStageEventRecall":{"status":stage.get("status"),"matched":stage.get("matched"),
                                    "events":stage.get("events"),"missingIds":stage_missing,
                                    "originalArticleMatches":stage.get("originalArticleMatches"),
                                    "alternateOnlyMatches":stage.get("alternateOnlyMatches")},
            "fixedArticleRecall":{"status":article.get("status"),"matched":article.get("matched"),
                                  "events":article.get("events"),"missingIds":sorted(missing_article),
                                  "articleOnlyGapIds":article_only,"blocking":False},
            "independentFactAccuracy":gates["independentFactAccuracy"],
            "priorityDiscoveryLatency":gates["priorityDiscoveryLatency"],
            "automaticRepairRate":gates["automaticRepairRate"],
            "structuralIntegrity":gates["structuralIntegrity"],
            "negativeControls":gates["negativeControls"],
            "blockingGates":blockers,
            "productionPublication":gates["productionPublication"],
            "policy":"Read-only pre-publication audit; article access gaps are not same-stage misses. No fresh transport or deployment proof."}


def render_acceptance(report):
    a=acceptance(report)
    stage,article=a["sameStageEventRecall"],a["fixedArticleRecall"]
    def count(g):
        return f"{g['matched']}/{g['events']}" if g["matched"] is not None and g["events"] is not None else "not measured"
    def names(values):
        return ", ".join(values) if values else ("not measured" if values is None else "none")
    feed=a["priorityDiscoveryLatency"].get("retainedFeedDiagnostic",{})
    prospective=a["priorityDiscoveryLatency"].get("prospectiveFeedDiagnostic",{})
    incident=a["automaticRepairRate"].get("observedBatchIncidentDiagnostic",{})
    return "\n".join([
        "### Acceptance (pre-publication, not a deployment certificate)",
        f"Audit checked: {a['auditCheckedAt']}",
        f"- Same-stage event recall: {count(stage)} ({stage['status']}); missing: {names(stage['missingIds'])}",
        f"- Fixed original-article recall: {count(article)} ({article['status']}, non-blocking); missing: {names(article['missingIds'])}",
        f"- Article-only gaps, do not reopen as event misses: {names(article['articleOnlyGapIds'])}",
        f"- Independent factual accuracy: {a['independentFactAccuracy']['status']}",
        f"- Priority discovery latency: {a['priorityDiscoveryLatency']['status']}; retained feed article diagnostic: {feed.get('observedArticles', 'not measured')} observations (not SLA)",
        f"- Prospective precise feed cohort: {prospective.get('observedArticles', 'not measured')} observations; within two hours: {prospective.get('withinTwoHours', 'not measured')} (observed only, not independent SLA)",
        f"- Automatic repair rate: {a['automaticRepairRate']['status']}; observed batch incidents: {incident.get('observedIncidents', 'not measured')} (not recoverable-incident denominator)",
        f"- Structural integrity: {a['structuralIntegrity']['status']}; negative controls: {a['negativeControls']['status']}",
        f"- Blocking gates: {names(a['blockingGates'])}",
        "- Verify production persistence and Pages separately against actual revision.",
    ])+"\n"


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--path",type=Path,default=ROOT/"site/data/system-audit.json")
    p.add_argument("--json",action="store_true")
    a=p.parse_args()
    report=json.loads(a.path.read_text(encoding="utf-8"))
    print(json.dumps(acceptance(report),ensure_ascii=False,indent=2) if a.json else render_acceptance(report))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
