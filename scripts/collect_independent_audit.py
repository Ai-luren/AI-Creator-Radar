#!/usr/bin/env python3
"""Independent, pre-reconciliation repository observation coverage audit.

A repository is not necessarily a distinct product, usable weights, or release.
Never seed the sample with the model catalog or fixed release benchmark.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import urllib.request
from urllib.parse import urlencode

try:
    from scripts.collect_models import SameHostRedirect, USER_AGENT, write_json
    from scripts.collect_product_state import parse_stamp
except ModuleNotFoundError:
    from collect_models import SameHostRedirect, USER_AGENT, write_json
    from collect_product_state import parse_stamp

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site/data/independent-coverage.json"
AUTHORS = {"MiniMaxAI", "ByteDance-Seed", "Wan-AI"}
TASKS = {"text-generation","image-text-to-text","text-to-image","image-to-image",
         "text-to-video","image-to-video","image-text-to-video","video-to-video",
         "text-to-audio","text-to-speech","automatic-speech-recognition","audio-to-audio"}
MAX_BYTES = 4 * 1024 * 1024


def normalized(name):
    return re.sub(r"[\s_-]+", "", str(name or "").casefold().strip())


def exact_index(families, vendor_names):
    out = defaultdict(set)
    for family in families:
        if family.get("vendor") not in vendor_names:
            continue
        for version in family.get("versions", []):
            for name in [version.get("name"), (version.get("releaseEvidence") or {}).get("modelName")]:
                if name:
                    out[normalized(name)].add((family["id"], version["id"]))
    return out


def state_for(index, name):
    ids = sorted(index.get(normalized(name), set()))
    return ("exact-catalog-match" if len(ids)==1 else "ambiguous-identity" if ids else "unmatched-repository",
            [{"modelFamilyId": a, "modelVersionId": b} for a,b in ids])


def parse_rows(payload, author, now, days, limit):
    if not isinstance(payload, list) or not payload or len(payload)>limit:
        raise ValueError("Unexpected or empty repository response")
    recent, seen = [], set()
    all_dates = []
    for raw in payload:
        if not isinstance(raw, dict):
            raise ValueError("Invalid repository record")
        repo = raw.get("id") or raw.get("modelId")
        created = parse_stamp(raw.get("createdAt"))
        if (not isinstance(repo,str) or not re.fullmatch(r"[\w.-]+/[\w.-]+",repo)
                or repo.split("/",1)[0].casefold()!=author.casefold() or not created or created>now
                or repo.casefold() in seen):
            raise ValueError("Invalid repository identity or creation time")
        seen.add(repo.casefold())
        all_dates.append(created)
        if created >= now-timedelta(days=days):
            recent.append({"repositoryId":repo,"modelName":repo.split("/",1)[1],
                           "url":"https://huggingface.co/"+repo,"repositoryCreatedAt":created.isoformat(),
                           "pipelineTag":raw.get("pipeline_tag") if isinstance(raw.get("pipeline_tag"),str) else None})
    # A full page ending within the window does not establish complete coverage.
    return recent, len(payload)<limit or min(all_dates)<now-timedelta(days=days), len(payload)


def fetch(spec, config, now):
    author = spec["author"]
    if author not in AUTHORS:
        raise ValueError("Unapproved independent audit author")
    query = urlencode({"author":author,"sort":"createdAt","direction":-1,"limit":config["limitPerSource"]})
    url = "https://huggingface.co/api/models?"+query
    req = urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":USER_AGENT})
    with urllib.request.build_opener(SameHostRedirect()).open(req,timeout=15) as response:
        raw = response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:
        raise ValueError("Repository response too large")
    return parse_rows(json.loads(raw),author,now,config["windowDays"],config["limitPerSource"])


def audit(config, families, vendor_topics, previous, now, fetcher=fetch):
    if previous and previous.get("schema")!="independent-coverage/v1":
        raise ValueError("Unknown independent audit schema")
    stamp=now.isoformat(timespec="seconds")
    prev={s["author"]:s for s in previous.get("sources",[])}
    observations={r["id"]:r for r in previous.get("observations",[])}
    if len(observations)!=len(previous.get("observations",[])):
        raise ValueError("Duplicate independent observation")
    sources=[]
    indexes={spec["author"]:exact_index(families,set(vendor_topics[spec["vendorTopic"]])) for spec in config["sources"]}
    due=[]
    for spec in config["sources"]:
        old=prev.get(spec["author"],{})
        nxt=parse_stamp(old.get("nextAttemptAt"))
        if nxt and nxt>now:
            sources.append({**old,"deferred":True})
        else:
            due.append(spec)

    def probe(spec):
        try:
            return spec,fetcher(spec,config,now),None
        except (OSError,ValueError,TypeError) as exc:
            return spec,None,f"{type(exc).__name__}: {str(exc)[:160]}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(probe,due))
    for spec,result,error in results:
        author=spec["author"]
        old=prev.get(author,{})
        if error:
            count=int(old.get("consecutiveFailures",0))+1
            delay=min(1440,60*2**min(count,5))
            sources.append({**old,"author":author,"vendorTopic":spec["vendorTopic"],"checkedAt":stamp,
                            "lastSuccessAt":old.get("lastSuccessAt"),"error":error,"deferred":False,
                            "consecutiveFailures":count,"nextAttemptAt":(now+timedelta(minutes=delay)).isoformat()})
            continue
        recent,complete,scanned=result
        for row in recent:
            rid="holdout-"+hashlib.sha256((author+"|"+row["repositoryId"].casefold()).encode()).hexdigest()[:24]
            prior=observations.get(rid,{})
            state,matches=state_for(indexes[author],row["modelName"])
            # Preserve initial denominator and outcome, never rewrite after remediation.
            observations[rid]={**row,"id":rid,"author":author,"vendorTopic":spec["vendorTopic"],
                               "firstObservedAt":prior.get("firstObservedAt") or stamp,
                               "lastObservedAt":stamp,
                               "initialState":prior.get("initialState") or state,
                               "initialMatches":prior.get("initialMatches",matches),
                               "initialPipelineTag":prior.get("initialPipelineTag",row["pipelineTag"]),
                               "currentState":state,"currentMatches":matches}
        sources.append({"author":author,"vendorTopic":spec["vendorTopic"],"checkedAt":stamp,
                        "lastSuccessAt":stamp,"error":None,"deferred":False,"consecutiveFailures":0,
                        "nextAttemptAt":(now+timedelta(minutes=config["minIntervalMinutes"])).isoformat(),
                        "pageCoversWindow":complete,"scannedRepositories":scanned,"recentRepositories":len(recent)})
    # Re-evaluate existing observations against the catalog even during source outage.
    for row in observations.values():
        if row["author"] in indexes:
            state,matches=state_for(indexes[row["author"]],row["modelName"])
            row["currentState"],row["currentMatches"]=state,matches
    cutoff=now-timedelta(days=config["windowDays"])
    active=[r for r in observations.values() if r["author"] in indexes and parse_stamp(r["repositoryCreatedAt"])>=cutoff]
    in_scope=[r for r in active if r.get("initialPipelineTag") in TASKS]
    return {"schema":"independent-coverage/v1","checkedAt":stamp,
            "sources":sorted(sources,key=lambda s:s["author"]),
            "observations":sorted(observations.values(),key=lambda r:r["id"]),
            "summary":{"configuredSources":len(config["sources"]),
                       "successfulThisRun":sum(not s["deferred"] and not s["error"] for s in sources),
                       "sourcesWithSuccessfulObservation":sum(bool(s.get("lastSuccessAt")) for s in sources),
                       "sourcesWithCompleteLastPage":sum(s.get("pageCoversWindow") is True for s in sources),
                       "recentRepositories":len(active),"inScopeRepositorySamples":len(in_scope),
                       "initialStates":dict(sorted(Counter(r["initialState"] for r in in_scope).items())),
                       "currentStates":dict(sorted(Counter(r["currentState"] for r in in_scope).items())),
                       "unclassifiedPipeline":sum(r.get("initialPipelineTag") not in TASKS for r in active)},
            "policy":"Independent repository coverage sample, not release recall. Exact vendor/name matching only; unmatched may be checkpoints, aliases or out-of-catalog products. Initial outcome frozen; no automatic release, date or weights claim. Closed models not represented."}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run",action="store_true")
    p.add_argument("--report",type=Path)
    args=p.parse_args()
    def read(path,optional=False):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() or not optional else {}
    result=audit(read(ROOT/"config/independent-audit-sources.json"),read(ROOT/"site/data/models.json"),
                 read(ROOT/"config/chronicle-release-links.json")["vendorTopics"],read(OUTPUT,True),datetime.now(timezone.utc))
    print("Independent coverage:",json.dumps(result["summary"],ensure_ascii=False))
    for source in result["sources"]:
        print("[HOLDOUT]",source["author"],"recent=",source.get("recentRepositories"),"complete=",source.get("pageCoversWindow"),"error=",source["error"])
    if args.report:
        write_json(args.report,result)
    if not args.dry_run:
        write_json(OUTPUT,result)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
