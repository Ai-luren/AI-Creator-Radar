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
        page="""<h1>What's new</h1><time>November 26, 2026</time><h2>Seedream 5.5 now supports 4K</h2><ul><li>Improvement</li><li>Models</li></ul><p>Existing model resolution option.</p>
        <time>November 24, 2026</time><h2>MAGI-2</h2><ul><li>Feature</li><li>Models</li></ul><p>Video and sound</p>
        <time>November 21, 2026</time><h2>Editing Room</h2><ul><li>Release</li><li>Video Tools</li></ul>
        <time>November 2, 2026</time><h2>Higgsfield Mangaka</h2><ul><li>Release</li><li>Image Tools</li></ul>
        <time>November 1, 2026</time><h2>Black Friday discount</h2><ul><li>Feature</li><li>Billing</li></ul>
        <h2>Old models</h2><p>Footer</p><script>November 28, 2026</script>"""
        values=list(parse_higgs_changelog(page,{}).values())
        self.assertEqual([v["featureName"] for v in values],["Seedream 5.5 now supports 4K","MAGI-2","Editing Room","Higgsfield Mangaka"])
        self.assertEqual(values[0]["updateType"],"product-improvement")
        self.assertEqual(values[1]["updateType"],"model-integration")
        self.assertEqual(values[3]["publisherCalendarDay"],"2026-11-02")
        self.assertTrue(all(v["claimType"]=="first-party-product-changelog" for v in values))
        with self.assertRaises(ValueError):parse_higgs_changelog("<h2>Models</h2>",{})

    def test_correct_cached_model_improvement_during_cooldown_without_new_observation(self):
        spec={**self.spec,"id":"higgsfield-changelog","type":"higgs-changelog","url":"https://higgsfield.ai/creator-hub/changelog"}
        entry={"featureName":"Seedream 5.5 now supports 4K","publisherCalendarDay":"2026-11-26",
               "publisherLabel":"Improvement","productArea":"Models","updateType":"model-integration",
               "claimType":"first-party-product-changelog","firstObservedAt":"2026-11-27T00:00:00+00:00",
               "lastObservedAt":"2026-11-27T00:00:00+00:00"}
        integration={**entry,"featureName":"MAGI-2","publisherLabel":"Feature"}
        prior={"schema":"app-updates/v1","sources":[{**spec,"status":"observed","lastSuccessAt":entry["lastObservedAt"],
               "nextAttemptAt":(self.now+timedelta(hours=1)).isoformat(),"entries":{"feature":entry,"integration":integration}}],
               "events":[{**entry,"id":"feature","sourceId":spec["id"],"observedAt":entry["firstObservedAt"],"releaseDate":None},
                         {**integration,"id":"integration","sourceId":spec["id"],"observedAt":entry["firstObservedAt"],"releaseDate":None},
                         {**entry,"id":"other-source","sourceId":"other","observedAt":entry["firstObservedAt"],"releaseDate":None}]}
        result=collect({"sources":[spec]},prior,self.now,lambda *_:self.fail("cooldown must not fetch"))
        self.assertEqual(result["summary"]["successfulThisRun"],0)
        self.assertEqual(result["sources"][0]["entries"]["feature"],{**entry,"updateType":"product-improvement"})
        self.assertEqual(result["sources"][0]["entries"]["integration"],integration)
        byid={e["id"]:e for e in result["events"]}
        self.assertEqual(byid["feature"],{**prior["events"][0],"updateType":"product-improvement"})
        self.assertEqual(byid["integration"],prior["events"][1])
        self.assertEqual(byid["other-source"],prior["events"][2])
        self.assertEqual(prior["events"][0]["updateType"],"model-integration")

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
        spec={"aggregateQueryIds":["a","b"],"vendor":"Higgsfield"}
        snapshots=self.readable_fixture()
        def row(key,provider,features,models):
            return {"id":key,"provider":provider,"status":"observed","lastAttemptAt":self.now.isoformat(),"lastSuccessAt":self.now.isoformat(),"counts":{"selectedProductFeatures":features,"selectedModelIntegrations":models}}
        first=row("a","AIHOT",0,4)
        second=row("b","AIPick",3,0)
        self.assertEqual(aggregate_coverage(spec,{"queries":[first]},self.now)["status"],"awaiting-aggregate")
        self.assertEqual(aggregate_coverage(spec,{"queries":[first,second]},self.now)["status"],"aggregate-gap")
        self.assertEqual(aggregate_coverage(spec,{"queries":[first,second]},self.now,snapshots)["status"],"aggregate-covered-sample")
        second["counts"]["selectedProductFeatures"]=0
        result=aggregate_coverage(spec,{"queries":[first,second]},self.now,snapshots)
        self.assertEqual(result["status"],"aggregate-gap")
        self.assertEqual(result["missingLanes"],["selectedProductFeatures"])
        self.assertEqual(aggregate_coverage(spec,{"queries":[first,second]},self.now+timedelta(hours=13))["status"],"awaiting-aggregate")

    def readable_fixture(self):
        return {"AIHOT":{"fetchedAt":self.now.isoformat(),"items":[{"title":"Higgsfield 新功能","selected":True,"publishedAt":self.now.isoformat(),"links":{"original":"https://higgsfield.ai/blog/feature"}},{"title":"MAGI-2 模型接入 Higgsfield","selected":True,"publishedAt":self.now.isoformat(),"links":{"original":"https://higgsfield.ai/blog/model"}}]}}

    def test_aggregate_first_skips_direct_probe_and_preserves_existing_events(self):
        cfg={"sources":[{**self.spec,"vendor":"Higgsfield","aggregateQueryIds":["a","b"]}],"targetedDiscovery":{"intervalMinutes":480,"globalIntervalMinutes":25,"queries":[{"id":"a","term":"Higgsfield","provider":"AIHOT"},{"id":"b","term":"Higgsfield","provider":"AIPick"}]}}
        first=collect(cfg,{},self.now,lambda *_:self.fail("wait for both aggregate queries"),lambda *_:({"selectedProductFeatures":2,"selectedModelIntegrations":0},"a"))
        self.assertEqual(first["sources"][0]["skipReason"],"awaiting-aggregate")
        second=collect(cfg,first,self.now+timedelta(minutes=30),lambda *_:self.fail("no duplicate probe when both lanes covered"),lambda *_:({"selectedProductFeatures":0,"selectedModelIntegrations":2},"b"),snapshots=self.readable_fixture())
        self.assertEqual(second["sources"][0]["skipReason"],"aggregate-covered-sample")
        self.assertEqual(second["summary"]["successfulThisRun"],0)
        self.assertEqual(second["events"],[])

    def test_priority_bands_keep_existing_budget_and_lower_secondary_frequency(self):
        from scripts.collect_app_updates import collect_targeted
        cfg={"maxProvidersPerRun":2,"intervalMinutes":720,"globalIntervalMinutes":25,"queries":[
          {"id":"secondary","term":"Flova","provider":"AIHOT","priority":20,"intervalMinutes":1440},
          {"id":"primary","term":"TapNow","provider":"AIHOT","priority":0,"intervalMinutes":720}]}
        calls=[]
        def fetch(spec,etag):
            calls.append(spec["id"])
            return {"items":1},"e"
        first=collect_targeted(cfg,{},self.now,fetch)
        self.assertEqual(calls,["primary"])
        second=collect_targeted(cfg,first,self.now+timedelta(minutes=30),fetch)
        self.assertEqual(calls,["primary","secondary"])
        secondary=next(x for x in second["queries"] if x["id"]=="secondary")
        self.assertEqual(secondary["nextAttemptAt"],(self.now+timedelta(days=1,minutes=30)).isoformat())

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

    def test_platform_coverage_counts_originals_separately_from_hot_mentions(self):
        from scripts.collect_app_updates import snapshot_platform_coverage,platform_key
        platforms=[{"id":"x","label":"X","role":"social","domains":["x.com","twitter.com"]},
                   {"id":"wechat-article","label":"微信公众号","role":"social","domains":["mp.weixin.qq.com"]},
                   {"id":"instagram","label":"Instagram","role":"social","domains":["instagram.com"]}]
        def item(url,selected=True):
            return {"selected":selected,"publishedAt":self.now.isoformat(),"links":{"original":url}}
        snapshots={"AIHOT":{"fetchedAt":self.now.isoformat(),"items":[item("https://x.com/example/status/123?utm_source=a"),item("https://x.com.evil.test/status/123")]},
                   "AIPick":{"fetchedAt":self.now.isoformat(),"items":[item("https://twitter.com/example/status/123"),item("http://mp.weixin.qq.com/s?mid=123"),item("https://instagram.com/p/one",False)],"hotTopics":[{"latestAt":self.now.isoformat(),"sourceNames":["Instagram · creator","X · example"]}]}}
        result=snapshot_platform_coverage(platforms,snapshots,self.now)
        rows={x["id"]:x for x in result["platforms"]}
        self.assertEqual(rows["x"]["originalCount"],1)
        self.assertEqual(rows["x"]["providers"],["AIHOT","AIPick"])
        self.assertEqual(rows["wechat-article"]["originalCount"],1)
        self.assertEqual(rows["instagram"]["status"],"hot-mention-only")
        self.assertEqual(rows["instagram"]["originalCount"],0)
        self.assertIsNone(platform_key("https://x.com.evil.test/status/123",platforms))
        self.assertIsNone(platform_key("https://x.com:8000/status/123",platforms))
        self.assertIsNone(platform_key("https://user@x.com/status/123",platforms))

    def test_platform_coverage_rejects_non_content_urls_and_story_representatives(self):
        from scripts.collect_app_updates import platform_key,snapshot_platform_coverage
        platforms=[{"id":"x","label":"X","role":"social","domains":["x.com","twitter.com"]},
                   {"id":"wechat-article","label":"微信公众号","role":"social","domains":["mp.weixin.qq.com"]},
                   {"id":"douyin","label":"抖音","role":"social","domains":["douyin.com"]},
                   {"id":"youtube","label":"YouTube","role":"social","domains":["youtube.com","youtu.be"]},
                   {"id":"instagram","label":"Instagram","role":"social","domains":["instagram.com"]}]
        for url in ("https://x.com","https://x.com/Higgsfield","https://x.com/search?q=Higgsfield",
                    "https://mp.weixin.qq.com/","https://mp.weixin.qq.com/s",
                    "https://www.douyin.com/user/123","https://youtube.com/@creator",
                    "https://youtu.be/","https://instagram.com/creator/","https://x.com:80/a/status/123"):
            with self.subTest(url=url):
                self.assertIsNone(platform_key(url,platforms))
        for url,key in (("https://x.com/Higgsfield/status/123","x"),
                        ("https://www.douyin.com/video/123","douyin"),
                        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ","youtube"),
                        ("https://youtu.be/dQw4w9WgXcQ","youtube"),
                        ("https://instagram.com/reel/ABC123/","instagram"),
                        ("http://mp.weixin.qq.com/s?mid=123","wechat-article")):
            with self.subTest(url=url):
                self.assertEqual(platform_key(url,platforms),key)
        item={"selected":True,"publishedAt":self.now.isoformat(),"links":{"original":"https://x.com/a/status/123","story":"https://aipick.news/story/abc"}}
        coverage=snapshot_platform_coverage(platforms,{"AIPick":{"fetchedAt":self.now.isoformat(),"items":[item]}},self.now)
        self.assertEqual(coverage["platforms"][0]["originalCount"],0)

    def test_refresh_coverage_uses_final_snapshot_without_rewriting_probe_state(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from scripts.collect_app_updates import refresh_platform_coverage
        cfg={"monitoredPlatforms":[{"id":"x","label":"X","role":"social","domains":["x.com"]}]}
        previous={"schema":"app-updates/v1","checkedAt":self.now.isoformat(),
                  "sources":[{"id":"source","lastSuccessAt":self.now.isoformat()}],
                  "targetedDiscovery":{"attemptedThisRun":1},"events":[{"id":"event"}],
                  "platformCoverage":{"checkedAt":self.now.isoformat()}}
        later=self.now+timedelta(minutes=2)
        item={"selected":True,"publishedAt":later.isoformat(),"links":{"original":"https://x.com/a/status/123"}}
        with TemporaryDirectory() as tmp:
            directory=Path(tmp)
            (directory/"aihot-items.json").write_text(json.dumps({"fetchedAt":self.now.isoformat(),"items":[]}),encoding="utf-8")
            file=directory/"aipick-data.json"
            file.write_text(json.dumps({"fetchedAt":self.now.isoformat(),"items":[]}),encoding="utf-8")
            early=refresh_platform_coverage(cfg,previous,directory,self.now)
            file.write_text(json.dumps({"fetchedAt":later.isoformat(),"items":[item]}),encoding="utf-8")
            final=refresh_platform_coverage(cfg,early,directory,later)
        self.assertEqual(early["platformCoverage"]["platforms"][0]["originalCount"],0)
        self.assertEqual(final["platformCoverage"]["platforms"][0]["originalCount"],1)
        self.assertEqual(final["platformCoverage"]["sources"][1]["fetchedAt"],later.isoformat())
        self.assertEqual({k:v for k,v in final.items() if k!="platformCoverage"},
                         {k:v for k,v in previous.items() if k!="platformCoverage"})

    def test_public_product_surfaces_are_scoped_and_not_release_facts(self):
        from scripts.collect_app_updates import parse_product_surface
        hf={**self.spec,"id":"higgsfield-home","url":"https://higgsfield.ai/","type":"product-surface"}
        page="""<main>Higgsfield New drops <a href="/cinema-studio">Cinema Studio</a>
        <a href="/property-studio">Property Studio New</a><a href="/editing-room" aria-label="Open Higgsfield Editing Room">Editing Room</a>
        <a href="https://higgsfield.ai.evil.test/fake-studio">Fake Studio</a>
        <div hidden><a href="/hidden-studio">Hidden Studio</a></div><a href="/pricing">Discount</a></main>"""
        rows=parse_product_surface(page,hf)
        self.assertEqual({v["featureName"] for v in rows.values()},{"Cinema Studio","Property Studio","Higgsfield Editing Room"})
        self.assertTrue(all(v["claimType"]=="first-party-product-surface" and "publisherCalendarDay" not in v for v in rows.values()))
        lib={**self.spec,"id":"libtv-home","url":"https://www.liblib.tv/","type":"product-surface"}
        html="<main>LibTV 版本更新记录 新建画布创作 <span>LibTV 画布</span><span>LibTV 3D-BOX</span><h2>最近上新</h2><div>元素替换New</div><div>大赛New</div><h2>创作精选</h2><div>其他功能New</div></main>"
        values=list(parse_product_surface(html,lib).values())
        self.assertEqual({v["featureName"] for v in values},{"LibTV 画布","LibTV 3D-BOX","元素替换New"})
        with self.assertRaises(ValueError):parse_product_surface("<main>登录</main>",lib)
        first=collect({"sources":[hf]}, {},self.now,lambda _:rows)
        second=collect({"sources":[hf]},first,self.now+timedelta(hours=1),lambda _:parse_product_surface(page.replace("</main>",'<a href="/comic-studio">Comic Studio</a></main>'),hf))
        self.assertTrue(all(e["kind"]=="baseline-product-surface" and e["releaseDate"] is None for e in first["events"]))
        changes=[e for e in second["events"] if e["kind"]=="new-product-surface"]
        self.assertEqual([e["featureName"] for e in changes],["Comic Studio"])
        self.assertIsNone(changes[0]["releaseDate"])

    def test_libtv_whole_product_updates_and_non_feature_exclusions(self):
        from scripts.collect_app_updates import parse_product_surface
        spec={**self.spec,"id":"libtv-home","url":"https://www.liblib.tv/","type":"product-surface"}
        page="""<main><nav>首页项目资产插件</nav><span>LibTV 画布</span><span>版本更新记录</span><span>新建画布创作</span>
        <h2>最近上新</h2><p>新增资产共享功能</p><p>智能剪辑支持字幕导出</p><p>插件系统升级</p>
        <p>MAGI-2独家首发·低至12积分/秒</p><p>全新AI视频课程</p><p>电影节活动上线</p><p>会员优惠上线</p>
        <h2>创作精选</h2><p>角色资产新功能上线</p></main>"""
        labels={v["featureName"] for v in parse_product_surface(page,spec).values()}
        self.assertTrue({"项目","资产","插件","新增资产共享功能","智能剪辑支持字幕导出","插件系统升级","MAGI-2独家首发"}<=labels)
        self.assertFalse({"全新AI视频课程","电影节活动上线","会员优惠上线","角色资产新功能上线"}&labels)

    def test_real_surface_markup_identity_and_parser_upgrade(self):
        from scripts.collect_app_updates import parse_product_surface
        lib={**self.spec,"id":"libtv-home","url":"https://www.liblib.tv/","type":"product-surface"}
        html="""<main>LibTV 版本更新记录 新建画布创作<h2>最近上新</h2>
        <div><span>MAGI-2</span><span>独家首发</span></div>
        <div><span>Seedance</span><span>2.5 Flash</span><span>模型上新</span></div>
        <div><span>Seedream 5.5</span><span>模型上新</span></div>
        <div>模型上新</div><h2>创作精选</h2></main>"""
        names={e["featureName"] for e in parse_product_surface(html,lib).values()}
        self.assertEqual(names,{"MAGI-2独家首发","Seedance 2.5 Flash模型上新","Seedream 5.5模型上新"})
        hf={**self.spec,"id":"higgsfield-home","url":"https://higgsfield.ai/","type":"product-surface"}
        page="""<main>Higgsfield New drops <a href="/cinema-studio">Cinema Studio</a>
        <a href="/editing-room">Editing Room</a><a href="/editing-room">Higgsfield Editing Room Change the angle of any video</a>
        <a href="/miracle">Miracle Soon</a><a href="/ai/video?model=genjutsu">Genjutsu Top</a>
        <a href="/plugins/after-effects">Plugins</a><a href="/mcp?tab=claude">MCP for Claude</a>
        <a href="/supercomputer">Agentic</a><a href="/supercomputer">Supercomputer</a>
        <a href="/shorts-studio">View all presets</a></main>"""
        fresh=parse_product_surface(page,hf)
        self.assertEqual(len(fresh),7)
        self.assertEqual(len([x for x in fresh.values() if x["featureUrl"].endswith("/editing-room")]),1)
        self.assertEqual(next(x for x in fresh.values() if x["featureName"]=="Miracle")["surfaceStage"],"coming-soon")
        self.assertTrue(any(x["featureUrl"].endswith("?model=genjutsu") for x in fresh.values()))
        previous={"schema":"app-updates/v1","sources":[{**hf,"lastSuccessAt":(self.now-timedelta(hours=1)).isoformat(),"entries":{"old":{"featureName":"View all presets","claimType":"first-party-product-surface"}}}],"events":[]}
        migrated=collect({"sources":[hf]},previous,self.now,lambda _:fresh)
        self.assertTrue(all(e["kind"]=="baseline-product-surface" for e in migrated["events"]))
        self.assertFalse(migrated["sources"][0]["entries"]["old"]["visibleInLatestRead"])

    def test_model_watch_from_verified_recent_release_shares_existing_budget(self):
        from scripts.collect_app_updates import collect_targeted, model_watch_queries, model_watch_counts
        release={"modelName":"Seedance 3.5","modelFamilyId":"seedance","modelVersionId":"seedance-3-5","category":"video",
                 "publishedAt":self.now.date().isoformat(),"verifiedAt":self.now.date().isoformat(),
                 "evidenceType":"official-release","url":"https://example.org/official"}
        bad=[{**release,"modelName":"Seedance 9.9","verificationStatus":"pending"},
             {**release,"modelName":"Seedance 3.5?bad"},
             {**release,"publishedAt":"2026-01-01"}]
        queries=model_watch_queries([release,*bad],self.now)
        self.assertEqual(len(queries),2)
        self.assertEqual({q["provider"] for q in queries},{"AIHOT","AIPick"})
        calls=[]
        cfg={"maxProvidersPerRun":2,"intervalMinutes":720,"globalIntervalMinutes":25,"queries":[
            {"id":"hf","term":"Higgsfield","provider":"AIHOT","priority":0}]}
        def fetch(q,etag):
            calls.append(q["id"])
            return {"items":1},"e"
        first=collect_targeted(cfg,{},self.now,fetch,releases=[release])
        self.assertEqual(first["attemptedThisRun"],2)
        self.assertTrue(all(x.startswith("model-watch-") for x in calls))
        blocked=collect_targeted(cfg,first,self.now+timedelta(minutes=10),fetch,releases=[release])
        self.assertEqual(blocked["attemptedThisRun"],0)
        later=collect_targeted(cfg,blocked,self.now+timedelta(minutes=30),fetch,releases=[release])
        self.assertEqual(later["attemptedThisRun"],1)
        self.assertEqual(calls[-1],"hf")
        rows=[{"selected":True,"title":"Higgsfield 接入 Seedance 3.5","links":{"original":"https://example.org/1"}},
              {"selected":True,"title":"LibTV Seedance 3.50","links":{"original":"https://example.org/2"}}]
        result=model_watch_counts(rows,"Seedance 3.5")
        self.assertEqual(result["Higgsfield"],1)
        self.assertEqual(result["LibTV"],0)

    def test_model_watch_gap_enables_existing_official_probe_but_respects_cooldown(self):
        from scripts.collect_app_updates import model_watch_official_gap
        spec={"id":"hf","name":"Higgsfield","vendor":"Higgsfield","type":"higgs-changelog","url":"https://higgsfield.ai/creator-hub/changelog","links":[],"minIntervalMinutes":360}
        rows=[{"modelWatch":True,"modelFamilyId":"seedance","modelVersionId":"35","term":"Seedance 3.5",
               "provider":provider,"publisherCalendarDay":self.now.date().isoformat(),"lastAttemptAt":self.now.isoformat()} for provider in ("AIHOT","AIPick")]
        self.assertEqual(model_watch_official_gap(spec,{"queries":rows[:1]},{},self.now),[])
        self.assertEqual(model_watch_official_gap(spec,{"queries":rows},{},self.now),["Seedance 3.5"])
        prior={"sources":[spec],"events":[{"sourceId":"hf","claimType":"first-party-product-changelog","updateType":"model-integration",
               "featureName":"Seedance 3.5","publisherCalendarDay":self.now.date().isoformat()}]}
        self.assertEqual(model_watch_official_gap(spec,{"queries":rows},prior,self.now),[])
        self.assertEqual(model_watch_official_gap(spec,{"queries":rows},{},self.now+timedelta(hours=13)),[])
        release={"modelName":"Seedance 3.5","modelFamilyId":"seedance","modelVersionId":"35","category":"video",
                 "publishedAt":self.now.date().isoformat(),"verifiedAt":self.now.date().isoformat(),
                 "evidenceType":"official-release","url":"https://example.org/official"}
        cfg={"sources":[{**spec,"aggregateQueryIds":["a","b"]}],"targetedDiscovery":{"intervalMinutes":720,"globalIntervalMinutes":25,
             "maxProvidersPerRun":2,"queries":[{"id":"a","term":"Higgsfield","provider":"AIHOT"},{"id":"b","term":"Higgsfield","provider":"AIPick"}]}}
        previous={"schema":"app-updates/v1","sources":[{**spec,"nextAttemptAt":(self.now+timedelta(hours=1)).isoformat()}],"events":[]}
        got=collect(cfg,previous,self.now,lambda _:self.fail("must honor source cooldown"),lambda *_:({"items":0},"e"),releases=[release])
        self.assertEqual(got["sources"][0]["modelWatchGap"],["Seedance 3.5"])
        self.assertTrue(got["sources"][0]["deferred"])
        self.assertEqual(got["summary"]["successfulThisRun"],0)

    def test_model_watch_matches_spacing_without_collapsing_variants(self):
        from scripts.collect_app_updates import model_watch_pattern
        p=model_watch_pattern("MAGI-2")
        self.assertTrue(p.search("Higgsfield 接入 MAGI 2"))
        self.assertTrue(p.search("MAGI2模型上新"))
        self.assertFalse(p.search("MAGI-20"))
        self.assertFalse(p.search("MAGI-2.1"))
        self.assertFalse(p.search("MAGI-2-fast"))
        p=model_watch_pattern("Seedance 3.5")
        self.assertFalse(p.search("Seedance 3.5 Pro"))
        self.assertTrue(p.search("Seedance 3.5 视频模型"))

    def test_old_ordinary_query_gets_slot_before_repeated_watch(self):
        from scripts.collect_app_updates import collect_targeted
        cfg={"maxProvidersPerRun":1,"intervalMinutes":720,"globalIntervalMinutes":25,
             "queries":[{"id":"secondary","term":"Flova","provider":"AIHOT","priority":20}]}
        row={"modelName":"MAGI-2","modelFamilyId":"magi","modelVersionId":"2","category":"video",
             "publishedAt":self.now.date().isoformat(),"verifiedAt":self.now.date().isoformat(),
             "evidenceType":"official-release","url":"https://example.org/official"}
        from scripts.collect_app_updates import model_watch_queries
        watches=model_watch_queries([row],self.now)
        old={"queries":[{**cfg["queries"][0],"queuedAt":(self.now-timedelta(hours=25)).isoformat()},
                        *[{**w,"lastAttemptAt":(self.now-timedelta(hours=7)).isoformat()} for w in watches]]}
        calls=[]
        def fetch(q,etag):
            calls.append(q["id"])
            return {"items":0},"tag"
        got=collect_targeted(cfg,old,self.now,fetch,releases=[row])
        self.assertEqual(calls,["secondary"])
        self.assertEqual(got["attemptedThisRun"],1)

    def test_readable_coverage_rejects_stale_snapshots_and_report_only_links(self):
        from scripts.collect_app_updates import readable_competitor_lanes
        snapshots=self.readable_fixture()
        self.assertEqual(len(readable_competitor_lanes(snapshots,"Higgsfield",self.now)),2)
        snapshots["AIHOT"]["items"][1]["links"]["story"]="https://aihot.news/story/test"
        self.assertEqual(readable_competitor_lanes(snapshots,"Higgsfield",self.now),{"selectedProductFeatures"})
        snapshots["AIHOT"]["fetchedAt"]=(self.now-timedelta(hours=13)).isoformat()
        snapshots["AIHOT"]["checkedAt"]=self.now.isoformat()
        self.assertEqual(readable_competitor_lanes(snapshots,"Higgsfield",self.now),set())

    def test_oiioii_public_directory_lists_models_not_launch_dates(self):
        from scripts.collect_app_updates import parse_product_surface
        spec={**self.spec,"id":"oiioii-model-directory","vendor":"OiiOii","type":"product-surface",
              "url":"https://www.oiioii.ai/zh/explore/models"}
        page="""<main><h1>AI 创作模型介绍 · OiiOii</h1>
        <a href="/zh/gpt-image-2-6">GPT Image 2.6 图像生成器</a>
        <a href="/zh/seedance-2-5">Seedance 2.5</a>
        <a href="/zh/seedance-2-0-fast">Seedance 2.0 Fast</a>
        <a href="/zh/sora-2">Sora 2 已停用</a>
        <a href="/zh/veo-4">Veo 4 即将上线</a>
        <a href="/zh/blog/seedance">Seedance 9.9 教程</a>
        <a href="https://example.org/zh/magi">MAGI-2</a>
        <a hidden href="/zh/magi">MAGI-2</a></main>"""
        rows=parse_product_surface(page,spec)
        self.assertEqual({x["featureName"] for x in rows.values()},{"GPT Image 2.6","Seedance 2.5","Seedance 2.0 Fast"})
        self.assertTrue(all(x["surfaceStage"]=="catalog-listed" for x in rows.values()))
        first=collect({"sources":[spec]}, {},self.now,lambda _:rows)
        self.assertTrue(all(e["kind"]=="baseline-product-surface" and e["releaseDate"] is None for e in first["events"]))
        with self.assertRaises(ValueError):parse_product_surface("<main>OiiOii AI 创作模型介绍</main>",spec)


class CoreCompetitorConfigTests(unittest.TestCase):
    def test_five_core_competitors_use_same_query_band_and_model_watch(self):
        from pathlib import Path
        import json
        from scripts.collect_app_updates import MODEL_WATCH_BRANDS
        config=json.loads((Path(__file__).resolve().parents[1]/"config/app-update-sources.json").read_text(encoding="utf-8"))
        core=["Higgsfield","LibTV","TapNow","OiiOii","Flova"]
        self.assertEqual(list(MODEL_WATCH_BRANDS[:5]),core)
        for brand in core:
            rows=[q for q in config["targetedDiscovery"]["queries"] if q["term"]==brand]
            self.assertEqual({q["provider"] for q in rows},{"AIHOT","AIPick"})
            self.assertTrue(all(q["priority"]<10 and q["intervalMinutes"]==720 for q in rows))
