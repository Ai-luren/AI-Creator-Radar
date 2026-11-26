import json
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from scripts.plan_refresh import GROUPS, plan
from scripts.refresh_watchdog import check


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)
        self.calls = []
        self.runs = []
        self.age = 0
        self.fail = False
        self.fields = {name: field for items in GROUPS.values() for name, field in items}

    def invoke(self, args, **kwargs):
        self.calls.append(args)
        if self.fail:
            raise subprocess.CalledProcessError(1, args, stderr="HTTP 503")
        if args[1] == "workflow":
            return SimpleNamespace(stdout="")
        endpoint = args[-1]
        if "/runs?" in endpoint:
            data = {"workflow_runs": self.runs}
        elif endpoint.endswith("branches/main"):
            data = {"commit": {"sha": "fixed-sha"}}
        else:
            self.assertTrue(endpoint.endswith("?ref=fixed-sha"))
            filename = endpoint.split("/")[-1].split("?")[0]
            stamp = self.now - timedelta(minutes=self.age)
            data = {self.fields[filename]: stamp.isoformat(), "title": stamp.date().isoformat()}
        return SimpleNamespace(stdout=json.dumps(data))

    def run_check(self, dry=False):
        return check("gh", "owner/repo", self.now, dry, self.invoke)

    def test_active_and_recent_runs_prevent_duplicate_dispatch(self):
        self.runs = [{"status":"in_progress", "created_at": self.now.isoformat()}]
        self.assertEqual(self.run_check(), "active-run")
        self.runs[0]["status"] = "completed"
        self.assertEqual(self.run_check(), "cooldown")
        self.assertEqual(len(self.calls), 2)

    def test_fresh_snapshots_do_not_dispatch(self):
        self.assertEqual(self.run_check(), "fresh")
        self.assertFalse(any(a[1] == "workflow" for a in self.calls))

    def test_missed_schedule_dispatches_only_due_scope(self):
        self.age = 120
        self.assertTrue(self.run_check(True).startswith("would-dispatch:"))
        self.assertFalse(any(a[1] == "workflow" for a in self.calls))
        self.assertTrue(self.run_check().startswith("dispatched:"))
        self.assertEqual(self.calls[-1][-1], "scope=due")

    def test_api_failure_never_dispatches(self):
        self.fail = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_check()
        self.assertEqual(len(self.calls), 1)
