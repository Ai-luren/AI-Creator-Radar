#!/usr/bin/env python3
"""Token-free RSS/Atom and GitHub release collector for AI-Creator-Radar."""
from __future__ import annotations

import argparse
import concurrent.futures
import email.utils
import hashlib
import html
import json
import re
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = ROOT / "config" / "sources.json"
DATA_DIR = ROOT / "site" / "data"
NEWS_FILE = DATA_DIR / "news.json"
STATUS_FILE = DATA_DIR / "status.json"
MAX_FEED_BYTES = 5 * 1024 * 1024
MAX_ITEMS_PER_SOURCE = 40
RETENTION_DAYS = 60

MODEL_TERMS = ("gpt", "gemini", "claude", "deepseek", "qwen", "llama", "mistral", "seedance", "kling", "veo", "sora", "wan", "model", "模型", "发布", "推出", "release", "launch", "preview")
HIGH_TERMS = ("launch", "introducing", "announcing", "released", "release", "available now", "推出", "发布", "上线", "正式开放", "新模型", "重大更新", "开源")
MEDIUM_TERMS = ("update", "changelog", "feature", "新增", "更新", "升级", "版本", "beta", "preview", "research")

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        value = data.strip()
        if value:
            self.parts.append(value)

def clean_html(value: str) -> str:
    parser = TextExtractor()
    try:
        parser.feed(html.unescape(value or ""))
        text = " ".join(parser.parts)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()

def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()

def child_text(element: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(element):
        if local_name(child.tag) in names:
            if child.text and child.text.strip():
                return child.text.strip()
            nested = " ".join(part.strip() for part in child.itertext() if part.strip())
            if nested:
                return nested
    return ""

def item_link(element: ET.Element) -> str:
    for child in list(element):
        if local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if href:
            if child.attrib.get("rel", "alternate") in ("alternate", ""):
                return href.strip()
        if child.text and child.text.strip():
            return child.text.strip()
    return child_text(element, ("guid", "id"))

def normalize_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if not key.lower().startswith("utm_") and key.lower() not in ("fbclid", "gclid", "ocid", "ref")]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/", urlencode(query), ""))

