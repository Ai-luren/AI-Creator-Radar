import unittest
from scripts.link_model_records import chronicle_title_refs
from scripts.audit_model_completeness import audit


class ChronicleEvidenceTests(unittest.TestCase):
    def test_unrelated_vendor_and_summary_only_refs_are_rejected(self):
        families = [{"id": "veo", "vendor": "Google"}, {"id": "other", "vendor": "Other"}]
        refs = [{"modelFamilyId": "veo", "matchedName": "Veo 2"},
                {"modelFamilyId": "veo", "matchedName": "Veo 3"},
                {"modelFamilyId": "other", "matchedName": "Veo 3"}]
        self.assertEqual(chronicle_title_refs("Google 发布 Veo 3，支持声音", refs, families, ["Google"]), [refs[1]])

    def test_variant_prefix_is_not_a_base_release(self):
        families = [{"id": "gpt", "vendor": "OpenAI"}]
        refs = [{"modelFamilyId": "gpt", "matchedName": "GPT-5"}]
        self.assertEqual(chronicle_title_refs("GPT-5-Codex 发布", refs, families, ["OpenAI"]), [])

    def test_bare_version_is_not_an_identity(self):
        families = [{"id": "music", "vendor": "ElevenLabs"}]
        self.assertEqual(chronicle_title_refs("Eleven Flash v2.5", [{"modelFamilyId": "music", "matchedName": "v2.5"}], families, ["ElevenLabs"]), [])

    def test_missing_evidence_report_does_not_invent_dates(self):
        f = [{"id": "demo", "category": "video", "versions": [{"id": "v1", "name": "Demo 1"}]}]
        report = audit(f, [], {"links": [], "vendorTopics": {}})
        self.assertEqual(report["missingEvidence"], 1)
        self.assertFalse(report["gaps"][0]["hasDate"])


class HistoricalMilestoneTests(unittest.TestCase):
    def test_availability_is_not_release_evidence(self):
        family = {"id": "music", "vendor": "Vendor", "category": "music", "versions": [{"id": "v2", "name": "Music v2", "historicalMilestones": [{"date": "2026-06-15", "datePrecision": "day", "stage": "api-availability", "sourceUrl": "https://example.com/log", "verifiedAt": "2026-11-26", "chronicleAuditId": "audit"}]}]}
        topic = {"id": "vendor", "milestones": [{"auditId": "audit", "date": "2026-06-15", "url": "https://example.com/log", "verificationDate": "2026-11-26", "verificationStatus": "已确认：型号、日期与事件性质"}]}
        report = audit([family], [topic], {"links": [], "vendorTopics": {"vendor": ["Vendor"]}})
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["historicalMilestones"], 1)
        self.assertEqual(report["missingEvidence"], 1)
