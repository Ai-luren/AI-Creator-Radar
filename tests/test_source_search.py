import unittest
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from scripts.collect_source_search import build_targets, parse_results, search, augment_discovery
from scripts.collect_event_reconciliation import reconcile

class SourceSearchTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 27, tzinfo=timezone.utc)
        self.families = [{"id":"demo","versions":[{"id":"v3","name":"Demo v3"},{"id":"v3-live","name":"Demo v3 Live"}]}]
        self.discovery = {"items":[{"id":"lead","sourceId":"feed","title":"Demo v3 launched","officialArticleUrls":[],
                                    "firstSeenAt":"2026-11-26T00:00:00Z"}]}
        self.allowed = {"official.example":["/blog/"]}
        self.target = next(iter(build_targets(self.families,self.discovery,{},{}).values()))

    def run_search(self, old=None, hours=0, fetcher=lambda *args: []):
        return search(self.families,self.discovery,{}, {},old or {},self.allowed,
                      self.now+timedelta(hours=hours),fetcher)

    def test_build_targets_does_not_guess_unknown_headlines(self):
        rows = {"items":self.discovery["items"]+[{"id":"ambiguous","sourceId":"feed","title":"Demo v3 vs Demo v3 Live","officialArticleUrls":[]},
                                                {"id":"upload","sourceId":"hf","title":"Demo v3 Live","dateKind":"repository-created-at"}]}
        self.assertEqual(len(build_targets(self.families,rows,{},{})),1)

    def test_title_variant_and_host_validation(self):
        results = parse_results({"articles":[
            {"title":"Introducing Demo v3","url":"https://official.example/blog/v3","seendate":"20261126T120000Z"},
            {"title":"Demo v3 Live released","url":"https://official.example/blog/live"},
            {"title":"Demo v3 released","url":"https://official.example.evil.test/blog/v3"},
            {"title":"Demo v3 tutorial","url":"https://official.example/blog/tutorial"},
            {"title":"Demo v3 released","url":"http://official.example/blog/v3"}]},
            self.target,self.allowed,self.families)
        self.assertEqual(len(results),2)
        self.assertEqual(sum(bool(r["officialCandidateUrl"]) for r in results),1)
        self.assertNotIn("publishedAt",results[0])

    def test_single_request_budget_and_cooldown(self):
        calls=[]
        def fetch(*args):
            calls.append(args[0]["id"])
            return []
        first=self.run_search(fetcher=fetch)
        second=self.run_search(first,hours=1,fetcher=fetch)
        self.assertEqual(len(calls),1)
        self.assertEqual(second["summary"]["attemptedThisRun"],0)
        self.assertEqual(second["summary"]["targetStates"],{"no-matching-index-results":1})

    def test_429_is_global_backoff_not_source_failure_erasure(self):
        def fail(*args):
            raise HTTPError("https://api.gdeltproject.org/",429,"rate limit",{},None)
        first=self.run_search(fetcher=fail)
        self.assertIsNotNone(first["summary"]["indexError"])
        second=self.run_search(first,hours=1,fetcher=lambda *args: self.fail("should defer"))
        self.assertEqual(second["summary"]["attemptedThisRun"],0)
        self.assertEqual(second["summary"]["targetStates"],{"index-unavailable":1})
        self.assertIsNone(second["summary"]["indexLastSuccessAt"])

    def test_candidate_provenance_and_date_semantics(self):
        results=parse_results({"articles":[{"title":"Demo v3 released","url":"https://official.example/blog/v3",
                                           "seendate":"20261126T120000Z"}]},self.target,self.allowed,self.families)
        first=self.run_search(fetcher=lambda *args: results)
        merged=augment_discovery(self.discovery,first)
        self.assertEqual(merged["items"][0],self.discovery["items"][0])
        candidate=merged["items"][1]
        self.assertEqual(candidate["sourceId"],"gdelt-doc")
        self.assertIsNone(candidate["reportedAt"])
        self.assertEqual(candidate["dateKind"],"index-observed-only")
        self.assertEqual(len(augment_discovery(merged,first)["items"]),2)

    def test_old_results_survive_index_outage(self):
        results=parse_results({"articles":[{"title":"Demo v3 released","url":"https://official.example/blog/v3"}]},
                              self.target,self.allowed,self.families)
        first=self.run_search(fetcher=lambda *args:results)
        def fail(*args):
            raise OSError("403")
        second=self.run_search(first,hours=25,fetcher=fail)
        self.assertEqual(second["targets"][0]["results"],first["targets"][0]["results"])
        self.assertEqual(second["summary"]["indexLastSuccessAt"],first["summary"]["indexLastSuccessAt"])


    def test_blocked_index_still_associates_existing_evidence_without_promoting(self):
        evidence = {"id":"old-proof","claimType":"catalog-release","modelFamilyId":"demo","modelVersionId":"v3",
                    "sourceUrl":"https://official.example/blog/old","assertedDate":"2026-10-01",
                    "originalVerificationAt":"2026-10-02","datePrecision":"day"}
        ledger = {"evidence":[evidence]}
        products = {"sources":[{"id":"registry","url":"https://registry.example/api","lastSuccessAt":"2026-11-26T12:00:00Z",
                                "entries":{"demo|v3":{"product":{"name":"Demo v3"},"missingChecks":0},
                                           "demo|live":{"product":{"name":"Demo v3 Live"},"missingChecks":0}}}]}
        def fail(*args):
            raise HTTPError("https://api.gdeltproject.org/",429,"rate limit",{},None)
        result = search(self.families,self.discovery,ledger,products,{},self.allowed,self.now,fail)
        context = result["targets"][0]["localContext"]
        self.assertEqual({r["kind"] for r in context},{"catalog-release","catalog-listing-observed"})
        self.assertEqual(result["summary"]["targetsWithLocalContext"],1)
        self.assertEqual(result["summary"]["officialCandidates"],0)
        self.assertEqual(augment_discovery(self.discovery,result),self.discovery)
        state = reconcile(self.families,self.discovery,{},[],{},self.now,products,result)
        self.assertEqual(state["tasks"][0]["state"],"needs-source")
        self.assertEqual(state["tasks"][0]["sourceSearch"]["status"],"index-unavailable")
        self.assertEqual(state["tasks"][0]["sourceSearch"]["localContextKinds"]["catalog-release"],1)

class PublisherChannelPointerTests(unittest.TestCase):
    def test_social_and_wechat_are_context_not_evidence(self):
        from scripts.collect_source_search import local_context
        from scripts.event_identity import model_index
        families=[{"id":"demo","versions":[{"id":"v3","name":"Demo v3"}]}]
        target={"identity":{"modelFamilyId":"demo","modelVersionId":"v3"}}
        urls=["https://x.com/demo/status/1234567890123456789",
              "https://mp.weixin.qq.com/s/Abcdef012345",
              "https://x.com.evil.example/demo/status/1234567890123456789",
              "https://x.com/demo"]
        discovery={"items":[{"id":str(i),"title":"Demo v3 released","sourceId":"feed","url":url,
                             "firstSeenAt":"2026-11-27T00:00:00Z"} for i,url in enumerate(urls)]}
        rows=local_context(target,discovery,{}, {},model_index(families),{})
        self.assertEqual({r["sourceUrl"] for r in rows},set(urls[:2]))
        self.assertTrue(all(r["kind"]=="publisher-channel-pointer-unverified" and r["assertedDate"] is None
                            and r["originalVerificationAt"] is None for r in rows))
