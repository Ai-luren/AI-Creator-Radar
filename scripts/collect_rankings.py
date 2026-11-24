#!/usr/bin/env python3
"""Fetch public FAI.Fashion and Arena leaderboard snapshots."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://fai.fashion/api/site/observatory/model-snapshot"
PAGE_URL = "https://fai.fashion/leaderboard"
ARENA_DATASET = "lmarena-ai/leaderboard-dataset"
ARENA_DATASET_URL = "https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset"
ARENA_ROWS_URL = "https://datasets-server.huggingface.co/rows"
ARENA_BOARDS = (
    ("arena-text-to-image", "文生图 · Arena", "text_to_image", "https://arena.ai/leaderboard/image/text-to-image"),
    ("arena-image-edit", "图像编辑 · Arena", "image_edit", "https://arena.ai/leaderboard/image/image-edit/single-image"),
    ("arena-text-to-video", "文生视频 · Arena", "text_to_video", "https://arena.ai/leaderboard/video/text-to-video"),
    ("arena-image-to-video", "图生视频 · Arena", "image_to_video", "https://arena.ai/leaderboard/video/image-to-video"),
    ("arena-video-edit", "视频编辑 · Arena", "video_edit", "https://arena.ai/leaderboard/video/video-edit"),
    ("arena-webdev", "文字生成网页 · Arena", "webdev", "https://arena.ai/leaderboard/code/webdev/frontend"),
)
OUTPUTS = (ROOT / "site/data/reference-rankings.json", ROOT / "site/data-v3/reference-rankings.json")
MAX_BYTES = 5 * 1024 * 1024


def compact_board(board: dict) -> dict:
    rows = []
    for item in board.get("rows", []):
        tool = item.get("tool") or {}
        measure = item.get("measurement") or {}
        rows.append({
            "rank": item.get("rank"),
            "name": tool.get("name") or "未命名模型",
            "provider": tool.get("provider") or "厂商待确认",
            "releasedAt": tool.get("releasedAt"),
            "detailsUrl": tool.get("officialUrl"),
            "elo": item.get("elo"),
            "comparisons": item.get("comparisons"),
            "ciLow": item.get("ciLow"),
            "ciHigh": item.get("ciHigh"),
            "price": item.get("price"),
            "priceUnit": item.get("priceUnit"),
            "openWeights": item.get("openWeights"),
        })
    return {
        "id": board.get("id"),
        "name": board.get("name"),
        "kind": board.get("kind"),
        "task": board.get("task"),
        "audioMode": board.get("audioMode"),
        "version": board.get("version"),
        "source": board.get("source") or {},
        "rows": rows,
    }


def build_snapshot(payload: dict, fetched_at: str) -> dict:
    if not isinstance(payload, dict) or not str(payload.get("schema", "")).startswith("fai-published-model-board-snapshot/"):
        raise ValueError("Unexpected FAI snapshot schema")
    sync = payload.get("synchronization") or {}
    boards = [compact_board(board) for board in payload.get("boards", [])
              if board.get("kind") in {"video", "image", "speech"}
              and board.get("rows")]
    required_kinds = {board.get("kind") for board in boards}
    if not {"video", "image"}.issubset(required_kinds):
        raise ValueError("Snapshot is missing video or image ranking rows")
    return {
        "schema": "ai-creator-radar-reference-rankings/1",
        "provider": "FAI.Fashion",
        "providerUrl": PAGE_URL,
        "sourceUrl": SOURCE_URL,
        "publishedAt": payload.get("publishedAt"),
        "fetchedAt": fetched_at,
        "sourceCheckedAt": sync.get("lastCheckedAt"),
        "sourceStatus": sync.get("status"),
        "note": "第三方评测榜单的公开快照。名次与 Elo 按各自任务和原榜版本保留，不跨任务合并；模型资料链接不等同于厂商官方认证。",
        "boards": boards,
    }


def fetch_snapshot() -> dict:
    request = urllib.request.Request(SOURCE_URL, headers={
        "User-Agent": "AI-Creator-Radar/2.0 (+https://github.com/Ai-luren/AI-Creator-Radar)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(request, timeout=25) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("Leaderboard snapshot exceeds 5 MB safety limit")
        payload = json.loads(body.decode("utf-8"))
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return build_snapshot(payload, fetched_at)


def compact_arena_row(row: dict) -> dict:
    license_name = row.get("license")
    return {
        "rank": row.get("rank"),
        "name": row.get("model_name") or "未命名模型",
        "provider": row.get("organization") or "厂商待确认",
        "releasedAt": None,
        "elo": row.get("rating"),
        "comparisons": row.get("vote_count"),
        "ciLow": row.get("rating_lower"),
        "ciHigh": row.get("rating_upper"),
        "price": None,
        "priceUnit": None,
        "openWeights": None,
        "license": license_name,
    }


def fetch_arena_board(config: str, board_id: str, name: str, url: str) -> dict:
    rows = []
    offset = 0
    total = None
    while total is None or offset < total:
        query = urllib.parse.urlencode({
            "dataset": ARENA_DATASET,
            "config": config,
            "split": "latest",
            "offset": offset,
            "length": 100,
        })
        request = urllib.request.Request(ARENA_ROWS_URL + "?" + query, headers={
            "User-Agent": "AI-Creator-Radar/2.0 (+https://github.com/Ai-luren/AI-Creator-Radar)",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(request, timeout=25) as response:
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError(f"Arena {config} response exceeds 5 MB safety limit")
            payload = json.loads(body.decode("utf-8"))
        total = int(payload.get("num_rows_total", 0))
        rows.extend(item.get("row", {}) for item in payload.get("rows", []))
        offset += len(payload.get("rows", []))
        if not payload.get("rows"):
            break
    publish_dates = [row.get("leaderboard_publish_date") or "" for row in rows if row.get("category") == "overall"]
    rows = [compact_arena_row(row) for row in rows if row.get("category") == "overall"]
    if not rows:
        raise ValueError(f"Arena {config} has no overall rows")
    return {
        "id": board_id,
        "name": name,
        "kind": "arena",
        "task": config,
        "version": "Arena latest",
        "source": {
            "id": "arena",
            "name": "Arena",
            "url": url,
            "providerUrl": "https://arena.ai/blog/arena-leaderboard-dataset",
            "datasetUrl": ARENA_DATASET_URL,
            "license": "CC BY 4.0",
        },
        "publishedAt": max(publish_dates, default=""),
        "rows": rows,
    }


def fetch_arena_boards() -> list[dict]:
    boards = []
    for board_id, name, config, url in ARENA_BOARDS:
        boards.append(fetch_arena_board(config, board_id, name, url))
    return boards


def merge_reference_boards(snapshot: dict, arena_boards: list[dict], cached_boards: list[dict] | None = None) -> dict:
    snapshot = dict(snapshot)
    boards = list(snapshot.get("boards", []))
    board_ids = {board.get("id") for board in boards}

    cached_boards = cached_boards or []
    # Keep dated/supplemental snapshots when the live FAI feed does not
    # publish those board IDs. Fresh FAI boards win when an ID is present in
    # both the current feed and the cached snapshot.
    for board in cached_boards:
        if (board.get("source") or {}).get("id") == "arena":
            continue
        if board.get("id") and board["id"] not in board_ids:
            boards.append(board)
            board_ids.add(board["id"])

    # Fresh Arena boards win over cached versions.
    for board in arena_boards:
        if board.get("id") and board["id"] not in board_ids:
            boards.append(board)
            board_ids.add(board["id"])

    # Preserve any cached Arena board that was not refreshed this run.
    for board in cached_boards:
        if (board.get("source") or {}).get("id") != "arena":
            continue
        if board.get("id") and board["id"] not in board_ids:
            boards.append(board)
            board_ids.add(board["id"])

    snapshot["boards"] = boards
    return snapshot


def cached_reference_boards(path: Path) -> list[dict]:
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return cached.get("boards", [])


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(rendered)
        temp_path = Path(tmp.name)
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch FAI.Fashion image/video/speech and Arena public leaderboard snapshots.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report without writing JSON.")
    args = parser.parse_args()
    snapshot = fetch_snapshot()
    try:
        arena_boards = fetch_arena_boards()
        print(f"Arena snapshot: {len(arena_boards)} boards; "
              f"{sum(len(board['rows']) for board in arena_boards)} rows; "
              f"source {ARENA_DATASET} ({ARENA_DATASET_URL}).")
    except Exception as exc:
        print(f"Arena collection warning: {type(exc).__name__}: {exc}; retaining the last successful Arena snapshot.", file=sys.stderr)
        arena_boards = []
    kinds = ", ".join(sorted({board["kind"] for board in snapshot["boards"]}))
    print(f"Leaderboard snapshot: {len(snapshot['boards'])} FAI boards ({kinds}); "
          f"{sum(len(board['rows']) for board in snapshot['boards'])} rows; "
          f"source snapshot {snapshot.get('publishedAt')}; checked {snapshot.get('sourceCheckedAt')}.")
    if not args.dry_run:
        for output in OUTPUTS:
            cached_boards = cached_reference_boards(output)
            updated = merge_reference_boards(snapshot, arena_boards, cached_boards)
            write_json(output, updated)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Leaderboard collection failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
