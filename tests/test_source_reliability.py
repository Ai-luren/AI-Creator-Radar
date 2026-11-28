import unittest
from unittest.mock import patch

from scripts import collect_models as collector


class SourceReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "id": "demo", "name": "Demo", "url": "https://example.com/rss",
            "type": "rss", "fallbackUrls": ["https://example.com/backup"],
            "modelMatches": {"demo": ["demo"]},
        }

    def test_non_feed_xml_is_rejected(self):
        with self.assertRaises(ValueError):
            collector.rss_items(b"<html><body>Not a feed</body></html>", self.source)

    def test_valid_empty_feed_is_not_an_error(self):
        self.assertEqual(collector.rss_items(b"<rss><channel/></rss>", self.source), [])

    def test_transient_error_retries_once(self):
        with patch.object(collector, "fetch_source_once", side_effect=[
            (self.source, [], "HTTPError: HTTP Error 503: unavailable"),
            (self.source, [{"title": "Demo release"}], None),
        ]) as fetch, patch.object(collector.time, "sleep") as sleep:
            effective, items, error = collector.fetch_source(self.source)
        self.assertIsNone(error)
        self.assertEqual(len(items), 1)
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_called_once_with(2)
        self.assertEqual(len(effective["attempts"]), 2)

    def test_forbidden_uses_fallback_without_repeating_blocked_request(self):
        with patch.object(collector, "fetch_source_once", side_effect=[
            (self.source, [], "HTTPError: HTTP Error 403: Forbidden"),
            (self.source, [], None),
        ]) as fetch, patch.object(collector.time, "sleep") as sleep:
            effective, items, error = collector.fetch_source(self.source)
        self.assertIsNone(error)
        self.assertEqual(items, [])
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(effective["url"], self.source["fallbackUrls"][0])
        self.assertEqual(effective["primaryUrl"], self.source["url"])
        self.assertIn("403", effective["attempts"][0]["error"])
        sleep.assert_not_called()

    def test_failed_fallback_remains_failure(self):
        with patch.object(collector, "fetch_source_once", return_value=(
            self.source, [], "ValueError: invalid feed"
        )) as fetch:
            effective, items, error = collector.fetch_source(self.source)
        self.assertIsNotNone(error)
        self.assertEqual(items, [])
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(len(effective["attempts"]), 2)

    def test_valid_zero_match_does_not_trigger_fallback(self):
        with patch.object(collector, "fetch_source_once", return_value=(
            self.source, [], None
        )) as fetch:
            _, items, error = collector.fetch_source(self.source)
        self.assertIsNone(error)
        self.assertEqual(items, [])
        fetch.assert_called_once()

    def test_niji_release_index_excludes_tutorials_and_does_not_guess_dates(self):
        source = {"id": "niji-blog", "name": "Niji", "url": "https://nijijourney.com/blog",
                  "type": "niji-release-index", "modelMatches": {"midjourney": ["niji"]}}
        page = """
        <a href="/blog/niji-8"><h2>Welcome to Niji 8!</h2><p>What's new in Niji 8</p></a>
        <a href="/blog/niji-7-prompting-guide">Niji 7 Prompting Guide</a>
        <a href="https://example.com/blog/niji-9">Niji 9</a>
        <a href="/blog/niji-10">Unrelated article</a>
        <a href="/zh/blog/niji-7">欢迎来到Niji 7!</a>
        """
        items = collector.html_page_items(page, source)
        self.assertEqual({x["title"] for x in items}, {"Niji 8 官方发布公告", "Niji 7 官方发布公告"})
        self.assertTrue(all(x["publishedAt"] is None for x in items))
        self.assertTrue(all(x["modelId"] == "midjourney" for x in items))


