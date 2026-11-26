#!/usr/bin/env python3
"""Collect official model-release updates without LLM APIs or third-party packages."""
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
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config" / "model-sources.json"
MODELS_FILE = ROOT / "site" / "data" / "models.json"
UPDATES_FILE = ROOT / "site" / "data" / "model-updates.json"
STATUS_FILE = ROOT / "site" / "data" / "model-monitor-status.json"
STATE_FILE = ROOT / "site" / "data" / "model-monitor-state.json"
MAX_BYTES = 6 * 1024 * 1024
MAX_ITEMS_PER_SOURCE = 80
RETENTION_DAYS = 730
USER_AGENT = "AI-Creator-Radar/2.0 (+https://github.com/Ai-luren/AI-Creator-Radar)"

RELEASE_TERMS = (
    "release", "released", "introducing", "announcing", "announced",
    "launch", "launched", "now available", "officially available", "open-sourced", "open sourced", "开源",
    "正式发布", "正式上线", "发布", "上线", "推出", "新模型", "模型发布",
)
PRE_RELEASE_TERMS = (
    "coming soon", "available soon", "waitlist", "pre-register",
    "join the waitlist", "即将开放", "即将上线", "即将发布", "发布预告",
    "开放预约", "开启预约", "预约体验", "候补名单", "内测招募",
)
VERSION_RE = re.compile(r"(?<![a-z])v?\d+(?:\.\d+){1,3}(?!\d)", re.I)


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def normalize_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid", "ref"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                       parts.path or "/", urlencode(query), ""))


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    raw = html.unescape(str(value)).strip()
    iso = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except ValueError:
        pass

    chinese = re.search(r"(20\d{2})[年./-]\s*(\d{1,2})[月./-]\s*(\d{1,2})日?", raw)
    if chinese:
        year, month, day = map(int, chinese.groups())
        try:
            return datetime(year, month, day, tzinfo=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        except ValueError:
            return None

    for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
                "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%m/%d/%Y"):
        try:
            parsed = datetime.strptime(raw[:40], fmt).replace(tzinfo=timezone.utc)
            return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")
        except ValueError:
            continue
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError):
        return None


def find_date(value: str | None) -> str | None:
    if not value:
        return None
    raw = str(value)
    candidates = [
        r"20\d{2}[年./-]\s*\d{1,2}[月./-]\s*\d{1,2}日?",
        r"\d{1,2}/\d{1,2}/20\d{2}",
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+20\d{2}",
        r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+20\d{2}",
    ]
    direct = parse_date(raw)
    if direct:
        return direct
    for pattern in candidates:
        match = re.search(pattern, raw, flags=re.I)
        if match:
            parsed = parse_date(match.group(0))
            if parsed:
                return parsed
    return None


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(rendered)
        temp_path = Path(tmp.name)
    temp_path.replace(path)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(element: ET.Element, names: set[str]) -> str:
    for child in list(element):
        if local_name(child.tag) in names:
            value = " ".join(part.strip() for part in child.itertext() if part.strip())
            if value:
                return value
    return ""


def entry_link(element: ET.Element) -> str:
    for child in list(element):
        if local_name(child.tag) == "link":
            href = child.attrib.get("href")
            if href and child.attrib.get("rel", "alternate") in {"alternate", ""}:
                return href.strip()
            if child.text and child.text.strip():
                return child.text.strip()
    return child_text(element, {"guid", "id"})


