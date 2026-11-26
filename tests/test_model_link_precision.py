"""Regression guards for auto-generated model mentions, distinct from evidence."""
import json
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
