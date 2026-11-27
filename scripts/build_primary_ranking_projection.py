"""Candidate source-native leaderboard projection; not a production writer.

Use the existing audited row selection and identity rules without invoking the
retired cross-source calibration experiment. Keep the old builder intact until
the production consumers and output compatibility are independently verified.
"""
from scripts import build_unified_rankings as legacy
from scripts.ranking_identity import attach_rankings


def project(inputs, provider_aliases, alias_keys, families, identity_inputs):
    categories = []
    for category in legacy.CATEGORIES:
        key = category["id"]
        row = {"id": key, "primaryLeaderboard": legacy.build_primary_leaderboard(
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
