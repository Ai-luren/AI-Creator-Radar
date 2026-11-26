#!/usr/bin/env python3
"""Append official model updates to matching company chronologies."""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
TOPICS_FILE = ROOT / "site/data/topics.json"
UPDATES_FILE = ROOT / "site/data/model-updates.json"
STATUS_FILE = ROOT / "site/data/chronicle-updates-status.json"

VENDOR_TOPIC = {
    "anthropic": "anthropic",
    "google": "google",
    "google deepmind": "google",
    "meta superintelligence labs": "meta",
    "minimax": "minimax",
    "openai": "openai",
    "suno": "suno",
    "字节跳动 seed": "bytedance",
    "字节跳动 seed / 即梦": "bytedance",
    "快手": "kuaishou",
    "kling ai": "kuaishou",
    "阿里巴巴通义千问": "qwen",
    "生数科技": "shengshu",
    "pika": "pika",
}
AUTO_TOPIC_STUBS = {
    "pika": {
        "group": "公司与模型",
        "id": "pika",
        "name": "Pika",
        "description": "Pika 的 AI 视频生成产品与模型发布记录。",
        "keywords": ["Pika", "Pika Labs"],
        "topicUrl": "https://pika.art",
        "domain": "pika.art",
        "modelCategories": ["video"],
        "milestones": [],
        "chronicleSourceVersion": "official-feed-sync",
        "chronicleSourceUrl": "https://pika.art",
    }
}
ALLOWED_UPDATE_TYPES = {"release", "announcement", "model-card", "api", "pricing"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(rendered)
        temp_path = Path(tmp.name)
    temp_path.replace(path)


def normalize_url(value: str) -> str:
    try:
        parts = urlsplit(value.strip())
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))
    except ValueError:
        return value.strip()


def parse_date(value: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(candidate[:10], "%Y-%m-%d")
        except ValueError:
            return None
    return parsed.date().isoformat()


def event_kind(update_type: str) -> str:
    return {
        "model-card": "模型卡更新",
        "api": "接口更新",
        "pricing": "接口价格更新",
        "announcement": "模型预告",
    }.get(update_type, "模型发布")


def merge_official_updates(topics: list[dict], updates: list[dict], checked_at: str) -> tuple[list[dict], dict]:
    existing_topic_ids = {topic.get("id") for topic in topics}
    for topic_id, stub in AUTO_TOPIC_STUBS.items():
        if topic_id not in existing_topic_ids:
            topics.append(json.loads(json.dumps(stub, ensure_ascii=False)))
    topics_by_id = {topic.get("id"): topic for topic in topics if topic.get("group") == "公司与模型"}
    existing_events_by_id = {
        str(event.get("sourceUpdateId")): event
        for topic in topics_by_id.values()
        for event in topic.get("milestones", [])
        if event.get("sourceUpdateId") and event.get("autoCollected") is True
    }
    seen_links = {
        (normalize_url(str(event.get("url", ""))), str(event.get("date", "")))
        for topic in topics_by_id.values()
        for event in topic.get("milestones", [])
        if event.get("url")
    }

    added = 0
    updated = 0
    considered = 0
    unmatched_vendors: set[str] = set()
    for update in updates:
        update_type = str(update.get("updateType", "release")).casefold()
        if update.get("official") is not True or update_type not in ALLOWED_UPDATE_TYPES:
            continue
        date = parse_date(update.get("publishedAt", ""))
        url = str(update.get("url", "")).strip()
        vendor = str(update.get("vendor", "")).strip()
        title = str(update.get("title", "")).strip()
        if not date or not url or not title:
            continue
        considered += 1
        topic_id = VENDOR_TOPIC.get(vendor.casefold())
        topic = topics_by_id.get(topic_id)
        if not topic:
            unmatched_vendors.add(vendor or "（厂商缺失）")
            continue

        update_id = str(update.get("id", "")).strip()
        if update_id and update_id in existing_events_by_id:
            event = existing_events_by_id[update_id]
            next_values = {
                "date": date,
                "kind": event_kind(update_type),
                "title": title,
                "summary": str(update.get("summary", "")).strip(),
                "url": url,
                "sourceId": update.get("sourceId", ""),
                "sourceName": update.get("sourceName", ""),
                "verificationStatus": "官方一手来源自动收录 · 待复核",
            }
            if update.get("category"):
                next_values["modelCategory"] = update["category"]
            if any(event.get(key) != value for key, value in next_values.items()):
                event.update(next_values)
                updated += 1
            continue
        link_key = (normalize_url(url), date)
        if link_key in seen_links:
            continue

        event = {
            "date": date,
            "kind": event_kind(update_type),
            "title": title,
            "summary": str(update.get("summary", "")).strip(),
            "url": url,
            "sourceId": update.get("sourceId", ""),
            "sourceName": update.get("sourceName", ""),
            "sourceUpdateId": update_id,
            "sourceTier": "official-primary",
            "autoCollected": True,
            "verificationStatus": "官方一手来源自动收录 · 待复核",
        "collectedAt": checked_at,
        }
        if update.get("category"):
            event["modelCategory"] = update["category"]
        topic.setdefault("milestones", []).append(event)
        seen_links.add(link_key)
        if update_id:
            existing_events_by_id[update_id] = event
        added += 1

    for topic in topics_by_id.values():
        topic["milestones"] = sorted(
            topic.get("milestones", []),
            key=lambda event: (str(event.get("date", "")), str(event.get("title", ""))),
            reverse=True,
        )

    status = {
        "checkedAt": checked_at,
        "sourceFile": str(UPDATES_FILE.relative_to(ROOT)),
        "officialUpdatesConsidered": considered,
        "added": added,
        "updated": updated,
        "unmatchedVendors": sorted(unmatched_vendors),
        "policy": "仅追加官方来源采集记录；未人工复核的节点会明确标记，不覆盖人工审核节点。",
    }
    return topics, status


def main() -> int:
    parser = argparse.ArgumentParser(description="Append official model updates to company chronologies.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files.")
    args = parser.parse_args()

    topics = read_json(TOPICS_FILE)
    update_doc = read_json(UPDATES_FILE)
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    merged, status = merge_official_updates(topics, update_doc.get("items", []), checked_at)
    print(
        "Chronicles: {added} official-source nodes added; {considered} updates considered; unmatched vendors: {unmatched}".format(
            added=status["added"], considered=status["officialUpdatesConsidered"],
            unmatched=", ".join(status["unmatchedVendors"]) or "none",
        )
    )
    if not args.dry_run:
        write_json(TOPICS_FILE, merged)
        write_json(STATUS_FILE, status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
