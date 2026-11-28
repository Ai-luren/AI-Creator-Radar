import unittest
from datetime import datetime, timedelta, timezone
from scripts.revid_research_core import canonical_post, personal_candidates, quota_remaining

NOW = datetime(2026, 11, 28, 10, tzinfo=timezone.utc)


class RevidResearchCoreTest(unittest.TestCase):
    def test_rolling_window_and_failed_closed(self):
        previous = NOW - timedelta(hours=23)
        attempts = [previous.isoformat()] * 16
        self.assertEqual(quota_remaining(attempts, NOW), 0)
        self.assertEqual(quota_remaining(attempts, NOW, automatic=False), 4)
        self.assertEqual(quota_remaining(attempts, NOW + timedelta(hours=2)), 16)
        self.assertEqual(quota_remaining(None, NOW), 0)
        self.assertEqual(quota_remaining(["bad"], NOW), 0)
        self.assertEqual(quota_remaining([(NOW + timedelta(seconds=1)).isoformat()], NOW), 0)

    def test_original_url_allowlist(self):
        self.assertEqual(canonical_post("https://youtu.be/abcdefghijk?si=tracking"),
                         ("youtube", "https://www.youtube.com/watch?v=abcdefghijk"))
        self.assertEqual(canonical_post("https://twitter.com/example/status/123?s=20"),
                         ("x", "https://x.com/i/web/status/123"))
        for url in ("https://x.com/user", "https://youtube.com.evil.test/watch?v=abcdefghijk",
                    "https://youtube.com@evil.test/watch?v=abcdefghijk",
                    "https://www.youtube.com:444/watch?v=abcdefghijk", "", None):
            self.assertIsNone(canonical_post(url))

    def test_dates_platform_metrics_and_dedup(self):
        base = {"url": "https://www.youtube.com/shorts/abcdefghijk",
                "platform": "tiktok", "postedAt": NOW.isoformat(),
                "engagement": {"views": 10000, "likes": 0},
                "transcript": "synthetic fixture", "videoUrl": "https://example.test/video"}
        rows = [base, dict(base, url="https://youtu.be/abcdefghijk"),
                dict(base, postedAt=None), dict(base, url=""),
                dict(base, url="https://x.com/u/status/123",
                     postedAt=(NOW - timedelta(days=4)).isoformat()),
                dict(base, url="https://x.com/u/status/456",
                     postedAt=(NOW + timedelta(seconds=1)).isoformat()),
                dict(base, url="https://x.com/u/status/789",
                     engagement={"views": True})]
        output = personal_candidates(rows, NOW)
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["platform"], "youtube")
        self.assertEqual(output[0]["views"], 10000)
        self.assertEqual(output[0]["likes"], 0)
        self.assertIsNone(output[0]["shares"])
        self.assertNotIn("transcript", output[0])
        self.assertNotIn("videoUrl", output[0])
        self.assertEqual(len(personal_candidates(rows, NOW, days=7)), 2)
