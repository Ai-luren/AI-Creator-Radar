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
            (self.data / name).write_text(json.dumps({field: (self.now - timedelta(minutes=age)).isoformat()}), encoding="utf-8")

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
        self.assertEqual({k for k, v in plan(self.data, "workflow_dispatch", "resources", self.now).items() if v}, {"resources", "briefings"})
