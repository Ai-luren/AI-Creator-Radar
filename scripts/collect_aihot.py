#!/usr/bin/env python3
"""Fetch the latest selected AIHOT items into a small local site snapshot."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site" / "data-v4" / "aihot-items.json"
API_URL = "https://aihot.news/api/v1/items?mode=selected&window=24h&limit=20"
ACTOR = "0b482b0d-92b0-493c-8b24-5cac9f005987"


def read_existing() -> dict:
    try:
        value = json.loads(OUTPUT.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def atomic_write(payload: dict) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".aihot-items-", suffix=".json", dir=OUTPUT.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, OUTPUT)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def collect(dry_run: bool = False) -> tuple[int, bool]:
    previous = read_existing()
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "User-Agent": f"aihot-api/2.0.0 aihot-actor/{ACTOR}",
    }
    if previous.get("etag"):
        headers["If-None-Match"] = previous["etag"]
    request = urllib.request.Request(API_URL, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                body = gzip.decompress(body)
            data = json.loads(body.decode("utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("items"), list):
                raise ValueError("AIHOT response is missing an items array")
            payload = {
                "source": "AIHOT",
                "sourceUrl": "https://aihot.news",
                "attribution": {"name": "AIHOT", "url": "https://aihot.news"},
                "window": "24h",
                "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "etag": response.headers.get("ETag", ""),
                "schemaVersion": data.get("schemaVersion"),
                "page": data.get("page", {}),
                "items": data["items"],
            }
    except urllib.error.HTTPError as error:
        if error.code != 304:
            raise
        if not previous.get("items"):
            raise RuntimeError("AIHOT returned 304 but no existing snapshot is available") from error
        payload = {**previous, "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        if not dry_run:
            atomic_write(payload)
        return len(payload["items"]), True

    if not dry_run:
        atomic_write(payload)
    return len(payload["items"]), False


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch AIHOT selected items for the V4 preview.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without writing the snapshot.")
    args = parser.parse_args()
    count, unchanged = collect(dry_run=args.dry_run)
    action = "validated; unchanged (304)" if unchanged else "validated"
    if not args.dry_run:
        action += f" and wrote {OUTPUT.relative_to(ROOT)}"
    print(f"AIHOT: {count} items {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