class EffectiveYieldTests(unittest.TestCase):
    def test_glm_markdown_uses_explicit_dates_and_standalone_names(self):
        source = {"url": "https://docs.z.ai/notes.md", "modelTitlePattern": r"GLM-\d+(?:\.\d+)*(?:-[A-Za-z]+)*",
                  "modelMatches": {"glm": [r"re:\bGLM-\d"]}}
        page = "# Models\n**2026-08-26**\n\nGLM-5.3-Flash\n* Mentions GLM-5.2\n**2026-08-18**\nGLM-5.3\n# Other\nGLM-9\n"
        items = collector.markdown_dated_model_items(page, source)
        self.assertEqual([(x["title"], x["publishedAt"][:10]) for x in items],
                         [("GLM-5.3-Flash", "2026-08-26"), ("GLM-5.3", "2026-08-18")])
        self.assertTrue(all(x["updateType"] == "model-card" and "publicationDateKind" not in x for x in items))

    def test_version_docs_do_not_borrow_unrelated_dates(self):
        source = {"url": "https://docs.midjourney.com/version", "type": "version-document",
                  "modelTitlePattern": r"Niji\s+\d+", "modelMatches": {"midjourney": ["niji"]}}
        page = "<h2>Niji 7</h2><p>Overview. Niji 7, launched on January 9, 2026, has new features.</p><h2>Niji 8</h2><p>Other model released on June 1, 2026.</p>"
        items = collector.html_page_items(page, source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["publishedAt"][:10], "2026-01-09")
        self.assertEqual(items[0]["updateType"], "model-card")

    def test_zero_match_fallback_preserves_primary_degradation(self):
        source = {"url": "https://example.com/index", "fallbackOnZeroMatch": True,
                  "fallbackEndpoints": [{"url": "https://official.example/docs", "type": "version-document"}]}
        with patch.object(collector, "fetch_source_once", side_effect=[
                (source, [], None), (source, [{"title": "Niji 7"}], None)]) as fetch:
            effective, items, error = collector.fetch_source(source)
        self.assertIsNone(error)
        self.assertTrue(effective["primaryDegraded"])
        self.assertEqual(effective["type"], "version-document")
        self.assertEqual(effective["attempts"][0]["itemCount"], 0)
        self.assertEqual(len(items), 1)

    def test_effective_coverage_does_not_count_failed_old_or_duplicate_endpoints(self):
        entries = [
            {"error": None, "effectiveUrl": "https://docs.example/", "matchedModelFamilyIds": ["glm"],
             "recentDatedModelFamilyIds": ["glm"], "primaryDegraded": True},
            {"error": None, "effectiveUrl": "https://docs.example/", "matchedModelFamilyIds": ["glm"]},
            {"error": "403", "matchedModelFamilyIds": ["gpt"]},
            {"error": None, "matchedModelFamilyIds": []},
        ]
        result = collector.effective_coverage(entries, {"glm": {}, "gpt": {}})
        self.assertEqual(result["reachableSources"], 3)
        self.assertEqual(result["matchingModelSources"], 2)
        self.assertEqual(result["distinctMatchingEndpoints"], 1)
        self.assertEqual(result["matchedFamilies"], 1)
        self.assertEqual(result["unmatchedFamilies"], ["gpt"])
        self.assertEqual(result["fallbackSources"], 1)


    def test_public_article_json_ignores_updated_at(self):
        import json
        source = {"url": "https://docs.example/api", "articleUrl": "https://docs.example/version",
                  "articleId": 42, "modelTitlePattern": r"Niji\s+\d+", "modelMatches": {"midjourney": ["niji"]}}
        body = json.dumps({"article": {"id": 42, "draft": False, "updated_at": "2026-11-27",
                            "body": "<h2>Niji 7</h2><p>Niji 7, launched on January 9, 2026, is available.</p>"}})
        items = collector.version_document_json_items(body, source)
        self.assertEqual(items[0]["publishedAt"][:10], "2026-01-09")
        self.assertEqual(items[0]["url"], source["articleUrl"])
        with self.assertRaises(ValueError):
            collector.version_document_json_items('{"article":{"id":43,"draft":false,"body":"x"}}', source)

    def test_markdown_release_headings_exclude_minor_feature_updates(self):
        source = {"url": "https://official.example/changelog.md", "modelTitlePattern": r"Scribe\s+v\d+",
                  "modelMatches": {"eleven-scribe": ["scribe"]}}
        page = "## November 9, 2026\n### Scribe v3\nNow available\n### Scribe v3 character limits\nFeature\n## November\n### Scribe v4\n"
        items = collector.markdown_dated_release_headings(page, source)
        self.assertEqual([(x["title"], x["publishedAt"][:10]) for x in items], [("Scribe v3", "2026-11-09")])
        self.assertEqual(items[0]["updateType"], "model-card")


