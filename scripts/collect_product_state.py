#!/usr/bin/env python3
"""Observe public product catalogs independently of news pages.

Catalog listings and changes are not official model releases. No inference calls.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request

try:
    from scripts.collect_models import SameHostRedirect, USER_AGENT, write_json
    from scripts.event_identity import identify, model_index
except ModuleNotFoundError:
    from collect_models import SameHostRedirect, USER_AGENT, write_json
    from event_identity import identify, model_index

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site/data/product-state.json"
MAX_BYTES = 24 * 1024 * 1024
ALLOWED_ENDPOINTS = {
    "models-dev": {"https://models.dev/api.json"},
    "openrouter": {"https://openrouter.ai/api/v1/models", "https://openrouter.ai/api/v1/images/models"},
}
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,199}")
DATE_RE = re.compile(r"\d{4}-\d{2}(?:-\d{2})?")


def stable_id(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def metadata_date(value):
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        return None
    try:
        datetime.fromisoformat(value + "-01" if len(value) == 7 else value)
    except ValueError:
        return None
    return value


def parse_catalog(body, source):
    payload = json.loads(body)
    provider_ids = set(source["providerIds"])
    rows = {}

    def add(provider, mid, name, release_date=None, created=None):
        if not isinstance(mid, str) or not ID_RE.fullmatch(mid) or not isinstance(name, str) or not name.strip():
            raise ValueError("Invalid catalog model identity")
        key = provider + "|" + mid
        if key in rows:
            raise ValueError("Duplicate catalog model identity")
        row = {"providerId": provider, "productId": mid, "name": name.strip()[:200]}
        if (reported := metadata_date(release_date)):
            row["reportedReleaseDate"] = reported
        if type(created) is int and 0 < created < 4102444800:
            row["providerRecordCreatedAt"] = datetime.fromtimestamp(created, timezone.utc).isoformat()
        rows[key] = row

    if source["type"] == "models-dev":
        if not isinstance(payload, dict):
            raise ValueError("Unexpected Models.dev schema")
        for pid in sorted(provider_ids & payload.keys()):
            provider = payload[pid]
            if not isinstance(provider, dict) or not isinstance(provider.get("models"), dict):
                raise ValueError("Unexpected Models.dev provider schema")
            for mid, model in provider["models"].items():
                if not isinstance(model, dict) or model.get("id", mid) != mid:
                    raise ValueError("Unexpected Models.dev model schema")
                add(pid, mid, model.get("name") or mid, model.get("release_date"))
    elif source["type"] == "openrouter":
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("Unexpected OpenRouter schema")
        for item in payload["data"]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise ValueError("Unexpected OpenRouter model schema")
            mid = item["id"]
            pid = mid.split("/", 1)[0]
            if pid in provider_ids and "/" in mid:
                add(pid, mid, item.get("name") or mid, created=item.get("created"))
    else:
        raise ValueError("Unknown product source type")
    if len(rows) < source["minRows"] or len(rows) > 10000:
        raise ValueError("Catalog coverage outside configured bounds")
    return rows


def fetch(source):
    if source["url"] not in ALLOWED_ENDPOINTS.get(source["type"], set()):
        raise ValueError("Unapproved product endpoint")
    req = urllib.request.Request(source["url"], headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.build_opener(SameHostRedirect()).open(req, timeout=15) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Catalog exceeds size limit")
    return parse_catalog(raw, source)


def parse_stamp(value):
    try:
        dt = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return dt if dt.tzinfo else None
    except ValueError:
        return None


def observe(config, previous, families, now, fetcher=fetch):
    if previous and previous.get("schema") != "product-state/v1":
        raise ValueError("Unknown product state schema")
    stamp = now.isoformat(timespec="seconds")
    old = {s["id"]: s for s in previous.get("sources", [])}
    if len(old) != len(previous.get("sources", [])):
        raise ValueError("Duplicate prior source")
    index = model_index(families)
    sources, events = [], []
    for spec in config["sources"]:
        sid = spec["id"]
        prior = old.get(sid, {})
        # A changed scope is a new baseline, not a mass delisting.
        scope = stable_id(spec["type"], spec["url"], sorted(spec["providerIds"]))
        same = prior.get("scope") == scope
        if same:
            next_at = parse_stamp(prior.get("nextAttemptAt"))
            if next_at and now < next_at:
                sources.append({**prior, "deferred": True})
                continue
        else:
            prior = {}
        existing = prior.get("entries", {})
        try:
            fresh = fetcher(spec)
            if not isinstance(fresh, dict) or len(fresh) < spec["minRows"]:
                raise ValueError("Missing or incomplete catalog")
            # Refuse suspicious truncation rather than interpreting it as removals.
            present = {k for k, v in existing.items() if v.get("missingChecks", 0) < 2}
            if present and len(set(fresh) & present) < 0.8 * len(present):
                raise ValueError("Large catalog disappearance; retain last good snapshot")
        except (OSError, ValueError, TypeError) as exc:
            failures = int(prior.get("consecutiveFailures", 0)) + 1
            delay = min(720, 30 * 2 ** min(failures, 5))
            sources.append({**prior, "id": sid, "scope": scope, "url": spec["url"],
                            "attribution": spec["attribution"], "entries": existing,
                            "checkedAt": stamp, "lastSuccessAt": prior.get("lastSuccessAt"),
                            "error": f"{type(exc).__name__}: {str(exc)[:160]}",
                            "deferred": False, "consecutiveFailures": failures,
                            "nextAttemptAt": (now + timedelta(minutes=delay)).isoformat()})
            continue
        baseline = not prior.get("lastSuccessAt")
        entries = {}
        def event(kind, key, row, old_row=None):
            ident = identify(index, row["name"])
            events.append({"id": stable_id(sid, scope, kind, key, stamp), "sourceId": sid,
                           "sourceUrl": spec["url"], "attribution": spec["attribution"],
                           "eventType": kind, "observedAt": stamp, "productKey": key,
                           "product": row, "previousProduct": old_row,
                           "identity": {"modelFamilyId": ident[0], "modelVersionId": ident[1]} if ident else None,
                           "claimType": "catalog-observation"})
        for key, row in sorted(fresh.items()):
            before = existing.get(key)
            first_seen = before.get("firstSeenAt") if before else stamp
            entries[key] = {"product": row, "firstSeenAt": first_seen, "missingChecks": 0}
            if baseline:
                reported = row.get("reportedReleaseDate", "")
                if len(reported) == 10 and (now-timedelta(days=29)).date().isoformat() <= reported <= now.date().isoformat():
                    event("baseline-recent-reported-date", key, row)
            elif before is None:
                event("added-to-catalog", key, row)
            elif before.get("missingChecks", 0) >= 2:
                event("reappeared-in-catalog", key, row)
            elif before.get("product") != row:
                event("catalog-metadata-changed", key, row, before.get("product"))
        for key in sorted(existing.keys() - fresh.keys()):
            before = existing[key]
            misses = min(2, int(before.get("missingChecks", 0)) + 1)
            entries[key] = {**before, "missingChecks": misses}
            if misses == 2 and before.get("missingChecks", 0) < 2:
                event("absent-from-catalog", key, before["product"])
        sources.append({"id": sid, "scope": scope, "url": spec["url"], "attribution": spec["attribution"],
                        "entries": entries, "checkedAt": stamp, "lastSuccessAt": stamp,
                        "error": None, "deferred": False, "consecutiveFailures": 0,
                        "nextAttemptAt": (now + timedelta(minutes=spec["minIntervalMinutes"])).isoformat(),
                        "baselineInitializedAt": prior.get("baselineInitializedAt") or stamp})
    # Retain recent delta events; the reconciliation task ledger persists unresolved work.
    retained = {r["id"]: r for r in previous.get("events", [])}
    retained.update({r["id"]: r for r in events})
    cutoff = (now - timedelta(days=45)).isoformat()
    retained = [r for r in retained.values() if r["observedAt"] >= cutoff]
    return {"schema": "product-state/v1", "checkedAt": stamp, "sources": sources,
            "events": sorted(retained, key=lambda r: (r["observedAt"], r["id"]), reverse=True),
            "summary": {"configuredSources": len(config["sources"]),
                        "sourcesWithBaseline": sum(bool(s.get("lastSuccessAt")) for s in sources),
                        "successfulThisRun": sum(not s["deferred"] and not s["error"] for s in sources),
                        "newEvents": len(events), "retainedEvents": len(retained),
                        "listedEntries": sum(sum(v.get("missingChecks", 0) == 0 for v in s["entries"].values()) for s in sources)},
            "policy": "Public catalog observations only; never equate provider creation, reported metadata, first observation, addition or absence with formal launch, availability or withdrawal."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))
    result = observe(read(ROOT / "config/product-state-sources.json"), read(OUTPUT) if OUTPUT.exists() else {},
                     read(ROOT / "site/data/models.json"), datetime.now(timezone.utc))
    print("Product state:", json.dumps(result["summary"], ensure_ascii=False))
    for source in result["sources"]:
        print("[PRODUCT]", source["id"], "entries=", len(source["entries"]), "error=", source["error"], "deferred=", source["deferred"])
    if args.report:
        write_json(args.report, result)
    if not args.dry_run:
        write_json(OUTPUT, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
