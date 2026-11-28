import unittest
import urllib.error
from datetime import datetime, timezone, timedelta
from scripts.collect_resources import discover_repos, candidate_repo, repo_identity, observed_stars

from scripts.collect_resources import parse_feed_bytes


class ResourceFeedTests(unittest.TestCase):
    def test_goodcase_rss_extracts_case_author_prompt_and_image(self):
        body = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>MiniMax H3 Image product portrait</title>
              <link>https://goodcase.ai/cases/example</link>
              <guid>https://goodcase.ai/cases/example</guid>
              <pubDate>Sat, 21 Nov 2026 22:01:12 GMT</pubDate>
              <description><![CDATA[aiwithaly：MiniMax H3 Image 的人像案例。Prompt 预览：Create a cinematic portrait with natural window light.]]></description>
              <enclosure url="opengraph-image" type="image/png"/>
            </item>
          </channel>
        </rss>""".encode("utf-8")
        source = {
            "id": "goodcase",
            "name": "GoodCase.ai",
            "url": "https://goodcase.ai/feed.xml",
            "category": "cases",
        }
        items = parse_feed_bytes(body, source, "2026-11-22T00:00:00Z")
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["title"], "MiniMax H3 Image product portrait")
        self.assertEqual(item["creator"], "aiwithaly")
        self.assertIn("人像案例", item["summary"])
        self.assertEqual(item["promptPreview"], "Create a cinematic portrait with natural window light.")
        self.assertEqual(item["imageUrl"], "https://goodcase.ai/cases/example/opengraph-image")
        self.assertEqual(item["publishedAt"], "2026-11-21T22:01:12Z")
        self.assertEqual(item["url"], "https://goodcase.ai/cases/example")

    def test_news_rss_preserves_original_link_and_description(self):
        body = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>AI Brief 2026-11-22</title>
              <link>https://daily.example/brief-2026-11-22</link>
              <guid>brief-2026-11-22</guid>
              <pubDate>Sun, 22 Nov 2026 00:54:18 GMT</pubDate>
              <description><![CDATA[Today's AI news summary. Read the original sources.]]></description>
            </item>
          </channel>
        </rss>""".encode("utf-8")
        source = {
            "id": "juya-daily",
            "name": "橘鸦 AI 早报",
            "url": "https://daily.juya.uk/rss.xml",
            "category": "news",
        }
        items = parse_feed_bytes(body, source, "2026-11-22T01:00:00Z")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["category"], "news")
        self.assertEqual(items[0]["url"], "https://daily.example/brief-2026-11-22")
        self.assertEqual(items[0]["summary"], "Today's AI news summary. Read the original sources.")
        self.assertIsNone(items[0]["promptPreview"])


class ResearchRadarTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,28,12,tzinfo=timezone.utc)
        self.payload={"full_name":"maker/whitebox","html_url":"https://github.com/maker/whitebox",
                      "description":"AI video storyboard and camera control","topics":["ai-video"],
                      "archived":False,"fork":False,"private":False,"stargazers_count":3,
                      "pushed_at":"2026-11-27T00:00:00Z","license":{"spdx_id":"MIT"}}

    def test_selected_pointer_first_then_scoped_search(self):
        snap={"items":[{"selected":True,"title":"AI video storyboard","publishedAt":"2026-11-27T00:00:00Z",
                        "links":{"original":"https://github.com/maker/whitebox"}}]}
        calls=[]
        def lookup(url):
            calls.append(url)
            return self.payload
        first=discover_repos([("AIHOT",snap)],{},[],self.now,lookup,lambda *_:self.fail("no search before pointer"))
        self.assertEqual(calls,["https://api.github.com/repos/maker/whitebox"])
        self.assertEqual(first["items"][0]["provider"],"AIHOT")
        self.assertNotIn("observedStarChange",first["items"][0])
        def search(q,now):
            self.assertTrue(q.startswith("topic:"))
            return [{**self.payload,"stargazers_count":5}]
        later=discover_repos([("AIHOT",snap)],first,[],self.now+timedelta(hours=6),lambda *_:self.fail("duplicate pointer"),search)
        self.assertEqual(len(later["items"]),1)
        self.assertEqual(later["items"][0]["observedStarChange"]["delta"],2)
        self.assertEqual(later["nextLane"],1)

    def test_selected_pointer_transient_failure_retries_after_backoff(self):
        snap={"items":[{"selected":True,"title":"AI video storyboard","publishedAt":"2026-11-27T00:00:00Z",
                        "links":{"original":"https://github.com/maker/whitebox"}}]}
        def fail(url):
            raise urllib.error.HTTPError(url,429,"rate limit",None,None)
        first=discover_repos([("AIHOT",snap)],{},[],self.now,fail,lambda *_:self.fail("unexpected search"))
        self.assertEqual(first["status"],"cached")
        self.assertEqual(first["recentPointerAttempts"],[])
        later=discover_repos([("AIHOT",snap)],first,[],self.now+timedelta(hours=6),
                            lambda _:self.payload,lambda *_:self.fail("pointer was lost"))
        self.assertEqual(later["items"][0]["provider"],"AIHOT")
        self.assertEqual(later["recentPointerAttempts"],["maker/whitebox"])

    def test_missing_pointer_does_not_block_next_search(self):
        snap={"items":[{"selected":True,"title":"AI video storyboard","publishedAt":"2026-11-27T00:00:00Z",
                        "links":{"original":"https://github.com/maker/whitebox"}}]}
        def missing(url):
            raise urllib.error.HTTPError(url,404,"not found",None,None)
        first=discover_repos([("AIHOT",snap)],{},[],self.now,missing,lambda *_:self.fail("extra request"))
        self.assertEqual(first["status"],"ok")
        self.assertEqual(first["items"],[])
        self.assertEqual(first["recentPointerAttempts"],["maker/whitebox"])
        later=discover_repos([("AIHOT",snap)],first,[],self.now+timedelta(hours=6),
                            lambda _:self.fail("terminal pointer"),lambda *_:[])
        self.assertEqual(later["lastProvider"],"GitHub Search")

    def test_selected_attribution_upgrades_search_and_survives_refresh(self):
        first=discover_repos([],{},[],self.now,searcher=lambda *_:[self.payload])
        snap={"items":[{"selected":True,"title":"AI video storyboard","publishedAt":"2026-11-27T00:00:00Z",
                        "links":{"original":"https://github.com/maker/whitebox"}}]}
        second=discover_repos([("AIPick",snap)],first,[],self.now+timedelta(hours=6),
                             lambda _:self.payload,lambda *_:self.fail("selected pointer should upgrade source"))
        self.assertEqual(second["items"][0]["provider"],"AIPick")
        third=discover_repos([],second,[],self.now+timedelta(hours=12),searcher=lambda *_:[self.payload])
        self.assertEqual(third["items"][0]["provider"],"AIPick")
        self.assertEqual(third["items"][0]["lastMetadataProvider"],"GitHub Search")
        self.assertEqual(third["items"][0]["firstObservedAt"],first["items"][0]["firstObservedAt"])

    def test_reject_noncreative_and_invalid_repositories(self):
        for x in ({**self.payload,"description":"General LLM framework","topics":["llm"]},
                  {**self.payload,"archived":True},{**self.payload,"fork":True},
                  {**self.payload,"html_url":"https://github.com.evil.test/maker/whitebox"},
                  {**self.payload,"pushed_at":"2026-10-01T00:00:00Z"}):
            self.assertIsNone(candidate_repo(x,"GitHub Search",self.now))
        for url in ("https://github.com/topics/ai-video","https://github.com/maker/whitebox/issues/1","http://github.com/maker/whitebox"):
            self.assertIsNone(repo_identity(url))

    def test_rate_limit_preserves_metadata_and_observation_dates(self):
        first=discover_repos([],{},[],self.now,searcher=lambda *_:[self.payload])
        def fail(*_):
            raise OSError("429")
        later=discover_repos([],first,[],self.now+timedelta(hours=6),searcher=fail)
        self.assertEqual(later["status"],"cached")
        self.assertEqual(later["items"],first["items"])
        deferred=discover_repos([],later,[],self.now+timedelta(hours=7),searcher=lambda *_:self.fail("backoff"))
        self.assertTrue(deferred["deferred"])
        self.assertEqual(deferred["items"],first["items"])


if __name__ == "__main__":
    unittest.main()