class EndpointBackoffTests(unittest.TestCase):
    def setUp(self):
        from datetime import datetime, timezone
        self.now = datetime(2026, 11, 27, 0, tzinfo=timezone.utc)
        self.source = {"id": "demo", "url": "https://example.com/blocked",
                       "fallbackUrls": ["https://example.com/working"]}
    def test_blocked_primary_is_deferred_but_fallback_still_checked(self):
        from datetime import timedelta
        def fetch(s):
            return s, [], "HTTPError: HTTP Error 403: Forbidden" if s["url"].endswith("blocked") else None
        with patch.object(collector, "fetch_source_once", side_effect=fetch) as mock:
            first, _, error = collector.fetch_source(self.source, now=self.now)
            self.assertIsNone(error)
            self.assertEqual(mock.call_count, 2)
            second, _, error = collector.fetch_source(self.source, first, self.now + timedelta(minutes=15))
            self.assertIsNone(error)
            self.assertEqual(mock.call_count, 3)
            self.assertTrue(second["attempts"][0]["deferred"])
            self.assertEqual(second["attempts"][0]["checkedAt"], first["attempts"][0]["checkedAt"])
            self.assertTrue(second["primaryDegraded"])
            collector.fetch_source(self.source, second, self.now + timedelta(hours=1))
            self.assertEqual(mock.call_count, 5)
    def test_all_blocked_remain_errors_and_config_change_retries(self):
        from datetime import timedelta
        source = {"url": "https://example.com/missing"}
        with patch.object(collector, "fetch_source_once", return_value=(source, [], "HTTPError: HTTP Error 404: Not Found")) as mock:
            first, _, error = collector.fetch_source(source, now=self.now)
            self.assertIsNotNone(error)
            second, items, error = collector.fetch_source(source, first, self.now + timedelta(minutes=15))
            self.assertTrue(second["sourceDeferred"])
            self.assertEqual(items, [])
            self.assertIn("404", error)
            self.assertEqual(mock.call_count, 1)
            collector.fetch_source(dict(source, type="rss"), second, self.now + timedelta(minutes=16))
            self.assertEqual(mock.call_count, 2)
    def test_niji_link_retains_real_heading_for_article_verification(self):
        source = {"url": "https://nijijourney.com/blog", "type": "niji-release-index"}
        rows = collector.html_page_items('<a href="/blog/niji-8"><h2>Welcome to Niji 8!</h2><p>Details</p></a>', source)
        self.assertEqual(rows[0]["articleTitle"], "Welcome to Niji 8!")
        self.assertIsNone(rows[0]["publishedAt"])

