#!/usr/bin/env python3
"""Read public cross-platform leads, isolated from authoritative release records."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, unquote
import xml.etree.ElementTree as ET

try:
    from scripts.collect_models import (MAX_BYTES, USER_AGENT, SameHostRedirect, clean_text,
        child_text, entry_link, local_name, parse_date, non_release_title, normalize_url, write_json)
except ModuleNotFoundError:
    from collect_models import (MAX_BYTES, USER_AGENT, SameHostRedirect, clean_text,
        child_text, entry_link, local_name, parse_date, non_release_title, normalize_url, write_json)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/cross-platform-sources.json"
OUTPUT = ROOT / "site/data/cross-platform-discovery.json"
MODEL_SIGNAL = re.compile(r"\b(?:GPT[- ]?(?:Image|Live|\d)|Claude|Gemini|Veo|Imagen|Nano Banana|Seedance|Seedream|Kling|Niji|Midjourney|GLM|DeepSeek|Qwen|Wan\d|HappyHorse|MiniMax|Hailuo|Vidu|PixVerse|Grok|Muse|Suno|Mureka|Scribe|Eleven|Llama|MAGI)\b", re.I)


def https_url(value):
    try:
        p = urlsplit(value or "")
        if p.scheme == "https" and p.hostname and not p.username and not p.password and p.port in (None,443):
            return normalize_url(value)
    except (ValueError, TypeError):
        pass
    return ""


def article_url(value, allowed):
    url = https_url(value)
    if not url:
        return ""
    p = urlsplit(url)
    path = unquote(p.path)
    if "\\" in path or any(part in {".", ".."} for part in path.split("/")) or path != p.path:
        return ""
    if p.hostname == "qwen.ai" and path == "/blog":
        return url if any(k == "id" and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", v) for k, v in parse_qsl(p.query)) else ""
    return url if any(path.startswith(prefix) and path != prefix for prefix in allowed.get(p.hostname, [])) else ""


def feed_leads(body, source, allowed):
    root = ET.fromstring(body)
    if local_name(root.tag) not in {"rss", "feed", "rdf"}:
        raise ValueError("Expected RSS/Atom document")
    rows = []
    for item in [n for n in root.iter() if local_name(n.tag) in {"entry", "item"}][:100]:
        title = clean_text(child_text(item, {"title"}))
        link = https_url(entry_link(item))
        if not title or not link or not MODEL_SIGNAL.search(title) or non_release_title(title):
            continue
        summary = child_text(item, {"description", "summary", "content", "encoded"}) or ""
        # Link extraction only; do not execute HTML or follow third-party redirects.
        candidates = [link]
        candidates.extend(re.findall(r'https://[^\s<>"\']+', summary))
        urls = sorted({u for v in candidates if (u := article_url(v.rstrip(".,);"), allowed))})
        published = parse_date(child_text(item, {"pubdate", "published", "date"}))
        rows.append({"title": title[:240], "url": link, "sourceId": source["id"], "sourceName": source["name"],
                     "reportedAt": published, "dateKind": "external-feed-date",
                     "officialArticleUrls": urls[:5], "verificationStatus": "unverified-lead"})
    return rows


def hf_leads(body, source):
    data = json.loads(body)
    if not isinstance(data, list):
        raise ValueError("Expected Hugging Face model list")
    rows = []
    prefix = source["author"].casefold() + "/"
    for item in data[:20]:
        if not isinstance(item, dict):
            continue
        repo = item.get("id") or item.get("modelId") or ""
        if not repo.casefold().startswith(prefix) or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
            continue
        url = "https://huggingface.co/" + repo
        rows.append({"title": repo, "url": url, "sourceId": source["id"], "sourceName": source["name"],
                     "reportedAt": parse_date(item.get("createdAt")), "dateKind": "repository-created-at",
                     "officialArticleUrls": [], "verificationStatus": "unverified-model-repository"})
    return rows



def llm_world_leads(body, source, allowed):
    """Read event-scoped source links; never inherit external release assertions."""
    data = json.loads(body)
    if not isinstance(data, dict) or not isinstance(data.get("releases"), list) or not str(data.get("schema_version", "")).startswith("1."):
        raise ValueError("Unsupported LLM World schema")
    rows = []
    for item in data["releases"]:
        name = str(item.get("model") or "").strip()
        if not name or len(name) > 160 or not MODEL_SIGNAL.search(name):
            continue
        refs = {s.get("id"): s for s in item.get("sources", []) if isinstance(s, dict)}
        for event in item.get("events", []):
            stamp = parse_date(event.get("date"))
            if not stamp or event.get("type") not in {"announcement", "release", "launch", "general_availability", "availability", "open_weights", "open_weights_release"}:
                continue
            urls = sorted({url for key in event.get("sources", [])
                           if (ref := refs.get(key, {})).get("authority") == "primary"
                           and (url := article_url(ref.get("url"), allowed))})
            if not urls:
                continue
            rows.append({"title": name, "url": urls[0], "sourceId": source["id"], "sourceName": source["name"],
                         "reportedAt": stamp, "dateKind": "external-dataset-event-date",
                         "officialArticleUrls": urls[:5], "verificationStatus": "unverified-lead",
                         "attribution": {"name": "LLM World", "url": source["project"],
                                         "license": source["license"], "licenseUrl": source["licenseUrl"]}})
    return sorted(rows, key=lambda row: row["reportedAt"], reverse=True)[:100]


def fetch(source, allowed):
    try:
        req = urllib.request.Request(source["url"], headers={"User-Agent": USER_AGENT,
                                     "Accept": "application/json, application/rss+xml, application/atom+xml, */*"})
        with urllib.request.build_opener(SameHostRedirect()).open(req, timeout=15) as response:
            body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("Source exceeds size limit")
        if source["type"] == "hf-models":
            rows = hf_leads(body, source)
        elif source["type"] == "llm-world-json":
            rows = llm_world_leads(body, source, allowed)
        else:
            rows = feed_leads(body, source, allowed)
        return source, rows, None
    except Exception as exc:
        return source, [], f"{type(exc).__name__}: {str(exc)[:180]}"


def collect(config, previous, now, fetcher=fetch):
    old = {r["id"]: r for r in previous.get("items", [])}
    statuses = []
    old_status = {s["id"]: s for s in previous.get("sources", [])}
    stamp = now.isoformat(timespec="seconds")
    cutoff = (now - timedelta(days=45)).date().isoformat()
    today = now.date().isoformat()
    def due(source):
        prior = old_status.get(source["id"], {})
        if prior.get("url") == source["url"] and prior.get("nextAttemptAt") and prior["nextAttemptAt"] > stamp:
            return False
        return True
    active = [source for source in config["sources"] if due(source)]
    for source in config["sources"]:
        if not due(source):
            statuses.append({**old_status[source["id"]], "deferred": True})
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda s: fetcher(s, config["officialArticleHosts"]), active))
    for source, rows, error in results:
        accepted = 0
        for row in rows:
            # Future dates and stale model uploads are not recent launch leads.
            day = str(row.get("reportedAt") or "")[:10]
            if day and not cutoff <= day <= today:
                continue
            row_id = hashlib.sha256((row["sourceId"] + "|" + row["url"] + "|" + row["title"]).encode()).hexdigest()[:20]
            first = old.get(row_id, {}).get("firstSeenAt", stamp)
            old[row_id] = {"id": row_id, **row, "firstSeenAt": first, "lastSeenAt": stamp}
            accepted += 1
        prior = old_status.get(source["id"], {})
        failures = int(prior.get("consecutiveFailures", 0)) + 1 if error else 0
        delay = min(24 * 60, 30 * (2 ** min(failures, 6))) if error else 0
        statuses.append({"id": source["id"], "name": source["name"], "url": source["url"],
                         "error": error, "itemCount": accepted, "checkedAt": stamp,
                         "deferred": False, "consecutiveFailures": failures,
                         "lastSuccessAt": prior.get("lastSuccessAt") if error else stamp,
                         "nextAttemptAt": (now + timedelta(minutes=delay)).isoformat(timespec="seconds") if delay else None})
    items = [r for r in old.values() if cutoff <= str(r.get("reportedAt") or r.get("firstSeenAt") or "")[:10] <= today]
    items.sort(key=lambda r: (r.get("reportedAt") or r["firstSeenAt"], r["id"]), reverse=True)
    return {"schema": "cross-platform-discovery/v1", "checkedAt": stamp,
            "sources": statuses, "items": items[:500], "policy": "辅助线索；不计正式发布，不写入模型库/发展史，不以仓库创建日当首发日"}



# Existing repository snapshots, not extra HTTP requests. Their dates are observation
# dates or third-party reports, never evidence of first release.
LOCAL_INPUTS = (
    ("local-aihot-selected", "AIHOT 精选", "aihot-items.json", "fetchedAt"),
    ("local-aihot-daily", "AIHOT 日报", "aihot-daily.json", "fetchedAt"),
    ("local-juya-daily", "橘鸦 AI 早报", "juya-daily.json", "fetchedAt"),
    ("local-official-candidates", "既有官方候选索引", "model-updates.json", "generatedAt"),
)
LOCAL_RELEASE_CATEGORIES = {"ai-models", "模型发布", "模型发布/更新", "模型发布／更新", "模型"}


def literal_model_hints(title, families):
    """Only exact names already present in canonical catalog; no invented versions."""
    names = set()
    for family in families:
        for version in family.get("versions", []):
            name = str(version.get("name") or "").strip()
            if len(name) >= 5 and re.search(r"\d", name):
                if re.search(r"(?<![A-Za-z0-9.])" + re.escape(name) + r"(?![A-Za-z0-9.]|[-_][A-Za-z0-9])", title, re.I):
                    names.add(name)
    # Nested version prefixes are redundant; multiple independent names are
    # ambiguous in a translated headline, so don't supply a model hint.
    names = {n for n in names if not any(n.casefold() != m.casefold() and n.casefold() in m.casefold() for m in names)}
    return sorted(names) if len(names) == 1 else []


def local_snapshot_leads(source_id, source_name, snapshot, stamp_field, allowed, families, model_sources):
    stamp = parse_date(snapshot.get(stamp_field))
    if not stamp or not isinstance(snapshot.get("items"), list):
        raise ValueError("Missing valid snapshot observation or items")
    edition = parse_date(re.search(r"20\d{2}\s*[-年]\s*\d{1,2}\s*[-月]\s*\d{1,2}", snapshot.get("title", "")).group(0).replace(" ", "")) if re.search(r"20\d{2}\s*[-年]\s*\d{1,2}\s*[-月]\s*\d{1,2}", snapshot.get("title", "")) else None
    official_index = source_id == "local-official-candidates"
    listings = {normalize_url(u).rstrip("/") for s in model_sources for u in
                [s["url"], *s.get("fallbackUrls", []), *(e["url"] for e in s.get("fallbackEndpoints", []))]}
    rows = []
    for item in snapshot["items"]:
        title = clean_text(item.get("title") or "")
        if not title or non_release_title(title):
            continue
        if official_index:
            if item.get("official") is not True or not item.get("modelId") or item.get("updateType") not in {"release", "model-release", "model-card", "announcement"}:
                continue
            if item.get("publicationDateKind") in {"jsonld-datePublished", "feed-published", "article-explicit-date"}:
                continue
            url = article_url(item.get("url"), allowed)
            if not url or url.rstrip("/") in listings:
                continue
            candidates = [url]
            primary = url
            reported = parse_date(item.get("publishedAt") or item.get("firstSeenAt") or item.get("discoveredAt"))
            kind = "existing-candidate-date"
        else:
            if item.get("category") not in LOCAL_RELEASE_CATEGORIES:
                continue
            links = item.get("links") or []
            if isinstance(links, dict):
                candidates = [links.get("original")]
                primary = https_url(links.get("original")) or https_url(links.get("aihot"))
            elif isinstance(links, list):
                candidates = [item.get("url"), *(link.get("url") for link in links if isinstance(link, dict))]
                primary = https_url(item.get("url")) or next((u for link in candidates if (u := https_url(link))), "")
            else:
                continue
            if not primary:
                continue
            reported = parse_date(item.get("publishedAt")) if source_id == "local-aihot-selected" else edition
            kind = "external-report-date" if source_id == "local-aihot-selected" else "briefing-edition-date"
        urls = sorted({u for raw in candidates if (u := article_url(raw, allowed))})
        hints = literal_model_hints(title, families)
        original = clean_text(item.get("originalTitle") or "")
        rows.append({"title": title[:240], "url": primary, "sourceId": source_id, "sourceName": source_name,
                     "reportedAt": reported, "dateKind": kind, "officialArticleUrls": urls[:5],
                     "titleHints": sorted(set(hints + ([original[:240]] if original else []))),
                     "observedAt": stamp, "verificationStatus": "unverified-lead",
                     "attribution": {"name": source_name, "url": snapshot.get("sourceUrl") or primary}})
    return rows, stamp


def merge_local_inputs(result, snapshots, allowed, families, model_sources, now):
    cutoff = (now - timedelta(days=45)).date().isoformat()
    today = now.date().isoformat()
    items = {r["id"]: r for r in result["items"]}
    states = []
    for source_id, name, filename, field in LOCAL_INPUTS:
        snap = snapshots.get(filename)
        try:
            if not isinstance(snap, dict):
                raise ValueError("Snapshot missing or invalid")
            rows, stamp = local_snapshot_leads(source_id, name, snap, field, allowed, families, model_sources)
            if stamp[:10] > today or stamp[:10] < cutoff:
                raise ValueError("Snapshot observation outside retention window")
            accepted = 0
            for row in rows:
                day = str(row.get("reportedAt") or stamp)[:10]
                if not cutoff <= day <= today:
                    continue
                rid = hashlib.sha256((source_id + "|" + row["url"] + "|" + row["title"]).encode()).hexdigest()[:20]
                old = items.get(rid, {})
                # Reading the same local file does not refresh its observation time.
                items[rid] = {"id": rid, **row, "firstSeenAt": old.get("firstSeenAt", stamp),
                              "lastSeenAt": max(old.get("lastSeenAt", stamp), stamp)}
                accepted += 1
            states.append({"id": source_id, "name": name, "snapshot": filename, "observedAt": stamp,
                           "itemCount": accepted, "error": None})
        except (ValueError, TypeError, AttributeError) as exc:
            states.append({"id": source_id, "name": name, "snapshot": filename, "itemCount": 0, "error": str(exc)})
    # Reserve capacity for article-backed candidates, rather than filling the
    # limited queue with unrelated repository uploads and news mentions.
    ordered = sorted(items.values(), key=lambda row: (row.get("reportedAt") or row.get("firstSeenAt") or "", row["id"]), reverse=True)
    bounded = sorted(ordered, key=lambda row: bool(row.get("officialArticleUrls")), reverse=True)[:500]
    result["items"] = sorted(bounded, key=lambda row: (row.get("reportedAt") or row.get("firstSeenAt") or "", row["id"]), reverse=True)
    result["localSources"] = states
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    old = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    now = datetime.now(timezone.utc)
    result = collect(config, old, now)
    snapshots = {}
    for _, _, name, _ in LOCAL_INPUTS:
        try:
            snapshots[name] = json.loads((ROOT / "site/data" / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    families = json.loads((ROOT / "site/data/models.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "config/model-sources.json").read_text(encoding="utf-8"))
    result = merge_local_inputs(result, snapshots, config["officialArticleHosts"], families, sources, now)
    print("Cross-platform discovery:", json.dumps({"reachable": sum(s["error"] is None for s in result["sources"]),
          "sources": len(result["sources"]), "retainedLeads": len(result["items"]),
          "officialArticleLeads": sum(bool(r["officialArticleUrls"]) for r in result["items"])}, ensure_ascii=False))
    for s in result["sources"]:
        print("[DISCOVERY]", s["id"], "items=", s["itemCount"], "error=", s["error"])
    for s in result.get("localSources", []):
        print("[LOCAL-DISCOVERY]", s["id"], "items=", s["itemCount"], "observed=", s.get("observedAt"), "error=", s["error"])
    if args.report:
        write_json(args.report, result)
    if not args.dry_run:
        write_json(OUTPUT, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
