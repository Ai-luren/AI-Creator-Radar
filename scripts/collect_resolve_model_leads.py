#!/usr/bin/env python3
"""Recover first-party publication candidates from external leads, never promote them to releases."""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

try:
    from scripts.collect_models import (BlockParser, MAX_BYTES, USER_AGENT, SameHostRedirect,
        article_publication_date, title_identity, match_model, non_release_title, is_release_candidate, write_json)
    from scripts.collect_cross_platform import article_url
    from scripts.collect_release_recall import url_key, article_day_stamp
except ModuleNotFoundError:
    from collect_models import (BlockParser, MAX_BYTES, USER_AGENT, SameHostRedirect,
        article_publication_date, title_identity, match_model, non_release_title, is_release_candidate, write_json)
    from collect_cross_platform import article_url
    from collect_release_recall import url_key, article_day_stamp

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site/data/lead-resolution.json"
MAX_PROBES = 12
RESOLVER_REVISION = 4
CATEGORY = {"video", "image", "llm", "music", "tts", "audio"}


def compact_heading(title):
    # Many publishers omit the introductory verb and repeated brand in H1.
    title = re.sub(r"^(?:introducing|announcing|meet)\s+", "", str(title or "").strip(), flags=re.I)
    first = re.match(r"^([A-Za-z][A-Za-z0-9-]+)\s+", title)
    if first:
        title = re.sub(r"(\band\s+|&\s*)" + re.escape(first.group(1)) + r"\s+", r"\1", title, flags=re.I)
    return title_identity(title)


def title_agrees(actual, expected):
    if title_identity(actual) == title_identity(expected) or compact_heading(actual) == compact_heading(expected):
        return True
    # Structured dataset model names may be shorter than the publisher headline.
    # Boundary protection prevents matching GPT-6.2 against GPT-6.2.1.
    if len(expected) > 100 or not re.search(r"\d", expected):
        return False
    parts = re.split(r"[\s_-]+", expected.strip())
    pattern = r"(?<![\w.])" + r"[\s_-]*".join(re.escape(p) for p in parts) + r"(?![\w.]|[-_]\w|\s+(?:turbo|flash|pro|lite|mini|ultra|plus|max|preview|thinking|live|fast|medical)\b)"
    return bool(re.search(pattern, actual, re.I))


def source_families(url, title, sources):
    host = urlsplit(url).hostname
    families = set()
    for s in sources:
        if s.get("active") is not True or s.get("official") is not True:
            continue
        endpoints = [s["url"], *s.get("fallbackUrls", []),
                     *(e["url"] for e in s.get("fallbackEndpoints", []))]
        hosts = {urlsplit(u).hostname for u in endpoints} | set(s.get("articleHosts", [])) | set(s.get("announcementHosts", []))
        if host in hosts:
            found = match_model(title, s)
            if found:
                families.add(found)
    return families


def explicit_body_release(blocks, title, family):
    """Recognize a same-model launch statement in the article introduction only."""
    names = {v.get("name", "") for v in family.get("versions", [])}
    names = sorted((name for name in names if name and re.search(r"\d", name)
                    and title_agrees(title, name)), key=len, reverse=True)
    if not names:
        return False
    name = names[0]
    model_pattern = r"[\s_-]+".join(re.escape(p) for p in re.split(r"[\s_-]+", name))
    vendor_pattern = re.escape(family["vendor"])
    heading = next((b["sequence"] for b in blocks if b["tag"] == "h1" and b["text"] == title), None)
    if heading is None:
        return False
    paragraphs = [b["text"] for b in blocks if b["tag"] == "p" and heading < b["sequence"] <= heading + 80][:8]
    pattern = (r"(?:^|[.!?]\s+)Today,\s+(?:" + vendor_pattern + r"\s+(?:is releasing|has released|is launching|has launched|introduces)|we\s+(?:are releasing|have released|are launching|have launched|introduce))\s+"
               + model_pattern + r"(?=\s*[,.;:!?]|\s*$)")
    return any(re.search(pattern, p, re.I) for p in paragraphs)


