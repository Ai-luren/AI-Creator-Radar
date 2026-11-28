import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.plan_refresh import GROUPS, plan, execution_plan


class RefreshPlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        self.now = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)

    def stamp(self, group, age=0):
        for name, field in GROUPS[group]:
            ts = self.now - timedelta(minutes=age)
            (self.data / name).write_text(json.dumps({field: ts.isoformat(), "title": ts.date().isoformat()}), encoding="utf-8")

    def test_missed_cron_recovers_every_overdue_group(self):
        for group in GROUPS:
            self.stamp(group, 1500)
        self.assertTrue(all(plan(self.data, "schedule", now=self.now).values()))

    def test_fresh_snapshots_skip_collection(self):
        for group in GROUPS:
            self.stamp(group)
        self.assertFalse(any(plan(self.data, "schedule", now=self.now).values()))

    def test_collector_push_exercises_model_transaction_even_when_fresh(self):
        for group in GROUPS:
            self.stamp(group)
        self.assertFalse(any(plan(self.data, "schedule", now=self.now).values()))
        result = plan(self.data, "push", now=self.now)
        self.assertEqual({k for k, v in result.items() if v}, {"models"})

    def test_collector_push_preserves_selected_cooldown(self):
        for group in GROUPS:
            self.stamp(group, 40)
        self.assertTrue(plan(self.data, "schedule", now=self.now)["selected"])
        self.assertFalse(plan(self.data, "push", now=self.now)["selected"])

    def test_missing_or_future_timestamp_is_due(self):
        self.stamp("models", -5)
        self.assertTrue(plan(self.data, "push", now=self.now)["models"])
        self.assertTrue(plan(self.data, "push", now=self.now)["maintenance"])

    def test_explicit_scope_and_deploy_only(self):
        self.assertFalse(any(plan(self.data, "workflow_dispatch", "deploy-only", self.now).values()))
        self.assertEqual({k for k, v in plan(self.data, "workflow_dispatch", "models", self.now).items() if v}, {"models", "selected"})
        self.assertEqual({k for k, v in plan(self.data, "workflow_dispatch", "resources", self.now).items() if v}, {"resources", "aihot_daily", "juya_daily", "aipick"})

    def test_daily_issue_not_fetch_timestamp_drives_independent_morning_refresh(self):
        morning = datetime(2026, 11, 27, 0, 5, tzinfo=timezone.utc)
        for group in ("aihot_daily", "juya_daily"):
            name, field = GROUPS[group][0]
            (self.data / name).write_text(json.dumps({field: "2026-11-26T23:50:00Z", "title": "2026-11-26"}), encoding="utf-8")
        result = plan(self.data, "schedule", now=morning, schedule="5,15 0,2 * * *")
        self.assertTrue(result["aihot_daily"])
        self.assertFalse(result["juya_daily"])
        self.assertFalse(result["models"])
        self.assertTrue(plan(self.data, "schedule", now=morning + timedelta(hours=2))["juya_daily"])
        name, field = GROUPS["aihot_daily"][0]
        (self.data / name).write_text(json.dumps({field: morning.isoformat(), "title": "AI 日报 2026 年 11 月 27 日"}), encoding="utf-8")
        self.assertFalse(plan(self.data, "schedule", now=morning + timedelta(hours=3))["aihot_daily"])

    def test_future_dated_issue_cannot_be_fresh_with_older_fetch_timestamp(self):
        name, field = GROUPS["aihot_daily"][0]
        (self.data / name).write_text(json.dumps({field: "2026-11-25T00:00:00Z", "title": "2026-11-26"}), encoding="utf-8")
        self.assertTrue(plan(self.data, "schedule", now=self.now)["aihot_daily"])


    def test_failed_group_backoff_does_not_suppress_other_due_groups(self):
        for group in GROUPS:
            self.stamp(group, 1500)
        path = self.data / "collection-health.json"
        for count, minutes in [(1, 15), (2, 30), (99, 30)]:
            path.write_text(json.dumps({"sources": {"models-batch": {
                "status": "degraded", "consecutiveFailures": count,
                "lastAttemptAt": self.now.isoformat()}}}), encoding="utf-8")
            self.assertFalse(plan(self.data, "schedule", now=self.now)["models"])
            self.assertTrue(plan(self.data, "schedule", now=self.now)["selected"])
            self.assertTrue(plan(self.data, "schedule", now=self.now, respect_backoff=False)["models"])
            self.assertFalse(plan(self.data, "workflow_dispatch", "due", self.now)["models"])
            self.assertTrue(plan(self.data, "workflow_dispatch", "models", self.now)["models"])
            self.assertTrue(plan(self.data, "push", now=self.now)["models"])
            self.assertTrue(plan(self.data, "schedule", now=self.now + timedelta(minutes=minutes))["models"])

    def test_invalid_or_recovered_health_does_not_hide_stale_data(self):
        self.stamp("models", 120)
        path = self.data / "collection-health.json"
        for record in [
            {"status": "healthy", "consecutiveFailures": 0, "lastAttemptAt": self.now.isoformat()},
            {"status": "degraded", "consecutiveFailures": True, "lastAttemptAt": self.now.isoformat()},
            {"status": "degraded", "consecutiveFailures": 2, "lastAttemptAt": (self.now + timedelta(minutes=5)).isoformat()},
            {"status": "degraded", "consecutiveFailures": 2, "lastAttemptAt": "bad"},
            None,
        ]:
            path.write_text(json.dumps({"sources": {"models-batch": record}}), encoding="utf-8")
            self.assertTrue(plan(self.data, "schedule", now=self.now)["models"])
        path.write_text("invalid json", encoding="utf-8")
        self.assertTrue(plan(self.data, "schedule", now=self.now)["models"])


    def test_successful_304_revalidates_selected_snapshot_without_changing_download_date(self):
        self.stamp("selected", 120)
        path = self.data / "aihot-items.json"
        payload = json.loads(path.read_text())
        original = payload["fetchedAt"]
        payload.update(items=[], checkedAt=self.now.isoformat())
        path.write_text(json.dumps(payload))
        self.assertFalse(plan(self.data, "schedule", now=self.now)["selected"])
        self.assertTrue(plan(self.data, "schedule", now=self.now + timedelta(minutes=25))["selected"])
        self.assertEqual(json.loads(path.read_text())["fetchedAt"], original)
        for invalid in ("bad", (self.now - timedelta(hours=3)).isoformat(), (self.now + timedelta(minutes=5)).isoformat()):
            payload["checkedAt"] = invalid
            path.write_text(json.dumps(payload))
            self.assertTrue(plan(self.data, "schedule", now=self.now)["selected"])
        payload["checkedAt"] = self.now.isoformat()
        del payload["items"]
        path.write_text(json.dumps(payload))
        self.assertTrue(plan(self.data, "schedule", now=self.now)["selected"])

    def test_aipick_freshness_independent_of_rankings(self):
        for group in GROUPS:
            self.stamp(group)
        self.stamp("aipick", 26)
        result = plan(self.data, "schedule", now=self.now)
        self.assertTrue(result["aipick"])
        self.assertFalse(result["resources"])
        self.assertTrue(plan(self.data, "push", now=self.now)["aipick"])
        self.stamp("aipick")
        self.stamp("resources", 400)
        result = plan(self.data, "schedule", now=self.now)
        self.assertTrue(result["resources"])
        self.assertFalse(result["aipick"])
        self.assertEqual({k for k,v in plan(self.data,"workflow_dispatch","aipick",self.now).items() if v},{"aipick"})

    def test_aipick_failure_does_not_block_other_due_groups(self):
        for group in GROUPS:
            self.stamp(group, 1500)
        (self.data / "collection-health.json").write_text(json.dumps({"sources":{"aipick-selected":{
            "status":"degraded","consecutiveFailures":2,"lastAttemptAt":self.now.isoformat()}}}))
        result = plan(self.data,"schedule",now=self.now)
        self.assertFalse(result["aipick"])
        self.assertTrue(result["models"])
        self.assertTrue(result["resources"])
        self.assertTrue(plan(self.data,"schedule",now=self.now+timedelta(minutes=30))["aipick"])

    def record_deferred(self, groups):
        (self.data / "scheduler-health.json").write_text(json.dumps({
            "schema":"scheduler-health/v1","deferredSlowGroups":groups}))

    def test_hot_priority_defers_slow_groups_once_and_keeps_raw_due_visible(self):
        for group in GROUPS:
            self.stamp(group, 1500)
        selected, deferred = execution_plan(self.data,"schedule",now=self.now)
        self.assertTrue(selected["models"])
        self.assertTrue(selected["aipick"])
        self.assertFalse(selected["resources"])
        self.assertFalse(selected["maintenance"])
        self.assertEqual(deferred,["maintenance","resources"])
        self.assertTrue(plan(self.data,"schedule",now=self.now)["resources"])
        self.record_deferred(deferred)
        selected, deferred = execution_plan(self.data,"workflow_dispatch","due",now=self.now)
        self.assertTrue(selected["resources"])
        self.assertTrue(selected["maintenance"])
        self.assertEqual(deferred,[])

    def test_explicit_dispatch_and_push_do_not_defer(self):
        for group in GROUPS:
            self.stamp(group,1500)
        for event,scope in [("push",""),("workflow_dispatch","all")]:
            selected,deferred=execution_plan(self.data,event,scope,now=self.now)
            self.assertTrue(selected["resources"])
            self.assertTrue(selected["maintenance"])
            self.assertEqual(deferred,[])

    def test_slow_only_run_never_defers_and_morning_does_not_erase_obligation(self):
        for group in GROUPS:
            self.stamp(group)
        self.stamp("resources",400)
        selected,deferred=execution_plan(self.data,"schedule",now=self.now)
        self.assertTrue(selected["resources"])
        self.assertEqual(deferred,[])
        self.record_deferred(["resources"])
        selected,deferred=execution_plan(self.data,"schedule",now=self.now,schedule="15,25 0,2 * * *")
        self.assertFalse(selected["resources"])
        self.assertEqual(deferred,["resources"])

    def test_backoff_does_not_discard_deferred_obligation(self):
        for group in GROUPS:
            self.stamp(group,1500)
        self.record_deferred(["resources"])
        (self.data/"collection-health.json").write_text(json.dumps({"sources":{"resources-batch":{
            "status":"degraded","consecutiveFailures":2,"lastAttemptAt":self.now.isoformat()}}}))
        selected,deferred=execution_plan(self.data,"schedule",now=self.now)
        self.assertFalse(selected["resources"])
        self.assertIn("resources",deferred)
        self.record_deferred(deferred)
        selected,deferred=execution_plan(self.data,"schedule",now=self.now+timedelta(minutes=30))
        self.assertTrue(selected["resources"])
        self.assertEqual(deferred,[])
