import io
import json
import unittest
import urllib.error
from datetime import datetime, timezone
from scripts.check_revid_auth import check
from scripts.check_revid_cloud import verify

NOW = datetime(2026, 11, 28, 10, tzinfo=timezone.utc)


class ProductionSmokeTests(unittest.TestCase):
    def test_auth_probe_status_only(self):
        class Fake:
            def open(self, req, timeout):
                self.req = req
                return io.BytesIO(json.dumps({"success": 1, "email": "synthetic"}).encode())
        op = Fake()
        self.assertEqual(check("synthetic-key", op), "authenticated")
        self.assertEqual(op.req.full_url, "https://www.revid.ai/api/public/v3/me")
        self.assertEqual(op.req.get_header("Key"), "synthetic-key")
        self.assertEqual(check("", op), "missing-secret")

    def test_failed_auth_never_searches(self):
        def forbidden(*args, **kwargs):
            self.fail("unexpected search")
        self.assertEqual(verify(None, "test", auth_fn=lambda _: "invalid-secret",
                                search_fn=forbidden), "invalid-secret")

    def test_cloud_success_releases_and_failure_does_not(self):
        class Ledger:
            def __init__(self):
                self.reserved = 0
                self.released = 0
            def reserve(self, now):
                self.reserved += 1
                return True
            def complete_success(self, now):
                self.released += 1
                return True
        for response, expected, released in [("ok", "search-authenticated", 1),
                                               ("rate-limited", "rate-limited", 0)]:
            ledger = Ledger()
            def search_fn(query, key, reserve, **kw):
                self.assertTrue(reserve(kw["now"]))
                return {"status": response, "candidates": []}
            self.assertEqual(verify(ledger, "test", auth_fn=lambda _: "authenticated",
                                    search_fn=search_fn, clock=lambda: NOW), expected)
            self.assertEqual(ledger.reserved, 1)
            self.assertEqual(ledger.released, released)
