import unittest
from scripts.audit_discovery_coverage import inspect_leads


class DiscoveryCoverageTests(unittest.TestCase):
    def test_tracks_external_leads_without_official_urls_and_pending_probes(self):
        discovery = {"items": [
            {"id": "a", "sourceId": "rss", "title": "Model 3", "officialArticleUrls": []},
            {"id": "b", "sourceId": "rss", "title": "Model 4", "officialArticleUrls": ["https://example.org/b"]},
            {"id": "c", "sourceId": "local-official-candidates", "officialArticleUrls": []}]}
        result = inspect_leads(discovery, {})
        self.assertEqual(result["leadCount"], 2)
        self.assertEqual(result["counts"], {"awaiting-probe": 1, "no-allowlisted-original": 1})
        self.assertEqual({r["leadId"] for r in result["openLeads"]}, {"a", "b"})

    def test_mixed_evidence_does_not_hide_unresolved_article(self):
        discovery = {"items": [{"id": "a", "sourceId": "index",
                                "officialArticleUrls": ["https://example.org/a", "https://example.org/b"]}]}
        resolution = {"items": [{"leadIds": ["a"], "status": "article-date-verified"},
                                {"leadIds": ["a"], "status": "fetch-failed", "nextAttemptAt": "2026-11-28"}]}
        result = inspect_leads(discovery, resolution)
        self.assertEqual(result["openLeads"][0]["state"], "unresolved")
        self.assertEqual(result["openLeads"][0]["nextAttemptAt"], "2026-11-28")

    def test_article_observation_and_negative_review_are_not_release_claims(self):
        discovery = {"items": [{"id": "a", "officialArticleUrls": ["https://example.org/a"]},
                                {"id": "b", "officialArticleUrls": ["https://example.org/b"]}]}
        resolution = {"items": [{"leadIds": ["a"], "status": "article-date-verified"},
                                {"leadIds": ["b"], "status": "not-model-announcement"}]}
        result = inspect_leads(discovery, resolution)
        self.assertEqual(result["counts"], {"article-date-observed": 1, "excluded-by-article-review": 1})
        self.assertEqual(result["openLeads"], [])
        self.assertNotIn("confirmedReleases", result)
