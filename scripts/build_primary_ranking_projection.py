"""Candidate source-native leaderboard projection; not a production writer.

Use the existing audited row selection and identity rules without invoking the
retired cross-source calibration experiment. Keep the old builder intact until
the production consumers and output compatibility are independently verified.
"""
import argparse
import json
from pathlib import Path

try:
    from scripts import build_unified_rankings as legacy
    from scripts.ranking_identity import attach_rankings, inputs as ranking_inputs
except ModuleNotFoundError:
    import build_unified_rankings as legacy
    from ranking_identity import attach_rankings, inputs as ranking_inputs


def project(inputs, provider_aliases, alias_keys, families, identity_inputs):
    categories = []
    for category in legacy.CATEGORIES:
        key = category["id"]
        row = {"id": key, "name": category["name"], "primaryLeaderboard": legacy.build_primary_leaderboard(
            key, inputs, provider_aliases, alias_keys)}
        if key == "video":
            row["primaryLeaderboards"] = {
                "text-to-video-audio": row["primaryLeaderboard"],
                "image-to-video-audio": legacy.build_primary_leaderboard(
                    key, inputs, provider_aliases, alias_keys, config_key="video-i2v"),
            }
        categories.append(row)
    result = {"categories": categories}
    attach_rankings(result, families, *identity_inputs)
    return result


def build_document():
    """Generate the complete reader payload without writing a baseline."""
    aliases = legacy.load_vendor_aliases()
    families = json.loads((legacy.ROOT / "site/data/models.json").read_text())
    result = project(legacy.load_inputs(), aliases, legacy.load_models(aliases),
                     families, ranking_inputs())
    return {"schema": "ai-creator-radar-primary-rankings/1",
            "calculatedAt": legacy.now_iso(),
            "displayPolicy": "Source-native ranks, scores, intervals and samples only; no cross-source calibration.",
            **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="Candidate output outside production data")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to((legacy.ROOT / "site").resolve()) or output.is_relative_to((legacy.ROOT / "config").resolve()):
        parser.error("Candidate must not overwrite production data or configuration")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_document(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
