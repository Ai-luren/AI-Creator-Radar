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
