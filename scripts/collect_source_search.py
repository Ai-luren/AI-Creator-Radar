#!/usr/bin/env python3
"""Bounded independent news-index lookup for unresolved model leads.

No paid API, guessed publisher paths, benchmark URLs, or inferred release dates.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import gzip
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlsplit

try:
    from scripts.collect_models import SameHostRedirect, USER_AGENT, clean_text, non_release_title, write_json, access_retry_at
    from scripts.collect_cross_platform import article_url, https_url
    from scripts.collect_release_recall import url_key
    from scripts.event_identity import identify, model_index
except ModuleNotFoundError:
    from collect_models import SameHostRedirect, USER_AGENT, clean_text, non_release_title, write_json, access_retry_at
    from collect_cross_platform import article_url, https_url
    from collect_release_recall import url_key
    from event_identity import identify, model_index

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site/data/source-search.json"
ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
ATTRIBUTION = {"name": "GDELT DOC 2.0", "url": "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"}
AIHOT_ENDPOINT = "https://aihot.news/api/v1/items"
AIHOT_ATTRIBUTION = {"name": "AIHOT", "url": "https://aihot.news"}
AIPICK_ENDPOINT = "https://aipick.news/api/v1/items"
AIPICK_ATTRIBUTION = {"name": "AIPick", "url": "https://aipick.news"}
MAX_BYTES = 2 * 1024 * 1024
BROAD_DEADLINE_SECONDS = 8
BROAD_SOCKET_TIMEOUT_SECONDS = 6
OPEN_STATES = {"needs-source", "probe-unresolved", "awaiting-probe", "needs-product-identity", "needs-repository-identity"}


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
    names = {(f["id"], v["id"]): (safe_name(v.get("name")) or safe_name((v.get("releaseEvidence") or {}).get("modelName")))
             for f in families for v in f.get("versions", [])}
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
        elif task.get("taskType") in {"product-observation", "independent-repository"}:
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


def unverified_channel_pointer(raw):
    """Retain a discovered original social/WeChat URL, not an official proof."""
    try:
        p = urlsplit(raw or "")
        if p.scheme != "https" or p.username or p.password or p.port not in (None, 443):
            return None
        if p.hostname in {"x.com", "twitter.com", "www.x.com", "www.twitter.com"} and re.fullmatch(r"/[A-Za-z0-9_]{1,15}/status/[0-9]{10,25}/?", p.path):
            return "https://x.com" + p.path.rstrip("/")
        if p.hostname == "mp.weixin.qq.com" and re.fullmatch(r"/s/[A-Za-z0-9_-]{8,100}", p.path):
            return "https://mp.weixin.qq.com" + p.path
    except (ValueError, TypeError):
        pass
    return None


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
        channel = unverified_channel_pointer(lead.get("url"))
        if channel:
            add({"kind": "publisher-channel-pointer-unverified", "sourceUrl": channel,
                 "sourceRecordId": lead["id"], "sourceId": lead["sourceId"],
                 "assertedDate": None, "originalVerificationAt": None,
                 "lastObservedAt": lead.get("lastSeenAt") or lead.get("firstSeenAt"),
                 "provenance": "existing-discovery"})
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
    with urllib.request.build_opener(SameHostRedirect()).open(req, timeout=BROAD_SOCKET_TIMEOUT_SECONDS) as response:
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("Index response exceeds size limit")
    return parse_results(json.loads(body), target, allowed, families)


class BroadSearchDeadlineExceeded(TimeoutError):
    pass


def broad_search_worker():
    """One fixed-provider, read-only request; only the parent persists results."""
    request = json.load(sys.stdin)
    try:
        rows = fetch(request["target"],request["allowed"],request["families"])
        response = {"rows":rows}
    except urllib.error.HTTPError as exc:
        response = {"httpError":exc.code,"reason":str(exc.reason)[:120],
                    "retryAfter":exc.headers.get("Retry-After","") if exc.headers else ""}
    except (OSError,ValueError,TypeError) as exc:
        response = {"error":f"{type(exc).__name__}: {str(exc)[:160]}"}
    print(json.dumps(response,ensure_ascii=False))
    return 0


def bounded_broad_fetch(target,allowed,families,runner=subprocess.run):
    payload = json.dumps({"target":target,"allowed":allowed,"families":families},ensure_ascii=False)
    try:
        completed = runner([sys.executable,str(Path(__file__).resolve()),"--broad-search-worker"],
                           input=payload,text=True,capture_output=True,check=True,timeout=BROAD_DEADLINE_SECONDS)
    except subprocess.TimeoutExpired as exc:
        raise BroadSearchDeadlineExceeded(f"GDELT hard wall-clock budget {BROAD_DEADLINE_SECONDS}s") from exc
    except subprocess.SubprocessError as exc:
        raise OSError("GDELT worker failed") from exc
    obj = json.loads(completed.stdout)
    if not isinstance(obj,dict):
        raise ValueError("Invalid GDELT worker response")
    if "httpError" in obj:
        code = obj["httpError"]
        if type(code) is not int or not 400<=code<=599:
            raise ValueError("Invalid GDELT HTTP error")
        raise urllib.error.HTTPError(ENDPOINT,code,obj.get("reason",""),
                                     {"Retry-After":obj.get("retryAfter","")},None)
    if "error" in obj:
        raise OSError(obj["error"])
    if not isinstance(obj.get("rows"),list):
        raise ValueError("Missing GDELT worker rows")
    return obj["rows"]


def broad_fallback_ready(target,now,recent_cutoff,providers):
    """A normal aggregator cooldown is not an observed coverage gap."""
    first = stamp(target.get("firstDetectedAt"))
    if not target.get("identity") or first is None or first<recent_cutoff:
        return True
    # Targets with existing index pointers are intentionally not re-queried
    # by the aggregate adapter; allow their ordinary due broad recovery.
    if any(row.get("officialCandidateUrl") for row in target.get("results",[])):
        return True
    for prefix,state,configured in providers:
        if not configured:
            continue
        attempted = stamp(target.get(prefix+"LastAttemptAt"))
        until = stamp(state.get("nextAttemptAt"))
        if attempted is not None and attempted<=now:
            continue
        if state.get("error") and until is not None and until>now:
            continue
        return False
    return True


def parse_aihot_pointers(payload, target, allowed, families, provider="aihot-targeted"):
    """Consume bounded results transiently. Keep only original publisher pointers,
    exact local model labels and attribution, never AIHOT headlines or summaries.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("Unexpected AIHOT response schema")
    identity = target.get("identity") or {}
    expected = (identity.get("modelFamilyId"), identity.get("modelVersionId"))
    if not all(expected):
        return []
    index = model_index(families)
    if provider not in {"aihot-targeted","aipick-targeted"}:
        raise ValueError("Unsupported aggregation provider")
    host = "aihot.news" if provider=="aihot-targeted" else "aipick.news"
    attribution = AIHOT_ATTRIBUTION if provider=="aihot-targeted" else AIPICK_ATTRIBUTION
    found = {}
    for item in payload["items"][:20]:
        if not isinstance(item, dict) or item.get("category") != "ai-models":
            continue
        title = clean_text(item.get("title") or "")
        original = clean_text(item.get("originalTitle") or "")
        if not title or non_release_title(title) or (original and non_release_title(original)):
            continue
        if identify(index, title, [original] if original else []) != expected:
            continue
        links = item.get("links") or {}
        if not isinstance(links, dict):
            continue
        url = article_url(links.get("original"), allowed)
        canonical = https_url(links.get("aihot"))
        p = urlsplit(canonical or "")
        if not url or p.hostname != host or not re.fullmatch(r"/items/[A-Za-z0-9_-]{1,100}", p.path) or p.query or p.fragment:
            continue
        key = url_key(url)
        if not key:
            continue
        found[key] = {"url": url, "title": target["query"], "domain": urlsplit(url).hostname,
                      "indexSeenAt": None, "officialCandidateUrl": url,
                      "claimType": "index-discovery", "provider": provider,
                      "attribution": attribution, "discoveryPointer": canonical}
    return sorted(found.values(), key=lambda r:r["url"])[:2]