def parse_article(page, url, titles, sources, catalog, now):
    parser = BlockParser()
    parser.feed(page)
    parser.close()
    headings = [b["text"] for b in sorted(parser.blocks, key=lambda b: b["sequence"]) if b["tag"] == "h1"]
    matches = list(dict.fromkeys(t for t in headings if any(title_agrees(t, x) for x in titles)))
    if len(matches) != 1:
        return {"status": "identity-unresolved"}
    title = matches[0]
    if non_release_title(title) or re.search(r"\b(?:partnership|case study|customer story|pricing|tutorial|guide)\b|合作伙伴|使用教程", title, re.I):
        return {"status": "not-model-announcement", "title": title}
    ids = source_families(url, title, sources) & set(catalog)
    if len(ids) != 1:
        # Record an unclassified official article without fabricating a family.
        stamp = article_publication_date(page, title, leading_date=urlsplit(url).hostname in {"www.anthropic.com", "anthropic.com", "z.ai"})
        return {"status": "family-unresolved", "title": title,
                "articlePublishedAt": stamp, "possibleModelFamilyIds": sorted(ids)}
    family = catalog[ids.pop()]
    if family.get("category") not in CATEGORY:
        return {"status": "outside-model-scope", "title": title}
    stamp = article_publication_date(page, title, leading_date=urlsplit(url).hostname in {"www.anthropic.com", "anthropic.com", "z.ai"})
    if not stamp:
        return {"status": "date-unresolved", "title": title, "modelId": family["id"]}
    day = article_day_stamp(stamp, url)[:10]
    if not (now - timedelta(days=45)).date().isoformat() <= day <= now.date().isoformat():
        return {"status": "outside-current-window", "title": title, "articlePublishedAt": stamp,
                "modelId": family["id"], "vendor": family["vendor"], "category": family["category"]}
    if not is_release_candidate(title, stamp, True) and not explicit_body_release(sorted(parser.blocks, key=lambda b: b["sequence"]), title, family):
        return {"status": "not-model-announcement", "title": title}
    return {"status": "article-date-verified", "title": title, "modelId": family["id"],
            "vendor": family["vendor"], "category": family["category"], "articlePublishedAt": stamp}


def fetch_page(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urllib.request.build_opener(SameHostRedirect()).open(request, timeout=12) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Article exceeds size limit")
    return data.decode("utf-8", errors="replace")


def choose_article_url(task, old, config):
    """One request per article per cycle. Retry a publisher's language variant
    only after a missing heading, never after access denial or a date conflict."""
    primary = task["url"]
    key = url_key(primary)
    allowed = config["officialArticleHosts"]
    variants = [primary, *sorted(task["urls"] - {primary})]
    parts = urlsplit(primary)
    policy = config.get("articleLocaleQueries", {}).get(parts.hostname, {})
    # Configuration is publisher-specific and may only vary the known locale key.
    if policy.get("key") == "lang" and policy.get("value") in {"en", "zh"}:
        pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "lang"]
        candidate = urlunsplit((parts.scheme, parts.netloc, parts.path,
                                urlencode(pairs + [("lang", policy["value"])]), ""))
        variants.append(candidate)
    variants = list(dict.fromkeys(u for u in variants if article_url(u, allowed) and url_key(u) == key))
    last = old.get("url")
    if old.get("status") == "identity-unresolved" and len(variants) > 1:
        return variants[(variants.index(last) + 1) % len(variants)] if last in variants else variants[1]
    # Recheck the exact previously fetched representation when still allowed.
    return last if last in variants else primary


