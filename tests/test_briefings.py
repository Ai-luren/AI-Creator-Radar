import unittest

from scripts.collect_briefings import compact_aihot, compact_juya


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


if __name__ == "__main__":
    unittest.main()
