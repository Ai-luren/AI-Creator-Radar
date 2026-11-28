import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from scripts import collect_model_evaluations as collector
from scripts.collect_model_evaluations import (
    SogouResultsParser,
    aipick_candidates,
    contains_captcha,
    recent_targets,
    sogou_candidate,
)


class ModelEvaluationCollectorTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)
        self.models = [
            {"id": "seedream", "name": "Seedream", "vendor": "Seed", "category": "image", "version": "5.5"},
            {"id": "kling-image", "name": "Kling Image", "vendor": "Kling", "category": "image", "version": "4.0"},
            {"id": "minimax-h3", "name": "MiniMax H3", "vendor": "MiniMax", "category": "video", "version": "H3"},
        ]
        self.updates = [
            {"modelId": "seedream", "modelName": "Seedream", "title": "Seedream 5.5 发布", "category": "image", "updateType": "release", "publishedAt": "2026-11-09T00:00:00Z"},
            {"modelName": "Kling Image 4.0", "title": "Kling Image 4.0 发布", "category": "image", "updateType": "model-release", "publishedAt": "2026-11-17T00:00:00Z"},
            {"modelId": "minimax-h3", "title": "MiniMax H3 发布", "category": "video", "updateType": "release", "publishedAt": "2026-08-03T00:00:00Z"},
            {"modelName": "Kling 4.0", "title": "Kling API 更新", "category": "video", "updateType": "api-update", "publishedAt": "2026-11-19T00:00:00Z"},
        ]

    def test_recent_targets_include_versioned_recent_releases_only(self):
        targets = recent_targets(self.models, self.updates, self.now)

        self.assertEqual({target["id"] for target in targets}, {"seedream", "kling-image"})
        seedream = next(target for target in targets if target["id"] == "seedream")
        self.assertEqual(seedream["name"], "Seedream 5.5")
        self.assertIn("Seedream 5.5 发布", seedream["aliases"])
        self.assertIn("Seedream 5.5", seedream["query"])

    def test_sogou_parser_extracts_only_public_result_fields(self):
        search_url = "https://weixin.sogou.com/weixin?type=2&query=Seedream"
        parser = SogouResultsParser(search_url)
        parser.feed("""
          <li><h3><a href="/link?url=example">Seedream 5.5 深度测评</a></h3>
          <p class="txt-info">实测多轮编辑表现，并与旧版进行对比。</p>
          <span class="all-time-y2">AI图像研究所</span>
          <span class="s2"><script>document.write(timeConvert('1795348800'))</script></span></li>
        """)
        parser.close()

        self.assertEqual(len(parser.items), 1)
        item = parser.items[0]
        self.assertEqual(item["title"], "Seedream 5.5 深度测评")
        self.assertIn("实测多轮编辑", item["summary"])
        self.assertEqual(item["account"], "AI图像研究所")
        self.assertEqual(item["url"], "https://weixin.sogou.com/link?url=example")
        self.assertIsNotNone(item["publishedAt"])

    def test_captcha_is_detected_and_not_treated_as_a_result(self):
        self.assertTrue(contains_captcha("请完成验证码验证", "https://weixin.sogou.com/antispider/"))
        self.assertFalse(contains_captcha("Seedream 5.5 评测结果", "https://weixin.sogou.com/weixin"))

    def test_collection_stops_after_first_sogou_verification_response(self):
        paths = {
            collector.OUTPUT: {},
            collector.MODELS_PATH: self.models,
            collector.UPDATES_PATH: {"items": self.updates[:2]},
            collector.AIPICK_PATH: {"items": []},
        }
        with patch.object(collector, "load_json", side_effect=lambda path, fallback: paths[path]), \
             patch.object(collector, "fetch_sogou", return_value=([], True, "搜狗返回验证页")) as fetch:
            result = collector.collect(now=self.now, dry_run=True)

        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(result["status"]["sogou"]["status"], "blocked")
        self.assertEqual(result["status"]["sogou"]["searchesThisRun"], 1)
        self.assertEqual(result["searchState"]["blockedUntil"], "2026-11-23T12:00:00Z")

    def test_sogou_candidate_requires_model_name_and_evaluation_signal(self):
        target = next(target for target in recent_targets(self.models, self.updates, self.now) if target["id"] == "seedream")
        candidate = sogou_candidate({
            "title": "Seedream 5.5 多轮编辑实测",
            "summary": "对新模型进行了体验和对比。",
            "account": "AI图像研究所",
            "publishedAt": "2026-11-20T00:00:00Z",
            "url": "https://weixin.sogou.com/link?url=example",
        }, target, self.now)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["sourceType"], "sogou-wechat")

        unrelated = sogou_candidate({
            "title": "Seedream 5.5 官方发布",
            "summary": "模型发布说明。",
        }, target, self.now)
        self.assertIsNone(unrelated)

    def test_aipick_candidate_needs_model_match_and_evaluation_signal(self):
        target = next(target for target in recent_targets(self.models, self.updates, self.now) if target["id"] == "seedream")
        payload = {"items": [
            {
                "id": "review-1", "title": "Seedream 5.5 实测：多轮编辑表现",
                "summary": "一组模型对比。", "publishedAt": "2026-11-20T00:00:00Z",
                "source": {"name": "创作观察"},
                "links": {"original": "https://example.com/review"},
            },
            {
                "id": "news-2", "title": "Seedream 5.5 正式发布",
                "summary": "官方介绍新功能。", "publishedAt": "2026-11-20T00:00:00Z",
                "source": {"name": "新闻来源"}, "links": {"original": "https://example.com/news"},
            },
        ]}

        candidates = aipick_candidates(payload, [target], self.now)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["sourceType"], "aipick")
        self.assertEqual(candidates[0]["url"], "https://example.com/review")


if __name__ == "__main__":
    unittest.main()
