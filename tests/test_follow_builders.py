import unittest
from unittest.mock import patch
from datetime import datetime, timezone

from scripts.collect_follow_builders import add_chinese_translations, compact_feed


class FollowBuildersCollectorTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 22, 8, 0, tzinfo=timezone.utc)

    def test_compacts_recent_builder_posts_and_drops_old_posts(self):
        payload = {"x": [{"name": "Builder", "handle": "builder", "tweets": [
            {"id": "new", "text": "New idea", "createdAt": "2026-11-22T07:00:00Z", "url": "https://x.com/builder/status/new", "likes": 3},
            {"id": "old", "text": "Old idea", "createdAt": "2026-11-20T07:00:00Z", "url": "https://x.com/builder/status/old"},
        ]}]}
        result = compact_feed("builders", "x", payload, self.now)
        self.assertEqual([item["id"] for item in result], ["new"])
        self.assertEqual(result[0]["name"], "Builder")
        self.assertEqual(result[0]["likes"], 3)

    def test_translation_cache_is_reused_for_unchanged_post(self):
        posts = [{"id": "1", "text": "Build faster"}]
        add_chinese_translations(posts, {"builders": [{"id": "1", "text": "Build faster", "textZh": "更快构建"}]})
        self.assertEqual(posts[0]["textZh"], "更快构建")

    def test_chinese_post_uses_original_as_chinese_display(self):
        posts = [{"id": "2", "text": "今天发布新模型"}]
        add_chinese_translations(posts)
        self.assertEqual(posts[0]["textZh"], posts[0]["text"])

    @patch("scripts.collect_follow_builders.translate_to_chinese", side_effect=lambda text: "译文：" + text)
    def test_profile_bio_is_translated_and_reused_for_same_author(self, translate):
        posts = [
            {"id": "1", "handle": "rauchg", "bio": "CEO @vercel", "text": "Launch"},
            {"id": "2", "handle": "rauchg", "bio": "CEO @vercel", "text": "Update"},
        ]
        add_chinese_translations(posts)
        self.assertEqual(posts[0]["bioZh"], "译文：CEO @vercel")
        self.assertEqual(posts[1]["bioZh"], posts[0]["bioZh"])
        self.assertEqual(translate.call_count, 3)  # two post texts and one profile bio

    def test_podcast_snapshot_omits_full_transcript(self):
        payload = {"podcasts": [{"name": "Show", "title": "Episode", "publishedAt": "2026-11-21T00:00:00Z", "url": "https://example.com/episode", "transcript": "Do not copy"}]}
        result = compact_feed("podcasts", "podcasts", payload, self.now)
        self.assertEqual(len(result), 1)
        self.assertNotIn("transcript", result[0])

    def test_invalid_feed_shape_is_rejected(self):
        with self.assertRaises(ValueError):
            compact_feed("builders", "x", {"x": {}}, self.now)


if __name__ == "__main__":
    unittest.main()
