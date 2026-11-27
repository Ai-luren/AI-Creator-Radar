import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.collect_models import (
    BlockParser, html_page_items, is_release_candidate, make_item, markdown_news_items, match_model, parse_date,
    rss_items, merge_item, apply_recent_model_versions,
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

    def test_merge_item_accepts_legacy_records_without_tracking_fields(self):
        old = {"id": "entry", "sourceName": "Old source", "summary": "old"}
        new = {"id": "entry", "sourceName": "New source", "summary": "longer new summary",
               "discoveredAt": "2026-11-22T00:00:00Z", "lastSeenAt": "2026-11-22T00:00:00Z"}
        merged = merge_item(old, new)
        self.assertEqual(merged["sourceNames"], ["Old source", "New source"])
        self.assertEqual(merged["summary"], "longer new summary")
        self.assertEqual(merged["lastSeenAt"], "2026-11-22T00:00:00Z")

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
        self.assertTrue(is_release_candidate("Seedance 2.5 coming soon", None))
        self.assertTrue(is_release_candidate("Seedance 2.5 开放预约", None))
        self.assertFalse(is_release_candidate("Seedream 5.5", "2026-11-09T00:00:00Z"))
        self.assertTrue(is_release_candidate("Seedream 5.5 officially released", "2026-11-09T00:00:00Z"))
        self.assertFalse(is_release_candidate("Seedance", None))

    def test_pre_release_teaser_is_labeled_announcement_not_api_release(self):
        item = make_item({
            "title": "Seedance 2.5 coming soon",
            "summary": "Join the waitlist",
            "url": "https://seed.example/blog/seedance-teaser",
            "publishedAt": None,
            "modelId": "seedance",
        }, self.source, {}, "2026-11-23T00:00:00Z")
        self.assertEqual(item["updateType"], "announcement")
        self.assertIsNone(item["publishedAt"])

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

    def test_heading_enclosing_article_anchor_beats_unrelated_icon(self):
        page = '<a href="/icons.svg?v=1">Icon</a><a href="/blog/seedance-3"><h2>Introducing Seedance 3.0</h2></a><time datetime="2026-11-26">Nov 26, 2026</time>'
        items = html_page_items(page, self.source)
        self.assertEqual(items[0]["url"], "https://seed.example/blog/seedance-3")

    def test_no_article_link_does_not_guess_from_adjacent_navigation(self):
        page = '<a href="/blog/unrelated">Navigation</a><h2>Introducing Seedance 3.0</h2><time datetime="2026-11-26">Nov 26, 2026</time>'
        items = html_page_items(page, self.source)
        self.assertEqual(items[0]["url"], self.source["url"])

    def test_dated_catalog_preserves_explicit_section_date(self):
        source = dict(self.source, type="dated-headings")
        page = '<h2>2026</h2><h3>Seedance 2.9</h3><h3>2026-11-25</h3><h4>Seedance 3.0</h4><p>Some description</p><h3>2026-11-26</h3><h4>Seedream 6.0</h4>'
        items = html_page_items(page, source)
        self.assertEqual([(x["title"], x["publishedAt"][:10]) for x in items], [("Seedance 3.0", "2026-11-25"), ("Seedream 6.0", "2026-11-26")])
        self.assertTrue(all(x["url"] == source["url"] for x in items))

    def test_source_coverage_uses_active_canonical_ids(self):
        from scripts.collect_models import source_coverage
        result = source_coverage([dict(self.source, active=True), dict(self.source, active=False, modelMatches={"other": ["other"]})], {"seedance": {}, "other": {}})
        self.assertEqual(result["configuredFamilies"], 1)
        self.assertEqual(result["unmappedFamilyIds"], ["seedream"])
        self.assertEqual(result["unmonitoredFamilyIds"], ["other"])

    def test_same_article_can_announce_distinct_model_families(self):
        from scripts.collect_models import make_item
        first = {"title": "Introducing Seedance 3.0", "url": "https://seed.example/blog/both", "modelId": "seedance"}
        second = dict(first, title="Introducing Seedream 6.0", modelId="seedream")
        self.assertNotEqual(make_item(first, self.source, {}, "2026-11-26")["id"], make_item(second, self.source, {}, "2026-11-26")["id"])

    def test_explicit_named_version_heading(self):
        source = dict(self.source, allowNamedVersion=True, modelMatches={"midjourney": ["re:^Version"]})
        page = '<h2><a href="/version-9">Version 9</a></h2><time datetime="2026-11-26">2026-11-26</time>'
        self.assertEqual(html_page_items(page, source)[0]["title"], "Version 9")

    def test_old_first_seen_is_preserved(self):
        from scripts.collect_models import merge_item
        old = {"firstSeenAt": "2026-01-01", "discoveredAt": "2026-01-02"}
        new = {"firstSeenAt": "2026-11-26", "discoveredAt": "2026-11-26"}
        self.assertEqual(merge_item(old, new)["firstSeenAt"], "2026-01-01")

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

    def test_recent_version_updates_structured_family_via_legacy_id(self):
        models = {
            "wan": {
                "id": "wan", "name": "Wan", "legacyIds": ["wan-3"],
                "version": "Wan 2.7", "versions": [
                    {"id": "wan-27", "name": "Wan 2.7", "releaseDate": "2026-06-12"}
                ],
            }
        }
        incoming = [{"modelId": "wan-3", "modelVersion": "Wan 3.0",
                     "publishedAt": "2026-11-22T10:00:00Z",
                     "url": "https://wan.example/wan-30"}]
        changed = apply_recent_model_versions(
            models, incoming, datetime(2026, 11, 23, tzinfo=timezone.utc))
        self.assertEqual(changed, ["wan-3 → Wan 3.0"])
        self.assertEqual(len(models["wan"]["versions"]), 2)
        self.assertEqual(models["wan"]["versions"][-1]["releaseUrl"], incoming[0]["url"])
        self.assertIn("Wan 2.7", models["wan"]["version"])

    def test_official_versioned_product_release_feed_accepts_version_only_titles(self):
        source = {
            "id": "claude-code", "name": "Claude Code releases",
            "url": "https://github.com/anthropics/claude-code/releases.atom",
            "type": "rss", "allowVersionOnly": True,
            "modelMatches": {"claude-code": [r"re:v?2\.1\.\d+"]},
        }
        xml = b"""<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'><entry>
        <title>v2.1.322</title><link href='https://github.com/anthropics/claude-code/releases/tag/v2.1.322'/>
        <updated>2026-11-10T02:29:00Z</updated><summary>Added a Vertex fast mode fallback.</summary>
        </entry></feed>"""
        items = rss_items(xml, source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["modelId"], "claude-code")
        self.assertEqual(items[0]["title"], "v2.1.322")
        self.assertEqual(items[0]["publishedAt"], "2026-11-10T02:29:00Z")

    def test_product_releases_do_not_change_foundation_model_version(self):
        from datetime import datetime, timezone
        from scripts.collect_models import apply_recent_model_versions
        models = {"claude-code": {"id": "claude-code", "version": "2.1.322"}}
        items = [{
            "modelId": "claude-code", "modelVersion": "2.1.330",
            "publishedAt": "2026-11-20T22:32:56Z", "url": "https://example.com/release",
            "updateType": "product-release",
        }]
        changed = apply_recent_model_versions(models, items, datetime(2026, 11, 23, tzinfo=timezone.utc))
        self.assertEqual(changed, [])
        self.assertEqual(models["claude-code"]["version"], "2.1.322")
        self.assertNotIn("versions", models["claude-code"])

    def test_official_markdown_news_section_extracts_dated_model_release(self):
        source = {
            "id": "qwen3-tts", "name": "Qwen3-TTS official repository",
            "url": "https://raw.githubusercontent.com/QwenLM/Qwen3-TTS/main/README.md",
            "section": "News", "modelMatches": {"qwen3-tts": ["Qwen3-TTS"]},
        }
        page = """# Qwen3-TTS
## News
- 2026.1.22: We have released [Qwen3-TTS](https://qwen.ai/blog?id=qwen3-tts) series (0.6B/1.7B).
## Contents
- unrelated text
"""
        items = markdown_news_items(page, source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["modelId"], "qwen3-tts")
        self.assertEqual(items[0]["publishedAt"], "2026-01-22T00:00:00Z")
        self.assertEqual(items[0]["url"], "https://qwen.ai/blog?id=qwen3-tts")


class SandResearchTests(unittest.TestCase):
    def test_research_card_uses_its_own_date_and_official_article_only(self):
        source = {
            "id": "sandai-research", "name": "Sand.ai research",
            "url": "https://sand.ai/research/", "official": True,
            "updateType": "announcement", "modelMatches": {"magi-2": ["MAGI-2"]},
        }
        page = """
        <a href="/blog/magi-2/"><h2>MAGI-2: A frontier video model</h2>
        <span>November 24, 2026 · Research</span></a>
        <a href="/blog/magi-2-preview/"><h2>MAGI-2 Preview</h2></a>
        <a href="https://other.example/blog/magi-2/">
        MAGI-2 November 25, 2026 · Research</a>
        <a href="/blog/other/">Unrelated November 26, 2026 · Research</a>
        """
        items = html_page_items(page, source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], "https://sand.ai/blog/magi-2/")
        self.assertEqual(items[0]["publishedAt"], "2026-11-24T00:00:00Z")
        self.assertEqual(items[0]["modelId"], "magi-2")
        self.assertEqual(items[0]["updateType"], "announcement")


