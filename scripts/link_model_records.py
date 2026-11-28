#!/usr/bin/env python3
"""Attach exact-name model references to records across the creator radar."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "site/data/models.json"
CHRONICLE_CONFIG = ROOT / "config/chronicle-release-links.json"

RECORD_SECTIONS = {
    "site/data/model-updates.json": ("items", ("title", "summary")),
    "site/data/aihot-daily.json": ("items", ("title", "summary")),
    "site/data/juya-daily.json": ("items", ("title", "summary")),
    "site/data/aihot-items.json": ("items", ("title", "summary", "reason")),
    "site/data/feed-items.json": ("items", ("title", "summary")),
    "site/data/topics.json": ("milestones", ("title", "summary")),
    "site/data/social-accounts.json": ("posts", ("title", "note")),
    "site/data/social-platforms.json": (None, ("name", "type", "note")),
}


def is_unqualified_version_label(value: str) -> bool:
    """A number or generic modality/version label is not a model identity."""
    return bool(re.match(r"^(?:(?:v(?:ersion)?|image|video|audio|music|speech|model)\s*[-_]?\s*)?\d+(?:[.-]\d+)*(?=$|[\s-])", str(value or "").strip(), re.I))


def phrases(family: dict, version: dict) -> list[str]:
    values = [version.get("name", "")]
    # A few catalogs store version numbers without the family prefix.
    if family.get("id") == "glm" and version.get("name"):
        values.append("GLM-" + version["name"])
    evidence = version.get("releaseEvidence") or {}
    if evidence.get("modelName"):
        values.append(evidence["modelName"])
    return list(dict.fromkeys(value.strip() for value in values
                              if len(value.strip()) >= 4 and re.search(r"\d", value)
                              and not is_unqualified_version_label(value)))


class ModelMentionIndex:
    """Compile catalog patterns once; preserve original exact matching and order."""
    def __init__(self, families):
        self.versions = []
        self.families = []
        for family in families:
            if family.get("category") == "agent":
                continue
            fid = family["id"]
            versions = family.get("versions", [])
            for version in versions:
                for phrase in phrases(family, version):
                    suffixes = tuple(
                        str(sibling["name"])[len(phrase):].casefold()
                        for sibling in versions
                        if sibling.get("id") != version.get("id")
                        and str(sibling.get("name", "")).casefold().startswith(phrase.casefold())
                        and len(str(sibling.get("name", ""))) > len(phrase)
                    )
                    pattern = re.compile(r"(?<![\w])" + re.escape(phrase) + r"(?![\w])", re.I)
                    self.versions.append((fid, version["id"], phrase, pattern, suffixes))
            for name in [family.get("name", "")] + (family.get("aliases") or []):
                name = str(name).strip()
                if len(name) < 4 or name.endswith("系列"):
                    continue
                pattern = re.compile(r"(?<![\w])" + re.escape(name) + r"(?![\w])", re.I)
                self.families.append((fid, name, pattern))

    def record_refs(self, text):
        found = {}
        for fid, vid, phrase, pattern, suffixes in self.versions:
            match = pattern.search(text)
            if not match:
                continue
            if suffixes:
                tail = text[match.end():]
                if tail.casefold().startswith(suffixes) or re.match(r"^(?:[.-]\s*\d|\s+\d)", tail):
                    continue
            found[(fid, vid)] = {"modelFamilyId":fid, "modelVersionId":vid, "matchedName":phrase}
        return [found[key] for key in sorted(found)]

    def family_refs(self, text):
        found = {}
        for fid, name, pattern in self.families:
            if pattern.search(text):
                found[fid] = {"modelFamilyId":fid, "matchedName":name}
        return [found[key] for key in sorted(found)]


def record_refs(text: str, families: list[dict]) -> list[dict]:
    return ModelMentionIndex(families).record_refs(text)


def family_refs(text: str, families: list[dict]) -> list[dict]:
    return ModelMentionIndex(families).family_refs(text)


def chronicle_title_refs(title: str, refs: list[dict], families: list[dict], vendors: list[str]) -> list[dict]:
    """A chronology event is not evidence for models merely mentioned in its summary."""
    by_id = {family["id"]: family for family in families}
    accepted = []
    for ref in refs:
        family = by_id.get(ref.get("modelFamilyId"), {})
        phrase = str(ref.get("matchedName") or "").strip()
        if family.get("vendor") not in vendors or not phrase:
            continue
        if re.fullmatch(r"v?\d+(?:[.\-]\d+)*(?:\s+(?:flash|pro|lite|turbo|fast))?", phrase, re.I):
            continue
        pattern = re.escape(phrase)
        if not re.search(r"(?<![A-Za-z0-9])" + pattern + r"(?![A-Za-z0-9])", title, re.I):
            continue
        if re.search(pattern + r"(?:[.-]\d|[- ](?:Flash|Pro|Lite|Turbo|Fast|Codex|Max|Mini|Nano|Omni|Image|Video|TTS|Cyber|Preview)\b)", title, re.I):
            continue
        accepted.append(ref)
    return accepted


def explicit_chronicle_refs(families: list[dict]) -> dict:
    """Use already audited evidence/milestone IDs, not bare title or summary matches."""
    result = {}
    for family in families:
        for version in family.get("versions", []):
            records = [version.get("releaseEvidence") or {}, *version.get("historicalMilestones", [])]
            for evidence in records:
                aid = evidence.get("chronicleAuditId")
                if aid:
                    result.setdefault(aid, {})[(family["id"], version["id"])] = {
                        "modelFamilyId": family["id"], "modelVersionId": version["id"],
                        "matchedName": version["name"],
                    }
    return result


def apply_records(document, section: str | None, fields: tuple[str, ...], families: list[dict], index=None) -> bool:
    index = index if index is not None else ModelMentionIndex(families)
    if section is None and isinstance(document, list):
        records = document
    elif isinstance(document, list):
        records = [record for parent in document for record in parent.get(section, [])]
    else:
        records = document.get(section, [])
    changed = False
    chronology_vendors = {}
    explicit_refs = explicit_chronicle_refs(families) if section == "milestones" else {}
    by_family = {f["id"]: f for f in families}
    if section == "milestones" and isinstance(document, list):
        vendor_topics = json.loads(CHRONICLE_CONFIG.read_text(encoding="utf-8"))["vendorTopics"]
        chronology_vendors = {id(record): vendor_topics[parent["id"]] for parent in document if parent.get("id") in vendor_topics for record in parent.get("milestones", [])}
    for record in records:
        text = " ".join(str(record.get(field, "")) for field in fields)
        refs = index.record_refs(text)
        family_mentions = index.family_refs(text)
        if id(record) in chronology_vendors:
            vendors = chronology_vendors[id(record)]
            refs = chronicle_title_refs(str(record.get("title") or ""), refs, families, vendors)
            merged = {(r["modelFamilyId"], r["modelVersionId"]): r for r in refs}
            if not record.get("autoCollected") and record.get("verificationStatus") == "已确认：型号、日期与事件性质":
                for key, ref in explicit_refs.get(record.get("auditId"), {}).items():
                    if by_family[key[0]].get("vendor") in vendors:
                        merged[key] = ref
            refs = [merged[key] for key in sorted(merged)]
        if refs:
            if record.get("modelMentions") != refs:
                record["modelMentions"] = refs
                changed = True
        elif "modelMentions" in record:
            del record["modelMentions"]
            changed = True
        if family_mentions:
            if record.get("modelFamilyMentions") != family_mentions:
                record["modelFamilyMentions"] = family_mentions
                changed = True
        elif "modelFamilyMentions" in record:
            del record["modelFamilyMentions"]
            changed = True
    return changed


def main() -> int:
    families = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    index = ModelMentionIndex(families)
    updated = []
    for relative, (section, fields) in RECORD_SECTIONS.items():
        path = ROOT / relative
        if not path.exists():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        if apply_records(document, section, fields, families, index):
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            updated.append(relative)
    try:
        from scripts.ranking_identity import update_rankings
    except ModuleNotFoundError:
        from ranking_identity import update_rankings
    print("Primary ranking identity coverage:", update_rankings(families))
    print("Updated model references in " + (", ".join(updated) if updated else "no records"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
