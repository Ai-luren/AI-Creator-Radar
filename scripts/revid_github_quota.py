"""Shared GitHub quota via optimistic blob-SHA compare-and-swap.

Only timestamps and cooldown metadata belong in the state branch.
Missing state, conflicts and ambiguous writes fail closed; no retries.
"""
import base64
import json
import urllib.request
from datetime import timedelta, timezone
from scripts.revid_research_core import parse_time, quota_remaining
from scripts.revid_research_transport import NoRedirect

STATE_BRANCH = "state/revid-quota"
STATE_PATH = "revid-quota.json"


class GitHubQuota:
    def __init__(self, repository, token, *, opener=None):
        if repository != "Ai-luren/AI-Creator-Radar" or not token:
            raise ValueError("invalid quota configuration")
        self.url = "https://api.github.com/repos/" + repository + "/contents/" + STATE_PATH
        self.token = token
        self.opener = opener or urllib.request.build_opener(NoRedirect())

    def _request(self, method, url, payload=None):
        req = urllib.request.Request(url, method=method,
            headers={"Authorization": "Bearer " + self.token,
                     "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json",
                     "X-GitHub-Api-Version": "2022-11-28"},
            data=None if payload is None else json.dumps(payload).encode())
        with self.opener.open(req, timeout=15) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("oversized quota response")
        return json.loads(raw)

    def _read(self, now):
        result = self._request("GET", self.url + "?ref=" + STATE_BRANCH)
        state = json.loads(base64.b64decode(result["content"]))
        if not isinstance(state, dict) or set(state) != {"attempts", "blocked_until"}:
            raise ValueError("invalid quota state")
        attempts = state["attempts"]
        if not isinstance(attempts, list) or len(attempts) > 20:
            raise ValueError("invalid quota attempts")
        if any(parse_time(v) is None or parse_time(v) > now for v in attempts):
            raise ValueError("invalid quota time")
        blocked = state["blocked_until"]
        if blocked is not None and parse_time(blocked) is None:
            raise ValueError("invalid cooldown")
        return result["sha"], state

    def _write(self, sha, state):
        result = self._request("PUT", self.url, {
            "message": "Reserve Revid quota metadata",
            "branch": STATE_BRANCH, "sha": sha,
            "content": base64.b64encode(json.dumps(state).encode()).decode()})
        if not result.get("commit", {}).get("sha"):
            raise ValueError("unconfirmed quota write")

    def reserve(self, now):
        if now.tzinfo is None:
            return False
        now = now.astimezone(timezone.utc)
        try:
            sha, state = self._read(now)
            if not quota_remaining(state["attempts"], now):
                return False
            blocked = parse_time(state["blocked_until"])
            if blocked and blocked > now:
                return False
            state["attempts"] = [v for v in state["attempts"]
                                 if parse_time(v) > now - timedelta(hours=24)]
            state["attempts"].append(now.isoformat())
            self._write(sha, state)
            return True
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return False

    def cool_down(self, now):
        if now.tzinfo is None:
            raise ValueError("aware time required")
        now = now.astimezone(timezone.utc)
        sha, state = self._read(now)
        blocked = parse_time(state["blocked_until"])
        until = now + timedelta(hours=24)
        state["blocked_until"] = max(until, blocked).isoformat() if blocked else until.isoformat()
        self._write(sha, state)
