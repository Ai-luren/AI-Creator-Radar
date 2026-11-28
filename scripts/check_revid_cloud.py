"""Explicit cloud search smoke: metadata-only logs, no public results."""
import os
from datetime import datetime, timezone
from scripts.check_revid_auth import check
from scripts.revid_github_quota import GitHubQuota
from scripts.revid_research_transport import search

QUERY = "cinematic video visual transformation match cut creative filmmaking"


def verify(ledger, key, *, search_fn=search, auth_fn=check,
           clock=lambda: datetime.now(timezone.utc)):
    status = auth_fn(key)
    if status != "authenticated":
        return status
    result = search_fn(QUERY, key, ledger.reserve, now=clock(), creative_only=True)
    status = result["status"]
    if status == "ok":
        if not ledger.complete_success(clock()):
            return "quota-release-unconfirmed"
        return "search-authenticated"
    # The atomic pre-request hold remains on any non-success. No retry.
    return status


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REF") != "refs/heads/main":
        print("Revid cloud smoke: wrong-runtime")
        return 1
    try:
        ledger = GitHubQuota(os.environ.get("GITHUB_REPOSITORY"),
                             os.environ.get("RADAR_GITHUB_API_TOKEN"))
        status = verify(ledger, os.environ.get("REVID_API_KEY"))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        status = "verification-error"
    print("Revid cloud smoke: " + status)
    return 0 if status == "search-authenticated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
