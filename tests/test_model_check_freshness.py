import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.plan_refresh import last_model_success, model_check_stamps, plan


class ModelCheckFreshnessTests(unittest.TestCase):
    def test_all_failed_preserves_success_and_complete_dates(self):
        old = {"checkedAt": "2026-11-25T12:00:00Z", "successSources": 38, "failedSources": 0}
        result = model_check_stamps(old, "2026-11-26T12:00:00Z", 0, 38)
        self.assertEqual(result["lastSuccessfulCheckAt"], old["checkedAt"])
        self.assertEqual(result["lastCompleteCheckAt"], old["checkedAt"])
        self.assertIsNone(last_model_success({"successSources": 0, "checkedAt": old["checkedAt"]}))

    def test_partial_success_does_not_mark_complete(self):
        old = {"checkedAt": "2026-11-25T12:00:00Z", "successSources": 38, "failedSources": 0}
        now = "2026-11-26T12:00:00Z"
        result = model_check_stamps(old, now, 37, 38)
        self.assertEqual(result["lastSuccessfulCheckAt"], now)
        self.assertEqual(result["lastCompleteCheckAt"], old["checkedAt"])
        self.assertEqual(model_check_stamps(result, now, 38, 38)["lastCompleteCheckAt"], now)

    def test_failed_transport_with_new_attempt_still_due(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp)
            now = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)
            (data / "model-monitor-status.json").write_text(json.dumps({"checkedAt": now.isoformat(), "lastSuccessfulCheckAt": "2026-11-25T12:00:00Z", "successSources": 0}))
            (data / "chronicle-updates-status.json").write_text(json.dumps({"checkedAt": now.isoformat()}))
            (data / "model-releases-30d.json").write_text(json.dumps({"updatedAt": now.isoformat()}))
            self.assertTrue(plan(data, "workflow_dispatch", "due", now)["models"])
            self.assertEqual(plan(data, "workflow_dispatch", "due", now), plan(data, "schedule", now=now))
