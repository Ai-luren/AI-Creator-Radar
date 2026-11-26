#!/usr/bin/env python3
"""Build conservative, evidence-linked creator capability rankings.

Raw provider snapshots are read-only inputs. This builder writes a separate
derived file and records which source pools were calibrated or left provisional.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site/data/unified-rankings.json"
BASELINE = ROOT / "config/unified-ranking-baseline.json"
VENDOR_ALIASES = ROOT / "config/unified-ranking-vendor-aliases.json"
PRIMARY_SNAPSHOTS = ROOT / "site/data/leaderboard-reference-snapshots.json"
METHOD_VERSION = "2026.11-radar-index-v4"
MIN_ANCHORS = 20
MIN_SPEARMAN = 0.80
MAX_LOO_RMSE = 0.50
MIN_ANCHOR_SPAN_SD = 1.0

# Each subtask is a separate measurement pool. Repeated mirrors of the same
# upstream leaderboard are deliberately omitted as duplicate evidence.
CATEGORIES = [
    {
        "id": "image", "name": "图片生成",
        "description": "文生图与图片编辑等权构成创作者用途指数。",
        "subtasks": [
            {"id": "text-to-image", "name": "文生图", "boards": [
                ("reference", "image", "Artificial Analysis", "aa-image-t2i"),
                ("reference", "arena-text-to-image", "Arena", "arena-image-t2i"),
            ]},
            {"id": "image-editing", "name": "图片编辑", "boards": [
                ("maomu", "image-aa-edit", "Artificial Analysis", "aa-image-edit"),
                ("reference", "arena-image-edit", "Arena", "arena-image-edit"),
            ]},
        ],
    },
    {
        "id": "video", "name": "视频生成",
        "description": "视频榜只纳入有声文生视频与有声图生视频；无声评测不进入这张主榜，模式未标明的来源只作参考。",
        "subtasks": [
            {"id": "text-to-video-audio", "name": "文生视频·有声", "audioMode": "audio", "boards": [
                ("reference", "video-text-audio", "Artificial Analysis", "aa-video-t2v-audio"),
            ], "referenceOnlyBoards": [("reference", "arena-text-to-video", "Arena", "arena-video-t2v")],
                "referenceOnlyReason": "Arena 快照没有标注该榜有声或无声"},
            {"id": "image-to-video-audio", "name": "图生视频·有声", "audioMode": "audio", "boards": [
                ("reference", "video-image-audio", "Artificial Analysis", "aa-video-i2v-audio"),
            ], "referenceOnlyBoards": [("reference", "arena-image-to-video", "Arena", "arena-video-i2v")],
                "referenceOnlyReason": "Arena 快照没有标注该榜有声或无声"},
        ],
        "referenceOnlyBoards": [("reference", "arena-video-edit", "Arena", "arena-video-edit")],
        "referenceOnlyReason": "视频编辑快照未标明音频模式，暂不计入有声视频指数",
    },
    {
        "id": "music", "name": "音乐生成",
        "description": "器乐与人声音乐等权；当前数据为单来源暂定指数。",
        "subtasks": [
            {"id": "instrumental", "name": "器乐", "boards": [
                ("reference", "music-aa-instrumental-aurion-20261112", "Artificial Analysis", "aa-music-instrumental"),
            ]},
            {"id": "vocal", "name": "人声音乐", "boards": [
                ("reference", "music-aa-vocal-aurion-202610", "Artificial Analysis", "aa-music-vocal"),
            ]},
        ],
    },
    {
        "id": "tts", "name": "语音合成",
        "description": "主表使用 Artificial Analysis Provider Voice 全量文本转语音榜，包含 ElevenLabs 等商业服务；开放权重子榜是不同筛选口径。",
        "subtasks": [
            {"id": "speech-generation", "name": "语音生成", "boards": [
                ("reference", "speech", "Artificial Analysis", "aa-speech"),
            ]},
        ],
    },
    {
        "id": "coding", "name": "编程",
        "description": "当前公开可用的编程偏好榜；WebDev 与通用代码能力不作等同解释。",
        "subtasks": [
            {"id": "coding-preference", "name": "编程任务偏好", "boards": [
                ("maomu", "llm-coding", "Arena", "arena-coding"),
            ]},
        ],
    },
]

# The public-facing table is deliberately a source-native reference list. The
# cross-source v4 experiment stays available in the generated data for audit,
# but is not promoted as a main-board rank until its sources are genuinely
# comparable and the model inclusion rules have been reviewed.
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


def build_baseline(boards):
    entries = {}
    for board in boards.values():
        values = [row["score"] for row in board["rows"]]
        if len(values) < 2:
            continue
        sd = statistics.stdev(values)
        if sd <= 0:
            continue
        entries[board["family"]] = {
            "mean": statistics.mean(values), "sd": sd,
            "observations": len(values), "sourceBoardId": board["id"],
            "sourceName": board["name"], "frozenAt": now_iso(),
            "referenceModels": [{"key": row["identityKey"], "sourceNameKey": row["key"], "identityRule": row["identityRule"],
                                 "name": row["name"], "provider": row["provider"]}
                                for row in sorted(board["rows"], key=lambda item: item["key"])],
            "referenceScores": {row["identityKey"]: row["score"] for row in board["rows"]},
            "referenceRows": [{"identityKey": row["identityKey"], "name": row["name"],
                                "provider": row["provider"], "score": row["score"]}
                               for row in board["rows"]],
            "sourceSnapshotHash": board["sourceHash"],
            "evaluationVersion": board["evaluationVersion"],
            "evaluationSpecHash": board["evaluationSpecHash"],
            "evaluationSpec": board["evaluationSpec"],
        }
    return {"schema": "ai-creator-radar-unified-baseline/1", "methodVersion": METHOD_VERSION,
            "boards": entries, "categoryAnchors": {}}


def pearson(xs, ys):
    if len(xs) < 3:
        return 0.0
    mx, my = statistics.mean(xs), statistics.mean(ys)
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else 0.0


def rank_values(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    pos = 0
    while pos < len(order):
        end = pos + 1
        while end < len(order) and values[order[end]] == values[order[pos]]:
            end += 1
        rank = (pos + end - 1) / 2
        for j in range(pos, end):
            ranks[order[j]] = rank
        pos = end
    return ranks


def spearman(xs, ys):
    return pearson(rank_values(xs), rank_values(ys))


def fit_line(xs, ys):
    mx, my = statistics.mean(xs), statistics.mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else 0.0
    return slope, my - slope * mx


def calibrate(base_board, source_board, baseline, frozen=None):
    if base_board.get("baselineIssue"):
        return {"status": "uncalibrated", "reason": base_board["baselineIssue"]}
    if source_board.get("baselineIssue"):
        return {"status": "uncalibrated", "reason": source_board["baselineIssue"]}
    base = baseline.get(base_board["family"])
    source = baseline.get(source_board["family"])
    if not base or not source:
        return {"status": "uncalibrated", "reason": "基准数据不足"}
    base_rows = unique_rows_by_identity(base_board)
    source_rows = unique_rows_by_identity(source_board)
    common = sorted(set(base_rows) & set(source_rows))
    if frozen:
        common = [key for key in frozen.get("anchorKeys", []) if key in base_rows and key in source_rows]
        if len(common) < MIN_ANCHORS:
            return {"status": "uncalibrated", "reason": f"冻结校准锚点当前仅 {len(common)} 个，少于 {MIN_ANCHORS} 个",
                    "anchors": len(common), "currentAnchorKeys": common,
                    "frozenAnchorCount": len(frozen.get("anchorKeys", []))}
    elif len(common) < MIN_ANCHORS:
        return {"status": "uncalibrated", "reason": f"共同型号 {len(common)} 个，少于 {MIN_ANCHORS} 个", "anchors": len(common)}
    xs = [(source_rows[k]["score"] - source["mean"]) / source["sd"] for k in common]
    ys = [(base_rows[k]["score"] - base["mean"]) / base["sd"] for k in common]
    if max(xs) - min(xs) < MIN_ANCHOR_SPAN_SD:
        return {"status": "uncalibrated", "reason": "共同型号的能力跨度不足", "anchors": len(common)}
    rho = spearman(xs, ys)
    if frozen:
        slope, intercept = frozen["slope"], frozen["intercept"]
        rmse = math.sqrt(statistics.mean(((slope * x + intercept) - y) ** 2 for x, y in zip(xs, ys)))
    else:
        # Deterministic leave-one-out prediction checks extrapolation/overfit risk.
        predictions = []
        for i in range(len(xs)):
            train_x = xs[:i] + xs[i + 1:]
            train_y = ys[:i] + ys[i + 1:]
            loo_slope, loo_intercept = fit_line(train_x, train_y)
            predictions.append(loo_slope * xs[i] + loo_intercept)
        rmse = math.sqrt(statistics.mean((p - y) ** 2 for p, y in zip(predictions, ys)))
        slope, intercept = fit_line(xs, ys)
    reasons = []
    if rho < MIN_SPEARMAN:
        reasons.append(f"锚点秩相关 {rho:.2f} 低于 {MIN_SPEARMAN:.2f}")
    if rmse > MAX_LOO_RMSE:
        reasons.append(f"留一标准化 RMSE {rmse:.2f} 高于 {MAX_LOO_RMSE:.2f}")
    if slope <= 0:
        reasons.append("映射斜率非正")
    return {
        "status": "calibrated" if not reasons else "uncalibrated",
        "reason": "; ".join(reasons) if reasons else ("冻结映射通过当前锚点漂移检查" if frozen else "同任务共同型号锚点通过初筛"),
        "anchors": len(common), "spearman": round(rho, 4),
        "looRmse": frozen.get("looRmse") if frozen else round(rmse, 4),
        "currentRmse": round(rmse, 4) if frozen else None,
        "slope": slope, "intercept": intercept,
        "baseBoardId": base_board["id"], "sourceBoardId": source_board["id"],
        "anchorKeys": common if not frozen else frozen.get("anchorKeys", []),
        "currentAnchorKeys": common,
        "frozenAnchorCount": len(frozen.get("anchorKeys", [])) if frozen else len(common),
        "frozenAt": frozen.get("frozenAt") if frozen else now_iso(),
        "identityRule": "exact model version ID when mapped; otherwise canonical provider plus exact normalized model name",
        "sourceSnapshotHashes": {"base": base_board["sourceHash"], "source": source_board["sourceHash"]},
        "methodVersion": METHOD_VERSION,
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


def model_ids(row, alias_keys, provider_aliases, known_by_name=None):
    provider = canonical_provider(row.get("provider"), provider_aliases, known_by_name, row.get("name"))[0]
    hits = alias_keys.get((norm(row["name"]), provider), set())
    if len(hits) == 1:
        family_id, version_id = next(iter(hits))
        return family_id, version_id
    # Fallback only on an unambiguous exact model name. Do not merge variants by fuzzy similarity.
    name_hits = set()
    for (name, _provider), identities in alias_keys.items():
        if name == norm(row["name"]):
            name_hits.update(identities)
    if len(name_hits) == 1:
        return next(iter(name_hits))
    return None, None


def exact_model_version(row, alias_keys, provider_aliases):
    provider = canonical_provider(row.get("provider"), provider_aliases)[0]
    hits = alias_keys.get((norm(row.get("name", "")), provider), set())
    versions = {(family_id, version_id) for family_id, version_id in hits if version_id}
    return next(iter(versions)) if len(versions) == 1 else None


def unique_rows_by_identity(board):
    grouped = {}
    for row in board["rows"]:
        grouped.setdefault(row["identityKey"], []).append(row)
    return {key: rows[0] for key, rows in grouped.items() if len(rows) == 1}


def refresh_baseline_audit_fields(entry, current):
    """Refresh identity/version audit metadata without moving frozen moments."""
    for key in ("referenceModels", "referenceScores", "referenceRows", "sourceSnapshotHash",
                "evaluationVersion", "evaluationSpecHash", "evaluationSpec"):
        if key in current:
            entry[key] = current[key]


def validate_source_baseline(board, baseline_boards):
    entry = baseline_boards.get(board["family"])
    if not entry:
        return False, "缺少冻结来源基线"
    if not entry.get("evaluationSpecHash"):
        if entry.get("sourceSnapshotHash") != board["sourceHash"]:
            return False, "旧基线没有评测版本指纹且原快照已变化，需人工重建"
        current = build_baseline({board["family"]: board})["boards"].get(board["family"])
        if not current:
            return False, "无法建立评测版本指纹"
        refresh_baseline_audit_fields(entry, current)
        return True, "从未变化的冻结快照补录评测版本指纹"
    if (entry.get("evaluationVersion") != board["evaluationVersion"]
            or entry.get("evaluationSpecHash") != board["evaluationSpecHash"]):
        return False, "上游评测版本或任务口径已变化，需人工审核并升方法版本"
    return True, "评测版本与冻结基线一致"


def normalized_score(row, board, baseline):
    ref = baseline.get(board["family"])
    if not ref:
        return None, None
    z = (row["score"] - ref["mean"]) / ref["sd"]
    low = high = None
    if row["ciLow"] is not None and row["ciHigh"] is not None:
        low = (row["ciLow"] - ref["mean"]) / ref["sd"]
        high = (row["ciHigh"] - ref["mean"]) / ref["sd"]
    return z, (low, high) if low is not None else None


def entity_task_measure(entity, task_id):
    if entity.get("identityAmbiguous"):
        return None
    evidence = entity["tasks"].get(task_id, [])
    by_source = {}
    for ev in evidence:
        by_source.setdefault(ev["source"], ev)
    if not by_source:
        return None
    measures = list(by_source.values())
    standard_errors = [ev["standardError"] for ev in measures]
    return {
        "score": statistics.mean(ev["normalizedScore"] for ev in measures),
        # With unknown source covariance, use the fully correlated bound (mean SE), not an independence gain.
        "standardError": statistics.mean(standard_errors) if all(se is not None for se in standard_errors) else None,
        "sourceCount": len(by_source), "evidenceCount": len(evidence),
    }


def category_anchor_candidate(category, entity_map):
    task_ids = [task["id"] for task in category["subtasks"]]
    scores = {task_id: {} for task_id in task_ids}
    for key, entity in entity_map.items():
        if entity.get("identityAmbiguous"):
            continue
        for task_id in task_ids:
            measure = entity_task_measure(entity, task_id)
            if measure:
                scores[task_id][key] = measure["score"]
    common = set.intersection(*(set(scores[task_id]) for task_id in task_ids)) if task_ids else set()
    if len(common) < MIN_ANCHORS:
        return None, f"跨子任务共同型号 {len(common)} 个，少于 {MIN_ANCHORS} 个"
    references = {}
    for task_id in task_ids:
        values = [scores[task_id][key] for key in sorted(common)]
        sd = statistics.stdev(values)
        if sd <= 0:
            return None, f"{task_id} 锚点标准差无效"
        references[task_id] = {"mean": statistics.mean(values), "sd": sd}
    anchor_scores = {task_id: {key: scores[task_id][key] for key in sorted(common)} for task_id in task_ids}
    snapshot_hashes = {task_id: sorted({ev["sourceSnapshotHash"] for entity in entity_map.values()
                                       for ev in entity["tasks"].get(task_id, []) if ev.get("sourceSnapshotHash")})
                       for task_id in task_ids}
    return {
        "anchorKeys": sorted(common), "anchorCount": len(common),
        "references": references, "anchorScores": anchor_scores,
        "sourceSnapshotHashes": snapshot_hashes, "frozenAt": now_iso(), "methodVersion": METHOD_VERSION,
        "identityRule": "exact model version ID or canonical provider plus exact normalized model name; unresolved and duplicate identities excluded",
    }, "共同型号达到首轮锚点数量"


def usable_category_anchors(category, entity_map, reference):
    if not reference:
        return False, "跨子任务锚点尚未建立", {}
    if reference.get("methodVersion") != METHOD_VERSION:
        return False, "锚点面板方法版本与当前计分方法不一致，需人工审核连接", {}
    required = max(MIN_ANCHORS, math.ceil(len(reference["anchorKeys"]) * 0.8))
    current_anchors = {}
    for task in category["subtasks"]:
        task_id = task["id"]
        current = {}
        for key in reference["anchorKeys"]:
            entity = entity_map.get(key)
            measure = entity_task_measure(entity, task_id) if entity else None
            if measure:
                current[key] = measure["score"]
        ref = reference["references"][task_id]
        current_anchors[task_id] = {"count": len(current), "keys": sorted(current)}
        if len(current) < required:
            return False, f"{task['name']} 当前共同锚点 {len(current)} 个，少于 {required} 个", current_anchors
        if max(current.values()) - min(current.values()) < MIN_ANCHOR_SPAN_SD * ref["sd"]:
            return False, f"{task['name']} 当前锚点分数跨度不足", current_anchors
    return True, "固定共同型号锚点通过覆盖与跨度检查", current_anchors


def build_rankings(inputs, baseline):
    baseline_boards = baseline.get("boards", {})
    all_specs = [spec for category in CATEGORIES for task in category["subtasks"]
                 for spec in (task["boards"] + task.get("referenceOnlyBoards", []))]
    all_specs.extend(spec for category in CATEGORIES for spec in category.get("referenceOnlyBoards", []))
    provider_aliases = load_vendor_aliases()
    alias_keys = load_models(provider_aliases)
    boards = {}
    for spec in all_specs:
        board = get_board(inputs, spec, provider_aliases, alias_keys)
        if board and board["rows"]:
            boards[board["family"]] = board
    scored_families = {spec[3] for category in CATEGORIES for task in category["subtasks"] for spec in task["boards"]}
    for family in scored_families:
        if family in boards:
            usable, reason = validate_source_baseline(boards[family], baseline_boards)
            boards[family]["baselineUsable"] = usable
            boards[family]["baselineIssue"] = None if usable else reason
    calibrations = {}
    frozen_calibrations = baseline.setdefault("sourceCalibrations", {})
    for category in CATEGORIES:
        for task in category["subtasks"]:
            task_boards = [boards.get(spec[3]) for spec in task["boards"]]
            task_boards = [board for board in task_boards if board]
            audio_mode = task.get("audioMode")
            mismatched = [b for b in task_boards if audio_mode and b.get("audioMode") != audio_mode]
            invalid_baselines = [b for b in task_boards if b not in mismatched and b.get("baselineIssue")]
            if mismatched:
                for board in mismatched:
                    calibrations[f"{category['id']}:{task['id']}:{board['family']}"] = {
                        "status": "uncalibrated", "reason": f"来源音频模式与任务定义 {audio_mode} 不一致或未标注",
                    }
                task_boards = [b for b in task_boards if b not in mismatched]
            if invalid_baselines:
                for board in invalid_baselines:
                    calibrations[f"{category['id']}:{task['id']}:{board['family']}"] = {
                        "status": "uncalibrated", "reason": board["baselineIssue"],
                    }
                task_boards = [b for b in task_boards if b not in invalid_baselines]
            if len(task_boards) > 1:
                base = task_boards[0]
                for source in task_boards[1:]:
                    key = f"{category['id']}:{task['id']}:{source['family']}"
                    frozen = frozen_calibrations.get(key)
                    result = calibrate(base, source, baseline_boards, frozen)
                    if result.get("status") == "calibrated" and not frozen:
                        frozen_calibrations[key] = result
                    calibrations[key] = result

    categories_out = []
    category_anchor_status = {}
    category_anchors = baseline.setdefault("categoryAnchors", {})
    for category in CATEGORIES:
        entity_map = {}
        source_catalog = {}
        if category.get("referenceOnlyBoards"):
            source_catalog["其他参考"] = []
            for spec in category["referenceOnlyBoards"]:
                board = boards.get(spec[3])
                if board:
                    source_catalog["其他参考"].append({
                        "id": board["id"], "name": board["provider"], "url": board["url"],
                        "updatedAt": board["updatedAt"], "status": "reference-only",
                        "reason": category.get("referenceOnlyReason", "该来源不纳入当前计分任务"),
                        "audioMode": board.get("audioMode"),
                        "evaluationVersion": board.get("evaluationVersion"),
                    })
        known_by_name = {}
        for task in category["subtasks"]:
            for spec in task["boards"]:
                board = boards.get(spec[3])
                if not board:
                    continue
                for raw in board["rows"]:
                    canonical, _label, unknown = canonical_provider(raw.get("provider"), provider_aliases)
                    if not canonical.startswith("unknown:") and not unknown:
                        known_by_name.setdefault(norm(raw["name"]), set()).add(canonical)
        ambiguous_names = {name for name, vendors in known_by_name.items() if len(vendors) > 1}
        for task in category["subtasks"]:
            task_id = task["id"]
            available = [boards.get(spec[3]) for spec in task["boards"]]
            available = [board for board in available if board]
            audio_mode = task.get("audioMode")
            mismatched = [b for b in available if audio_mode and b.get("audioMode") != audio_mode]
            invalid_baselines = [b for b in available if b not in mismatched and b.get("baselineIssue")]
            available = [b for b in available if b not in mismatched and b not in invalid_baselines]
            source_catalog[task_id] = []
            for spec in task.get("referenceOnlyBoards", []):
                board = boards.get(spec[3])
                if board:
                    source_catalog[task_id].append({
                        "id": board["id"], "name": board["provider"], "url": board["url"],
                        "updatedAt": board["updatedAt"], "status": "reference-only",
                        "reason": task.get("referenceOnlyReason", "任务模式尚未核实"),
                        "audioMode": board.get("audioMode"),
                        "evaluationVersion": board.get("evaluationVersion"),
                    })
            for board in mismatched:
                source_catalog[task_id].append({
                    "id": board["id"], "name": board["provider"], "url": board["url"],
                    "updatedAt": board["updatedAt"], "status": "reference-only",
                    "reason": f"来源音频模式与任务定义 {audio_mode} 不一致或未标注",
                    "audioMode": board.get("audioMode"),
                    "evaluationVersion": board.get("evaluationVersion"),
                })
            for board in invalid_baselines:
                source_catalog[task_id].append({
                    "id": board["id"], "name": board["provider"], "url": board["url"],
                    "updatedAt": board["updatedAt"], "status": "reference-only",
                    "reason": board["baselineIssue"], "audioMode": board.get("audioMode"),
                    "evaluationVersion": board.get("evaluationVersion"),
                })
            if not available:
                continue
            base = available[0]
            for board in available:
                calibration = None
                if board is not base:
                    calibration = calibrations.get(f"{category['id']}:{task_id}:{board['family']}")
                    if not calibration or calibration.get("status") != "calibrated":
                        source_catalog[task_id].append({
                            "id": board["id"], "name": board["provider"], "url": board["url"],
                            "updatedAt": board["updatedAt"], "status": "reference-only",
                            "reason": (calibration or {}).get("reason", "尚未通过同任务校准"),
                            "audioMode": board.get("audioMode"),
                            "evaluationVersion": board.get("evaluationVersion"),
                        })
                        continue
                source_catalog[task_id].append({
                    "id": board["id"], "name": board["provider"], "url": board["url"],
                    "updatedAt": board["updatedAt"],
                    "status": "calibrated" if calibration else ("base" if len(available) > 1 else "single-source"),
                    "audioMode": board.get("audioMode"),
                    "evaluationVersion": board.get("evaluationVersion"),
                })
                for raw in board["rows"]:
                    z, interval = normalized_score(raw, board, baseline_boards)
                    if z is None:
                        continue
                    se = None
                    if interval:
                        se = (interval[1] - interval[0]) / (2 * 1.96)
                    if calibration:
                        z = calibration["slope"] * z + calibration["intercept"]
                        if interval:
                            interval = (calibration["slope"] * interval[0] + calibration["intercept"],
                                        calibration["slope"] * interval[1] + calibration["intercept"])
                        if se is not None:
                            se = abs(calibration["slope"]) * se + calibration["looRmse"]
                    vendor_id, vendor_label, _ = canonical_provider(raw.get("provider"), provider_aliases, known_by_name, raw.get("name"))
                    family_id, version_id = model_ids(raw, alias_keys, provider_aliases, known_by_name)
                    exact_version = bool(family_id and version_id)
                    entity_key = f"{family_id}:{version_id}" if exact_version else f"name:{norm(raw['name'])}:{vendor_id}"
                    identity_ambiguous = not exact_version and norm(raw["name"]) in ambiguous_names
                    entity = entity_map.setdefault(entity_key, {
                        "name": raw["name"], "provider": vendor_label,
                        "modelFamilyId": family_id, "modelVersionId": version_id,
                        "tasks": {}, "evidence": [], "sources": set(), "rawProviders": set(),
                        "identityAmbiguous": identity_ambiguous,
                    })
                    ev = {
                        "taskId": task_id, "taskName": task["name"], "source": board["provider"],
                        "boardId": board["id"], "rank": raw["rank"], "sourceScore": raw["score"],
                        "normalizedScore": z,
                        "sourceCiLow": raw["ciLow"], "sourceCiHigh": raw["ciHigh"],
                        "normalizedCiLow": interval[0] if interval else None,
                        "normalizedCiHigh": interval[1] if interval else None,
                        "standardError": se, "comparisons": raw["comparisons"],
                        "evaluationVersion": board["evaluationVersion"],
                        "evaluationSpecHash": board["evaluationSpecHash"],
                        "modelProvider": raw["provider"], "sourceSnapshotHash": board["sourceHash"],
                        "url": raw["detailUrl"] or board["url"], "updatedAt": board["updatedAt"],
                    }
                    entity["evidence"].append(ev)
                    entity["sources"].add(board["provider"])
                    entity["rawProviders"].add(raw["provider"])
                    entity["tasks"].setdefault(task_id, []).append(ev)

        anchor_ref = category_anchors.get(category["id"])
        if anchor_ref and not anchor_ref.get("methodVersion"):
            # v2 migration: this panel was just created by the first local implementation and had no version field.
            anchor_ref["methodVersion"] = METHOD_VERSION
        if len(category["subtasks"]) > 1 and not anchor_ref:
            candidate, reason = category_anchor_candidate(category, entity_map)
            if candidate:
                anchor_ref = candidate
                category_anchors[category["id"]] = candidate
        elif len(category["subtasks"]) == 1:
            reason = "单一子任务，无跨任务刻度换算"
        else:
            reason = "沿用已冻结的共同型号锚点"
        if len(category["subtasks"]) == 1:
            anchor_ready, anchor_reason, current_anchors = True, reason, {}
        else:
            anchor_ready, anchor_reason, current_anchors = usable_category_anchors(category, entity_map, anchor_ref)
        category_anchor_status[category["id"]] = {"status": "aligned" if anchor_ready else "provisional", "reason": anchor_reason,
                                                   "anchorCount": anchor_ref.get("anchorCount", 0) if anchor_ref else 0,
                                                   "currentAnchors": current_anchors}

        rows = []
        for entity in entity_map.values():
            if entity.get("identityAmbiguous"):
                ambiguous_subtasks = []
                for task in category["subtasks"]:
                    evidence = entity["tasks"].get(task["id"], [])
                    if not evidence:
                        continue
                    by_source = {}
                    for ev in evidence:
                        by_source.setdefault(ev["source"], ev)
                    ambiguous_subtasks.append({
                        "id": task["id"], "name": task["name"],
                        "score": round(50 + 15 * statistics.mean(ev["normalizedScore"] for ev in by_source.values()), 2),
                        "sourceCount": len(by_source), "evidenceCount": len(evidence),
                    })
                rows.append({
                    "name": entity["name"], "provider": entity["provider"],
                    "modelFamilyId": entity["modelFamilyId"], "modelVersionId": entity["modelVersionId"],
                    "score": None, "z": None, "scoreInterval": None, "scoreType": "unresolved-identity",
                    "status": "provisional", "statusLabel": "厂商/型号身份冲突，待核验",
                    "identityStatus": "ambiguous",
                    "coverage": round(len(ambiguous_subtasks) / len(category["subtasks"]), 3),
                    "measuredTasks": len(ambiguous_subtasks),
                    "totalTasks": len(category["subtasks"]), "sourceCount": len(entity["sources"]),
                    "crossSourceTasks": 0, "subtasks": ambiguous_subtasks, "evidence": entity["evidence"],
                })
                continue
            task_measures = []
            subtasks = []
            cross_source_tasks = 0
            for task in category["subtasks"]:
                measured = entity_task_measure(entity, task["id"])
                if not measured:
                    continue
                if measured["sourceCount"] >= 2:
                    cross_source_tasks += 1
                task_z = measured["score"]
                task_se = measured["standardError"]
                ref = (anchor_ref or {}).get("references", {}).get(task["id"])
                if len(category["subtasks"]) > 1 and anchor_ready and ref:
                    task_z = (task_z - ref["mean"]) / ref["sd"]
                    if task_se is not None:
                        task_se /= ref["sd"]
                task_measures.append({"score": task_z, "standardError": task_se})
                subtasks.append({"id": task["id"], "name": task["name"],
                                 "score": round(50 + 15 * task_z, 2), "sourceCount": measured["sourceCount"],
                                 "evidenceCount": measured["evidenceCount"]})
            if not task_measures:
                continue
            can_score_category = len(category["subtasks"]) == 1 or anchor_ready
            z = statistics.mean(item["score"] for item in task_measures) if can_score_category else None
            coverage = len(task_measures) / len(category["subtasks"])
            source_count = len(entity["sources"])
            all_task_errors = all(item["standardError"] is not None for item in task_measures)
            composite_ci = None
            if all_task_errors and can_score_category:
                # Conservative fully-correlated bound across measured tasks; baseline-panel uncertainty is not included.
                composite_se = statistics.mean(item["standardError"] for item in task_measures)
                half_width = 1.96 * 15 * composite_se
                score = 50 + 15 * z
                composite_ci = [round(score - half_width, 2), round(score + half_width, 2)]
            formal = (source_count >= 2 and coverage >= (2 / 3) and cross_source_tasks >= 1
                      and can_score_category and composite_ci is not None)
            if formal:
                status_label = "达到 v4 公式门槛；方法复核中"
            elif not can_score_category:
                status_label = "跨任务锚点不足，暂不能合榜"
            elif source_count < 2 or cross_source_tasks == 0:
                status_label = "单来源/缺少交叉验证"
            elif composite_ci is None:
                status_label = "区间证据不足"
            else:
                status_label = "任务覆盖不足"
            rows.append({
                "name": entity["name"], "provider": entity["provider"],
                "modelFamilyId": entity["modelFamilyId"], "modelVersionId": entity["modelVersionId"],
                "score": round(50 + 15 * z, 2) if z is not None else None,
                "z": round(z, 5) if z is not None else None, "scoreInterval": composite_ci,
                "scoreType": "anchor-aligned-index" if can_score_category else "unavailable-without-anchor",
                "status": "ranked" if formal else "provisional", "statusLabel": status_label,
                "coverage": round(coverage, 3), "measuredTasks": len(task_measures),
                "totalTasks": len(category["subtasks"]), "sourceCount": source_count,
                "crossSourceTasks": cross_source_tasks,
                "subtasks": subtasks, "evidence": entity["evidence"],
            })
        # Order all scored records by the same experimental index. Evidence
        # status remains a separate label; it must not silently override score.
        rows.sort(key=lambda row: (row["score"] is None, -(row["score"] or 0),
                                   row["name"].casefold(), (row.get("provider") or "").casefold()))
        formal_rows = [row for row in rows if row["status"] == "ranked"]
        for row in formal_rows:
            low, high = row["scoreInterval"]
            better_certain = sum(1 for other in formal_rows if other is not row and other["scoreInterval"][0] > high)
            could_outrank = sum(1 for other in formal_rows if other is not row and other["scoreInterval"][1] >= low)
            row["rankRange"] = [1 + better_certain, 1 + could_outrank]
        formal_rank = 0
        provisional_rank = 0
        for row in rows:
            if row["status"] == "ranked":
                formal_rank += 1
                row["rank"] = formal_rank
                row["provisionalOrder"] = None
            else:
                row["rank"] = None
                if row["score"] is not None:
                    provisional_rank += 1
                    row["provisionalOrder"] = provisional_rank
                else:
                    row["provisionalOrder"] = None
        primary_leaderboards = None
        if category["id"] == "video":
            primary_leaderboards = {
                "text-to-video-audio": build_primary_leaderboard(category["id"], inputs, provider_aliases, alias_keys),
                "image-to-video-audio": build_primary_leaderboard(category["id"], inputs, provider_aliases, alias_keys, config_key="video-i2v"),
            }
            primary_leaderboard = primary_leaderboards["text-to-video-audio"]
        else:
            primary_leaderboard = build_primary_leaderboard(category["id"], inputs, provider_aliases, alias_keys)
        categories_out.append({
            "id": category["id"], "name": category["name"], "description": category["description"],
            "status": "ranked" if any(r["status"] == "ranked" for r in rows) else "provisional",
            "statusLabel": "探索性试算：含达到 v4 公式门槛与待交叉验证记录" if any(r["status"] == "ranked" for r in rows) else "探索性试算：当前证据未达到 v4 综合门槛",
            "primaryLeaderboard": primary_leaderboard,
            **({"primaryLeaderboards": primary_leaderboards} if primary_leaderboards else {}),
            "anchorStatus": category_anchor_status[category["id"]],
            "subtasks": [{"id": t["id"], "name": t["name"], "audioMode": t.get("audioMode")} for t in category["subtasks"]],
            "sources": source_catalog, "rows": rows,
        })
    return {
        "schema": "ai-creator-radar-unified-rankings/1",
        "methodVersion": METHOD_VERSION, "calculatedAt": now_iso(),
        "displayPolicy": "The public-facing top ten use source-native primary leaderboards. Raw source rank, score, interval, and sample count are retained without cross-source score aggregation. The earlier v4 composite remains exploratory audit output only.",
        "scale": {"formula": "50 + 15 × z", "reference": "frozen source baselines and fixed category anchor panel; relative index, not accuracy or cross-category score"},
        "method": "Source scores are standardized against frozen source-board baselines. Calibration anchors use exact model-version IDs or canonical provider plus exact normalized model names; unresolved and duplicate identities are excluded. Evaluation-version or methodology-fingerprint changes suspend a source pending review. Different sources merge only after same-task anchor calibration passes. Multi-task categories require a frozen panel of at least 20 exact common model identities; each task is standardized against that same panel before equal-weight aggregation. Missing tasks are not zero-filled. Conditional approximate intervals are error hints, not coverage-calibrated 95% confidence intervals; they use a fully-correlated conservative bound from source intervals and calibration residuals and exclude anchor-panel and calibration-coefficient uncertainty. Formal ranks require source, task-coverage, anchor, and interval gates.",
        "thresholds": {"minAnchors": MIN_ANCHORS, "minSpearman": MIN_SPEARMAN, "maxLeaveOneOutRmse": MAX_LOO_RMSE, "minAnchorSpanSD": MIN_ANCHOR_SPAN_SD, "formalSourceFamilies": 2, "formalTaskCoverage": 2/3, "requiresCompositeInterval": True},
        "calibrations": calibrations, "categoryAnchors": category_anchor_status, "categories": categories_out,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    inputs = load_inputs()
    specs = [spec for category in CATEGORIES for task in category["subtasks"] for spec in task["boards"]]
    provider_aliases = load_vendor_aliases()
    alias_keys = load_models(provider_aliases)
    boards = {spec[3]: get_board(inputs, spec, provider_aliases, alias_keys) for spec in specs}
    boards = {key: value for key, value in boards.items() if value and value["rows"]}
    vendor_alias_hash = hashlib.sha256(VENDOR_ALIASES.read_bytes()).hexdigest()
    if BASELINE.exists():
        baseline = json.loads(BASELINE.read_text())
        prior_method = baseline.get("methodVersion")
        prior_alias_hash = baseline.get("vendorAliasHash")
        if prior_alias_hash and prior_alias_hash != vendor_alias_hash and prior_method == METHOD_VERSION:
            raise SystemExit("Vendor alias config changed without a method-version bump; review and version the baseline migration first.")
        if prior_method and prior_method != METHOD_VERSION:
            baseline.setdefault("history", []).append({
                "methodVersion": prior_method, "archivedAt": now_iso(),
                "categoryAnchors": baseline.get("categoryAnchors", {}),
                "sourceCalibrations": baseline.get("sourceCalibrations", {}),
            })
            baseline["categoryAnchors"] = {}
            baseline["sourceCalibrations"] = {}
            baseline["methodVersion"] = METHOD_VERSION
        baseline_boards = baseline.get("boards", {})
        # Freeze newly encountered pools once; never silently move an existing scale.
        current_baselines = build_baseline(boards)["boards"]
        # The v4 migration changes anchor identity and adds explicit evaluation
        # fingerprints. Backfill only when the exact source snapshot is unchanged.
        if prior_method and prior_method != METHOD_VERSION:
            for key, current in current_baselines.items():
                frozen = baseline_boards.get(key)
                if frozen and frozen.get("sourceSnapshotHash") == current.get("sourceSnapshotHash"):
                    refresh_baseline_audit_fields(frozen, current)
        added = {key: value for key, value in current_baselines.items() if key not in baseline_boards}
        if added:
            baseline_boards.update(added)
        # Backfill the original frozen panel only when the current snapshot reproduces its stored moments exactly.
        for key, entry in baseline_boards.items():
            current = current_baselines.get(key)
            if (current and "referenceModels" not in entry
                    and current["observations"] == entry["observations"]
                    and abs(current["mean"] - entry["mean"]) < 1e-10
                    and abs(current["sd"] - entry["sd"]) < 1e-10):
                entry["referenceModels"] = current["referenceModels"]
            if (current and "referenceScores" not in entry
                    and current["observations"] == entry["observations"]
                    and abs(current["mean"] - entry["mean"]) < 1e-10
                    and abs(current["sd"] - entry["sd"]) < 1e-10):
                entry["referenceScores"] = current["referenceScores"]
                entry["sourceSnapshotHash"] = current["sourceSnapshotHash"]
            BASELINE.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n")
    else:
        baseline = build_baseline(boards)
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n")
    baseline["methodVersion"] = METHOD_VERSION
    baseline["vendorAliasHash"] = vendor_alias_hash
    result = build_rankings(inputs, baseline)
    result["vendorAliasHash"] = vendor_alias_hash
    BASELINE.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {args.output.relative_to(ROOT)}")
    for category in result["categories"]:
        ranked = sum(row["status"] == "ranked" for row in category["rows"])
        print(f"{category['name']}: {len(category['rows'])} rows, {ranked} passed the v4 formula gate (exploratory only), status={category['statusLabel']}")
    for key, value in result["calibrations"].items():
        print(f"{key}: {value['status']} ({value['reason']})")


if __name__ == "__main__":
    main()
