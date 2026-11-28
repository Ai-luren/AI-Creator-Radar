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

    def test_new_model_name_from_exact_repository_and_independent_briefing(self):
        repo = {"id":"repo","sourceId":"hf-inclusionai","title":"inclusionAI/Ming-Image-0.2-Design",
                "url":"https://huggingface.co/inclusionAI/Ming-Image-0.2-Design","dateKind":"repository-created-at",
                "reportedAt":"2026-11-25T00:00:00Z","firstSeenAt":"2026-11-26T00:00:00Z"}
        lead = {"id":"new","sourceId":"local-aihot-daily","title":"蚂蚁开源 Ming-Image-0.2-Design 图像模型",
                "officialArticleUrls":[],"firstSeenAt":"2026-11-26T00:00:00Z"}
        calls=[]
        result=search(self.families,{"items":[repo,lead]}, {}, {},{},self.allowed,self.now,
                      lambda target,*a:calls.append(target["query"]) or [])
        self.assertEqual(calls,["Ming-Image-0.2-Design"])
        target=result["targets"][0]
        self.assertIsNone(target["identity"])
        self.assertEqual(target["localContext"][0]["kind"],"repository-pointer-unverified")
        self.assertIsNone(target["localContext"][0]["assertedDate"])
        for rows in ([lead], [repo], [repo,dict(lead,title="Ming-Image-0.2-Design-Layer 发布")],
                     [dict(repo,url="https://huggingface.co/other/Ming-Image-0.2-Design"),lead]):
            self.assertEqual(build_targets(self.families,{"items":rows},{},{}),{})

    def test_repository_backed_unknown_uses_aggregators_before_broad_search(self):
        from scripts.collect_source_search import parse_aihot_pointers
        name = "Ming-Image-0.2-Design"
        repo = {"id":"repo","sourceId":"hf-inclusionai","title":"inclusionAI/"+name,
                "url":"https://huggingface.co/inclusionAI/"+name,"dateKind":"repository-created-at",
                "firstSeenAt":"2026-11-26T00:00:00Z"}
        lead = {"id":"lead","sourceId":"local-aihot-daily","title":name+" 发布",
                "firstSeenAt":"2026-11-26T00:00:00Z","officialArticleUrls":[]}
        discovery = {"items":[repo,lead]}
        calls = []
        def primary(target, allowed, families, etag):
            calls.append(target["query"])
            payload = {"items":[{"category":"ai-models","title":name+" 发布",
                       "links":{"original":"https://official.example/blog/design","aihot":"https://aihot.news/items/design"}},
                      {"category":"ai-models","title":name+"-Layer 发布",
                       "links":{"original":"https://official.example/blog/layer","aihot":"https://aihot.news/items/layer"}}]}
            return parse_aihot_pointers(payload,target,allowed,families), '"etag"'
        result = search(self.families,discovery,{}, {},{},self.allowed,self.now,
                        lambda *a:self.fail("broad index before aggregator"),aihot_fetcher=primary)
        self.assertEqual(calls,[name])
        self.assertEqual(result["summary"]["attemptedThisRun"],1)
        self.assertEqual(result["summary"]["aihotAttemptedThisRun"],1)
        target = result["targets"][0]
        self.assertTrue(target["repositoryBacked"])
        self.assertIsNone(target["identity"])
        self.assertEqual([r["officialCandidateUrl"] for r in target["results"]],["https://official.example/blog/design"])
        self.assertNotIn("publishedAt",target["results"][0])

    def test_curated_exact_original_repository_link_does_not_require_full_vendor_listing(self):
        name = "Nemotron-Labs-Image-30B-A3B"
        lead = {"id":"direct","sourceId":"local-juya-daily","title":"NVIDIA 开放 "+name,
                "url":"https://huggingface.co/nvidia/"+name,"officialArticleUrls":[],
                "reportedAt":"2026-11-26","firstSeenAt":"2026-11-26T02:00:00Z"}
        calls=[]
        result=search(self.families,{"items":[lead]}, {}, {},{},self.allowed,self.now,
                      lambda *a:self.fail("broad before aggregate"),
                      aihot_fetcher=lambda t,*a:(calls.append(t["query"]) or [],"etag"))
        self.assertEqual(calls,[name])
        target=result["targets"][0]
        self.assertTrue(target["repositoryBacked"])
        self.assertIsNone(target["identity"])
        self.assertEqual(target["localContext"][0]["sourceUrl"],lead["url"])
        self.assertIsNone(target["localContext"][0]["assertedDate"])
        self.assertIsNone(target["localContext"][0]["originalVerificationAt"])
        self.assertEqual(augment_discovery({"items":[lead]},result),{"items":[lead]})
        for wrong in (dict(lead,url=lead["url"]+"/tree/main"),
                      dict(lead,url="https://huggingface.co.evil.test/nvidia/"+name),
                      dict(lead,url="https://huggingface.co/nvidia/"+name+"-Other"),
                      dict(lead,title=lead["title"]+"-Other"),
                      dict(lead,sourceId="untrusted-feed")):
            self.assertEqual(build_targets(self.families,{"items":[wrong]},{},{}),{})
        competing = dict(lead,id="other",url="https://huggingface.co/other/"+name)
        self.assertEqual(build_targets(self.families,{"items":[lead,competing]},{},{}),{})

    def test_distinct_fresh_report_with_old_detection_does_not_bypass_aggregators(self):
        lead = dict(self.discovery["items"][0],reportedAt="2026-11-27",
                    firstSeenAt="2026-10-01T00:00:00Z")
        previous={"schema":"source-search/v1","targets":[],
                  "aihotService":{"nextAttemptAt":(self.now+timedelta(minutes=10)).isoformat(),"error":None}}
        result=search(self.families,{"items":[lead]}, {}, {},previous,self.allowed,self.now,
                      lambda *a:self.fail("broad index during normal aggregate cooldown"),
                      aihot_fetcher=lambda *a:self.fail("aggregate cooldown"))
        self.assertEqual(result["summary"]["attemptedThisRun"],0)
        self.assertEqual(result["summary"]["broadDeferredForAggregators"],1)
        self.assertEqual(result["targets"][0]["priorityDay"],"2026-11-27")
        self.assertEqual(result["targets"][0]["firstDetectedAt"],lead["firstSeenAt"])

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

    def test_historical_target_kept_without_index_requests(self):
        old_discovery = {"items":[dict(self.discovery["items"][0], firstSeenAt="2026-09-01T00:00:00Z")]}
        result = search(self.families,old_discovery,{}, {},{},self.allowed,self.now,lambda *a:self.fail("historical query"))
        self.assertEqual(result["summary"]["attemptedThisRun"],0)
        self.assertEqual(len(result["targets"]),1)
        self.assertTrue(result["targets"][0]["active"])

    def test_recent_target_precedes_older_due_target(self):
        leads = {"items":self.discovery["items"]+[dict(self.discovery["items"][0],id="older",title="Demo v3 Live launched",firstSeenAt="2026-11-08T00:00:00Z")]}
        calls = []
        search(self.families,leads,{}, {},{},self.allowed,self.now,lambda target,*a:calls.append(target["query"]) or [])
        self.assertEqual(calls,["Demo v3"])

    def test_three_day_priority_and_no_eight_day_index_polling(self):
        leads = {"items":self.discovery["items"]+[dict(self.discovery["items"][0],id="week",title="Demo v3 Live launched",firstSeenAt="2026-11-22T00:00:00Z")]}
        calls = []
        search(self.families,leads,{}, {},{},self.allowed,self.now,lambda target,*a:calls.append(target["query"]) or [])
        self.assertEqual(calls,["Demo v3"])
        later = search(self.families,self.discovery,{}, {},{},self.allowed,self.now+timedelta(days=8),lambda *a:self.fail("old index request"))
        self.assertEqual(later["summary"]["attemptedThisRun"],0)

    def test_recent_rediscovery_does_not_make_old_report_or_repository_fresh(self):
        old = dict(self.discovery["items"][0], reportedAt="2026-11-04T00:00:00Z")
        ledger = {"tasks":[{"id":"oldtask","taskType":"lead-review","state":"needs-source",
                            "identity":{"modelFamilyId":"demo","modelVersionId":"v3"},
                            "reportedDay":"2026-11-04","firstDetectedAt":self.now.isoformat()},
                           {"id":"repo","taskType":"independent-repository","state":"needs-repository-identity",
                            "modelName":"Demo v9","repositoryCreatedAt":"2026-11-06T00:00:00Z",
                            "firstDetectedAt":self.now.isoformat()}]}
        products = {"events":[{"id":"product","eventType":"added-to-catalog","product":{"name":"Demo v8","reportedReleaseDate":"2026-09-22"},
                               "observedAt":self.now.isoformat()}]}
        result=search(self.families,{"items":[old]},ledger,products,{},self.allowed,self.now,
                      lambda *a:self.fail("historical broad request"),
                      aihot_fetcher=lambda *a:self.fail("historical AIHOT request"),
                      aipick_fetcher=lambda *a:self.fail("historical AIPick request"))
        self.assertEqual(result["summary"]["attemptedThisRun"],0)
        self.assertEqual(result["summary"]["priorityTargetCounts"]["outsideHotWindowOrUnknown"],3)
        self.assertEqual({t["priorityDay"] for t in result["targets"]},{"2026-11-04","2026-11-06","2026-09-22"})
        self.assertTrue(all(t["active"] for t in result["targets"]))

    def test_distinct_recent_report_reopens_priority_without_resetting_first_detection(self):
        old = dict(self.discovery["items"][0], reportedAt="2026-11-04", firstSeenAt="2026-11-04T00:00:00Z")
        fresh = dict(old,id="fresh",reportedAt="2026-11-27",firstSeenAt=self.now.isoformat())
        second = dict(old,id="week",title="Demo v3 Live launched",reportedAt="2026-11-22",firstSeenAt=self.now.isoformat())
        calls=[]
        result=search(self.families,{"items":[old,fresh,second]}, {}, {},{},self.allowed,self.now,
                      lambda *a:self.fail("broad before AIHOT"),
                      aihot_fetcher=lambda t,*a:(calls.append(t["query"]) or [],"etag"))
        self.assertEqual(calls,["Demo v3"])
        target=next(t for t in result["targets"] if t["query"]=="Demo v3")
        self.assertEqual(target["priorityDay"],"2026-11-27")
        self.assertEqual(target["firstDetectedAt"],old["firstSeenAt"])
        self.assertEqual(result["summary"]["priorityTargetCounts"],{"latestThreeDays":1,"remainingSevenDays":1,"outsideHotWindowOrUnknown":0})

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

