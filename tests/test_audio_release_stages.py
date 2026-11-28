"""Keep reviewed service launches separate from first-release records."""
from datetime import date
import json
import unittest
from pathlib import Path

from scripts.build_model_release_digest import build, collect_verified_stages, reviewed_pending_disposition, REVIEWED_PENDING_DISPOSITIONS

ROOT = Path(__file__).resolve().parents[1]


class AudioStageTests(unittest.TestCase):
    def test_known_stages_are_distinct_from_releases(self):
        result = build(date(2026, 11, 26))
        ids = {r["modelVersionId"] for r in result["verifiedStages"]}
        self.assertIn("qwen-audio-3-1-live", ids)
        self.assertIn("mureka-remix-v9-5", ids)
        self.assertIn("gpt-live-1-1", ids)
        self.assertTrue(any(r["modelVersionId"] == "scribe-v3-live-medical" for r in result["items"]))
        self.assertFalse(any(r["modelFamilyId"] == "suno" and r["title"] == "Introducing the v6 family of music models." for r in result["pending"]))
        self.assertFalse(ids.intersection(r["modelVersionId"] for r in result["items"]))
        self.assertTrue(all("publishedAt" not in r for r in result["verifiedStages"]))
        expected = {
            "qwen-audio-3-1-live": ("api-availability", "2026-11-23"),
            "mureka-remix-v9-5": ("api-availability", "2026-11-12"),
            "gpt-live-1-1": ("api-availability", "2026-11-20"),
            "mai-image-2-7": ("preview", "2026-11-17"),
            "mai-image-2-7-flash": ("preview", "2026-11-17"),
        }
        self.assertEqual(len(result["verifiedStages"]), len(expected))
        self.assertEqual(
            {r["modelVersionId"]: (r["stage"], r["stageDate"]) for r in result["verifiedStages"]},
            expected,
        )
        for row in result["verifiedStages"]:
            if row["stage"] == "preview":
                self.assertEqual(row["url"], "https://microsoft.ai/news/introducing-mai-image-2-7/")

    def test_reviewed_stages_and_non_model_updates_not_pending(self):
        result=build(date(2026,11,28))
        self.assertFalse(set(REVIEWED_PENDING_DISPOSITIONS).intersection(r["id"] for r in result["pending"]))
        for uid,(family,day,url,title,stage_id) in REVIEWED_PENDING_DISPOSITIONS.items():
            row={"id":uid,"modelId":family,"publishedAt":day,"url":url,"title":title,"official":True}
            self.assertIsNotNone(reviewed_pending_disposition(row,result["verifiedStages"]))
            self.assertIsNone(reviewed_pending_disposition({**row,"title":title+" changed"},result["verifiedStages"]))
            self.assertIsNone(reviewed_pending_disposition({**row,"publishedAt":"2026-11-29"},result["verifiedStages"]))
            if stage_id!="non-model":
                self.assertIsNone(reviewed_pending_disposition(row,[]))

    def test_window_and_unknown_stages(self):
        families = json.loads((ROOT / "site/data/models.json").read_text(encoding="utf-8"))
        self.assertEqual(collect_verified_stages(families, date(2026, 10, 27)), [])
        self.assertEqual(collect_verified_stages(families, date(2027, 1, 1)), [])
        self.assertEqual(collect_verified_stages([{"id": "mureka", "versions": [{"id": "mureka-remix-v9-5", "historicalMilestones": [{"chronicleAuditId": "unreviewed", "datePrecision": "day", "date": "2026-11-12", "stage": "api-availability", "verifiedAt": "2026-11-26", "sourceUrl": "https://example.com"}]}]}], date(2026, 11, 26)), [])

    def test_digest_matches_canonical_snapshot(self):
        actual = json.loads((ROOT / "site/data/model-releases-30d.json").read_text(encoding="utf-8"))
        expected = build(date.fromisoformat(actual["windowEnd"]))
        actual.pop("updatedAt", None)
        expected.pop("updatedAt", None)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
