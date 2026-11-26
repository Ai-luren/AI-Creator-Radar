#!/usr/bin/env python3
"""Check registered creator opportunity links, not eligibility or application status."""
from __future__ import annotations
import argparse
import concurrent.futures
import json
from collections import Counter
from datetime import datetime, timezone, date
from pathlib import Path
from urllib.parse import urlsplit

try:
    from .check_model_resources import normalize_url, probe, write_json
except ImportError:
    from check_model_resources import normalize_url, probe, write_json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site/data"


def gather_links(contests, platforms):
    links = {}
    def add(url, reference):
        if not url:
            return
        p = urlsplit(url)
        if p.scheme != "https" or not p.hostname:
            raise ValueError(f"Invalid creator source URL: {url}")
        key = normalize_url(url)
        refs = links.setdefault(key, [])
        if reference not in refs:
            refs.append(reference)

    seen = set()
    for x in contests["items"]:
        if x["id"] in seen:
            raise ValueError(f"Duplicate contest ID: {x['id']}")
        seen.add(x["id"])
        if x["review"] not in {"official-page", "official-indexed", "partner-announcement"}:
            raise ValueError("Unsupported source provenance")
        if x["category"] not in {"video", "image", "music"} or x["region"] not in {"domestic", "overseas", "global"}:
            raise ValueError("Unsupported contest classification")
        for field in ("deadlineDate", "startDate", "checkedAt"):
            if x.get(field):
                date.fromisoformat(x[field])
        if x.get("startDate") and x.get("deadlineDate") and x["startDate"] > x["deadlineDate"]:
            raise ValueError("Contest deadline precedes start")
        if x.get("deadlineAt"):
            dt = datetime.fromisoformat(x["deadlineAt"].replace("Z", "+00:00"))
            if dt.utcoffset() is None or dt.date().isoformat() != x["deadlineDate"]:
                raise ValueError("Deadline timestamp must retain its source date and time zone")
        if not x.get("sourceUrl") or not x.get("entryUrl"):
            raise ValueError("Contest must include traceable source and entry")
        for field in ("sourceUrl", "entryUrl", "secondSource"):
            add(x.get(field), {"kind": "contest", "id": x["id"]})
    for p in platforms:
        scopes = p.get("creatorPrograms") or {}
        for scope in ("domestic", "overseas", "global"):
            records = scopes.get(scope) or []
            if isinstance(records, dict):
                records = [records]
            for item in records:
                ref = {"kind": "program", "platformId": p["id"], "scope": scope, "name": item.get("programName", "")}
                for field in ("url", "sourceUrl"):
                    add(item.get(field), ref)
    return [{"url": url, "references": refs} for url, refs in sorted(links.items())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validate and list counts without network or writes")
    parser.add_argument("--report", type=Path, help="Write a diagnostic snapshot outside canonical data")
    args = parser.parse_args()
    read = lambda name: json.loads((DATA / name).read_text(encoding="utf-8"))
    links = gather_links(read("creator-contests.json"), read("social-platforms.json"))
    print(f"Creator opportunity links: {len(links)} distinct URLs")
    if args.dry_run:
        return 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda item: {**item, **probe(item["url"])}, links))
    counts = dict(Counter(x["status"] for x in results))
    payload = {"checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
               "total": len(results), "counts": counts, "results": results,
               "method": "HTTP reachability only; never confirms registration, eligibility, authenticity, deadlines or terms."}
    write_json(args.report or DATA / "creator-link-status.json", payload)
    print(json.dumps(counts, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
