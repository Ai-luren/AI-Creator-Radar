#!/usr/bin/env python3
"""Build the 30-day release view from version-level official evidence."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "site/data/models.json"
OUTPUT = ROOT / "site/data/model-releases-30d.json"
UPDATES = ROOT / "site/data/model-updates.json"


CATEGORIES = ("video", "image", "llm", "music", "tts", "audio")


def collect_pending(families: list, updates: list, confirmed: list, today: date) -> list:
    """Display discovery separately; never infer publication or verification dates."""
    family_map = {family["id"]: family for family in families}
    for family in families:
        for legacy in family.get("legacyIds", []):
            family_map.setdefault(legacy, family)
    confirmed_keys = {
        (row["modelFamilyId"], str(row["publishedAt"])[:10], row["url"])
        for row in confirmed
    }
    start = today - timedelta(days=29)
    candidates = {}
    for update in updates:
        family = family_map.get(update.get("modelId"))
        if not family or update.get("official") is not True:
            continue
        if update.get("updateType") not in {"release", "model-release", "model-card", "announcement"}:
            continue
        category = family.get("category")
        url, title = update.get("url"), update.get("title")
        if category not in CATEGORIES or not isinstance(url, str) or not url.startswith("https://") or not title or not update.get("id"):
            continue
        published = update.get("publishedAt")
        discovered = update.get("firstSeenAt") or update.get("discoveredAt")
        try:
            event_day = date.fromisoformat(str(published or discovered)[:10])
        except ValueError:
            continue
        if not start <= event_day <= today:
            continue
        if published and (family["id"], str(published)[:10], url) in confirmed_keys:
            continue
        # Same rolling URL can contain several distinct announcements.
        key = (family["id"], url, " ".join(title.casefold().split()))
        candidate = {
            "id": update["id"], "category": category,
            "vendor": family.get("vendor") or update.get("vendor", ""),
            "title": title, "summary": update.get("summary", ""),
            "url": url, "sourceName": update.get("sourceName", "官方来源"),
            "publishedAt": published, "discoveredAt": discovered,
            "modelFamilyId": family["id"], "updateType": update.get("updateType"),
            "verificationStatus": "pending",
        }
        old = candidates.get(key)
        if old is None or str(candidate.get("discoveredAt") or "") < str(old.get("discoveredAt") or ""):
            candidates[key] = candidate
    return sorted(candidates.values(), key=lambda item: (item["publishedAt"] or item["discoveredAt"] or "", item["id"]), reverse=True)


def build(today: date) -> dict:
    families = json.loads(MODELS.read_text(encoding="utf-8"))
    start = today - timedelta(days=29)
    items = []
    for family in families:
        for version in family.get("versions", []):
            evidence = version.get("releaseEvidence")
            if not isinstance(evidence, dict):
                continue
            published = evidence.get("publishedAt") or version.get("releaseDate")
            if not published:
                continue
            try:
                release_day = date.fromisoformat(str(published)[:10])
            except ValueError:
                continue
            if not start <= release_day <= today:
                continue
            items.append({
                "id": evidence["eventId"],
                "publishedAt": published,
                "category": evidence.get("category", family.get("category", "other")),
                "vendor": family.get("vendor", "未知厂商"),
                "modelName": evidence.get("modelName", version.get("name", "未知型号")),
                "summary": evidence.get("summary", ""),
                "access": evidence.get("access", version.get("access", "")),
                "url": evidence["sourceUrl"],
                "sourceName": evidence.get("sourceName", "官方原文"),
                "modelFamilyId": family["id"],
                "modelVersionId": version["id"],
                "evidenceType": evidence.get("evidenceType", "official-release"),
                "verifiedAt": evidence.get("verifiedAt", ""),
            })
    items.sort(key=lambda item: (item["publishedAt"], item["vendor"], item["modelName"]), reverse=True)
    return {
        "schema": "model-release-digest/v2",
        "sourceOfTruth": "site/data/models.json",
        "windowDays": 30,
        "windowStart": start.isoformat(),
        "windowEnd": today.isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "categories": list(CATEGORIES),
        "items": items,
        "pending": collect_pending(families, json.loads(UPDATES.read_text(encoding="utf-8")).get("items", []) if UPDATES.exists() else [], items, today),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", help="Override date for repeatable generation (YYYY-MM-DD)")
    parser.add_argument("--check", action="store_true", help="Fail if the checked-in digest differs")
    args = parser.parse_args()
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()
    result = build(today)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not OUTPUT.exists():
            raise SystemExit("30-day release digest is missing")
        previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
        previous.pop("updatedAt", None)
        expected = dict(result)
        expected.pop("updatedAt", None)
        if previous != expected:
            raise SystemExit("30-day release digest is stale; run scripts/build_model_release_digest.py")
        return 0
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"Built {len(result['items'])} releases for {result['windowStart']} to {result['windowEnd']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
