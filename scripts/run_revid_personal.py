"""Explicit personal Revid research entrypoint; no public publication."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scripts.revid_research_quota import LocalQuota
from scripts.revid_research_transport import search
from scripts.revid_creative_triage import group_topics

QUERIES = (
    "cinematic AI filmmaking visual transformation match cut creative video effects",
    "popular character crossover superhero fan film creative video transformations",
    "creative product reveal advertising animated storytelling short film plot twist",
    "Christmas holiday seasonal creative commercials visual effects video",
)


def run(ledger, key, *, search_fn=search, clock=lambda: datetime.now(timezone.utc)):
    accepted = {}
    statuses = []
    for query in QUERIES:
        result = search_fn(query, key, ledger.reserve, now=clock(), creative_only=True)
        status = result["status"]
        statuses.append(status)
        if status == "rate-limited":
            ledger.cool_down(clock())
        if status != "ok":
            break
        for candidate in result["candidates"]:
            accepted.setdefault(candidate["url"], candidate)
    candidates = list(accepted.values())
    return {"statuses": statuses, "candidates": candidates, "topics": group_topics(candidates)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--initialize", action="store_true")
    args = parser.parse_args()
    ledger = LocalQuota(args.ledger)
    if args.initialize:
        ledger.initialize()
        return 0
    key = os.environ.get("REVID_API_KEY", "")
    if not key:
        parser.error("REVID_API_KEY is not configured")
    if os.environ.get("GITHUB_ACTIONS") == "true" or not os.isatty(1):
        parser.error("personal terminal only; no public CI logs or redirected output")
    result = run(ledger, key)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["statuses"] and all(s == "ok" for s in result["statuses"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
