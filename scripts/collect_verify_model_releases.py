#!/usr/bin/env python3
"""Conservative, zero-token confirmation of recent releases from two official publications.

Only structured publication dates (not modified dates or nearby HTML dates) and
unambiguous release titles qualify. Uncertain candidates remain in discovery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

try:
    from scripts.collect_models import normalize_url, write_json
except ModuleNotFoundError:
    from collect_models import normalize_url, write_json

ROOT = Path(__file__).resolve().parents[1]
METHOD = "automatic-dual-official"
DATE_KINDS = {"jsonld-datePublished", "feed-published"}
# New identities are intentionally limited to uncomplicated numeric versions
# of canonical families. Named variants and unfamiliar model families stay pending.
NEW_NAMES = {
    "seedance": r"Seedance \d+(?:\.\d+){0,2}",
    "seedream": r"Seedream \d+(?:\.\d+){0,2}",
    "glm": r"GLM-\d+(?:\.\d+){0,2}",
    "llama": r"Llama \d+(?:\.\d+){0,2}",
}
STAGE_WARNING = re.compile(
    r"\b(?:preview|alpha|beta|early access|waitlist|coming soon|api|rollout|"
    r"update|upgrade|weights|research|limited access|select users|not yet|will be)\b"
    r"|预览|内测|公测|预约|即将|接口|权重|灰度|更新|升级|部分用户", re.I)
TITLE_FORMS = (
    r"(.+?)\s+(?:officially released|officially launched|has been released|is released|release[d]?)",
    r"(?:official release of|official launch of|releasing)\s+(.+?)",
    r"(.+?)\s*(?:正式发布|正式推出)",
    r"(?:正式发布|正式推出)\s*(.+?)",
)


def release_name(title):
    title = str(title or "").strip().rstrip("!.！。").strip()
    for pattern in TITLE_FORMS:
        match = re.fullmatch(pattern, title, re.I)
        if match:
            name = match.group(1).strip()
            if len(name) <= 80 and re.search(r"\d", name) and not STAGE_WARNING.search(name):
                return name
    return None


def key(name):
    return re.sub(r"[\s_-]+", "", str(name or "").casefold())


def host_for(url):
    try:
        value = urlsplit(url)
        return value.hostname if value.scheme == "https" and not value.username and not value.password and value.port in (None, 443) else None
    except (ValueError, TypeError):
        return None


def evidence_item(item, source, status, today):
    if not source or not source.get("active") or source.get("official") is not True:
        return None
    if item.get("official") is not True or item.get("updateType") not in {"release", "model-release"}:
        return None
    if item.get("modelId") not in source.get("modelMatches", {}):
        return None
    if item.get("publicationDateKind") not in DATE_KINDS or not status or status.get("error"):
        return None
    if not item.get("publicationObservedAt") or item["publicationObservedAt"] != status.get("checkedAt"):
        return None
    if STAGE_WARNING.search(str(item.get("summary") or "")):
        return None
    name = release_name(item.get("title"))
    if not name or not item.get("id"):
        return None
    try:
        day = date.fromisoformat(str(item.get("publishedAt"))[:10])
    except ValueError:
        return None
    if not today - timedelta(days=29) <= day <= today:
        return None
    url = normalize_url(item.get("url") or "")
    host = host_for(url)
    # No URL guesses, arbitrary external links, listing pages or same-page translations.
    endpoints = [source["url"], *source.get("fallbackUrls", [])]
    allowed_hosts = {host_for(u) for u in endpoints} | set(source.get("announcementHosts", []))
    if not host or host not in allowed_hosts or url in {normalize_url(u) for u in endpoints}:
        return None
    if not urlsplit(url).path.strip("/"):
        return None
    return {"sourceId": source["id"], "sourceUrl": url, "sourceName": source["name"],
            "sourceUpdateId": item["id"], "title": item["title"], "modelName": name,
            "publishedAt": day.isoformat(), "publicationDateKind": item["publicationDateKind"],
            "observedAt": item["publicationObservedAt"]}


def reconcile(families, updates, sources, status, vendor_topics, today):
    source_by_id = {s["id"]: s for s in sources}
    source_status = {s["id"]: s for s in status.get("sources", [])}
    vendor_group = {vendor.casefold(): topic for topic, vendors in vendor_topics.items() for vendor in vendors}
    groups = defaultdict(list)
    conflicts = defaultdict(set)
    fam_by_id = {f["id"]: f for f in families}
    for item in updates:
        family = fam_by_id.get(item.get("modelId"))
        source = source_by_id.get(item.get("sourceId"))
        if not family or family.get("category") not in {"video", "image", "llm", "music", "tts", "audio"} or not source:
            continue
        topic = vendor_group.get(str(family.get("vendor", "")).casefold())
        if not topic or vendor_group.get(str(source.get("vendor", "")).casefold()) != topic:
            continue
        if item.get("official") is not True or source.get("official") is not True or not source.get("active"):
            continue
        name = release_name(item.get("title"))
        if not name:
            continue
        identity = (family["id"], key(name))
        try:
            conflicts[identity].add(date.fromisoformat(str(item.get("publishedAt"))[:10]).isoformat())
        except ValueError:
            pass
        proof = evidence_item(item, source, source_status.get(source["id"]), today)
        if proof:
            groups[identity].append(proof)

    confirmed, pending = [], []
    for (fid, identity), records in sorted(groups.items()):
        family = fam_by_id[fid]
        label = records[0]["modelName"]
        dates = {p["publishedAt"] for p in records}
        pairs = [(a, b) for i, a in enumerate(records) for b in records[i+1:]
                 if a["sourceId"] != b["sourceId"] and host_for(a["sourceUrl"]) != host_for(b["sourceUrl"])
                 and a["sourceUrl"] != b["sourceUrl"] and a["sourceUpdateId"] != b["sourceUpdateId"]]
        reason = None
        if len(dates) != 1 or len(conflicts[(fid, identity)]) > 1:
            reason = "conflicting-publication-dates"
        elif not pairs:
            reason = "independent-official-publication-required"
        versions = family.get("versions", [])
        matches = [v for v in versions if key(v.get("name")) == identity]
        if len(matches) > 1:
            reason = "ambiguous-canonical-identity"
        version = matches[0] if len(matches) == 1 else None
        if version and version.get("releaseEvidence"):
            continue
        if version and (version.get("recordKind") or version.get("historicalMilestones") or version.get("derivedFrom") or version.get("provider")):
            reason = "existing-stage-or-identity-needs-review"
        if version and version.get("releaseDate") and str(version["releaseDate"])[:10] not in dates:
            reason = "existing-release-date-conflict"
        if not version and not re.fullmatch(NEW_NAMES.get(fid, r"(?!)"), label, re.I):
            reason = "new-identity-needs-review"
        vid = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        if not version and (not vid or any(v.get("id") == vid or key(v.get("id")) == identity or
                    any(key(a.get("name")) == identity for a in v.get("leaderboardAliases", [])) for v in versions)):
            reason = "new-identity-collides-with-existing-version"
        if reason:
            pending.append({"modelFamilyId": fid, "modelName": label, "reason": reason, "evidence": records})
            continue
        a, b = sorted(pairs, key=lambda pair: tuple(sorted(p["sourceId"] for p in pair)))[0]
        a, b = sorted([a, b], key=lambda p: (p["sourceId"], p["sourceUrl"]))
        if version is None:
            version = {"id": vid, "name": label, "legacyIds": [], "leaderboardAliases": [],
                       "status": "官方发布 · 自动双源核验"}
            family.setdefault("versions", []).append(version)
            family["version"] = " / ".join(dict.fromkeys(v["name"] for v in family["versions"]))
        day = a["publishedAt"]
        version["releaseDate"] = day
        version["releaseUrl"] = a["sourceUrl"]
        version["releaseEvidence"] = {
            "eventId": "auto-" + hashlib.sha256(f"{fid}|{version['id']}|{day}".encode()).hexdigest()[:20],
            "publishedAt": day, "modelName": version["name"], "category": family["category"],
            "sourceUrl": a["sourceUrl"], "sourceName": a["sourceName"],
            "evidenceType": METHOD, "verificationMethod": METHOD, "verifiedAt": today.isoformat(),
            "sourceUpdateIds": [a["sourceUpdateId"], b["sourceUpdateId"]],
            "corroboratingSources": [a, b],
            "summary": "两条不同官方站点的明确发布标题及结构化发布日期一致；未自动推断许可或可用性。",
        }
        confirmed.append({"modelFamilyId": fid, "modelVersionId": version["id"], "eventId": version["releaseEvidence"]["eventId"]})
    return {"confirmed": confirmed, "pending": pending}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    def read(path):
        return json.loads((ROOT / path).read_text(encoding="utf-8"))
    models = read("site/data/models.json")
    today = datetime.now(timezone.utc).date()
    result = reconcile(models, read("site/data/model-updates.json")["items"],
                       read("config/model-sources.json"), read("site/data/model-monitor-status.json"),
                       read("config/chronicle-release-links.json")["vendorTopics"], today)
    if not args.dry_run:
        if result["confirmed"]:
            write_json(ROOT / "site/data/models.json", models)
        write_json(ROOT / "site/data/model-release-verification-status.json", {
            "checkedAt": datetime.now(timezone.utc).isoformat(), **result})
    print(json.dumps({"confirmed": len(result["confirmed"]), "pending": len(result["pending"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