class ProductAnnouncementTests(unittest.TestCase):
    def test_official_rss_can_include_non_model_product_news_without_promoting_it(self):
        source = {"id":"test","name":"Official","url":"https://official.example/rss","allowProductAnnouncements":True,"announcementHosts":["official.example"],"modelMatches":{}}
        feed = b'<rss><channel><item><title>Introducing new subscription pricing</title><link>https://official.example/news/pricing</link><pubDate>Fri, 20 Nov 2026 10:00:00 GMT</pubDate></item><item><title>Introducing a new feature</title><link>https://unrelated.example/news</link><pubDate>Fri, 20 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>'
        items = rss_items(feed, source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["updateType"], "product-announcement")
        self.assertIsNone(make_item(items[0], source, {}, "2026-11-26T00:00:00Z")["modelId"])


class LocalizedResearchTests(unittest.TestCase):
    def test_research_index_collects_exact_links_without_inferred_dates(self):
        source={"id":"zhipu-research-index","type":"zhipu-research-index",
                "url":"https://www.zhipuai.cn/zh/research","modelMatches":{"glm":["re:\\bGLM[- ]\\d+(?:\\.\\d+)*\\b"]}}
        page="""<a href="/zh/news/123"><span>2026/11/22</span><h2>GLM-5.4：新架构</h2></a>
        <a href="/zh/research/124">2026/11/23 GLM-5.5：新模型</a>
        <a href="/zh/news/125"><h2>新闻汇总 GLM-5.6</h2></a>
        <a href="https://evil.example/zh/news/126"><h2>GLM-5.7</h2></a>
        <a href="/zh/news/127"><h2>GLM-5.8</h2><h2>GLM-5.9</h2></a>"""
        items=html_page_items(page,source)
        self.assertEqual([x["url"] for x in items],["https://www.zhipuai.cn/zh/news/123","https://www.zhipuai.cn/zh/research/124"])
        self.assertTrue(all(x["publishedAt"] is None and x["updateType"]=="model-card" for x in items))

    def test_localized_article_date_is_anchored_and_conflicts_rejected(self):
        from scripts.collect_models import article_publication_date
        title="GLM-5.4：新架构"
        page=f"<h1>{title}</h1><p>2026年11月22日</p><h2>更多</h2><p>2026年11月23日</p>"
        self.assertEqual(article_publication_date(page,title),"2026-11-22T00:00:00Z")
        conflict=f"<h1>{title}</h1><p>2026/11/22</p><p>2026年11月23日</p>"
        self.assertIsNone(article_publication_date(conflict,title))

    def test_localized_publisher_clock_and_category_are_date_only(self):
        from scripts.collect_models import article_publication_date
        title="GLM-5.4：新架构"
        page=f"<h1>{title}</h1><div>2026/11/22 16:00<span>基座模型</span></div><p>模型介绍</p><h1>泛Coding</h1>"
        self.assertEqual(article_publication_date(page,title,leading_date=True,publisher_host="www.zhipuai.cn"),"2026-11-22T00:00:00Z")
        self.assertIsNone(article_publication_date(page,title,leading_date=True,publisher_host="other.example"))
        conflict=f"<h1>{title}</h1><div>2026/11/22 16:00基座模型</div><p>2026年11月23日</p>"
        self.assertIsNone(article_publication_date(conflict,title,leading_date=True,publisher_host="www.zhipuai.cn"))


if __name__ == "__main__":
    unittest.main()
