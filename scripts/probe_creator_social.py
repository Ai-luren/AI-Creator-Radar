#!/usr/bin/env python3
"""Bounded read-only probe of public creator sources. No cookies, proxy, or publication."""
import argparse
import datetime as dt
import json
import re
import urllib.request
import urllib.error
from pathlib import Path
from html.parser import HTMLParser

TARGETS = [
    ("Instagram", "kaye.creatives", "https://www.instagram.com/kaye.creatives/embed/", "creator"),
    ("Instagram", "joeysnoisygroup", "https://www.instagram.com/joeysnoisygroup/embed/", "identity-candidate"),
    ("X", "PixVerse", "https://x.com/PixVerse", "brand-control"),
]
class PublicLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()
        self.title = ""
        self.in_title = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "a" and a.get("href"):
            self.links.add(a["href"])
    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
    def handle_data(self, data):
        if self.in_title:
            self.title += data

def inspect(page, platform, handle):
    parser = PublicLinks()
    parser.feed(page)
    if platform == "Instagram":
        pattern = r"(?:https://(?:www\.)?instagram\.com)?/(?:p|reel)/([A-Za-z0-9_-]+)/?(?:\?.*)?$"
        links = {"https://www.instagram.com/p/" + m.group(1) + "/" for href in parser.links if (m := re.fullmatch(pattern, href))}
    else:
        pattern = r"(?:https://(?:www\.)?x\.com)?/" + re.escape(handle) + r"/status/(\d+)/?(?:\?.*)?$"
        links = {"https://x.com/" + handle + "/status/" + m.group(1) for href in parser.links if (m := re.fullmatch(pattern, href, re.I))}
    status = "candidate-links-only" if links else "no-parseable-post-links"
    if re.search(r"login|log in|sign in|challenge|just a moment|access denied", parser.title, re.I) and not links:
        status = "login-or-access-blocked"
    return {"status": status, "candidateLinks": sorted(links)[:10], "publishedAtVerified": 0,
            "note": "Profile HTML links alone do not verify creator attribution, publication date or post accessibility."}

def probe(platform, handle, url, purpose):
    row = {"platform": platform, "handle": handle, "url": url, "purpose": purpose}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Creator-Radar/0.1 (read-only public source diagnostic)", "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=12) as response:
            html = response.read(2_000_001)
            row.update(httpStatus=response.status, finalUrl=response.url)
        if len(html) > 2_000_000:
            row.update(status="response-too-large", candidateLinks=[], publishedAtVerified=0)
        else:
            row.update(inspect(html.decode("utf-8", "replace"), platform, handle))
    except urllib.error.HTTPError as exc:
        row.update(status="http-error", httpStatus=exc.code, candidateLinks=[], publishedAtVerified=0)
    except (OSError, ValueError) as exc:
        row.update(status="unavailable", error=type(exc).__name__, candidateLinks=[], publishedAtVerified=0)
    return row

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    results = [probe(*target) for target in TARGETS]
    report = {"checkedAt": now.isoformat(), "mode": "diagnostic-only", "results": results,
              "verifiedRecentPosts": 0, "note": "No post is published by this script; blocked or unparsed does not mean no updates."}
    a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
if __name__ == "__main__":
    main()
