import unittest
from datetime import datetime, timezone, timedelta
from copy import deepcopy
from scripts.event_identity import associate_leads, identify, model_index
from scripts.collect_event_reconciliation import reconcile


class EventReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 27, tzinfo=timezone.utc)
        self.families = [{"id": "demo", "versions": [
            {"id": "v3", "name": "Demo v3", "releaseEvidence": {
                "publishedAt": "2026-11-22", "verifiedAt": "2026-11-23",
                "sourceUrl": "https://official.example/release", "eventId": "batch-v3"}},
            {"id": "v3-live", "name": "Demo v3 Live"}]}]
        self.a = {"id": "a", "sourceId": "index", "title": "Demo v3",
                  "reportedAt": "2026-11-22", "dateKind": "external-dataset-event-date",
                  "officialArticleUrls": ["https://official.example/release"]}
        self.b = {"id": "b", "sourceId": "feed", "title": "Demo v3 announced",
                  "reportedAt": "2026-11-22", "dateKind": "external-feed-date", "officialArticleUrls": []}

    def test_precise_identity_and_variant_boundary(self):
        index = model_index(self.families)
        self.assertEqual(identify(index, "Demo v3 Live"), ("demo", "v3-live"))
        self.assertIsNone(identify(index, "Demo v3 Live Medical"))
        self.assertIsNone(identify(index, "Demo v3.1"))
        self.assertIsNone(identify(index, "Demo v3", ["Demo v3 Live"]))

    def test_same_model_day_association_does_not_copy_provenance(self):
        rows = associate_leads(deepcopy([self.a, self.b]), self.families)
        self.assertEqual(rows[1]["officialArticleUrls"], [])
        self.assertEqual(rows[1]["relatedArticleCandidates"], [
            {"url": "https://official.example/release", "supportingLeadIds": ["a"]}])
        other = dict(self.b, id="c", reportedAt="2026-11-23")
        upload = dict(self.b, id="d", dateKind="repository-created-at")
        rows = associate_leads(deepcopy([self.a, other, upload]), self.families)
        self.assertNotIn("relatedArticleCandidates", rows[1])
        self.assertNotIn("relatedArticleCandidates", rows[2])

    def test_whole_domain_failure_retains_evidence_without_refreshing_verification(self):
        verified = {"id": "proof", "url": "https://official.example/release",
                    "modelId": "demo", "title": "Demo v3",
                    "articlePublishedAt": "2026-11-22T00:00:00Z",
                    "firstVerifiedAt": "2026-11-23T00:00:00Z", "status": "article-date-verified"}
        first = reconcile(self.families, {"items": [self.a, self.b]}, {"items": [verified]}, [], {}, self.now)
        self.assertEqual(first["summary"]["evidenceCount"], 2)
        self.assertEqual(first["summary"]["taskStates"], {"article-date-observed": 1})
        blocked = dict(verified, status="fetch-failed", nextAttemptAt="2026-11-28T00:00:00Z",
                       lastVerifiedObservation=verified)
        later = reconcile(self.families, {"items": [self.a, self.b]}, {"items": [blocked]}, [], first, self.now+timedelta(days=1))
        self.assertEqual(later["evidence"], first["evidence"])
        self.assertEqual(later["summary"]["newEvidence"], 0)
        self.assertEqual(later["tasks"][0]["firstDetectedAt"], first["tasks"][0]["firstDetectedAt"])
        self.assertEqual(later["tasks"][0]["state"], "probe-unresolved")

    def test_catalog_correction_keeps_old_fact_and_reports_history(self):
        first = reconcile(self.families, {}, {}, [], {}, self.now)
        revised = deepcopy(self.families)
        revised[0]["versions"][0]["releaseEvidence"]["publishedAt"] = "2026-11-21"
        second = reconcile(revised, {}, {}, [], first, self.now+timedelta(days=1))
        self.assertEqual(len(second["evidence"]), 2)
        self.assertEqual(second["historicalReleaseDateDifferences"][0]["historicalDates"], ["2026-11-21", "2026-11-22"])
        self.assertEqual(len(second["currentEvidenceIds"]), 1)

    def test_unresolved_task_survives_discovery_expiration(self):
        first = reconcile(self.families, {"items": [self.b]}, {}, [], {}, self.now)
        self.assertEqual(first["tasks"][0]["state"], "needs-source")
        second = reconcile(self.families, {}, {}, [], first, self.now+timedelta(days=46))
        self.assertEqual(second["tasks"][0]["id"], first["tasks"][0]["id"])
        self.assertEqual(second["tasks"][0]["state"], "no-longer-in-current-input")

    def test_historical_stage_is_not_release_and_gap_closes_only_on_catalog_evidence(self):
        families = deepcopy(self.families)
        v = families[0]["versions"][1]
        v["historicalMilestones"] = [{"stage": "api-availability", "date": "2026-11-22",
            "datePrecision": "day", "sourceUrl": "https://official.example/api", "verifiedAt": "2026-11-23"}]
        gap = {"reviewKind": "release-source-review", "modelFamilyId": "demo", "modelVersionId": "v3-live"}
        result = reconcile(families, {}, {}, [gap], {}, self.now)
        self.assertIn("historical-api-availability", [e["claimType"] for e in result["evidence"]])
        self.assertEqual(result["tasks"][0]["state"], "needs-release-evidence")
        later = reconcile(families, {}, {}, [], result, self.now+timedelta(days=1))
        self.assertEqual(later["tasks"][0]["state"], "no-longer-in-current-input")

    def test_corrupt_ledger_rejected_not_overwritten(self):
        first = reconcile(self.families, {}, {}, [], {}, self.now)
        first["evidence"][0]["assertedDate"] = "2020-01-01"
        with self.assertRaises(ValueError):
            reconcile(self.families, {}, {}, [], first, self.now)
