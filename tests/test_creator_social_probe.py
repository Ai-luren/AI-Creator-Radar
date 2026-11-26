import unittest
from scripts.probe_creator_social import inspect
class CreatorSocialProbeTests(unittest.TestCase):
    def test_instagram_links_remain_candidates(self):
        row=inspect('<a href="/reel/AbC123/">reel</a><a href="/accounts/login/">login</a>',"Instagram","kaye.creatives")
        self.assertEqual(row["status"],"candidate-links-only")
        self.assertEqual(row["publishedAtVerified"],0)
        self.assertEqual(len(row["candidateLinks"]),1)
    def test_x_only_matching_handle(self):
        row=inspect('<a href="/Other/status/11">other</a><a href="/PixVerse/status/22">own</a>',"X","PixVerse")
        self.assertEqual(row["candidateLinks"],["https://x.com/PixVerse/status/22"])
    def test_login_and_empty_distinct(self):
        self.assertEqual(inspect("<title>Log in</title>","Instagram","foo")["status"],"login-or-access-blocked")
        self.assertEqual(inspect("<title>Public profile</title>","Instagram","foo")["status"],"no-parseable-post-links")