class BlockParser(HTMLParser):
    """Extract headings, links, dates and paragraphs from server-rendered pages."""
    CAPTURE = {"h1", "h2", "h3", "h4", "h5", "h6", "a", "time", "p", "li", "tr", "td", "th"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = []
        self.blocks = []
        self.sequence = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.CAPTURE:
            self.active.append({
                "tag": tag, "attrs": dict(attrs), "text": [], "sequence": self.sequence
            })
            self.sequence += 1
        elif tag == "br":
            for block in self.active:
                block["text"].append(" ")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        for block in self.active:
            block["text"].append(data)

    def handle_endtag(self, tag):
        for index in range(len(self.active) - 1, -1, -1):
            if self.active[index]["tag"] == tag:
                block = self.active.pop(index)
                block["text"] = re.sub(r"\s+", " ", "".join(block["text"])).strip()
                block["endSequence"] = self.sequence
                if block["text"] or block["attrs"].get("datetime"):
                    self.blocks.append(block)
                break

    def close(self):
        super().close()
        for block in self.active:
            block["text"] = re.sub(r"\s+", " ", "".join(block["text"])).strip()
            block["endSequence"] = self.sequence
            if block["text"] or block["attrs"].get("datetime"):
                self.blocks.append(block)
        self.active = []


def walk_jsonld(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_jsonld(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_jsonld(child)


def jsonld_items(page: str, source: dict) -> list[dict]:
    results = []
    scripts = re.findall(
        r"<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        page, flags=re.I | re.S
    )
    for raw in scripts:
        try:
            payload = json.loads(html.unescape(raw.strip()))
        except json.JSONDecodeError:
            continue
        for obj in walk_jsonld(payload):
            title = clean_text(str(obj.get("headline") or obj.get("name") or ""))
            if not title:
                continue
            description = clean_text(str(obj.get("description") or ""))
            model_id = match_model(title, source) or match_model(title + " " + description, source)
            published = find_date(obj.get("datePublished") or obj.get("dateCreated"))
            if not model_id or not is_release_candidate(title, published):
                continue
            results.append({
                "title": title,
                "summary": description,
                "url": valid_article_url(obj.get("url") or obj.get("mainEntityOfPage"), source["url"]) or source["url"],
                "publishedAt": published,
            })
    return results


def match_model(text: str, source: dict) -> str | None:
    haystack = text.casefold()
    for model_id, terms in source.get("modelMatches", {}).items():
        for term in terms:
            if term.startswith("re:"):
                if re.search(term[3:], text, flags=re.I):
                    return model_id
            elif term.casefold() in haystack:
                return model_id
    return None


def is_release_candidate(title: str, published_at: str | None, allow_version_only: bool = False) -> bool:
    lowered = title.casefold()
    if any(term in lowered for term in PRE_RELEASE_TERMS):
        return True
    has_release_word = any(term in lowered for term in RELEASE_TERMS)
    has_version = bool(VERSION_RE.search(title))
    # A bare model heading is not an announcement; model-card tables have their own parser.
    return has_release_word or (has_version and published_at is not None and
                                (allow_version_only or len(title.split()) >= 3))



def find_date_near_title(page: str, title: str) -> str | None:
    patterns = (
        r"20\d{2}[年./-]\s*\d{1,2}[月./-]\s*\d{1,2}日?",
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+20\d{2}",
        r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+20\d{2}",
    )
    for match in re.finditer(re.escape(title), page, flags=re.I):
        start = max(0, match.start() - 700)
        end = min(len(page), match.end() + 700)
        window = page[start:end]
        found = []
        for pattern in patterns:
            for date_match in re.finditer(pattern, window, flags=re.I):
                parsed = find_date(date_match.group(0))
                if parsed:
                    absolute_position = start + date_match.start()
                    found.append((abs(absolute_position - match.start()), parsed))
        if found:
            return min(found, key=lambda item: item[0])[1]
    return None
def valid_article_url(value: str, base_url: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    resolved = urljoin(base_url, html.unescape(value))
    parts = urlsplit(resolved)
    if parts.scheme != "https" or not parts.netloc or parts.path.lower().endswith(
        (".svg", ".png", ".jpg", ".jpeg", ".webp", ".css", ".js", ".ico", ".woff", ".woff2")
    ):
        return ""
    return resolved


def find_related_url(page: str, title: str, base_url: str) -> str:
    # Do not pick nearby arbitrary hrefs (often navigation, icons, or a different article).
    # An enclosing anchor or a matching nested anchor is handled by html_page_items.
    return base_url


def dedupe_candidates(candidates: list[dict]) -> list[dict]:
    deduped = {}
    for item in candidates:
        key = item["title"].casefold() + "|" + (item.get("publishedAt") or "")
        old = deduped.get(key)
        if old is None:
            deduped[key] = item
            continue
        old_path = urlsplit(old.get("url") or "").path
        new_path = urlsplit(item.get("url") or "").path
        if len(new_path) > len(old_path):
            deduped[key] = item
    return list(deduped.values())[:MAX_ITEMS_PER_SOURCE]


def model_card_items(blocks: list[dict], source: dict) -> list[dict]:
    results = []
    rows = [block for block in blocks if block["tag"] == "tr"]
    for row in rows:
        if len(row.get("text", "")) > int(source.get("maxRowLength", 260)):
            continue
        nested = [
            block for block in blocks
            if row["sequence"] < block["sequence"] < row.get("endSequence", row["sequence"] + 1)
            and block["tag"] in {"td", "th", "a", "time"}
        ]
        row_text = row["text"]
        published_at = find_date(row_text)
        if not published_at:
            for block in nested:
                published_at = find_date(block.get("attrs", {}).get("datetime")) or find_date(block["text"])
                if published_at:
                    break
        model_id = match_model(row_text, source)
        if not model_id or not published_at:
            continue
        matching_titles = [
            block["text"] for block in nested
            if block["tag"] in {"td", "th", "a"} and match_model(block["text"], source)
        ]
        title = min(matching_titles, key=len) if matching_titles else ""
        title = title or row_text
        article_url = source["url"]
        for block in nested:
            if block["tag"] == "a" and block["attrs"].get("href"):
                article_url = urljoin(source["url"], block["attrs"]["href"])
                break
        results.append({
            "title": clean_text(title)[:220],
            "summary": clean_text(row_text)[:520] or "官方模型资料页记录的更新。",
            "url": article_url,
            "publishedAt": published_at,
            "modelId": model_id,
        })
    return dedupe_candidates(results)


def dated_heading_items(blocks: list[dict], source: dict) -> list[dict]:
    """Read explicit date section headings, never infer dates from neighboring articles."""
    results = []
    current_date = None
    for block in blocks:
        if block["tag"] not in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            continue
        title = clean_text(block["text"])
        if re.fullmatch(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", title):
            current_date = parse_date(title)
            continue
        if re.fullmatch(r"20\d{2}", title):
            current_date = None
            continue
        model_id = match_model(title, source)
        if not current_date or not model_id or len(title) > 220:
            continue
        results.append({"title": title, "summary": "官方模型可用性目录条目；具体发布阶段待复核。",
                        "url": source["url"], "publishedAt": current_date, "modelId": model_id})
    return dedupe_candidates(results)


def source_coverage(sources: list, models: dict) -> dict:
    configured = {key for source in sources if source.get("active")
                  for key in source.get("modelMatches", {})}
    return {
        "catalogFamilies": len(models),
        "configuredFamilies": len(configured & set(models)),
        "unmappedFamilyIds": sorted(configured - set(models)),
        "unmonitoredFamilyIds": sorted(set(models) - configured),
    }


def html_page_items(page: str, source: dict) -> list[dict]:
    parser = BlockParser()
    parser.feed(page)
    parser.close()
    blocks = sorted(parser.blocks, key=lambda block: block["sequence"])

    if source.get("type") == "dated-headings":
        return dated_heading_items(blocks, source)
    if source.get("type") == "model-cards":
        cards = model_card_items(blocks, source)
        if cards or not source.get("fallbackHeadings"):
            return cards

    headings = [i for i, block in enumerate(blocks) if block["tag"] in {"h1", "h2", "h3", "h4", "h5", "h6"}]
    candidates = []

    for heading_position, block_index in enumerate(headings):
        heading = blocks[block_index]
        title = clean_text(heading["text"])
        if not title or len(title) > 220:
            continue
        next_heading = headings[heading_position + 1] if heading_position + 1 < len(headings) else len(blocks)
        nearby = blocks[block_index + 1:min(next_heading, block_index + 14)]
        summary_parts = []
        published_at = find_date(heading["attrs"].get("datetime"))
        article_url = ""
        enclosing = [
            block for block in blocks
            if block["tag"] == "a" and block["sequence"] < heading["sequence"]
            < block.get("endSequence", block["sequence"] + 1)
        ]
        for anchor in reversed(enclosing):
            article_url = valid_article_url(anchor["attrs"].get("href", ""), source["url"])
            if article_url:
                break
        for candidate in nearby:
            attrs = candidate["attrs"]
            if candidate["tag"] == "time":
                published_at = published_at or find_date(attrs.get("datetime") or candidate["text"])
            elif candidate["tag"] in {"p", "li"}:
                published_at = published_at or find_date(candidate["text"])
                if candidate["text"] and not find_date(candidate["text"]) and len(summary_parts) < 2:
                    summary_parts.append(candidate["text"])
            elif candidate["tag"] == "a":
                href = attrs.get("href", "")
                anchor_text = clean_text(candidate["text"])
                if href and anchor_text and (
                    title.casefold() in anchor_text.casefold()
                    or anchor_text.casefold() in title.casefold()
                ):
                    if not article_url:
                        article_url = valid_article_url(href, source["url"])
        combined = title + " " + " ".join(summary_parts)
        model_id = match_model(title, source) or match_model(combined, source)
        published_at = published_at or find_date_near_title(page, title)
        if not article_url:
            # Accept a direct "Learn more" link only in this heading's own section.
            for candidate in nearby:
                if candidate["tag"] == "a" and candidate["text"].strip().casefold() in {"learn more", "read more", "了解更多", "阅读更多", "查看详情"}:
                    article_url = valid_article_url(candidate["attrs"].get("href", ""), source["url"])
                    if article_url:
                        break
        article_url = article_url or source["url"]
        if model_id and (is_release_candidate(title, published_at) or (source.get("allowNamedVersion") and published_at and re.search(r"^\s*(?:version|v|niji)\s*v?\d+(?:\.\d+)*\b", title, re.I))):
            candidates.append({
                "title": title,
                "summary": " ".join(summary_parts),
                "url": article_url,
                "publishedAt": published_at,
                "modelId": model_id,
            })

    # Only fall back to standalone links when the page has no usable headings.
    if not candidates:
        for index, block in enumerate(blocks):
            if block["tag"] != "a" or not block["attrs"].get("href"):
                continue
            title = clean_text(block["text"])
            if not title or len(title) > 220:
                continue
            model_id = match_model(title, source)
            if not model_id:
                continue
            nearby = blocks[index + 1:index + 6]
            published_at = next(
                (find_date(item.get("attrs", {}).get("datetime")) or find_date(item["text"])
                 for item in nearby if find_date(item.get("attrs", {}).get("datetime")) or find_date(item["text"])),
                None,
            )
            article_url = valid_article_url(block["attrs"]["href"], source["url"])
            if article_url and (is_release_candidate(title, published_at) or (source.get("allowNamedVersion") and published_at and re.search(r"^\s*(?:version|v|niji)\s*v?\d+(?:\.\d+)*\b", title, re.I))):
                candidates.append({
                    "title": title, "summary": "", "url": article_url,
                    "publishedAt": published_at, "modelId": model_id,
                })

    candidates.extend(jsonld_items(page, source))
    return dedupe_candidates(candidates)


def rss_items(body: bytes, source: dict) -> list[dict]:
    root = ET.fromstring(body)
    entries = [node for node in root.iter() if local_name(node.tag) in {"item", "entry"}]
    results = []
    for entry in entries[:MAX_ITEMS_PER_SOURCE]:
        title = clean_text(child_text(entry, {"title"}))
        if not title:
            continue
        summary = clean_text(child_text(entry, {"description", "summary", "content", "encoded"}))
        model_id = match_model(title, source) or match_model(title + " " + summary, source)
        published = parse_date(child_text(entry, {"pubdate", "published", "date", "created"})) or parse_date(child_text(entry, {"updated"}))
        if not model_id or not is_release_candidate(title, published, source.get("allowVersionOnly", False)):
            continue
        results.append({
            "title": title, "summary": summary, "url": entry_link(entry),
            "publishedAt": published, "modelId": model_id,
        })
    return results


def markdown_news_items(page: str, source: dict) -> list[dict]:
    """Read dated announcement bullets from a named section in an official Markdown page."""
    section_name = re.escape(source.get("section", "News"))
    section = re.search(rf"^#+\s+{section_name}\s*$([\s\S]*?)(?=^#{{1,6}}\s|\Z)", page, flags=re.I | re.M)
    if not section:
        return []
    results = []
    for line in section.group(1).splitlines():
        bullet = re.match(r"^\s*[-*+]\s+(.+)$", line)
        if not bullet:
            continue
        raw = bullet.group(1).strip()
        links = re.findall(r"\[([^\]]+)\]\((https?://[^)]+)\)", raw)
        plain = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", raw)
        plain = plain.replace("**", "").replace("`", "")
        title = clean_text(plain)
        published = find_date(title)
        model_id = match_model(title, source)
        if not model_id or not published or not is_release_candidate(title, published, True):
            continue
        summary = re.sub(r"^20\d{2}[年./-]\s*\d{1,2}[月./-]\s*\d{1,2}日?\s*[:：-]?\s*", "", title)
        results.append({
            "title": title[:220], "summary": summary[:520],
            "url": links[0][1] if links else source["url"],
            "publishedAt": published, "modelId": model_id,
        })
    return dedupe_candidates(results)


def make_item(raw: dict, source: dict, models: dict, now_iso: str) -> dict:
    model_id = raw.get("modelId") or match_model(raw["title"] + " " + raw.get("summary", ""), source)
    model = models.get(model_id, {})
    url = normalize_url(urljoin(source["url"], raw.get("url") or source["url"]))
    identity = url if url != normalize_url(source["url"]) else source["id"] + "|" + raw["title"].casefold()
    # Shared announcements can contain different model families. Preserve each family.
    if model_id:
        identity += "|" + model_id
    stable_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:18]
    version = None
    version_pattern = source.get("versionPatterns", {}).get(model_id)
    if version_pattern:
        version_match = re.search(version_pattern, raw["title"] + " " + raw.get("summary", ""), flags=re.I)
        if version_match:
            version = clean_text(version_match.group(1))
    update_type = source.get("updateType", "release")
    title_lower = raw["title"].casefold()
    if update_type in {"release", "model-release", "model-card"} and any(term in title_lower for term in PRE_RELEASE_TERMS):
        update_type = "announcement"
    return {
        "id": stable_id,
        "modelId": model_id,
        "modelName": model.get("name") or source.get("vendor") or source["name"],
        "vendor": model.get("vendor") or source.get("vendor") or source["name"],
        "category": model.get("category") or source.get("category") or "video",
        "title": clean_text(raw["title"]),
        "summary": clean_text(raw.get("summary", ""))[:520],
        "url": url,
        "publishedAt": raw.get("publishedAt"),
        "discoveredAt": now_iso,
        "firstSeenAt": now_iso,
        "lastSeenAt": now_iso,
        "sourceId": source["id"],
        "sourceName": source["name"],
        "official": bool(source.get("official", True)),
        "updateType": update_type,
        "modelVersion": version,
    }


def update_identity(item: dict) -> tuple:
    url = normalize_url(item.get("url") or "")
    title = " ".join(str(item.get("title") or "").casefold().split())
    published = str(item.get("publishedAt") or "")[:10]
    return (item.get("modelId"), url, title, published)


def merge_item(old: dict, new: dict) -> dict:
    merged = dict(old)
    last_seen = new.get("lastSeenAt") or new.get("discoveredAt") or old.get("lastSeenAt") or old.get("discoveredAt")
    discovered = [value for value in (old.get("discoveredAt"), new.get("discoveredAt")) if value]
    if last_seen:
        merged["lastSeenAt"] = last_seen
    if discovered:
        merged["discoveredAt"] = min(discovered)
    first_seen = [value for value in (old.get("firstSeenAt"), new.get("firstSeenAt"), *discovered) if value]
    if first_seen:
        merged["firstSeenAt"] = min(first_seen)
    if not merged.get("publishedAt") and new.get("publishedAt"):
        merged["publishedAt"] = new["publishedAt"]
    if len(new.get("summary", "")) > len(old.get("summary", "")):
        merged["summary"] = new["summary"]
    if new.get("modelVersion"):
        merged["modelVersion"] = new["modelVersion"]
    existing_sources = old.get("sourceNames")
    if not isinstance(existing_sources, list):
        existing_sources = [old.get("sourceName", "")]
    sources = list(dict.fromkeys(existing_sources + [new.get("sourceName", "")]))
    merged["sourceNames"] = [value for value in sources if value]
    return merged


def apply_recent_model_versions(models: dict, items: list[dict], now: datetime) -> list[str]:
    """Apply only explicitly configured, dated version announcements from the last 4 days."""
    cutoff = now - timedelta(days=4)
    changed = []
    dated = sorted(items, key=lambda item: item.get("publishedAt") or "")
    for item in dated:
        if item.get("official") is False or item.get("updateType") in {"product-release", "announcement", "model-card"}:
            continue
        model_id = item.get("modelId")
        model = models.get(model_id)
        if not model and model_id:
            # Family consolidation keeps old collector IDs on versions so existing
            # source configuration continues to update the right family.
            model = next((candidate for candidate in models.values()
                          if model_id in candidate.get("legacyIds", [])), None)
        version = item.get("modelVersion")
        published = find_date(item.get("publishedAt"))
        if not model or not version or not published:
            continue
        published_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if published_dt < cutoff or published_dt > now:
            continue
        previous_dt = find_date(model.get("versionUpdatedAt"))
        if previous_dt and published_dt < datetime.fromisoformat(previous_dt.replace("Z", "+00:00")):
            continue
        structured = model.setdefault("versions", [])
        current = next((entry for entry in structured
                        if entry.get("name") == version or entry.get("id") == re.sub(r"[^a-z0-9]+", "-", version.lower()).strip("-")), None)
        if current and (current.get("releaseEvidence") or current.get("releaseDate")):
            # Never overwrite an existing publication date or reviewed evidence.
            # Conflicting source announcements remain visible in the discovery stream.
            continue
        if not current:
            version_id = re.sub(r"[^a-z0-9]+", "-", version.lower()).strip("-")
            current = {"id": version_id, "name": version, "legacyIds": [],
                       "leaderboardAliases": [], "status": "官方发布"}
            structured.append(current)
        current["releaseDate"] = published
        current["releaseUrl"] = item.get("url")
        current["status"] = "官方来源自动收录 · 待复核"
        if model_id and model_id not in current.setdefault("legacyIds", []):
            current["legacyIds"].append(model_id)
        model["version"] = " / ".join(dict.fromkeys(
            entry.get("name", "") for entry in structured if entry.get("name")))
        model["versionUpdatedAt"] = published
        model["versionSourceUrl"] = item.get("url")
        changed.append(f"{model_id} → {version}")
    return changed


def fetch_source(source: dict) -> tuple[dict, list[dict], str | None]:
    request = urllib.request.Request(source["url"], headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
    })
    try:
        with urllib.request.urlopen(request, timeout=24) as response:
            body = response.read(MAX_BYTES + 1)
            content_type = response.headers.get("Content-Type", "")
        if len(body) > MAX_BYTES:
            raise ValueError("Source exceeds 6 MB safety limit")
        source_type = source.get("type", "html").lower()
        if source_type == "rss":
            items = rss_items(body, source)
        else:
            charset = "utf-8"
            match = re.search(r"charset=([\w-]+)", content_type, flags=re.I)
            if match:
                charset = match.group(1)
            try:
                page = body.decode(charset, errors="replace")
            except LookupError:
                page = body.decode("utf-8", errors="replace")
            required_text = source.get("requiredText")
            if required_text and not re.search(required_text, page, flags=re.I):
                raise ValueError("Expected model text is absent; the official page may be client-rendered or changed")
            items = markdown_news_items(page, source) if source_type == "markdown-news" else html_page_items(page, source)
        return source, items, None
    except Exception as exc:
        return source, [], f"{type(exc).__name__}: {str(exc)[:220]}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect official model version announcements.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report without writing JSON.")
    parser.add_argument("--source", help="Only check a source by ID.")
    parser.add_argument("--report", type=Path, help="Write a local JSON diagnostic report; requires --dry-run.")
    args = parser.parse_args()
    if args.report and not args.dry_run:
        parser.error("--report requires --dry-run")

    sources = load_json(CONFIG_FILE, [])
    active = [source for source in sources if source.get("active") and source.get("url")]
    if args.source:
        active = [source for source in active if source.get("id") == args.source]
        if not active:
            parser.error(f"Unknown or inactive source: {args.source}")

    models_list = load_json(MODELS_FILE, [])
    models = {model["id"]: model for model in models_list if model.get("id")}
    previous_updates = load_json(UPDATES_FILE, {"items": []})
    previous_status = load_json(STATUS_FILE, {"sources": []})
    old_status = {entry.get("id"): entry for entry in previous_status.get("sources", [])}
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat(timespec="seconds").replace("+00:00", "Z")

    fetched = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(active)))) as pool:
        futures = [pool.submit(fetch_source, source) for source in active]
        for future in concurrent.futures.as_completed(futures):
            fetched.append(future.result())

    by_id = {}
    for item in previous_updates.get("items", []):
        if item.get("id"):
            by_id[item["id"]] = item
    existing_keys = {update_identity(item): key for key, item in by_id.items()}
    status_entries = []
    success_count = 0
    new_count = 0
    new_recent = 0
    new_undated = 0
    new_historical = 0
    new_future = 0

    for source, raw_items, error in sorted(fetched, key=lambda value: value[0]["name"]):
        old = old_status.get(source["id"], {})
        if error is None:
            success_count += 1
            incoming = [make_item(item, source, models, now_iso) for item in raw_items]
            for item in incoming:
                key = update_identity(item)
                item_id = existing_keys.get(key) or item["id"]
                if item_id in by_id and update_identity(by_id[item_id])[:3] != key[:3]:
                    # A single URL can be a rolling page; do not merge unrelated entries.
                    item_id = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:18]
                if item_id in by_id:
                    by_id[item_id] = merge_item(by_id[item_id], item)
                else:
                    item["id"] = item_id
                    by_id[item_id] = item
                    new_count += 1
                    published = parse_date(item.get("publishedAt"))
                    if not published:
                        new_undated += 1
                    else:
                        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                        if dt.date() > now.date():
                            new_future += 1
                        elif dt.date() >= (now - timedelta(days=29)).date():
                            new_recent += 1
                        else:
                            new_historical += 1
                existing_keys[key] = item_id
            status_entries.append({
                "id": source["id"], "name": source["name"], "type": source.get("type", "html"),
                "url": source["url"], "active": True, "official": bool(source.get("official", True)),
                "checkedAt": now_iso, "lastSuccessAt": now_iso, "itemCount": len(incoming),
                "latestItemAt": max((item.get("publishedAt") or "" for item in incoming), default="") or None,
                "resultStatus": "matched" if incoming else "zero-match",
                "lastMatchAt": now_iso if incoming else old.get("lastMatchAt") or (old.get("lastSuccessAt") if old.get("itemCount") else None),
                "error": None,
            })
        else:
            status_entries.append({
                "id": source["id"], "name": source["name"], "type": source.get("type", "html"),
                "url": source["url"], "active": True, "official": bool(source.get("official", True)),
                "checkedAt": now_iso, "lastSuccessAt": old.get("lastSuccessAt"),
                "itemCount": old.get("itemCount", 0), "latestItemAt": old.get("latestItemAt"),
                "resultStatus": "failed",
                "lastMatchAt": old.get("lastMatchAt") or (old.get("lastSuccessAt") if old.get("itemCount") else None),
                "error": error,
            })

    cutoff = now - timedelta(days=RETENTION_DAYS)
    retained = []
    for item in by_id.values():
        published = find_date(item.get("publishedAt")) or find_date(item.get("discoveredAt"))
        if published and datetime.fromisoformat(published.replace("Z", "+00:00")) < cutoff:
            continue
        retained.append(item)
    retained.sort(key=lambda item: item.get("publishedAt") or item.get("discoveredAt") or "", reverse=True)
    retained = retained[:1000]

    recent_incoming = [item for source_entry in status_entries
                       for item in by_id.values()
                       if item.get("sourceId") == source_entry["id"] and item.get("lastSeenAt") == now_iso]
    # Automatic discoveries are not reviewed release evidence. Keep the canonical
    # version registry untouched; publish candidates via the pending discovery stream.
    version_changes = []
    status = {
        "zeroMatchSources": sum(e.get("resultStatus") == "zero-match" for e in status_entries),
        "coverage": source_coverage(sources, models),
        "checkedAt": now_iso, "totalSources": len(active), "successSources": success_count,
        "failedSources": len(active) - success_count, "newUpdates": new_count,
        "newRecentDated": new_recent, "newUndated": new_undated, "newHistorical": new_historical, "newFutureDated": new_future,
        "sources": status_entries,
    }
    updates = {"generatedAt": now_iso, "items": retained}
    print(f"Model monitor: {success_count}/{len(active)} official sources OK; "
          f"{new_count} new items; {len(retained)} retained.")
    print(f"New candidates by source date: recent={new_recent}, undated={new_undated}, historical={new_historical}, future={new_future}.")
    coverage = status["coverage"]
    print(f"Source coverage: {coverage['configuredFamilies']}/{coverage['catalogFamilies']} canonical families; {len(coverage['unmappedFamilyIds'])} unmapped IDs.")
    if version_changes:
        print("Model versions updated from recent official sources: " + ", ".join(version_changes))
    for entry in status_entries:
        label = "WARN" if entry["error"] or entry.get("resultStatus") == "zero-match" else "OK"
        print(f"[{label}] {entry['name']}: {entry['itemCount']} matched updates"
              + (f" — {entry['error']}" if entry["error"] else " — no matching items; parser and source need review" if entry.get("resultStatus") == "zero-match" else ""))

    if args.source and not args.dry_run:
        parser.error("--source requires --dry-run; partial writes would replace full monitor status")
    if args.report:
        write_json(args.report, {"status": status, "items": retained})
    if not args.dry_run:
        write_json(UPDATES_FILE, updates)
        write_json(STATUS_FILE, status)
        write_json(STATE_FILE, {"checkedAt": now_iso, "sourceIds": [s["id"] for s in active]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
