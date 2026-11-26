import unittest
from unittest.mock import patch

from scripts import collect_models as collector


class SourceReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "id": "demo", "name": "Demo", "url": "https://example.com/rss",
            "type": "rss", "fallbackUrls": ["https://example.com/backup"],
            "modelMatches": {"demo": ["demo"]},
        }

    def test_non_feed_xml_is_rejected(self):
        with self.assertRaises(ValueError):
            collector.rss_items(b"<html><body>Not a feed</body></html>", self.source)

    def test_valid_empty_feed_is_not_an_error(self):
        self.assertEqual(collector.rss_items(b"<rss><channel/></rss>", self.source), [])

    def test_transient_error_retries_once(self):
        with patch.object(collector, "fetch_source_once", side_effect=[
            (self.source, [], "HTTPError: HTTP Error 503: unavailable"),
            (self.source, [{"title": "Demo release"}], None),
        ]) as fetch, patch.object(collector.time, "sleep") as sleep:
            effective, items, error = collector.fetch_source(self.source)
        self.assertIsNone(error)
        self.assertEqual(len(items), 1)
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_called_once_with(2)
        self.assertEqual(len(effective["attempts"]), 2)

    def test_forbidden_uses_fallback_without_repeating_blocked_request(self):
        with patch.object(collector, "fetch_source_once", side_effect=[
            (self.source, [], "HTTPError: HTTP Error 403: Forbidden"),
            (self.source, [], None),
        ]) as fetch, patch.object(collector.time, "sleep") as sleep:
            effective, items, error = collector.fetch_source(self.source)
        self.assertIsNone(error)
        self.assertEqual(items, [])
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(effective["url"], self.source["fallbackUrls"][0])
        self.assertEqual(effective["primaryUrl"], self.source["url"])
        self.assertIn("403", effective["attempts"][0]["error"])
        sleep.assert_not_called()

    def test_failed_fallback_remains_failure(self):
        with patch.object(collector, "fetch_source_once", return_value=(
            self.source, [], "ValueError: invalid feed"
        )) as fetch:
            effective, items, error = collector.fetch_source(self.source)
        self.assertIsNotNone(error)
        self.assertEqual(items, [])
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(len(effective["attempts"]), 2)

    def test_valid_zero_match_does_not_trigger_fallback(self):
        with patch.object(collector, "fetch_source_once", return_value=(
            self.source, [], None
        )) as fetch:
            _, items, error = collector.fetch_source(self.source)
        self.assertIsNone(error)
        self.assertEqual(items, [])
        fetch.assert_called_once()

    def test_niji_release_index_excludes_tutorials_and_does_not_guess_dates(self):
        source = {"id": "niji-blog", "name": "Niji", "url": "https://nijijourney.com/blog",
                  "type": "niji-release-index", "modelMatches": {"midjourney": ["niji"]}}
        page = """
        <a href="/blog/niji-8"><h2>Welcome to Niji 8!</h2><p>What's new in Niji 8</p></a>
        <a href="/blog/niji-7-prompting-guide">Niji 7 Prompting Guide</a>
        <a href="https://example.com/blog/niji-9">Niji 9</a>
        <a href="/blog/niji-10">Unrelated article</a>
        <a href="/zh/blog/niji-7">欢迎来到Niji 7!</a>
        """
        items = collector.html_page_items(page, source)
        self.assertEqual({x["title"] for x in items}, {"Niji 8 官方发布公告", "Niji 7 官方发布公告"})
        self.assertTrue(all(x["publishedAt"] is None for x in items))
        self.assertTrue(all(x["modelId"] == "midjourney" for x in items))


class EffectiveYieldTests(unittest.TestCase):
    def test_glm_markdown_uses_explicit_dates_and_standalone_names(self):
        source = {"url": "https://docs.z.ai/notes.md", "modelTitlePattern": r"GLM-\d+(?:\.\d+)*(?:-[A-Za-z]+)*",
                  "modelMatches": {"glm": [r"re:\bGLM-\d"]}}
        page = "# Models\n**2026-08-26**\n\nGLM-5.3-Flash\n* Mentions GLM-5.2\n**2026-08-18**\nGLM-5.3\n# Other\nGLM-9\n"
        items = collector.markdown_dated_model_items(page, source)
        self.assertEqual([(x["title"], x["publishedAt"][:10]) for x in items],
                         [("GLM-5.3-Flash", "2026-08-26"), ("GLM-5.3", "2026-08-18")])
        self.assertTrue(all(x["updateType"] == "model-card" and "publicationDateKind" not in x for x in items))

    def test_version_docs_do_not_borrow_unrelated_dates(self):
        source = {"url": "https://docs.midjourney.com/version", "type": "version-document",
                  "modelTitlePattern": r"Niji\s+\d+", "modelMatches": {"midjourney": ["niji"]}}
        page = "<h2>Niji 7</h2><p>Overview. Niji 7, launched on January 9, 2026, has new features.</p><h2>Niji 8</h2><p>Other model released on June 1, 2026.</p>"
        items = collector.html_page_items(page, source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["publishedAt"][:10], "2026-01-09")
        self.assertEqual(items[0]["updateType"], "model-card")

    def test_zero_match_fallback_preserves_primary_degradation(self):
        source = {"url": "https://example.com/index", "fallbackOnZeroMatch": True,
                  "fallbackEndpoints": [{"url": "https://official.example/docs", "type": "version-document"}]}
        with patch.object(collector, "fetch_source_once", side_effect=[
                (source, [], None), (source, [{"title": "Niji 7"}], None)]) as fetch:
            effective, items, error = collector.fetch_source(source)
        self.assertIsNone(error)
        self.assertTrue(effective["primaryDegraded"])
        self.assertEqual(effective["type"], "version-document")
        self.assertEqual(effective["attempts"][0]["itemCount"], 0)
        self.assertEqual(len(items), 1)

    def test_effective_coverage_does_not_count_failed_old_or_duplicate_endpoints(self):
        entries = [
            {"error": None, "effectiveUrl": "https://docs.example/", "matchedModelFamilyIds": ["glm"],
             "recentDatedModelFamilyIds": ["glm"], "primaryDegraded": True},
            {"error": None, "effectiveUrl": "https://docs.example/", "matchedModelFamilyIds": ["glm"]},
            {"error": "403", "matchedModelFamilyIds": ["gpt"]},
            {"error": None, "matchedModelFamilyIds": []},
        ]
        result = collector.effective_coverage(entries, {"glm": {}, "gpt": {}})
        self.assertEqual(result["reachableSources"], 3)
        self.assertEqual(result["matchingModelSources"], 2)
        self.assertEqual(result["distinctMatchingEndpoints"], 1)
        self.assertEqual(result["matchedFamilies"], 1)
        self.assertEqual(result["unmatchedFamilies"], ["gpt"])
        self.assertEqual(result["fallbackSources"], 1)
