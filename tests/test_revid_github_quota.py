import base64
import io
import json
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from scripts.revid_github_quota import GitHubQuota

NOW = datetime(2026, 11, 28, 10, tzinfo=timezone.utc)


class FakeGitHub:
    def __init__(self):
        self.state = {"attempts": [], "blocked_until": None}
        self.sha = "1"
        self.conflict = False
        self.missing = False

    def open(self, req, timeout):
        def error(code):
            raise urllib.error.HTTPError(req.full_url, code, "synthetic", {}, None)
        if self.missing:
            error(404)
        if req.method == "GET":
            response = {"sha": self.sha, "content": base64.b64encode(json.dumps(self.state).encode()).decode()}
        else:
            body = json.loads(req.data)
            if self.conflict or body["sha"] != self.sha:
                error(409)
            self.state = json.loads(base64.b64decode(body["content"]))
            self.sha = str(int(self.sha) + 1)
            response = {"commit": {"sha": self.sha}}
        return io.BytesIO(json.dumps(response).encode())


class CloudQuotaTests(unittest.TestCase):
    def test_persisted_limit_across_runners(self):
        api = FakeGitHub()
        for i in range(16):
            runner = GitHubQuota("Ai-luren/AI-Creator-Radar", "test", opener=api)
            now = NOW + timedelta(seconds=i)
            self.assertTrue(runner.reserve(now))
            self.assertFalse(GitHubQuota("Ai-luren/AI-Creator-Radar", "test", opener=api).reserve(now))
            self.assertTrue(runner.complete_success(now))
        q = GitHubQuota("Ai-luren/AI-Creator-Radar", "test", opener=api)
        self.assertFalse(q.reserve(NOW + timedelta(hours=23)))
        self.assertTrue(q.reserve(NOW + timedelta(hours=25)))

    def test_conflicts_missing_corruption_fail_closed(self):
        api = FakeGitHub()
        q = GitHubQuota("Ai-luren/AI-Creator-Radar", "test", opener=api)
        api.conflict = True
        self.assertFalse(q.reserve(NOW))
        self.assertEqual(api.state["attempts"], [])
        api.conflict = False
        api.missing = True
        self.assertFalse(q.reserve(NOW))
        api.missing = False
        api.state["attempts"] = ["broken"]
        self.assertFalse(q.reserve(NOW))

    def test_cooldown_across_runners(self):
        api = FakeGitHub()
        GitHubQuota("Ai-luren/AI-Creator-Radar", "test", opener=api).cool_down(NOW)
        q = GitHubQuota("Ai-luren/AI-Creator-Radar", "test", opener=api)
        self.assertFalse(q.reserve(NOW + timedelta(hours=23)))
        self.assertTrue(q.reserve(NOW + timedelta(hours=25)))

    def test_abandoned_request_holds_gate(self):
        api = FakeGitHub()
        q = GitHubQuota("Ai-luren/AI-Creator-Radar", "test", opener=api)
        self.assertTrue(q.reserve(NOW))
        replacement = GitHubQuota("Ai-luren/AI-Creator-Radar", "test", opener=api)
        self.assertFalse(replacement.reserve(NOW + timedelta(hours=23)))
        self.assertFalse(replacement.complete_success(NOW))
        self.assertTrue(replacement.reserve(NOW + timedelta(hours=25)))
