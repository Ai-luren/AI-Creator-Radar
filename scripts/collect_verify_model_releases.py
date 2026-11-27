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
    "kling": r"Kling \d+(?:\.\d+){0,2}",
    "kling-image": r"Kling Image \d+(?:\.\d+){0,2}",
    "veo": r"Veo \d+(?:\.\d+){0,2}",
    "vidu": r"Vidu \d+(?:\.\d+){0,2}",
    "qwen-image": r"Qwen-Image \d+(?:\.\d+){0,2}",
    "midjourney": r"Midjourney V?\d+(?:\.\d+){0,2}",
    "suno": r"Suno V?\d+(?:\.\d+){0,2}",
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


def independent_article_pair(a, b):
    """Different hostnames alone do not make mirrored articles independent."""
    first, second = urlsplit(a["sourceUrl"]), urlsplit(b["sourceUrl"])
    if first.hostname.removeprefix("www.") == second.hostname.removeprefix("www."):
        return False
    def path_identity(p):
        return re.sub(r"^/(?:en|zh|cn|ja|en-us|zh-cn)(?=/)", "", p.path.casefold()).rstrip("/")
    return (a["sourceId"] != b["sourceId"] and a["sourceUpdateId"] != b["sourceUpdateId"]
            and a["sourceUrl"] != b["sourceUrl"]
            and path_identity(first) != path_identity(second))


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
    if "publicationObservations" in status and not any(
            o.get("modelId") == item.get("modelId") and o.get("title") == item.get("title")
            and o.get("publishedAt") == item.get("publishedAt") and normalize_url(o.get("url") or "") == normalize_url(item.get("url") or "")
            for o in status["publicationObservations"]):
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


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def proof_key(proof):
    return fingerprint({k: v for k, v in proof.items() if k != "observedAt"})


def ledger_record(fid, proof, source):
    data = {"modelFamilyId": fid, "proof": proof, "sourceConfigHash": fingerprint(source)}
    return {"id": fingerprint(data), **data, "quarantineReason": None}


def prior_eligible(entry, source, family, vendor_group, today):
    proof = entry["proof"]
    if (entry.get("quarantineReason") or not source or source.get("active") is not True
            or source.get("official") is not True or not family
            or entry["sourceConfigHash"] != fingerprint(source)
            or entry["modelFamilyId"] not in source.get("modelMatches", {})):
        return False
    vendor = vendor_group.get(str(family.get("vendor", "")).casefold())
    if not vendor or vendor_group.get(str(source.get("vendor", "")).casefold()) != vendor:
        return False
    try:
        published = date.fromisoformat(proof["publishedAt"])
        observed = datetime.fromisoformat(proof["observedAt"].replace("Z", "+00:00"))
    except (ValueError, TypeError, KeyError, AttributeError):
        return False
    endpoints = [source["url"], *source.get("fallbackUrls", [])]
    allowed = {host_for(u) for u in endpoints} | set(source.get("announcementHosts", []))
    return (today - timedelta(days=29) <= published <= today
            and observed.tzinfo is not None and published <= observed.date() <= today
            and proof.get("publicationDateKind") in DATE_KINDS
            and bool(proof.get("sourceUpdateId")) and bool(release_name(proof.get("title")))
            and key(release_name(proof["title"])) == key(proof.get("modelName"))
            and host_for(proof.get("sourceUrl")) in allowed and bool(host_for(proof.get("sourceUrl")))
            and proof["sourceUrl"] not in {normalize_url(u) for u in endpoints})


