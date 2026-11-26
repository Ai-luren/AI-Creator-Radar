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


class ExplicitChronicleReferenceTests(unittest.TestCase):
    def test_shared_audited_event_keeps_two_distinct_versions(self):
        from scripts.link_model_records import explicit_chronicle_refs
        family = {"id": "s2", "versions": [
            {"id": "avatar", "name": "S2-Avatar", "releaseEvidence": {"chronicleAuditId": "event"}},
            {"id": "editing", "name": "S2-Editing", "historicalMilestones": [{"chronicleAuditId": "event"}]},
        ]}
        refs = explicit_chronicle_refs([family])
        self.assertEqual(set(refs["event"]), {("s2", "avatar"), ("s2", "editing")})


class EvidenceQueueTests(unittest.TestCase):
    def test_gap_classification_preserves_unknowns(self):
        from scripts.audit_model_completeness import gap_kind
        family = {"category": "video"}
        self.assertEqual(gap_kind(family, {"releaseDate": "2026-01-01"}), "dated-without-evidence")
        self.assertEqual(gap_kind(family, {"historicalMilestones": [{"stage": "preview"}]}), "historical-stage-only")
        self.assertEqual(gap_kind(family, {"status": "榜单型号待核验"}), "leaderboard-identity-review")
        self.assertEqual(gap_kind(family, {"derivedFrom": "base"}), "provider-variant-review")
        self.assertEqual(gap_kind(family, {"name": "Demo Preview"}), "preview-stage-review")
        self.assertEqual(gap_kind({"category": "agent"}, {}), "agent-product-scope")
        self.assertEqual(gap_kind(family, {"status": "已发布"}), "release-source-review")

    def test_queue_is_exhaustive_and_does_not_promote_sources(self):
        families = [{"id": "demo", "vendor": "Vendor", "category": "video", "versions": [
            {"id": "v1", "name": "Demo 1", "releaseUrl": "https://example.com/catalog"},
            {"id": "v2", "name": "Demo 2", "releaseEvidence": {"eventId": "known"}},
        ]}]
        result = audit(families, [], {"links": [], "vendorTopics": {}})
        self.assertEqual(result["missingEvidence"], 1)
        self.assertEqual(sum(result["gapKinds"].values()), 1)
        self.assertEqual(result["vendors"]["Vendor"]["evidence"], 1)
        self.assertEqual(result["gaps"][0]["candidateSourceUrl"], "https://example.com/catalog")
        self.assertNotIn("releaseEvidence", families[0]["versions"][0])


class AudioStageTests(unittest.TestCase):
    def test_research_availability_and_updates_do_not_become_release_evidence(self):
        for stage in ("development-milestone", "documented-availability", "model-update"):
            milestone = {"date": "2024-11", "datePrecision": "month", "stage": stage,
                         "sourceUrl": "https://example.com/history", "verifiedAt": "2026-11-26",
                         "chronicleAuditId": "a"}
            families = [{"id": "demo", "vendor": "Vendor", "category": "music",
                         "versions": [{"id": "v1", "name": "Demo 1", "historicalMilestones": [milestone]}]}]
            topics = [{"id": "vendor", "milestones": [{"auditId": "a", "date": "2024-11",
                       "url": "https://example.com/history", "verificationDate": "2026-11-26",
                       "verificationStatus": "已确认：型号、日期与事件性质"}]}]
            result = audit(families, topics, {"links": [], "vendorTopics": {"vendor": ["Vendor"]}})
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["missingEvidence"], 1)
            self.assertEqual(result["gaps"][0]["reviewKind"], "historical-stage-only")
