#!/usr/bin/env python3
"""Bounded re-verification of already observed historical release pointers.

This is a separate repair queue, never an independent recall sample or automatic
first-release assertion. It may retain dates older than the recent news window.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

try:
    from scripts.collect_models import BlockParser, article_publication_date, non_release_title, write_json
    from scripts.collect_release_recall import url_key, article_day_stamp
    from scripts.collect_cross_platform import article_url
    from scripts.collect_resolve_model_leads import fetch_page, source_families
    from scripts.event_identity import identify, model_index, day
    from scripts.collect_event_claims import classify
    from scripts.collect_product_state import parse_stamp
    from scripts.audit_model_completeness import audit
except ModuleNotFoundError:
    from collect_models import BlockParser, article_publication_date, non_release_title, write_json
    from collect_release_recall import url_key, article_day_stamp
    from collect_cross_platform import article_url
    from collect_resolve_model_leads import fetch_page, source_families
    from event_identity import identify, model_index, day
    from collect_event_claims import classify
    from collect_product_state import parse_stamp
    from audit_model_completeness import audit

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"site/data/historical-evidence.json"
MAX_URLS=3
# Exact mappings from already observed official repository pointers, reviewed
# for identity. No expected dates or benchmark answers in this configuration.
REPOSITORY_DOCUMENTS={
    ("hunyuan-video","1-5"): {
        "modelName":"1.5",
        "pointer":"https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5",
        "publisherModelName":"HunyuanVideo-1.5",
        "documents":{
            "readme":"https://raw.githubusercontent.com/Tencent-Hunyuan/HunyuanVideo-1.5/main/README.md",
            "license":"https://raw.githubusercontent.com/Tencent-Hunyuan/HunyuanVideo-1.5/main/LICENSE"
        }
    }
}


def inspect_repository_document(content,kind,model_name,now):
    """Parse exact publisher assertions, not commits, tags or file timestamps."""
    name=r"[\s_-]+".join(re.escape(part) for part in re.split(r"[\s_-]+",model_name))
    month=r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    date_pattern=rf"({month} \d{{1,2}}, \d{{4}})"
    if kind=="readme":
        pattern=rf"^\s*[-*]\s*(?:[^\w\s]+\s*)?{date_pattern}:\s*We release the inference code and model weights of {name}\.\s*$"
        claim="code-and-weights-release-statement"
    elif kind=="license":
        pattern=rf"^\s*(?:Tencent )?{name} Release Date:\s*{date_pattern}\s*$"
        claim="license-declared-release-date"
    else:
        raise ValueError("Unsupported repository document type")
    days=set()
    for match in re.finditer(pattern,content,re.I|re.M):
        for fmt in ("%b %d, %Y","%B %d, %Y"):
            try:
                date=datetime.strptime(match.group(1),fmt).date()
            except ValueError:
                continue
            if date<=now.date():
                days.add(date.isoformat())
    if len(days)!=1:
        return {"status":"document-date-conflict" if len(days)>1 else "document-assertion-unresolved",
                "observedDates":sorted(days)}
    return {"status":"document-assertion-observed","claimType":claim,"assertedDate":next(iter(days)),
            "datePrecision":"day","eventDate":None}


def recover_repository_documents(task, mapping, now, fetcher, budget):
    stamp=now.isoformat(timespec="seconds")
    state=dict(task.get("repositoryDocuments",{}))
    history={r["id"]:r for r in task.get("repositoryEvidence",[])}
    attempted=0
    for kind,url in mapping["documents"].items():
        prior=state.get(kind,{})
        nxt=parse_stamp(prior.get("nextAttemptAt"))
        if budget<=attempted or (nxt and nxt>now):
            continue
        attempted+=1
        try:
            content=fetcher(url)
        except (OSError,ValueError,TypeError) as exc:
            count=int(prior.get("consecutiveFailures",0))+1
            state[kind]={**prior,"sourceUrl":url,"status":"fetch-failed","lastAttemptAt":stamp,
                         "error":f"{type(exc).__name__}: {str(exc)[:160]}","consecutiveFailures":count,
                         "nextAttemptAt":(now+timedelta(hours=min(24,6*2**min(count-1,2)))).isoformat()}
            # Same raw content host: stop this round after failure.
            break
        result=inspect_repository_document(content,kind,mapping["publisherModelName"],now)
        state[kind]={"sourceUrl":url,**result,"lastAttemptAt":stamp,"consecutiveFailures":0,
                     "nextAttemptAt":(now+timedelta(days=7)).isoformat()}
        if result["status"]=="document-assertion-observed":
            body={**result,"sourceUrl":url,"documentKind":kind}
            eid="historical-document-"+stable(body)
            if eid not in history:
                history[eid]={"id":eid,**body,"firstVerifiedAt":stamp,
                              "firstContentSha256":hashlib.sha256(content.encode()).hexdigest()}
            state[kind]["lastContentSha256"]=hashlib.sha256(content.encode()).hexdigest()
    task["repositoryDocuments"]=state
    task["repositoryEvidence"]=sorted(history.values(),key=lambda r:r["id"])
    conflicts=[]
    for kind in mapping["documents"]:
        dates=sorted({r["assertedDate"] for r in history.values() if r["documentKind"]==kind})
        if len(dates)>1:
            conflicts.append({"documentKind":kind,"assertedDates":dates})
    task["repositoryConflicts"]=conflicts
    task["status"]=("repository-date-conflict" if conflicts else
                    "repository-document-evidence-observed" if history else
                    "repository-documents-pending")
    return attempted


def stable(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(",",":")).encode()).hexdigest()


def supports_family(url, fid, sources):
    host=urlsplit(url).hostname
    for source in sources:
        if source.get("active") is not True or source.get("official") is not True or fid not in source.get("modelMatches",{}):
            continue
        endpoints=[source["url"],*source.get("fallbackUrls",[]),*(e["url"] for e in source.get("fallbackEndpoints",[]))]
        hosts={urlsplit(u).hostname for u in endpoints}|set(source.get("articleHosts",[]))|set(source.get("announcementHosts",[]))
        if host in hosts and url_key(url) not in {url_key(u) for u in endpoints}:
            return True
    return False


def inspect_page(html,url,identity,model_name,index,sources,now):
    parser=BlockParser()
    parser.feed(html)
    parser.close()
    headings=list(dict.fromkeys(b["text"] for b in parser.blocks if b["tag"]=="h1"))
    if len(headings)!=1:
        return {"status":"heading-unresolved"}
    title=headings[0]
    if identify(index,title)!=identity or source_families(url,title,sources)!={identity[0]}:
        return {"status":"identity-mismatch","publisherTitle":title}
    if non_release_title(title):
        return {"status":"non-release-article","publisherTitle":title}
    value=article_publication_date(html,title,leading_date=urlsplit(url).hostname in {"anthropic.com","www.anthropic.com","z.ai"})
    calendar=day(article_day_stamp(value,url))
    if not calendar or calendar>now.date().isoformat():
        return {"status":"article-date-unresolved","publisherTitle":title}
    kind,service=classify(title,model_name)
    return {"status":"article-date-observed","publisherTitle":title,
            "articlePublishedAt":value,"publisherCalendarDay":calendar,
            "claimType":kind,"service":service,"eventDate":None}


def recover(families,gaps,sources,allowed,previous,resolution,now,fetcher=fetch_page):
    if previous and previous.get("schema")!="historical-evidence/v1":
        raise ValueError("Unknown historical evidence schema")
    stamp=now.isoformat(timespec="seconds")
    old={r["id"]:r for r in previous.get("tasks",[])}
    if len(old)!=len(previous.get("tasks",[])):
        raise ValueError("Duplicate historical evidence task")
    index=model_index(families)
    tasks={}
    for gap in gaps:
        if gap.get("reviewKind")!="release-source-review":
            continue
        ident=(gap["modelFamilyId"],gap["modelVersionId"])
        rid="history-"+stable(*ident)
        prior=old.get(rid,{})
        raw=gap.get("candidateSourceUrl")
        url=article_url(raw,allowed)
        name=gap["modelName"]
        eligible=bool(url and supports_family(url,ident[0],sources))
        same=prior.get("candidateSourceUrl")==raw and prior.get("modelName")==name
        task={**(prior if same else {}),"id":rid,"identity":{"modelFamilyId":ident[0],"modelVersionId":ident[1]},
              "modelName":name,"candidateSourceUrl":raw,"firstDetectedAt":prior.get("firstDetectedAt") or stamp,"active":True,
              "evidence":list(prior.get("evidence",[])),
              "repositoryEvidence":list(prior.get("repositoryEvidence",[]))}
        # A replaced pointer is not a reason to erase earlier verified observations.
        # It also must not inherit an obsolete probe URL or imply fresh evidence.
        task.pop("probeUrl",None)
        mapping=REPOSITORY_DOCUMENTS.get(ident)
        if mapping and raw==mapping["pointer"] and name==mapping["modelName"]:
            task["status"]="repository-documents-pending"
        elif not raw:
            task["status"]="missing-original-pointer"
        elif not eligible:
            task["status"]="unsupported-original-pointer"
        elif identify(index,name)!=ident:
            task["status"]="identity-needs-review"
        else:
            task["probeUrl"]=url
            task.setdefault("status","awaiting-probe")
            if task["status"] in {"missing-original-pointer","unsupported-original-pointer","identity-needs-review"}:
                task["status"]="awaiting-probe"
        tasks[rid]=task
    for rid,row in old.items():
        if rid not in tasks:
            tasks[rid]={**row,"active":False}
    # Do not re-request a URL already subject to the resolver's future retry time.
    blocked={}
    for row in resolution.get("items",[]):
        if row.get("status")=="fetch-failed":
            until=parse_stamp(row.get("nextAttemptAt"))
            if until and until>now:
                blocked[url_key(row.get("url"))]=until
    host_backoff={}
    for task in old.values():
        url=task.get("probeUrl")
        until=parse_stamp(task.get("nextAttemptAt"))
        if url and task.get("status")=="fetch-failed" and until and until>now:
            host=urlsplit(url).hostname
            host_backoff[host]=max(host_backoff.get(host,until),until)
    due=defaultdict(list)
    for task in tasks.values():
        if not task["active"] or task["status"] in {"missing-original-pointer","unsupported-original-pointer","identity-needs-review"}:
            continue
        url=task.get("probeUrl")
        nxt=parse_stamp(task.get("nextAttemptAt"))
        if not url or (nxt and nxt>now) or url_key(url) in blocked or urlsplit(url).hostname in host_backoff:
            continue
        due[url].append(task)
    urls=sorted(due,key=lambda u:(min(t.get("nextAttemptAt") or t["firstDetectedAt"] for t in due[u]),u))
    attempted=0
    document_attempts=0
    for task in tasks.values():
        if not task["active"] or task["status"]!="repository-documents-pending":
            continue
        obj=task["identity"]
        mapping=REPOSITORY_DOCUMENTS[(obj["modelFamilyId"],obj["modelVersionId"])]
        document_attempts+=recover_repository_documents(task,mapping,now,fetcher,MAX_URLS-document_attempts)
    attempted=document_attempts
    for url in urls:
        if attempted>=MAX_URLS:
            break
        host=urlsplit(url).hostname
        if host in host_backoff:
            continue
        attempted+=1
        try:
            page=fetcher(url)
        except (OSError,ValueError,TypeError) as exc:
            for task in due[url]:
                failures=int(task.get("consecutiveFailures",0))+1
                delay=min(1440,360*2**min(failures-1,2))
                retry=now+timedelta(minutes=delay)
                task.update(status="fetch-failed",error=f"{type(exc).__name__}: {str(exc)[:160]}",
                            lastAttemptAt=stamp,consecutiveFailures=failures,nextAttemptAt=retry.isoformat())
                host_backoff[host]=retry
            continue
        for task in due[url]:
            ident=task["identity"]
            outcome=inspect_page(page,url,(ident["modelFamilyId"],ident["modelVersionId"]),task["modelName"],index,sources,now)
            task.update(status=outcome["status"],lastAttemptAt=stamp,error=None,consecutiveFailures=0,
                        latestObservation=outcome,nextAttemptAt=(now+timedelta(days=7)).isoformat())
            if outcome["status"]=="article-date-observed":
                history={r["id"]:r for r in task.get("evidence",[])}
                body={**outcome,"sourceUrl":url}
                eid="historical-article-"+stable(body)
                if eid not in history:
                    history[eid]={"id":eid,**body,"firstVerifiedAt":stamp}
                task["evidence"]=sorted(history.values(),key=lambda r:r["id"])
                days={r["publisherCalendarDay"] for r in task["evidence"] if url_key(r["sourceUrl"])==url_key(url)}
                if len(days)>1:
                    task["status"]="article-date-conflict"
                    task["conflictingArticleDays"]=sorted(days)
    active=[t for t in tasks.values() if t["active"]]
    return {"schema":"historical-evidence/v1","checkedAt":stamp,"tasks":sorted(tasks.values(),key=lambda t:t["id"]),
            "summary":{"activeTasks":len(active),"urlsAttemptedThisRun":attempted,
                       "states":dict(sorted(Counter(t["status"] for t in active).items())),
                       "tasksWithDatedArticleEvidence":sum(bool(t.get("evidence")) for t in active),
                       "datedArticleRecords":sum(len(t.get("evidence",[])) for t in tasks.values()),
                       "repositoryDocumentRequests":document_attempts,
                       "repositoryDocumentEvidenceRecords":sum(len(t.get("repositoryEvidence",[])) for t in tasks.values()),
                       "tasksWithCurrentPointerEvidence":sum(any(url_key(r["sourceUrl"])==url_key(t.get("probeUrl"))
                           for r in t.get("evidence",[])) for t in active)},
            "policy":"Repair queue based on existing catalog pointers, not independent recall. Exact publisher article or reviewed repository-document assertions only. No inferred event date or automatic release promotion."}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run",action="store_true")
    parser.add_argument("--resolution",type=Path)
    parser.add_argument("--report",type=Path)
    args=parser.parse_args()
    directory=ROOT/"site/data"
    def read(path,optional=False):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() or not optional else {}
    families=read(directory/"models.json")
    report=audit(families,read(directory/"topics.json"),read(ROOT/"config/chronicle-release-links.json"))
    if report["errors"]:
        raise ValueError("Cannot inspect invalid canonical catalog")
    result=recover(families,report["gaps"],read(ROOT/"config/model-sources.json"),
                   read(ROOT/"config/cross-platform-sources.json")["officialArticleHosts"],
                   read(OUTPUT,True),read(args.resolution or directory/"lead-resolution.json",True),datetime.now(timezone.utc))
    print("Historical evidence:",json.dumps(result["summary"],ensure_ascii=False))
    if args.report:
        write_json(args.report,result)
    if not args.dry_run:
        write_json(OUTPUT,result)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
