"""Structural guards for the production/collection split (no network needed)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PipelineContractTests(unittest.TestCase):
    def test_publish_uses_committed_main_without_collectors(self):
        text = (ROOT / ".github/workflows/deploy-pages.yml").read_text()
        self.assertIn("workflow_call:", text)
        self.assertIn("ref: main", text)
        self.assertIn("group: radar-pages-publish", text)
        self.assertIn("node --test tests/test_overview.mjs", text)
        self.assertIn("actions/deploy-pages@", text)
        self.assertNotIn("python scripts/collect_", text)
        self.assertNotIn("git push", text)

    def test_collection_only_publishes_committed_data_and_reports_new_incidents(self):
        text = (ROOT / ".github/workflows/update-site.yml").read_text()
        self.assertIn("group: radar-data-refresh", text)
        self.assertIn("paths:", text)
        self.assertNotIn("'site/**'", text)
        self.assertIn("uses: ./.github/workflows/deploy-pages.yml", text)
        self.assertIn("needs.collect.outputs.changed == 'true'", text)
        self.assertIn("python scripts/collection_health.py", text)
        self.assertNotIn("persistent-source-alert:", text)
        self.assertNotIn("needs.collect.outputs.notify", text)
        self.assertIn("Concurrent main update won", text)
        self.assertIn("node --test tests/test_overview.mjs", text)

    def test_browser_supersedes_old_pr_runs(self):
        text = (ROOT / ".github/workflows/browser-visual.yml").read_text()
        self.assertIn("cancel-in-progress: true", text)
        self.assertIn("matrix:", text)
        self.assertIn("chromium, webkit", text)
