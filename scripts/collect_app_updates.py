#!/usr/bin/env python3
"""Observe first-party creative app surfaces; never infer formal model launch."""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import urllib.request

try:
    from scripts.collect_models import SameHostRedirect, USER_AGENT, write_json
    from scripts.collect_product_state import parse_stamp
except ModuleNotFoundError:
    from collect_models import SameHostRedirect, USER_AGENT, write_json
    from collect_product_state import parse_stamp

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"site/data/app-updates.json"
MAX_BYTES=6*1024*1024
ALLOWED={"https://jimeng.jianying.com/ai-tool/home"}
VOID={"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"}

class VisibleText(HTMLParser):
    """Conservative server-rendered text only, not bundled JS or hidden fields."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]
        self.parts=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        hidden=(tag in {"script","style","template","noscript","head","svg"} or "hidden" in attrs
                or attrs.get("aria-hidden")=="true" or bool(re.search(r"display\s*:\s*none|visibility\s*:\s*hidden",attrs.get("style") or "",re.I)))
        if tag not in VOID:
            self.stack.append((tag,hidden or any(v for _,v in self.stack)))
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:
            self.handle_endtag(tag)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                del self.stack[i:]
                break
    def handle_data(self,data):
        if not any(v for _,v in self.stack):
            self.parts.append(data)

def parse_surface(page,source):
    p=VisibleText()
    p.feed(page)
    p.close()
    text=" ".join(" ".join(p.parts).split())
    if not all(a in text for a in source["anchors"]):
        raise ValueError("Expected app navigation absent; login, client-rendered shell or changed template")
    prefixes="|".join(re.escape(p) for p in source["modelPrefixes"])
    pattern=rf"(?<![A-Za-z0-9_.-])({prefixes})\s*(\d+(?:\.\d+)+)(?![\d.]|[-_][A-Za-z0-9])"
    labels={}
    for m in re.finditer(pattern,text,re.I):
        tail=text[m.end():]
        # Variant suffixes must not be silently reduced to a base model.
        if re.match(r"\s+(?:pro|lite|fast|mini|plus|preview|turbo|ultra|vip)\b",tail,re.I):
            continue
        prefix=next(x for x in source["modelPrefixes"] if x.casefold()==m[1].casefold())
        name=prefix+" "+m[2]
        key=name.casefold().replace(" ","")
        labels[key]={"modelName":name,"category":"audio" if prefix.casefold()=="seedaudio" else "video" if prefix.casefold()=="seedance" else "image",
                     "claimType":"first-party-visible-label"}
    if not labels:
        raise ValueError("No explicit model labels in readable app surface")
    return labels

def fetch(source):
    if source["url"] not in ALLOWED:
        raise ValueError("Unapproved app surface")
    req=urllib.request.Request(source["url"],headers={"Accept":"text/html","User-Agent":USER_AGENT})
    with urllib.request.build_opener(SameHostRedirect()).open(req,timeout=18) as response:
        data=response.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:
        raise ValueError("App surface exceeds byte limit")
    return parse_surface(data.decode("utf-8"),source)

def collect(config,previous,now,fetcher=fetch):
    if previous and previous.get("schema")!="app-updates/v1":
        raise ValueError("Unexpected app updates schema")
    stamp=now.isoformat(timespec="seconds")
    prior={s["id"]:s for s in previous.get("sources",[])}
    events={e["id"]:e for e in previous.get("events",[])}
    sources=[]
    for spec in config["sources"]:
        old=prior.get(spec["id"],{})
        row={**old,**{k:spec[k] for k in ("id","name","vendor","url","links")}}
        entries=old.get("entries",{})
        next_at=parse_stamp(old.get("nextAttemptAt"))
        if next_at and next_at>now:
            sources.append({**row,"deferred":True})
            continue
        try:
            fresh=fetcher(spec)
            if not fresh:
                raise ValueError("Empty app observations")
        except (OSError,ValueError,TypeError) as exc:
            count=int(old.get("consecutiveFailures",0))+1
            sources.append({**row,"entries":entries,"checkedAt":stamp,"lastSuccessAt":old.get("lastSuccessAt"),
                            "status":"probe-unavailable","error":f"{type(exc).__name__}: {str(exc)[:160]}","deferred":False,
                            "consecutiveFailures":count,"nextAttemptAt":(now+timedelta(minutes=min(720,60*2**min(count-1,3)))).isoformat()})
            continue
        # Absence from home marketing/navigation is NOT a withdrawal or
        # delisting; preserve historical observations, track only current view.
        merged={k:{**v,"visibleInLatestRead":False} for k,v in entries.items()}
        for k,value in fresh.items():
            prev=entries.get(k,{})
            merged[k]={**value,"firstObservedAt":prev.get("firstObservedAt") or stamp,"lastObservedAt":stamp,"visibleInLatestRead":True}
            if k not in entries:
                kind="new-visible-label" if old.get("lastSuccessAt") else "baseline-visible-label"
                eid=hashlib.sha256((spec["id"]+"|"+k+"|"+stamp).encode()).hexdigest()
                events[eid]={"id":eid,"sourceId":spec["id"],"sourceUrl":spec["url"],"kind":kind,
                             "observedAt":stamp,"releaseDate":None,**value}
        sources.append({**row,"entries":merged,"checkedAt":stamp,"lastSuccessAt":stamp,"status":"observed",
                        "error":None,"deferred":False,"consecutiveFailures":0,
                        "nextAttemptAt":(now+timedelta(minutes=spec["minIntervalMinutes"])).isoformat()})
    return {"schema":"app-updates/v1","checkedAt":stamp,"sources":sources,
            "reviewedObservations":config.get("reviewedObservations",[]),
            "events":sorted(events.values(),key=lambda e:(e["observedAt"],e["id"]),reverse=True),
            "summary":{"configuredSources":len(config["sources"]),"successfulThisRun":sum(not s.get("deferred") and s["status"]=="observed" for s in sources),
                       "baselineSources":sum(bool(s.get("lastSuccessAt")) for s in sources),
                       "listedModels":sum(sum(v.get("visibleInLatestRead",False) for v in s["entries"].values()) for s in sources),
                       "reviewedObservations":len(config.get("reviewedObservations",[]))},
            "policy":"App visible model label is a product observation, not launch date, availability guarantee or withdrawal. Manual observations separate from automated counts. Private notice and guide links are navigation only."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run",action="store_true")
    p.add_argument("--report",type=Path)
    a=p.parse_args()
    read=lambda path:json.loads(path.read_text(encoding="utf-8"))
    result=collect(read(ROOT/"config/app-update-sources.json"),read(OUTPUT) if OUTPUT.exists() else {},datetime.now(timezone.utc))
    print("App updates:",json.dumps(result["summary"],ensure_ascii=False))
    for source in result["sources"]:
        print("[APP]",source["id"],source["status"],"error=",source.get("error"))
    if a.report:
        write_json(a.report,result)
    if not a.dry_run:
        write_json(OUTPUT,result)
    return 0
if __name__=="__main__":
    raise SystemExit(main())
