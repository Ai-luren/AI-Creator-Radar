import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from scripts.plan_refresh import GROUPS, plan
from scripts.scheduler_manifest import build

class SchedulerManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data=Path(self.temp.name)
        self.now=datetime(2026,11,26,18,0,tzinfo=timezone.utc)
        for group,inputs in GROUPS.items():
            for filename,field in inputs:
                (self.data/filename).write_text(json.dumps({field:self.now.isoformat(),"title":"2026-11-27"}),encoding="utf-8")

    def test_fresh_heartbeat_uses_existing_due_planner(self):
        result=build(self.data,self.now,"schedule","123","1","5,35 * * * *")
        self.assertEqual(result["schema"],"scheduler-health/v1")
        self.assertEqual(result["trigger"]["runId"],"123")
        self.assertEqual(result["nextDueAt"],(self.now+timedelta(minutes=25)).isoformat())
        self.assertFalse(any(g["due"] for g in result["groups"].values()))

    def test_missing_data_does_not_claim_freshness(self):
        (self.data/"lead-resolution.json").unlink()
        result=build(self.data,self.now,"workflow_dispatch","123","1",scope="due")
        self.assertEqual(result["nextDueAt"],self.now.isoformat())
        self.assertTrue(result["groups"]["models"]["due"])
        self.assertIsNone(result["groups"]["models"]["oldestSnapshotAt"])

    def test_new_morning_retry_does_not_trigger_all_groups(self):
        result=plan(self.data,"schedule",now=self.now+timedelta(hours=8),schedule="15,25 0,2 * * *")
        self.assertFalse(result["models"])
        self.assertFalse(result["resources"])
        self.assertFalse(result["selected"])


    def test_deferred_group_remains_visibly_due_with_real_next_boundary(self):
        (self.data / "lead-resolution.json").unlink()
        (self.data / "collection-health.json").write_text(json.dumps({"sources": {
            "models-batch": {"status": "degraded", "consecutiveFailures": 1,
                             "lastAttemptAt": self.now.isoformat()}}}), encoding="utf-8")
        result = build(self.data, self.now, "schedule", "123", "1")
        self.assertTrue(result["groups"]["models"]["due"])
        self.assertFalse(result["groups"]["models"]["eligible"])
        self.assertIsNone(result["groups"]["models"]["oldestSnapshotAt"])
        self.assertEqual(result["groups"]["models"]["retryAfter"], (self.now + timedelta(minutes=15)).isoformat())
        self.assertEqual(result["nextDueAt"], (self.now + timedelta(minutes=15)).isoformat())
