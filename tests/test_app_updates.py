import unittest
from datetime import datetime, timedelta, timezone
from scripts.collect_app_updates import parse_surface,collect

class AppUpdatesTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,27,tzinfo=timezone.utc)
        self.spec={"id":"app","name":"App","vendor":"Vendor","url":"https://jimeng.jianying.com/ai-tool/home",
                   "anchors":["创作","画布"],"modelPrefixes":["SeedAudio","Seedream","Seedance"],"links":[],"minIntervalMinutes":60}
        self.cfg={"sources":[self.spec],"reviewedObservations":[{"id":"manual"}]}
        self.page="<main>创作 画布 <span>SeedAudio 1.5</span></main>"
    def run_collect(self,old=None,hours=0,page=None):
        return collect(self.cfg,old or {},self.now+timedelta(hours=hours),
                       lambda _:parse_surface(self.page if page is None else page,self.spec))
    def test_only_visible_named_models(self):
        page=self.page+'<script>SeedAudio 2.0</script><div hidden>Seedream 8.0</div><span>Seedance 2.5 Pro</span>'
        self.assertEqual(list(parse_surface(page,self.spec)),["seedaudio1.5"])
    def test_baseline_and_new_label_are_not_release_dates(self):
        first=self.run_collect()
        self.assertEqual(first["events"][0]["kind"],"baseline-visible-label")
        later=self.run_collect(first,1,self.page+"<span>Seedream 5.5</span>")
        self.assertEqual(later["events"][0]["kind"],"new-visible-label")
        self.assertIsNone(later["events"][0]["releaseDate"])
        self.assertEqual(later["reviewedObservations"],self.cfg["reviewedObservations"])
    def test_missing_labels_and_login_do_not_invent_withdrawal(self):
        first=self.run_collect()
        failed=self.run_collect(first,1,"<html>登录</html>")
        self.assertEqual(failed["sources"][0]["lastSuccessAt"],first["sources"][0]["lastSuccessAt"])
        self.assertEqual(failed["events"],first["events"])
        later=self.run_collect(first,1,"创作 画布 Seedream 5.5")
        self.assertFalse(later["sources"][0]["entries"]["seedaudio1.5"]["visibleInLatestRead"])
        self.assertEqual(len(later["events"]),2)
    def test_manual_review_is_not_automatic_success(self):
        result=self.run_collect(page="登录")
        self.assertEqual(result["summary"]["successfulThisRun"],0)
        self.assertEqual(result["summary"]["reviewedObservations"],1)


    def test_store_observation_is_not_model_release(self):
        from scripts.collect_app_updates import parse_store
        spec={"trackId":6503676563,"expectedName":"即梦"}
        payload={"resultCount":1,"results":[{"trackId":6503676563,"trackName":"即梦 AI","version":"3.2.1",
            "currentVersionReleaseDate":"2026-11-26T00:00:00Z","releaseNotes":"New model and feature"}]}
        records=parse_store(payload,spec)
        row=next(iter(records.values()))
        self.assertEqual(row["storeVersion"],"3.2.1")
        self.assertEqual(row["claimType"],"first-party-store-version")
        self.assertNotIn("modelName",row)
        self.assertNotIn("releaseNotes",row)
        payload["results"][0]["trackId"]=123
        with self.assertRaises(ValueError):
            parse_store(payload,spec)

    def test_targeted_query_keeps_counts_not_articles_and_respects_cooldown(self):
        from scripts.collect_app_updates import collect_targeted
        cfg={"intervalMinutes":360,"globalIntervalMinutes":60,"queries":[{"id":"a","term":"即梦","category":"ai-products"},{"id":"b","term":"Sand.ai","category":"ai-models"}]}
        calls=[]
        def fetch(spec,etag):
            calls.append(spec["id"])
            return {"items":11,"wechatOriginalLinks":7,"otherOriginalLinks":4,"missingOriginalLinks":0,"exactTitleMatches":11,"hasNextCursor":False},"tag"
        first=collect_targeted(cfg,{},self.now,fetch)
        blocked=collect_targeted(cfg,first,self.now+timedelta(minutes=30),fetch)
        second=collect_targeted(cfg,blocked,self.now+timedelta(hours=1),fetch)
        self.assertEqual(calls,["a","b"])
        self.assertEqual(second["queries"][0]["counts"]["wechatOriginalLinks"],7)
        later=collect_targeted(cfg,second,self.now+timedelta(hours=6),lambda spec,etag:(None,etag))
        self.assertEqual(later["queries"][0]["countsObservedAt"],first["queries"][0]["countsObservedAt"])
        self.assertEqual(later["queries"][0]["status"],"unchanged")

    def test_targeted_rate_limit_does_not_erase_last_good_counts(self):
        from scripts.collect_app_updates import collect_targeted
        from urllib.error import HTTPError
        cfg={"intervalMinutes":360,"globalIntervalMinutes":60,"queries":[{"id":"a","term":"即梦","category":"ai-products"}]}
        first=collect_targeted(cfg,{},self.now,lambda *_:({"items":0,"wechatOriginalLinks":0},"tag"))
        def fail(*args):
            raise HTTPError("https://aipick.news/",429,"limit",{"Retry-After":"28800"},None)
        second=collect_targeted(cfg,first,self.now+timedelta(hours=6),fail)
        self.assertEqual(second["queries"][0]["counts"],first["queries"][0]["counts"])
        self.assertEqual(second["queries"][0]["lastSuccessAt"],first["queries"][0]["lastSuccessAt"])
        self.assertEqual(second["service"]["nextAttemptAt"],(self.now+timedelta(hours=14)).isoformat())

    def test_higgs_changelog_dates_stage_and_no_promotions(self):
        from scripts.collect_app_updates import parse_higgs_changelog
        page="""<h1>What's new</h1><time>November 24, 2026</time><h2>MAGI-2</h2><ul><li>Feature</li><li>Models</li></ul><p>Video and sound</p>
        <time>November 21, 2026</time><h2>Editing Room</h2><ul><li>Release</li><li>Video Tools</li></ul>
        <time>November 2, 2026</time><h2>Higgsfield Mangaka</h2><ul><li>Release</li><li>Image Tools</li></ul>
        <time>November 1, 2026</time><h2>Black Friday discount</h2><ul><li>Feature</li><li>Billing</li></ul>
        <h2>Old models</h2><p>Footer</p><script>November 28, 2026</script>"""
        values=list(parse_higgs_changelog(page,{}).values())
        self.assertEqual([v["featureName"] for v in values],["MAGI-2","Editing Room","Higgsfield Mangaka"])
        self.assertEqual(values[0]["updateType"],"model-integration")
        self.assertEqual(values[2]["publisherCalendarDay"],"2026-11-02")
        self.assertTrue(all(v["claimType"]=="first-party-product-changelog" for v in values))
        with self.assertRaises(ValueError):parse_higgs_changelog("<h2>Models</h2>",{})

    def test_dated_changelog_adapter_keeps_real_dates_and_distinct_features(self):
        from scripts.collect_app_updates import parse_dated_changelog
        page="""<h1>Latest Updates</h1><p>2026-11-24</p><h2>Audio processing and track separation</h2><p>Split vocals and background music into independent tracks.</p><h2>Video and timeline audio translation</h2><p>Translate the selected track and retain editable project media.</p><p>2026-11-14</p><h2>Seedance 2.5 Flash is here</h2><p>Generate and extend videos within the creative application.</p><h2>Credit estimates for upscaling</h2><p>See the estimated credits before submitting a job.</p>"""
        rows=list(parse_dated_changelog(page,{"id":"flova-changelog"}).values())
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]["publisherCalendarDay"],"2026-11-24")
        self.assertEqual(rows[2]["updateType"],"model-integration")
        self.assertNotIn("releaseDate",rows[2])
        self.assertEqual(rows[0]["updateType"],"product-update")
        tap='<h1>TapNow changelog</h1><p>v2.20.10</p><p>October 13, 2026</p><h2>Preview relighting live</h2><p>Adjust the light and export the image to a canvas.</p>'
        v=next(iter(parse_dated_changelog(tap,{"id":"tapnow-changelog"}).values()))
        self.assertEqual(v["publisherCalendarDay"],"2026-10-13")
        self.assertEqual(v["productVersion"],"v2.20.10")
        with self.assertRaises(ValueError):parse_dated_changelog("<h2>Login</h2>",{"id":"flova-changelog"})

    def test_navigation_only_never_fetches_or_claims_success(self):
        cfg={"sources":[{"id":"libtv","name":"LibTV","vendor":"LibTV","role":"competitor","url":"https://www.liblib.tv/show","type":"navigation-only","links":[]}]}
        result=collect(cfg,{},self.now,lambda *_:self.fail("navigation-only must not fetch"))
        self.assertEqual(result["sources"][0]["status"],"navigation-only")
        self.assertIsNone(result["sources"][0]["lastSuccessAt"])
        self.assertEqual(result["summary"]["successfulThisRun"],0)
        self.assertEqual(result["events"],[])

    def test_aggregate_first_coverage_defers_only_after_both_provider_queries(self):
        from scripts.collect_app_updates import aggregate_coverage
        spec={"aggregateQueryIds":["a","b"]}
        def row(key,provider,features,models):
            return {"id":key,"provider":provider,"status":"observed","lastAttemptAt":self.now.isoformat(),"lastSuccessAt":self.now.isoformat(),"counts":{"selectedProductFeatures":features,"selectedModelIntegrations":models}}
        first=row("a","AIHOT",0,4)
        second=row("b","AIPick",3,0)
        self.assertEqual(aggregate_coverage(spec,{"queries":[first]},self.now)["status"],"awaiting-aggregate")
        self.assertEqual(aggregate_coverage(spec,{"queries":[first,second]},self.now)["status"],"aggregate-covered-sample")
        second["counts"]["selectedProductFeatures"]=0
        result=aggregate_coverage(spec,{"queries":[first,second]},self.now)
        self.assertEqual(result["status"],"aggregate-gap")
        self.assertEqual(result["missingLanes"],["selectedProductFeatures"])
        self.assertEqual(aggregate_coverage(spec,{"queries":[first,second]},self.now+timedelta(hours=13))["status"],"awaiting-aggregate")

    def test_aggregate_first_skips_direct_probe_and_preserves_existing_events(self):
        cfg={"sources":[{**self.spec,"aggregateQueryIds":["a","b"]}],"targetedDiscovery":{"intervalMinutes":480,"globalIntervalMinutes":25,"queries":[{"id":"a","term":"Higgsfield","provider":"AIHOT"},{"id":"b","term":"Higgsfield","provider":"AIPick"}]}}
        first=collect(cfg,{},self.now,lambda *_:self.fail("wait for both aggregate queries"),lambda *_:({"selectedProductFeatures":2,"selectedModelIntegrations":0},"a"))
        self.assertEqual(first["sources"][0]["skipReason"],"awaiting-aggregate")
        second=collect(cfg,first,self.now+timedelta(minutes=30),lambda *_:self.fail("no duplicate probe when both lanes covered"),lambda *_:({"selectedProductFeatures":0,"selectedModelIntegrations":2},"b"))
        self.assertEqual(second["sources"][0]["skipReason"],"aggregate-covered-sample")
        self.assertEqual(second["summary"]["successfulThisRun"],0)
        self.assertEqual(second["events"],[])

    def test_dual_provider_round_robin_keeps_one_request_each_and_prioritizes_unseen(self):
        from scripts.collect_app_updates import collect_targeted
        cfg={"maxProvidersPerRun":2,"intervalMinutes":720,"globalIntervalMinutes":25,"queries":[
            {"id":"a","term":"Higgsfield","provider":"AIHOT","priority":0},
            {"id":"b","term":"Higgsfield","provider":"AIPick","priority":0},
            {"id":"c","term":"Flova","provider":"AIHOT","priority":10},
            {"id":"d","term":"Flova","provider":"AIPick","priority":10}]}
        calls=[]
        def fetch(spec,etag):
            calls.append(spec["id"])
            return {"items":1},"e"
        first=collect_targeted(cfg,{},self.now,fetch)
        self.assertEqual(calls,["a","b"])
        self.assertEqual(first["attemptedThisRun"],2)
        collect_targeted(cfg,first,self.now+timedelta(minutes=20),fetch)
        self.assertEqual(calls,["a","b"])
        second=collect_targeted(cfg,first,self.now+timedelta(minutes=30),fetch)
        self.assertEqual(calls,["a","b","c","d"])
        self.assertEqual(second["attemptedThisRun"],2)
