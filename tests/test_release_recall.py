import unittest
from datetime import date
from scripts.collect_release_recall import assess
from scripts.collect_models import article_publication_date, merge_item, non_release_title, is_release_candidate


class ReleaseRecallTests(unittest.TestCase):
    def setUp(self):
        self.url = "https://official.example/model-3"
        self.stamp = "2026-11-26T17:00:00Z"
        self.bench = {"reviewedAt": "2026-11-27", "scope": "fixture", "events": [{
            "id": "event", "modelFamilyId": "demo", "eventDate": "2026-11-23",
            "sourceUrls": [self.url], "titlePatterns": ["Demo 3", "Turbo"], "modelNames": ["Demo 3", "Demo 3 Turbo"]}]}
        self.item = {"id":"x","official":True,"modelId":"demo","title":"Introducing Demo 3 and Turbo",
                     "url":self.url + "?utm_source=feed", "sourceId":"a","lastSeenAt":self.stamp,
                     "publishedAt":"2026-11-23T00:00:00Z"}
        self.status = {"checkedAt":self.stamp,"sources":[{"id":"a","checkedAt":self.stamp,"error":None}]}

    def run_score(self, items, digest=None):
        return assess(self.bench, items, self.status, digest or {}, date(2026,11,26))

    def test_current_and_retained_are_distinct(self):
        self.assertEqual(self.run_score([self.item])["allSample"]["currentDated"],1)
        self.item["lastSeenAt"]="old"
        self.assertEqual(self.run_score([self.item])["events"][0]["outcome"],"retained-dated-only")

    def test_date_mismatch_and_wrong_family_are_not_hits(self):
        self.item["publishedAt"]="2026-10-18"
        self.assertEqual(self.run_score([self.item])["events"][0]["outcome"],"date-mismatch")
        self.item["modelId"]="other"
        self.assertEqual(self.run_score([self.item])["events"][0]["outcome"],"identity-mismatch")

    def test_multi_model_event_requires_all_versions(self):
        row={"modelFamilyId":"demo","modelName":"Demo 3","publishedAt":"2026-11-23","url":self.url}
        self.assertFalse(self.run_score([self.item],{"items":[row]})["events"][0]["canonicalComplete"])
        self.assertTrue(self.run_score([self.item],{"items":[row,dict(row,modelName="Demo 3 Turbo")]})["events"][0]["canonicalComplete"])

    def test_article_date_beats_index_date_and_preserves_previous(self):
        page='<h1>Demo 3 Released</h1><time datetime="2026-11-23">Nov 23, 2026</time><h2>Other</h2><p>Nov 17, 2026</p>'
        stamp=article_publication_date(page,"Demo 3 Released")
        self.assertEqual(stamp,"2026-11-23T00:00:00Z")
        old=dict(self.item,publishedAt="2026-10-18T00:00:00Z")
        new=dict(self.item,publishedAt=stamp,publicationDateKind="article-explicit-date",publicationObservedAt=self.stamp)
        merged=merge_item(old,new)
        self.assertEqual(merged["publishedAt"],stamp)
        self.assertIn(old["publishedAt"],merged["previousSourceDates"])

    def test_article_does_not_use_unrelated_or_conflicting_dates(self):
        self.assertIsNone(article_publication_date('<h1>Different model</h1><time datetime="2026-11-23"/>',"Demo 3"))
        page='<meta property="article:published_time" content="2026-11-24"><h1>Demo 3</h1><time datetime="2026-11-23"/>'
        self.assertIsNone(article_publication_date(page,"Demo 3"))
        self.assertIsNone(article_publication_date('<h1>Demo 3</h1><h2>Other</h2><time datetime="2026-11-23"/>',"Demo 3"))

    def test_tutorials_do_not_become_model_release_candidates(self):
        for title in ("How to make a film with Kling 4.0","Seedance 2.0 Review: Features and Prompts","Seedance 2.0 评测：功能"):
            self.assertTrue(non_release_title(title))
            self.assertFalse(is_release_candidate(title, "2026-11-23"))
        self.assertTrue(is_release_candidate("Introducing Demo 3", "2026-11-23"))


    def test_research_label_date_requires_matching_heading(self):
        page = '<span>2026-11-23 · Research</span><h1>GLM-5.4: New architecture</h1>'
        self.assertEqual(article_publication_date(page, "GLM-5.4: New architecture", leading_date=True)[:10], "2026-11-23")
        self.assertIsNone(article_publication_date(page, "GLM-5.3", leading_date=True))


    def test_compact_publisher_heading_is_exact_not_substring(self):
        page = '<span>November 9, 2026</span><h1>Claude Fable 5.2 and Mythos 5.2</h1>'
        title = "Introducing Claude Fable 5.2 and Claude Mythos 5.2"
        self.assertEqual(article_publication_date(page, title, leading_date=True)[:10], "2026-11-09")
        self.assertIsNone(article_publication_date(page, title))
        self.assertIsNone(article_publication_date(page, title.replace("Fable 5.2", "Fable 5.3"), leading_date=True))
        self.assertIsNone(article_publication_date(page, "Claude Fable 5.2", leading_date=True))
        conflict = '<meta property="article:published_time" content="2026-10-18">' + page
        self.assertIsNone(article_publication_date(conflict, title, leading_date=True))
        ambiguous = page + '<h1>Introducing Claude Fable 5.2 and Claude Mythos 5.2</h1>'
        self.assertIsNone(article_publication_date(ambiguous, title, leading_date=True))
