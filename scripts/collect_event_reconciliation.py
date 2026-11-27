#!/usr/bin/env python3
"""Shadow evidence ledger and durable gap reconciliation; never write canonical facts."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

try:
    from scripts.collect_models import write_json
    from scripts.collect_release_recall import url_key
    from scripts.audit_model_completeness import audit
    from scripts.event_identity import associate_leads, day, identify, model_index
    from scripts.collect_source_search import augment_discovery
except ModuleNotFoundError:
    from collect_models import write_json
    from collect_release_recall import url_key
    from audit_model_completeness import audit
    from event_identity import associate_leads, day, identify, model_index
    from collect_source_search import augment_discovery

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site/data/event-reconciliation.json"


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def evidence_id(row):
    return "evidence-" + digest({k: v for k, v in row.items() if k != "id"})


def task_id(*identity):
    return "task-" + digest(identity)


def reconcile(families, discovery, resolution, gaps, previous, now, product_state=None, search_state=None):
    stamp = now.isoformat(timespec="seconds")
    if previous and previous.get("schema") != "event-reconciliation/v1":
        raise ValueError("Unrecognized evidence ledger schema; refusing to replace it")
    ledger = {}
    for row in previous.get("evidence", []):
        if row.get("id") != evidence_id(row) or row["id"] in ledger:
            raise ValueError("Invalid or duplicate stored evidence")
        ledger[row["id"]] = row
    prior_count = len(ledger)
    current = set()
    versions = {}
    index = model_index(families)

    def append(kind, fid, vid, source, asserted, verified, ref, precision="day"):
        if not url_key(source) or not asserted:
            return
        body = {"claimType": kind, "modelFamilyId": fid, "modelVersionId": vid,
                "sourceUrl": source, "assertedDate": asserted, "datePrecision": precision,
                "originalVerificationAt": verified, "sourceRecordId": ref}
        eid = evidence_id(body)
        ledger.setdefault(eid, {"id": eid, **body})
        current.add(eid)

    for family in families:
        fid = family["id"]
        for version in family.get("versions", []):
            vid = version["id"]
            versions[(fid, vid)] = version
            proof = version.get("releaseEvidence") or {}
            if day(proof.get("publishedAt")) and proof.get("verifiedAt"):
                append("catalog-release", fid, vid, proof.get("sourceUrl"), proof["publishedAt"],
                       proof["verifiedAt"], proof.get("eventId"))
            for milestone in version.get("historicalMilestones", []):
                value = milestone.get("date")
                if milestone.get("verifiedAt") and milestone.get("stage") and value:
                    append("historical-" + milestone["stage"], fid, vid, milestone.get("sourceUrl"),
                           value, milestone["verifiedAt"], milestone.get("chronicleAuditId"),
                           milestone.get("datePrecision") or "unknown")

    probes = defaultdict(list)
    for row in resolution.get("items", []):
        url = url_key(row.get("url"))
        if not url:
            continue
        probes[url].append(row)
        proof = row if row.get("status") == "article-date-verified" else (
            row.get("lastVerifiedObservation") if row.get("status") == "fetch-failed" else None)
        if not proof or not proof.get("modelId") or not day(proof.get("articlePublishedAt")):
            continue
        identity = identify(index, proof.get("title"), family_id=proof["modelId"])
        append("article-publication", proof["modelId"], identity[1] if identity else None,
               row["url"], proof["articlePublishedAt"],
               proof.get("firstVerifiedAt") or proof.get("checkedAt"), row.get("id"),
               "publisher-timestamp-or-day")

    # Historical records persist even if the original URL becomes inaccessible.
    # Current canonical assertions remain separate from historic observations.
    by_release = defaultdict(set)
    for row in ledger.values():
        if row["claimType"] == "catalog-release":
            by_release[(row["modelFamilyId"], row["modelVersionId"])].add(row["assertedDate"][:10])
    conflicts = [{"modelFamilyId": fid, "modelVersionId": vid, "historicalDates": sorted(values)}
                 for (fid, vid), values in sorted(by_release.items()) if len(values) > 1]

    old_tasks = {}
    for task in previous.get("tasks", []):
        if not task.get("id") or task["id"] in old_tasks:
            raise ValueError("Invalid or duplicate stored reconciliation task")
        old_tasks[task["id"]] = task
    tasks = {}

    def save(tid, payload):
        old = old_tasks.get(tid, {})
        tasks[tid] = {"id": tid, "firstDetectedAt": old.get("firstDetectedAt", stamp), **payload}

    # Recompute associations from raw original URLs, not cached associations.
    leads = associate_leads([dict(r) for r in discovery.get("items", [])], families)
    grouped = defaultdict(list)
    for lead in leads:
        if lead.get("sourceId") == "local-official-candidates" or lead.get("dateKind") == "repository-created-at":
            continue
        identity = lead.get("canonicalModelIdentity")
        reported = day(lead.get("reportedAt"))
        if identity and reported:
            k = ("model-lead", identity["modelFamilyId"], identity["modelVersionId"], reported)
        else:
            k = ("unclassified-lead", lead["id"])
        grouped[k].append(lead)

    for k, rows in sorted(grouped.items()):
        tid = task_id(*k)
        raw_urls = {url_key(u): u for r in rows for u in r.get("officialArticleUrls", []) if url_key(u)}
        states = {url: sorted({p.get("status", "unknown") for p in probes[url]}) for url in sorted(raw_urls)}
        if not raw_urls:
            state = "needs-source"
        elif any(not values for values in states.values()):
            state = "awaiting-probe"
        elif any(s not in {"article-date-verified", "not-model-announcement", "outside-current-window"}
                 for values in states.values() for s in values):
            state = "probe-unresolved"
        elif any("article-date-verified" in values for values in states.values()):
            state = "article-date-observed"
        else:
            state = "articles-excluded"
        identity = rows[0].get("canonicalModelIdentity") if k[0] == "model-lead" else None
        next_attempt = min((p["nextAttemptAt"] for url in raw_urls for p in probes[url]
                            if p.get("nextAttemptAt") and p.get("status") not in
                            {"article-date-verified", "not-model-announcement", "outside-current-window"}),
                           default=None)
        save(tid, {"taskType": "lead-review", "identity": identity,
                   "reportedDay": k[-1] if identity else day(rows[0].get("reportedAt")),
                   "state": state, "leadIds": sorted({r["id"] for r in rows}),
                   "sourceIds": sorted({r["sourceId"] for r in rows}),
                   "titles": sorted({r["title"] for r in rows}),
                   "lastSourceObservationAt": max((r.get("lastSeenAt") or r.get("firstSeenAt") or "" for r in rows), default="") or None,
                   "originalUrls": sorted(raw_urls.values()), "probeStates": states,
                   "nextAttemptAt": next_attempt})

    # Catalog observations are not publication evidence. Stage only recent additions
    # or recent third-party metadata claims; known catalog identities do not imply omissions.
    product_state = product_state or {}
    for event in product_state.get("events", []):
        if event.get("eventType") not in {"added-to-catalog", "baseline-recent-reported-date"}:
            continue
        ident = event.get("identity")
        if ident and (ident.get("modelFamilyId"), ident.get("modelVersionId")) in versions:
            continue
        product = event["product"]
        save(task_id("product-observation", event["sourceId"], event["productKey"]), {
            "taskType": "product-observation", "identity": None, "state": "needs-product-identity",
            "modelName": product.get("name"), "sourceUrl": event["sourceUrl"],
            "productId": product.get("productId"), "observedAt": event["observedAt"],
            "reportedReleaseDate": product.get("reportedReleaseDate"), "claimType": "catalog-observation",
            "sourceEventId": event["id"]})

    for gap in gaps:
        if gap.get("reviewKind") != "release-source-review":
            continue
        fid, vid = gap["modelFamilyId"], gap["modelVersionId"]
        save(task_id("release-gap", fid, vid), {"taskType": "release-gap",
             "identity": {"modelFamilyId": fid, "modelVersionId": vid},
             "state": "needs-release-evidence", "modelName": gap.get("modelName"),
             "candidateSourceUrl": gap.get("candidateSourceUrl"), "existingDate": gap.get("existingDate")})

    for tid, old in old_tasks.items():
        if tid in tasks:
            continue
        identity = old.get("identity") or {}
        version = versions.get((identity.get("modelFamilyId"), identity.get("modelVersionId")), {})
        state = ("catalog-evidence-present" if old["taskType"] == "release-gap" and version.get("releaseEvidence")
                 else "no-longer-in-current-input")
        tasks[tid] = {**old, "state": state}

    # A search task may have useful historical or product context even when the
    # external index is blocked. Link it, but do not close an unresolved event
    # on a catalog listing, a different date, or a prior canonical assertion.
    searches = (search_state or {}).get("targets", [])
    by_identity = {(s["identity"]["modelFamilyId"], s["identity"]["modelVersionId"]): s
                   for s in searches if s.get("active") and s.get("identity")}
    by_origin = {origin: s for s in searches if s.get("active") for origin in s.get("originIds", [])}
    for task in tasks.values():
        obj = task.get("identity") or {}
        target = by_identity.get((obj.get("modelFamilyId"), obj.get("modelVersionId"))) or by_origin.get(task["id"])
        if not target:
            target = next((by_origin[lead] for lead in task.get("leadIds", []) if lead in by_origin), None)
        if target:
            task["sourceSearch"] = {"targetId": target["id"], "status": target.get("status", "awaiting-search"),
                                    "nextAttemptAt": target.get("nextAttemptAt"),
                                    "localContextKinds": dict(sorted(Counter(r["kind"] for r in target.get("localContext", [])).items())),
                                    "indexCandidates": sum(bool(r.get("officialCandidateUrl")) for r in target.get("results", [])),
                                    "indexReports": sum(not r.get("officialCandidateUrl") for r in target.get("results", []))}
        else:
            task.pop("sourceSearch", None)

    counts = dict(sorted(Counter(t["state"] for t in tasks.values()).items()))
    return {"schema": "event-reconciliation/v1", "checkedAt": stamp,
            "inputObservations": {"discovery": discovery.get("checkedAt"), "resolution": resolution.get("checkedAt")},
            "evidence": sorted(ledger.values(), key=lambda r: r["id"]),
            "currentEvidenceIds": sorted(current), "historicalReleaseDateDifferences": conflicts,
            "tasks": sorted(tasks.values(), key=lambda r: r["id"]),
            "summary": {"evidenceCount": len(ledger), "newEvidence": len(ledger)-prior_count,
                        "currentlyReferencedEvidence": len(current),
                        "relatedLeads": sum(bool(r.get("relatedArticleCandidates")) for r in leads),
                        "taskStates": counts},
            "policy": "Shadow reconciliation only. Same-model same-day reports are related leads, not equivalent release claims. Historical evidence is retained, not re-certified. No canonical facts are changed."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--discovery", type=Path)
    parser.add_argument("--resolution", type=Path)
    parser.add_argument("--product-state", type=Path)
    parser.add_argument("--source-search", type=Path)
    args = parser.parse_args()
    def read(path, optional=False):
        if optional and not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    directory = ROOT / "site/data"
    families = read(directory / "models.json")
    report = audit(families, read(directory / "topics.json"), read(ROOT / "config/chronicle-release-links.json"))
    if report["errors"]:
        raise ValueError("Cannot reconcile an invalid canonical catalog")
    discovery = read(args.discovery or directory / "cross-platform-discovery.json")
    search_state = read(args.source_search or directory / "source-search.json", optional=True)
    result = reconcile(families, augment_discovery(discovery, search_state),
                       read(args.resolution or directory / "lead-resolution.json"),
                       report["gaps"], read(OUTPUT, optional=True), datetime.now(timezone.utc),
                       read(args.product_state or directory / "product-state.json", optional=True), search_state)
    print("Event reconciliation:", json.dumps(result["summary"], ensure_ascii=False))
    if not args.dry_run:
        write_json(OUTPUT, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
