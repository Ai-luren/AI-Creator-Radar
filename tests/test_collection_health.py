import unittest

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