def fetch_aggregator(target, allowed, families, etag=None, provider="aihot-targeted"):
    query = urlencode({"mode": "all", "category": "ai-models", "window": "7d",
                       "q": target["query"], "limit": 20})
    endpoint = AIHOT_ENDPOINT if provider=="aihot-targeted" else AIPICK_ENDPOINT
    headers = {"Accept": "application/json", "Accept-Encoding": "gzip",
               "User-Agent": "aihot-api/2.0.0 " + USER_AGENT if provider=="aihot-targeted" else USER_AGENT}
    if etag:
        headers["If-None-Match"] = etag
    req = urllib.request.Request(endpoint+"?"+query, headers=headers)
    try:
        with urllib.request.build_opener(SameHostRedirect()).open(req, timeout=15) as response:
            body = response.read(MAX_BYTES+1)
            new_etag = response.headers.get("ETag")
            compressed = response.headers.get("Content-Encoding", "").lower()=="gzip"
    except urllib.error.HTTPError as exc:
        if exc.code==304 and etag:
            return None, etag
        raise
    if len(body)>MAX_BYTES:
        raise ValueError("AIHOT response exceeds size limit")
    if compressed:
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
            body=stream.read(MAX_BYTES+1)
    if len(body)>MAX_BYTES:
        raise ValueError("AIHOT decompressed response exceeds size limit")
    return parse_aihot_pointers(json.loads(body),target,allowed,families,provider),new_etag


