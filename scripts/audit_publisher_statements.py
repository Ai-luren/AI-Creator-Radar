"""Audit persisted publisher statement proofs without inferring release events.

Only the reviewed pilot adapters are accepted. A dated statement remains a
separate claim; matching its model never satisfies an article/release sample.
"""
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import re
from urllib.parse import urlsplit

try:
    from scripts.event_identity import day
    from scripts.publisher_statement_recovery import post_url
except ModuleNotFoundError:
    from event_identity import day
    from publisher_statement_recovery import post_url


def parse_time(value):
    try:
        result = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def statement_id(fact):
    basis = {k: v for k, v in fact.items() if k != "contentSha256"}
    return "publisher-" + hashlib.sha256(json.dumps(basis, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def inspect_statements(snapshot, families, now, benchmark=None):
    errors = []
    records = snapshot.get("records", [])
    if not isinstance(records, list):
        return [], {"errors": ["Invalid publisher statement record list"], "conflicts": [], "summary": {}}
    known = {(f["id"], v["id"]) for f in families for v in f.get("versions", [])}
    seen = set()
    valid = []
    checked = parse_time(snapshot.get("checkedAt"))
    for pos, record in enumerate(records):
        try:
            if not isinstance(record, dict) or not isinstance(record.get("fact"), dict):
                raise ValueError("Malformed statement")
            fact = record["fact"]
            rid = record.get("id")
            if rid != statement_id(fact) or rid in seen:
                raise ValueError("Invalid or duplicate statement identity")
            seen.add(rid)
            ident = (fact.get("modelFamilyId"), fact.get("modelVersionId"))
            if ident not in known:
                raise ValueError("Unknown canonical model identity")
            if fact.get("claimType") not in {"service-availability-statement","announcement-statement"} or "eventDate" not in fact or fact["eventDate"] is not None:
                raise ValueError("Publisher statement must not infer an event or first-release date")
            if fact.get("datePrecision") != "day":
                raise ValueError("Unexpected date precision")
            date_value = fact.get("publisherCalendarDay")
            first = parse_time(record.get("firstObservedAt"))
            last = parse_time(record.get("lastSuccessfulObservationAt"))
            if not (day(date_value) == date_value and first and last and checked
                    and date_value <= first.date().isoformat() and first <= last <= checked <= now):
                raise ValueError("Invalid publication/observation chronology")
            if any(not re.fullmatch(r"[0-9a-f]{64}", str(fact.get(k) or "")) for k in ("statementSha256", "contentSha256")):
                raise ValueError("Missing content or statement hash")
            source = fact.get("sourceUrl")
            p = urlsplit(source or "")
            discovery = record.get("discovery")
            if not isinstance(discovery, dict):
                raise ValueError("Missing original discovery provenance")
            if fact.get("evidenceGrade") == "official-dated-article-statement":
                if not (ident[0] == "glm" and p.scheme == "https" and p.hostname == "www.zhipuai.cn"
                        and p.port in (None,443) and not p.username and not p.password and not p.query and not p.fragment
                        and re.fullmatch(r"/zh/(?:news|research)/\d+",p.path)
                        and fact.get("claimType") == "service-availability-statement"
                        and fact.get("service") == "GLM Coding Plan"
                        and discovery.get("channel") == "official-article-collector" and discovery.get("sourceUrl") == source):
                    raise ValueError("Unexpected article provenance or service")
            elif fact.get("evidenceGrade") == "official-dated-social-statement":
                post = post_url(source)
                pointer = urlsplit(discovery.get("sourceUrl") or "")
                stage_ok = (ident[0]=="midjourney" and fact.get("claimType")=="service-availability-statement"
                            and fact.get("service")=="Midjourney / Niji Journey" and post and post[1] in {"midjourney","nijijourney"}
                            or ident[0]=="glm" and fact.get("claimType")=="announcement-statement"
                            and fact.get("service") is None and post and post[1]=="zai_org")
                safe_pointer=(pointer.scheme=="https" and pointer.port in (None,443)
                              and not pointer.username and not pointer.password and not pointer.query and not pointer.fragment)
                archive_ok=(ident[0]=="midjourney" and discovery.get("channel")=="public-launch-index-pointer"
                            and pointer.hostname=="launcharchive.ai"
                            and re.fullmatch(r"/launches/[a-z0-9-]+--x_"+re.escape(p.path.rsplit("/",1)[-1]),pointer.path))
                index_ok=(discovery.get("channel")=="public-daily-index-pointer"
                          and pointer.hostname=="www.advanceintelligence.ai"
                          and re.fullmatch(r"/20\d{2}-\d{2}-\d{2}/all",pointer.path)
                          and isinstance(discovery.get("sourceRecordId"),str) and bool(discovery["sourceRecordId"]))
                if not (post and post[0]==source and post[1]==fact.get("publisherAccount")
                        and stage_ok and safe_pointer and (archive_ok or index_ok)):
                    raise ValueError("Unexpected social publisher or discovery pointer")
            else:
                raise ValueError("Unsupported publisher statement adapter")
            valid.append(record)
        except (ValueError, TypeError, KeyError) as exc:
            errors.append("Publisher statement "+str(pos)+": "+str(exc))
    by_source = defaultdict(list)
    for record in valid:
        fact = record["fact"]
        by_source[(fact["sourceUrl"],fact["modelFamilyId"],fact["modelVersionId"])].append(record)
    conflicts = []
    blocked = set()
    for identity, group in sorted(by_source.items()):
        dates = sorted({r["fact"]["publisherCalendarDay"] for r in group})
        if len(dates)>1:
            blocked.update(r["id"] for r in group)
            conflicts.append({"sourceUrl":identity[0],"modelFamilyId":identity[1],"modelVersionId":identity[2],"dates":dates})
    usable = [r for r in valid if r["id"] not in blocked]
    sample = []
    for case in (benchmark or {}).get("events", []):
        matched = [r for r in usable if all(r["fact"].get(k)==case[k] for k in
                   ("modelFamilyId","modelVersionId","claimType","service","publisherCalendarDay","sourceUrl"))]
        sample.append({"id":case["id"],"matched":bool(matched),"evidenceIds":sorted(r["id"] for r in matched)})
    return usable, {"errors":errors,"checkedAt":snapshot.get("checkedAt"),"conflicts":conflicts,
        "summary":{"records":len(records),"validUnconflicted":len(usable),
                   "identities":len({(r["fact"]["modelFamilyId"],r["fact"]["modelVersionId"]) for r in usable}),
                   "observedThisRun":sum(r["lastSuccessfulObservationAt"]==snapshot.get("checkedAt") for r in usable),
                   "dateConflicts":len(conflicts),
                   "byClaimType":dict(sorted(Counter(r["fact"]["claimType"] for r in usable).items()))},
        "sourceHealth":{k:{field:s.get(field) for field in ("lastAttemptAt","lastSuccessAt","nextAttemptAt","error","candidateCount")}
                        for k,s in snapshot.get("sources",{}).items()},
        "availabilitySample":{"events":len(sample),"matched":sum(r["matched"] for r in sample),"rows":sample,
                              "scope":(benchmark or {}).get("scope")},
        "policy":"Structural integrity and separate availability-statement coverage only. Does not establish first-release dates or replace original article recall."}
