import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from scripts.revid_research_quota import LocalQuota
from scripts.run_revid_personal import run

NOW = datetime(2026, 11, 28, 10, tzinfo=timezone.utc)


class PersonalRunnerTests(unittest.TestCase):
    def test_four_requests_dedup_and_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = LocalQuota(Path(directory) / "ledger.sqlite")
            ledger.initialize()
            calls = []
            def search_fn(query, key, reserve, **kw):
                if not reserve(kw["now"]):
                    return {"status": "budget-exhausted", "candidates": []}
                calls.append(query)
                self.assertTrue(kw["creative_only"])
                return {"status": "ok", "candidates": [{"url": "https://x.com/i/web/status/1",
                         "platform": "x", "views": 15000, "creativeTopics": ["cinematic"]}]}
            for _ in range(4):
                result = run(ledger, "synthetic", search_fn=search_fn, clock=lambda: NOW)
                self.assertEqual(result["statuses"], ["ok"] * 4)
                self.assertEqual(len(result["candidates"]), 1)
            self.assertEqual(len(calls), 16)
            self.assertEqual(run(ledger, "synthetic", search_fn=search_fn,
                                 clock=lambda: NOW)["statuses"], ["budget-exhausted"])

    def test_rate_limit_persists_and_stops_round(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            ledger = LocalQuota(path)
            ledger.initialize()
            calls = []
            def search_fn(query, key, reserve, **kw):
                if not reserve(kw["now"]):
                    return {"status": "budget-exhausted", "candidates": []}
                calls.append(query)
                return {"status": "rate-limited", "candidates": []}
            result = run(ledger, "synthetic", search_fn=search_fn, clock=lambda: NOW)
            self.assertEqual(result["statuses"], ["rate-limited"])
            self.assertEqual(len(calls), 1)
            self.assertFalse(LocalQuota(path).reserve(NOW + timedelta(hours=23)))
            self.assertTrue(LocalQuota(path).reserve(NOW + timedelta(hours=25)))
