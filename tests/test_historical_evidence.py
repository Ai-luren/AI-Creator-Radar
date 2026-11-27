import unittest
from datetime import datetime,timedelta,timezone
from scripts.collect_historical_evidence import recover

class HistoricalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,27,tzinfo=timezone.utc)
        self.url="https://official.example/news/demo-3"
        self.families=[{"id":"demo","vendor":"Vendor","versions":[{"id":"v3","name":"Demo 3"},{"id":"v4","name":"Demo 4"}]}]
        self.sources=[{"id":"official","active":True,"official":True,"url":"https://official.example/news",
                       "modelMatches":{"demo":["demo"]}}]
        self.allowed={"official.example":["/news/"]}
        self.gap={"modelFamilyId":"demo","modelVersionId":"v3","modelName":"Demo 3",
                  "reviewKind":"release-source-review","candidateSourceUrl":self.url}
        self.page='<h1>Demo 3 officially released</h1><time datetime="2024-01-03T00:00:00Z">January 3, 2024</time>'
    def run_recover(self,old=None,gaps=None,resolution=None,days=0,fetcher=None):
        return recover(self.families,[self.gap] if gaps is None else gaps,self.sources,self.allowed,
                       old or {},resolution or {},self.now+timedelta(days=days),fetcher or (lambda _:self.page))
    def test_old_article_date_is_recovered_not_first_release(self):
        result=self.run_recover()
        t=result["tasks"][0]
        self.assertEqual(t["status"],"article-date-observed")
        self.assertEqual(t["evidence"][0]["publisherCalendarDay"],"2024-01-03")
        self.assertIsNone(t["evidence"][0]["eventDate"])
        self.assertEqual(t["evidence"][0]["claimType"],"explicit-release-statement")
    def test_shared_url_wrong_variant_is_not_evidence(self):
        second=dict(self.gap,modelVersionId="v4",modelName="Demo 4")
        result=self.run_recover(gaps=[self.gap,second])
        self.assertEqual(result["summary"]["urlsAttemptedThisRun"],1)
        self.assertEqual(result["summary"]["states"],{"article-date-observed":1,"identity-mismatch":1})
    def test_unknown_or_listing_pointer_is_not_fetched(self):
        for url in (None,"https://untrusted.example/news/demo","https://official.example/news"):
            result=self.run_recover(gaps=[dict(self.gap,candidateSourceUrl=url)],
                                    fetcher=lambda _:self.fail("unexpected fetch"))
            self.assertEqual(result["summary"]["urlsAttemptedThisRun"],0)
    def test_outage_preserves_evidence_and_cooldown(self):
        first=self.run_recover()
        def fail(_):
            raise OSError("403")
        second=self.run_recover(first,days=8,fetcher=fail)
        self.assertEqual(second["tasks"][0]["evidence"],first["tasks"][0]["evidence"])
        self.assertEqual(second["tasks"][0]["status"],"fetch-failed")
        third=self.run_recover(second,days=8,fetcher=lambda _:self.fail("cooldown"))
        self.assertEqual(third["summary"]["urlsAttemptedThisRun"],0)
    def test_resolver_backoff_is_respected(self):
        result=self.run_recover(resolution={"items":[{"url":self.url,"status":"fetch-failed",
                 "nextAttemptAt":"2026-11-28T00:00:00Z"}]},fetcher=lambda _:self.fail("cooldown"))
        self.assertEqual(result["summary"]["urlsAttemptedThisRun"],0)
    def test_date_conflict_is_not_guessed(self):
        result=self.run_recover(fetcher=lambda _:self.page+'<time datetime="2024-01-04T00:00:00Z">January 4, 2024</time>')
        self.assertEqual(result["tasks"][0]["status"],"article-date-unresolved")
        self.assertEqual(result["summary"]["datedArticleRecords"],0)


    def test_replaced_pointer_does_not_erase_or_reuse_old_evidence(self):
        first=self.run_recover()
        newer=dict(self.gap,candidateSourceUrl="https://untrusted.example/news/demo")
        result=self.run_recover(first,gaps=[newer],days=1,fetcher=lambda _:self.fail("unsupported"))
        self.assertEqual(result["tasks"][0]["evidence"],first["tasks"][0]["evidence"])
        self.assertEqual(result["tasks"][0]["status"],"unsupported-original-pointer")
        self.assertEqual(result["summary"]["tasksWithCurrentPointerEvidence"],0)

    def test_later_different_article_date_retains_and_flags_conflict(self):
        first=self.run_recover()
        second=self.run_recover(first,days=8,fetcher=lambda _:self.page.replace("2024-01-03","2024-01-04").replace("January 3","January 4"))
        self.assertEqual(second["tasks"][0]["status"],"article-date-conflict")
        self.assertEqual(second["tasks"][0]["conflictingArticleDays"],["2024-01-03","2024-01-04"])
        self.assertEqual(second["summary"]["datedArticleRecords"],2)
