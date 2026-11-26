#!/usr/bin/env python3
"""Read-only public discovery; never promote candidates or infer eligibility."""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

try:
    from .check_model_resources import write_json
except ImportError:
    from check_model_resources import write_json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site/data"
CONFIG = ROOT / "config/creator-opportunity-sources.json"
OUTPUT = DATA / "creator-opportunity-discovery.json"
MAX_BYTES = 2_000_000
KEYWORDS = re.compile(r"contest|competition|challenge|festival|open.call|call.for.entries|award|征集|大赛|竞赛|挑战赛|电影节", re.I)
OPEN = re.compile(r"\bapply now\b|\bapplications are open\b|\bsubmit application\b|立即申请|开放申请|正在招募", re.I)
CLOSED = re.compile(r"\bapplications (?:are )?closed\b|\bno longer accepting applications\b|\bnot accepting (?:new )?applications\b|暂停招募|申请已截止|报名已结束", re.I)
INVITE = re.compile(r"\binvitation.only\b|\binvite.only\b|仅限邀请|仅受邀", re.I)


def clean(value):
    return " ".join(str(value).split())


def canonical(url):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        return ""
    return urlunsplit(("https", p.netloc.lower(), p.path.rstrip("/") or "/", p.query, ""))


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.words = []
        self.href = None
        self.label = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template", "noscript"}:
            self.hidden += 1
        if self.hidden:
            return
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.label = []

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template", "noscript"}:
            self.hidden = max(0, self.hidden - 1)
        if self.hidden:
            return
        if tag == "a" and self.href:
            self.links.append((self.href, clean(" ".join(self.label))))
            self.href = None
            self.label = []

    def handle_data(self, text):
        if self.hidden:
            return
        self.words.append(text)
        if self.href:
            self.label.append(text)


def read_page(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AI-Creator-Radar/2.0", "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=12) as response:
        if not canonical(response.geturl()):
            raise ValueError("Non-HTTPS final URL")
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Page exceeded bounded read")
        if "html" not in response.headers.get("Content-Type", "").lower():
            raise ValueError("Expected HTML")
        page = Page()
        page.feed(data.decode(response.headers.get_content_charset() or "utf-8", errors="replace"))
        return page, response.geturl()


def candidates(source, page, final_url, known):
    results = {}
    for href, label in page.links:
        url = canonical(urljoin(final_url, href))
        if not url or url in known or urlsplit(url).hostname != urlsplit(final_url).hostname:
            continue
        path = urlsplit(url).path
        if not re.fullmatch(source["pathPattern"], path) or not KEYWORDS.search(label + " " + path.rsplit("/", 1)[-1]):
            continue
        title = label if len(label) >= 8 else path.rsplit("/", 1)[-1].replace("-", " ")
        if not 8 <= len(title) <= 240:
            continue
        ident = hashlib.sha256(url.encode()).hexdigest()[:20]
        results[ident] = {"id": ident, "title": title, "url": url, "sourceUrl": source["url"],
                          "sourceName": source["name"], "provenance": source["provenance"],
                          "review": "pending", "deadlineDate": None}
        if len(results) >= 40:
            break
    return list(results.values())


def program_signal(page):
    visible = clean(" ".join(page.words))
    matches = [(kind, pattern.search(visible)) for kind, pattern in
               [("closure-signal", CLOSED), ("invitation-signal", INVITE), ("application-signal", OPEN)]]
    present = [(kind, match) for kind, match in matches if match]
    if len(present) != 1:
        return {"signal": "ambiguous" if present else "unconfirmed", "excerpt": ""}
    kind, match = present[0]
    return {"signal": kind, "excerpt": visible[max(0, match.start()-40):match.end()+80]}


def scan(config, contests, previous, now, fetch=read_page):
    stamp = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    known = {canonical(x.get(k, "")) for x in contests.get("items", []) for k in ("sourceUrl", "entryUrl", "secondSource")}
    sources = []
    programs = []
    found = {}
    cutoff = (now - timedelta(days=45)).isoformat()
    old = {x["id"]: x for x in previous.get("candidates", [])
           if str(x.get("lastSeenAt", "")) >= cutoff and x.get("url") not in known}

    def check(pair):
        kind, source = pair
        base = {"sourceUrl": source["url"], "checkedAt": stamp}
        if kind == "contest":
            base.update({"id": source["id"], "name": source["name"]})
        else:
            base.update({"platformId": source["platformId"], "scope": source["scope"]})
        try:
            page, final_url = fetch(source["url"])
            base.update({"status": "reachable", "effectiveUrl": final_url})
            if kind == "contest":
                rows = candidates(source, page, final_url, known)
                base["candidateCount"] = len(rows)
                return kind, base, rows
            base.update(program_signal(page))
        except Exception as exc:
            base.update({"status": "failed", "error": str(exc)[:200]})
            if kind == "program":
                base.update({"signal": "unconfirmed", "excerpt": ""})
        return kind, base, []

    tasks = [("contest", x) for x in config["contests"]] + [("program", x) for x in config["programs"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for kind, status, rows in pool.map(check, tasks):
            if kind == "contest":
                sources.append(status)
                for row in rows:
                    prior = old.get(row["id"], {})
                    found[row["id"]] = {**row, "firstSeenAt": prior.get("firstSeenAt", stamp), "lastSeenAt": stamp}
            else:
                programs.append(status)
    for ident, row in old.items():
        found.setdefault(ident, row)
    return {"schemaVersion": 1, "checkedAt": stamp, "sources": sources, "programSignals": programs,
            "candidates": sorted(found.values(), key=lambda x: (x["lastSeenAt"], x["id"]), reverse=True)[:180],
            "method": "Public links and text signals only; no inferred dates, eligibility, or automatic promotion."}


def validate_config(config):
    for x in config["contests"]:
        if not canonical(x["url"]) or x["provenance"] not in {"official", "directory"}:
            raise ValueError("Invalid contest discovery source")
        re.compile(x["pathPattern"])
    for x in config["programs"]:
        if not canonical(x["url"]) or x["scope"] not in {"domestic", "overseas", "global"}:
            raise ValueError("Invalid program monitoring source")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validate configuration without network")
    parser.add_argument("--report", type=Path, help="Write a live diagnostic to a separate file")
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    validate_config(config)
    if args.dry_run:
        print(f"Opportunity sources: {len(config['contests'])} contest indexes; {len(config['programs'])} program pages")
        return 0
    contests = json.loads((DATA / "creator-contests.json").read_text(encoding="utf-8"))
    previous = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    result = scan(config, contests, previous, datetime.now(timezone.utc))
    write_json(args.report or OUTPUT, result)
    print(f"Opportunity scan: {len(result['candidates'])} unreviewed candidates; "
          f"{sum(x['status']=='failed' for x in result['sources']+result['programSignals'])} failed sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