def resolve(discovery, previous, config, sources, families, now, fetcher=fetch_page):
    catalog = {m["id"]: m for m in families}
    stamp = now.isoformat(timespec="seconds")
    allowed = config["officialArticleHosts"]
    queue = {}
    for lead in discovery.get("items", []):
        for raw in lead.get("officialArticleUrls", []):
            url = article_url(raw, allowed)
            if not url:
                continue
            key = url_key(url)
            if not key:
                continue
            item = queue.setdefault(key, {"url": url, "urls": set(), "titles": set(), "leadIds": set(), "sourceIds": set(),
                                         "reportedDates": set(), "latest": ""})
            item["urls"].add(url)
            item["titles"].add(lead["title"])
            item["titles"].update(t for t in lead.get("titleHints", []) if isinstance(t, str) and t.strip())
            item["leadIds"].add(lead["id"])
            item["sourceIds"].add(lead["sourceId"])
            if lead.get("reportedAt"):
                item["reportedDates"].add(lead["reportedAt"][:10])
            item["latest"] = max(item["latest"], lead.get("reportedAt") or lead.get("firstSeenAt") or "")
    previous_rows = {r["urlKey"]: r for r in previous.get("items", [])}
    def due(key):
        old = previous_rows.get(key, {})
        return (not old.get("nextAttemptAt") or old["nextAttemptAt"] <= stamp
                or (old.get("status") in {"not-model-announcement", "identity-unresolved", "family-unresolved", "date-unresolved"} and old.get("resolverRevision", 0) < RESOLVER_REVISION)
                or (old.get("status") in {"identity-unresolved", "family-unresolved"}
                    and (not set(queue[key]["leadIds"]).issubset(old.get("leadIds", []))
                         or not set(queue[key]["titles"]).issubset(old.get("titleHintsChecked", [])))))
    # New URLs first; then retries. Recently reported and multi-source leads take precedence.
    ordered = sorted(queue, key=lambda k: (k not in previous_rows, len(queue[k]["sourceIds"]), queue[k]["latest"]), reverse=True)
    eligible = [key for key in ordered if due(key)]
    new = [key for key in eligible if key not in previous_rows]
    retries = sorted((key for key in eligible if key in previous_rows), key=lambda k: previous_rows[k].get("nextAttemptAt") or "")
    # Prevent a continuous stream of new leads from starving deferred evidence.
    selected = new[:8] + retries[:4]
    selected += [key for key in eligible if key not in selected][:MAX_PROBES-len(selected)]
    def probe(key):
        task, old = queue[key], previous_rows.get(key, {})
        request_url = choose_article_url(task, old, config)
        try:
            outcome = parse_article(fetcher(request_url), request_url, sorted(task["titles"]), sources, catalog, now)
        except (OSError, ValueError, TypeError) as exc:
            outcome = {"status": "fetch-failed", "error": f"{type(exc).__name__}: {str(exc)[:180]}"}
        state = outcome["status"]
        failures = 0 if state == "article-date-verified" else int(old.get("consecutiveUnresolved", 0)) + 1
        delay = 24 * 60 if state in {"article-date-verified", "not-model-announcement", "outside-current-window"} else min(24 * 60, 30 * 2 ** min(failures, 6))
        row = {"id": "recovery-" + hashlib.sha256(key.encode()).hexdigest()[:20], "urlKey": key, "url": request_url,
               "leadIds": sorted(task["leadIds"]), "discoverySourceIds": sorted(task["sourceIds"]),
               "titleHintsChecked": sorted(task["titles"]), "resolverRevision": RESOLVER_REVISION,
               "reportedDates": sorted(task["reportedDates"]), "checkedAt": stamp,
               "firstAttemptAt": old.get("firstAttemptAt", stamp), "consecutiveUnresolved": failures,
               "nextAttemptAt": (now + timedelta(minutes=delay)).isoformat(timespec="seconds"), **outcome}
        if state == "article-date-verified":
            row["firstVerifiedAt"] = old.get("firstVerifiedAt") or (old.get("lastVerifiedObservation") or {}).get("firstVerifiedAt") or stamp
        # Preserve last confirmed observation on transient failure without claiming a new successful read.
        elif state == "fetch-failed" and (old.get("status") == "article-date-verified" or old.get("lastVerifiedObservation")):
            prior = old.get("lastVerifiedObservation") or {k: old[k] for k in ("title", "modelId", "vendor", "category", "articlePublishedAt", "firstVerifiedAt", "checkedAt")}
            row["lastVerifiedObservation"] = prior
        return key, row
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        current = dict(pool.map(probe, selected))
    rows = [current.get(key) or previous_rows[key] for key in ordered if key in current or key in previous_rows]
    counts = {"uniqueOfficialUrls": len(queue), "attempted": len(selected),
              "articleDateVerified": sum(r["status"] == "article-date-verified" for r in rows),
              "newlyCheckedVerified": sum(r["status"] == "article-date-verified" for r in current.values()),
              "awaitingProbe": len(queue) - len(rows),
              "unresolved": sum(r["status"] not in {"article-date-verified", "not-model-announcement", "outside-current-window"} for r in rows),
              "notAnnouncement": sum(r["status"] == "not-model-announcement" for r in rows)}
    return {"schema": "lead-resolution/v1", "checkedAt": stamp, "summary": counts, "items": rows[:500]}


