import io
import json
import unittest
from urllib.error import HTTPError, URLError
from scripts.publication_guard import status, URL

TREE = 'a' * 40
COMMIT = 'b' * 40


class Response(io.BytesIO):
    def __init__(self, payload, url=URL):
        super().__init__(payload)
        self.url = url

    def geturl(self):
        return self.url


class PublicationGuardTests(unittest.TestCase):
    def test_current_site_ignores_different_commit(self):
        def opener(request, timeout):
            self.assertEqual(timeout, 8)
            self.assertEqual(request.full_url, URL + '?tree=' + TREE)
            return Response(json.dumps({'commit': COMMIT, 'siteTree': TREE}).encode())
        self.assertEqual(status(TREE, opener), 'current')

    def test_stale_and_legacy_marker(self):
        for doc in ({'commit': COMMIT, 'siteTree': 'c' * 40}, {'commit': COMMIT}):
            self.assertEqual(status(TREE, lambda *a, **kw: Response(json.dumps(doc).encode())), 'stale')

    def test_bad_payload_does_not_infer_staleness(self):
        for payload in (b'not JSON', b'[]', b'{}', b'x' * 4097, json.dumps({'commit': COMMIT, 'siteTree': None}).encode()):
            self.assertEqual(status(TREE, lambda *a, **kw: Response(payload)), 'unknown')
        self.assertEqual(status(TREE, lambda *a, **kw: Response(b'{}', 'https://example.com/')), 'unknown')

    def test_transport_errors_and_bootstrap(self):
        for code, expected in ((404, 'stale'), (403, 'unknown'), (429, 'unknown'), (503, 'unknown')):
            def opener(*a, **kw):
                raise HTTPError(URL, code, 'test', {}, None)
            self.assertEqual(status(TREE, opener), expected)
        def offline(*a, **kw):
            raise URLError('offline')
        self.assertEqual(status(TREE, offline), 'unknown')

    def test_invalid_expected_tree_is_fatal(self):
        with self.assertRaises(ValueError):
            status('bad', lambda *a, **kw: self.fail('must not request'))

    def test_live_gate_requires_actual_matching_tree(self):
        from datetime import datetime, timezone
        from scripts.publication_guard import verify_live
        now=datetime(2026,11,28,tzinfo=timezone.utc)
        for tree,expected in ((TREE,"pass"),("c"*40,"unverified")):
            proof=verify_live(TREE,lambda *a,**kw: Response(json.dumps({"commit":COMMIT,"siteTree":tree}).encode()),now)
            self.assertEqual(proof["gate"],expected)
            self.assertEqual(proof["expectedSiteTree"],TREE)
            self.assertEqual(proof["checkedAt"],now.isoformat())
        def offline(*a,**kw):
            raise URLError("offline")
        proof=verify_live(TREE,offline,now)
        self.assertEqual(proof["gate"],"unverified")
        self.assertEqual(proof["status"],"unknown")
