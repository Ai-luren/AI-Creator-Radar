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

    def test_pages_artifacts_are_isolated_by_run_and_attempt(self):
        workflow = (ROOT / ".github/workflows/deploy-pages.yml").read_text()
        caller = (ROOT / ".github/workflows/update-site.yml").read_text()
        guard = (ROOT / "scripts/wait_pages_artifact.sh").read_text()
        name = "github-pages-${{ github.run_id }}-${{ github.run_attempt }}"
        self.assertIn("name: " + name, workflow)
        self.assertIn("PAGES_ARTIFACT_NAME: " + name, workflow)
        self.assertIn("artifact_name: " + name, workflow)
        self.assertIn("steps.pages_upload.outputs.artifact_id", workflow)
        self.assertIn("actions: read", workflow)
        self.assertIn("actions: read", caller.split("  publish:", 1)[1])
        self.assertIn("bash scripts/wait_pages_artifact.sh", workflow)
        self.assertLess(workflow.index("Verify Pages artifact visibility"),
                        workflow.index("Deploy to GitHub Pages"))
        self.assertIn("seq 1 12", guard)
        self.assertIn("($matches | length) == 1", guard)
        self.assertIn("$matches[0].expired == false", guard)
        self.assertIn("($matches[0].id | tostring) == $id", guard)
        self.assertTrue(guard.rstrip().endswith("exit 1"))

    def test_browser_supersedes_old_pr_runs(self):
        text = (ROOT / ".github/workflows/browser-visual.yml").read_text()
        self.assertIn("cancel-in-progress: true", text)
        self.assertIn("matrix:", text)
        self.assertIn("chromium, webkit", text)