class CollectionPerformanceTests(unittest.TestCase):
    def test_identical_article_probe_is_reused_but_different_title_is_not(self):
        cache = collector.ArticleDateProbeCache()
        source = {"url":"https://example.com/news","articleDateCheck":True}
        original = {"url":"https://example.com/news/demo","title":"Demo model release"}
        with patch.object(collector, "probe_article_date", return_value="2026-11-27T00:00:00Z") as probe:
            first = collector.enrich_article_dates(source, [dict(original)], cache)
            second = collector.enrich_article_dates(source, [dict(original)], cache)
            collector.enrich_article_dates(source, [{**original,"title":"Another release"}], cache)
        self.assertEqual(first, second)
        self.assertEqual(first[0]["publicationDateKind"], "article-explicit-date")
        self.assertEqual(probe.call_count, 2)
        self.assertEqual((cache.requests, cache.reused), (2, 1))

    def test_failed_probe_not_cached_or_promoted(self):
        cache = collector.ArticleDateProbeCache()
        key = ("https://example.com/news/demo", "Demo release")
        with patch.object(collector, "probe_article_date", side_effect=[None, "2026-11-27T00:00:00Z"]) as probe:
            self.assertIsNone(cache.get(key, lambda: probe(*key)))
            self.assertEqual(cache.get(key, lambda: probe(*key)), "2026-11-27T00:00:00Z")
            self.assertEqual(probe.call_count, 2)

    def test_concurrent_probes_share_one_request(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        cache = collector.ArticleDateProbeCache()
        entered, release = Event(), Event()
        def fetch():
            entered.set()
            self.assertTrue(release.wait(3))
            return "2026-11-27T00:00:00Z"
        key = ("https://example.com/news/demo", "Demo release")
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(cache.get, key, fetch)
            self.assertTrue(entered.wait(3))
            second = pool.submit(cache.get, key, lambda: self.fail("duplicate request"))
            release.set()
            self.assertEqual(first.result(timeout=3), second.result(timeout=3))
        self.assertEqual((cache.requests, cache.reused), (1, 1))

    def test_unmatched_headings_do_not_scan_full_page_for_date(self):
        source = {"url":"https://example.com/news","modelMatches":{"demo":["demo"]}}
        page = "".join("<h2>Navigation section %d</h2>" % n for n in range(100))
        page += '<a href="/news/demo"><h2>Introducing Demo 2.0</h2></a>'
        with patch.object(collector, "find_date_near_title", wraps=collector.find_date_near_title) as scan:
            items = collector.html_page_items(page, source)
        self.assertEqual([i["title"] for i in items], ["Introducing Demo 2.0"])
        self.assertEqual(scan.call_count, 1)

class ConditionalFeedTests(unittest.TestCase):
    def setUp(self):
        from datetime import datetime, timezone
        self.now = datetime(2026,11,28,0,0,tzinfo=timezone.utc)
        self.source = {"id":"feed","name":"Feed","url":"https://example.com/rss","type":"rss","modelMatches":{"demo":["demo"]}}
        self.items = [{"title":"Demo 2.0 release","summary":"","url":"https://example.com/release","publishedAt":"2026-11-27T00:00:00Z","modelId":"demo","publicationDateKind":"feed-published"}]
        self.cache = {"key":collector.feed_cache_key(self.source,"parser"),"etag":'"v1"',"downloadedAt":self.now.isoformat(),"items":self.items,"itemsHash":collector.feed_items_hash(self.items)}
        self.conditional = {"entry":self.cache,"now":self.now,"revision":"parser"}

    def test_304_reuses_exact_parsed_feed_and_original_download_time(self):
        import urllib.error
        err = urllib.error.HTTPError(self.source["url"],304,"Not Modified",{},None)
        with patch.object(collector.urllib.request,"urlopen",side_effect=err) as fetch:
            effective, items, error = collector.fetch_source_once(self.source,conditional=self.conditional)
        self.assertIsNone(error)
        self.assertEqual(items,self.items)
        self.assertTrue(effective["_notModified"])
        self.assertEqual(effective["_feedCache"]["downloadedAt"],self.cache["downloadedAt"])
        self.assertEqual(fetch.call_args.args[0].get_header("If-none-match"),'"v1"')

    def test_expired_changed_or_corrupt_cache_and_article_probes_not_reused(self):
        from datetime import timedelta
        for source, entry, now, revision in [
            (self.source,self.cache,self.now+timedelta(hours=6),"parser"),
            (self.source,self.cache,self.now,"new-parser"),
            ({**self.source,"url":"https://example.com/other"},self.cache,self.now,"parser"),
            ({**self.source,"articleDateCheck":True},self.cache,self.now,"parser"),
            (self.source,{**self.cache,"items":[]},self.now,"parser"),
            (self.source,{**self.cache,"downloadedAt":"bad"},self.now,"parser"),
        ]:
            self.assertIsNone(collector.reusable_feed_cache(source,entry,now,revision))

    def test_unconditional_304_is_failure_not_empty_success(self):
        import urllib.error
        err = urllib.error.HTTPError(self.source["url"],304,"Not Modified",{},None)
        with patch.object(collector.urllib.request,"urlopen",side_effect=err) as fetch:
            effective, items, error = collector.fetch_source_once(self.source,conditional={**self.conditional,"entry":None})
        self.assertIsNotNone(error)
        self.assertEqual(items,[])
        self.assertIsNone(fetch.call_args.args[0].get_header("If-none-match"))

    def test_valid_200_stores_exact_representation(self):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers = {"ETag":'"v2"',"Content-Type":"application/rss+xml"}
        response.read.return_value = b"<rss/>"
        with patch.object(collector.urllib.request,"urlopen",return_value=response), patch.object(collector,"rss_items",return_value=self.items):
            effective, items, error = collector.fetch_source_once(self.source,conditional={**self.conditional,"entry":None})
        self.assertIsNone(error)
        self.assertEqual(items,self.items)
        self.assertEqual(effective["_feedCache"]["etag"],'"v2"')
        self.assertIsNotNone(collector.reusable_feed_cache(self.source,effective["_feedCache"],self.now,"parser"))

    def test_source_attempt_records_304_without_changing_publication_date(self):
        import urllib.error
        err = urllib.error.HTTPError(self.source["url"],304,"Not Modified",{},None)
        with patch.object(collector.urllib.request,"urlopen",side_effect=err):
            effective, items, error = collector.fetch_source(self.source,now=self.now,feed_state=self.cache,parser_revision="parser")
        self.assertIsNone(error)
        self.assertEqual(items,self.items)
        self.assertTrue(effective["attempts"][0]["httpNotModified"])
        self.assertEqual(effective["attempts"][0]["representationFetchedAt"],self.cache["downloadedAt"])
        self.assertEqual(items[0]["publishedAt"],"2026-11-27T00:00:00Z")

class HardSourceDeadlineTests(unittest.TestCase):
    def test_only_configured_source_is_isolated_and_timeout_is_not_success(self):
        from datetime import datetime, timezone
        import subprocess
        from unittest.mock import Mock
        source = {"id":"zhipu","name":"Zhipu","url":"https://example.com/news","hardDeadlineSeconds":18}
        now = datetime(2026,11,28,tzinfo=timezone.utc)
        runner = Mock(side_effect=subprocess.TimeoutExpired("worker",18))
        effective, items, error = collector.fetch_with_hard_deadline(source,{},now,None,None,None,runner)
        self.assertEqual(items,[])
        self.assertIn("SourceDeadlineExceeded",error)
        self.assertEqual(effective["attempts"][0]["budgetSeconds"],18)
        self.assertFalse(effective["sourceDeferred"])
        self.assertEqual(runner.call_args.kwargs["timeout"],18)
        self.assertEqual(runner.call_args.args[0][-1],"--isolated-source-worker")
        with patch.object(collector,"fetch_source",return_value=(source,[],None)) as normal:
            collector.fetch_with_hard_deadline({"id":"other"},None,now,None,None,None,runner)
        normal.assert_called_once()
        self.assertEqual(runner.call_count,1)

    def test_isolated_success_preserves_actual_evidence_and_attempts(self):
        from datetime import datetime, timezone
        import json
        from types import SimpleNamespace
        from unittest.mock import Mock
        source = {"id":"zhipu","name":"Zhipu","url":"https://example.com/news","hardDeadlineSeconds":18}
        result = [{**source,"attempts":[{"url":source["url"],"error":None}]},[{"title":"GLM 5","publishedAt":"2026-11-01T00:00:00Z"}],None]
        runner=Mock(return_value=SimpleNamespace(stdout=json.dumps(result)))
        actual=collector.fetch_with_hard_deadline(source,None,datetime.now(timezone.utc),None,None,None,runner)
        self.assertEqual(list(actual),result)

    def test_bounded_retry_moves_to_fallback_without_sleep(self):
        source={"id":"zhipu","name":"Zhipu","url":"https://example.com/news",
                "fallbackUrls":["https://example.com/research"],"maxTransientAttempts":1}
        with patch.object(collector,"fetch_source_once",side_effect=[
            (source,[],"URLError: timed out"),(source,[{"title":"GLM 5"}],None)]) as fetch, patch.object(collector.time,"sleep") as sleep:
            effective, items, error = collector.fetch_source(source)
        self.assertIsNone(error)
        self.assertEqual(fetch.call_count,2)
        self.assertEqual(effective["url"],source["fallbackUrls"][0])
        sleep.assert_not_called()

    def test_real_process_deadline_kills_slow_response(self):
        from datetime import datetime, timezone
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        import time
        class SlowHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                time.sleep(3)
            def log_message(self,*args):
                pass
        server=ThreadingHTTPServer(("127.0.0.1",0),SlowHandler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            source={"id":"slow","name":"Slow","url":f"http://127.0.0.1:{server.server_port}/",
                    "hardDeadlineSeconds":1,"requestTimeoutSeconds":10}
            started=time.monotonic()
            effective, items, error=collector.fetch_with_hard_deadline(source,None,datetime.now(timezone.utc),None,None,None)
            self.assertLess(time.monotonic()-started,3)
            self.assertIn("SourceDeadlineExceeded",error)
            self.assertEqual(items,[])
        finally:
            server.shutdown()
            server.server_close()