def candidate_rows(resolution):
    rows = []
    for row in resolution.get("items", []):
        # A failed recheck must not remove a previously proven publication-date observation.
        proof = row if row.get("status") == "article-date-verified" else row.get("lastVerifiedObservation")
        if not proof:
            continue
        rows.append({"id": row["id"], "title": proof["title"], "modelId": proof["modelId"], "vendor": proof["vendor"],
                     "category": proof["category"], "url": row["url"], "sourceId": "official-article-recovery",
                     "sourceName": "官方文章原文 · 跨平台发现", "official": True, "updateType": "model-card",
                     "summary": "已读取官方文章日期及型号标题；正式首发阶段仍待核验。",
                     "publishedAt": article_day_stamp(proof["articlePublishedAt"], row["url"]),
                     "articlePublishedAt": proof["articlePublishedAt"], "discoveredAt": proof["firstVerifiedAt"],
                     "firstSeenAt": proof["firstVerifiedAt"], "lastSeenAt": proof["checkedAt"],
                     "publicationDateKind": "article-explicit-date"})
    return rows



def reconcile_candidate_dates(updates, resolution):
    """Correct weak listing observations in derived views; do not mutate raw evidence."""
    index = {}
    for proof in candidate_rows(resolution):
        key = (proof["modelId"], url_key(proof["url"]))
        if key[1]:
            index.setdefault(key, []).append(proof)
    # Historical observations must also correct undated duplicates; otherwise a
    # rediscovered old article re-enters the rolling recent window forever.
    for row in resolution.get("items", []):
        if row.get("status") != "outside-current-window" or not row.get("articlePublishedAt") or not row.get("checkedAt"):
            continue
        article_date = article_day_stamp(row["articlePublishedAt"], row["url"])
        try:
            observed = datetime.fromisoformat(row["checkedAt"].replace("Z", "+00:00"))
            day = datetime.fromisoformat(article_date.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            continue
        if day >= (observed - timedelta(days=45)).date():
            continue
        # Migrate older proof records that predate modelId: only same article,
        # exact normalized title, official provenance, and one unique family.
        matched = {u.get("modelId") for u in updates if u.get("official") is True and u.get("modelId")
                   and url_key(u.get("url")) == url_key(row["url"])
                   and title_identity(u.get("title") or "") == title_identity(row.get("title") or "")}
        fid = row.get("modelId") or (next(iter(matched)) if len(matched) == 1 else None)
        if not fid or matched != {fid}:
            continue
        proof = {"id": row["id"], "title": row["title"], "modelId": fid, "url": row["url"],
                 "publishedAt": article_date, "articlePublishedAt": row["articlePublishedAt"],
                 "lastSeenAt": row["checkedAt"]}
        index.setdefault((fid, url_key(row["url"])), []).append(proof)
    output = []
    corrections = []
    for original in updates:
        item = dict(original)
        key = (item.get("modelId"), url_key(item.get("url")))
        matches = [p for p in index.get(key, [])
                   if title_agrees(p["title"], item.get("title") or "") or title_agrees(item.get("title") or "", p["title"])]
        days = {p["publishedAt"][:10] for p in matches}
        current_day = str(item.get("publishedAt") or "")[:10]
        if (item.get("official") is True and len(days) == 1
                and item.get("publicationDateKind") not in {"jsonld-datePublished", "feed-published", "article-explicit-date"}
                and current_day not in days):
            proof = matches[0]
            item["listingPublishedAt"] = item.get("publishedAt")
            item["publishedAt"] = proof["publishedAt"]
            item["publicationDateKind"] = "article-explicit-date"
            item["publicationObservedAt"] = proof["lastSeenAt"]
            item["articlePublishedAt"] = proof.get("articlePublishedAt", proof["publishedAt"])
            item["recoveryProofId"] = proof["id"]
            corrections.append({"updateId": item["id"], "previousDate": original.get("publishedAt"),
                                "articleDate": item["publishedAt"], "proofId": proof["id"]})
        output.append(item)
    return output, corrections


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--discovery", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    def read(path, default=None):
        p = ROOT / path
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    discovery = json.loads(args.discovery.read_text(encoding="utf-8")) if args.discovery else read("site/data/cross-platform-discovery.json", {})
    result = resolve(discovery, {} if args.discovery else read(OUTPUT, {}),
                     read("config/cross-platform-sources.json"), read("config/model-sources.json"),
                     read("site/data/models.json"), datetime.now(timezone.utc))
    _, corrections = reconcile_candidate_dates(read("site/data/model-updates.json", {}).get("items", []), result)
    result["candidateDateCorrections"] = corrections
    result["summary"]["weakCandidateDatesCorrected"] = len(corrections)
    print("Lead resolution:", json.dumps(result["summary"], ensure_ascii=False))
    for row in result["items"]:
        print("[PROOF]", row["url"], row["status"], row.get("articlePublishedAt"), row.get("error", ""))
    if args.report:
        write_json(args.report, result)
    if not args.dry_run:
        write_json(OUTPUT, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
