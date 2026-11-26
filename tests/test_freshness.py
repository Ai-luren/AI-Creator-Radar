import unittest
from datetime import date, datetime, timezone
from scripts.build_model_release_digest import collect_pending
from scripts.collect_models import apply_recent_model_versions


class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.family = {"id": "demo", "name": "Demo", "category": "music", "vendor": "Vendor", "legacyIds": ["legacy"]}
        self.update = {"id": "event", "modelId": "demo", "official": True,
                       "updateType": "announcement", "title": "Demo 2 coming soon",
                       "url": "https://example.com/news", "publishedAt": None,
                       "discoveredAt": "2026-11-25T10:00:00Z"}
        self.today = date(2026, 11, 26)

    def test_pending_is_visible_without_invented_publication(self):
        rows = collect_pending([self.family], [self.update], [], self.today)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["publishedAt"])
        self.assertEqual(rows[0]["modelFamilyId"], "demo")
        self.assertEqual(rows[0]["verificationStatus"], "pending")

    def test_excludes_unofficial_untracked_old_and_tool_updates(self):
        rows = [dict(self.update, official=False), dict(self.update, modelId="unknown"), dict(self.update, modelId="legacy"),
                dict(self.update, discoveredAt="2026-01-01"), dict(self.update, updateType="product-release")]
        self.assertEqual(collect_pending([self.family], rows, [], self.today), [])

    def test_duplicate_and_confirmed_release(self):
        row = dict(self.update, publishedAt="2026-11-25", updateType="model-release")
        self.assertEqual(len(collect_pending([self.family], [row, dict(row, id="other")], [], self.today)), 1)
        confirmed = [{"modelFamilyId": "demo", "publishedAt": "2026-11-25", "url": row["url"]}]
        self.assertEqual(collect_pending([self.family], [row], confirmed, self.today), [])

    def test_reject_static_asset_and_dedupe_translated_article(self):
        row = dict(self.update, title="Introducing Demo 2", publishedAt="2026-11-25")
        confirmed = [{"modelFamilyId": "demo", "modelName": "Demo 2", "publishedAt": "2026-11-25", "url": "https://example.com/en/news"}]
        self.assertEqual(collect_pending([self.family], [row], confirmed, self.today), [])
        self.assertEqual(collect_pending([self.family], [dict(row, url="https://example.com/icons.svg?v=1")], [], self.today), [])

    def test_announcement_and_model_card_do_not_mutate_catalog(self):
        models = {"demo": dict(self.family)}
        for kind in ("announcement", "model-card"):
            row = dict(self.update, modelId="demo", modelVersion="Demo 2", updateType=kind,
                       publishedAt="2026-11-25T00:00:00Z")
            self.assertEqual(apply_recent_model_versions(models, [row], datetime(2026, 11, 26, tzinfo=timezone.utc)), [])
        self.assertNotIn("versions", models["demo"])

    def test_verified_release_date_is_not_overwritten(self):
        version = {"name": "Demo 2", "id": "demo-2", "releaseDate": "2026-11-24",
                   "releaseEvidence": {"publishedAt": "2026-11-24"}}
        models = {"demo": dict(self.family, versions=[version])}
        row = dict(self.update, modelId="demo", modelVersion="Demo 2", updateType="model-release",
                   publishedAt="2026-11-25T00:00:00Z")
        self.assertEqual(apply_recent_model_versions(models, [row], datetime(2026, 11, 26, tzinfo=timezone.utc)), [])
        self.assertEqual(version["releaseDate"], "2026-11-24")
