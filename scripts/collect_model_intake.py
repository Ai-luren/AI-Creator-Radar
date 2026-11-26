#!/usr/bin/env python3
"""Stage previously unknown model identities without fabricating canonical versions."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
try:
    from scripts.collect_verify_model_releases import release_name, key
    from scripts.collect_release_recall import article_day_stamp, url_key
    from scripts.collect_models import write_json
except ModuleNotFoundError:
    from collect_verify_model_releases import release_name, key
    from collect_release_recall import article_day_stamp, url_key
    from collect_models import write_json

ROOT=Path(__file__).resolve().parents[1]

def candidate_name(title):
    if release_name(title):
        return release_name(title)
    match = re.fullmatch(r"(?:Introducing|Announcing|Meet)\s+([A-Za-z][A-Za-z0-9 ._-]{2,75})[.!]?", str(title or ""), re.I)
    name = match.group(1).strip().rstrip(".") if match else ""
    if not re.search(r"\d", name) or re.search(r"\b(?:api|update|guide|preview|beta|pricing|feature|benchmark|research|tutorial)\b",name,re.I):
        return None
    return name

def stage(families, resolution, discovery, now):
    known = {f["id"]: {key(v.get("name")) for v in f.get("versions", [])} for f in families}
    # Treat alternate version names as existing, not as a new identity.
    for f in families:
        for v in f.get("versions", []):
            for alias in v.get("leaderboardAliases", []):
                if isinstance(alias,dict) and alias.get("name"):
                    known[f["id"]].add(key(alias["name"]))
            if (v.get("releaseEvidence") or {}).get("modelName"):
                known[f["id"]].add(key(v["releaseEvidence"]["modelName"]))
    cutoff=(now-timedelta(days=29)).date().isoformat()
    today=now.date().isoformat()
    candidates={}
    for row in resolution.get("items", []):
        if row.get("status") not in {"article-date-verified","family-unresolved"}:
            continue
        name=candidate_name(row.get("title"))
        url=row.get("url")
        day=str(article_day_stamp(row.get("articlePublishedAt"),url) or "")[:10]
        fid=row.get("modelId")
        if not name or not cutoff<=day<=today or not url_key(url):
            continue
        if fid and key(name) in known.get(fid,set()):
            continue
        if not fid and any(key(name) in names for names in known.values()):
            continue
        identity=(fid or "unclassified",key(name))
        record=candidates.setdefault(identity,{"id":"intake-"+hashlib.sha256(repr(identity).encode()).hexdigest()[:16],
            "modelName":name,"modelFamilyId":fid,"status":"needs-family-classification" if not fid else "needs-version-verification",
            "articleDates":[],"officialArticleUrls":[],"proofIds":[]})
        record["articleDates"]=sorted(set(record["articleDates"]+[day]))
        record["officialArticleUrls"]=sorted(set(record["officialArticleUrls"]+[url]))
        record["proofIds"]=sorted(set(record["proofIds"]+[row["id"]]))
    for record in candidates.values():
        if len(record["articleDates"])>1:
            record["status"]="publication-date-conflict"
    items=sorted(candidates.values(),key=lambda x:(x["articleDates"][-1],x["id"]),reverse=True)
    # Repo uploads and external leads remain in the existing discovery file.
    return {"schema":"model-intake/v1","checkedAt":now.isoformat(),"items":items,
            "summary":{"candidateIdentities":len(items),
                       "unclassifiedFamilies":sum(not r["modelFamilyId"] for r in items),
                       "knownFamilyNewVersions":sum(bool(r["modelFamilyId"]) for r in items),
                       "externalUnverifiedLeads":sum(not r.get("officialArticleUrls") for r in discovery.get("items",[]))},
            "policy":"Automatic staging only. No inferred release date, model category, license, availability, or new canonical family."}

def main():
    p=argparse.ArgumentParser();p.add_argument("--dry-run",action="store_true");p.add_argument("--resolution",type=Path)
    a=p.parse_args()
    def read(path,default=None):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    result=stage(read(ROOT/"site/data/models.json",[]),read(a.resolution or ROOT/"site/data/lead-resolution.json",{}),
                 read(ROOT/"site/data/cross-platform-discovery.json",{}),datetime.now(timezone.utc))
    print("Model intake:",json.dumps(result["summary"],ensure_ascii=False))
    for row in result["items"]: print("[INTAKE]",row["modelName"],row["status"],row["articleDates"])
    if not a.dry_run: write_json(ROOT/"site/data/model-intake.json",result)
    return 0
if __name__=="__main__":raise SystemExit(main())
