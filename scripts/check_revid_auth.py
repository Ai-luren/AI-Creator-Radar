"""Read-only production authentication smoke; never print account fields."""
import json
import os
import urllib.error
import urllib.request
from scripts.revid_research_transport import NoRedirect

ENDPOINT = "https://www.revid.ai/api/public/v3/me"


def check(key, opener=None):
    if not isinstance(key, str) or not key.strip():
        return "missing-secret"
    req = urllib.request.Request(ENDPOINT, headers={
        "key": key, "Accept": "application/json", "User-Agent": "AI-Creator-Radar/1.0"})
    opener = opener or urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=15) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            return "invalid-response"
        data = json.loads(raw)
        return "authenticated" if isinstance(data, dict) and data.get("success") == 1 else "invalid-response"
    except urllib.error.HTTPError as exc:
        return {401: "invalid-secret", 403: "access-denied", 429: "rate-limited"}.get(exc.code, "http-error")
    except (OSError, ValueError, TypeError):
        return "transport-error"


def main():
    status = check(os.environ.get("REVID_API_KEY"))
    print("Revid authentication: " + status)
    return 0 if status == "authenticated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
