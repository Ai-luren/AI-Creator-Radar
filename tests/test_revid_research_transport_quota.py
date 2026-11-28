import concurrent.futures
import io
import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from scripts.revid_research_quota import LocalQuota
from scripts.revid_research_transport import search, NoRedirect

NOW = datetime(2026, 11, 28, 10, tzinfo=timezone.utc)


class FakeOpener:
    def __init__(self, payload=None, status=None):
        self.payload = payload
        self.status = status
        self.requests = []

    def open(self, req, timeout):
        self.requests.append((req, timeout))
        if self.status:
            raise urllib.error.HTTPError(req.full_url, self.status, "test", {}, None)
        return io.BytesIO(json.dumps(self.payload).encode())


class RevidTransportTests(unittest.TestCase):
    def test_no_request_without_reservation(self):
        op = FakeOpener()
        self.assertEqual(search("creative", "synthetic", lambda _: False, now=NOW,
                                opener=op)["status"], "budget-exhausted")
        self.assertEqual(op.requests, [])

    def test_success_filters_and_reserves_first(self):
        op = FakeOpener({"success": 1, "videos": [
            {"url": "https://youtu.be/abcdefghijk", "postedAt": NOW.isoformat(),
             "engagement": {"views": 15000}, "transcript": "synthetic"}]})
        def reserve(value):
            self.assertEqual(value, NOW)
            self.assertFalse(op.requests)
            return True
        result = search("creative", "synthetic", reserve, now=NOW, opener=op)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["candidates"]), 1)
        self.assertNotIn("transcript", result["candidates"][0])
        req, timeout = op.requests[0]
        self.assertEqual(req.get_header("Key"), "synthetic")
        self.assertNotIn("synthetic", req.full_url)
        self.assertEqual(timeout, 20)

    def test_errors_never_retry(self):
        for code, expected in [(429, "rate-limited"), (401, "auth-denied"),
                               (403, "auth-denied"), (500, "http-error")]:
            op = FakeOpener(status=code)
            attempts = []
            result = search("creative", "synthetic", lambda t: attempts.append(t) or True,
                            now=NOW, opener=op)
            self.assertEqual(result["status"], expected)
            self.assertEqual(len(attempts), 1)
            self.assertEqual(len(op.requests), 1)

    def test_malformed_schema_and_redirect(self):
        op = FakeOpener({"success": 1, "videos": "invalid"})
        self.assertEqual(search("creative", "synthetic", lambda _: True, now=NOW,
                                opener=op)["status"], "response-error")
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.test"))


class RevidQuotaTests(unittest.TestCase):
    def test_concurrent_reservations_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            ledger = LocalQuota(path)
            self.assertFalse(ledger.reserve(NOW))
            ledger.initialize()
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                outcomes = list(pool.map(lambda _: LocalQuota(path).reserve(NOW), range(30)))
            self.assertEqual(sum(outcomes), 16)
            self.assertFalse(LocalQuota(path).reserve(NOW + timedelta(hours=23)))
            self.assertTrue(LocalQuota(path).reserve(NOW + timedelta(hours=24, seconds=1)))
            with self.assertRaises(FileExistsError):
                ledger.initialize()

    def test_cooldown_and_corrupt_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            ledger = LocalQuota(path)
            ledger.initialize()
            ledger.cool_down(NOW)
            self.assertFalse(LocalQuota(path).reserve(NOW + timedelta(hours=23)))
            self.assertTrue(LocalQuota(path).reserve(NOW + timedelta(hours=25)))
            path.write_bytes(b"corrupt")
            self.assertFalse(LocalQuota(path).reserve(NOW + timedelta(hours=26)))
