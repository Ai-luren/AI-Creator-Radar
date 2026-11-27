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
