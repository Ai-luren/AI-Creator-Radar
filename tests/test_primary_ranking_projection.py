"""Compare the candidate against the legacy implementation on real snapshots."""
import copy
import json
import unittest
from unittest.mock import patch

from scripts import build_unified_rankings as legacy
from scripts import ranking_identity
from scripts.build_primary_ranking_projection import project


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

    def test_empty_primary_sources_are_not_fabricated(self):
        inputs = {"reference": {}, "maomu": {}, "primary": {}, "metadata": {}}
        candidate = project(inputs, self.aliases, self.keys,
                            self.families, self.identity_inputs)
        for category in candidate["categories"]:
            self.assertIsNone(category["primaryLeaderboard"])
            for board in category.get("primaryLeaderboards", {}).values():
                self.assertIsNone(board)


if __name__ == "__main__":
    unittest.main()
