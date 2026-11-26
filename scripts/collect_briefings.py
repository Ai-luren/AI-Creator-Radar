#!/usr/bin/env python3
"""Collect structured, compact daily digests from AIHOT and Juya public pages."""
from __future__ import annotations

import argparse
import json
import re
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = {
    "aihot": ROOT / "site" / "data" / "aihot-daily.json",
    "juya": ROOT / "site" / "data" / "juya-daily.json",
}
AIHOT_URL = "https://aihot.news/daily"
JUYA_ARCHIVE_URL = "https://daily.juya.uk/archive/"
JUYA_RSS_URL = "https://daily.juya.uk/rss.xml"
USER_AGENT = "AI-Creator-Radar/1.0 (+https://github.com/Ai-luren/AI-Creator-Radar)"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class Node:
    def __init__(self, tag: str, attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children: list[Node | str] = []

    def text(self) -> str:
        parts = [child if isinstance(child, str) else child.text() for child in self.children]
        return re.sub(r"\s+", " ", " ".join(part for part in parts if part.strip())).strip()

    def find_all(self, tag: str):
        for child in self.children:
            if isinstance(child, Node):
                if child.tag == tag:
                    yield child
                yield from child.find_all(tag)

    def direct(self, tag: str):
        return [child for child in self.children if isinstance(child, Node) and child.tag == tag]


class TreeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_html(body: bytes | str) -> Node:
    parser = TreeParser()
    parser.feed(body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body)
    parser.close()
    return parser.root


def request(url: str, accept: str = "text/html,application/xml") -> bytes:
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                body = response.read(5 * 1024 * 1024 + 1)
            break
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    else:
        raise last_error or RuntimeError(f"Could not fetch {url}")
    if len(body) > 5 * 1024 * 1024:
        raise ValueError(f"Page exceeds 5 MB safety limit: {url}")
    return body


def anchors(node: Node, base: str) -> list[dict]:
    result = []
    for anchor in node.find_all("a"):
        href = anchor.attrs.get("href", "").strip()
        if not href:
            continue
        result.append({"label": anchor.text()[:120], "url": urljoin(base, href)})
    return result


def compact_aihot(body: bytes | str, source_url: str, fetched_at: str) -> dict:
    root = parse_html(body)
    main = next(root.find_all("main"), None)
    if not main:
        raise ValueError("AIHOT daily page has no main element")
    report = next(main.find_all("article"), None)
    if not report:
        raise ValueError("AIHOT daily page has no report article")
    items = []
    # Keep the report's lead story as a distinct item.
    for section in report.direct("section"):
        classes = section.attrs.get("class", "")
        if "grid" in classes and not list(section.find_all("article")):
            title = next((x.text() for x in section.find_all("h2") if x.text()), "")
            paragraphs = [p.text() for p in section.find_all("p") if p.text()]
            if title and paragraphs:
                items.append({"category": "头条", "title": title, "summary": paragraphs[0][:1800], "links": anchors(section, source_url)[:8]})
            break
    for section in report.direct("section"):
        if "grid" in section.attrs.get("class", ""):
            continue
        category = next((x.text() for x in section.find_all("h2") if x.text()), "AI 日报")
        for article in section.find_all("article"):
            title = next((x.text() for x in article.direct("h3") if x.text()), "")
            summary = next((x.text() for x in article.direct("p") if x.text()), "")
            if not title or not summary:
                continue
            links = anchors(article, source_url)
            items.append({
                "category": category,
                "title": title[:300],
                "summary": summary[:1800],
                "sourceName": next((x.text() for x in article.find_all("div") if x.text()), "")[:180],
                "url": next((link["url"] for link in links if link["label"] in {"原文", "查看原文"}), ""),
                "links": links[:8],
            })
    if len(items) < 2:
        raise ValueError(f"AIHOT daily parse returned too few digest items ({len(items)})")
    title = next((h.text() for h in report.find_all("h1") if h.text()), "AIHOT 日报")
    return {"source": "AIHOT 日报", "sourceUrl": source_url, "title": title[:300], "fetchedAt": fetched_at, "items": items}


def find_juya_url() -> str:
    """Read a live official index, never mark a cached old issue freshly discovered."""
    from urllib.parse import urlsplit
    import xml.etree.ElementTree as ET

    def valid_issues(links, base):
        result = []
        for link in links:
            url = urljoin(base, link.strip())
            parsed = urlsplit(url)
            if parsed.scheme == "https" and parsed.netloc == "daily.juya.uk" and re.fullmatch(r"/issues/\d{4}-\d{2}-\d{2}/?", parsed.path):
                result.append(f"https://daily.juya.uk{parsed.path.rstrip('/')}/")
        return result

    errors = []
    try:
        root = parse_html(request(JUYA_ARCHIVE_URL))
        issues = valid_issues((a.attrs.get("href", "") for a in root.find_all("a")), JUYA_ARCHIVE_URL)
        if issues:
            return max(issues)
        errors.append("official archive contains no issue links")
    except (OSError, ValueError) as error:
        errors.append(f"archive: {error}")

    # A fresh RSS response, rather than the repository's previous cached feed,
    # handles an unreachable archive or changed archive markup.
    try:
        rss = ET.fromstring(request(JUYA_RSS_URL, "application/rss+xml,application/xml"))
        links = [child.text.strip() for item in rss.iter()
                 if item.tag.rsplit("}", 1)[-1].lower() == "item"
                 for child in item
                 if child.tag.rsplit("}", 1)[-1].lower() == "link" and child.text]
        issues = valid_issues(links, JUYA_RSS_URL)
        if issues:
            return max(issues)
        errors.append("official RSS contains no issue links")
    except (OSError, ValueError, ET.ParseError) as error:
        errors.append(f"RSS: {error}")
    raise ValueError("Could not confirm the latest Juya issue URL: " + "; ".join(errors))


def compact_juya(body: bytes | str, source_url: str, fetched_at: str) -> dict:
    root = parse_html(body)
    main = next(root.find_all("main"), None)
    if not main:
        raise ValueError("Juya issue page has no main element")
    title = next((x.text() for x in main.find_all("h1") if x.text()), "橘鸦 AI 早报")
    items = []
    category = "今日要闻"
    for child in main.children:
        if not isinstance(child, Node):
            continue
        if child.tag == "h2" and child.text():
            category = child.text()
        if child.tag != "section" or "news-item" not in child.attrs.get("class", ""):
            continue
        headline = next((x.text() for x in child.direct("h3") if x.text()), "")
        if not headline:
            continue
        paragraphs = [x.text() for x in child.find_all("p") if x.text() and not x.text().startswith("相关链接")]
        links = anchors(child, source_url)
        summary = "\n\n".join(paragraphs)[:2400]
        if not summary:
            summary = headline
        items.append({"category": category, "title": re.sub(r"\s+#\d+$", "", headline)[:300], "summary": summary, "url": next((x["url"] for x in links if x["url"] != source_url), ""), "links": links[:8]})
    if len(items) < 2:
        raise ValueError(f"Juya issue parse returned too few digest items ({len(items)})")
    return {"source": "橘鸦 AI 早报", "sourceUrl": source_url, "title": title[:300], "fetchedAt": fetched_at, "items": items}


def write_snapshot(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def collect(which: str, dry_run: bool = False) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    result = {}
    if which in {"all", "aihot"}:
        result["aihot"] = compact_aihot(request(AIHOT_URL), AIHOT_URL, now)
        if not dry_run:
            write_snapshot(OUTPUTS["aihot"], result["aihot"])
    if which in {"all", "juya"}:
        url = find_juya_url()
        result["juya"] = compact_juya(request(url), url, now)
        if not dry_run:
            write_snapshot(OUTPUTS["juya"], result["juya"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch structured AIHOT and Juya daily briefings.")
    parser.add_argument("source", choices=("all", "aihot", "juya"), nargs="?", default="all")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without writing snapshots.")
    args = parser.parse_args()
    result = collect(args.source, args.dry_run)
    for name, data in result.items():
        print(f"{name}: {len(data['items'])} digest items ({data['title']})")
        if not args.dry_run:
            print(f"Wrote {OUTPUTS[name].relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
