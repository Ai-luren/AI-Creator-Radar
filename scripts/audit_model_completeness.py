#!/usr/bin/env python3
"""Report data coverage and validate explicit historical release-evidence links."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path

try:
    from scripts.collect_verify_model_releases import automatic_evidence_valid
except ModuleNotFoundError:
    from collect_verify_model_releases import automatic_evidence_valid

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


IDENTITY_REVIEW_KINDS = {
    "generation-aggregate", "rolling-alias", "evaluation-variant",
    "unversioned-alias", "service-mode", "leaderboard-snapshot",
}


def gap_kind(family, version):
    """Triage missing evidence without inferring a release date or model identity."""
    if version.get("releaseDate"):
        return "dated-without-evidence"
    if version.get("recordKind") in IDENTITY_REVIEW_KINDS:
        return "non-release-identity-review"
    if version.get("historicalMilestones"):
        return "historical-stage-only"
    if family.get("category") == "agent":
        return "agent-product-scope"
    status = str(version.get("status") or "")
    if "榜单" in status or "排行榜" in status:
        return "leaderboard-identity-review"
    if version.get("derivedFrom") or version.get("provider"):
        return "provider-variant-review"
    if "预览" in status or "Preview" in str(version.get("name") or ""):
        return "preview-stage-review"
    return "release-source-review"


def audit(families, topics, config):
    versions = {(f["id"], v["id"]): (f, v) for f in families for v in f.get("versions", [])}
    events = {e["auditId"]: (t, e) for t in topics for e in t.get("milestones", []) if e.get("auditId")}
    errors, gaps, by_category = [], [], {}
    gap_kinds, by_vendor = Counter(), {}
    for key, (family, version) in versions.items():
        category = family["category"]
        counts = by_category.setdefault(category, Counter())
        counts["versions"] += 1
        counts["dated"] += bool(version.get("releaseDate"))
        counts["evidence"] += bool(version.get("releaseEvidence"))
        vendor = family.get("vendor") or "unknown"
        vendor_counts = by_vendor.setdefault(vendor, Counter())
        vendor_counts["versions"] += 1
        vendor_counts["evidence"] += bool(version.get("releaseEvidence"))
        if not automatic_evidence_valid(family, version):
            errors.append(f"Invalid automatic release proof: {key}")
        record_kind = version.get("recordKind")
        if record_kind in IDENTITY_REVIEW_KINDS:
            identity = version.get("identityReview") or {}
            if not identity.get("reviewedAt") or not identity.get("note"):
                errors.append(f"Missing identity review: {key}")
            if version.get("releaseEvidence") or version.get("releaseDate"):
                errors.append(f"Non-release identity must not have formal release evidence: {key}")
        if not version.get("releaseEvidence"):
            kind = gap_kind(family, version)
            gap_kinds[kind] += 1
            vendor_counts["missingEvidence"] += 1
            gaps.append({"modelFamilyId": key[0], "modelVersionId": key[1], "modelName": version["name"],
                         "category": category, "vendor": vendor, "issue": "missing-release-evidence",
                         "reviewKind": kind, "status": version.get("status"),
                         "recordKind": record_kind, "identityReview": version.get("identityReview"),
                         "hasDate": bool(version.get("releaseDate")), "existingDate": version.get("releaseDate"),
                         "candidateSourceUrl": version.get("releaseUrl"),
                         "historicalStages": [m.get("stage") for m in version.get("historicalMilestones", [])]})
    milestone_count = 0
    for key, (family, version) in versions.items():
        for milestone in version.get("historicalMilestones", []):
            milestone_count += 1
            aid = milestone.get("chronicleAuditId")
            if aid not in events:
                errors.append(f"Unknown historical milestone: {key} / {aid}")
                continue
            topic, event = events[aid]
            if (family["vendor"] not in config["vendorTopics"].get(topic["id"], [])
                    or milestone.get("date") != event.get("date")
                    or milestone.get("sourceUrl") != event.get("url")
                    or milestone.get("verifiedAt") != event.get("verificationDate")
                    or event.get("autoCollected") or event.get("verificationStatus") != "已确认：型号、日期与事件性质"
                    or milestone.get("datePrecision") != ("month" if len(event.get("date", "")) == 7 else "day")
                    or milestone.get("stage") not in {"release", "early-access", "general-availability", "api-availability", "preview", "alpha", "announcement", "official-introduction", "development-milestone", "documented-availability", "model-update"}):
                errors.append(f"Invalid historical milestone: {key} / {aid}")
    seen = set()
    for link in config["links"]:
        key = link["modelFamilyId"], link["modelVersionId"]
        aid = link["chronicleAuditId"]
        if key in seen or key not in versions or aid not in events:
            errors.append(f"Invalid or duplicate explicit link: {key} / {aid}")
            continue
        seen.add(key)
        family, version = versions[key]
        topic, event = events[aid]
        evidence = version.get("releaseEvidence") or {}
        if (family["vendor"] not in config["vendorTopics"].get(topic["id"], [])
                or event.get("autoCollected") or event.get("verificationStatus") != "已确认：型号、日期与事件性质"
                or version.get("releaseDate") != event.get("date")
                or evidence.get("publishedAt") != event.get("date")
                or evidence.get("verifiedAt") != event.get("verificationDate")
                or evidence.get("sourceUrl") != event.get(link["sourceField"])
                or evidence.get("chronicleAuditId") != aid
                or evidence.get("chronicleTopicId") != topic["id"]):
            errors.append(f"Historical evidence mismatch: {key} / {aid}")
    return {"families": len(families), "versions": len(versions),
            "chronicleNodes": sum(len(t.get("milestones", [])) for t in topics),
            "explicitHistoricalLinks": len(seen), "historicalMilestones": milestone_count, "missingEvidence": len(gaps),
            "nonReleaseIdentityRecords": gap_kinds["non-release-identity-review"],
            "categories": {k: dict(v) for k, v in sorted(by_category.items())},
            "gapKinds": dict(sorted(gap_kinds.items())),
            "vendors": {k: dict(v) for k, v in sorted(by_vendor.items())},
            "gaps": gaps, "errors": errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Optional local JSON report")
    args = parser.parse_args()
    report = audit(read("site/data/models.json"), read("site/data/topics.json"),
                   read("config/chronicle-release-links.json"))
    print(json.dumps({k: v for k, v in report.items() if k != "gaps"}, ensure_ascii=False))
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
