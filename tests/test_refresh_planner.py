import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.plan_refresh import GROUPS, plan


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

    def test_regular_push_skips_recent_fast_collectors(self):
        for group in GROUPS:
            self.stamp(group, 40)
        self.assertTrue(plan(self.data, "schedule", now=self.now)["models"])
        self.assertFalse(plan(self.data, "push", now=self.now)["models"])

    def test_missing_or_future_timestamp_is_due(self):
        self.stamp("models", -5)
        self.assertTrue(plan(self.data, "push", now=self.now)["models"])
        self.assertTrue(plan(self.data, "push", now=self.now)["maintenance"])

    def test_explicit_scope_and_deploy_only(self):
        self.assertFalse(any(plan(self.data, "workflow_dispatch", "deploy-only", self.now).values()))
        self.assertEqual({k for k, v in plan(self.data, "workflow_dispatch", "models", self.now).items() if v}, {"models", "selected"})
        self.assertEqual({k for k, v in plan(self.data, "workflow_dispatch", "resources", self.now).items() if v}, {"resources", "aihot_daily", "juya_daily"})

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
