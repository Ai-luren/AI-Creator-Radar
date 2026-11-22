import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.collect_models import (
    BlockParser, html_page_items, is_release_candidate, match_model, parse_date,
    rss_items,
)


class ModelCollectorTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "id": "seed", "name": "Seed official", "url": "https://seed.example/",
            "type": "html", "official": True,
            "modelMatches": {
                "seedance": ["seedance"],
                "seedream": ["seedream"],
            },
        }

    def test_parse_chinese_date(self):
        self.assertEqual(parse_date("2026.11.16"), "2026-11-16T00:00:00Z")
        self.assertEqual(parse_date("2026年11月9日"), "2026-11-09T00:00:00Z")

    def test_parse_month_date(self):
        self.assertEqual(parse_date("Nov 17, 2026"), "2026-11-17T00:00:00Z")

    def test_parse_us_numeric_date(self):
        self.assertEqual(parse_date("11/19/2026"), "2026-11-19T00:00:00Z")

    def test_model_match(self):
        self.assertEqual(match_model("Seedance 2.5 正式发布", self.source), "seedance")
        self.assertEqual(match_model("Seedream 5.5 release", self.source), "seedream")
        self.assertIsNone(match_model("A general company announcement", self.source))

    def test_release_candidate_requires_release_signal_or_dated_version(self):
        self.assertTrue(is_release_candidate("Seedance 2.5 正式发布", None))
        self.assertFalse(is_release_candidate("Seedream 5.5", "2026-11-09T00:00:00Z"))
        self.assertTrue(is_release_candidate("Seedream 5.5 officially released", "2026-11-09T00:00:00Z"))
        self.assertFalse(is_release_candidate("Seedance", None))

    def test_html_page_extracts_title_date_link_and_summary(self):
        page = """
        <html><body><h2><a href="/blog/seedance-25">一镜成片，Seedance 2.5 正式发布</a></h2>
        <time datetime="2026-11-16">2026.11.16</time>
        <p>支持 30 秒长叙事与精准参考。</p></body></html>
        """
        items = html_page_items(page, self.source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["modelId"], "seedance")
        self.assertEqual(items[0]["url"], "https://seed.example/blog/seedance-25")
        self.assertEqual(items[0]["publishedAt"], "2026-11-16T00:00:00Z")
        self.assertIn("30 秒", items[0]["summary"])

    def test_html_finds_date_and_article_link_outside_heading(self):
        from scripts.collect_models import html_page_items
        page = """
        <section><h2>MiniMax Music 3.0：新一代音乐模型</h2>
        <span>2026-08-13</span><a href="/news/music-30">Learn more</a>
        <p>新一代音乐生成模型。</p></section>
        """
        source = {
            "id": "minimax", "name": "MiniMax", "url": "https://ir.minimax.io/zh/news-events/new-releases",
            "modelMatches": {"minimax-music": ["minimax music"]},
        }
        items = html_page_items(page, source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["publishedAt"], "2026-08-13T00:00:00Z")
        self.assertEqual(items[0]["url"], "https://ir.minimax.io/news/music-30")

    def test_html_ignores_unrelated_features(self):
        page = """
        <h2>Introducing Visuals</h2><time datetime="2026-11-17">Nov 17, 2026</time>
        <p>Turn any song into a video.</p>
        """
        self.assertEqual(html_page_items(page, self.source), [])

    def test_model_card_table_extracts_title_date_and_link(self):
        from scripts.collect_models import model_card_items
        page = '<table><tr><td><a href="/models/veo-31-lite">Veo 3.1 Lite</a></td><td>Updated 8 April 2026</td></tr></table>'
        parser = BlockParser()
        parser.feed(page)
        parser.close()
        source = {
            "id": "deepmind", "name": "DeepMind",
            "url": "https://deepmind.google/models/model-cards/",
            "modelMatches": {"veo": ["veo"]},
        }
        items = model_card_items(parser.blocks, source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Veo 3.1 Lite")
        self.assertEqual(items[0]["publishedAt"], "2026-04-08T00:00:00Z")
        self.assertEqual(items[0]["url"], "https://deepmind.google/models/veo-31-lite")

    def test_model_card_table_accepts_long_official_update_rows(self):
        from scripts.collect_models import model_card_items
        page = (
            "<table><tr><td>2026/10/7</td><td>New Models - Vidu Q4 Preview: "
            + ("Supports reference voices and high-dynamic scenes. " * 12)
            + "</td></tr></table>"
        )
        parser = BlockParser()
        parser.feed(page)
        parser.close()
        source = {
            "id": "vidu-updates", "name": "Vidu updates",
            "url": "https://platform.vidu.com/docs/api-reference/updates",
            "modelMatches": {"vidu": ["vidu q4", "viduq4"]},
            "maxRowLength": 2500,
        }
        items = model_card_items(parser.blocks, source)
        self.assertEqual(len(items), 1)
        self.assertIn("Vidu Q4 Preview", items[0]["title"])
        self.assertEqual(items[0]["publishedAt"], "2026-10-07T00:00:00Z")

    def test_rss_extracts_official_model_release(self):
        source = {
            "id": "google", "name": "DeepMind", "url": "https://example.com/feed.xml",
            "type": "rss", "modelMatches": {"veo": ["veo"]},
        }
        xml = b"""<?xml version='1.0'?><rss><channel><item>
        <title>Introducing Veo 3.1</title><link>https://example.com/veo-31</link>
        <description>New video model</description><pubDate>Tue, 17 Nov 2026 10:00:00 GMT</pubDate>
        </item></channel></rss>"""
        items = rss_items(xml, source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["modelId"], "veo")
        self.assertEqual(items[0]["publishedAt"], "2026-11-17T10:00:00Z")


if __name__ == "__main__":
    unittest.main()
