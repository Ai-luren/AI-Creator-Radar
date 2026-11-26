import json
import unittest
from pathlib import Path
from scripts.check_creator_links import gather_links

DATA = Path(__file__).resolve().parents[1] / "site/data"


class CreatorLinksTests(unittest.TestCase):
    def test_current_data_and_deduplication(self):
        contests = json.loads((DATA / "creator-contests.json").read_text())
        platforms = json.loads((DATA / "social-platforms.json").read_text())
        rows = gather_links(contests, platforms)
        self.assertGreater(len(rows), 30)
        self.assertEqual(len(rows), len({r["url"] for r in rows}))
        self.assertTrue(all(r["url"].startswith("https://") for r in rows))

    def test_reject_naive_and_wrong_date_deadline(self):
        base = {"id":"x","category":"video","region":"global","review":"official-page",
                "deadlineDate":"2026-11-26","sourceUrl":"https://example.com/rules",
                "entryUrl":"https://example.com/apply"}
        for deadline in ("2026-11-26T19:00:00", "2026-11-27T19:00:00Z"):
            with self.assertRaises(ValueError):
                gather_links({"items":[{**base,"deadlineAt":deadline}]}, [])

    def test_links_do_not_claim_application_status(self):
        rows = gather_links({"items":[]}, [{"id":"p","creatorPrograms":{"global":{"url":"https://example.com/#apply","sourceUrl":"https://example.com/","programName":"P"}}}])
        self.assertEqual(len(rows),1)
        self.assertNotIn("applicationStatus",rows[0])
