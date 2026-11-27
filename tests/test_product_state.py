import json
import unittest
from datetime import datetime, timezone, timedelta
from scripts.collect_product_state import parse_catalog, observe

class ProductStateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 27, tzinfo=timezone.utc)
        self.spec = {"id":"test","type":"models-dev","url":"https://models.dev/api.json",
                     "providerIds":["demo"],"minRows":1,"minIntervalMinutes":60,"attribution":{"name":"demo"}}
        self.config = {"sources":[self.spec]}
        self.rows = {"demo|v1":{"providerId":"demo","productId":"v1","name":"Demo 1"}}
        self.families = [{"id":"demo","versions":[{"id":"v1","name":"Demo 1"}]}]

    def run_observe(self, rows, old=None, hours=0):
        return observe(self.config, old or {}, self.families, self.now+timedelta(hours=hours), lambda _: rows)

    def test_catalog_parser_separates_provider_metadata_from_release_claim(self):
        rows = parse_catalog(json.dumps({"demo":{"models":{"v1":{"id":"v1","name":"Demo 1","release_date":"2026-11"}}}}), self.spec)
        self.assertEqual(rows["demo|v1"]["reportedReleaseDate"], "2026-11")
        self.assertNotIn("releaseDate", rows["demo|v1"])
        with self.assertRaises(ValueError):
            parse_catalog("{}", self.spec)

    def test_baseline_does_not_create_mass_new_events_and_delta_is_idempotent(self):
        first = self.run_observe(self.rows)
        self.assertEqual(first["events"], [])
        added = {**self.rows, "demo|v2":{"providerId":"demo","productId":"v2","name":"Demo 2"}}
        second = self.run_observe(added, first, 1)
        self.assertEqual([e["eventType"] for e in second["events"]], ["added-to-catalog"])
        self.assertIsNone(second["events"][0]["identity"])
        third = self.run_observe(added, second, 2)
        self.assertEqual(third["events"], second["events"])
        self.assertEqual(third["summary"]["newEvents"], 0)

    def test_catalog_failure_and_mass_drop_do_not_remove_records(self):
        baseline = self.run_observe(self.rows)
        def denied(_):
            raise OSError("403")
        failed = observe(self.config, baseline, self.families, self.now+timedelta(hours=1), denied)
        self.assertEqual(failed["sources"][0]["entries"], baseline["sources"][0]["entries"])
        self.assertEqual(failed["sources"][0]["lastSuccessAt"], baseline["sources"][0]["lastSuccessAt"])
        self.assertEqual(failed["events"], [])
        self.assertTrue(self.run_observe(self.rows, failed, 1)["sources"][0]["deferred"])
        drop = self.run_observe({"demo|v2":{"providerId":"demo","productId":"v2","name":"Demo 2"}}, baseline, 1)
        self.assertIn("disappearance", drop["sources"][0]["error"])

    def test_absence_requires_two_successful_observations_and_is_not_withdrawal(self):
        rows = {f"demo|v{i}":{"providerId":"demo","productId":f"v{i}","name":f"Demo {i}"} for i in range(6)}
        first = self.run_observe(rows)
        missing = {k:v for k,v in rows.items() if k!="demo|v0"}
        second = self.run_observe(missing, first, 1)
        self.assertEqual(second["events"], [])
        third = self.run_observe(missing, second, 2)
        self.assertEqual(third["events"][0]["eventType"], "absent-from-catalog")
        fourth = self.run_observe(rows, third, 3)
        self.assertEqual(fourth["events"][0]["eventType"], "reappeared-in-catalog")

    def test_recent_baseline_claim_is_distinct_from_new_addition(self):
        rows = {"demo|v1":{**self.rows["demo|v1"],"reportedReleaseDate":"2026-11-22"}}
        first = self.run_observe(rows)
        self.assertEqual(first["events"][0]["eventType"], "baseline-recent-reported-date")
        self.assertEqual(first["events"][0]["claimType"], "catalog-observation")
        self.assertEqual(first["events"][0]["identity"]["modelVersionId"], "v1")

    def test_openrouter_created_is_not_a_release_date(self):
        spec = {**self.spec, "type":"openrouter"}
        rows = parse_catalog(json.dumps({"data":[{"id":"demo/v1","name":"Demo 1","created":1700000000}]}), spec)
        self.assertIn("providerRecordCreatedAt", rows["demo|demo/v1"])
        self.assertNotIn("reportedReleaseDate", rows["demo|demo/v1"])
