import unittest

from scripts.audit_collection_timing import audit


class CollectionTimingTests(unittest.TestCase):
    def test_real_step_boundaries_and_test_output_are_separate(self):
        log = """2026-11-27T09:02:31.3601653Z ##[group]Run python scripts/run_collection_batch.py models
2026-11-27T09:06:08.2888674Z Committed transaction in working tree: models
2026-11-27T09:06:08.2891551Z Committed transaction in working tree: recovery
2026-11-27T09:06:08.3054972Z ##[group]Run test ! -e .radar-collection-fatal
2026-11-27T09:06:08.5043233Z ##[group]Run python scripts/link_model_records.py
2026-11-27T09:06:49.3490953Z ##[group]Run python scripts/collection_health.py
2026-11-27T09:06:49.5532197Z ##[group]Run python -m unittest discover -s tests -v
2026-11-27T09:06:52.6717315Z ##[warning]Rolled back fixture: TimeoutExpired
2026-11-27T09:06:52.6719588Z Committed transaction in working tree: test
"""
        result = audit(log)
        models, links = result["phases"]
        self.assertAlmostEqual(models["secondsToNextStep"], 216.945, places=3)
        self.assertAlmostEqual(links["secondsToNextStep"], 40.845, places=3)
        self.assertEqual(models["committedTransactions"], 2)
        self.assertEqual(models["rolledBackTransactions"], 0)
        self.assertIsNone(result["networkRequestCount"])
        self.assertIsNone(result["individualTransactionSeconds"])

    def test_unfinished_and_out_of_order_logs_remain_unknown(self):
        result = audit("2026-11-27T09:02:31Z ##[group]Run python scripts/run_collection_batch.py models")
        self.assertIsNone(result["phases"][0]["secondsToNextStep"])
        result = audit("2026-11-27T09:02:31Z ##[group]Run python scripts/run_collection_batch.py models\n2026-11-27T09:02:30Z ##[group]Run another step")
        self.assertIsNone(result["phases"][0]["secondsToNextStep"])
        self.assertEqual(audit("")["phases"], [])

    def test_real_failures_remain_visible(self):
        result = audit("""2026-11-27T09:02:31Z ##[group]Run python scripts/run_collection_batch.py models
2026-11-27T09:02:32Z ##[warning]Rolled back first: ValueError
2026-11-27T09:02:33Z ##[warning]Collection time budget exhausted before second
2026-11-27T09:02:34Z ##[group]Run another step""")
        phase = result["phases"][0]
        self.assertEqual(phase["rolledBackTransactions"], 1)
        self.assertEqual(phase["budgetSkippedTransactions"], 1)
        self.assertEqual(phase["committedTransactions"], 0)


if __name__ == "__main__":
    unittest.main()
