#!/usr/bin/env python3
"""Stage Apify Instagram exports for manual review; never publish or call a paid API."""
import argparse
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

UTC = dt.timezone.utc

def parse_timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(UTC) if result.tzinfo else None
    except ValueError:
        return None

def canonical_post(url):
    if not isinstance(url, str):
        return None
    try:
        p = urlsplit(url)
    except ValueError:
        return None
    if p.scheme != "https" or p.netloc.lower() not in {"instagram.com", "www.instagram.com"}:
        return None
    m = re.fullmatch(r"/(p|reel|reels)/([A-Za-z0-9_-]+)/?", p.path)
    if not m:
        return None
    kind = "p" if m[1] == "p" else "reel"
    return m[2], f"https://www.instagram.com/{kind}/{m[2]}/"

def stage(rows, registry, now, days=30):
    if not isinstance(rows, list):
        raise ValueError("Expected a JSON array of Actor results")
    handles = {}
    for creator in registry.get("creators", []):
        for account in creator.get("accounts", []):
            if account.get("platform") != "Instagram":
                continue
            p = urlsplit(account["url"])
            handle = p.path.strip("/").lower()
            if p.scheme == "https" and p.netloc.lower() in {"instagram.com", "www.instagram.com"} and re.fullmatch(r"[a-z0-9_.]+", handle):
                handles.setdefault(handle, set()).add(creator["id"])
    rejected = {}
    candidates = {}
    def reject(reason):
        rejected[reason] = rejected.get(reason, 0) + 1
    for row in rows:
        if not isinstance(row, dict):
            reject("invalid-row")
            continue
        handle = row.get("ownerUsername")
        owners = handles.get(handle.lower(), set()) if isinstance(handle, str) else set()
        if len(owners) != 1:
            reject("unlinked-or-ambiguous-author")
            continue
        post = canonical_post(row.get("url"))
        if not post or (row.get("shortCode") and row["shortCode"] != post[0]):
            reject("invalid-post-url")
            continue
        timestamp = parse_timestamp(row.get("timestamp"))
        if timestamp is None or timestamp > now or timestamp < now - dt.timedelta(days=days):
            reject("missing-or-outside-window")
            continue
        caption = row.get("caption")
        candidate = {"creator": next(iter(owners)), "platform": "Instagram",
                     "url": post[1], "postId": post[0], "ownerUsername": handle,
                     "reportedPublishedAt": timestamp.isoformat(),
                     "caption": caption[:500] if isinstance(caption, str) else "",
                     "status": "manual-review-required",
                     "reason": "Provider timestamp and owner are not direct original-post verification."}
        if post[0] in candidates:
            reject("duplicate-post")
            continue
        candidates[post[0]] = candidate
    return {"mode": "staging-only", "checkedAt": now.isoformat(), "windowDays": days,
            "inputRows": len(rows), "candidates": sorted(candidates.values(), key=lambda x: x["reportedPublishedAt"], reverse=True),
            "rejected": rejected, "published": 0}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--registry", type=Path, default=Path("site/data/creator-watch.json"))
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--days", type=int, choices=(7, 30), default=30)
    args = p.parse_args()
    if args.report.resolve() in {args.registry.resolve(), args.input.resolve()} or "site" in args.report.resolve().parts:
        p.error("Review reports must stay outside the published site and input paths.")
    result = stage(json.loads(args.input.read_text(encoding="utf-8")),
                   json.loads(args.registry.read_text(encoding="utf-8")),
                   dt.datetime.now(UTC), args.days)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Staged {len(result['candidates'])} candidate(s); published 0.")
if __name__ == "__main__":
    main()
