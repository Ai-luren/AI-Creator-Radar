import unittest
from datetime import datetime,timezone
from scripts.collect_cross_platform import tracker_model_leads, tracker_leads
from scripts.collect_model_intake import stage
from scripts.audit_radar_system import inspect

class IntakeAuditTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,26,17,tzinfo=timezone.utc)
        self.source={"id":"tracker","name":"tracker","url":"https://isitsota.com/releases"}
        self.hosts={"official.example":["/blog/"]}
    def test_tracker_only_imports_allowlisted_lab_links_and_not_release_assertions(self):
        data={"slug":"demo-3","name":"Demo 3","releaseDate":"2026-11-25","tracked":{"announced":"2026-11-24","sources":[
            {"kind":"lab","url":"https://official.example/blog/demo-3","title":"Introducing Demo 3 (Official blog)"},
            {"kind":"lab","url":"https://official.example.evil.test/blog/x"},{"kind":"press","url":"https://official.example/blog/x"}]}}
        row=tracker_model_leads(data,self.source,self.hosts)[0]
        self.assertEqual(row["officialArticleUrls"],["https://official.example/blog/demo-3"])
        self.assertEqual(row["reportedAt"][:10],"2026-11-24")
        self.assertNotIn("publishedAt",row)
        self.assertEqual(row["attribution"]["license"],"CC BY 4.0")
    def test_new_family_is_staged_not_created(self):
        families=[{"id":"demo","versions":[{"name":"Demo 3"}]}]
        row={"id":"p","status":"family-unresolved","title":"Introducing NewModel 2","articlePublishedAt":"2026-11-23T00:00:00Z","url":"https://official.example/blog/new"}
        result=stage(families,{"items":[row]}, {},self.now)
        self.assertEqual(result["items"][0]["status"],"needs-family-classification")
        self.assertIsNone(result["items"][0]["modelFamilyId"])
        self.assertEqual(len(families),1)
        self.assertNotIn("releaseDate",result["items"][0])
    def test_existing_model_and_unverified_article_are_not_new(self):
        family={"id":"demo","versions":[{"name":"Demo 3"}]}
        row={"id":"x","status":"article-date-verified","modelId":"demo","title":"Introducing Demo 3","articlePublishedAt":"2026-11-23","url":"https://official.example/blog/demo"}
        self.assertEqual(stage([family],{"items":[row]}, {},self.now)["items"],[])
        self.assertEqual(stage([family],{"items":[dict(row,title="Introducing Demo 4",status="date-unresolved")]}, {},self.now)["items"],[])
    def test_adversarial_audit_separates_coverage_from_structural_errors(self):
        families=[{"id":"demo","vendor":"Vendor","category":"llm","versions":[{"id":"v1","name":"Demo 1"}]}]
        data={"models":families,"topics":[],"digest":{"items":[]},"recall":{"negativeControls":[{"incorrectConfirmedIds":["bad"]}]}}
        result=inspect(data,{"links":[],"vendorTopics":{}},self.now)
        self.assertIn("Negative-control article incorrectly confirmed",result["errors"])
        self.assertEqual(result["counts"]["missingEvidence"],1)
