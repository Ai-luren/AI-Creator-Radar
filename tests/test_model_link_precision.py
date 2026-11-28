"""Regression guards for auto-generated model mentions, distinct from evidence."""
import json
import re
import unittest
from pathlib import Path

from scripts.link_model_records import (
    RECORD_SECTIONS, is_unqualified_version_label, phrases, record_refs,
    explicit_chronicle_refs,
)

ROOT = Path(__file__).resolve().parents[1]


class ModelLinkPrecisionTests(unittest.TestCase):
    def test_bare_versions_and_generic_modality_labels_are_not_identities(self):
        for label in ("V4.1", "2.5 Flash", "Video 1", "version 3.2", "Audio-2"):
            self.assertTrue(is_unqualified_version_label(label), label)
        for label in ("GLM-5.4", "Recraft V4.1", "Seedance 2.5", "HeyGen Video 1"):
            self.assertFalse(is_unqualified_version_label(label), label)

    def test_named_evidence_is_retained_but_generic_name_is_not_used(self):
        self.assertEqual(phrases({"id": "glm"}, {"name": "5.4"}), ["GLM-5.4"])
        self.assertEqual(phrases({"id": "recraft"}, {"name": "V4.1",
                         "releaseEvidence": {"modelName": "Recraft V4.1"}}), ["Recraft V4.1"])

    def test_actual_catalog_no_cross_vendor_or_input_number_false_positive(self):
        families = json.loads((ROOT / "site/data/models.json").read_text())
        for text, forbidden in (
            ("DeepSeek-V4.1-Flash Release", "recraft"),
            ("Gemini 2.5 Flash-Lite", "agnes-image-25-flash"),
            ("Gemini 2.5 Flash-Lite", "agnes-video-25"),
            ("Grok Imagine Video 1.5", "heygen-video"),
            ("Kling 4.0 as video 1", "heygen-video"),
        ):
            self.assertNotIn(forbidden, {ref["modelFamilyId"] for ref in record_refs(text, families)}, text)
        self.assertIn("kling", {ref["modelFamilyId"] for ref in record_refs("Kling 4.0 as video 1", families)})
        self.assertIn("seedance", {ref["modelFamilyId"] for ref in record_refs("Seedance 2.5", families)})

    def test_committed_automatic_mentions_have_no_unqualified_names(self):
        for relative, (section, _) in RECORD_SECTIONS.items():
            if section == "milestones":
                continue
            document = json.loads((ROOT / relative).read_text())
            rows = document if section is None else document.get(section, [])
            for row in rows:
                for ref in row.get("modelMentions", []):
                    self.assertFalse(is_unqualified_version_label(ref.get("matchedName")), (relative, ref))

    def test_audited_short_names_are_not_deleted_from_explicit_history(self):
        families = [{"id": "demo", "versions": [{"id": "v2", "name": "v2.5",
                     "releaseEvidence": {"chronicleAuditId": "reviewed"}}]}]
        self.assertEqual(explicit_chronicle_refs(families)["reviewed"][("demo", "v2")]["matchedName"], "v2.5")

def legacy_record_refs(text: str, families: list[dict]) -> list[dict]:
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


def legacy_family_refs(text: str, families: list[dict]) -> list[dict]:
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



class CompiledMentionIndexTests(unittest.TestCase):
    def test_equivalence_to_original_matcher(self):
        from scripts.link_model_records import ModelMentionIndex
        families = json.loads((ROOT / "site/data/models.json").read_text())
        index = ModelMentionIndex(families)
        def old(text):
            return legacy_record_refs(text, families), legacy_family_refs(text, families)
        samples = ["Gemini 2.5 Flash-Lite / Seedance 2.5", "DeepSeek-V4.1-Flash Release",
                   "GLM-5.4 和 GLM-5.3-Flash", "Kling 4.0 as video 1", "no model here", "İmage 2.0"]
        for relative, (section, fields) in RECORD_SECTIONS.items():
            document = json.loads((ROOT / relative).read_text())
            rows = document if section is None else ([r for p in document for r in p.get(section, [])] if isinstance(document,list) else document.get(section,[]))
            samples.extend(" ".join(str(row.get(field,"")) for field in fields) for row in rows[::max(1,len(rows)//3)][:4])
        for text in samples:
            with self.subTest(text=text[:100]):
                versions, family_mentions = old(text)
                self.assertEqual(index.record_refs(text), versions)
                self.assertEqual(index.family_refs(text), family_mentions)

    def test_apply_records_reuses_index_and_is_idempotent(self):
        from scripts.link_model_records import ModelMentionIndex, apply_records
        from unittest.mock import patch
        families = [{"id":"demo","name":"Demo","versions":[{"id":"v2","name":"Demo 2.0"}]}]
        index = ModelMentionIndex(families)
        document = {"items":[{"title":"Demo 2.0"},{"title":"Other"}]}
        with patch("scripts.link_model_records.ModelMentionIndex", side_effect=AssertionError("recompiled")):
            self.assertTrue(apply_records(document,"items",("title",),families,index))
            self.assertFalse(apply_records(document,"items",("title",),families,index))
        self.assertEqual(document["items"][0]["modelMentions"][0]["modelVersionId"], "v2")
