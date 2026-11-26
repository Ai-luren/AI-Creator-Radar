#!/usr/bin/env python3
"""Attach exact-name model references to records across the creator radar."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "site/data/models.json"

RECORD_SECTIONS = {
    "site/data/model-evaluations.json": ("items", ("modelName", "title", "summary")),
    "site/data/aihot-daily.json": ("items", ("title", "summary")),
    "site/data/juya-daily.json": ("items", ("title", "summary")),
    "site/data/aihot-items.json": ("items", ("title", "summary", "reason")),
    "site/data/feed-items.json": ("items", ("title", "summary")),
    "site/data/topics.json": ("milestones", ("title", "summary")),
    "site/data/social-accounts.json": ("posts", ("title", "note")),
    "site/data/social-platforms.json": (None, ("name", "type", "note")),
}


def phrases(family: dict, version: dict) -> list[str]:
    values = [version.get("name", "")]
    # A few catalogs store version numbers without the family prefix.
    if family.get("id") == "glm" and version.get("name"):
        values.append("GLM-" + version["name"])
    evidence = version.get("releaseEvidence") or {}
    if evidence.get("modelName"):
        values.append(evidence["modelName"])
    return list(dict.fromkeys(value.strip() for value in values
                              if len(value.strip()) >= 4 and re.search(r"\d", value)))


def record_refs(text: str, families: list[dict]) -> list[dict]:
    found = {}
    for family in families:
        if family.get("category") == "agent":
            continue
        for version in family.get("versions", []):
            for phrase in phrases(family, version):
                # A shorter version label can match several sibling variants;
                # only attach a version when the exact full display name occurs.
                pattern = re.compile(r"(?<![\w])" + re.escape(phrase) + r"(?![\w])", re.I)
                match = pattern.search(text)
                if match:
                    tail = text[match.end():]
                    is_sibling_prefix = any(
                        sibling.get("id") != version.get("id")
                        and str(sibling.get("name", "")).casefold().startswith(phrase.casefold())
                        and len(str(sibling.get("name", ""))) > len(phrase)
                        and (tail.casefold().startswith(str(sibling["name"])[len(phrase):].casefold())
                             or re.match(r"^(?:[.-]\s*\d|\s+\d)", tail))
                        for sibling in family.get("versions", [])
                    )
                    if is_sibling_prefix:
                        continue
                    key = (family["id"], version["id"])
                    found[key] = {"modelFamilyId": family["id"], "modelVersionId": version["id"], "matchedName": phrase}
    return sorted(found.values(), key=lambda item: (item["modelFamilyId"], item["modelVersionId"]))


def family_refs(text: str, families: list[dict]) -> list[dict]:
    found = {}
    for family in families:
        # Product/tool families are not part of the creator-model catalog links.
        # Exact-name matching can otherwise turn mentions of Codex or Claude Code
        # into misleading model references.
        if family.get("category") == "agent":
            continue
        names = [family.get("name", "")] + (family.get("aliases") or [])
        for name in names:
            name = str(name).strip()
            if len(name) < 4 or name.endswith("系列"):
                continue
            pattern = re.compile(r"(?<![\w])" + re.escape(name) + r"(?![\w])", re.I)
            if pattern.search(text):
                found[family["id"]] = {"modelFamilyId": family["id"], "matchedName": name}
    return sorted(found.values(), key=lambda item: item["modelFamilyId"])


def apply_records(document, section: str | None, fields: tuple[str, ...], families: list[dict]) -> bool:
    if section is None and isinstance(document, list):
        records = document
    elif isinstance(document, list):
        records = [record for parent in document for record in parent.get(section, [])]
    else:
        records = document.get(section, [])
    changed = False
    for record in records:
        text = " ".join(str(record.get(field, "")) for field in fields)
        refs = record_refs(text, families)
        family_mentions = family_refs(text, families)
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
    updated = []
    for relative, (section, fields) in RECORD_SECTIONS.items():
        path = ROOT / relative
        if not path.exists():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        if apply_records(document, section, fields, families):
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            updated.append(relative)
    print("Updated model references in " + (", ".join(updated) if updated else "no records"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
