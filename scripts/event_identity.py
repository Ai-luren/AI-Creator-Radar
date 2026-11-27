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


def joint_title_identities(index, title, family_id):
    """Resolve an explicit conjunctive list of canonical model names.

    Full-match every list element. A shortened subsequent element may inherit
    a literal leading prefix from the first full name ONLY when that yields
    one exact known identity. Never treat prose, comparisons, mixed-stage
    suffixes or unknown variants as a joint model list.
    """
    value = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2212]", "-", str(title or ""))
    value = re.sub(r"\s+", " ", value).strip().rstrip("!.！。")
    verb = re.match(r"^(Introducing|Announcing)\s+", value, re.I)
    stage = "announcement-statement" if verb else "article-publication"
    value = value[verb.end():] if verb else value
    if not re.search(r"\s+(?:and|&)\s+", value, re.I):
        return None
    parts = re.split(r"\s+(?:and|&)\s+", value, flags=re.I)
    if not 2 <= len(parts) <= 4 or any(not p.strip() for p in parts):
        return None

    def exact(text):
        found = set()
        for pattern, ids in index:
            if pattern.fullmatch(text):
                found.update(ids)
        return found

    first = exact(parts[0])
    if len(first) != 1 or next(iter(first))[0] != family_id:
        return None
    all_ids = set(first)
    words = parts[0].split()
    # The prefix is literal text from this same publisher title. No alias
    # dictionary, substring match, benchmark names, or catalog date involved.
    prefixes = [" ".join(words[:n]) + " " for n in range(1, len(words))]
    for part in parts[1:]:
        matches = exact(part)
        if not matches:
            for prefix in prefixes:
                matches.update(exact(prefix + part))
        if len(matches) != 1 or next(iter(matches))[0] != family_id or all_ids & matches:
            return None
        all_ids.update(matches)
    return {"identities": sorted(all_ids), "claimType": stage}


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
