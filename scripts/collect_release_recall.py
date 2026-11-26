#!/usr/bin/env python3
"""Score independently curated release samples against collector output."""
from __future__ import annotations
import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

try:
    from scripts.collect_models import write_json, non_release_title
except ModuleNotFoundError:
    from collect_models import write_json, non_release_title

ROOT = Path(__file__).resolve().parents[1]
TRACKING = {"tab", "view_from", "trk", "source", "lang", "ref", "fbclid", "gclid"}


def url_key(value):
    try:
        p = urlsplit(value or "")
        if p.scheme != "https" or not p.hostname:
            return ""
        query = sorted((k, v) for k, v in parse_qsl(p.query) if k.casefold() not in TRACKING and not k.casefold().startswith("utm_"))
        return urlunsplit(("https", p.netloc.lower(), p.path.rstrip("/") or "/", urlencode(query), ""))
    except ValueError:
        return ""


def identity(value):
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def assess(benchmark, updates, status, digest, today, recovery=None):
    source_states = {s["id"]: s for s in status.get("sources", [])}
    checked = status.get("checkedAt")
    recovery = recovery or {}
    rows = []
    for event in benchmark["events"]:
        family, day = event["modelFamilyId"], event["eventDate"]
        urls = {url_key(u) for u in event["sourceUrls"]}
        same_article = [u for u in updates if url_key(u.get("url")) in urls and u.get("official") is True]
        matched = [u for u in same_article if u.get("modelId") == family
                   and not non_release_title(u.get("title"))
                   and all(re.search(p, str(u.get("title") or ""), re.I) for p in event["titlePatterns"])]
        dated = [u for u in matched if str(u.get("publishedAt") or "")[:10] == day]
        current = [u for u in dated if checked and u.get("lastSeenAt") == checked
                   and source_states.get(u.get("sourceId"), {}).get("checkedAt") == checked
                   and not source_states[u["sourceId"]].get("error")]
        actual_dates = sorted({str(u.get("publishedAt"))[:10] for u in matched if u.get("publishedAt")})
        confirmed = {identity(x.get("modelName")) for x in digest.get("items", [])
                     if x.get("modelFamilyId") == family and str(x.get("publishedAt") or "")[:10] == day
                     and url_key(x.get("url")) in urls}
        outcome = ("current-dated" if current else "retained-dated-only" if dated else
                   "date-mismatch" if matched and actual_dates else "undated" if matched else
                   "identity-mismatch" if same_article else "not-discovered")
        recovered = [p for row in recovery.get("items", []) if url_key(row.get("url")) in urls
                     for p in [row if row.get("status") == "article-date-verified" else row.get("lastVerifiedObservation") or {}]
                     if p.get("modelId") == family and str(p.get("articlePublishedAt") or "")[:10] == day
                     and all(re.search(pattern, str(p.get("title") or ""), re.I) for pattern in event["titlePatterns"])]
        first_days = [str(p.get("firstVerifiedAt") or "")[:10] for p in recovered if p.get("firstVerifiedAt")]
        lag = (datetime.fromisoformat(min(first_days)).date() - datetime.fromisoformat(day).date()).days if first_days else None
        rows.append({"id": event["id"], "modelFamilyId": family, "eventDate": day,
                     "recoveredDated": bool(recovered), "endToEndDated": bool(dated or recovered),
                     "recoveryFirstVerifiedLagDays": lag if lag is not None and lag >= 0 else None,
                     "modelNames": event["modelNames"], "sourceUrls": event["sourceUrls"],
                     "outcome": outcome, "actualDates": actual_dates,
                     "dateConflict": any(d != day for d in actual_dates),
                     "currentDated": bool(current), "retainedDated": bool(dated),
                     "discovered": bool(matched),
                     "canonicalComplete": all(identity(n) in confirmed for n in event["modelNames"]),
                     "matchingUpdateIds": sorted({u["id"] for u in matched if u.get("id")}),
                     "within30Days": (today-timedelta(days=29)).isoformat() <= day <= today.isoformat()})
    def counts(rows):
        return {"events": len(rows), "discovered": sum(r["discovered"] for r in rows),
                "retainedDated": sum(r["retainedDated"] for r in rows),
                "currentDated": sum(r["currentDated"] for r in rows),
                "recoveredDated": sum(r["recoveredDated"] for r in rows),
                "endToEndDated": sum(r["endToEndDated"] for r in rows),
                "canonicalComplete": sum(r["canonicalComplete"] for r in rows),
                "dateConflicts": sum(r["dateConflict"] for r in rows)}
    negatives = []
    for case in benchmark.get("negativeControls", []):
        urls = {url_key(u) for u in case["sourceUrls"]}
        pending = [p["id"] for p in digest.get("pending", []) if url_key(p.get("url")) in urls]
        false_confirmed = [p["id"] for p in digest.get("items", []) if url_key(p.get("url")) in urls
                           and (not case.get("dateConflict") or str(p.get("publishedAt"))[:10] == case["dateConflict"][-1])]
        negatives.append({"id": case["id"], "note": case["note"], "pendingIds": pending,
                          "incorrectConfirmedIds": false_confirmed})
    return {"sampleReviewedAt": benchmark["reviewedAt"], "sampleScope": benchmark["scope"],
            "collectorCheckedAt": checked, "allSample": counts(rows),
            "recoveryCheckedAt": recovery.get("checkedAt"), "recoverySummary": recovery.get("summary", {}),
            "activeWindow": counts([r for r in rows if r["within30Days"]]),
            "events": rows, "negativeControls": negatives}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--probe", type=Path)
    args = parser.parse_args()
    def read(p):
        return json.loads((ROOT / p).read_text(encoding="utf-8"))
    if args.probe:
        probe = json.loads(args.probe.read_text(encoding="utf-8"))
        items, status = probe["items"], probe["status"]
    else:
        items = read("site/data/model-updates.json")["items"]
        status = read("site/data/model-monitor-status.json")
    now = datetime.now(timezone.utc)
    recovery_path = ROOT / "site/data/lead-resolution.json"
    recovery = json.loads(recovery_path.read_text(encoding="utf-8")) if recovery_path.exists() and not args.probe else {}
    result = assess(read("config/release-recall-benchmark.json"), items, status,
                    read("site/data/model-releases-30d.json"), now.date(), recovery)
    print("Release sample recall:", json.dumps(result["allSample"], ensure_ascii=False))
    for row in result["events"]:
        print(f"[RECALL] {row['id']}: {row['outcome']}; dates={row['actualDates']}; canonical={row['canonicalComplete']}")
    for case in result["negativeControls"]:
        print(f"[CONTROL] {case['id']}: pending={len(case['pendingIds'])}, incorrect confirmed={len(case['incorrectConfirmedIds'])}")
    if not args.dry_run and not args.probe:
        write_json(ROOT / "site/data/release-recall-status.json", {"checkedAt": now.isoformat(), **result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