def fetch_aihot(target, allowed, families, etag=None):
    return fetch_aggregator(target,allowed,families,etag)


def fetch_aipick(target, allowed, families, etag=None):
    return fetch_aggregator(target,allowed,families,etag,"aipick-targeted")


def search(families, discovery, reconciliation, product_state, previous, allowed, now, fetcher=fetch, aihot_fetcher=None, aipick_fetcher=None):
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
    # Use existing high-quality aggregation before broad search. Independent
    # providers keep their own health and per-target cooldown. One request total.
    aihot_service = dict(previous.get("aihotService", {}))
    aipick_service = dict(previous.get("aipickService", {}))
    aihot_attempted = aipick_attempted = 0
    recent_cutoff = now - timedelta(days=7)

    def eligible(prefix, provider_state):
        until = stamp(provider_state.get("nextAttemptAt"))
        if until and until>now:
            return []
        rows = [t for t in targets.values() if t["active"] and t.get("identity")
                and stamp(t.get("firstDetectedAt")) and stamp(t["firstDetectedAt"])>=recent_cutoff
                and not any(r.get("officialCandidateUrl") for r in t.get("results",[]))
                and (not stamp(t.get(prefix+"NextAttemptAt")) or stamp(t[prefix+"NextAttemptAt"])<=now)]
        if prefix=="aipick":
            # AIPick complements, not duplicates, the primary model index.
            # Prefer previously attempted primary queries; permit fresh targets
            # only when the entire primary provider is in failure backoff.
            primary_failed=bool(aihot_service.get("error") and stamp(aihot_service.get("nextAttemptAt"))
                                and stamp(aihot_service["nextAttemptAt"])>now)
            rows=[t for t in rows if t.get("aihotLastAttemptAt") or primary_failed]
        return sorted(rows,key=lambda t:(t.get(prefix+"LastAttemptAt") or "",t["firstDetectedAt"],t["id"]))

    def search_aggregated(target, provider, prefix, provider_state, fetch_fn):
        target[prefix+"LastAttemptAt"]=checked
        try:
            rows,etag=fetch_fn(target,allowed,families,target.get(prefix+"ETag"))
            if rows is not None and not isinstance(rows,list):
                raise ValueError("Invalid aggregate pointers")
            if rows is None and not target.get(prefix+"ETag"):
                raise ValueError("Unexpected aggregate 304")
        except (OSError,ValueError,TypeError) as exc:
            failures=int(provider_state.get("consecutiveFailures",0))+1
            delay=access_retry_at(exc,now,now+timedelta(hours=min(48,6*2**min(failures-1,3))))
            provider_state.update(lastAttemptAt=checked,error=f"{type(exc).__name__}: {str(exc)[:160]}",
                                  consecutiveFailures=failures,nextAttemptAt=delay.isoformat())
            target.update({prefix+"Status":"index-unavailable",prefix+"NextAttemptAt":delay.isoformat()})
        else:
            if rows is not None:
                retained={url_key(r["url"]):r for r in target.get("results",[]) if r.get("provider")!=provider}
                prior={url_key(r["url"]):r for r in target.get("results",[]) if r.get("provider")==provider}
                for row in rows[:2]:
                    key=url_key(row["url"])
                    if key and key not in retained:
                        retained[key]={**row,"firstObservedAt":prior.get(key,{}).get("firstObservedAt") or checked,
                                       "lastObservedAt":checked}
                target["results"]=sorted(retained.values(),key=lambda r:(r["lastObservedAt"],r["url"]),reverse=True)[:40]
            target.update({prefix+"ETag":etag,prefix+"LastSuccessAt":checked,
                           prefix+"Status":"unchanged" if rows is None else "index-candidates" if rows else "no-matching-index-results",
                           prefix+"NextAttemptAt":(now+timedelta(hours=24)).isoformat()})
            provider_state.update(lastAttemptAt=checked,lastSuccessAt=checked,error=None,
                                  consecutiveFailures=0,nextAttemptAt=(now+timedelta(minutes=30)).isoformat())

    if not attempted:
        primary=eligible("aihot",aihot_service) if aihot_fetcher else []
        secondary=eligible("aipick",aipick_service) if aipick_fetcher else []
        if primary:
            aihot_attempted=attempted=1
            search_aggregated(primary[0],"aihot-targeted","aihot",aihot_service,aihot_fetcher)
        elif secondary:
            aipick_attempted=attempted=1
            search_aggregated(secondary[0],"aipick-targeted","aipick",aipick_service,aipick_fetcher)
    providers = (("aihot",aihot_service,aihot_fetcher is not None),
                 ("aipick",aipick_service,aipick_fetcher is not None))
    broad_due = [t for t in due if broad_fallback_ready(t,now,recent_cutoff,providers)]
    if not attempted and broad_due and (not cooldown or cooldown <= now):
        target = broad_due[0]
        attempted = 1
        try:
            results = fetcher(target, allowed, families)
            if not isinstance(results, list):
                raise ValueError("Invalid search results")
        except (OSError, ValueError, TypeError) as exc:
            count = int(service.get("consecutiveFailures", 0)) + 1
            delay = min(1440, 60 * 2 ** min(count, 5))
            if isinstance(exc,BroadSearchDeadlineExceeded):
                # A deadline may hide a late rate-limit response; do not
                # increase pressure on a slow provider by retrying immediately.
                delay = max(delay,360)
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
    return {"schema": "source-search/v1", "checkedAt": checked, "service": service, "aihotService": aihot_service, "aipickService": aipick_service,
            "targets": sorted(targets.values(), key=lambda t: t["id"]),
            "summary": {"activeTargets": len(active_rows), "attemptedThisRun": attempted,
                        "targetStates": dict(sorted(counts.items())),
                        "broadDeferredForAggregators": len(due)-len(broad_due),
                        "broadDeadlineSeconds": BROAD_DEADLINE_SECONDS,
                        "targetsWithLocalContext": sum(bool(t["localContext"]) for t in active_rows),
                        "localContextRecords": sum(len(t["localContext"]) for t in active_rows),
                        "officialCandidates": sum(bool(r.get("officialCandidateUrl")) for t in active_rows for r in t.get("results", [])),
                        "indexReports": sum(not r.get("officialCandidateUrl") for t in active_rows for r in t.get("results", [])),
                        "aipickAttemptedThisRun": aipick_attempted,
                        "aipickLastSuccessAt": aipick_service.get("lastSuccessAt"),
                        "aipickError": aipick_service.get("error"),
                        "aipickPointers": sum(r.get("provider")=="aipick-targeted" for t in active_rows for r in t.get("results", [])),
                        "aihotAttemptedThisRun": aihot_attempted,
                        "aihotLastSuccessAt": aihot_service.get("lastSuccessAt"),
                        "aihotError": aihot_service.get("error"),
                        "aihotPointers": sum(r.get("provider")=="aihot-targeted" for t in active_rows for r in t.get("results", [])),
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
            provider=result.get("provider")
            aggregate=provider in {"aihot-targeted","aipick-targeted"}
            items.append({"id": rid, "title": result["title"], "url": url,
                          "sourceId": provider if aggregate else "gdelt-doc",
                          "sourceName": {"aihot-targeted":"AIHOT 定向寻源","aipick-targeted":"AIPick 定向寻源"}.get(provider,"GDELT DOC 2.0"),
                          "titleHints": [target["query"]], "officialArticleUrls": [url],
                          "reportedAt": None, "dateKind": "index-observed-only",
                          "firstSeenAt": result["firstObservedAt"], "lastSeenAt": result["lastObservedAt"],
                          "verificationStatus": "unverified-lead",
                          "attribution": {"aihot-targeted":AIHOT_ATTRIBUTION,"aipick-targeted":AIPICK_ATTRIBUTION}.get(provider,ATTRIBUTION),
                          **({"discoveryPointer":result["discoveryPointer"]} if aggregate else {}),
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
                    read(OUTPUT, True), config["officialArticleHosts"], datetime.now(timezone.utc), fetcher=bounded_broad_fetch, aihot_fetcher=fetch_aihot, aipick_fetcher=fetch_aipick)
    print("Source search:", json.dumps(result["summary"], ensure_ascii=False))
    if args.report:
        write_json(args.report, result)
    if not args.dry_run:
        write_json(OUTPUT, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(broad_search_worker() if sys.argv[1:]==["--broad-search-worker"] else main())
