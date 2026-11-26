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
from urllib.parse import urlsplit

try:
    from scripts.collect_models import (BlockParser, MAX_BYTES, USER_AGENT, SameHostRedirect,
        article_publication_date, title_identity, match_model, non_release_title, is_release_candidate, write_json)
    from scripts.collect_cross_platform import article_url
    from scripts.collect_release_recall import url_key
except ModuleNotFoundError:
    from collect_models import (BlockParser, MAX_BYTES, USER_AGENT, SameHostRedirect,
        article_publication_date, title_identity, match_model, non_release_title, is_release_candidate, write_json)
    from collect_cross_platform import article_url
    from collect_release_recall import url_key

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site/data/lead-resolution.json"
MAX_PROBES = 12
CATEGORY = {"video", "image", "llm", "music", "tts", "audio"}


def title_agrees(actual, expected):
    if title_identity(actual) == title_identity(expected):
        return True
    # Structured dataset model names may be shorter than the publisher headline.
    # Boundary protection prevents matching GPT-6.2 against GPT-6.2.1.
    if len(expected) > 100 or not re.search(r"\d", expected):
        return False
    parts = re.split(r"[\s_-]+", expected.strip())
    pattern = r"(?<![\w.])" + r"[\s_-]*".join(re.escape(p) for p in parts) + r"(?![\w.])"
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
        return {"status": "family-unresolved", "title": title}
    family = catalog[ids.pop()]
    if family.get("category") not in CATEGORY:
        return {"status": "outside-model-scope", "title": title}
    stamp = article_publication_date(page, title)
    if not stamp:
        return {"status": "date-unresolved", "title": title, "modelId": family["id"]}
    if not (now - timedelta(days=45)).date().isoformat() <= stamp[:10] <= now.date().isoformat():
        return {"status": "outside-current-window", "title": title, "articlePublishedAt": stamp}
    if not is_release_candidate(title, stamp, True):
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
            item = queue.setdefault(key, {"url": url, "titles": set(), "leadIds": set(), "sourceIds": set(),
                                         "reportedDates": set(), "latest": ""})
            item["titles"].add(lead["title"])
            item["leadIds"].add(lead["id"])
            item["sourceIds"].add(lead["sourceId"])
            if lead.get("reportedAt"):
                item["reportedDates"].add(lead["reportedAt"][:10])
            item["latest"] = max(item["latest"], lead.get("reportedAt") or lead.get("firstSeenAt") or "")
    previous_rows = {r["urlKey"]: r for r in previous.get("items", [])}
    def due(key):
        old = previous_rows.get(key, {})
        return not old.get("nextAttemptAt") or old["nextAttemptAt"] <= stamp
    # New URLs first; then retries. Recently reported and multi-source leads take precedence.
    ordered = sorted(queue, key=lambda k: (k not in previous_rows, len(queue[k]["sourceIds"]), queue[k]["latest"]), reverse=True)
    selected = [key for key in ordered if due(key)][:MAX_PROBES]
    def probe(key):
        task, old = queue[key], previous_rows.get(key, {})
        try:
            outcome = parse_article(fetcher(task["url"]), task["url"], sorted(task["titles"]), sources, catalog, now)
        except (OSError, ValueError, TypeError) as exc:
            outcome = {"status": "fetch-failed", "error": f"{type(exc).__name__}: {str(exc)[:180]}"}
        state = outcome["status"]
        failures = 0 if state == "article-date-verified" else int(old.get("consecutiveUnresolved", 0)) + 1
        delay = 24 * 60 if state in {"article-date-verified", "not-model-announcement", "outside-current-window"} else min(24 * 60, 30 * 2 ** min(failures, 6))
        row = {"id": "recovery-" + hashlib.sha256(key.encode()).hexdigest()[:20], "urlKey": key, "url": task["url"],
               "leadIds": sorted(task["leadIds"]), "discoverySourceIds": sorted(task["sourceIds"]),
               "reportedDates": sorted(task["reportedDates"]), "checkedAt": stamp,
               "firstAttemptAt": old.get("firstAttemptAt", stamp), "consecutiveUnresolved": failures,
               "nextAttemptAt": (now + timedelta(minutes=delay)).isoformat(timespec="seconds"), **outcome}
        if state == "article-date-verified":
            row["firstVerifiedAt"] = old.get("firstVerifiedAt", stamp)
        # Preserve last confirmed observation on transient failure without claiming a new successful read.
        elif old.get("status") == "article-date-verified" or old.get("lastVerifiedObservation"):
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
                     "publishedAt": proof["articlePublishedAt"], "discoveredAt": proof["firstVerifiedAt"],
                     "firstSeenAt": proof["firstVerifiedAt"], "lastSeenAt": proof["checkedAt"],
                     "publicationDateKind": "article-explicit-date"})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    def read(path, default=None):
        p = ROOT / path
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    result = resolve(read("site/data/cross-platform-discovery.json", {}), read(OUTPUT, {}),
                     read("config/cross-platform-sources.json"), read("config/model-sources.json"),
                     read("site/data/models.json"), datetime.now(timezone.utc))
    print("Lead resolution:", json.dumps(result["summary"], ensure_ascii=False))
    for row in result["items"]:
        print("[PROOF]", row["url"], row["status"], row.get("articlePublishedAt"), row.get("error", ""))
    if not args.dry_run:
        write_json(OUTPUT, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
