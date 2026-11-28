#!/usr/bin/env python3
"""Append explicitly unreviewed official discovery records, never rewrite audited history."""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

try:
    from scripts.collect_models import non_release_title
    from scripts.collect_resolve_model_leads import reconcile_candidate_dates
    from scripts.build_model_release_digest import reviewed_pending_disposition
    from scripts.collect_release_recall import url_key
except ModuleNotFoundError:
    from collect_models import non_release_title
    from collect_resolve_model_leads import reconcile_candidate_dates
    from build_model_release_digest import reviewed_pending_disposition
    from collect_release_recall import url_key

ROOT = Path(__file__).resolve().parents[1]
TOPICS_FILE = ROOT / "site/data/topics.json"
UPDATES_FILE = ROOT / "site/data/model-updates.json"
STATUS_FILE = ROOT / "site/data/chronicle-updates-status.json"

CONFIG_FILE = ROOT / "config/chronicle-release-links.json"
ALLOWED_UPDATE_TYPES = {"release", "model-release", "announcement"}
PENDING_STATUS = "官方一手来源自动收录 · 待复核"

def vendor_topics() -> dict:
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {vendor.casefold(): topic for topic, vendors in config["vendorTopics"].items()
            for vendor in vendors}

def protected(event: dict) -> bool:
    return (event.get("autoCollected") is not True or bool(event.get("auditId"))
            or bool(event.get("verificationDate"))
            or event.get("verificationStatus") != PENDING_STATUS)


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


# Reviewed one-to-one original article duplicates of existing audited nodes.
# Do not infer equality from vendor/day alone, especially rolling docs.
REVIEWED_HISTORY_DUPLICATES = {
    "b6edf533d574346e9f": ("anthropic", "2026-11-09", "claude", "Introducing Claude Fable 5.2 and Claude Mythos 5.2", "https://www.anthropic.com/claude-fable-and-mythos-5-2", "v48-anthropic-0014", "https://www.anthropic.com/claude-fable-and-mythos-5-2"),
    "5534c5e9b31121f3bc": ("anthropic", "2026-10-07", "claude", "Introducing Claude Haiku 5.5", "https://www.anthropic.com/claude-haiku-5-5", "v48-anthropic-0035", "https://www.anthropic.com/claude-haiku-5-5"),
    "1d613fd24eac33beca": ("anthropic", "2026-09-22", "claude", "Introducing Claude Opus 5.5", "https://www.anthropic.com/claude-opus-5-5", "v48-anthropic-0046", "https://www.anthropic.com/claude-opus-5-5"),
    "cde87921a4e22a4cb6": ("suno", "2025-10-21", "suno", "v4.5-all: A new free model for everyone", "https://suno.com/release-notes/v4-5-all-a-new-free-model-for-everyone", "review-20261126-suno-suno-v4-5-all-release-20251021", "https://suno.com/release-notes/v4-5-all-a-new-free-model-for-everyone"),
    "02f7888b26ecc3fff0": ("bytedance", "2026-11-09", "seedream", "生成更真实，百轮编辑更稳定｜Seedream 5.5 发布", "https://seed.bytedance.com/zh/blog/more-realistic-images-more-stable-editing-across-100-rounds-introducing-seedream-5-5?view_from=homepage_tab", "v48-bytedance-0012", "https://seed.bytedance.com/zh/blog/more-realistic-images-more-stable-editing-across-100-rounds-introducing-seedream-5-5"),
    "a58e69516f39f27b5e": ("bytedance", "2026-08-05", "seed-realtime", "SeedRealtime 音视频全双工大模型发布：走向全模态自然交互", "https://seed.bytedance.com/zh/blog/seedrealtime-audio-visual-full-duplex-llm-released-toward-omni-modal-natural-interaction?view_from=homepage_tab", "v48-bytedance-seed-0088", "https://seed.bytedance.com/zh/blog/seedrealtime-audio-visual-full-duplex-llm-released-toward-omni-modal-natural-interaction"),
    "839af1e97986262326": ("bytedance", "2026-07-31", "seedance", "一镜成片，随心参考：Seedance 2.5 正式发布", "https://seed.bytedance.com/zh/blog/one-take-creation-flexible-referencing-introducing-seedance-2-5?view_from=homepage_tab", "review-20261127-seedance-25", "https://seed.bytedance.com/zh/blog/one-take-creation-flexible-referencing-introducing-seedance-2-5"),
}


