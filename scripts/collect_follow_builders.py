#!/usr/bin/env python3
"""Collect the public Follow Builders feeds into a compact V4 snapshot."""
from __future__ import annotations

import argparse
import json
import re
import tempfile
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site" / "data-v4" / "follow-builders.json"
BASE = "https://raw.githubusercontent.com/zarazhangrui/follow-builders/main"
SOURCES = {
    "builders": (f"{BASE}/feed-x.json", "x"),
    "podcasts": (f"{BASE}/feed-podcasts.json", "podcasts"),
    "blogs": (f"{BASE}/feed-blogs.json", "blogs"),
}
USER_AGENT = "AI-Creator-Radar/1.0 (+https://github.com/Ai-luren/AI-Creator-Radar)"
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
# Concise Chinese labels, derived from the public bios bundled by Follow Builders.
# Keep uncertainty explicit where the source bio does not state a current employer.
PROFILE_ZH = {
    "rauchg": "Vercel 首席执行官",
    "amasad": "Replit 首席执行官",
    "thsottiaux": "OpenAI Codex 与 ChatGPT 团队（公开简介未注明具体职位）",
    "danshipper": "Every 首席执行官；AI 内容与订阅产品负责人",
    "zarazhangrui": "产品构建者；哈佛 2017 届（公开简介未注明当前公司）",
    "garrytan": "Y Combinator 总裁兼 CEO；Garry’s List 创始人；GStack、GBrain 创作者",
    "levie": "Box 首席执行官",
    "thenanyu": "OpenAI 产品团队（Codex）；曾任 Linear 产品负责人",
    "trq212": "曾在 Anthropic Claude Code 团队工作；公开简介未注明当前职位",
    "mattturck": "FirstMark Capital 风险投资人；MAD 播客主持人、Data Driven NYC 组织者",
    "petergyang": "AI 教程与访谈创作者；公开简介未注明所属公司",
}


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def compact_feed(source: str, key: str, payload: dict, now: datetime) -> list[dict]:
    """Keep recent public posts and metadata; deliberately omit podcast transcripts."""
    cutoff = now - timedelta(hours=336 if source == "podcasts" else 48 if source == "blogs" else 24)
    entries = payload.get(key, [])
    if not isinstance(entries, list):
        raise ValueError(f"Follow Builders {source} feed is missing {key} list")
    result = []
    if source == "builders":
        for builder in entries:
            if not isinstance(builder, dict):
                continue
            for post in builder.get("tweets", []):
                published = parse_time(post.get("createdAt"))
                if not published or published < cutoff:
                    continue
                result.append({
                    "id": str(post.get("id") or post.get("url") or ""),
                    "name": str(builder.get("name") or builder.get("handle") or "AI Builder"),
                    "handle": str(builder.get("handle") or ""),
                    "bio": str(builder.get("bio") or "")[:240],
                    "text": str(post.get("text") or "")[:600],
                    "publishedAt": published.isoformat(timespec="seconds").replace("+00:00", "Z"),
                    "url": str(post.get("url") or ""),
                    "likes": post.get("likes"),
                    "reposts": post.get("retweets"),
                    "replies": post.get("replies"),
                })
    elif source == "podcasts":
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            published = parse_time(entry.get("publishedAt"))
            if not published or published < cutoff:
                continue
            result.append({
                "name": str(entry.get("name") or "AI 播客"),
                "title": str(entry.get("title") or "未命名节目"),
                "publishedAt": published.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "url": str(entry.get("url") or ""),
            })
    else:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            published = parse_time(entry.get("publishedAt"))
            if not published or published < cutoff:
                continue
            result.append({
                "name": str(entry.get("name") or entry.get("source") or "AI 官方博客"),
                "title": str(entry.get("title") or "未命名文章"),
                "summary": str(entry.get("summary") or entry.get("description") or "")[:600],
                "publishedAt": published.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "url": str(entry.get("url") or ""),
            })
    result.sort(key=lambda x: x.get("publishedAt", ""), reverse=True)
    return result[:60]



