"""Model registry joins for primary ranking display, not score calibration."""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def norm(value):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", unicodedata.normalize("NFKC", str(value or "")).lower())


def identity_index(families, aliases, reference=None, maomu=None):
    vendor_map = {}
    for a in aliases.get("aliases", []):
        for name in [*a["names"], a["displayName"], a["canonicalId"]]:
            vendor_map[norm(name)] = norm(a["canonicalId"])

    def vendor(value):
        return vendor_map.get(norm(value), norm(value))

    providers = {}
    boards = [("reference", b) for b in (reference or {}).get("boards", [])]
    boards += [("maomu", b) for c in (maomu or {}).get("categories", []) for b in c.get("boards", [])]
    for source, board in boards:
        for row in board.get("rows", []):
            if row.get("provider"):
                providers.setdefault((source, board["id"], norm(row.get("name"))), set()).add(vendor(row["provider"]))

    index = {}

    def add(name, provider, fid, vid):
        if len(norm(name)) >= 4 and vendor(provider):
            index.setdefault((norm(name), vendor(provider)), set()).add((fid, vid))

    for family in families:
        if family.get("category") == "agent":
            continue
        for version in family.get("versions", []):
            for name in (version.get("name"), (version.get("releaseEvidence") or {}).get("modelName")):
                if name and re.search(r"[0-9]", name):
                    add(name, family.get("vendor"), family["id"], version["id"])
            for alias in version.get("leaderboardAliases", []):
                name = alias.get("name")
                add(name, alias.get("provider") or family.get("vendor"), family["id"], version["id"])
                # Existing audited board aliases supply provider evidence even
                # when the catalog uses a Chinese or composite company name.
                observed = providers.get((alias.get("source"), alias.get("boardId"), norm(name)), set())
                if len(observed) == 1:
                    add(name, next(iter(observed)), family["id"], version["id"])
    return index, vendor


def primary_boards(document):
    for category in document.get("categories", []):
        if category.get("primaryLeaderboard"):
            yield category["primaryLeaderboard"]
        # A task may have no source snapshot; keep it missing, not a synthetic board.
        yield from (board for board in category.get("primaryLeaderboards", {}).values()
                    if board is not None)


def attach_rankings(document, families, aliases, reference=None, maomu=None):
    index, vendor = identity_index(families, aliases, reference, maomu)
    counts = {"exact": 0, "unmatched": 0, "ambiguous": 0}
    for board in primary_boards(document):
        for row in board.get("rows", []):
            hits = index.get((norm(row.get("name")), vendor(row.get("provider"))), set())
            row.pop("modelFamilyId", None)
            row.pop("modelVersionId", None)
            status = "exact" if len(hits) == 1 else "ambiguous" if hits else "unmatched"
            row["modelLinkStatus"] = status
            counts[status] += 1
            if status == "exact":
                row["modelFamilyId"], row["modelVersionId"] = next(iter(hits))
    return counts


def inputs():
    def read(relative):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))
    return (read("config/unified-ranking-vendor-aliases.json"), read("site/data/reference-rankings.json"), read("site/data/maomu-rankings.json"))


def update_rankings(families):
    path = ROOT / "site/data/unified-rankings.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    before = json.dumps(doc, ensure_ascii=False)
    counts = attach_rankings(doc, families, *inputs())
    if json.dumps(doc, ensure_ascii=False) != before:
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return counts
