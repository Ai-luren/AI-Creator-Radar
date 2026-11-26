#!/usr/bin/env python3
"""Collect public Google Trends signals for entertainment and creator topics."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site" / "data" / "social-trends.json"
BASE = "https://trends.google.com/trending/rss?geo={}"
WINDOW = timedelta(days=7)
REGIONS = {
    "US": "美国",
    "GB": "英国",
    "CA": "加拿大",
    "AU": "澳大利亚",
    "JP": "日本",
    "KR": "韩国",
    "TW": "台湾地区",
    "IN": "印度",
}
TREND_NAMESPACE = "https://trends.google.com/trending/rss"
USER_AGENT = "AI-Creator-Radar/1.0 (public Google Trends RSS reader)"

CATEGORIES = {
    "music": re.compile(r"\b(music|song|singer|album|concert|tour|kpop|k-pop|rapper|grammy|billboard|suno|mv)\b|音乐|歌曲|歌手|专辑|演唱会|巡演|偶像|乐队|音综|音樂|歌手|歌曲|專輯|演唱會|음악|가수|앨범|콘서트|歌|アルバム|コンサート", re.I),
    "film_tv": re.compile(r"\b(movie|film|actor|actress|celebrity|tv show|series|anime|manga|oscars|emmys|netflix|disney|disney\+|marvel|star wars|reality show|voice actor)\b|电影|影片|演员|明星|综艺|剧集|电视剧|电影节|动漫|动画|漫画|配音|聲優|電影|演員|明星|連續劇|動畫|漫畫|배우|영화|드라마|애니|俳優|映画|アニメ|ドラマ", re.I),
    "games": re.compile(r"\b(game|gaming|gamer|playstation|xbox|nintendo|fortnite|minecraft|roblox|gta|pokemon|esports)\b|游戏|电竞|電競|遊戲|게임|ゲーム|ポケモン", re.I),
    "sports": re.compile(r"\b(vs\.?|match|league|tournament|world cup|championship|nba|nfl|fifa|cricket|basketball|football|baseball|tennis|formula 1|f1|ufc|olympics|haka)\b|比赛|联赛|锦标赛|世界杯|总决赛|球队|球员|赛事|篮球|棒球|足球|野球|比賽|聯賽|월드컵|경기|試合|大会|야구|축구", re.I),
    "social_format": re.compile(r"\b(meme|challenge|viral|trend|reels|tiktok|instagram|youtube shorts|dance trend)\b|网络热梗|挑战|挑战赛|爆火|走红|短视频|热梗|チャレンジ|ミーム|챌린지", re.I),
}
CATEGORY_LABELS = {
    "music": "音乐 / MV 话题",
    "film_tv": "影视 / 文娱话题",
    "games": "游戏 / 电竞话题",
    "sports": "体育事件话题",
    "social_format": "社媒形式 / 热梗",
}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def trend_category(title: str, related: list[dict]) -> str | None:
    # Classify from the actual trending query only. Related headlines help a
    # creator verify context, but must not turn an unrelated query into a
    # category match merely because a headline mentions a movie, game or song.
    text = title
    for category, pattern in CATEGORIES.items():
        if pattern.search(text):
            return category
    return None


def trend_url(geo: str, title: str) -> str:
    params = urllib.parse.urlencode({"date": "now 7-d", "geo": geo, "q": title})
    return f"https://trends.google.com/trends/explore?{params}"


def parse_related_news(item: ET.Element) -> list[dict]:
    result = []
    for node in item:
        if local_name(node.tag) != "news_item":
            continue
        fields = {local_name(child.tag): (child.text or "").strip() for child in node}
        url = fields.get("news_item_url", "")
        if not fields.get("news_item_title") or not url.startswith("https://"):
            continue
        result.append({
            "title": fields["news_item_title"],
            "source": fields.get("news_item_source", ""),
            "url": url,
            "image": fields.get("news_item_picture", ""),
        })
    return result[:3]


def parse_feed(geo: str, body: bytes, now: datetime) -> list[dict]:
    root = ET.fromstring(body)
    entries = []
    for node in root.findall("./channel/item"):
        fields = {local_name(child.tag): child for child in node if local_name(child.tag) != "news_item"}
        title = (fields.get("title").text or "").strip() if fields.get("title") is not None else ""
        published_raw = (fields.get("pubDate").text or "").strip() if fields.get("pubDate") is not None else ""
        if not title or not published_raw:
            continue
        # Calendar-only queries do not give creators a usable subject or angle.
        if re.fullmatch(r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?", title):
            continue
        try:
            published = parsedate_to_datetime(published_raw).astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            continue
        if published > now or now - published > WINDOW:
            continue
        related = parse_related_news(node)
        category = trend_category(title, related)
        if not category:
            continue
        traffic = (fields.get("approx_traffic").text or "").strip() if fields.get("approx_traffic") is not None else ""
        canonical_title = re.sub(r"[\W_]+", "", title.casefold(), flags=re.UNICODE)
        key = hashlib.sha1(canonical_title.encode("utf-8")).hexdigest()[:12]
        entries.append({
            "id": f"google-search-trend-{key}",
            "type": "search-trend",
            "title": title,
            "category": category,
            "categoryLabel": CATEGORY_LABELS[category],
            "source": {"name": "Google 搜索趋势", "url": "https://trends.google.com/trending"},
            "region": "overseas",
            "regionCode": geo,
            "regionName": REGIONS[geo],
            "publishedAt": published.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "approxSearchTraffic": traffic or None,
            "trendUrl": trend_url(geo, title),
            "relatedNews": related,
            "evidenceNote": "Google 搜索趋势信号；估算搜索量不是社媒播放量、点赞数或互动率。",
        })
    return entries


def fetch_region(geo: str, now: datetime) -> list[dict]:
    request = urllib.request.Request(BASE.format(geo), headers={"Accept": "application/rss+xml, application/xml", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        return parse_feed(geo, response.read(), now)


def merge_regions(records: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for record in records:
        item = merged.get(record["id"])
        observation = {
            "regionCode": record["regionCode"],
            "regionName": record["regionName"],
            "publishedAt": record["publishedAt"],
            "approxSearchTraffic": record["approxSearchTraffic"],
            "trendUrl": record["trendUrl"],
        }
        if item is None:
            item = {**record, "observations": []}
            merged[record["id"]] = item
        item["observations"].append(observation)
        item["publishedAt"] = max(item["publishedAt"], record["publishedAt"])
        known = {news["url"] for news in item["relatedNews"]}
        for news in record["relatedNews"]:
            if news["url"] not in known:
                item["relatedNews"].append(news)
                known.add(news["url"])
        item["relatedNews"] = item["relatedNews"][:5]
    def search_signal(item: dict) -> int:
        values = []
        for observation in item["observations"]:
            raw = str(observation.get("approxSearchTraffic") or "")
            match = re.search(r"\d[\d,]*", raw)
            if match:
                values.append(int(match.group().replace(",", "")))
        return max(values, default=0)

    # Google search-volume buckets are comparable only as search signals.
    # Use their highest observed region bucket, then freshness as a tiebreaker.
    return sorted(merged.values(), key=lambda item: (search_signal(item), item["publishedAt"], item["title"].casefold()), reverse=True)


def collect(dry_run: bool = False, geos: list[str] | None = None) -> dict:
    now = datetime.now(timezone.utc)
    selected = geos or list(REGIONS)
    unknown = sorted(set(selected) - set(REGIONS))
    if unknown:
        raise ValueError(f"Unsupported region code(s): {', '.join(unknown)}")
    records = []
    statuses = {}
    for geo in selected:
        try:
            records.extend(fetch_region(geo, now))
            statuses[geo] = {"status": "ok", "region": REGIONS[geo]}
        except Exception as error:
            statuses[geo] = {"status": "error", "region": REGIONS[geo], "message": str(error)}
    if not records and not any(status["status"] == "ok" for status in statuses.values()):
        raise RuntimeError("All Google Trends RSS feeds failed")
    result = {
        "source": "Google Trends RSS",
        "sourceUrl": "https://trends.google.com/trending",
        "fetchedAt": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "window": "7d",
        "metricDefinition": "approxSearchTraffic is an approximate search-volume bucket supplied by Google Trends. It is not a social-platform engagement metric.",
        "regions": statuses,
        "items": merge_regions(records),
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
    parser = argparse.ArgumentParser(description="Collect public Google Trends signals for video-topic discovery.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without writing the snapshot.")
    parser.add_argument("--geo", action="append", choices=sorted(REGIONS), help="Region code to fetch; repeat to choose multiple regions.")
    args = parser.parse_args()
    data = collect(dry_run=args.dry_run, geos=args.geo)
    action = "validated without writing" if args.dry_run else f"saved to {OUTPUT.relative_to(ROOT)}"
    print(f"Google Trends: {len(data['items'])} deduplicated culture/search signals {action}")
    print("Regions:", ", ".join(f"{code}={status['status']}" for code, status in data["regions"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
