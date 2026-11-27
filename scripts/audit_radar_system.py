#!/usr/bin/env python3
"""Cross-module adversarial audit: structural errors fail; coverage gaps stay visible."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
try:
    from scripts.audit_model_completeness import audit
    from scripts.audit_discovery_coverage import inspect_leads
    from scripts.collect_release_recall import url_key
    from scripts.plan_refresh import plan
    from scripts.collect_models import write_json, title_identity
except ModuleNotFoundError:
    from audit_model_completeness import audit
    from audit_discovery_coverage import inspect_leads
    from collect_release_recall import url_key
    from plan_refresh import plan
    from collect_models import write_json, title_identity
ROOT=Path(__file__).resolve().parents[1]

def inspect(data, config, now):
    families=data["models"]
    topics=data["topics"]
    report=audit(families,topics,config)
    errors=list(report["errors"])
    all_events=[e for t in topics for e in t.get("milestones",[])]
    audit_ids=Counter(e["auditId"] for e in all_events if e.get("auditId"))
    if any(n>1 for n in audit_ids.values()): errors.append("Duplicate reviewed chronicle IDs")
    version_keys={(f["id"],v["id"]) for f in families for v in f.get("versions",[])}
    if len(version_keys)!=sum(len(f.get("versions",[])) for f in families): errors.append("Duplicate canonical version IDs")
    if len({f["id"] for f in families})!=len(families): errors.append("Duplicate canonical family IDs")
    digest=data["digest"]
    ids=Counter(r["id"] for r in digest.get("items",[]))
    if any(n>1 for n in ids.values()): errors.append("Duplicate confirmed release event IDs")
    if any((r.get("modelFamilyId"),r.get("modelVersionId")) not in version_keys for r in digest.get("items",[])):
        errors.append("Unresolved confirmed release identity")
    negatives=data.get("recall",{}).get("negativeControls",[])
    if any(n.get("incorrectConfirmedIds") for n in negatives): errors.append("Negative-control article incorrectly confirmed")
    pending_keys=Counter((r.get("modelFamilyId"),url_key(r.get("url")),title_identity(r.get("title") or ""),str(r.get("publishedAt") or "")[:10]) for r in digest.get("pending",[]))
    monitor=data.get("monitor",{})
    coverage=monitor.get("effectiveCoverage",{})
    recall=data.get("recall",{}).get("activeWindow",{})
    evidence_queue = sorted((g for g in report["gaps"] if g["reviewKind"] == "release-source-review"),
                            key=lambda g: (g["category"] not in {"video", "image"}, g["vendor"], g["modelFamilyId"], g["modelVersionId"]))
    return {"schema":"radar-system-audit/v1","checkedAt":now.isoformat(),"errors":errors,
            "releaseEvidenceReview": evidence_queue,
            "counts":{"families":report["families"],"versions":report["versions"],"chronicleNodes":report["chronicleNodes"],
                      "missingEvidence":report["missingEvidence"],"formalReleaseEvidenceGaps":report["gapKinds"].get("release-source-review",0),
                      "confirmedRecentReleases":len(digest.get("items",[])),"pendingRecentCandidates":len(digest.get("pending",[])),
                      "duplicatePendingCandidates":sum(n-1 for n in pending_keys.values() if n>1)},
            "gapKinds":report["gapKinds"],"sourceCoverage":coverage,"sampleRecall":recall,
            "externalLeadCoverage":inspect_leads(data.get("discovery",{}),data.get("resolution",{})),
            "negativeControls":{"checked":len(negatives),"incorrectConfirmed":sum(len(n.get("incorrectConfirmedIds",[])) for n in negatives)},
            "scopeNote":"Structural checks are not exhaustive source-level fact verification, ranking accuracy or visual review."}

def main():
    p=argparse.ArgumentParser();p.add_argument("--write",action="store_true");a=p.parse_args()
    directory=ROOT/"site/data"
    def read(name):return json.loads((directory/name).read_text(encoding="utf-8"))
    data={k:read(v) for k,v in {"models":"models.json","topics":"topics.json","digest":"model-releases-30d.json",
              "recall":"release-recall-status.json","monitor":"model-monitor-status.json"}.items()}
    for key,name in (("discovery","cross-platform-discovery.json"),("resolution","lead-resolution.json")):
        data[key]=read(name) if (directory/name).exists() else {}
    now=datetime.now(timezone.utc)
    report=inspect(data,json.loads((ROOT/"config/chronicle-release-links.json").read_text(encoding="utf-8")),now)
    report["dueScopes"]=[k for k,v in plan(directory,"schedule",now=now,respect_backoff=False).items() if v]
    report["eligibleScopes"]=[k for k,v in plan(directory,"schedule",now=now).items() if v]
    print("System audit:",json.dumps(report,ensure_ascii=False))
    if a.write:write_json(directory/"system-audit.json",report)
    return 1 if report["errors"] else 0
if __name__=="__main__":raise SystemExit(main())
