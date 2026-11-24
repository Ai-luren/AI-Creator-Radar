#!/usr/bin/env python3
"""Check official model-card, API, demo and tutorial links without editing them."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import socket
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
PRACTICE_FILE = ROOT / "site/data-v4/model-practice.json"
TUTORIALS_FILE = ROOT / "site/data/tutorials.json"
OUTPUT_FILE = ROOT / "site/data-v4/model-resource-status.json"
TIMEOUT_SECONDS = 10
USER_AGENT = "AI-Creator-Radar/2.0 (+https://github.com/Ai-luren/AI-Creator-Radar)"


def normalize_url(url: str) -> str:
    parts = urlsplit(str(url).strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def classify_status(status: int | None, error: str = "") -> str:
    if status is None:
        return "unknown"
    if 200 <= status < 400:
        return "available"
    if status in {401, 403, 407, 429, 451}:
        return "restricted"
    if status in {404, 410}:
        return "missing"
    if status >= 500:
        return "server-error"
    return "unknown"


def _fetch_status(url: str, method: str = "HEAD") -> tuple[int | None, str, str]:
    request = urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"} if method == "GET" else {"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.geturl(), ""
    except urllib.error.HTTPError as exc:
        return exc.code, exc.geturl(), ""
    except (urllib.error.URLError, TimeoutError, socket.timeout, ValueError) as exc:
        return None, url, type(exc).__name__


def probe(url: str) -> dict:
    normalized = normalize_url(url)
    parts = urlsplit(normalized)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        status, final_url, error = None, normalized, "invalid-url"
    else:
        status, final_url, error = _fetch_status(normalized, "HEAD")
        if status in {403, 404, 405, 410, 429, 501}:
            get_status, get_url, get_error = _fetch_status(normalized, "GET")
            if get_status is not None:
                status, final_url, error = get_status, get_url, get_error
            elif status in {404, 410}:
                status, final_url, error = None, get_url, get_error or "head-mismatch-get-unreachable"
    return {
        "url": normalized,
        "status": classify_status(status, error),
        "httpStatus": status,
        "finalUrl": final_url,
        "errorType": error,
    }


def gather_resources(practice: dict, tutorials: list[dict]) -> list[dict]:
    resources: dict[str, dict] = {}

    def add(url: str, ref: dict) -> None:
        if not url:
            return
        normalized = normalize_url(url)
        if not normalized:
            return
        item = resources.setdefault(normalized, {"url": normalized, "references": []})
        item["references"].append(ref)

    for model in practice.get("models", []):
        identity = {"model": model.get("model", ""), "vendor": model.get("vendor", "")}
        for field, label in (("officialUrl", "模型说明"), ("apiUrl", "API"), ("demoUrl", "官方演示"), ("entryUrl", "官方体验")):
            add(model.get(field, ""), {**identity, "kind": label})
    for case in practice.get("cases", []):
        add(case.get("url", ""), {"model": case.get("model", ""), "vendor": case.get("vendor", ""), "kind": "官方演示"})
    for tutorial in tutorials:
        if tutorial.get("official") is True:
            add(tutorial.get("url", ""), {"model": tutorial.get("model", ""), "vendor": tutorial.get("vendor", ""), "kind": "官方教程"})
    return [resources[key] for key in sorted(resources)]


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(rendered)
        temp_path = Path(tmp.name)
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the reachability of official model resource links.")
    parser.add_argument("--dry-run", action="store_true", help="List links without making requests or writing data.")
    args = parser.parse_args()
    practice = json.loads(PRACTICE_FILE.read_text(encoding="utf-8"))
    tutorials = json.loads(TUTORIALS_FILE.read_text(encoding="utf-8"))
    resources = gather_resources(practice, tutorials)
    if args.dry_run:
        print(f"Model resources: {len(resources)} unique URLs from official model cards, demos and tutorials.")
        return 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda item: {**item, **probe(item["url"])}, resources))
    counts: dict[str, int] = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    payload = {
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "practiceUpdatedAt": practice.get("updatedAt", ""),
        "total": len(results),
        "counts": counts,
        "results": results,
        "method": "HTTP HEAD; GET range fallback where HEAD is unsupported. Restricted, rate-limited or unreachable pages are not marked as dead.",
    }
    write_json(OUTPUT_FILE, payload)
    print("Model resources checked: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
