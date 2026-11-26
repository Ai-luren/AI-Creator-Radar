import datetime as dt
import unittest
from scripts.stage_creator_instagram import stage, canonical_post

class CreatorInstagramStagingTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 11, 26, 12, tzinfo=dt.timezone.utc)
        self.registry = {"creators":[{"id":"kaye","accounts":[{"platform":"Instagram","url":"https://www.instagram.com/kaye.creatives/"}]}]}
        self.row = {"ownerUsername":"KAYE.Creatives","url":"https://www.instagram.com/reel/AbC123/?igsh=abc","shortCode":"AbC123","timestamp":"2026-11-25T12:00:00Z"}
    def test_recent_candidate_is_never_published(self):
        report = stage([self.row, self.row], self.registry, self.now, 7)
        self.assertEqual(report["published"], 0)
        self.assertEqual(len(report["candidates"]), 1)
        self.assertEqual(report["candidates"][0]["url"], "https://www.instagram.com/reel/AbC123/")
        self.assertEqual(report["rejected"], {"duplicate-post":1})
    def test_stale_future_and_missing_timezone(self):
        rows = [dict(self.row,timestamp=t) for t in ("2026-11-18T00:00:00Z","2026-11-27T00:00:00Z","2026-11-25T12:00:00")]
        report = stage(rows,self.registry,self.now,7)
        self.assertEqual(report["rejected"],{"missing-or-outside-window":3})
    def test_author_and_url_must_match(self):
        rows = [dict(self.row,ownerUsername="other"),dict(self.row,url="https://instagram.com.evil.example/reel/AbC123/"),dict(self.row,shortCode="different")]
        report = stage(rows,self.registry,self.now)
        self.assertEqual(report["rejected"],{"unlinked-or-ambiguous-author":1,"invalid-post-url":2})
    def test_profile_is_not_post(self):
        self.assertIsNone(canonical_post("https://www.instagram.com/kaye.creatives/"))
    def test_window_30_days(self):
        report = stage([dict(self.row,timestamp="2026-11-01T12:00:00Z")],self.registry,self.now,30)
        self.assertEqual(len(report["candidates"]),1)
