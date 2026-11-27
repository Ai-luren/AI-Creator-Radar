#!/usr/bin/env python3
"""Bounded independent news-index lookup for unresolved model leads.

No paid API, guessed publisher paths, benchmark URLs, or inferred release dates.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlsplit

try:
    from scripts.collect_models import SameHostRedirect, USER_AGENT, clean_text, non_release_title, write_json
    from scripts.collect_cross_platform import article_url, https_url
    from scripts.collect_release_recall import url_key
    from scripts.event_identity import identify, model_index
except ModuleNotFoundError:
    from collect_models import SameHostRedirect, USER_AGENT, clean_text, non_release_title, write_json
    from collect_cross_platform import article_url, https_url
    from collect_release_recall import url_key
    from event_identity import identify, model_index

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site/data/source-search.json"
ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
ATTRIBUTION = {"name": "GDELT DOC 2.0", "url": "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"}
MAX_BYTES = 2 * 1024 * 1024
OPEN_STATES = {"needs-source", "probe-unresolved", "awaiting-probe", "needs-product-identity"}


def stable_id(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def stamp(value):
    try:
        dt = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return dt if dt.tzinfo else None
    except ValueError:
        return None


def safe_name(value):
    name = str(value or "").strip()
    # Never pass arbitrary article text, query operators, or URLs to the API.
    return name if (5 <= len(name) <= 90 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._+-]*", name)
                    and re.search(r"[A-Za-z]", name) and re.search(r"\d", name)) else None


def build_targets(families, discovery, reconciliation, product_state):
    index = model_index(families)
    names = {(f["id"], v["id"]): v.get("name") for f in families for v in f.get("versions", [])}
    targets = {}

    def add(name, identity, origin, first):
        name = safe_name(name)
        if not name:
            return
        tid = stable_id("canonical", *identity) if identity else stable_id("unclassified", name.casefold())
        target = targets.setdefault(tid, {"id": tid, "query": name, "identity": (
            {"modelFamilyId": identity[0], "modelVersionId": identity[1]} if identity else None),
            "originIds": [], "firstDetectedAt": first})
        target["originIds"] = sorted(set(target["originIds"] + [origin]))
        target["firstDetectedAt"] = min(x for x in (target["firstDetectedAt"], first) if x) if first or target["firstDetectedAt"] else None

    for lead in discovery.get("items", []):
        if lead.get("sourceId") == "local-official-candidates" or lead.get("dateKind") == "repository-created-at" or lead.get("officialArticleUrls"):
            continue
        identity = identify(index, lead.get("title"), lead.get("titleHints") or ())
        if identity in names:
            add(names[identity], identity, lead["id"], lead.get("firstSeenAt"))
    for task in reconciliation.get("tasks", []):
        if task.get("state") not in OPEN_STATES:
            continue
        obj = task.get("identity") or {}
        identity = (obj.get("modelFamilyId"), obj.get("modelVersionId"))
        if identity in names:
            add(names[identity], identity, task["id"], task.get("firstDetectedAt"))
        elif task.get("taskType") == "product-observation":
            add(task.get("modelName"), None, task["id"], task.get("firstDetectedAt"))
    for event in product_state.get("events", []):
        if event.get("eventType") not in {"added-to-catalog", "baseline-recent-reported-date"}:
            continue
        if event.get("identity"):
            continue
        name = (event.get("product") or {}).get("name")
        identity = identify(index, name)
        if not identity:
            add(name, None, event["id"], event.get("observedAt"))
    return targets


def local_context(target, discovery, reconciliation, product_state, index, allowed):
    """Reuse persisted observations without manufacturing independent evidence.

    Existing catalog facts and prior observations are context, not fresh recall
    or proof that the reported event occurred. This path requires no network.
    """
    obj = target.get("identity") or {}
    identity = (obj.get("modelFamilyId"), obj.get("modelVersionId"))
    if not all(identity):
        return []
    records = {}

    def add(row):
        records[stable_id(row["kind"], row["sourceUrl"], row.get("sourceRecordId"),
                          row.get("assertedDate"))] = row

    for row in reconciliation.get("evidence", []):
        if (row.get("modelFamilyId"), row.get("modelVersionId")) != identity or not url_key(row.get("sourceUrl")):
            continue
        add({"kind": row["claimType"], "sourceUrl": row["sourceUrl"],
             "sourceRecordId": row["id"], "assertedDate": row.get("assertedDate"),
             "originalVerificationAt": row.get("originalVerificationAt"),
             "datePrecision": row.get("datePrecision"), "provenance": "persisted-evidence"})
    for lead in discovery.get("items", []):
        if lead.get("dateKind") == "repository-created-at":
            continue
        if identify(index, lead.get("title"), lead.get("titleHints") or ()) != identity:
            continue
        for raw in lead.get("officialArticleUrls", []):
            url = article_url(raw, allowed)
            if url:
                add({"kind": "original-url-pointer", "sourceUrl": url,
                     "sourceRecordId": lead["id"], "sourceId": lead["sourceId"],
                     "assertedDate": None, "originalVerificationAt": None,
                     "lastObservedAt": lead.get("lastSeenAt") or lead.get("firstSeenAt"),
                     "provenance": "existing-discovery"})
    for source in product_state.get("sources", []):
        if not source.get("lastSuccessAt") or not url_key(source.get("url")):
            continue
        for key, entry in source.get("entries", {}).items():
            product = entry.get("product") or {}
            if entry.get("missingChecks", 0) or identify(index, product.get("name")) != identity:
                continue
            add({"kind": "catalog-listing-observed", "sourceUrl": source["url"],
                 "sourceRecordId": key, "sourceId": source["id"],
                 "assertedDate": None, "originalVerificationAt": source["lastSuccessAt"],
                 "reportedReleaseDate": product.get("reportedReleaseDate"),
                 "firstObservedAt": entry.get("firstSeenAt"),
                 "provenance": "product-catalog"})
    # Retain the explicit distinction between dated primary evidence,
    # unverified pointers, and third-party product listing observations.
    return sorted(records.values(), key=lambda r: (r["kind"], r["sourceUrl"],
                  r.get("sourceRecordId") or ""))[:40]


def parse_results(payload, target, allowed, families):
    if not isinstance(payload, dict) or not isinstance(payload.get("articles"), list):
        raise ValueError("Unexpected GDELT response schema")
    index = model_index(families)
    expected = target.get("identity")
    exact = re.compile(r"(?<![A-Za-z0-9.])" + re.escape(target["query"]) +
                       r"(?![A-Za-z0-9.]|[-_][A-Za-z0-9]|\s+(?:pro|plus|flash|mini|lite|live|medical|fast|preview|ultra|max|omni|next|code|instruct)\b)", re.I)
    results = {}
    for item in payload["articles"][:30]:
        if not isinstance(item, dict):
            continue
        title = clean_text(item.get("title") or "")
        url = https_url(item.get("url"))
        if not title or not url or non_release_title(title):
            continue
        if expected:
            found = identify(index, title)
            if found != (expected["modelFamilyId"], expected["modelVersionId"]):
                continue
        elif not exact.search(title):
            continue
        key = url_key(url)
        if not key:
            continue
        seen = str(item.get("seendate") or "")
        if not re.fullmatch(r"\d{8}T\d{6}Z", seen):
            seen = None
        results[key] = {"url": url, "title": title[:240], "domain": urlsplit(url).hostname,
                        "indexSeenAt": seen, "officialCandidateUrl": article_url(url, allowed) or None,
                        "claimType": "index-discovery", "attribution": ATTRIBUTION}
    return sorted(results.values(), key=lambda row: (not bool(row["officialCandidateUrl"]), row["url"]))[:20]


def fetch(target, allowed, families):
    # Query exact model names; result titles are independently checked again.
    query = urlencode({"query": '"' + target["query"] + '"', "mode": "artlist", "format": "json",
                       "maxrecords": 30, "timespan": "3m", "sort": "HybridRel"})
    req = urllib.request.Request(ENDPOINT + "?" + query,
                                 headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.build_opener(SameHostRedirect()).open(req, timeout=15) as response:
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("Index response exceeds size limit")
    return parse_results(json.loads(body), target, allowed, families)


def search(families, discovery, reconciliation, product_state, previous, allowed, now, fetcher=fetch):
    if previous and previous.get("schema") != "source-search/v1":
        raise ValueError("Unknown source search schema")
    checked = now.isoformat(timespec="seconds")
    active = build_targets(families, discovery, reconciliation, product_state)
    old = {t["id"]: t for t in previous.get("targets", [])}
    if len(old) != len(previous.get("targets", [])):
        raise ValueError("Duplicate source search target")
    targets = {}
    for tid, target in active.items():
        prior = old.get(tid, {})
        same = prior.get("query") == target["query"]
        targets[tid] = {**(prior if same else {}), **target, "active": True,
                        "firstDetectedAt": prior.get("firstDetectedAt") or target.get("firstDetectedAt") or checked}
    for tid, prior in old.items():
        if tid not in targets:
            targets[tid] = {**prior, "active": False}
    service = dict(previous.get("service", {}))
    cooldown = stamp(service.get("nextAttemptAt"))
    due = [t for t in targets.values() if t["active"] and
           (not stamp(t.get("nextAttemptAt")) or stamp(t["nextAttemptAt"]) <= now)]
    # Oldest untried first, then least-recently attempted. A flood of new tasks
    # cannot indefinitely starve an older retry with an earlier due time.
    due.sort(key=lambda t: (t.get("nextAttemptAt") or t["firstDetectedAt"], t["id"]))
    attempted = 0
    if due and (not cooldown or cooldown <= now):
        target = due[0]
        attempted = 1
        try:
            results = fetcher(target, allowed, families)
            if not isinstance(results, list):
                raise ValueError("Invalid search results")
        except (OSError, ValueError, TypeError) as exc:
            count = int(service.get("consecutiveFailures", 0)) + 1
            delay = min(1440, 60 * 2 ** min(count, 5))
            if isinstance(exc, urllib.error.HTTPError):
                retry = exc.headers.get("Retry-After", "") if exc.headers else ""
                if str(retry).isdigit():
                    delay = max(delay, min(1440, (int(retry) + 59) // 60))
                if exc.code in {403, 429}:
                    delay = max(delay, 360)
            service.update(lastAttemptAt=checked, error=f"{type(exc).__name__}: {str(exc)[:160]}",
                           consecutiveFailures=count, nextAttemptAt=(now+timedelta(minutes=delay)).isoformat())
            target.update(lastAttemptAt=checked, status="index-unavailable",
                          nextAttemptAt=service["nextAttemptAt"])
        else:
            # Previously observed links survive temporary search failure or result rotation.
            retained = {url_key(r["url"]): r for r in target.get("results", [])}
            for row in results:
                key = url_key(row["url"])
                prior = retained.get(key, {})
                retained[key] = {**row, "firstObservedAt": prior.get("firstObservedAt") or checked,
                                 "lastObservedAt": checked}
            cutoff = (now - timedelta(days=90)).isoformat()
            target.update(results=sorted((r for r in retained.values() if r["lastObservedAt"] >= cutoff),
                                         key=lambda r: (r["lastObservedAt"], r["url"]), reverse=True)[:40],
                          lastAttemptAt=checked, lastSuccessfulSearchAt=checked,
                          status="index-candidates" if results else "no-matching-index-results",
                          nextAttemptAt=(now+timedelta(hours=24)).isoformat())
            service.update(lastAttemptAt=checked, lastSuccessAt=checked, error=None,
                           consecutiveFailures=0, nextAttemptAt=(now+timedelta(minutes=30)).isoformat())
    index = model_index(families)
    active_rows = [t for t in targets.values() if t["active"]]
    for target in active_rows:
        target["localContext"] = local_context(target, discovery, reconciliation, product_state, index, allowed)
    counts = Counter(t.get("status", "awaiting-search") for t in active_rows)
    return {"schema": "source-search/v1", "checkedAt": checked, "service": service,
            "targets": sorted(targets.values(), key=lambda t: t["id"]),
            "summary": {"activeTargets": len(active_rows), "attemptedThisRun": attempted,
                        "targetStates": dict(sorted(counts.items())),
                        "targetsWithLocalContext": sum(bool(t["localContext"]) for t in active_rows),
                        "localContextRecords": sum(len(t["localContext"]) for t in active_rows),
                        "officialCandidates": sum(bool(r.get("officialCandidateUrl")) for t in active_rows for r in t.get("results", [])),
                        "indexReports": sum(not r.get("officialCandidateUrl") for t in active_rows for r in t.get("results", [])),
                        "indexLastSuccessAt": service.get("lastSuccessAt"),
                        "indexError": service.get("error"), "nextIndexAttemptAt": service.get("nextAttemptAt")},
            "policy": "Search only unresolved observed names. Search hits and index observation times are not release facts, and mirrors are not independent official sources."}


def augment_discovery(discovery, search_state):
    """Add separately attributed publisher URL candidates, never fake a source date."""
    items = list(discovery.get("items", []))
    seen = {r["id"] for r in items}
    for target in search_state.get("targets", []):
        if not target.get("active"):
            continue
        for result in target.get("results", []):
            url = result.get("officialCandidateUrl")
            if not url_key(url):
                continue
            rid = "index-" + stable_id(target["id"], url_key(url))[:20]
            if rid in seen:
                continue
            seen.add(rid)
            items.append({"id": rid, "title": result["title"], "url": url,
                          "sourceId": "gdelt-doc", "sourceName": "GDELT DOC 2.0",
                          "titleHints": [target["query"]], "officialArticleUrls": [url],
                          "reportedAt": None, "dateKind": "index-observed-only",
                          "firstSeenAt": result["firstObservedAt"], "lastSeenAt": result["lastObservedAt"],
                          "verificationStatus": "unverified-lead", "attribution": ATTRIBUTION,
                          "searchTargetId": target["id"]})
    return {**discovery, "items": items}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--discovery", type=Path)
    p.add_argument("--product-state", type=Path)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    directory = ROOT / "site/data"
    def read(path, optional=False):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() or not optional else {}
    config = read(ROOT / "config/cross-platform-sources.json")
    result = search(read(directory / "models.json"), read(args.discovery or directory / "cross-platform-discovery.json"),
                    read(directory / "event-reconciliation.json", True),
                    read(args.product_state or directory / "product-state.json", True),
                    read(OUTPUT, True), config["officialArticleHosts"], datetime.now(timezone.utc))
    print("Source search:", json.dumps(result["summary"], ensure_ascii=False))
    if args.report:
        write_json(args.report, result)
    if not args.dry_run:
        write_json(OUTPUT, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
