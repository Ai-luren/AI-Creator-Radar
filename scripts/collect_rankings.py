#!/usr/bin/env python3
"""Fetch the public FAI.Fashion model leaderboard snapshot for local display."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://fai.fashion/api/site/observatory/model-snapshot"
PAGE_URL = "https://fai.fashion/leaderboard"
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
              if board.get("kind") in {"video", "image"}]
    if not boards or any(not board["rows"] for board in boards):
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


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(rendered)
        temp_path = Path(tmp.name)
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch the public FAI.Fashion video and image leaderboard snapshot.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report without writing JSON.")
    args = parser.parse_args()
    snapshot = fetch_snapshot()
    print(f"Leaderboard snapshot: {len(snapshot['boards'])} image/video boards; "
          f"{sum(len(board['rows']) for board in snapshot['boards'])} rows; "
          f"source snapshot {snapshot.get('publishedAt')}; checked {snapshot.get('sourceCheckedAt')}.")
    if not args.dry_run:
        for output in OUTPUTS:
            write_json(output, snapshot)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Leaderboard collection failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
