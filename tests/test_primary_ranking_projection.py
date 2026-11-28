"""Compare the candidate against the legacy implementation on real snapshots."""
import copy
import json
import unittest
from unittest.mock import patch

from scripts import build_unified_rankings as legacy
from scripts import ranking_identity
from scripts.build_primary_ranking_projection import project, build_document


def primary_fields(document):
    return [
        {key: copy.deepcopy(category[key])
         for key in ("id", "primaryLeaderboard", "primaryLeaderboards")
         if key in category}
        for category in document["categories"]
    ]


class PrimaryRankingProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = legacy.load_inputs()
        cls.aliases = legacy.load_vendor_aliases()
        cls.keys = legacy.load_models(cls.aliases)
        cls.families = json.loads((legacy.ROOT / "site/data/models.json").read_text())
        cls.identity_inputs = ranking_identity.inputs()

    def test_real_snapshot_primary_fields_identical(self):
        baseline = json.loads(legacy.BASELINE.read_text())
        original = legacy.build_rankings(copy.deepcopy(self.inputs), copy.deepcopy(baseline))
        ranking_identity.attach_rankings(original, self.families, *self.identity_inputs)
        with patch.object(legacy, "build_rankings", side_effect=AssertionError("composite path invoked")):
            candidate = project(self.inputs, self.aliases, self.keys,
                                self.families, self.identity_inputs)
        self.assertEqual(primary_fields(original), primary_fields(candidate))
        by_id = {row["id"]: row for row in candidate["categories"]}
        self.assertEqual(set(by_id), {"image", "video", "music", "tts", "coding"})
        video = by_id["video"]["primaryLeaderboards"]
        self.assertEqual(set(video), {"text-to-video-audio", "image-to-video-audio"})
        boards = [by_id[key]["primaryLeaderboard"]
                  for key in ("image", "music", "tts", "coding")] + list(video.values())
        self.assertTrue(all(board and board["rows"] for board in boards))
        self.assertTrue(all(len(board["rows"]) <= 10 for board in boards))

    def test_complete_reader_document_without_composite_or_baseline_write(self):
        before = legacy.BASELINE.read_bytes()
        with patch.object(legacy, "build_rankings", side_effect=AssertionError("composite invoked")):
            candidate = build_document()
        self.assertEqual(legacy.BASELINE.read_bytes(), before)
        self.assertEqual(candidate["schema"], "ai-creator-radar-primary-rankings/1")
        self.assertTrue(candidate["calculatedAt"])
        self.assertNotIn("calibrations", candidate)
        self.assertNotIn("categoryAnchors", candidate)
        self.assertTrue(all("rows" not in c for c in candidate["categories"]))
        original = legacy.build_rankings(copy.deepcopy(self.inputs), json.loads(before))
        ranking_identity.attach_rankings(original, self.families, *self.identity_inputs)
        self.assertEqual(primary_fields(candidate), primary_fields(original))

    def test_empty_primary_sources_are_not_fabricated(self):
        inputs = {"reference": {}, "maomu": {}, "primary": {}, "metadata": {}}
        candidate = project(inputs, self.aliases, self.keys,
                            self.families, self.identity_inputs)
        for category in candidate["categories"]:
            self.assertIsNone(category["primaryLeaderboard"])
            for board in category.get("primaryLeaderboards", {}).values():
                self.assertIsNone(board)

    def test_missing_video_task_does_not_break_other_task(self):
        inputs = copy.deepcopy(self.inputs)
        inputs["primary"].pop("aa-video-i2v-audio-20261125")
        candidate = project(inputs, self.aliases, self.keys,
                            self.families, self.identity_inputs)
        video = next(row for row in candidate["categories"] if row["id"] == "video")
        self.assertIsNone(video["primaryLeaderboards"]["image-to-video-audio"])
        self.assertTrue(video["primaryLeaderboard"]["rows"])
        self.assertTrue(all("modelLinkStatus" in row for row in video["primaryLeaderboard"]["rows"]))
        self.assertEqual(video["primaryLeaderboard"], video["primaryLeaderboards"]["text-to-video-audio"])


if __name__ == "__main__":
    unittest.main()
