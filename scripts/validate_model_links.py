#!/usr/bin/env python3
"""Validate canonical model IDs and cross-section model references."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def main() -> int:
    families = read("site/data/models.json")
    errors = []
    family_ids = [family.get("id") for family in families]
    if len(family_ids) != len(set(family_ids)):
        errors.append("duplicate model family IDs")
    family_map = {family["id"]: family for family in families}
    versions = set()
    version_map = {}
    for family in families:
        family_version_ids = [version.get("id") for version in family.get("versions", [])]
        if len(family_version_ids) != len(set(family_version_ids)):
            errors.append(f"duplicate model version IDs within family {family['id']}")
        for version in family.get("versions", []):
            version_id = version.get("id")
            if not version_id:
                errors.append(f"{family['id']}: version without ID")
            else:
                versions.add((family["id"], version_id))
                version_map[(family["id"], version_id)] = version
            evidence = version.get("releaseEvidence")
            if evidence:
                if not evidence.get("eventId") or not evidence.get("sourceUrl") or not evidence.get("publishedAt"):
                    errors.append(f"{family['id']}/{version_id}: release evidence needs eventId, publishedAt and sourceUrl")
                if version.get("releaseDate") and str(version["releaseDate"])[:10] != str(evidence.get("publishedAt", ""))[:10]:
                    errors.append(f"{family['id']}/{version_id}: releaseDate conflicts with releaseEvidence.publishedAt")

    digest = read("site/data/model-releases-30d.json")
    for item in digest.get("items", []):
        fid, vid = item.get("modelFamilyId"), item.get("modelVersionId")
        if fid not in family_map:
            errors.append(f"release {item.get('id')}: unresolved modelFamilyId {fid}")
        elif (fid, vid) not in versions:
            errors.append(f"release {item.get('id')}: modelVersionId {vid} does not belong to {fid}")
        if not item.get("url") or not item.get("verifiedAt"):
            errors.append(f"release {item.get('id')}: missing source URL or verification date")
        version = version_map.get((fid, vid))
        evidence = version.get("releaseEvidence", {}) if version else {}
        if evidence and (item.get("id") != evidence.get("eventId")
                         or str(item.get("publishedAt", ""))[:10] != str(evidence.get("publishedAt", ""))[:10]
                         or item.get("url") != evidence.get("sourceUrl")
                         or item.get("modelName") != evidence.get("modelName", version.get("name"))):
            errors.append(f"release {item.get('id')}: digest fields do not match canonical version evidence")

    for item in digest.get("verifiedStages", []):
        version = version_map.get((item.get("modelFamilyId"), item.get("modelVersionId")))
        stages = version.get("historicalMilestones", []) if version else []
        if not any(item.get("id") == "stage-" + str(s.get("chronicleAuditId")) and item.get("stageDate") == s.get("date") and item.get("stage") == s.get("stage") and item.get("url") == s.get("sourceUrl") and item.get("verifiedAt") == s.get("verifiedAt") for s in stages):
            errors.append(f"verified stage {item.get('id')}: no matching canonical historical milestone")
    practice = read("site/data/model-practice.json")
    for item in practice.get("models", []):
        fid, vid = item.get("modelFamilyId"), item.get("modelVersionId")
        if fid and fid not in family_map:
            errors.append(f"practice {item.get('id')}: unresolved modelFamilyId {fid}")
        if vid and (fid, vid) not in versions:
            errors.append(f"practice {item.get('id')}: modelVersionId {vid} does not belong to {fid}")

    for relative, section in [
        ("site/data/model-evaluations.json", "items"),
        ("site/data/aihot-daily.json", "items"),
        ("site/data/juya-daily.json", "items"),
        ("site/data/aihot-items.json", "items"),
        ("site/data/feed-items.json", "items"),
        ("site/data/topics.json", "milestones"),
        ("site/data/social-accounts.json", "posts"),
        ("site/data/social-platforms.json", None),
    ]:
        path = ROOT / relative
        if not path.exists():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        if section is None:
            records = document if isinstance(document, list) else []
        elif isinstance(document, list):
            records = [record for parent in document for record in parent.get(section, [])]
        else:
            records = document.get(section, [])
        for record in records:
            for ref in record.get("modelMentions", []):
                fid, vid = ref.get("modelFamilyId"), ref.get("modelVersionId")
                if fid not in family_map or (fid, vid) not in versions:
                    errors.append(f"{relative}: unresolved model mention {fid}/{vid}")
            for ref in record.get("modelFamilyMentions", []):
                fid = ref.get("modelFamilyId")
                if fid not in family_map:
                    errors.append(f"{relative}: unresolved model family mention {fid}")

    if errors:
        print("Model link validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Model links valid: {len(family_map)} families, {len(versions)} versions, {len(digest.get('items', []))} release rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
