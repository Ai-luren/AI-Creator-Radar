#!/usr/bin/env python3
"""Grade actual publisher observations by claim type without inferring first release.

The article's dated statement is itself a fact, but its date is not necessarily
the event date. Canonical release validation remains an independent gate.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

try:
    from scripts.collect_models import write_json
    from scripts.collect_release_recall import url_key, article_day_stamp
    from scripts.collect_verify_model_releases import host_for, key, release_name, STAGE_WARNING
    from scripts.collect_cross_platform import article_url
    from scripts.event_identity import identify, model_index, day, joint_title_identities
except ModuleNotFoundError:
    from collect_models import write_json
    from collect_release_recall import url_key, article_day_stamp
    from collect_verify_model_releases import host_for, key, release_name, STAGE_WARNING
    from collect_cross_platform import article_url
    from event_identity import identify, model_index, day, joint_title_identities

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site/data/event-claims.json"
DATE_KINDS = {"jsonld-datePublished", "feed-published", "article-explicit-date"}


def hash_record(row):
    return "claim-" + hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                               separators=(",", ":")).encode()).hexdigest()


def normalize_title(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).rstrip("!.！。")


def classify(title, name, summary=""):
    """Recognize narrow, explicit publisher wording. No inferred first-release date."""
    t = normalize_title(title)
    s = normalize_title(summary)
    n = r"[\s_-]+".join(re.escape(p) for p in re.split(r"[\s_-]+", name))
    product = r"([A-Za-z][A-Za-z0-9 ._-]{1,45})"
    flags = re.I
    # Require affirmative whole headlines; negated, future or mixed-stage
    # wording is not an explicit positive stage claim.
    if re.search(r"\b(?:not yet|no longer|will be|coming soon|planned|waitlist)\b|尚未|即将|计划", t, flags):
        return "article-publication", None
    if release_name(t) and key(release_name(t)) == key(name) and not STAGE_WARNING.search(s):
        return "explicit-release-statement", None
    patterns = (
        ("api-availability-statement", rf"{n} (?:is )?now available (?:via|in|through|on) (?:the )?API"),
        ("general-availability-statement", rf"{n} (?:is )?(?:now )?generally available"),
        ("preview-statement", rf"{n} (?:is )?(?:now )?available in (?:public |private )?(?:preview|beta|alpha|early access)"),
        ("announcement-statement", rf"(?:Introducing|Announcing|Meet) {n}"),
    )
    for kind, pattern in patterns:
        if re.fullmatch(pattern, t, flags):
            return kind, None
    match = re.fullmatch(rf"{n} (?:is )?now available in {product}", t, flags)
    if match and not STAGE_WARNING.search(match[1]) and not re.search(r"\b(?:api|preview|beta|alpha|access)\b", match[1], flags):
        return "service-availability-statement", match[1]
    # A product-specific "Meet X in Y" heading alone is not sufficient.
    # Require an affirmative same-product integration statement in its summary.
    match = re.fullmatch(rf"Meet {n} in {product}", t, flags)
    if match and not STAGE_WARNING.search(match[1]):
        service = re.escape(match[1])
        statement = rf"^{n}(?:,\s*[^,]{{1,90}},)?\s+is now integrated into {service}(?=\s*(?:[,.!?;]|and\b|$))"
        if re.search(statement, s, flags):
            return "service-integration-statement", match[1]
    return "article-publication", None


def allowed_for_source(source, url):
    host = host_for(url)
    endpoints = [source.get("url"), *source.get("fallbackUrls", []),
                 *(e.get("url") for e in source.get("fallbackEndpoints", []))]
    hosts = {host_for(u) for u in endpoints if u} | set(source.get("articleHosts", [])) | set(source.get("announcementHosts", []))
    return bool(host and host in hosts and url_key(url) and urlsplit(url).path.strip("/")
                and url_key(url) not in {url_key(u) for u in endpoints if u})


def collect_claims(families, updates, monitor, sources, resolution, allowed, previous, now):
    stamp = now.isoformat(timespec="seconds")
    if previous and previous.get("schema") != "event-claims/v1":
        raise ValueError("Unrecognized event claims schema")
    rows = {}
    for entry in previous.get("claims", []):
        fact = entry.get("fact")
        if not isinstance(fact, dict) or entry.get("id") != hash_record(fact) or entry["id"] in rows:
            raise ValueError("Invalid stored claim identity")
        rows[entry["id"]] = {**entry, "observedInInput": False, "currentSuccessfulObservation": False}
    initial = len(rows)
    index = model_index(families)
    versions = {(f["id"], v["id"]): v for f in families for v in f.get("versions", [])}
    configs = {s["id"]: s for s in sources}
    status = {s["id"]: s for s in monitor.get("sources", [])}
    today = now.date().isoformat()

    def add(title, summary, fid, url, article_stamp, observed, channel, ref, fresh):
        joint = joint_title_identities(index, title, fid)
        if joint:
            identities = joint["identities"]
        else:
            identities = [identify(index, title, family_id=fid)]
        for ident in identities:
            add_identity(ident, joint, title, summary, url, article_stamp, observed, channel, ref, fresh)

    def add_identity(ident, joint, title, summary, url, article_stamp, observed, channel, ref, fresh):
        d = day(article_day_stamp(article_stamp, url))
        observed_day = day(observed)
        if ident not in versions or not d or not observed_day or not d <= observed_day <= today or not url_key(url):
            return
        # A jointly introduced list establishes an announcement for each
        # member, never a release/availability date. Neutral lists only
        # establish article-publication. Preserve the actual original title.
        kind, service = ((joint["claimType"], None) if joint else
                         classify(title, versions[ident]["name"], summary))
        fact = {"modelFamilyId": ident[0], "modelVersionId": ident[1],
                "claimType": kind, "service": service, "publisherTitle": normalize_title(title),
                "sourceUrlKey": url_key(url), "articlePublishedAt": article_stamp,
                "publisherCalendarDay": d, "eventDate": None,
                "evidenceGrade": "official-dated-statement" if kind != "article-publication" else "official-article-date"}
        cid = hash_record(fact)
        prior = rows.get(cid, {})
        provenance = { (p["channel"], p["sourceRecordId"]): p for p in prior.get("provenance", []) }
        pkey = (channel, str(ref))
        old_proof = provenance.get(pkey, {})
        provenance[pkey] = {"channel": channel, "sourceRecordId": str(ref), "sourceUrl": url,
                            "firstObservedAt": min(observed, old_proof.get("firstObservedAt") or observed),
                            "lastObservedAt": max(observed, old_proof.get("lastObservedAt") or observed)}
        rows[cid] = {"id": cid, "fact": fact,
                     "firstObservedAt": min(observed, prior.get("firstObservedAt") or observed),
                     "lastSuccessfulObservationAt": max(observed, prior.get("lastSuccessfulObservationAt") or observed),
                     "observedInInput": True,
                     "currentSuccessfulObservation": bool(fresh or prior.get("currentSuccessfulObservation")),
                     "provenance": sorted(provenance.values(), key=lambda p: (p["channel"], p["sourceRecordId"]))}

    for item in updates:
        source = configs.get(item.get("sourceId"))
        state = status.get(item.get("sourceId"), {})
        if not source or not source.get("active") or source.get("official") is not True or item.get("official") is not True:
            continue
        if item.get("modelId") not in source.get("modelMatches", {}) or item.get("publicationDateKind") not in DATE_KINDS:
            continue
        observed = item.get("publicationObservedAt")
        if not observed or state.get("checkedAt") != observed or state.get("error") or not allowed_for_source(source, item.get("url")):
            continue
        # A merged item's date must match the raw source observation exactly.
        if not any(o.get("modelId") == item.get("modelId") and o.get("title") == item.get("title")
                   and o.get("publishedAt") == item.get("publishedAt") and url_key(o.get("url")) == url_key(item.get("url"))
                   for o in state.get("publicationObservations", [])):
            continue
        add(item["title"], item.get("summary", ""), item["modelId"], item["url"],
            item["publishedAt"], observed, "official-collector:" + source["id"], item.get("id"),
            not state.get("deferred") and observed == monitor.get("checkedAt"))

    for row in resolution.get("items", []):
        state = row.get("status")
        proof = row if state == "article-date-verified" else row.get("lastVerifiedObservation") if state == "fetch-failed" else None
        if not proof or not article_url(row.get("url"), allowed) or not proof.get("checkedAt"):
            continue
        # The recovered article title/date alone cannot prove body-level wording.
        add(proof.get("title"), "", proof.get("modelId"), row["url"], proof.get("articlePublishedAt"),
            proof["checkedAt"], "official-article-recovery", row.get("id"),
            state == "article-date-verified" and proof["checkedAt"] == resolution.get("checkedAt"))

    # A shared publisher URL with competing dates needs review; multiple different
    # articles about the same model are not necessarily conflicting release events.
    by_url = defaultdict(list)
    for row in rows.values():
        fact = row["fact"]
        by_url[(fact["modelFamilyId"], fact["modelVersionId"], fact["sourceUrlKey"])].append(row)
    conflicts = []
    for ident, observations in sorted(by_url.items()):
        dates = sorted({r["fact"]["publisherCalendarDay"] for r in observations})
        if len(dates) > 1:
            conflicts.append({"modelFamilyId": ident[0], "modelVersionId": ident[1],
                              "sourceUrlKey": ident[2], "articleDateCandidates": dates,
                              "claimIds": sorted(r["id"] for r in observations)})
    unresolved = set(cid for c in conflicts for cid in c["claimIds"])
    gap_candidates = []
    for row in rows.values():
        fact = row["fact"]
        version = versions.get((fact["modelFamilyId"], fact["modelVersionId"]), {})
        if fact["claimType"] == "explicit-release-statement" and not version.get("releaseEvidence") and row["id"] not in unresolved:
            gap_candidates.append(row["id"])
    return {"schema": "event-claims/v1", "checkedAt": stamp,
            "claims": sorted(rows.values(), key=lambda r: r["id"]),
            "articleDateConflicts": conflicts, "releaseStatementReviewCandidates": sorted(gap_candidates),
            "summary": {"claims": len(rows), "newClaims": len(rows)-initial,
                        "byType": dict(sorted(Counter(r["fact"]["claimType"] for r in rows.values()).items())),
                        "currentSuccessfulObservations": sum(r["currentSuccessfulObservation"] for r in rows.values()),
                        "articleDateConflicts": len(conflicts), "releaseStatementReviewCandidates": len(gap_candidates)},
            "policy": "Dated publisher statements only; observation and article dates are not inferred event dates. URL/channel duplicates do not count as independent proof. Existing canonical records are not used to manufacture source recall or changed by this shadow layer."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--resolution", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    directory = ROOT / "site/data"
    def read(path, optional=False):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() or not optional else {}
    if args.probe:
        probe = read(args.probe)
        updates, monitor = probe["items"], probe["status"]
    else:
        updates, monitor = read(directory / "model-updates.json")["items"], read(directory / "model-monitor-status.json")
    result = collect_claims(read(directory / "models.json"), updates, monitor, read(ROOT / "config/model-sources.json"),
                            read(args.resolution or directory / "lead-resolution.json"),
                            read(ROOT / "config/cross-platform-sources.json")["officialArticleHosts"],
                            read(OUTPUT, optional=True), datetime.now(timezone.utc))
    try:
        from scripts.publisher_statement_recovery import collect_statements
    except ModuleNotFoundError:
        from publisher_statement_recovery import collect_statements
    result["publisherStatements"] = collect_statements(result["claims"], read(directory / "models.json"),
                                                       read(OUTPUT, optional=True).get("publisherStatements", {}),
                                                       datetime.now(timezone.utc))
    print("Publisher statements:", json.dumps(result["publisherStatements"], ensure_ascii=False))
    print("Event claims:", json.dumps(result["summary"], ensure_ascii=False))
    if args.report:
        write_json(args.report, result)
    if not args.dry_run:
        write_json(OUTPUT, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