def redundant_review_node(topic,event):
    if protected(event):
        return False
    update={"id":event.get("sourceUpdateId"),"modelId":event.get("sourceModelId"),
            "publishedAt":event.get("date"),"url":event.get("url"),"title":event.get("title"),
            "official":event.get("sourceTier")=="official-primary"}
    if reviewed_pending_disposition(update)=="reviewed-non-model":
        return True
    proof=REVIEWED_HISTORY_DUPLICATES.get(event.get("sourceUpdateId"))
    if not proof:
        return False
    topic_id,day,family,title,url,audit_id,audit_url=proof
    if (topic.get("id")!=topic_id or event.get("date")!=day or event.get("sourceModelId")!=family
            or event.get("title")!=title or url_key(event.get("url"))!=url_key(url)):
        return False
    return any(n.get("auditId")==audit_id and n.get("date")==day
               and url_key(n.get("url"))==url_key(audit_url)
               and str(n.get("verificationStatus","")).startswith(("已确认","已核实"))
               and n.get("autoCollected") is not True for n in topic.get("milestones",[]))


def merge_official_updates(topics: list[dict], updates: list[dict], checked_at: str) -> tuple[list[dict], dict]:
    mapping = vendor_topics()
    topics_by_id = {topic.get("id"): topic for topic in topics if topic.get("group") == "公司与模型"}
    existing_events_by_id = {
        (topic["id"], str(event.get("sourceUpdateId"))): event
        for topic in topics_by_id.values()
        for event in topic.get("milestones", [])
        if event.get("sourceUpdateId")
    }
    seen_links = {
        (topic["id"], normalize_url(str(event.get("url", ""))), str(event.get("date", "")), str(event.get("sourceModelId", "")))
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
        if update.get("official") is not True or update_type not in ALLOWED_UPDATE_TYPES or non_release_title(update.get("title")):
            continue
        date = parse_date(update.get("publishedAt", ""))
        url = str(update.get("url", "")).strip()
        vendor = str(update.get("vendor", "")).strip()
        title = str(update.get("title", "")).strip()
        parsed_url = urlsplit(url)
        if not date or date > checked_at[:10] or parsed_url.scheme != "https" or not parsed_url.hostname or not title:
            continue
        considered += 1
        topic_id = mapping.get(vendor.casefold())
        topic = topics_by_id.get(topic_id)
        if not topic:
            unmatched_vendors.add(vendor or "（厂商缺失）")
            continue

        update_id = str(update.get("id", "")).strip()
        model_id = str(update.get("modelId") or "")
        event_key = (topic_id, update_id)
        if update_id and event_key in existing_events_by_id:
            event = existing_events_by_id[event_key]
            if protected(event):
                continue
            next_values = {
                "date": date,
                "kind": event_kind(update_type),
                "title": title,
                "summary": str(update.get("summary", "")).strip(),
                "url": url,
                "sourceId": update.get("sourceId", ""),
                "sourceName": update.get("sourceName", ""),
                "verificationStatus": PENDING_STATUS,
                "sourceModelId": model_id,
                "dateKind": "article-publication-date" if update.get("recoveryProofId") else "source-date",
                **({"recoveryProofId": update["recoveryProofId"], "previousSourceDate": update.get("listingPublishedAt")} if update.get("recoveryProofId") else {}),
            }
            if update.get("category"):
                next_values["modelCategory"] = update["category"]
            if not update.get("recoveryProofId") and event.get("recoveryProofId"):
                event.pop("recoveryProofId", None)
                event.pop("previousSourceDate", None)
                updated += 1
            if any(event.get(key) != value for key, value in next_values.items()):
                event.update(next_values)
                updated += 1
            continue
        link_key = (topic_id, normalize_url(url), date, model_id)
        if link_key in seen_links or (topic_id, normalize_url(url), date, "") in seen_links:
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
            "verificationStatus": PENDING_STATUS,
            "dateKind": "article-publication-date" if update.get("recoveryProofId") else "source-date",
            **({"recoveryProofId": update["recoveryProofId"], "previousSourceDate": update.get("listingPublishedAt")} if update.get("recoveryProofId") else {}),
            "sourceModelId": model_id,
            "collectedAt": checked_at,
        }
        if update.get("category"):
            event["modelCategory"] = update["category"]
        topic.setdefault("milestones", []).append(event)
        seen_links.add(link_key)
        if update_id:
            existing_events_by_id[event_key] = event
        added += 1

    # Exact duplicate unreviewed nodes only. Preserve all audited history and distinct date conflicts.
    deduplicated = 0
    reconciled = 0
    for topic in topics_by_id.values():
        seen = set()
        retained = []
        for event in topic.get("milestones", []):
            if protected(event):
                retained.append(event)
                continue
            if redundant_review_node(topic,event):
                reconciled += 1
                continue
            identity = (normalize_url(str(event.get("url", ""))).split("?")[0], str(event.get("date", "")),
                        str(event.get("sourceModelId", "")), "".join(ch for ch in str(event.get("title", "")).casefold() if ch.isalnum()))
            # Strip only known tracking query parameters using the common key, not meaningful query IDs.
            from urllib.parse import parse_qsl, urlencode
            parsed = urlsplit(str(event.get("url", "")))
            query = urlencode(sorted((k,v) for k,v in parse_qsl(parsed.query) if k.casefold() not in {"tab","view_from","trk","source","lang","ref","fbclid","gclid"} and not k.casefold().startswith("utm_")))
            identity = (identity[0] + ("?" + query if query else ""), *identity[1:])
            if identity[0] and identity[2] and identity in seen:
                deduplicated += 1
                continue
            seen.add(identity)
            retained.append(event)
        topic["milestones"] = sorted(
            retained,
            key=lambda event: (str(event.get("date", "")), str(event.get("title", ""))),
            reverse=True,
        )

    status = {
        "checkedAt": checked_at,
        "sourceFile": str(UPDATES_FILE.relative_to(ROOT)),
        "officialUpdatesConsidered": considered,
        "added": added,
        "updated": updated,
        "deduplicatedUnreviewed": deduplicated,
        "reconciledReviewedOrNonModel": reconciled,
        "unmatchedVendors": sorted(unmatched_vendors),
        "policy": "仅收录已配置厂商的模型发布或预告候选；来源日期不等于首发日期；不覆盖人工审核记录、不自动新增厂商。",
    }
    return topics, status