class AIHOTTargetedTests(unittest.TestCase):
    setUp=SourceSearchTests.setUp
    run_search=SourceSearchTests.run_search
    def payload(self):
        return {"items":[
            {"category":"ai-models","title":"Demo v3 released","summary":"Never retain this summary",
             "links":{"original":"https://official.example/blog/v3","aihot":"https://aihot.news/items/demo"}},
            {"category":"ai-models","title":"Demo v3 Live released","links":{"original":"https://official.example/blog/live","aihot":"https://aihot.news/items/live"}},
            {"category":"tip","title":"Demo v3 tutorial","links":{"original":"https://official.example/blog/tutorial","aihot":"https://aihot.news/items/tutorial"}},
            {"category":"ai-models","title":"Demo v3 released","links":{"original":"https://official.example.evil.test/blog/v3","aihot":"https://aihot.news/items/fake"}},
            {"category":"ai-models","title":"Demo v3 released","links":{"original":"https://official.example/blog/another","aihot":"https://evil.example/items/fake"}}]}

    def test_targeted_fallback_is_bounded_and_does_not_copy_aihot_text(self):
        from scripts.collect_source_search import parse_aihot_pointers
        from datetime import timedelta
        old=self.run_search(fetcher=lambda *a:(_ for _ in ()).throw(HTTPError("https://api.gdeltproject.org/",429,"limit",{},None)))
        calls=[]
        def aihot(target,allowed,families,etag):
            calls.append(target["query"])
            return parse_aihot_pointers(self.payload(),target,allowed,families),'"etag"'
        result=search(self.families,self.discovery,{}, {},old,self.allowed,self.now+timedelta(minutes=5),
                      lambda *args:self.fail("GDELT cooldown"),aihot_fetcher=aihot)
        self.assertEqual(calls,["Demo v3"])
        self.assertEqual(result["summary"]["attemptedThisRun"],1)
        self.assertEqual(result["summary"]["aihotAttemptedThisRun"],1)
        self.assertEqual(result["summary"]["aihotPointers"],1)
        row=result["targets"][0]["results"][0]
        self.assertEqual(row["title"],"Demo v3")
        self.assertNotIn("summary",row)
        self.assertIsNone(row["indexSeenAt"])
        candidate=augment_discovery(self.discovery,result)["items"][-1]
        self.assertEqual(candidate["sourceId"],"aihot-targeted")
        self.assertIsNone(candidate["reportedAt"])
        self.assertEqual(candidate["discoveryPointer"],"https://aihot.news/items/demo")
        second=search(self.families,self.discovery,{}, {},result,self.allowed,self.now+timedelta(minutes=10),
                      lambda *args:self.fail("GDELT cooldown"),aihot_fetcher=lambda *args:self.fail("AIHOT cooldown"))
        self.assertEqual(second["summary"]["attemptedThisRun"],0)

    def test_short_display_label_uses_exact_full_registered_name(self):
        families=[{"id":"demo","versions":[{"id":"v3","name":"3","releaseEvidence":{"modelName":"Demo v3"}}]}]
        self.assertEqual(next(iter(build_targets(families,self.discovery,{},{}).values()))["query"],"Demo v3")

    def test_aihot_retry_after_and_no_new_pointers_on_failure(self):
        from datetime import timedelta
        old=self.run_search(fetcher=lambda *a:(_ for _ in ()).throw(HTTPError("https://api.gdeltproject.org/",429,"limit",{},None)))
        def deny(*args):
            raise HTTPError("https://aihot.news/",429,"limit",{"Retry-After":"86400"},None)
        result=search(self.families,self.discovery,{}, {},old,self.allowed,self.now+timedelta(minutes=5),
                      lambda *args:self.fail("GDELT cooldown"),aihot_fetcher=deny)
        self.assertEqual(result["summary"]["aihotPointers"],0)
        self.assertEqual(result["aihotService"]["nextAttemptAt"],(self.now+timedelta(days=1,minutes=5)).isoformat())
        self.assertIsNone(result["summary"]["aihotLastSuccessAt"])


    def test_primary_aggregation_precedes_generic_index_and_secondary_fills_gap(self):
        from scripts.collect_source_search import parse_aihot_pointers
        calls=[]
        def primary(target,allowed,families,etag):
            calls.append("aihot")
            return [],"primary"
        def secondary(target,allowed,families,etag):
            calls.append("aipick")
            payload=self.payload()
            for item in payload["items"]:
                item["links"]["aihot"]=item["links"]["aihot"].replace("aihot.news","aipick.news")
            return parse_aihot_pointers(payload,target,allowed,families,"aipick-targeted"),"secondary"
        first=search(self.families,self.discovery,{}, {},{},self.allowed,self.now,
                     lambda *args:self.fail("generic index must not precede primary"),
                     aihot_fetcher=primary,aipick_fetcher=secondary)
        self.assertEqual(calls,["aihot"])
        self.assertEqual(first["summary"]["aihotPointers"],0)
        second=search(self.families,self.discovery,{}, {},first,self.allowed,self.now+timedelta(minutes=35),
                      lambda *args:self.fail("secondary should fill primary gap"),
                      aihot_fetcher=primary,aipick_fetcher=secondary)
        self.assertEqual(calls,["aihot","aipick"])
        self.assertEqual(second["summary"]["aipickPointers"],1)
        candidate=augment_discovery(self.discovery,second)["items"][-1]
        self.assertEqual(candidate["sourceId"],"aipick-targeted")
        self.assertEqual(candidate["attribution"]["name"],"AIPick")
        self.assertIsNone(candidate["reportedAt"])

    def test_aipick_cannot_relabel_aihot_pointer_as_independent(self):
        from scripts.collect_source_search import parse_aihot_pointers
        self.assertEqual(parse_aihot_pointers(self.payload(),next(iter(build_targets(self.families,self.discovery,{},{}).values())),self.allowed,self.families,"aipick-targeted"),[])

