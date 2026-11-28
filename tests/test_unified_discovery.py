import unittest
from datetime import datetime, timezone, timedelta
from scripts.collect_cross_platform import local_snapshot_leads, merge_local_inputs, literal_model_hints
from scripts.collect_resolve_model_leads import resolve, reconcile_candidate_dates, candidate_rows, parse_article
from scripts.run_collection_batch import BATCHES


class UnifiedDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 26, 17, tzinfo=timezone.utc)
        self.url = "https://official.example/news/demo-3"
        self.hosts = {"official.example":["/news/"]}
        self.families = [{"id":"demo","vendor":"Demo","category":"llm","versions":[{"name":"Demo 3"},{"name":"Demo 3.1"}]}]
        self.sources = [{"id":"official","url":"https://official.example/news/","active":True,"official":True,"modelMatches":{"demo":["demo"]}}]
        self.snap = {"title":"AI 日报 2026 年 11 月 26 日", "fetchedAt":"2026-11-26T10:00:00Z",
            "items":[{"category":"模型发布","title":"发布 Demo 3 新模型","url":self.url,
                      "links":[{"url":self.url},{"url":"https://official.example.evil.test/news/x"}]},
                     {"category":"行业","title":"Demo 3 访谈","url":self.url}]}
        self.page = '<h1>Introducing Demo 3</h1><time datetime="2026-11-23">November 23, 2026</time><h2>Other</h2>'
    def test_daily_date_is_edition_not_first_release_and_exact_title_hint(self):
        rows, stamp = local_snapshot_leads("local-aihot-daily","AIHOT",self.snap,"fetchedAt",self.hosts,self.families,self.sources)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["dateKind"],"briefing-edition-date")
        self.assertEqual(rows[0]["reportedAt"][:10],"2026-11-26")
        self.assertEqual(rows[0]["officialArticleUrls"],[self.url])
        self.assertEqual(rows[0]["titleHints"],["Demo 3"])
        self.assertNotIn("publishedAt",rows[0])
    def test_unchanged_snapshot_does_not_refresh_observation(self):
        result=merge_local_inputs({"items":[]},{"aihot-daily.json":self.snap},self.hosts,self.families,self.sources,self.now)
        later=merge_local_inputs(result,{"aihot-daily.json":self.snap},self.hosts,self.families,self.sources,self.now+timedelta(hours=1))
        self.assertEqual(result["items"][0]["lastSeenAt"],later["items"][0]["lastSeenAt"])
    def test_model_name_boundaries_and_multiple_models(self):
        self.assertEqual(literal_model_hints("发布Demo 3.1新模型",self.families),["Demo 3.1"])
        self.assertEqual(literal_model_hints("Demo 3.2",self.families),[])
        self.assertEqual(literal_model_hints("Demo 3 Turbo",self.families),[])
    def test_direct_candidate_index_does_not_refetch_structured_or_listing(self):
        item={"title":"Introducing Demo 3","official":True,"modelId":"demo","updateType":"release","url":self.url}
        snap={"generatedAt":"2026-11-26T17:00:00Z","items":[item,dict(item,publicationDateKind="feed-published"),dict(item,url=self.sources[0]["url"])]}
        rows,_=local_snapshot_leads("local-official-candidates","Official",snap,"generatedAt",self.hosts,self.families,self.sources)
        self.assertEqual(len(rows),1)
    def run_resolution(self, previous=None, page=None, now=None):
        result=merge_local_inputs({"items":[]},{"aihot-daily.json":self.snap},self.hosts,self.families,self.sources,self.now)
        return resolve(result,previous or {},{"officialArticleHosts":self.hosts},self.sources,self.families,now or self.now,lambda u:page or self.page)
    def test_translated_news_hint_is_checked_against_official_article(self):
        self.assertEqual(self.run_resolution()["items"][0]["status"],"article-date-verified")
    def test_correction_preserves_raw_source_and_protects_explicit_dates(self):
        proof=self.run_resolution()
        original={"id":"x","official":True,"modelId":"demo","url":self.url+"?utm_source=x","title":"Introducing Demo 3","publishedAt":"2026-11-17"}
        rows,changes=reconcile_candidate_dates([original,dict(original,id="y",publicationDateKind="feed-published"),dict(original,id="z",title="Introducing Demo 3.1")],proof)
        self.assertEqual(len(changes),1)
        self.assertEqual(rows[0]["publishedAt"][:10],"2026-11-23")
        self.assertEqual(original["publishedAt"],"2026-11-17")
        self.assertEqual(rows[1]["publishedAt"],"2026-11-17")
        self.assertEqual(rows[2]["publishedAt"],"2026-11-17")
    def test_successful_read_with_date_conflict_withdraws_cached_proof(self):
        old=self.run_resolution()
        conflict='<meta property="article:published_time" content="2026-11-25">'+self.page
        result=self.run_resolution(old,conflict,self.now+timedelta(days=1))
        self.assertEqual(result["items"][0]["status"],"date-unresolved")
        self.assertEqual(candidate_rows(result),[])
    def test_old_verified_article_is_retained_without_network_polling(self):
        old = self.run_resolution()
        later = self.now + timedelta(days=40)
        result = self.run_resolution(old, now=later)
        self.assertEqual(result["summary"]["attempted"], 0)
        self.assertEqual(result["items"], old["items"])

    def test_recent_leads_precede_older_retries_under_request_budget(self):
        from unittest.mock import patch
        recent = self.url
        older = "https://official.example/news/demo-older"
        leads = {"items":[
            {"id":"old","sourceId":"a","title":"Demo 3","reportedAt":"2026-11-05","officialArticleUrls":[older]},
            {"id":"new","sourceId":"b","title":"Demo 3","reportedAt":"2026-11-25","officialArticleUrls":[recent]}]}
        calls = []
        with patch("scripts.collect_resolve_model_leads.MAX_PROBES", 1):
            resolve(leads, {}, {"officialArticleHosts":self.hosts}, self.sources, self.families, self.now, lambda url: calls.append(url) or self.page)
        self.assertEqual(calls, [recent])

    def test_recovery_is_independent_transaction_and_updates_derived_views(self):
        self.assertEqual(BATCHES["recovery"][1][0],BATCHES["models"][1][1])
        self.assertIn("collect_chronicle_updates",BATCHES["recovery"][1][0])

    def test_explicit_body_release_requires_same_model_and_present_tense(self):
        family = {"id":"demo","vendor":"Demo","category":"llm","versions":[{"name":"Demo v3 Medical"}]}
        catalog = {"demo":family}
        title = "Demo v3 Medical helps conversational agents"
        prefix = '<h1>'+title+'</h1><time datetime="2026-11-23">November 23, 2026</time>'
        def outcome(body):
            return parse_article(prefix+'<p>'+body+'</p>',self.url,[title],self.sources,catalog,self.now)["status"]
        self.assertEqual(outcome("Today, Demo is releasing Demo v3 Medical, a specialized model."),"article-date-verified")
        self.assertEqual(outcome("Today, Demo is releasing Demo v3 Medical Turbo, a specialized model."),"not-model-announcement")
        self.assertEqual(outcome("Today, Demo is releasing Demo v3 Medical next month."),"not-model-announcement")
        self.assertEqual(outcome("Last year, Demo released Demo v3 Medical."),"not-model-announcement")
        self.assertEqual(outcome("Today, another company is releasing Demo v3 Medical."),"not-model-announcement")
