"""Conservative model identity and same-day lead association, not release inference."""
from collections import defaultdict
from datetime import date
import re

try:
    from scripts.collect_release_recall import url_key
except ModuleNotFoundError:
    from collect_release_recall import url_key


def day(value):
    try:
        return date.fromisoformat(str(value or "")[:10]).isoformat()
    except ValueError:
        return None


def model_index(families):
    result = defaultdict(set)
    for family in families:
        for version in family.get("versions", []):
            # Leaderboard aliases may denote variants or configurations.
            for value in (version.get("name"), (version.get("releaseEvidence") or {}).get("modelName")):
                name = str(value or "").strip()
                if len(name) >= 5 and re.search(r"[A-Za-z]", name) and re.search(r"\d", name):
                    result[name].add((family["id"], version["id"]))
    return [(re.compile(r"(?<![A-Za-z0-9.])" +
                        r"[\s_-]+".join(re.escape(t) for t in re.split(r"[\s_-]+", name)) +
                        r"(?![A-Za-z0-9.]|[-_][A-Za-z0-9]|\s+(?:turbo|flash|pro|lite|mini|ultra|plus|max|preview|thinking|live|fast|medical|astra|sol|luna|omni|next|code|instruct)\b)", re.I), ids)
            for name, ids in sorted(result.items())]


def identify(index, title, hints=(), family_id=None):
    """Do not guess identity from family, version prefix, or contradictory hints."""
    ids = set()
    for value in (title, *hints):
        for pattern, matches in index:
            if pattern.search(str(value or "")):
                ids.update(matches)
    if len(ids) != 1:
        return None
    identity = next(iter(ids))
    return identity if not family_id or identity[0] == family_id else None


def associate_leads(items, families):
    """Same model and reported calendar day suggests URLs for probing only.

    Never copy a URL into officialArticleUrls or count it as new independent proof.
    Repository creation dates and articles lacking a usable date are not joined.
    """
    index = model_index(families)
    groups = defaultdict(list)
    for row in items:
        row.pop("relatedArticleCandidates", None)
        row.pop("canonicalModelIdentity", None)
        identity = identify(index, row.get("title"), row.get("titleHints") or ())
        if not identity:
            continue
        row["canonicalModelIdentity"] = {"modelFamilyId": identity[0], "modelVersionId": identity[1]}
        stamp = day(row.get("reportedAt"))
        if stamp and row.get("dateKind") != "repository-created-at":
            groups[(identity, stamp)].append(row)
    for rows in groups.values():
        candidates = defaultdict(set)
        for row in rows:
            for raw in row.get("officialArticleUrls", []):
                if url_key(raw):
                    candidates[raw].add(row["id"])
        for row in rows:
            own = {url_key(u) for u in row.get("officialArticleUrls", [])}
            related = [{"url": url, "supportingLeadIds": sorted(ids - {row["id"]})}
                       for url, ids in sorted(candidates.items())
                       if url_key(url) not in own and ids - {row["id"]}]
            if related:
                row["relatedArticleCandidates"] = related[:5]
    return items
