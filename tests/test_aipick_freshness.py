import unittest
from unittest.mock import patch
from scripts import collect_aipick as collector

class AIPickFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.previous={"fetchedAt":"2026-11-27T00:00:00+00:00","items":[],"hotTopics":[{"title":"old"}],"etags":{"items":"a","hotTopics":"b"}}

    def test_partial_failure_preserves_last_complete_stamp_even_with_empty_valid_list(self):
        with patch.object(collector,"read_existing",return_value=self.previous), patch.object(collector,"request_json",side_effect=[OSError("offline"),({"items":[{"title":"new"}]},"c",False)]), patch.object(collector,"atomic_write") as write:
            result=collector.collect()
        self.assertEqual(result["fetchedAt"],self.previous["fetchedAt"])
        self.assertEqual(result["items"],[])
        self.assertEqual(result["hotTopics"],[{"title":"new"}])
        self.assertTrue(result["errors"])
        write.assert_called_once_with(result)

    def test_two_successful_304_revalidate_complete_snapshot(self):
        with patch.object(collector,"read_existing",return_value=self.previous), patch.object(collector,"request_json",side_effect=[(None,"a",True),(None,"b",True)]) as fetch:
            result=collector.collect(dry_run=True)
        self.assertEqual(result["fetchedAt"],result["checkedAt"])
        self.assertEqual(result["unchanged"],["items","hotTopics"])
        self.assertEqual(result["errors"],[])
        self.assertEqual(fetch.call_count,2)

    def test_304_without_snapshot_rejected(self):
        with patch.object(collector,"read_existing",return_value={"etags":{"items":"a"}}), patch.object(collector,"request_json",return_value=(None,"a",True)) as fetch:
            with self.assertRaises(RuntimeError):
                collector.collect(dry_run=True)
        self.assertEqual(fetch.call_args.args[1],"")

    def test_cli_reports_partial_failure(self):
        with patch.object(collector,"collect",return_value={"items":[],"hotTopics":[],"unchanged":[],"errors":["items: offline"]}), patch("sys.argv",["collect_aipick.py"]):
            self.assertEqual(collector.main(),1)
