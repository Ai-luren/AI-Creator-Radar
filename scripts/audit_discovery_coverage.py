"""Audit external discovery coverage without interpreting reports as release facts."""
from collections import Counter, defaultdict

try:
    from scripts.collect_release_recall import url_key
except ModuleNotFoundError:
    from collect_release_recall import url_key

TERMINAL = {"not-model-announcement", "outside-current-window"}


def inspect_leads(discovery, resolution):
    """Track each observed external lead, even if it has no allowlisted article.

    A verified article date is not a verified first-release claim. This audit
    intentionally keeps article, canonical release, and external report separate.
    """
    by_lead = defaultdict(list)
    for row in resolution.get("items", []):
        for lead_id in row.get("leadIds", []):
            by_lead[lead_id].append(row)
    rows = []
    for lead in discovery.get("items", []):
        if lead.get("sourceId") == "local-official-candidates":
            continue
        lead_id = lead.get("id")
        if not lead_id:
            continue
        originals = {url_key(url): url for url in lead.get("officialArticleUrls", []) if url_key(url)}
        probes = [r for r in by_lead.get(lead_id, []) if url_key(r.get("url")) in originals]
        checked_urls = {url_key(r.get("url")) for r in probes}
        unprobed = sorted(originals[k] for k in originals.keys() - checked_urls)
        statuses = sorted({r.get("status", "unknown") for r in probes})
        # A verified article cannot conceal an unresolved or unprobed second article.
        if not originals:
            state = "no-allowlisted-original"
        elif not probes:
            state = "awaiting-probe"
        elif unprobed:
            state = "unresolved"
        elif all(s in TERMINAL for s in statuses):
            state = "excluded-by-article-review"
        elif all(s in TERMINAL | {"article-date-verified"} for s in statuses):
            state = "article-date-observed"
        else:
            state = "unresolved"
        rows.append({"leadId": lead_id, "title": lead.get("title"), "sourceId": lead.get("sourceId"),
                     "url": lead.get("url"), "firstSeenAt": lead.get("firstSeenAt"),
                     "reportedAt": lead.get("reportedAt"), "dateKind": lead.get("dateKind"),
                     "state": state, "probeStates": statuses,
                     "officialArticleUrls": lead.get("officialArticleUrls", []),
                     "unprobedOfficialArticleUrls": unprobed,
                     "nextAttemptAt": min((p["nextAttemptAt"] for p in probes
                                           if p.get("nextAttemptAt") and p.get("status") not in TERMINAL | {"article-date-verified"}), default=None)})
    rows.sort(key=lambda r: (r["firstSeenAt"] or "", r["leadId"]))
    return {"discoveryCheckedAt": discovery.get("checkedAt"),
            "resolutionCheckedAt": resolution.get("checkedAt"),
            "leadCount": len(rows), "counts": dict(sorted(Counter(r["state"] for r in rows).items())),
            "openLeads": [r for r in rows if r["state"] in {"no-allowlisted-original", "awaiting-probe", "unresolved"}],
            "scopeNote": "Counts observed external lead records, not distinct release events or verified omissions. Article-date evidence is not first-release evidence."}
