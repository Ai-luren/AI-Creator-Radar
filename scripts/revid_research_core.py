"""Pure helpers for personal Revid research; never persist or publish results.

No network, credentials, scheduler, or public data writer in this module.
"""
from datetime import datetime, timedelta, timezone
import re
from urllib.parse import urlsplit, parse_qs

WINDOW = timedelta(hours=24)
AUTOMATIC_LIMIT = 16
FREE_LIMIT = 20


def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, OverflowError):
        return None


def quota_remaining(attempts, now, *, automatic=True):
    """Count every attempted request, including failed ones, in rolling 24h.

    The eventual runner must reserve attempts atomically before network I/O
    and preserve its ledger across runs. Unknown ledger state is not safe.
    """
    if now.tzinfo is None or attempts is None:
        return 0
    times = [parse_time(value) for value in attempts]
    if any(value is None or value > now for value in times):
        return 0
    count = sum(now - WINDOW < value <= now for value in times)
    return max(0, (AUTOMATIC_LIMIT if automatic else FREE_LIMIT) - count)


def canonical_post(url):
    """Return platform and a stable original-post URL, or None.

    Use a strict host/path allowlist. Do not resolve arbitrary short links.
    """
    if not isinstance(url, str):
        return None
    try:
        p = urlsplit(url)
        if p.scheme != "https" or p.username or p.password or p.port is not None:
            return None
        host, path = p.hostname, p.path.rstrip("/")
    except ValueError:
        return None
    if host in ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"):
        if host == "youtu.be":
            ident = path.lstrip("/")
        elif path == "/watch":
            vals = parse_qs(p.query).get("v", [])
            ident = vals[0] if len(vals) == 1 else ""
        elif path.startswith("/shorts/"):
            ident = path[len("/shorts/"):]
        else:
            return None
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", ident):
            return "youtube", "https://www.youtube.com/watch?v=" + ident
    if host in ("www.tiktok.com", "tiktok.com"):
        if re.fullmatch(r"/@[A-Za-z0-9_.-]+/video/[0-9]+", path):
            return "tiktok", "https://www.tiktok.com" + path
    if host in ("instagram.com", "www.instagram.com"):
        if re.fullmatch(r"/(?:p|reel|reels)/[A-Za-z0-9_-]+", path):
            code = path.split("/")[-1]
            return "instagram", "https://www.instagram.com/p/" + code + "/"
    if host in ("x.com", "www.x.com", "twitter.com", "www.twitter.com"):
        match = re.fullmatch(r"/(?:[A-Za-z0-9_]+/status|i/web/status)/([0-9]+)", path)
        if match:
            return "x", "https://x.com/i/web/status/" + match.group(1)
    return None


def count_metric(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def personal_candidates(rows, now, *, days=3):
    """Return minimal in-memory candidates, not a verified viral ranking.

    Provider-supplied metrics and date are unverified original-platform facts.
    Human relevance review is still required. No upstream text, media, or
    transcript is retained. Caller must not write this output to public files.
    """
    if now.tzinfo is None or days not in (3, 7):
        raise ValueError("invalid research window")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        original = canonical_post(row.get("url"))
        posted = parse_time(row.get("postedAt"))
        if not original or not posted or not now - timedelta(days=days) <= posted <= now:
            continue
        platform, url = original
        engagement = row.get("engagement")
        engagement = engagement if isinstance(engagement, dict) else {}
        views = count_metric(engagement.get("views"))
        if views is None:
            continue
        candidate = {"url": url, "platform": platform,
                     "postedAt": posted.isoformat(), "observedAt": now.isoformat(),
                     "views": views, "likes": count_metric(engagement.get("likes")),
                     "shares": count_metric(engagement.get("shares")),
                     "source": "revid", "verification": "provider-reported"}
        # Never add duplicate engagement. Preserve the first valid observation.
        result.setdefault(url, candidate)
    return list(result.values())
