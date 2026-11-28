import json
import unittest
from datetime import datetime, timezone
from scripts.collect_cross_platform import article_url, feed_leads, hf_leads, collect


class CrossPlatformTests(unittest.TestCase):
    def setUp(self):
        self.source = {"id":"test","name":"Demo","url":"https://example.org/feed"}
        self.allowed = {"www.anthropic.com":["/news/","/claude-"]}
        self.now = datetime(2026,11,26,tzinfo=timezone.utc)

    def test_external_rss_is_unverified_and_rejects_lookalike_hosts(self):
        xml = b'<rss><channel><item><title>Introducing Claude 5</title><link>https://example.org/news/5</link><description>https://www.anthropic.com/news/claude-5 https://www.anthropic.com.evil.test/news/x</description><pubDate>Thu, 26 Nov 2026 00:00:00 GMT</pubDate></item></channel></rss>'
        rows = feed_leads(xml,self.source,self.allowed)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["officialArticleUrls"],["https://www.anthropic.com/news/claude-5"])
        self.assertEqual(rows[0]["verificationStatus"],"unverified-lead")
        self.assertNotIn("publishedAt",rows[0])

    def test_repository_creation_does_not_become_release_date(self):
        src = dict(self.source,author="zai-org")
        rows = hf_leads(json.dumps([{"id":"zai-org/GLM-5","createdAt":"2026-11-25T00:00:00Z"},
                         {"id":"other/GLM-5","createdAt":"2026-11-25T00:00:00Z"}]),src)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["dateKind"],"repository-created-at")
        self.assertNotIn("publishedAt",rows[0])

    def test_failed_sources_keep_previous_without_refreshing_last_seen(self):
        row = {"id":"old","sourceId":"test","title":"Claude 5","url":"https://example.org/x",
               "reportedAt":"2026-11-25","firstSeenAt":"2026-11-25","lastSeenAt":"2026-11-25",
               "officialArticleUrls":[]}
        config={"sources":[self.source],"officialArticleHosts":self.allowed}
        result=collect(config,{"items":[row]},self.now,lambda s,a:(s,[],"HTTP 403"))
        self.assertEqual(result["items"],[row])
        self.assertEqual(result["sources"][0]["error"],"HTTP 403")

    def test_future_dates_and_old_uploads_are_not_recent_leads(self):
        def fake(s,a):
            return s,[{"title":"Claude 5","sourceId":"test","url":"https://example.org/1","reportedAt":"2026-12-01"},
                      {"title":"Claude 4","sourceId":"test","url":"https://example.org/2","reportedAt":"2026-01-01"}],None
        result=collect({"sources":[self.source],"officialArticleHosts":self.allowed},{},self.now,fake)
        self.assertEqual(result["items"],[])

    def test_invalid_or_generic_article_urls_are_rejected(self):
        for url in ("http://www.anthropic.com/news/x","https://www.anthropic.com.evil.test/news/x",
                    "https://www.anthropic.com/news/","https://www.anthropic.com:444/news/x",
                    "https://user@www.anthropic.com/news/x"):
            self.assertEqual(article_url(url,self.allowed),"")

    def test_repeated_failure_cools_only_failed_source_and_alternative_continues(self):
        from datetime import timedelta
        alternative={"id":"alternative","name":"Alternative","url":"https://example.org/other"}
        config={"sources":[self.source,alternative],"officialArticleHosts":self.allowed}
        calls=[]
        def fetch(s,a):
            calls.append(s["id"])
            return s,[], "HTTP 403" if s["id"]=="test" else None
        first=collect(config,{},self.now,fetch)
        self.assertEqual(calls,["test","alternative"])
        second=collect(config,first,self.now+timedelta(days=1),fetch)
        failed=next(s for s in second["sources"] if s["id"]=="test")
        self.assertEqual(failed["consecutiveFailures"],2)
        self.assertEqual(datetime.fromisoformat(failed["nextAttemptAt"]),self.now+timedelta(days=8))
        calls.clear()
        third=collect(config,second,self.now+timedelta(days=2),fetch)
        self.assertEqual(calls,["alternative"])
        self.assertTrue(next(s for s in third["sources"] if s["id"]=="test")["deferred"])

    def test_http_retry_after_preserved_across_runs(self):
        from datetime import timedelta
        from email.utils import format_datetime
        from urllib.error import HTTPError
        from unittest.mock import patch
        from scripts.collect_cross_platform import fetch
        source = dict(self.source, type="rss")
        config = {"sources":[source],"officialArticleHosts":self.allowed}
        until = self.now + timedelta(days=9)
        for value in (str(9 * 86400), format_datetime(until, usegmt=True)):
            error = HTTPError(source["url"], 429, "Too Many Requests", {"Retry-After":value}, None)
            with patch("scripts.collect_cross_platform.urllib.request.build_opener") as opener:
                opener.return_value.open.side_effect = error
                first = collect(config, {}, self.now, fetch)
                self.assertIn("429", first["sources"][0]["error"])
                self.assertEqual(datetime.fromisoformat(first["sources"][0]["nextAttemptAt"]), until)
                second = collect(config, first, self.now + timedelta(days=2), fetch)
                self.assertTrue(second["sources"][0]["deferred"])
                self.assertEqual(opener.return_value.open.call_count, 1)