class BoundedBroadSearchTests(unittest.TestCase):
    setUp=SourceSearchTests.setUp
    run_search=SourceSearchTests.run_search

    def test_normal_aggregator_cooldown_is_not_permission_to_use_broad_search(self):
        calls=[]
        def primary(*args):
            calls.append("aihot")
            return [],"a"
        def secondary(*args):
            calls.append("aipick")
            return [],"b"
        def broad(*args):
            calls.append("gdelt")
            return []
        old=search(self.families,self.discovery,{}, {},{},self.allowed,self.now,broad,
                   aihot_fetcher=primary,aipick_fetcher=secondary)
        # Simulate a different target with no provider observations during
        # normal successful provider cooldown, not a failed provider.
        other={"items":[{"id":"lead2","sourceId":"feed","title":"Demo v3 Live launched",
                        "officialArticleUrls":[],"firstSeenAt":"2026-11-26T00:00:00Z"}]}
        old["aipickService"]={"lastSuccessAt":self.now.isoformat(),
                              "nextAttemptAt":(self.now+timedelta(minutes=30)).isoformat(),"error":None}
        later=search(self.families,other,{}, {},old,self.allowed,self.now+timedelta(minutes=5),broad,
                     aihot_fetcher=primary,aipick_fetcher=secondary)
        self.assertEqual(calls,["aihot"])
        self.assertEqual(later["summary"]["attemptedThisRun"],0)
        self.assertEqual(later["summary"]["broadDeferredForAggregators"],1)

    def test_actual_gap_after_both_providers_allows_broad_recovery(self):
        calls=[]
        def broad(*args):
            calls.append("gdelt")
            return []
        first=search(self.families,self.discovery,{}, {},{},self.allowed,self.now,broad,
                     aihot_fetcher=lambda *a:([],"a"),aipick_fetcher=lambda *a:([],"b"))
        second=search(self.families,self.discovery,{}, {},first,self.allowed,self.now+timedelta(minutes=5),broad,
                      aihot_fetcher=lambda *a:([],"a"),aipick_fetcher=lambda *a:([],"b"))
        third=search(self.families,self.discovery,{}, {},second,self.allowed,self.now+timedelta(minutes=10),broad,
                     aihot_fetcher=lambda *a:([],"a"),aipick_fetcher=lambda *a:([],"b"))
        self.assertEqual(calls,["gdelt"])
        self.assertEqual(third["summary"]["attemptedThisRun"],1)

    def test_worker_deadline_preserves_previous_success_and_backoff(self):
        import subprocess
        from unittest.mock import Mock
        from scripts.collect_source_search import bounded_broad_fetch, BroadSearchDeadlineExceeded
        runner=Mock(side_effect=subprocess.TimeoutExpired("worker",8))
        with self.assertRaises(BroadSearchDeadlineExceeded):
            bounded_broad_fetch(self.target,self.allowed,self.families,runner)
        self.assertEqual(runner.call_args.kwargs["timeout"],8)
        first=self.run_search(fetcher=lambda *a:[])
        def timed(*args):
            return bounded_broad_fetch(*args,runner=runner)
        second=self.run_search(first,hours=25,fetcher=timed)
        self.assertIn("BroadSearchDeadlineExceeded",second["service"]["error"])
        self.assertEqual(second["service"]["lastSuccessAt"],first["service"]["lastSuccessAt"])
        self.assertGreaterEqual(datetime.fromisoformat(second["service"]["nextAttemptAt"]),
                                self.now+timedelta(hours=31))

    def test_worker_preserves_http_error_and_retry_after(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from scripts.collect_source_search import bounded_broad_fetch
        runner=Mock(return_value=SimpleNamespace(stdout='{"httpError":429,"reason":"limit","retryAfter":"86400"}'))
        result=self.run_search(fetcher=lambda *args: bounded_broad_fetch(*args,runner=runner))
        self.assertIn("429",result["service"]["error"])
        self.assertEqual(result["service"]["nextAttemptAt"],(self.now+timedelta(days=1)).isoformat())
