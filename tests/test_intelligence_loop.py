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

class SandGraphicHeadingTests(unittest.TestCase):
    def setUp(self):
        self.url = "https://sand.ai/blog/magi-2/"
        self.now = datetime(2026,11,28,tzinfo=timezone.utc)
        self.title = "MAGI-2: A 480B Frontier Video Generation Model"
        self.sources = [{"id":"sandai-research","url":"https://sand.ai/research/","active":True,"official":True,
                         "modelMatches":{"magi-2":["re:\\bMAGI[- ]2\\b"]}}]
        self.catalog = {"magi-2":{"id":"magi-2","vendor":"Sand.ai","category":"video","versions":[
            {"id":"magi-2-preview","name":"MAGI-2 Preview"},{"id":"magi-2","name":"MAGI-2"}]}}
        self.page = ('<title>'+self.title+'</title><div><span>November 24, 2026•RESEARCH</span>'
                     '<h1><img src="logo.svg" alt="">A 480B Frontier<br>Video Generation Model</h1>'
                     '<p>In August 2026, we released MAGI-2 Preview.</p>'
                     '<p>Today, we are launching MAGI-2—our flagship model.</p></div>')

    def parse(self, page=None, url=None):
        return parse_article(page or self.page,url or self.url,["MAGI-2"],self.sources,self.catalog,self.now)

    def test_graphic_heading_recovers_exact_launch_evidence(self):
        row = self.parse()
        self.assertEqual(row["status"],"article-date-verified")
        self.assertEqual(row["title"],self.title)
        self.assertEqual(row["articlePublishedAt"][:10],"2026-11-24")
        self.assertEqual(row["publisherReleaseStatement"]["modelName"],"MAGI-2")
        self.assertEqual(row["publisherReleaseStatement"]["calendarDay"],"2026-11-24")
        self.assertEqual(row["publisherReleaseStatement"]["statement"],"Today, we are launching MAGI-2")
        self.assertNotIn("releaseEvidence",row)

    def test_future_preview_missing_title_and_conflicting_dates_do_not_pass(self):
        for page in [self.page.replace("we are launching MAGI-2—","we will launch MAGI-2—"),
                     self.page.replace("we are launching MAGI-2—","we are launching MAGI-2 Preview—"),
                     self.page.replace("<title>"+self.title+"</title>",""),
                     self.page.replace("A 480B Frontier<br>","A Different Model<br>"),
                     '<meta property="article:published_time" content="2026-11-25">'+self.page]:
            self.assertNotEqual(self.parse(page)["status"],"article-date-verified")
        self.assertEqual(self.parse(url="https://unrelated.example/blog/magi-2/")["status"],"identity-unresolved")

class SandLocalizedDiscoveryTests(unittest.TestCase):
    def test_chinese_research_fallback_keeps_publisher_date_and_article_url(self):
        from pathlib import Path
        from unittest.mock import patch
        from scripts.collect_models import fetch_source, html_page_items
        sources = json.loads((Path(__file__).resolve().parents[1] / "config/model-sources.json").read_text())
        source = next(s for s in sources if s["id"] == "sandai-research")
        cn = "https://sandai.cn/research"
        article = "https://sand.ai/blog/magi-2/"
        page = ('<a href="'+article+'"><h2>MAGI-2：480B 旗舰视频生成模型</h2>'
                '<span>2026年11月24日 · 研究</span></a>'
                '<a href="https://sand.ai/blog/magi-2-preview/"><h2>MAGI-2 Preview</h2>'
                '<span>2026年8月5日 · 研究</span></a>'
                '<a href="https://unrelated.example/blog/magi-2/">MAGI-2 2026年11月25日</a>')
        for error in ("HTTPError: HTTP Error 403: Forbidden", None):
            calls = []
            def fetch(endpoint):
                calls.append(endpoint["url"])
                if endpoint["url"] == source["url"]:
                    return endpoint, [], error
                self.assertEqual(endpoint["url"],cn)
                return endpoint, html_page_items(page,endpoint), None
            with patch("scripts.collect_models.fetch_source_once",side_effect=fetch):
                effective, rows, err = fetch_source(source,now=datetime(2026,11,28,tzinfo=timezone.utc))
            self.assertEqual(calls,[source["url"],cn])
            self.assertIsNone(err)
            self.assertTrue(effective["primaryDegraded"])
            self.assertEqual(effective["url"],cn)
            self.assertEqual(len(rows),2)
            row = next(x for x in rows if x["url"]==article)
            self.assertEqual(row["publishedAt"][:10],"2026-11-24")
            self.assertEqual(row["modelId"],"magi-2")
            self.assertEqual(row["updateType"],"announcement")
            self.assertNotIn("releaseEvidence",row)
            self.assertNotIn("publicationDateKind",row)

