import json
import unittest
from datetime import datetime, timezone
from scripts.collect_cross_platform import llm_world_leads, collect
from scripts.collect_resolve_model_leads import resolve, parse_article, candidate_rows, title_agrees
from scripts.collect_release_recall import assess


class IntelligenceLoopTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026,11,26,17,tzinfo=timezone.utc)
        self.url = "https://official.example/news/model-3"
        self.config = {"officialArticleHosts":{"official.example":["/news/"]}}
        self.sources = [{"id":"official","url":"https://official.example/news/","active":True,"official":True,
                         "modelMatches":{"demo":["demo"]}}]
        self.families = [{"id":"demo","vendor":"Demo","category":"llm"}]
        self.lead = {"id":"lead","title":"Demo 3","sourceId":"third-party","reportedAt":"2026-11-25",
                     "officialArticleUrls":[self.url]}
        self.page = '<h1>Introducing Demo 3</h1><time datetime="2026-11-23">November 23, 2026</time><h2>Model</h2>'
    def run_resolution(self, previous=None, fetcher=None, now=None):
        return resolve({"items":[self.lead]}, previous or {}, self.config, self.sources,
                       self.families, now or self.now, fetcher or (lambda u:self.page))
    def test_model_identity_and_actual_article_date_not_feed_date(self):
        result=self.run_resolution()
        row=result["items"][0]
        self.assertEqual(row["status"],"article-date-verified")
        self.assertEqual(row["articlePublishedAt"][:10],"2026-11-23")
        candidate=candidate_rows(result)[0]
        self.assertEqual(candidate["updateType"],"model-card")
        self.assertNotIn("releaseEvidence",candidate)
        self.assertEqual(candidate["publishedAt"][:10],"2026-11-23")
    def test_verified_cache_does_not_refresh_observation(self):
        old=self.run_resolution()
        result=self.run_resolution(old,lambda u:self.fail("should not fetch"))
        self.assertEqual(result["summary"]["attempted"],0)
        self.assertEqual(result["items"],old["items"])
    def test_fetch_failure_preserves_old_verified_observation(self):
        from datetime import timedelta
        old=self.run_resolution()
        def fail(u):
            raise OSError("unavailable")
        result=self.run_resolution(old,fail,self.now+timedelta(days=1))
        self.assertEqual(result["items"][0]["status"],"fetch-failed")
        self.assertEqual(candidate_rows(result)[0]["lastSeenAt"],old["items"][0]["checkedAt"])
    def test_version_prefix_not_identity(self):
        self.assertFalse(title_agrees("Introducing Demo 3.1","Demo 3"))
        self.assertEqual(parse_article('<h1>Introducing Demo 3.1</h1><time datetime="2026-11-23"/>',
                         self.url,["Demo 3"],self.sources,{"demo":self.families[0]},self.now)["status"],"identity-unresolved")
    def test_conflicting_article_dates_are_not_evidence(self):
        result=parse_article('<meta property="article:published_time" content="2026-11-24">'+self.page,
                             self.url,["Demo 3"],self.sources,{"demo":self.families[0]},self.now)
        self.assertEqual(result["status"],"date-unresolved")
    def test_llm_world_only_event_scoped_primary_links_with_attribution(self):
        src={"id":"llm-world","name":"LLM World","project":"https://example.org","license":"CC BY 4.0","licenseUrl":"https://creativecommons.org/licenses/by/4.0/"}
        data={"schema_version":"1.6","releases":[{"model":"Claude 5.2","events":[{"type":"announcement","date":"2026-11-23","sources":["a","b"]}],
              "sources":[{"id":"a","authority":"primary","url":self.url},{"id":"b","authority":"secondary","url":"https://official.example/news/secondary"},{"id":"c","authority":"primary","url":"https://official.example/news/unrelated"}]}]}
        rows=llm_world_leads(json.dumps(data),src,self.config["officialArticleHosts"])
        self.assertEqual(rows[0]["officialArticleUrls"],[self.url])
        self.assertEqual(rows[0]["attribution"]["license"],"CC BY 4.0")
        self.assertNotIn("publishedAt",rows[0])
    def test_failed_discovery_endpoint_backoff_does_not_claim_freshness(self):
        cfg={"sources":[{"id":"s","name":"source","url":"https://example.org/rss"}],"officialArticleHosts":{}}
        old=collect(cfg,{},self.now,lambda s,a:(s,[],"HTTP 403"))
        fresh=collect(cfg,old,self.now,lambda s,a:self.fail("deferred source fetched"))
        self.assertTrue(fresh["sources"][0]["deferred"])
        self.assertEqual(fresh["sources"][0]["checkedAt"],old["sources"][0]["checkedAt"])
    def test_recovery_scored_separately_from_direct_collector(self):
        b={"reviewedAt":"2026-11-26","scope":"test","events":[{"id":"demo","modelFamilyId":"demo","eventDate":"2026-11-23",
           "sourceUrls":[self.url],"titlePatterns":["Demo 3"],"modelNames":["Demo 3"]}]}
        result=assess(b,[],{}, {},self.now.date(),self.run_resolution())
        self.assertEqual(result["allSample"]["currentDated"],0)
        self.assertEqual(result["allSample"]["endToEndDated"],1)
        self.assertEqual(result["events"][0]["recoveryFirstVerifiedLagDays"],3)


    def test_compound_heading_and_preceding_publisher_date(self):
        from scripts.collect_models import article_publication_date
        article = '<div><span>November 9, 2026</span><h1>Brand Fable 5.2 and Mythos 5.2</h1><p>Intro</p><h2>Other</h2></div>'
        self.assertTrue(title_agrees("Brand Fable 5.2 and Mythos 5.2", "Introducing Brand Fable 5.2 and Brand Mythos 5.2"))
        self.assertFalse(title_agrees("Brand Fable 5.3 and Mythos 5.2", "Introducing Brand Fable 5.2 and Brand Mythos 5.2"))
        self.assertEqual(article_publication_date(article, "Brand Fable 5.2 and Mythos 5.2", leading_date=True)[:10], "2026-11-09")
        conflict = '<meta property="article:published_time" content="2026-11-10">'+article
        self.assertIsNone(article_publication_date(conflict, "Brand Fable 5.2 and Mythos 5.2", leading_date=True))

    def test_retry_missing_heading_uses_publisher_locale_without_extra_requests(self):
        from datetime import timedelta
        self.url = "https://z.ai/blog/demo-3"
        self.lead["officialArticleUrls"] = [self.url]
        self.config = {"officialArticleHosts": {"z.ai": ["/blog/"]},
                       "articleLocaleQueries": {"z.ai": {"key": "lang", "value": "en"}}}
        self.sources[0]["url"] = "https://z.ai/blog"
        calls = []
        def fetch(url):
            calls.append(url)
            return self.page if url.endswith("?lang=en") else "<h1>Loading</h1>"
        first = self.run_resolution(fetcher=fetch)
        self.assertEqual(first["items"][0]["status"], "identity-unresolved")
        second = self.run_resolution(first, fetch, self.now + timedelta(hours=2))
        self.assertEqual(second["items"][0]["status"], "article-date-verified")
        self.assertEqual(second["items"][0]["urlKey"], self.url)
        self.assertEqual(second["items"][0]["url"], self.url + "?lang=en")
        self.assertEqual(calls, [self.url, self.url + "?lang=en"])
        third = self.run_resolution(second, fetch, self.now + timedelta(days=2))
        self.assertEqual(third["items"][0]["status"], "article-date-verified")
        self.assertEqual(calls[-1], self.url + "?lang=en")

    def test_locale_variant_does_not_evade_access_denial_or_date_conflict(self):
        from datetime import timedelta
        self.url = "https://z.ai/blog/demo-3"
        self.lead["officialArticleUrls"] = [self.url]
        self.config = {"officialArticleHosts": {"z.ai": ["/blog/"]},
                       "articleLocaleQueries": {"z.ai": {"key": "lang", "value": "en"}}}
        self.sources[0]["url"] = "https://z.ai/blog"
        for failing in ("denied", "conflict"):
            calls = []
            def fetch(url):
                calls.append(url)
                if failing == "denied":
                    raise OSError("HTTP 403")
                return '<meta property="article:published_time" content="2026-11-24">' + self.page
            first = self.run_resolution(fetcher=fetch)
            second = self.run_resolution(first, fetch, self.now + timedelta(hours=2))
            self.assertIn(second["items"][0]["status"], {"fetch-failed", "date-unresolved"})
            self.assertEqual(calls, [self.url, self.url])

    def test_discovered_url_variants_remain_one_candidate(self):
        from datetime import timedelta
        self.lead["officialArticleUrls"] = [self.url, self.url + "?lang=en", "https://untrusted.example/news/model-3"]
        calls = []
        def fetch(url):
            calls.append(url)
            return self.page if url.endswith("?lang=en") else "<h1>Loading</h1>"
        first = self.run_resolution(fetcher=fetch)
        second = self.run_resolution(first, fetch, self.now + timedelta(hours=2))
        self.assertEqual(second["summary"]["uniqueOfficialUrls"], 1)
        self.assertEqual(second["items"][0]["status"], "article-date-verified")
        self.assertEqual(calls, [self.url, self.url + "?lang=en"])