def parse_datetime(value: str) -> str | None:
    if not value:
        return None
    parsed = None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def infer_priority(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    if any(term in text for term in HIGH_TERMS):
        return "high"
    if any(term in text for term in MEDIUM_TERMS):
        return "medium"
    return "normal"

def infer_tags(title: str, summary: str, focus: str) -> list[str]:
    text = (title + " " + summary).lower()
    tags = []
    if focus:
        tags.append(focus)
    groups = {
        "模型发布": ("model", "模型", "gpt", "gemini", "claude", "seedance", "kling", "veo", "sora", "wan"),
        "视频生成": ("video", "视频", "text-to-video", "image-to-video", "视频生成"),
        "图像生成": ("image", "图像", "图片", "image generation"),
        "Agent / 工作流": ("agent", "workflow", "canvas", "agentic", "工作流", "智能体"),
        "创作者生态": ("creator", "community", "contest", "competition", "创作者", "赛事", "社区"),
        "商业化": ("pricing", "subscription", "credits", "price", "定价", "积分", "会员"),
        "开源 / 开发者": ("github", "open source", "open-source", "release", "api", "sdk", "开源", "开发者")
    }
    for label, terms in groups.items():
        if any(term in text for term in terms):
            tags.append(label)
    return list(dict.fromkeys(tags))[:6]

def parse_feed(xml_bytes: bytes, source: dict, now: datetime | None = None) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    entries = [node for node in root.iter() if local_name(node.tag) in ("item", "entry")]
    now_iso = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    results = []
    for entry in entries[:MAX_ITEMS_PER_SOURCE]:
        title = clean_html(child_text(entry, ("title",)))
        link = normalize_url(item_link(entry))
        if not title or not link:
            continue
        raw_summary = child_text(entry, ("description", "summary", "content", "encoded"))
        summary = clean_html(raw_summary)
        if len(summary) > 420:
            summary = summary[:417].rstrip() + "..."
        published_raw = child_text(entry, ("pubdate", "published", "updated", "date", "created"))
        published_at = parse_datetime(published_raw) or now_iso
        category = source.get("category", "industry")
        focus = source.get("focus", "")
        results.append({
            "id": hashlib.sha256(link.encode("utf-8")).hexdigest()[:16],
            "title": title,
            "url": link,
            "summary": summary or "来源未提供摘要，打开原文查看详情。",
            "publishedAt": published_at,
            "firstSeenAt": now_iso,
            "lastSeenAt": now_iso,
            "category": category,
            "focus": focus,
            "priority": infer_priority(title, summary),
            "tags": infer_tags(title, summary, focus),
            "sourceIds": [source["id"]],
            "sources": [source["name"]],
            "kind": source.get("kind", "official"),
            "region": source.get("region", "Global")
        })
    return results

def fetch_source(source: dict) -> tuple[dict, list[dict], str | None]:
    request = urllib.request.Request(
        source["url"],
        headers={"User-Agent": "AI-Creator-Radar/1.0 (+https://github.com/Ai-luren/AI-Creator-Radar)", "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8"}
    )
    try:
        with urllib.request.urlopen(request, timeout=22) as response:
            body = response.read(MAX_FEED_BYTES + 1)
        if len(body) > MAX_FEED_BYTES:
            raise ValueError("Feed exceeds 5 MB safety limit")
        items = parse_feed(body, source)
        return source, items, None
    except Exception as exc:
        return source, [], f"{type(exc).__name__}: {str(exc)[:220]}"

def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback

def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp:
        temp.write(rendered)
        temp_path = Path(temp.name)
    temp_path.replace(path)

def merge_item(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    merged["lastSeenAt"] = incoming["lastSeenAt"]
    merged["sourceIds"] = list(dict.fromkeys(existing.get("sourceIds", []) + incoming.get("sourceIds", [])))
    merged["sources"] = list(dict.fromkeys(existing.get("sources", []) + incoming.get("sources", [])))
    merged["tags"] = list(dict.fromkeys(existing.get("tags", []) + incoming.get("tags", [])))[:8]
    if len(incoming.get("summary", "")) > len(existing.get("summary", "")):
        merged["summary"] = incoming["summary"]
    if incoming.get("priority") == "high":
        merged["priority"] = "high"
    return merged

def main() -> int:
    parser = argparse.ArgumentParser(description="Collect public AI news feeds without LLM/API tokens.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report without writing data files.")
    args = parser.parse_args()

    sources = load_json(SOURCES_FILE, [])
    active_sources = [source for source in sources if source.get("active") and source.get("url")]
    previous_news = load_json(NEWS_FILE, {"items": []})
    previous_status = load_json(STATUS_FILE, {"sources": []})
    old_status = {entry.get("id"): entry for entry in previous_status.get("sources", [])}
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat(timespec="seconds").replace("+00:00", "Z")

    fetched = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch_source, source) for source in active_sources]
        for future in concurrent.futures.as_completed(futures):
            fetched.append(future.result())

    by_url = {}
    for item in previous_news.get("items", []):
        key = item.get("url") or item.get("id")
        if key:
            by_url[key] = item

    status_entries = []
    success_count = 0
    for source, items, error in sorted(fetched, key=lambda result: result[0].get("priority", 9)):
        previous = old_status.get(source["id"], {})
        if error is None:
            success_count += 1
            for item in items:
                key = item.get("url") or item["id"]
                by_url[key] = merge_item(by_url[key], item) if key in by_url else item
            status_entries.append({
                "id": source["id"], "name": source["name"], "category": source["category"],
                "kind": source.get("kind", "official"), "url": source["url"], "active": True,
                "checkedAt": now_iso, "lastSuccessAt": now_iso, "itemCount": len(items),
                "latestItemAt": max((item["publishedAt"] for item in items), default=None),
                "error": None
            })
        else:
            status_entries.append({
                "id": source["id"], "name": source["name"], "category": source["category"],
                "kind": source.get("kind", "official"), "url": source["url"], "active": True,
                "checkedAt": now_iso, "lastSuccessAt": previous.get("lastSuccessAt"),
                "itemCount": previous.get("itemCount", 0), "latestItemAt": previous.get("latestItemAt"),
                "error": error
            })

    cutoff = now - timedelta(days=RETENTION_DAYS)
    kept = []
    for item in by_url.values():
        try:
            published = datetime.fromisoformat(item.get("publishedAt", "").replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            if published < cutoff:
                continue
        except (ValueError, TypeError):
            pass
        kept.append(item)
    kept.sort(key=lambda item: item.get("publishedAt", ""), reverse=True)
    kept = kept[:1500]

    news_payload = {
        "generatedAt": now_iso,
        "items": kept,
        "stats": {
            "total": len(kept),
            "sources": len(active_sources),
            "successfulSources": success_count,
            "failedSources": len(active_sources) - success_count
        }
    }
    status_payload = {"checkedAt": now_iso, "sources": status_entries}
    source_payload = {"generatedAt": now_iso, "sources": active_sources}

    print(f"AI-Creator-Radar: {success_count}/{len(active_sources)} sources OK; {len(kept)} retained items.")
    for entry in status_entries:
        label = "OK" if not entry["error"] else "WARN"
        print(f"[{label}] {entry['name']}: {entry['itemCount']} items" + (f" — {entry['error']}" if entry["error"] else ""))

    if not args.dry_run:
        write_json(NEWS_FILE, news_payload)
        write_json(STATUS_FILE, status_payload)
        write_json(DATA_DIR / "sources.json", source_payload)
    return 0

if __name__ == "__main__":
    sys.exit(main())