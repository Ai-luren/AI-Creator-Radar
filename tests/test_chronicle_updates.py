import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "collect_chronicle_updates.py"
SPEC = importlib.util.spec_from_file_location("collect_chronicle_updates", MODULE_PATH)
chronicles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(chronicles)


class ChronicleUpdateTests(unittest.TestCase):
    def setUp(self):
        self.topics = [
            {
                "id": "openai",
                "group": "公司与模型",
                "name": "OpenAI / ChatGPT",
                "milestones": [
                    {"date": "2025-01-01", "title": "人工核验旧节点", "url": "https://openai.com/old"}
                ],
            },
            {"id": "video", "group": "技术方向", "name": "视频生成", "milestones": []},
        ]

    def test_adds_official_model_release_with_source_and_review_label(self):
        updates = [
            {
                "id": "gpt-new-1",
                "official": True,
                "updateType": "release",
                "publishedAt": "2026-11-20T10:00:00Z",
                "vendor": "OpenAI",
                "title": "GPT 新版本发布",
                "summary": "官方发布说明。",
                "url": "https://openai.com/news/gpt-new",
                "sourceId": "openai-news",
                "sourceName": "OpenAI News",
                "lastSeenAt": "2026-11-24T00:00:00Z",
                "category": "llm",
            }
        ]
        merged, status = chronicles.merge_official_updates(self.topics, updates, "2026-11-24T00:00:00Z")
        event = merged[0]["milestones"][0]
        self.assertEqual(status["added"], 1)
        self.assertEqual(event["date"], "2026-11-20")
        self.assertEqual(event["sourceTier"], "official-primary")
        self.assertTrue(event["autoCollected"])
        self.assertIn("待复核", event["verificationStatus"])
        self.assertEqual(merged[1]["milestones"], [])

    def test_ignores_nonofficial_unmapped_and_duplicate_updates(self):
        updates = [
            {"id": "not-official", "official": False, "updateType": "release", "publishedAt": "2026-11-20", "vendor": "OpenAI", "title": "Mirror", "url": "https://mirror.example/a"},
            {"id": "unmapped", "official": True, "updateType": "release", "publishedAt": "2026-11-20", "vendor": "Unknown Co", "title": "New", "url": "https://unknown.example/a"},
            {"id": "openai-new", "official": True, "updateType": "release", "publishedAt": "2026-11-20", "vendor": "OpenAI", "title": "New", "url": "https://openai.com/new#announcement"},
            {"id": "openai-dup", "official": True, "updateType": "release", "publishedAt": "2026-11-20", "vendor": "OpenAI", "title": "Duplicate", "url": "https://openai.com/new"},
        ]
        merged, status = chronicles.merge_official_updates(self.topics, updates, "2026-11-24T00:00:00Z")
        self.assertEqual(status["added"], 1)
        self.assertEqual(status["unmatchedVendors"], ["Unknown Co"])
        self.assertEqual(len(merged[0]["milestones"]), 2)


if __name__ == "__main__":
    unittest.main()
