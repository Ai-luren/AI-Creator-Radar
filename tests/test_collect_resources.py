import unittest

from scripts.collect_resources import parse_feed_bytes


class ResourceFeedTests(unittest.TestCase):
    def test_goodcase_rss_extracts_case_author_prompt_and_image(self):
        body = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>MiniMax H3 Image product portrait</title>
              <link>https://goodcase.ai/cases/example</link>
              <guid>https://goodcase.ai/cases/example</guid>
              <pubDate>Sat, 21 Nov 2026 22:01:12 GMT</pubDate>
              <description><![CDATA[aiwithaly：MiniMax H3 Image 的人像案例。Prompt 预览：Create a cinematic portrait with natural window light.]]></description>
              <enclosure url="opengraph-image" type="image/png"/>
            </item>
          </channel>
        </rss>""".encode("utf-8")
        source = {
            "id": "goodcase",
            "name": "GoodCase.ai",
            "url": "https://goodcase.ai/feed.xml",
            "category": "cases",
        }
        items = parse_feed_bytes(body, source, "2026-11-22T00:00:00Z")
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["title"], "MiniMax H3 Image product portrait")
        self.assertEqual(item["creator"], "aiwithaly")
        self.assertIn("人像案例", item["summary"])
        self.assertEqual(item["promptPreview"], "Create a cinematic portrait with natural window light.")
        self.assertEqual(item["imageUrl"], "https://goodcase.ai/cases/example/opengraph-image")
        self.assertEqual(item["publishedAt"], "2026-11-21T22:01:12Z")
        self.assertEqual(item["url"], "https://goodcase.ai/cases/example")

    def test_news_rss_preserves_original_link_and_description(self):
        body = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>AI Brief 2026-11-22</title>
              <link>https://daily.example/brief-2026-11-22</link>
              <guid>brief-2026-11-22</guid>
              <pubDate>Sun, 22 Nov 2026 00:54:18 GMT</pubDate>
              <description><![CDATA[Today's AI news summary. Read the original sources.]]></description>
            </item>
          </channel>
        </rss>""".encode("utf-8")
        source = {
            "id": "juya-daily",
            "name": "橘鸦 AI 早报",
            "url": "https://daily.juya.uk/rss.xml",
            "category": "news",
        }
        items = parse_feed_bytes(body, source, "2026-11-22T01:00:00Z")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["category"], "news")
        self.assertEqual(items[0]["url"], "https://daily.example/brief-2026-11-22")
        self.assertEqual(items[0]["summary"], "Today's AI news summary. Read the original sources.")
        self.assertIsNone(items[0]["promptPreview"])


if __name__ == "__main__":
    unittest.main()
