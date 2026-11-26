#!/usr/bin/env python3
"""Report data coverage and validate explicit historical release-evidence links."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def audit(families, topics, config):
    versions = {(f["id"], v["id"]): (f, v) for f in families for v in f.get("versions", [])}
    events = {e["auditId"]: (t, e) for t in topics for e in t.get("milestones", []) if e.get("auditId")}
    errors, gaps, by_category = [], [], {}
    for key, (family, version) in versions.items():
        category = family["category"]
        counts = by_category.setdefault(category, Counter())
        counts["versions"] += 1
        counts["dated"] += bool(version.get("releaseDate"))
        counts["evidence"] += bool(version.get("releaseEvidence"))
        if not version.get("releaseEvidence"):
            gaps.append({"modelFamilyId": key[0], "modelVersionId": key[1], "modelName": version["name"],
                         "category": category, "issue": "missing-release-evidence",
                         "hasDate": bool(version.get("releaseDate"))})
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
            "explicitHistoricalLinks": len(seen), "missingEvidence": len(gaps),
            "categories": {k: dict(v) for k, v in sorted(by_category.items())},
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
