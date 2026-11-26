#!/usr/bin/env python3
"""Refresh AIPick topic picks and hot topics for the creator radar."""

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
OUTPUT = ROOT / "site" / "data" / "aipick-data.json"
ENDPOINTS = {
    "items": "https://aipick.news/api/v1/items?mode=selected&window=7d&limit=30",
    "hotTopics": "https://aipick.news/api/v1/hot-topics",
}


def read_existing() -> dict:
    try:
        value = json.loads(OUTPUT.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def request_json(url: str, etag: str = "") -> tuple[dict | None, str, bool]:
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "User-Agent": "AI-Creator-Radar/1.0",
    }
    if etag:
        headers["If-None-Match"] = etag
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                body = gzip.decompress(body)
            data = json.loads(body.decode("utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("items"), list):
                raise ValueError("AIPick response is missing an items array")
            return data, response.headers.get("ETag", ""), False
    except urllib.error.HTTPError as error:
        if error.code == 304:
            return None, etag, True
        raise


def atomic_write(payload: dict) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".aipick-data-", suffix=".json", dir=OUTPUT.parent)
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


def collect(dry_run: bool = False) -> dict:
    previous = read_existing()
    etags = previous.get("etags", {}) if isinstance(previous.get("etags"), dict) else {}
    payload = {
        "source": "AIPick",
        "sourceUrl": "https://aipick.news",
        "attribution": {"name": "AIPick", "url": "https://aipick.news"},
        "window": "7d",
        "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "etags": dict(etags),
        "items": previous.get("items", []),
        "hotTopics": previous.get("hotTopics", []),
        "unchanged": [],
        "errors": [],
    }
    for key, url in ENDPOINTS.items():
        try:
            data, etag, unchanged = request_json(url, etags.get(key, ""))
            if unchanged:
                payload["unchanged"].append(key)
                continue
            if key == "items":
                payload["items"] = data["items"]
            else:
                payload["hotTopics"] = data["items"]
            payload["etags"][key] = etag
        except Exception as error:
            payload["errors"].append(f"{key}: {error}")
            if not payload[key]:
                raise RuntimeError(f"{key} failed and no previous snapshot exists") from error
    if not dry_run:
        atomic_write(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh AIPick video topic data for the creator radar.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without writing the snapshot.")
    args = parser.parse_args()
    data = collect(dry_run=args.dry_run)
    action = "validated without writing" if args.dry_run else f"saved to {OUTPUT.relative_to(ROOT)}"
    print(f"AIPick: {len(data['items'])} picks, {len(data['hotTopics'])} hot topics {action}")
    if data["unchanged"]:
        print("Unchanged via ETag:", ", ".join(data["unchanged"]))
    if data["errors"]:
        print("Warnings:", "; ".join(data["errors"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
