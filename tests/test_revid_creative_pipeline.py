import io
import json
import unittest
from datetime import datetime, timezone
from scripts.revid_creative_triage import classify, group_topics
from scripts.revid_research_transport import search

NOW = datetime(2026, 11, 28, 10, tzinfo=timezone.utc)


class CreativePipelineTests(unittest.TestCase):
    def test_positive_and_negative_examples(self):
        for text in ("cinematic video with a match cut", "Spider-Man fan film",
                     "Christmas product reveal video", "animated story with a plot twist"):
            self.assertTrue(classify({"description": text}), text)
        for text in ("AI video credits and affordable pricing", "AI worries and political debate",
                     "Christmas shopping video", "cinematic video subscription pricing"):
            self.assertFalse(classify({"description": text}), text)
        self.assertFalse(classify({"description": "cinematic film", "isTextPost": True}))

    def test_pipeline_dedup_and_topic_groups(self):
        row = {"url": "https://youtu.be/abcdefghijk", "postedAt": NOW.isoformat(),
               "description": "cinematic video with a match cut",
               "engagement": {"views": 15000}}
        rows = [row, dict(row, url="https://www.youtube.com/watch?v=abcdefghijk"),
                dict(row, url="https://x.com/u/status/123"),
                dict(row, url="https://x.com/u/status/456", description="AI pricing"),
                dict(row, url="https://x.com/u/status/789", engagement={"views": 9})]
        class Fake:
            def open(self, req, timeout):
                return io.BytesIO(json.dumps({"success": 1, "videos": rows}).encode())
        result = search("creative", "synthetic", lambda _: True, now=NOW,
                        opener=Fake(), creative_only=True)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["candidates"]), 2)
        for group in result["topics"]:
            self.assertEqual(group["distinctPosts"], 2)
            self.assertEqual(group["platforms"], ["x", "youtube"])
            self.assertNotIn("views", group)
        self.assertNotIn("description", result["candidates"][0])
        self.assertEqual(group_topics([]), [])
