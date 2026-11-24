import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ModelLibrarySchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = json.loads((ROOT / "site/data-v3/models.json").read_text())
        cls.by_id = {model["id"]: model for model in cls.models}
        cls.archive = json.loads((ROOT / "archive/model-library-excluded-v4.json").read_text())
        cls.maomu = json.loads((ROOT / "site/data-v4/maomu-rankings.json").read_text())
        cls.reference = json.loads((ROOT / "site/data-v3/reference-rankings.json").read_text())

    def test_family_and_variant_ids_are_unique_and_nonempty(self):
        self.assertEqual(len(self.by_id), len(self.models))
        for family in self.models:
            self.assertTrue(family["versions"], family["id"])
            ids = [version["id"] for version in family["versions"]]
            self.assertEqual(len(ids), len(set(ids)), family["id"])
            self.assertTrue(all(version.get("name") for version in family["versions"]))

    def test_family_merges_keep_every_legacy_record_id(self):
        legacy = [old_id for family in self.models for old_id in family.get("legacyIds", [])]
        self.assertEqual(len(legacy), len(set(legacy)))
        for old_id in ("wan-2-2", "wan-2-7", "wan-3", "qwen-image-3", "flux3-image", "agnes-video-25-flash"):
            self.assertIn(old_id, legacy)

    def test_distinct_modalities_and_products_stay_separate(self):
        self.assertEqual(self.by_id["kling"]["category"], "video")
        self.assertEqual(self.by_id["kling-image"]["category"], "image")
        self.assertNotEqual(self.by_id["hailuo"]["id"], self.by_id["minimax-h3"]["id"])
        self.assertEqual(self.by_id["gemini-omni-flash"]["category"], "video")
        self.assertEqual(self.by_id["muse-image"]["category"], "image")
        self.assertEqual(self.by_id["muse-video"]["category"], "video")
        self.assertEqual(self.by_id["muse"]["category"], "llm")
        self.assertIn("pixverse-world", self.by_id)
        self.assertEqual(self.by_id["seed-realtime"]["category"], "audio")
        self.assertEqual(self.by_id["qwen-audio-realtime"]["category"], "audio")
        self.assertNotIn("pika-h3-flex", self.by_id)
        self.assertNotIn("minimax-h3-max", self.by_id)
        self.assertEqual(self.by_id["minimax-h3"]["vendor"], "MiniMax")
        self.assertEqual([v["id"] for v in self.by_id["minimax-h3"]["versions"]], ["h3"])

    def test_ambiguous_family_rows_are_scoped_to_the_named_variant(self):
        def child_names(family_id, variant_name):
            version = next(v for v in self.by_id[family_id]["versions"] if v["name"] == variant_name)
            return {alias["name"] for alias in version.get("leaderboardAliases", [])}

        self.assertTrue(any("GPT Image 2.6" in name for name in child_names("gpt-image", "GPT Image 2.6 Sunburst")))
        self.assertFalse(any("GPT Image 2.5" in name or "GPT Image 2.6" in name for name in child_names("gpt-image", "GPT Image 2")))
        self.assertTrue(any("9B" in name for name in child_names("flux", "FLUX.2 [klein] 9B")))
        self.assertTrue(any("4B" in name for name in child_names("flux", "FLUX.2 [klein] 4B")))
        self.assertFalse(any("Klein" in name for name in child_names("flux", "FLUX 3 Image")))
        self.assertFalse(any("2.7" in name for name in child_names("qwen-image", "Qwen-Image 2.1")))
        self.assertTrue(any("M2.7" in name for name in child_names("minimax-llm", "MiniMax M2.7")))
        self.assertFalse(any("M2.7" in name for name in child_names("minimax-llm", "MiniMax M2")))
        self.assertTrue(any("Omni" in name for name in child_names("kling", "Kling 3.0 Omni")))
        self.assertFalse(any("Omni" in name for name in child_names("kling", "Kling 3.0")))
        self.assertTrue(any("LTX-2.3 Fast" == name for name in child_names("ltx", "LTX-2.3 Fast")))
        self.assertNotIn("hyperflow-h3", self.by_id)
        self.assertEqual({v["id"] for v in self.archive.get("excludedVariants", [])}, {"h3-max", "h3-flex-pika"})
        self.assertTrue(any("2.0-Pro (2026-06-22)" in name for name in child_names("qwen-image", "Qwen Image 2.0 Pro · 榜单标注 2026-06-22")))

    def test_image_edit_and_generation_variants_have_specific_rows(self):
        def child(family_id, variant_name):
            return next(v for v in self.by_id[family_id]["versions"] if v["name"] == variant_name)

        edit = self.by_id["qwen-image-edit"]
        self.assertTrue(all(v.get("leaderboardAliases") for v in edit["versions"]))
        self.assertTrue(child("nano-banana", "Nano Banana")["leaderboardAliases"])
        self.assertTrue(child("nano-banana", "Nano Banana 2.1")["leaderboardAliases"])
        self.assertFalse(any("Gemini 2.5 Flash Image" in a["name"] for a in child("nano-banana", "Nano Banana 2")["leaderboardAliases"]))
        self.assertFalse(any("Text to Image" in a["name"] for a in child("wan-image", "Wan 2.6 Image")["leaderboardAliases"]))
        self.assertTrue(child("wan-image", "Wan2.6 Text to Image")["leaderboardAliases"])

    def test_child_aliases_use_known_boards_and_are_not_duplicated(self):
        boards = {}
        for category in self.maomu.get("categories", []):
            for board in category.get("boards", []):
                boards[("maomu", board["id"])] = board
        for board in self.reference.get("boards", []):
            boards[("reference", board["id"])] = board
        for family in self.models:
            for version in family.get("versions", []):
                keys = set()
                for alias in version.get("leaderboardAliases", []):
                    key = (alias["source"], alias["boardId"], alias["name"])
                    self.assertNotIn(key, keys, (family["id"], version["name"], alias))
                    keys.add(key)
                    self.assertIn((alias["source"], alias["boardId"]), boards,
                                  (family["id"], version["name"], alias))
                    self.assertTrue(alias.get("name"), (family["id"], version["name"], alias))

    def test_family_ranking_aliases_reference_known_boards(self):
        boards = {}
        for category in self.maomu.get("categories", []):
            for board in category.get("boards", []):
                boards[("maomu", board["id"])] = board
        for board in self.reference.get("boards", []):
            boards[("reference", board["id"])] = board
        for family in self.models:
            for alias in family.get("leaderboardAliases", []):
                key = (alias["source"], alias["boardId"])
                self.assertIn(key, boards, (family["id"], alias))
                self.assertTrue(alias.get("name"), (family["id"], alias))
                self.assertGreater(int(alias.get("rank", 0)), 0, (family["id"], alias))

    def test_model_ranking_evidence_uses_current_snapshot_rank(self):
        html = (ROOT / "site/preview-v4.html").read_text()
        self.assertIn("var row=(board.rows||[]).find(function(r){return r.name===a.name})", html)
        self.assertIn("Object.assign({},a,{rank:row.rank})", html)
        self.assertIn("return row&&Number(row.rank)>0?", html)

    def test_production_and_v3_catalogs_match(self):
        production = json.loads((ROOT / "site/data/models.json").read_text())
        self.assertEqual(self.models, production)

    def test_composite_sort_uses_each_category_board_once_and_surfaces_top_ten(self):
        html = (ROOT / "site/preview-v4.html").read_text()
        self.assertNotIn("data-model-rank-board", html)
        self.assertIn("function modelCompositeFor", html)
        self.assertIn("综合参考第", html)

    def test_music_and_tts_categories_use_existing_reference_snapshots(self):
        html = (ROOT / "site/preview-v4.html").read_text()
        reference_boards = {board["id"]: board for board in self.reference["boards"]}
        self.assertIn("music-aa-instrumental-aurion-20261112", reference_boards)
        self.assertIn("music-aa-vocal-aurion-202610", reference_boards)
        self.assertIn("speech", reference_boards)
        self.assertIn("category==='music'", html)
        self.assertIn("category==='tts'", html)
        self.assertIn("人声数据较少且单独评测", html)
        self.assertIn("闭源厂商及不同测试条件不在同一名次体系内", html)
        self.assertTrue(any(a["boardId"] == "music-aa-instrumental-aurion-20261112"
                            for a in next(v for v in self.by_id["suno"]["versions"] if v["id"] == "suno-v6")["leaderboardAliases"]))
        self.assertTrue(any(a["boardId"] == "speech"
                            for a in next(v for v in self.by_id["fish-audio-drama"]["versions"] if v["id"] == "3-preview")["leaderboardAliases"]))
        self.assertIn("展开型号与变体", html)

        def ordered_top_ten(category_id, model_category):
            category = next(c for c in self.maomu["categories"] if c["id"] == category_id)
            boards = category["boards"]
            scored = []
            for family in self.models:
                if family["category"] != model_category:
                    continue
                percentiles = []
                for board in boards:
                    matches = [a for a in family.get("leaderboardAliases", [])
                               if a.get("source") == "maomu" and a.get("boardId") == board["id"]
                               and int(a.get("rank", 0)) > 0]
                    if matches:
                        rank = min(int(a["rank"]) for a in matches)
                        n = len(board.get("rows", []))
                        percentiles.append(100 * (1 - (rank - 1) / max(n - 1, 1)))
                if not percentiles:
                    continue
                percentiles.sort()
                mid = len(percentiles) // 2
                median = percentiles[mid] if len(percentiles) % 2 else (percentiles[mid - 1] + percentiles[mid]) / 2
                coverage = len(percentiles) / len(boards)
                score = median * coverage + 50 * (1 - coverage)
                scored.append((score, family["name"]))
            return [name for _, name in sorted(scored, reverse=True)[:10]]

        images = ordered_top_ten("image", "image")
        videos = ordered_top_ten("video", "video")
        self.assertEqual(images[:5], ["GPT Image", "MAI-Image", "Nano Banana", "Grok Imagine Image", "Seedream"])
        self.assertIn("Kling Image", images)
        self.assertEqual(videos[:4], ["Seedance", "Gemini Omni Flash", "MiniMax H3", "Wan"])
        self.assertEqual(len(images), 10)
        self.assertEqual(len(videos), 10)

    def test_requested_model_exclusions_are_archived_and_not_in_active_catalog(self):
        excluded_ids = {model["id"] for model in self.archive.get("models", [])}
        self.assertTrue({"ray3-14", "ideogram", "wan-2-2", "wan-2-7", "wan-3", "flux3-image", "qwen-image-3"}.issubset(excluded_ids))
        self.assertTrue(excluded_ids.isdisjoint(self.by_id))
        self.assertNotIn("h3-max", {v["id"] for v in self.by_id["minimax-h3"]["versions"]})
        self.assertNotIn("h3-flex-pika", {v["id"] for v in self.by_id["minimax-h3"]["versions"]})


if __name__ == "__main__":
    unittest.main()
