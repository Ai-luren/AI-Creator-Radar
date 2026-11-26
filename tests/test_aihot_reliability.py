import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from scripts import collect_aihot


class AIHOTReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "aihot-items.json"
        self.output_patch = patch.object(collect_aihot, "OUTPUT", self.output)
        self.output_patch.start()
        self.addCleanup(self.output_patch.stop)

    def seed(self, items):
        previous = {"items": items, "etag": "demo", "fetchedAt": "2026-11-25T00:00:00Z"}
        self.output.write_text(json.dumps(previous), encoding="utf-8")
        return previous

    def response_error(self, status):
        return HTTPError(collect_aihot.API_URL, status, "test", {}, None)

    def test_empty_snapshot_is_valid_for_304(self):
        previous = self.seed([])
        with patch.object(collect_aihot.urllib.request, "urlopen", side_effect=self.response_error(304)):
            self.assertEqual(collect_aihot.collect(), (0, True))
        current = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(current["items"], [])
        self.assertEqual(current["fetchedAt"], previous["fetchedAt"])
        self.assertIn("checkedAt", current)

    def test_http_failure_preserves_existing_snapshot(self):
        self.seed([{"id": "known"}])
        before = self.output.read_bytes()
        with patch.object(collect_aihot.urllib.request, "urlopen", side_effect=self.response_error(503)):
            with self.assertRaises(HTTPError):
                collect_aihot.collect()
        self.assertEqual(self.output.read_bytes(), before)

    def test_304_without_snapshot_fails_without_creating_one(self):
        with patch.object(collect_aihot.urllib.request, "urlopen", side_effect=self.response_error(304)):
            with self.assertRaises(RuntimeError):
                collect_aihot.collect()
        self.assertFalse(self.output.exists())

    def test_dry_run_304_does_not_write(self):
        self.seed([])
        before = self.output.read_bytes()
        with patch.object(collect_aihot.urllib.request, "urlopen", side_effect=self.response_error(304)):
            self.assertEqual(collect_aihot.collect(dry_run=True), (0, True))
        self.assertEqual(self.output.read_bytes(), before)
