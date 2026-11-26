#!/usr/bin/env python3
"""Build the 30-day release view from version-level official evidence."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    from scripts.collect_models import non_release_title
    from scripts.collect_resolve_model_leads import candidate_rows, reconcile_candidate_dates, title_agrees
    from scripts.collect_release_recall import url_key
except ModuleNotFoundError:
    from collect_models import non_release_title
    from collect_resolve_model_leads import candidate_rows, reconcile_candidate_dates, title_agrees
    from collect_release_recall import url_key

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "site/data/models.json"
OUTPUT = ROOT / "site/data/model-releases-30d.json"
UPDATES = ROOT / "site/data/model-updates.json"
RESOLUTION = ROOT / "site/data/lead-resolution.json"


CATEGORIES = ("video", "image", "llm", "music", "tts", "audio")


def collect_pending(families: list, updates: list, confirmed: list, today: date) -> list:
    """Display discovery separately; never infer publication or verification dates."""
    family_map = {family["id"]: family for family in families}
    # Only canonical IDs: retired aliases may point to unrelated derivative products.
    confirmed_keys = {
        (row["modelFamilyId"], str(row["publishedAt"])[:10], url_key(row["url"]))
        for row in confirmed
    }
    def normalize(value):
        return "".join(ch for ch in str(value).casefold() if ch.isalnum())

    confirmed_update_ids = {uid for family in families for version in family.get("versions", [])
                            for uid in (version.get("releaseEvidence") or {}).get("sourceUpdateIds", [])}
    start = today - timedelta(days=29)
    candidates = {}
    for update in updates:
        if non_release_title(update.get("title")) or update.get("id") in confirmed_update_ids:
            continue
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
        if published and (family["id"], str(published)[:10], url_key(url)) in confirmed_keys:
            continue
        # Equivalent translated URLs or model-card entries with the same model and date.
        # Do not hide a conflicting date, or collapse distinct models on a rolling URL.
        normalized_title = normalize(title)
        if not published and family["id"] == "suno" and normalized_title == "introducingthev6familyofmusicmodels" and url.rstrip("/") == "https://suno.com/release-notes" and any(v.get("id") == "suno-v6" and v.get("releaseEvidence", {}).get("publishedAt") == "2026-09-09" for v in family.get("versions", [])):
            continue
        if published and any(
            row["modelFamilyId"] == family["id"]
            and str(row["publishedAt"])[:10] == str(published)[:10]
            and normalize(row.get("modelName", "")) in normalized_title
            and normalize(row.get("modelName", ""))
            for row in confirmed
        ):
            continue
        # Reject static assets accidentally extracted as articles.
        if url.split("?", 1)[0].lower().endswith((".svg", ".png", ".jpg", ".jpeg", ".webp", ".css", ".js", ".ico")):
            continue
        key = (family["id"], str(published or discovered)[:10], normalized_title)
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


# Only explicitly reviewed, recent model-service launches are exposed here.
# Do not promote generic API updates, beta access or later rollout into first releases.
VERIFIED_MODEL_STAGES = {
    ("gpt-live", "gpt-live-1-1", "radar-20261126-gpt-live-1-1-api"),
    ("qwen-audio-realtime", "qwen-audio-3-1-live", "v48-qwen-0001"),
    ("mureka", "mureka-remix-v9-5", "review-20261126-mureka-mureka-remix-v9-5-api-availability-20261112"),
}


def collect_verified_stages(families: list, today: date) -> list:
    start = today - timedelta(days=29)
    rows = []
    for family in families:
        for version in family.get("versions", []):
            for stage in version.get("historicalMilestones", []):
                key = (family["id"], version["id"], stage.get("chronicleAuditId"))
                if key not in VERIFIED_MODEL_STAGES or stage.get("datePrecision") != "day":
                    continue
                if stage.get("stage") != "api-availability" or not stage.get("verifiedAt") or not str(stage.get("sourceUrl", "")).startswith("https://"):
                    continue
                day = date.fromisoformat(stage["date"])
                if not start <= day <= today:
                    continue
                rows.append({
                    "id": "stage-" + key[2], "stageDate": stage["date"], "stage": stage["stage"],
                    "category": family["category"], "vendor": family["vendor"],
                    "modelName": version["name"], "summary": stage.get("summary", ""),
                    "url": stage["sourceUrl"], "sourceName": stage.get("sourceName", "官方来源"),
                    "modelFamilyId": family["id"], "modelVersionId": version["id"],
                    "verifiedAt": stage["verifiedAt"],
                })
    return sorted(rows, key=lambda x: (x["stageDate"], x["id"]), reverse=True)


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
                **({"verificationMethod": evidence["verificationMethod"], "corroboratingSources": evidence["corroboratingSources"]}
                   if evidence.get("verificationMethod") == "automatic-dual-official" else {}),
                **({"audioSubtype": evidence["audioSubtype"]} if evidence.get("audioSubtype") else {}),
            })
    items.sort(key=lambda item: (item["publishedAt"], item["vendor"], item["modelName"]), reverse=True)
    updates = json.loads(UPDATES.read_text(encoding="utf-8")).get("items", []) if UPDATES.exists() else []
    resolution = json.loads(RESOLUTION.read_text(encoding="utf-8")) if RESOLUTION.exists() else {}
    updates, _ = reconcile_candidate_dates(updates, resolution)
    recovered = [p for p in candidate_rows(resolution) if not any(
        u.get("official") is True and u.get("modelId") == p["modelId"]
        and url_key(u.get("url")) == url_key(p["url"])
        and str(u.get("publishedAt") or "")[:10] == p["publishedAt"][:10]
        and (title_agrees(p["title"], u.get("title") or "") or title_agrees(u.get("title") or "", p["title"])) for u in updates)]
    return {
        "schema": "model-release-digest/v2",
        "sourceOfTruth": "site/data/models.json",
        "windowDays": 30,
        "windowStart": start.isoformat(),
        "windowEnd": today.isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "categories": list(CATEGORIES),
        "items": items,
        "verifiedStages": collect_verified_stages(families, today),
        "pending": collect_pending(families, updates + recovered, items, today),
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
