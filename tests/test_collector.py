import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.collect import clean_html, infer_priority, normalize_url, parse_feed

class CollectorTests(unittest.TestCase):
    def test_clean_html(self):
        self.assertEqual(clean_html("<p>Hello&nbsp;<b>world</b></p>"), "Hello world")

    def test_normalize_url_removes_tracking(self):
        self.assertEqual(
            normalize_url("https://Example.com/post/?utm_source=x&keep=1#top"),
            "https://example.com/post?keep=1"
        )

    def test_priority(self):
        self.assertEqual(infer_priority("Introducing a new model", ""), "high")
        self.assertEqual(infer_priority("Feature update", ""), "medium")
        self.assertEqual(infer_priority("A thoughtful essay", ""), "normal")

    def test_parse_rss(self):
        xml = b"""<?xml version='1.0'?><rss version='2.0'><channel><item><title>New video model released</title><link>https://example.com/post?utm_source=rss</link><description><![CDATA[<p>Useful <b>details</b></p>]]></description><pubDate>Sat, 21 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>"""
        source = {"id":"test","name":"Test Feed","category":"models","kind":"official","focus":"Example"}
        items = parse_feed(xml, source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "New video model released")
        self.assertEqual(items[0]["url"], "https://example.com/post")
        self.assertEqual(items[0]["summary"], "Useful details")
        self.assertEqual(items[0]["priority"], "high")

    def test_parse_atom(self):
        xml = b"""<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'><entry><title>ComfyUI release</title><link href='https://github.com/example/project/releases/tag/v1'/><updated>2026-11-21T10:00:00Z</updated><summary>New nodes</summary></entry></feed>"""
        source = {"id":"atom","name":"Atom","category":"software","kind":"github","focus":"ComfyUI"}
        items = parse_feed(xml, source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], "https://github.com/example/project/releases/tag/v1")
        self.assertEqual(items[0]["category"], "software")

if __name__ == "__main__":
    unittest.main()