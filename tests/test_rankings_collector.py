import unittest

from scripts.collect_rankings import build_snapshot, compact_arena_row, merge_arena_boards


class RankingsCollectorTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "schema": "fai-published-model-board-snapshot/1",
            "publishedAt": "2026-11-21T16:51:36.557Z",
            "synchronization": {"lastCheckedAt": "2026-11-22T08:52:22.204Z", "status": "healthy"},
            "boards": [
                {
                    "id": "image",
                    "name": "Text to Image",
                    "kind": "image",
                    "task": "text-to-image",
                    "source": {"name": "Artificial Analysis", "url": "https://artificialanalysis.ai/"},
                    "rows": [
                        {
                            "rank": 1,
                            "tool": {"name": "Example Image", "provider": "Example", "releasedAt": "2026-11-01", "officialUrl": "https://example.com/model"},
                            "elo": 1200,
                            "comparisons": 321,
                            "ciLow": 1180,
                            "ciHigh": 1220,
                            "price": 2.5,
                            "priceUnit": "$/image",
                            "openWeights": True,
                        }
                    ],
                },
                {"id": "llm", "name": "Language", "kind": "llm", "rows": [{"rank": 1}]},
                {
                    "id": "video",
                    "name": "Text to Video",
                    "kind": "video",
                    "task": "text-to-video",
                    "rows": [{"rank": 1, "tool": {"name": "Example Video"}, "elo": 1100}],
                },
                {
                    "id": "speech",
                    "name": "Provider Voice",
                    "kind": "speech",
                    "task": "text-to-speech",
                    "rows": [{"rank": 1, "tool": {"name": "Example Voice"}, "elo": 1090}],
                },
                {"id": "empty-speech", "name": "Empty Speech", "kind": "speech", "rows": []},
            ],
        }

    def test_keeps_populated_image_video_and_speech_boards(self):
        result = build_snapshot(self.payload, "2026-11-22T09:00:00Z")

        self.assertEqual([board["id"] for board in result["boards"]], ["image", "video", "speech"])
        self.assertEqual(len(result["boards"]), 3)

    def test_normalizes_rank_fields_for_local_display(self):
        result = build_snapshot(self.payload, "2026-11-22T09:00:00Z")
        row = result["boards"][0]["rows"][0]

        self.assertEqual(row["name"], "Example Image")
        self.assertEqual(row["provider"], "Example")
        self.assertEqual(row["elo"], 1200)
        self.assertTrue(row["openWeights"])
        self.assertEqual(result["providerUrl"], "https://fai.fashion/leaderboard")

    def test_rejects_snapshot_without_image_or_video_rows(self):
        self.payload["boards"] = [
            {"id": "empty-image", "kind": "image", "rows": []},
            {"id": "language", "kind": "llm", "rows": [{"rank": 1}]},
        ]

        with self.assertRaisesRegex(ValueError, "missing video or image"):
            build_snapshot(self.payload, "2026-11-22T09:00:00Z")

    def test_normalizes_official_arena_dataset_rows_for_table_display(self):
        row = compact_arena_row({
            "model_name": "Example Image Edit",
            "organization": "example-lab",
            "license": "Open Weights",
            "rating": 1300.5,
            "rating_lower": 1290.5,
            "rating_upper": 1310.5,
            "vote_count": 420,
            "rank": 1,
        })

        self.assertEqual(row["name"], "Example Image Edit")
        self.assertEqual(row["provider"], "example-lab")
        self.assertEqual(row["elo"], 1300.5)
        self.assertEqual(row["ciLow"], 1290.5)
        self.assertEqual(row["comparisons"], 420)
        self.assertEqual(row["license"], "Open Weights")

    def test_merges_arena_boards_without_replacing_fai_snapshot(self):
        snapshot = build_snapshot(self.payload, "2026-11-22T09:00:00Z")
        arena = {"id": "arena-text-to-image", "source": {"id": "arena"}, "rows": [{"rank": 1}]}

        result = merge_arena_boards(snapshot, [arena])

        self.assertEqual([board["id"] for board in result["boards"]], ["image", "video", "speech", "arena-text-to-image"])


if __name__ == "__main__":
    unittest.main()
