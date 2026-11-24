import importlib.util
import unittest
from unittest.mock import patch
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_model_resources.py"
SPEC = importlib.util.spec_from_file_location("check_model_resources", MODULE_PATH)
resources = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resources)


class ModelResourceCheckTests(unittest.TestCase):
    def test_status_classification_does_not_mislabel_access_blocks_as_dead(self):
        self.assertEqual(resources.classify_status(200), "available")
        self.assertEqual(resources.classify_status(302), "available")
        self.assertEqual(resources.classify_status(403), "restricted")
        self.assertEqual(resources.classify_status(429), "restricted")
        self.assertEqual(resources.classify_status(404), "missing")
        self.assertEqual(resources.classify_status(None, "TimeoutError"), "unknown")

    def test_gathers_unique_urls_and_only_official_tutorials(self):
        practice = {
            "models": [{"model": "M1", "vendor": "Vendor", "officialUrl": "https://example.com/model", "apiUrl": "https://example.com/api"}],
            "cases": [{"model": "M1", "url": "https://example.com/demo"}],
        }
        tutorials = [
            {"model": "M1", "url": "https://example.com/tutorial", "official": True},
            {"model": "M1", "url": "https://example.com/unverified", "official": False},
        ]
        found = resources.gather_resources(practice, tutorials)
        self.assertEqual(len(found), 4)
        self.assertNotIn("https://example.com/unverified", [item["url"] for item in found])
        kinds = {ref["kind"] for item in found for ref in item["references"]}
        self.assertEqual(kinds, {"模型说明", "API", "官方演示", "官方教程"})

    def test_retries_head_not_found_with_get_before_marking_a_link_dead(self):
        url = "https://docs.example/guide"
        with patch.object(resources, "_fetch_status", side_effect=[(404, url, ""), (200, url, "")]):
            self.assertEqual(resources.probe(url)["status"], "available")


if __name__ == "__main__":
    unittest.main()
