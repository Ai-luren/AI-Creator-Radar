import unittest
import tempfile
import subprocess
import os
import sys
import json
from pathlib import Path

from scripts.collection_health import update_health


class CollectionHealthTests(unittest.TestCase):
    def test_persistent_incident_alerts_once_and_recovery_resets(self):
        state = {}
        for i in range(1, 6):
            state, alerts = update_health(state, {"aihot-daily": "failure"}, f"attempt-{i}")
            self.assertEqual(alerts, ["aihot-daily"] if i == 3 else [])
            self.assertEqual(state["sources"]["aihot-daily"]["consecutiveFailures"], i)
        state, alerts = update_health(state, {"aihot-daily": "success"}, "recovered")
        self.assertEqual(alerts, [])
        self.assertEqual(state["sources"]["aihot-daily"]["consecutiveFailures"], 0)
        self.assertEqual(state["sources"]["aihot-daily"]["lastSuccessAt"], "recovered")
        for i in range(1, 4):
            state, alerts = update_health(state, {"aihot-daily": "failure"}, f"next-{i}")
        self.assertEqual(alerts, ["aihot-daily"])
        self.assertEqual(state["sources"]["aihot-daily"]["lastSuccessAt"], "recovered")

    def test_skip_preserves_state_and_does_not_alert(self):
        state, _ = update_health({}, {"juya-daily": "failure"}, "first")
        new, alerts = update_health(state, {"juya-daily": "skipped"}, "later")
        self.assertEqual(state, new)
        self.assertEqual(alerts, [])

    def test_sources_are_independent(self):
        state, _ = update_health({}, {"juya-daily": "failure", "aihot-daily": "success"}, "now")
        self.assertEqual(state["sources"]["juya-daily"]["status"], "degraded")
        self.assertEqual(state["sources"]["aihot-daily"]["status"], "healthy")


    def test_persistent_incident_cli_warns_without_failing_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "health.json"
            output = root / "output"
            summary = root / "summary"
            script = Path(__file__).resolve().parents[1] / "scripts" / "collection_health.py"
            env = {**os.environ, "AIHOT_SELECTED": "", "AIHOT_DAILY": "failure", "JUYA_DAILY": ""}
            for attempt in range(1, 5):
                result = subprocess.run(
                    [sys.executable, str(script), "--path", str(state), "--output", str(output), "--summary", str(summary)],
                    env=env, capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual("Persistent optional-source incident" in result.stdout, attempt == 3)
                self.assertNotIn("::error::", result.stdout)
                self.assertEqual(json.loads(state.read_text())["sources"]["aihot-daily"]["consecutiveFailures"], attempt)
            self.assertEqual(summary.read_text().count("New persistent incidents:"), 1)
            self.assertEqual(output.read_text().splitlines(), ["notify=false", "notify=false", "notify=true", "notify=false"])

    def test_optional_source_incident_does_not_create_failed_job(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/update-site.yml").read_text()
        self.assertNotIn("persistent-source-alert:", workflow)
        self.assertIn("python scripts/collection_health.py", workflow)
        self.assertIn("run: python scripts/validate_snapshot.py", workflow)
        self.assertLess(workflow.index("run: python scripts/validate_snapshot.py"), workflow.index("run: bash scripts/persist_data.sh"))
        self.assertIn('exit 1', workflow)  # real persistence failures remain blocking

    def test_same_run_retries_do_not_escalate_or_repeat_alerts(self):
        state = {}
        for i in range(5):
            state, alerts = update_health(state, {"models-batch": "failure"}, f"retry-{i}", "run-1")
            self.assertEqual(alerts, [])
            self.assertEqual(state["sources"]["models-batch"]["consecutiveFailures"], 1)
        state, alerts = update_health(state, {"models-batch": "failure"}, "next", "run-2")
        self.assertEqual(alerts, [])
        state, alerts = update_health(state, {"models-batch": "failure"}, "third", "run-3")
        self.assertEqual(alerts, ["models-batch"])
        for run_id in ("run-3", "run-1"):
            state, alerts = update_health(state, {"models-batch": "failure"}, "retry", run_id)
            self.assertEqual(alerts, [])
            self.assertEqual(state["sources"]["models-batch"]["consecutiveFailures"], 3)
        state, alerts = update_health(state, {"models-batch": "success"}, "recovered", "run-3")
        self.assertEqual(state["sources"]["models-batch"]["consecutiveFailures"], 0)
        state, alerts = update_health(state, {"models-batch": "failure"}, "new", "run-4")
        self.assertEqual(state["sources"]["models-batch"]["consecutiveFailures"], 1)


    def test_production_episode_persists_after_scheduled_recovery(self):
        state,_=update_health({},{"models-batch":"failure"},"2026-11-27T06:00:00+00:00","100","schedule","1")
        state,_=update_health(state,{"models-batch":"failure"},"2026-11-27T06:01:00+00:00","100","schedule","2")
        self.assertEqual(state["incidentSummary"]["observedIncidents"],1)
        self.assertEqual(len(state["incidents"][0]["failedRunIds"]),1)
        self.assertEqual(len(state["incidents"][0]["failedAttempts"]),2)
        state,_=update_health(state,{"models-batch":"skipped"},"2026-11-27T06:05:00+00:00","101","schedule","1")
        self.assertEqual(state["incidentSummary"]["openIncidents"],1)
        state,_=update_health(state,{"models-batch":"success"},"2026-11-27T06:30:00+00:00","102","schedule","1")
        self.assertEqual(state["incidentSummary"]["closedIncidents"],1)
        self.assertEqual(state["incidentSummary"]["scheduledRecoveries"],1)
        self.assertEqual(state["incidentSummary"]["maxRecoverySeconds"],1800)
        self.assertEqual(state["sources"]["models-batch"]["consecutiveFailures"],0)
        self.assertEqual(state["incidents"][0]["openedAt"],"2026-11-27T06:00:00+00:00")

    def test_dispatch_is_not_automatically_certified_and_legacy_is_not_new(self):
        state,_=update_health({},{"aihot-daily":"failure"},"2026-11-27T01:00:00+00:00")
        state,_=update_health(state,{"aihot-daily":"success"},"2026-11-27T02:00:00+00:00","200","workflow_dispatch","1")
        self.assertEqual(state["incidentSummary"]["leftCensoredIncidents"],1)
        self.assertEqual(state["incidentSummary"]["observedIncidents"],0)
        self.assertIsNone(state["incidentSummary"]["scheduledRecoveryShareOfClosed"])
        state,_=update_health(state,{"aihot-daily":"failure"},"2026-11-27T03:00:00+00:00","201","schedule","1")
        state,_=update_health(state,{"aihot-daily":"success"},"2026-11-27T04:00:00+00:00","202","workflow_dispatch","1")
        self.assertEqual(state["incidentSummary"]["observedIncidents"],1)
        self.assertEqual(state["incidentSummary"]["scheduledRecoveries"],0)
        self.assertEqual(state["incidentSummary"]["otherOrUnknownTriggerRecoveries"],1)

    def test_empty_production_cohort_is_not_perfect_recovery(self):
        state,_=update_health({},{"models-batch":"success"},"2026-11-27T06:00:00+00:00","300","push","1")
        self.assertEqual(state["incidentSummary"]["observedIncidents"],0)
        self.assertIsNone(state["incidentSummary"]["scheduledRecoveryShareOfClosed"])