class AccessDomainRoutingTests(unittest.TestCase):
    def test_denied_locales_skip_without_blocking_independent_api(self):
        from unittest.mock import patch
        from scripts.collect_models import fetch_source
        cfg = {"id":"niji","url":"https://nijijourney.com/blog",
               "fallbackUrls":["https://nijijourney.com/en/blog","https://nijijourney.com/zh/blog",
                               "https://docs.midjourney.com/hc/en-us/articles/test",
                               "https://docs.midjourney.com/api/v2/help_center/articles/test.json"],
               "fallbackOnZeroMatch":True}
        calls=[]
        def fetch(source):
            url=source["url"];calls.append(url)
            return (source,[{"title":"Niji 8"}],None) if "/api/" in url else (source,[],"HTTPError: HTTP Error 403: Forbidden")
        with patch("scripts.collect_models.fetch_source_once",side_effect=fetch):
            state, rows, error=fetch_source(cfg,now=datetime(2026,11,28,tzinfo=timezone.utc))
        self.assertEqual(calls,[cfg["url"],cfg["fallbackUrls"][2],cfg["fallbackUrls"][3]])
        self.assertIsNone(error)
        self.assertEqual(len(rows),1)
        self.assertEqual(sum(a.get("skipReason")=="access-domain-cooldown" for a in state["attempts"]),2)

    def test_resolver_403_reallocates_budget_and_preserves_observations(self):
        from datetime import timedelta
        now=datetime(2026,11,28,tzinfo=timezone.utc)
        urls=["https://official.example/blog/a","https://official.example/zh/blog/b",
              "https://other.example/news/c"]
        config={"officialArticleHosts":{"official.example":["/blog/","/zh/blog/"],"other.example":["/news/"]}}
        sources=[{"id":str(i),"url":url,"active":True,"official":True,"modelMatches":{"demo":["Demo"]}} for i,url in enumerate(urls)]
        discovery={"items":[{"id":str(i),"title":"Demo 3","sourceId":"feed",
                             "officialArticleUrls":[url],"reportedAt":"2026-11-27"} for i,url in enumerate(urls)]}
        family=[{"id":"demo","vendor":"Demo","category":"llm"}]
        calls=[]
        def fetch(url):
            calls.append(url)
            if "official.example" in url:
                raise OSError("HTTP 403")
            return '<h1>Introducing Demo 3</h1><time datetime="2026-11-27">November 27, 2026</time>'
        first=resolve(discovery,{},config,sources,family,now,fetch)
        self.assertEqual(first["summary"]["attempted"],2)
        self.assertEqual(first["summary"]["accessDomainDeferred"],1)
        self.assertEqual(first["summary"]["articleDateVerified"],1)
        self.assertEqual(sum("official.example" in u for u in calls),1)
        second=resolve(discovery,first,config,sources,family,now+timedelta(minutes=10),
                       lambda url:self.fail("cooldown must not request"))
        self.assertEqual(second["summary"]["attempted"],0)
        self.assertEqual(second["items"],first["items"])
        self.assertEqual(second["accessFaultDomains"],first["accessFaultDomains"])

    def test_429_honors_retry_after_and_404_does_not_open_domain(self):
        from scripts.collect_models import access_fault_code, access_retry_at
        from urllib.error import HTTPError
        from datetime import timedelta
        now=datetime(2026,11,28,tzinfo=timezone.utc)
        error=HTTPError("https://official.example/blog/a",429,"rate limit",{"Retry-After":"86400"},None)
        self.assertEqual(access_retry_at(error,now,now+timedelta(hours=6)),now+timedelta(days=1))
        self.assertIsNone(access_fault_code(HTTPError("https://official.example/blog/a",404,"missing",{},None)))