def translate_to_chinese(text: str) -> str:
    """Use the public no-key Google Translate endpoint; return empty on service failure."""
    if not text.strip() or re.search(r"[\u3400-\u9fff]", text):
        return ""
    query = urllib.parse.urlencode({"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": text[:600]})
    request = urllib.request.Request(TRANSLATE_URL + "?" + query, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=18) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return "".join(str(part[0]) for part in payload[0] if isinstance(part, list) and part and part[0])[:1200]
    except (OSError, ValueError, IndexError, TypeError):
        return ""


def add_chinese_translations(posts: list[dict], previous: dict | None = None) -> None:
    """Translate new English posts, reusing cached translations for unchanged posts."""
    cache = {str(item.get("id")): item for item in (previous or {}).get("builders", []) if item.get("id")}
    pending = []
    for post in posts:
        old = cache.get(str(post.get("id")))
        if old and old.get("text") == post.get("text") and old.get("textZh"):
            post["textZh"] = old["textZh"]
        elif re.search(r"[\u3400-\u9fff]", post.get("text", "")):
            post["textZh"] = post["text"]
        else:
            pending.append(post)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(translate_to_chinese, post.get("text", "")): post for post in pending}
        for future in as_completed(futures):
            post = futures[future]
            try:
                post["textZh"] = future.result()
            except Exception:
                post["textZh"] = ""

    # A builder can publish several posts; translate the public profile once per
    # author and copy it onto each post card, reusing the previous snapshot cache.
    old_profiles = {}
    for item in cache.values():
        handle = str(item.get("handle") or "")
        if handle and item.get("bio") and item.get("bioZh"):
            old_profiles[(handle, item["bio"])] = item["bioZh"]
    profiles = {}
    for post in posts:
        key = (str(post.get("handle") or ""), str(post.get("bio") or ""))
        if not key[1]:
            post["bioZh"] = ""
        elif re.search(r"[\u3400-\u9fff]", key[1]):
            profiles[key] = key[1]
            post["bioZh"] = key[1]
        elif key in old_profiles:
            post["bioZh"] = old_profiles[key]
        else:
            profiles[key] = ""
    pending_profiles = [key for key, translated in profiles.items() if not translated]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(translate_to_chinese, key[1]): key for key in pending_profiles}
        for future in as_completed(futures):
            key = futures[future]
            try:
                profiles[key] = future.result()
            except Exception:
                profiles[key] = ""
    for post in posts:
        handle = str(post.get("handle") or "")
        key = (handle, str(post.get("bio") or ""))
        if key in profiles:
            post["bioZh"] = profiles[key]
        post["profileZh"] = PROFILE_ZH.get(handle) or post.get("bioZh", "")


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected JSON shape from {url}")
    return data


def collect(dry_run: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    try:
        previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    snapshots = {}
    source_times = {}
    for source, (url, key) in SOURCES.items():
        payload = fetch_json(url)
        snapshots[source] = compact_feed(source, key, payload, now)
        source_times[source] = payload.get("generatedAt")
    add_chinese_translations(snapshots["builders"], previous)
    result = {
        "source": "Follow Builders",
        "sourceUrl": "https://github.com/zarazhangrui/follow-builders",
        "feedUrls": {name: url for name, (url, _) in SOURCES.items()},
        "fetchedAt": now.isoformat(timespec="seconds"),
        "sourceGeneratedAt": source_times,
        **snapshots,
        "counts": {name: len(items) for name, items in snapshots.items()},
    }
    if not dry_run:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=OUTPUT.parent, delete=False) as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            temporary = Path(stream.name)
        temporary.replace(OUTPUT)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch public Follow Builders feeds into the V4 local snapshot.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without writing the snapshot.")
    args = parser.parse_args()
    data = collect(args.dry_run)
    print("Follow Builders: " + ", ".join(f"{k}={v}" for k, v in data["counts"].items()))
    if not args.dry_run:
        print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
