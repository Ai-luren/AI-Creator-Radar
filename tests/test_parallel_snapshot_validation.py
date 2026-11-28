import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from scripts.validate_snapshot import validate


class ParallelSnapshotValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ("site", "config", "scripts", "tests"):
            (self.root / name).mkdir()
        (self.root / "site/snapshot.json").write_text("original")
        (self.root / "tests/test_overview.mjs").write_text("// fixture")
        self.calls = []

    def run_validation(self, fail=None):
        def runner(command, **kwargs):
            cwd = kwargs["cwd"]
            self.calls.append((command, cwd))
            if command[1] == "-m":
                self.assertEqual(cwd, self.root)
            else:
                self.assertNotEqual(cwd, self.root)
                self.assertEqual((cwd / "site/snapshot.json").read_text(), "original")
                self.assertTrue((cwd / "tests/test_overview.mjs").is_file())
            return SimpleNamespace(returncode=1 if fail in command else 0, stdout="gate output")
        with redirect_stdout(io.StringIO()):
            return validate(self.root, runner=runner)

    def test_all_four_existing_gates_are_required(self):
        self.assertEqual(self.run_validation(), 0)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual((self.root / "site/snapshot.json").read_text(), "original")

    def test_failure_in_either_lane_blocks_publication(self):
        for failure in ("unittest", "tests/test_overview.mjs", "scripts/validate_model_links.py", "scripts/audit_model_completeness.py"):
            with self.subTest(failure=failure):
                self.calls.clear()
                self.assertEqual(self.run_validation(failure), 1)
                self.assertEqual(len(self.calls), 4)

    def test_lane_launch_failure_blocks_publication(self):
        def runner(command, **kwargs):
            if command[0] == "node":
                raise OSError("node unavailable")
            return SimpleNamespace(returncode=0, stdout="")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(validate(self.root, runner=runner), 1)
