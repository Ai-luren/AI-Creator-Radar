import unittest
from datetime import datetime, timezone

from scripts.collect_creator_opportunities import Page, candidates, program_signal, scan
from scripts.check_creator_links import gather_links


def page(html):
    result = Page()
    result.feed(html)
    return result


class CreatorOpportunityTests(unittest.TestCase):
    def setUp(self):
        self.source = {"id": "demo", "name": "Demo", "url": "https://example.com/",
                       "pathPattern": "/contests/[^/]+", "provenance": "directory"}
        self.config = {"contests": [self.source], "programs": [
            {"platformId": "demo", "scope": "global", "url": "https://example.com/program"}]}
        self.now = datetime(2026, 11, 26, tzinfo=timezone.utc)

    def test_candidates_exclude_existing_external_and_unrelated_links(self):
        html = """
        <a href="/contests/new">AI film competition</a>
        <a href="/contests/new#rules">AI film competition</a>
        <a href="/contests/known">Known contest</a>
        <a href="https://other.example/contests/new">External contest</a>
        <a href="/about">AI contest</a>
        <a href="/contests/profile">Profile info</a>
        <script>fake competition</script>
        """
        rows = candidates(self.source, page(html), self.source["url"],
                          {"https://example.com/contests/known"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["review"], "pending")
        self.assertIsNone(rows[0]["deadlineDate"])

    def test_conflicting_signals_are_ambiguous(self):
        self.assertEqual(program_signal(page("<p>Apply now. Applications closed.</p>"))["signal"], "ambiguous")
        self.assertEqual(program_signal(page("<script>Apply now</script><p>Welcome</p>"))["signal"], "unconfirmed")
        self.assertEqual(program_signal(page("<a>Apply now</a>"))["signal"], "application-signal")
        self.assertEqual(program_signal(page("<p>Invitation only</p>"))["signal"], "invitation-signal")

    def test_failed_scan_retains_previous_candidates_without_promoting(self):
        def fetch(url):
            return page('<a href="/contests/new">AI film contest</a>'), url
        catalog = {"items": []}
        first = scan(self.config, catalog, {}, self.now, fetch)
        def fail(url):
            raise TimeoutError("offline")
        second = scan(self.config, catalog, first, self.now, fail)
        self.assertEqual(first["candidates"], second["candidates"])
        self.assertEqual(second["sources"][0]["status"], "failed")
        self.assertEqual(second["programSignals"][0]["signal"], "unconfirmed")
        self.assertEqual(catalog, {"items": []})

    def test_review_requires_date_source_and_note(self):
        platforms = [{"id": "demo", "creatorPrograms": {"global": {
            "programName": "Demo", "url": "https://example.com",
            "applicationReview": {"status": "open"}}}}]
        with self.assertRaises(ValueError):
            gather_links({"items": []}, platforms)

    def test_review_source_included_in_link_validation(self):
        platforms = [{"id": "demo", "creatorPrograms": {"global": {
            "programName": "Demo", "url": "https://example.com",
            "applicationReview": {"status": "open", "checkedAt": "2026-11-26",
                                  "sourceUrl": "https://example.com/rules", "note": "Official statement"}}}}]
        links = gather_links({"items": []}, platforms)
        self.assertEqual(len(links), 2)
