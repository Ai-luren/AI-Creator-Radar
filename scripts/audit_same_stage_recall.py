"""Independent stage-reviewed event recall; never a source of production facts.

An exact automated observation of a reviewed original article is evidence of
rediscovering that event, not automatic extraction of its semantic stage.
A different URL must be an explicitly reviewed equivalent and a separately
validated publisher statement with the same precise identity, date and stage.
"""
try:
    from scripts.collect_release_recall import url_key
except ModuleNotFoundError:
    from collect_release_recall import url_key


def assess_same_stage(benchmark, fixed, recall, usable_statements, families):
    if not benchmark:
        return {"status":"not-measured","reason":"Missing independent stage review"}
    cases=benchmark.get("events",[])
    original=fixed.get("events",[])
    by_id={r["id"]:r for r in original}
    expected={r["id"]:r for r in cases}
    if benchmark.get("schema")!="same-stage-event-benchmark/v1" or len(cases)!=8 or len(original)!=8 or len(expected)!=8 or set(expected)!=set(by_id):
        raise ValueError("Same-stage review must retain all eight fixed events")
    known={(f["id"],v["id"]):v["name"] for f in families for v in f.get("versions",[])}
    observations={}
    for row in recall.get("events",[]):
        if row["id"] in observations:
            raise ValueError("Duplicate fixed article observation")
        observations[row["id"]]=row
    rows=[]
    for case in cases:
        key=case["id"]
        base=by_id[key]
        for field in ("modelFamilyId","eventDate","modelNames","sourceUrls"):
            if case[field]!=base[field]:
                raise ValueError("Same-stage review changed fixed event: "+key)
        fid=case["modelFamilyId"]
        versions=case["versionIds"]
        if len(versions)!=len(case["modelNames"]) or sorted(known.get((fid,v),"") for v in versions)!=sorted(case["modelNames"]) or len(set(versions))!=len(versions):
            raise ValueError("Stage review has unknown or changed identity: "+key)
        if case.get("stage") not in {"announcement-statement","explicit-release-statement","service-availability-statement"} or not case.get("review"):
            raise ValueError("Missing explicit stage review: "+key)
        row=observations.get(key,{})
        original_match=(all(row.get(k)==base[k] for k in ("modelFamilyId","eventDate","modelNames","sourceUrls"))
                        and row.get("endToEndDated") is True and row.get("dateConflict") is False
                        and any(row.get(k) is True for k in ("currentDated","retainedDated","recoveredDated")))
        # Match only independently reviewed alternate primary URLs; cannot use
        # catalog records, search pointers, reported dates or a different stage.
        matched={v:[] for v in versions}
        for alt in case.get("alternatives",[]):
            if not alt.get("review") or not url_key(alt.get("reviewUrl")) or not url_key(alt.get("sourceUrl")):
                raise ValueError("Unreviewed alternate source: "+key)
            for record in usable_statements:
                fact=record["fact"]
                vid=fact.get("modelVersionId")
                if (fact.get("modelFamilyId")==fid and vid in matched
                        and fact.get("claimType")==case["stage"]
                        and fact.get("publisherCalendarDay")==case["eventDate"]
                        and fact.get("sourceUrl")==alt["sourceUrl"]
                        and fact.get("publisherAccount")==alt["publisherAccount"]
                        and fact.get("service")==alt["service"]
                        and fact.get("eventDate") is None):
                    matched[vid].append(record["id"])
        alternative_match=all(matched.values())
        # A known conflicting date in the original article stays an unresolved
        # conflict, even when a different publication happens to match.
        conflict=row.get("dateConflict") is True
        hit=not conflict and (original_match or alternative_match)
        rows.append({"id":key,"stage":case["stage"],"modelVersionIds":versions,
                     "matched":hit,"originalArticleMatched":bool(original_match),
                     "alternateStatementMatched":alternative_match,
                     "alternateEvidenceIds":sorted({x for ids in matched.values() for x in ids}),
                     "dateConflict":conflict,
                     "method":("original-stage-reviewed-article" if original_match else "reviewed-equivalent-publisher-statement" if alternative_match else None) if hit else None})
    total=sum(r["matched"] for r in rows)
    return {"status":"pass" if total==8 else "incomplete","events":8,"matched":total,
            "missingIds":[r["id"] for r in rows if not r["matched"]],
            "originalArticleMatches":sum(r["matched"] and r["originalArticleMatched"] for r in rows),
            "alternateOnlyMatches":sum(r["matched"] and not r["originalArticleMatched"] for r in rows),
            "rows":rows,"reviewedAt":benchmark["reviewedAt"],"scope":benchmark["scope"],
            "policy":"Event rediscovery using independently stage-reviewed originals or validated same-stage equivalents; not automated semantic stage extraction, first-release proof, population recall, or canonical catalog alignment."}
