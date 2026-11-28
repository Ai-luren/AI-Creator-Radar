"""Bounded Revid transport for personal research. No automatic execution or publication."""
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from scripts.revid_research_core import personal_candidates
from scripts.revid_creative_triage import classify, group_topics

ENDPOINT = "https://www.revid.ai/api/public/v3/search-viral-videos"
MAX_BYTES = 4 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def search(query, key, reserve, *, now=None, opener=None, creative_only=False):
    """Reserve a durable quota slot via caller before I/O; no automatic retry.

    The caller must honor rate-limited status across runs. Raw content stays
    in memory only. Do not log request headers or response bodies.
    """
    now = now or datetime.now(timezone.utc)
    if not isinstance(key, str) or not key.strip() or now.tzinfo is None:
        return {"status": "configuration-error", "candidates": []}
    if not isinstance(query, str) or not query.strip() or len(query) > 300:
        return {"status": "configuration-error", "candidates": []}
    params = {"query": query, "limit": 12, "minViews": 10000,
              "postedAfter": (now - timedelta(days=3)).date().isoformat(),
              "sort": "relevance"}
    # Official API accepts a comma-separated platform string.
    params["platforms"] = "youtube,instagram,tiktok,x"
    req = urllib.request.Request(ENDPOINT + "?" + urlencode(params, doseq=True),
                                 headers={"key": key, "Accept": "application/json",
                                          "User-Agent": "AI-Creator-Radar/1.0"})
    if not reserve(now):
        return {"status": "budget-exhausted", "candidates": []}
    opener = opener or urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=20) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("oversize")
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("success") != 1 or not isinstance(data.get("videos"), list):
            raise ValueError("unexpected schema")
        rows = data["videos"][:12]
        if not creative_only:
            return {"status": "ok", "candidates": personal_candidates(rows, now)}
        accepted = {}
        for row in rows:
            labels = classify(row)
            if not labels:
                continue
            for candidate in personal_candidates([row], now):
                if candidate["views"] < 10000:
                    continue
                candidate["creativeTopics"] = list(labels)
                accepted.setdefault(candidate["url"], candidate)
        candidates = list(accepted.values())
        return {"status": "ok", "candidates": candidates, "topics": group_topics(candidates)}
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            return {"status": "rate-limited", "candidates": []}
        if exc.code in (401, 403):
            return {"status": "auth-denied", "candidates": []}
        return {"status": "http-error", "candidates": []}
    except (OSError, ValueError, TypeError):
        return {"status": "response-error", "candidates": []}