def reconcile(families, updates, sources, status, vendor_topics, today, previous=None):
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

    # Persist only source-validated, structured-date observations. A later
    # independent article may corroborate an earlier one even if its origin
    # is temporarily offline. A retained record never becomes a fresh read.
    ledger = {}
    current_keys = set()
    if previous is not None:
        if previous.get("proofLedgerSchema") not in (None, "release-proof-ledger/v1"):
            raise ValueError("Unknown release proof ledger schema")
        for record in previous.get("proofLedger", []):
            body = {k: record[k] for k in ("modelFamilyId", "proof", "sourceConfigHash")}
            if record.get("id") != fingerprint(body) or record["id"] in ledger:
                raise ValueError("Invalid stored release proof")
            ledger[record["id"]] = dict(record)
        # A genuinely newer observation of the same publisher article with
        # incompatible wording/date quarantines prior proof, even if the new
        # observation itself is not a qualifying release statement.
        for record in ledger.values():
            proof = record["proof"]
            state = source_status.get(proof["sourceId"], {})
            checked = state.get("checkedAt")
            if state.get("error") or state.get("deferred") or not checked:
                continue
            try:
                newer = datetime.fromisoformat(checked.replace("Z", "+00:00")) > datetime.fromisoformat(proof["observedAt"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                newer = False
            if not newer:
                continue
            for obs in state.get("publicationObservations", []):
                if normalize_url(obs.get("url") or "") != proof["sourceUrl"]:
                    continue
                if (obs.get("modelId") != record["modelFamilyId"]
                        or obs.get("title") != proof["title"]
                        or str(obs.get("publishedAt") or "")[:10] != proof["publishedAt"]):
                    record["quarantineReason"] = "later-publisher-observation-conflict"
                    break
        captured = {(r["modelFamilyId"], proof_key(r["proof"]), r["sourceConfigHash"]): r
                    for r in ledger.values() if not r.get("quarantineReason")}
        for identity, proofs in list(groups.items()):
            for proof in proofs:
                state = source_status[proof["sourceId"]]
                # Legacy cached rows are insufficient for future cross-run use.
                if ("publicationObservations" not in state or state.get("deferred")
                        or (status.get("checkedAt") and state.get("checkedAt") != status["checkedAt"])):
                    continue
                source = source_by_id[proof["sourceId"]]
                record = ledger_record(identity[0], proof, source)
                match = (identity[0], proof_key(proof), record["sourceConfigHash"])
                if match not in captured:
                    ledger[record["id"]] = record
                    captured[match] = record
                current_keys.add((identity, proof_key(proof)))
        for record in ledger.values():
            proof = record["proof"]
            fid = record["modelFamilyId"]
            identity = (fid, key(proof["modelName"]))
            if identity not in groups or not any(k[0] == identity for k in current_keys):
                continue
            source = source_by_id.get(proof["sourceId"])
            if not prior_eligible(record, source, fam_by_id.get(fid), vendor_group, today):
                continue
            # The old proof may not override a conflicting current date.
            if all(proof_key(p) != proof_key(proof) for p in groups[identity]):
                groups[identity].append(proof)
            conflicts[identity].add(proof["publishedAt"])
        # Never choose between a quarantined assertion and a fresh assertion
        # for the same model without an explicit correction review.
        for record in ledger.values():
            if record.get("quarantineReason"):
                proof = record["proof"]
                identity = (record["modelFamilyId"], key(proof["modelName"]))
                if identity in groups:
                    conflicts[identity].add("quarantined-publisher-observation")
    confirmed, pending = [], []
    for (fid, identity), records in sorted(groups.items()):
        family = fam_by_id[fid]
        label = records[0]["modelName"]
        dates = {p["publishedAt"] for p in records}
        pairs = [(a, b) for i, a in enumerate(records) for b in records[i+1:]
                 if independent_article_pair(a, b)]
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
        numeric_suffix = re.search(r"\d+(?:\.\d+)*$", label)
        short_identity = key(numeric_suffix.group(0)) if numeric_suffix else ""
        if not version and (not vid or any(v.get("id") == vid or key(v.get("id")) in {identity, short_identity}
                    or key(v.get("name")) in {identity, short_identity}
                    or any(key(a.get("name")) in {identity, short_identity} for a in v.get("leaderboardAliases", [])) for v in versions)):
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
    result = {"confirmed": confirmed, "pending": pending}
    if previous is not None:
        result.update({"proofLedgerSchema": "release-proof-ledger/v1",
                       "proofLedger": sorted(ledger.values(), key=lambda r: r["id"]),
                       "proofLedgerSummary": {"records": len(ledger),
                                              "quarantined": sum(bool(r.get("quarantineReason")) for r in ledger.values()),
                                              "currentValidatedProofs": len(current_keys)}})
    return result



def automatic_evidence_valid(family, version):
    """Validate stored automatic proof, without requiring the source to remain online."""
    evidence = version.get("releaseEvidence") or {}
    if evidence.get("verificationMethod") != METHOD:
        return evidence.get("evidenceType") != METHOD
    proofs = evidence.get("corroboratingSources")
    if not isinstance(proofs, list) or len(proofs) != 2 or not all(isinstance(p, dict) for p in proofs):
        return False
    a, b = proofs
    try:
        day = date.fromisoformat(evidence["publishedAt"])
        verified = date.fromisoformat(evidence["verifiedAt"])
        if not day <= verified:
            return False
    except (KeyError, TypeError, ValueError):
        return False
    if (evidence.get("evidenceType") != METHOD or version.get("releaseDate") != day.isoformat()
            or version.get("recordKind") or version.get("historicalMilestones")
            or evidence.get("modelName") != version.get("name")
            or evidence.get("category") != family.get("category")
            or evidence.get("sourceUrl") != a.get("sourceUrl")
            or evidence.get("sourceUpdateIds") != [a.get("sourceUpdateId"), b.get("sourceUpdateId")]
            or not evidence.get("eventId")):
        return False
    if (not a.get("sourceId") or not b.get("sourceId") or a["sourceId"] == b["sourceId"]
            or not a.get("sourceUpdateId") or not b.get("sourceUpdateId") or a["sourceUpdateId"] == b["sourceUpdateId"]
            or not host_for(a.get("sourceUrl")) or not host_for(b.get("sourceUrl"))
            or not independent_article_pair(a, b)):
        return False
    return all(p.get("publicationDateKind") in DATE_KINDS and p.get("observedAt")
               and p.get("publishedAt") == day.isoformat()
               and key(release_name(p.get("title"))) == key(version["name"])
               and key(p.get("modelName")) == key(version["name"]) for p in proofs)


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
                       read("config/chronicle-release-links.json")["vendorTopics"], today,
                       read("site/data/model-release-verification-status.json")
                       if (ROOT / "site/data/model-release-verification-status.json").exists() else {})
    if not args.dry_run:
        if result["confirmed"]:
            write_json(ROOT / "site/data/models.json", models)
        write_json(ROOT / "site/data/model-release-verification-status.json", {
            "checkedAt": datetime.now(timezone.utc).isoformat(), **result})
    print(json.dumps({"confirmed": len(result["confirmed"]), "pending": len(result["pending"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
