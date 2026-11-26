import json
from pathlib import Path
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

from scripts.preflight import sync_digest
from scripts.ci_changed_scopes import scopes


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'digest.json'
        self.old = {'windowEnd': '2026-11-26', 'updatedAt': 'old', 'items': [1]}
        self.path.write_text(json.dumps(self.old))

    def test_equal_snapshot_preserves_bytes_and_window(self):
        raw = self.path.read_bytes()
        def build(day):
            self.assertEqual(day, date(2026, 11, 26))
            return {**self.old, 'updatedAt': 'new'}
        self.assertFalse(sync_digest(self.path, build, True))
        self.assertEqual(raw, self.path.read_bytes())

    def test_stale_snapshot_check_then_repair(self):
        def build(day):
            return {**self.old, 'items': [2]}
        with self.assertRaisesRegex(ValueError, 'stale'):
            sync_digest(self.path, build)
        self.assertEqual(json.loads(self.path.read_text()), self.old)
        self.assertTrue(sync_digest(self.path, build, True))
        self.assertEqual(json.loads(self.path.read_text())['items'], [2])
        self.assertFalse(sync_digest(self.path, build, True))

    def test_failed_build_or_replace_never_destroys_snapshot(self):
        raw = self.path.read_bytes()
        def broken(day):
            raise RuntimeError('bad canonical input')
        with self.assertRaises(RuntimeError):
            sync_digest(self.path, broken, True)
        with patch('scripts.preflight.os.replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                sync_digest(self.path, lambda day: {**self.old, 'items': [2]}, True)
        self.assertEqual(raw, self.path.read_bytes())
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_probe_scope_does_not_depend_on_regex_or_shell(self):
        self.assertEqual(scopes(['README.md', 'archive/scripts/collect_models.py']), {'models': False, 'opportunities': False})
        self.assertEqual(scopes(['scripts/collect_model_intake.py', 'config/creator-opportunity-sources.json']), {'models': True, 'opportunities': True})
        self.assertEqual(scopes(['scripts/build_model_release_digest.py']), {'models': True, 'opportunities': False})
