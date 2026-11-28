#!/usr/bin/env python3
"""Source-native primary rankings; no composite calibration or baseline writes."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.ranking_identity import attach_rankings, inputs as ranking_inputs
except ModuleNotFoundError:
    from ranking_identity import attach_rankings, inputs as ranking_inputs

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site/data/unified-rankings.json"
VENDOR_ALIASES = ROOT / "config/unified-ranking-vendor-aliases.json"
PRIMARY_SNAPSHOTS = ROOT / "site/data/leaderboard-reference-snapshots.json"
CATEGORIES = [
    {"id": "image", "name": "图片生成"},
    {"id": "video", "name": "视频生成"},
    {"id": "music", "name": "音乐生成"},
    {"id": "tts", "name": "语音合成"},
    {"id": "coding", "name": "编程"},
]

PRIMARY_LEADERBOARDS = {
    "image": {
        "board": ("reference", "arena-text-to-image", "Arena", "arena-image-t2i-primary"),
        "sourceName": "Arena 文生图",
        "sourceUrl": "https://arena.ai/leaderboard/image/text-to-image",
        "snapshotPublisher": "FAI.Fashion 快照；原榜为 Arena",
        "scoreLabel": "Arena Rating",
        "sampleLabel": "对战次数",
        "methodNote": "Arena 社区盲测偏好。只表示当前 Arena 文生图任务中的用户偏好，不是市场使用量或客观正确率。",
    },
    "video": {
        "board": ("primary", "aa-video-t2v-audio-20261125", "Artificial Analysis", "aa-video-audio-t2v-primary"),
        "sourceName": "AA 有声文生视频",
        "sourceUrl": "https://artificialanalysis.ai/video/leaderboard/text-to-video",
        "snapshotPublisher": "Artificial Analysis 原榜快照",
        "scoreLabel": "AA Elo",
        "sampleLabel": "评测样本",
        "methodNote": "AA 盲测偏好榜，只测有声文生视频输出，不测创作者使用量或市场采用率。保留 AA 原榜名次；无声榜、图生榜和 Arena 未标音轨的榜不合并。快照取原榜前 20 名，再隐藏已确认的 H3 衍生端点、同家族重复版本和身份未核实端点，最多展示 10 个合资格候选；原榜名次不重排。",
    },
    "video-i2v": {
        "board": ("primary", "aa-video-i2v-audio-20261125", "Artificial Analysis", "aa-video-audio-i2v-primary"),
        "sourceName": "AA 有声图生视频",
        "sourceUrl": "https://artificialanalysis.ai/video/leaderboard/image-to-video",
        "snapshotPublisher": "Artificial Analysis 原榜快照",
        "scoreLabel": "AA Elo",
        "sampleLabel": "评测样本",
        "methodNote": "AA 盲测偏好榜，只测以参考图生成有声视频，不测创作者使用量或市场采用率。I2V 有独立 Elo 池，不与文生视频或无声榜合并。快照取原榜前 20 名，再隐藏已确认的 H3 衍生端点、同家族重复版本和身份未核实端点，最多展示 10 个合资格候选；原榜名次不重排。",
    },
    "music": {
        "board": ("primary", "aa-music-vocal-20261125", "Artificial Analysis", "aa-music-vocal-primary"),
        "sourceName": "AA 含人声音乐",
        "sourceUrl": "https://artificialanalysis.ai/music/leaderboard/vocals",
        "snapshotPublisher": "Artificial Analysis 原榜快照",
        "scoreLabel": "AA Elo",
        "sampleLabel": "评测样本",
        "methodNote": "主表选含人声整曲榜。AA 把器乐和人声分成不同 Elo 池，因此不平均两池原始分；器乐榜作为不同创作任务查看。",
    },
    "tts": {
        "board": ("primary", "aa-speech-provider-voice-full-20261125", "Artificial Analysis", "aa-speech-provider-voice-primary"),
        "sourceName": "AA Provider Voice 全量 TTS",
        "sourceUrl": "https://artificialanalysis.ai/embed/text-to-speech-leaderboard/leaderboard/provider-voice",
        "snapshotPublisher": "Artificial Analysis 原榜快照",
        "scoreLabel": "AA Elo",
        "sampleLabel": "评测样本",
        "methodNote": "全量 Provider Voice 榜，包含 ElevenLabs 等商业 TTS；不是开放权重子榜，也不代表语音克隆或所有语言口音任务。",
    },
    "coding": {
        "board": ("maomu", "llm-coding", "Arena", "arena-coding-primary"),
        "sourceName": "Arena Code",
        "sourceUrl": "https://arena.ai/leaderboard/code",
        "snapshotPublisher": "猫目快照；原榜为 Arena Code",
        "scoreLabel": "Arena Score",
        "sampleLabel": "用户投票",
        "methodNote": "Arena Code 是真实用户偏好榜；它不等同于隐藏单元测试通过率，也不能代表所有编程任务。",
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def norm(value: str) -> str:
    # Keep variant qualifiers such as (high), [dev], and resolution intact.
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", unicodedata.normalize("NFKC", value or "").casefold())


def evaluation_spec(board: dict):
    source_meta = board.get("source") if isinstance(board.get("source"), dict) else {}
    version = board.get("evaluationVersion") or board.get("methodologyVersion") or board.get("version")
    stable_version = str(version or "").strip()
    # Snapshot dates are not evaluation-method versions. Keep the stable version
    # label while separately hashing the method/task metadata below.
    stable_version = re.sub(r"\s*[·•]\s*(?:20\d{2}[-/]\d{1,2}.*|20\d{2}年.*)$", "", stable_version).strip()
    spec = {
        "boardId": board.get("id"),
        "kind": board.get("kind"),
        "task": board.get("task"),
        "audioMode": board.get("audioMode"),
        "version": stable_version or None,
        "evaluationSource": board.get("evaluationSource"),
        "description": board.get("description"),
        "method": board.get("method"),
        "headers": board.get("headers"),
        "sourceKind": source_meta.get("kind") if source_meta else board.get("source"),
        "sourceDescription": source_meta.get("description"),
    }
    spec = {key: value for key, value in spec.items() if value is not None}
    fingerprint = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return stable_version or f"metadata:{fingerprint[:16]}", fingerprint, spec


def numeric(value):
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d[\d,]*(?:\.\d+)?", value.replace("−", "-"))
        if match:
            try:
                return float(match.group(0).replace(",", ""))
            except ValueError:
                return None
    return None


def row_score(row: dict):
    value = numeric(row.get("elo"))
    if value is not None:
        return value
    label = str(row.get("scoreLabel") or "").casefold()
    # Only use score-bearing benchmark rows. Never convert a rank to a score.
    if any(token in label for token in ("elo", "arena score", "benchalign", "多模态分", "coding score")):
        return numeric(row.get("score"))
    return None


def row_interval(row: dict):
    low, high = numeric(row.get("ciLow")), numeric(row.get("ciHigh"))
    if low is not None and high is not None and high >= low:
        return low, high
    for metric in row.get("metrics", []):
        if "95%" in str(metric.get("label", "")) or "置信" in str(metric.get("label", "")):
            found = re.findall(r"-?\d[\d,]*(?:\.\d+)?", str(metric.get("value", "")).replace("−", "-"))
            if len(found) >= 2:
                vals = [float(x.replace(",", "")) for x in found[-2:]]
                return min(vals), max(vals)
    return None, None


def load_inputs():
    ref_data = json.loads((ROOT / "site/data/reference-rankings.json").read_text())
    maomu_data = json.loads((ROOT / "site/data/maomu-rankings.json").read_text())
    primary_data = json.loads(PRIMARY_SNAPSHOTS.read_text())
    reference = {b["id"]: b for b in ref_data.get("boards", [])}
    maomu = {b["id"]: b for category in maomu_data.get("categories", []) for b in category.get("boards", [])}
    primary = {b["id"]: b for b in primary_data.get("boards", [])}
    return {
        "reference": reference, "maomu": maomu, "primary": primary,
        "metadata": {
            "reference": {key: ref_data.get(key) for key in ("provider", "sourceCheckedAt", "fetchedAt", "publishedAt")},
            "maomu": {key: maomu_data.get(key) for key in ("provider", "sourceCheckedAt", "checkedAt", "collectedAt", "fetchedAt", "publishedAt")},
            "primary": {key: primary_data.get(key) for key in ("capturedAt", "note")},
        },
    }


def row_sample_count(row: dict):
    for key in ("comparisons", "samples", "sampleCount", "votes"):
        value = numeric(row.get(key))
        if value is not None:
            return value
    for metric in row.get("metrics", []):
        if str(metric.get("label", "")).casefold() in {"投票", "votes", "samples", "comparisons", "对战"}:
            return numeric(metric.get("value"))
    return None


def get_board(inputs, spec, provider_aliases=None, alias_keys=None):
    source, board_id, provider, family = spec
    board = inputs[source].get(board_id)
    if not board:
        return None
    rows = []
    provider_aliases = provider_aliases or {}
    alias_keys = alias_keys or {}
    for row_index, raw in enumerate(board.get("rows", [])):
        score = row_score(raw)
        if score is None or not raw.get("name"):
            continue
        raw_provider = raw.get("provider") or "厂商待核实"
        canonical, _display, _unknown = canonical_provider(raw_provider, provider_aliases)
        version_identity = exact_model_version(raw, alias_keys, provider_aliases)
        if version_identity:
            identity_key = f"version:{version_identity[0]}:{version_identity[1]}"
            identity_rule = "exact-model-version-id"
        elif norm(raw_provider) in UNKNOWN_PROVIDERS:
            # Generic/missing vendor labels must never turn same-name models
            # into cross-source calibration anchors.
            identity_key = f"unresolved:{board_id}:{row_index}:{norm(raw['name'])}"
            identity_rule = "unresolved-source-provider"
        else:
            identity_key = f"vendor:{canonical}|model:{norm(raw['name'])}"
            identity_rule = "canonical-vendor-and-exact-model-name"
        low, high = row_interval(raw)
        rows.append({
            "key": norm(raw["name"]), "identityKey": identity_key, "identityRule": identity_rule,
            "name": raw["name"], "provider": raw_provider, "rank": raw.get("rank"),
            "rankRange": raw.get("rankRange"), "excludeReason": raw.get("excludeReason"),
            "score": score, "ciLow": low, "ciHigh": high,
            "comparisons": row_sample_count(raw),
            "detailUrl": raw.get("detailsUrl") or raw.get("detailUrl") or (board.get("source", {}).get("url") if isinstance(board.get("source"), dict) else None) or board.get("url"),
            "releasedAt": raw.get("releasedAt"),
        })
    source_meta = board.get("source") if isinstance(board.get("source"), dict) else {}
    source_url = source_meta.get("url") or board.get("url") or board.get("detailsUrl")
    updated = board.get("publishedAt") or board.get("sourceCheckedAt") or board.get("updatedAt") or board.get("evaluatedAt")
    if source == "reference":
        updated = board.get("publishedAt") or board.get("sourceCheckedAt") or updated
    evaluation_version, evaluation_spec_hash, evaluation_spec_data = evaluation_spec(board)
    return {
        "id": board_id, "name": board.get("name") or board.get("title") or board_id,
        "provider": provider, "family": family, "url": source_url,
        "updatedAt": updated, "publishedAt": board.get("publishedAt"),
        "sourceCheckedAt": board.get("sourceCheckedAt"), "collectedAt": board.get("collectedAt"), "capturedAt": board.get("capturedAt"), "audioMode": board.get("audioMode"),
        "snapshotScope": board.get("snapshotScope"), "excludedReferences": board.get("excludedReferences", []),
        "evaluationVersion": evaluation_version, "evaluationSpecHash": evaluation_spec_hash,
        "evaluationSpec": evaluation_spec_data,
        "sourceHash": hashlib.sha256(json.dumps(board, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
        "rows": rows,
    }


def build_primary_leaderboard(category_id, inputs, provider_aliases, alias_keys, config_key=None):
    config = PRIMARY_LEADERBOARDS.get(config_key or category_id)
    if not config:
        return None
    board = get_board(inputs, config["board"], provider_aliases, alias_keys)
    if not board:
        return None
    eligible, excluded = [], list(board.get("excludedReferences", []))
    for row in sorted(board["rows"], key=lambda item: (item["rank"] is None, item["rank"] or 10**9)):
        public_row = {
            "rank": row["rank"], "rankRange": row["rankRange"],
            "name": row["name"], "provider": row["provider"],
            "score": row["score"], "ciLow": row["ciLow"], "ciHigh": row["ciHigh"],
            "sampleCount": row["comparisons"], "releasedAt": row["releasedAt"],
            "url": row["detailUrl"] or config["sourceUrl"],
        }
        if row.get("excludeReason"):
            excluded.append({"rank": row["rank"], "name": row["name"], "reason": row["excludeReason"]})
            continue
        eligible.append(public_row)
    metadata = inputs.get("metadata", {}).get(config["board"][0], {})
    snapshot_date = board.get("capturedAt") if config["board"][0] == "primary" else None
    snapshot_date = snapshot_date or (metadata.get("capturedAt") if config["board"][0] == "primary" else None)
    snapshot_date = snapshot_date or board.get("publishedAt") or board.get("collectedAt") or board.get("capturedAt") or metadata.get("collectedAt") or metadata.get("publishedAt") or metadata.get("fetchedAt") or board.get("updatedAt")
    checked_at = board.get("sourceCheckedAt") or metadata.get("sourceCheckedAt") or metadata.get("checkedAt") or board.get("updatedAt")
    return {
        "sourceName": config["sourceName"], "sourceUrl": config["sourceUrl"],
        "snapshotPublisher": config["snapshotPublisher"], "snapshotDate": snapshot_date, "checkedAt": checked_at,
        "evaluationVersion": board["evaluationVersion"], "scoreLabel": config["scoreLabel"],
        "sampleLabel": config["sampleLabel"], "methodNote": config["methodNote"],
        "snapshotScope": board.get("snapshotScope"),
        "audioMode": board.get("audioMode"), "rows": eligible[:10],
        "excluded": excluded,
    }

def load_vendor_aliases():
    data = json.loads(VENDOR_ALIASES.read_text())
    aliases = {}
    for item in data.get("aliases", []):
        value = {"canonicalId": item["canonicalId"], "displayName": item["displayName"]}
        for name in item.get("names", []):
            aliases[norm(name)] = value
    return aliases


UNKNOWN_PROVIDERS = {norm(value) for value in ("", "unknown", "n/a", "厂商待确认", "厂商待核实", "待确认", "待核实", "未知")}


def canonical_provider(provider, aliases, known_by_name=None, model_name=""):
    raw = str(provider or "")
    key = norm(raw)
    alias = aliases.get(key)
    if alias:
        return alias["canonicalId"], alias["displayName"], False
    if key in UNKNOWN_PROVIDERS:
        candidates = (known_by_name or {}).get(norm(model_name), set())
        if len(candidates) == 1:
            canonical_id = next(iter(candidates))
            return canonical_id, next((v for v in aliases.values() if v["canonicalId"] == canonical_id), {}).get("displayName", raw), False
        return f"unknown:{key or 'missing'}", raw or "厂商待确认", bool(candidates)
    return f"raw:{key}", raw or "厂商待确认", False


def load_models(provider_aliases):
    models = json.loads((ROOT / "site/data/models.json").read_text())
    alias_keys = {}
    for family in models:
        for version in family.get("versions", []):
            for alias in version.get("leaderboardAliases", []):
                provider = canonical_provider(alias.get("provider"), provider_aliases)[0]
                key = (norm(alias.get("name", "")), provider)
                alias_keys.setdefault(key, set()).add((family.get("id"), version.get("id")))
        for alias in family.get("leaderboardAliases", []):
            provider = canonical_provider(alias.get("provider"), provider_aliases)[0]
            key = (norm(alias.get("name", "")), provider)
            alias_keys.setdefault(key, set()).add((family.get("id"), None))
    return alias_keys


def exact_model_version(row, alias_keys, provider_aliases):
    provider = canonical_provider(row.get("provider"), provider_aliases)[0]
    hits = alias_keys.get((norm(row.get("name", "")), provider), set())
    versions = {(family_id, version_id) for family_id, version_id in hits if version_id}
    return next(iter(versions)) if len(versions) == 1 else None

def project(inputs, provider_aliases, alias_keys, families, identity_inputs):
    categories = []
    for category in CATEGORIES:
        key = category["id"]
        row = {"id": key, "name": category["name"], "primaryLeaderboard": build_primary_leaderboard(
            key, inputs, provider_aliases, alias_keys)}
        if key == "video":
            row["primaryLeaderboards"] = {
                "text-to-video-audio": row["primaryLeaderboard"],
                "image-to-video-audio": build_primary_leaderboard(
                    key, inputs, provider_aliases, alias_keys, config_key="video-i2v"),
            }
        categories.append(row)
    result = {"categories": categories}
    attach_rankings(result, families, *identity_inputs)
    return result


def build_document():
    """Generate the complete reader payload without writing a baseline."""
    aliases = load_vendor_aliases()
    families = json.loads((ROOT / "site/data/models.json").read_text())
    result = project(load_inputs(), aliases, load_models(aliases),
                     families, ranking_inputs())
    return {"schema": "ai-creator-radar-primary-rankings/1",
            "calculatedAt": now_iso(),
            "displayPolicy": "Source-native ranks, scores, intervals and samples only; no cross-source calibration.",
            **result}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if output != OUTPUT.resolve() and (output.is_relative_to((ROOT / "site").resolve()) or output.is_relative_to((ROOT / "config").resolve())):
        parser.error("Do not overwrite other production data or configuration")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_document(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