def sync_automatic_confirmations(topics, families):
    """Promote only matching machine-discovered nodes; never change reviewed history."""
    mapping = vendor_topics()
    by_topic = {t["id"]: t for t in topics if t.get("group") == "公司与模型"}
    synced = 0
    for family in families:
        topic = by_topic.get(mapping.get(str(family.get("vendor", "")).casefold()))
        if not topic:
            continue
        for version in family.get("versions", []):
            evidence = version.get("releaseEvidence") or {}
            if evidence.get("verificationMethod") != "automatic-dual-official":
                continue
            ids = set(evidence.get("sourceUpdateIds", []))
            events = topic.get("milestones", [])
            # Explicit audited history, if present, remains authoritative.
            matches = [e for e in events if not protected(e) and e.get("sourceUpdateId") in ids
                       and e.get("sourceModelId") == family["id"]
                       and e.get("date") == evidence["publishedAt"]]
            if any(e.get("automaticReleaseEventId") == evidence["eventId"] for e in events):
                # A subsequent collection may rediscover the secondary article.
                topic["milestones"] = [e for e in events if not any(e is m for m in matches)]
                continue
            if not matches:
                continue
            primary = next((e for e in matches if e.get("url") == evidence["sourceUrl"]), matches[0])
            primary.update({
                "kind": "模型发布",
                "title": version["name"] + " 正式发布",
                "url": evidence["sourceUrl"],
                "sourceName": evidence["sourceName"],
                "verificationStatus": "自动双源核验 · 非人工复核",
                "verificationMethod": evidence["verificationMethod"],
                "automaticReleaseEventId": evidence["eventId"],
                "corroboratingSources": evidence["corroboratingSources"],
                "dateKind": "confirmed-release-date",
                "sourceModelId": family["id"],
            })
            topic["milestones"] = [e for e in events if e is primary or not any(e is m for m in matches)]
            synced += 1
    return synced


def main() -> int:
    parser = argparse.ArgumentParser(description="Append official model updates to company chronologies.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files.")
    args = parser.parse_args()

    topics = read_json(TOPICS_FILE)
    update_doc = read_json(UPDATES_FILE)
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    resolution_file = ROOT / "site/data/lead-resolution.json"
    resolution = read_json(resolution_file) if resolution_file.exists() else {}
    updates, corrections = reconcile_candidate_dates(update_doc.get("items", []), resolution)
    merged, status = merge_official_updates(topics, updates, checked_at)
    status["candidateDateCorrections"] = len(corrections)
    status["automaticallyConfirmed"] = sync_automatic_confirmations(merged, read_json(ROOT / "site/data/models.json"))
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
