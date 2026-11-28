import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from scripts.collect_briefings import compact_aihot, compact_juya, write_snapshot, find_juya_url, JUYA_ARCHIVE_URL, JUYA_RSS_URL


class BriefingCollectorTests(unittest.TestCase):
    def test_aihot_extracts_lead_and_category_articles(self):
        page = """<main><article><section class='grid'><h2>头条标题</h2><p>头条摘要</p><a href='/story/lead'>原文</a></section>
        <section class='daily'><h2>产品发布</h2><article><div>OpenAI 一手</div><h3>模型上线</h3><p>模型摘要</p><div><a href='https://example.com/source'>原文</a></div></article></section></article></main>"""
        result = compact_aihot(page, "https://aihot.news/daily", "2026-11-22T00:00:00Z")
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["category"], "头条")
        self.assertEqual(result["items"][1]["category"], "产品发布")
        self.assertEqual(result["items"][1]["url"], "https://example.com/source")

    def test_juya_extracts_multiple_items_and_category_groups(self):
        page = """<main><h1>AI 早报 2026-11-22</h1><h2>开发生态</h2>
        <section class='news-item'><h3>第一条 #1</h3><p>第一条摘要</p><p>更多内容</p><p>相关链接：</p><ul><li><a href='https://example.com/1'>https://example.com/1</a></li></ul></section>
        <h2>产品应用</h2><section class='news-item'><h3>第二条 #2</h3><p>第二条摘要</p></section></main>"""
        result = compact_juya(page, "https://daily.juya.uk/issues/2026-11-22/", "2026-11-22T00:00:00Z")
        self.assertEqual(result["title"], "AI 早报 2026-11-22")
        self.assertEqual([x["category"] for x in result["items"]], ["开发生态", "产品应用"])
        self.assertEqual(result["items"][0]["title"], "第一条")
        self.assertIn("更多内容", result["items"][0]["summary"])
        self.assertEqual(result["items"][0]["url"], "https://example.com/1")

    def test_changed_aihot_page_fails_closed_if_parser_finds_no_digest(self):
        with self.assertRaises(ValueError):
            compact_aihot("<main><article><h1>Changed page</h1></article></main>", "https://aihot.news/daily", "now")

    @patch("scripts.collect_briefings.request")
    def test_juya_uses_live_archive_and_latest_dated_official_link(self, fetch):
        fetch.return_value = b'<a href="/issues/2026-11-24/">old</a><a href="/issues/2026-11-26/">new</a><a href="https://evil.example/issues/2099-01-01/">other</a>'
        self.assertEqual(find_juya_url(), "https://daily.juya.uk/issues/2026-11-26/")
        fetch.assert_called_once_with(JUYA_ARCHIVE_URL)

    @patch("scripts.collect_briefings.request")
    def test_juya_falls_back_to_live_rss_if_archive_unavailable(self, fetch):
        fetch.side_effect = [OSError("archive unavailable"), b'<rss><channel><item><link>https://daily.juya.uk/issues/2026-11-26/</link></item></channel></rss>']
        self.assertEqual(find_juya_url(), "https://daily.juya.uk/issues/2026-11-26/")
        self.assertEqual(fetch.call_args_list[1].args, (JUYA_RSS_URL, "application/rss+xml,application/xml"))

    @patch("scripts.collect_briefings.request")
    def test_juya_cannot_mark_cached_issue_as_fresh_when_live_indexes_fail(self, fetch):
        fetch.side_effect = [OSError("offline"), b'<rss><channel/></rss>']
        with self.assertRaises(ValueError):
            find_juya_url()

    def test_snapshot_rejects_regressed_or_undated_edition(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "daily.json"
            current = {"title": "AI 日报 2026 年 11 月 26 日", "items": []}
            write_snapshot(path, current)
            for title in ("2026-11-25", "unknown"):
                with self.assertRaises(ValueError):
                    write_snapshot(path, {"title": title, "items": []})
                self.assertEqual(json.loads(path.read_text()), current)

    def test_denied_or_rate_limited_request_is_not_immediately_retried(self):
        from urllib.error import HTTPError
        from scripts.collect_briefings import request
        for status in (403,429):
            with patch("scripts.collect_briefings.urllib.request.urlopen",side_effect=HTTPError("https://example.org/feed",status,"blocked",{},None)) as fetch:
                with self.assertRaises(HTTPError):
                    request("https://example.org/feed")
                self.assertEqual(fetch.call_count,1)

    def test_transient_request_retries_at_most_once(self):
        from urllib.error import URLError
        from scripts.collect_briefings import request
        with patch("scripts.collect_briefings.urllib.request.urlopen",side_effect=URLError("offline")) as fetch, patch("scripts.collect_briefings.time.sleep"):
            with self.assertRaises(URLError):
                request("https://example.org/feed")
            self.assertEqual(fetch.call_count,2)


if __name__ == "__main__":
    unittest.main()
