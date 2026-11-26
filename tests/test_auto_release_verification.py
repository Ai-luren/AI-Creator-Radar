import copy
import unittest
from datetime import date

from scripts.collect_verify_model_releases import reconcile, release_name
from scripts.collect_models import rss_items, html_page_items


class AutoReleaseVerificationTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 27)
        self.stamp = "2026-11-27T00:00:00Z"
        self.models = [{"id": "seedance", "name": "Seedance", "vendor": "Vendor",
                        "category": "video", "versions": [{"id": "seedance-2", "name": "Seedance 2"}]}]
        self.sources = [{"id": sid, "name": sid, "vendor": "Vendor", "active": True, "official": True,
                         "url": f"https://{sid}.example/news", "modelMatches": {"seedance": ["seedance"]}}
                        for sid in ("a", "b")]
        self.status = {"sources": [{"id": sid, "checkedAt": self.stamp, "error": None} for sid in ("a", "b")]}
        self.updates = [{"id": sid, "sourceId": sid, "official": True, "updateType": "release",
                         "modelId": "seedance", "title": "Seedance 3 officially released",
                         "url": f"https://{sid}.example/news/model-3", "publishedAt": "2026-11-26T00:00:00Z",
                         "publicationDateKind": "feed-published", "publicationObservedAt": self.stamp}
                        for sid in ("a", "b")]

    def run_gate(self):
        return reconcile(self.models, self.updates, self.sources, self.status, {"vendor": ["Vendor"]}, self.today)

    def test_dual_source_new_model_and_idempotence(self):
        result = self.run_gate()
        self.assertEqual(len(result["confirmed"]), 1)
        version = self.models[0]["versions"][-1]
        self.assertEqual(version["name"], "Seedance 3")
        self.assertEqual(version["releaseDate"], "2026-11-26")
        self.assertEqual(len(version["releaseEvidence"]["corroboratingSources"]), 2)
        self.assertNotIn("license", version)
        snapshot = copy.deepcopy(self.models)
        self.assertEqual(self.run_gate()["confirmed"], [])
        self.assertEqual(self.models, snapshot)

    def test_conflicts_untrusted_stale_and_stage_cannot_promote(self):
        for field, bad in [("publishedAt", "2026-11-25T00:00:00Z"),
                           ("publicationDateKind", "modified"), ("publicationObservedAt", "old"),
                           ("url", "https://evil.example/news/model-3"),
                           ("summary", "Limited access preview"), ("official", False),
                           ("updateType", "api")]:
            old = self.updates[1].get(field)
            self.updates[1][field] = bad
            self.assertEqual(self.run_gate()["confirmed"], [], field)
            self.updates[1][field] = old
        self.assertEqual(len(self.models[0]["versions"]), 1)

    def test_same_host_is_not_two_independent_official_sites(self):
        self.sources[1]["url"] = "https://a.example/other"
        self.updates[1]["url"] = "https://a.example/other/model-3"
        self.assertEqual(self.run_gate()["confirmed"], [])

    def test_existing_evidence_and_stage_are_protected(self):
        version = self.models[0]["versions"][0]
        version["name"] = "Seedance 3"
        version["historicalMilestones"] = [{"stage": "preview"}]
        self.assertEqual(self.run_gate()["confirmed"], [])
        self.assertNotIn("releaseEvidence", version)

    def test_title_does_not_treat_introduction_api_or_preview_as_release(self):
        for title in ("Introducing Seedance 3", "Seedance 3 API released", "Seedance 3 Preview released"):
            self.assertIsNone(release_name(title))

    def test_atom_updated_is_not_publication_evidence(self):
        source = self.sources[0]
        feed = b'<feed><entry><title>Seedance 3 officially released</title><link href="https://a.example/news/model-3"/><updated>2026-11-26T00:00:00Z</updated></entry></feed>'
        self.assertNotIn("publicationDateKind", rss_items(feed, source)[0])

    def test_glm_dated_button_is_candidate_only(self):
        source = {"type": "dated-headings", "dateButtons": True, "url": "https://docs.z.ai/release-notes/new-released",
                  "modelMatches": {"glm": ["glm-5"]}}
        items = html_page_items("<h2>Models</h2><button>2026-08-26</button><h3>GLM-5.3-Flash</h3>", source)
        self.assertEqual(items[0]["publishedAt"][:10], "2026-08-26")
        self.assertNotIn("publicationDateKind", items[0])
