import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.run_collection_batch import BATCHES, run_batch


class BatchTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.data = self.root / "site/data"
        self.data.mkdir(parents=True)
        self.file = self.data / "sample.json"
        self.file.write_text('{"value": 0}')

    def test_historical_network_repair_is_maintenance_only(self):
        for group in ("models", "recovery"):
            scripts = [s for t in BATCHES[group][1] for s in t]
            self.assertNotIn("collect_historical_evidence", scripts)
            self.assertIn("collect_event_reconciliation", scripts)
        self.assertIn(("collect_historical_evidence", "collect_event_reconciliation"), BATCHES["maintenance"][1])

    def test_no_unconsumed_social_trends_or_evaluation_network_collectors(self):
        active = {script for _, transactions in BATCHES.values() for transaction in transactions for script in transaction}
        self.assertNotIn("collect_social_trends", active)
        self.assertNotIn("collect_model_evaluations", active)
        self.assertIn("collect_app_updates", active)
        self.assertIn("collect_creator_opportunities", active)

    def test_failure_rolls_back_only_its_transaction(self):
        def runner(args, **kwargs):
            script = Path(args[1]).stem
            if script == "good":
                self.file.write_text('{"value": 1}')
            elif script == "bad":
                self.file.write_text('{"value": 2}')
                (self.data / "partial.json").write_text('{}')
                raise subprocess.CalledProcessError(1, args)
            else:
                self.assertEqual(json.loads(self.file.read_text())["value"], 1)
                self.assertFalse((self.data / "partial.json").exists())
                (self.data / "later.json").write_text('{}')
        self.assertEqual(run_batch(self.root, [("good",), ("bad",), ("later",)], 10, runner), ["bad"])
        self.assertTrue((self.data / "later.json").exists())

    def test_dependent_failure_reverts_first_step_and_baseline(self):
        config = self.root / "config"
        config.mkdir()
        baseline = config / "unified-ranking-baseline.json"
        baseline.write_text('{}')
        def runner(args, **kwargs):
            self.file.write_text('{"value": 8}')
            baseline.write_text('{"changed":true}')
            if Path(args[1]).stem == "derive":
                raise subprocess.TimeoutExpired(args, 1)
        self.assertEqual(run_batch(self.root, [("fetch", "derive")], 10, runner), ["fetch+derive"])
        self.assertEqual(json.loads(self.file.read_text()), {"value": 0})
        self.assertEqual(baseline.read_text(), '{}')

    def test_invalid_json_and_deleted_snapshot_roll_back(self):
        for mode in ("corrupt", "delete"):
            def runner(args, **kwargs):
                if mode == "corrupt":
                    self.file.write_text('{')
                else:
                    self.file.unlink()
            self.assertEqual(run_batch(self.root, [(mode,)], 10, runner), [mode])
            self.assertEqual(json.loads(self.file.read_text()), {"value": 0})

    def test_budget_exhaustion_does_not_run_another_collector(self):
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
        stamps = iter([0, 11])
        self.assertEqual(run_batch(self.root, [("skip",)], 10, runner, lambda: next(stamps)), ["skip"])
        self.assertEqual(calls, [])
