#!/usr/bin/env python3
"""Collect recent model-evaluation candidates from AIPick and public Sogou results."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS_PATH = ROOT / "site/data-v3/models.json"
UPDATES_PATH = ROOT / "site/data-v3/model-updates.json"
AIPICK_PATH = ROOT / "site/data-v4/aipick-data.json"
OUTPUT = ROOT / "site/data-v4/model-evaluations.json"
SOGOU_BASE = "https://weixin.sogou.com/weixin"
MAX_BYTES = 4 * 1024 * 1024
RELEASE_WINDOW_DAYS = 21
SEARCH_INTERVAL = timedelta(hours=24)
CAPTCHA_COOLDOWN = timedelta(hours=24)
MAX_SEARCHES_PER_RUN = 3
EVALUATION_TERMS = re.compile(
    r"评测|测评|实测|横评|对比|体验|测试|评估|上手|试用|试了|跑分|实战|pk|vs",
    re.IGNORECASE,
)
CAPTCHA_TERMS = ("验证码", "您的正常行为", "antispider", "verifycode")


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(value or "").casefold())


def secure_url(value: str | None) -> str | None:
    if not value:
        return None
    value = str(value).strip()
    if value.startswith("http://"):
        value = "https://" + value[7:]
    try:
        parsed = urllib.parse.urlparse(value)
    except ValueError:
        return None
    return value if parsed.scheme == "https" and parsed.netloc else None


def match_model(update: dict, models: list[dict]) -> dict | None:
    model_id = update.get("modelId")
    if model_id:
        match = next((model for model in models if model.get("id") == model_id), None)
        if match:
            return match
    needle = normalize(update.get("modelName", ""))
    if not needle:
        return None
    candidates = [
        model for model in models
        if normalize(model.get("name", "")) in needle or needle in normalize(model.get("name", ""))
    ]
    return max(candidates, key=lambda model: len(normalize(model.get("name", ""))), default=None)


def recent_targets(models: list[dict], updates: list[dict], now: datetime) -> list[dict]:
    model_map = {model.get("id"): model for model in models if model.get("id")}
    cutoff = now - timedelta(days=RELEASE_WINDOW_DAYS)
    latest: dict[str, dict] = {}
    for update in updates:
        if update.get("category") not in {"video", "image"}:
            continue
        if update.get("updateType") not in {"release", "model-release", "model-card"}:
            continue
        published = parse_datetime(update.get("publishedAt"))
        if not published or published < cutoff or published > now + timedelta(days=1):
            continue
        model = match_model(update, models)
        model_id = (model or {}).get("id") or update.get("modelId")
        base_name = (model or {}).get("name") or update.get("modelName") or update.get("title") or "新模型"
        version = str((model or {}).get("version") or "").strip()
        name = base_name if not version or normalize(version) in normalize(base_name) else f"{base_name} {version}"
        target_id = str(model_id or "model-" + normalize(name))
        candidate = {
            "id": target_id,
            "modelId": model_id,
            "name": name,
            "vendor": update.get("vendor") or (model or {}).get("vendor") or "厂商待确认",
            "category": update["category"],
            "releasedAt": iso(published),
            "releaseTitle": update.get("title") or name,
            "aliases": list(dict.fromkeys([name, base_name, update.get("modelName", "")])),
        }
        if target_id not in latest or published > parse_datetime(latest[target_id]["releasedAt"]):
            latest[target_id] = candidate
        elif update.get("modelName") and update["modelName"] not in latest[target_id]["aliases"]:
            latest[target_id]["aliases"].append(update["modelName"])
        if update.get("title") and update["title"] not in latest[target_id]["aliases"]:
            latest[target_id]["aliases"].append(update["title"])

    targets = sorted(latest.values(), key=lambda item: item["releasedAt"], reverse=True)
    for target in targets:
        query = f"{target['name']} 评测"
        target["query"] = query
        target["searchUrl"] = f"{SOGOU_BASE}?type=2&query={urllib.parse.quote(query)}&page=1&ie=utf8"
    return targets


class SogouResultsParser(HTMLParser):
    """Extract only the public title, snippet, account and timestamp from result HTML."""

    def __init__(self, search_url: str):
        super().__init__(convert_charrefs=True)
        self.search_url = search_url
        self.items: list[dict] = []
        self.current: dict | None = None
        self.capture: str | None = None
        self.in_script = False
        self.script_data: list[str] = []

    def _finish(self) -> None:
        if not self.current:
            return
        title = re.sub(r"\s+", " ", " ".join(self.current.get("titleParts", []))).strip()
        summary = re.sub(r"\s+", " ", " ".join(self.current.get("summaryParts", []))).strip()
        account = re.sub(r"\s+", " ", " ".join(self.current.get("accountParts", []))).strip()
        if title:
            href = self.current.get("href")
            result_url = urllib.parse.urljoin("https://weixin.sogou.com", href) if href else None
            self.items.append({
                "title": html.unescape(title),
                "summary": html.unescape(summary),
                "account": html.unescape(account) or "公众号待确认",
                "publishedAt": self.current.get("publishedAt"),
                "url": result_url,
                "searchUrl": self.search_url,
            })
        self.current = None
        self.capture = None
        self.in_script = False
        self.script_data = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "h3":
            self._finish()
            self.current = {"titleParts": [], "summaryParts": [], "accountParts": []}
            self.capture = "title"
            return
        if not self.current:
            return
        if tag == "a" and self.capture == "title" and attributes.get("href"):
            self.current["href"] = html.unescape(attributes["href"])
        elif tag == "p" and "txt-info" in classes:
            self.capture = "summary"
        elif tag == "span" and "all-time-y2" in classes:
            self.capture = "account"
        elif tag == "span" and "s2" in classes:
            self.capture = "date"
        elif tag == "script" and self.capture == "date":
            self.in_script = True
            self.script_data = []

    def handle_data(self, data: str) -> None:
        if not self.current:
            return
        if self.in_script:
            self.script_data.append(data)
            return
        if self.capture == "title":
            self.current["titleParts"].append(data)
        elif self.capture == "summary":
            self.current["summaryParts"].append(data)
        elif self.capture == "account":
            self.current["accountParts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.current:
            return
        if tag == "script" and self.in_script:
            self.in_script = False
            match = re.search(r"timeConvert\(['\"](\d{9,})['\"]\)", "".join(self.script_data))
            if match:
                try:
                    self.current["publishedAt"] = iso(datetime.fromtimestamp(int(match.group(1)), timezone.utc))
                except (OverflowError, OSError, ValueError):
                    pass
        elif tag == "h3" and self.capture == "title":
            self.capture = None
        elif tag == "p" and self.capture == "summary":
            self.capture = None
        elif tag == "span" and self.capture in {"account", "date"}:
            self.capture = None

    def close(self) -> None:
        super().close()
        self._finish()


def contains_captcha(body: str, final_url: str) -> bool:
    lowered = (body + " " + final_url).casefold()
    return any(term.casefold() in lowered for term in CAPTCHA_TERMS)


def is_evaluation_candidate(title: str, summary: str) -> bool:
    return bool(EVALUATION_TERMS.search(f"{title} {summary}"))


def stable_id(source_type: str, parts: list[str]) -> str:
    normalized = "|".join(normalize(part) for part in parts)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]
    return f"{source_type}-{digest}"


def aipick_candidates(payload: dict, targets: list[dict], now: datetime) -> list[dict]:
    results = []
    items = payload.get("items", []) if isinstance(payload, dict) else []
    for item in items:
        source = item.get("source") or {}
        links = item.get("links") or {}
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        if not is_evaluation_candidate(title, summary):
            continue
        haystack = normalize(f"{title} {summary}")
        for target in targets:
            aliases = [normalize(alias) for alias in target.get("aliases", []) if len(normalize(alias)) >= 5]
            matched = next((alias for alias in sorted(aliases, key=len, reverse=True) if alias in haystack), None)
            if not matched:
                continue
            published = parse_datetime(item.get("publishedAt"))
            original_url = secure_url(links.get("original"))
            item_id = str(item.get("id") or stable_id("aipick", [title, source.get("name", ""), str(item.get("publishedAt", ""))]))
            results.append({
                "id": f"aipick-{item_id}",
                "targetId": target["id"],
                "modelName": target["name"],
                "category": target["category"],
                "title": title,
                "summary": summary,
                "sourceType": "aipick",
                "sourceName": source.get("name") or "AIPick 精选来源",
                "publishedAt": iso(published) if published else item.get("publishedAt"),
                "url": original_url or secure_url(links.get("aihot")),
                "searchUrl": target.get("searchUrl"),
                "candidateReason": "AIPick 近 7 天精选中命中模型名和实测/评测信号词，待核对原文。",
                "collectedAt": iso(now),
            })
            break
    return results


def sogou_candidate(result: dict, target: dict, now: datetime) -> dict | None:
    title = result.get("title", "")
    summary = result.get("summary", "")
    if not is_evaluation_candidate(title, summary):
        return None
    target_names = [normalize(alias) for alias in target.get("aliases", []) if len(normalize(alias)) >= 5]
    content = normalize(f"{title} {summary}")
    if target_names and not any(name in content for name in target_names):
        return None
    published = parse_datetime(result.get("publishedAt"))
    return {
        "id": stable_id("sogou", [title, result.get("account", ""), result.get("publishedAt", "")]),
        "targetId": target["id"],
        "modelName": target["name"],
        "category": target["category"],
        "title": title,
        "summary": summary,
        "sourceType": "sogou-wechat",
        "sourceName": result.get("account") or "公众号待确认",
        "publishedAt": iso(published) if published else None,
        "url": secure_url(result.get("url")),
        "searchUrl": target.get("searchUrl"),
        "candidateReason": "搜狗微信搜索摘要命中模型名和实测/评测信号词；尚未核对文章全文。",
        "collectedAt": iso(now),
    }


def fetch_sogou(target: dict) -> tuple[list[dict], bool, str | None]:
    request = urllib.request.Request(target["searchUrl"], headers={
        "Accept": "text/html",
        "User-Agent": "AI-Creator-Radar/1.0 (+https://github.com/Ai-luren/AI-Creator-Radar)",
    })
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read(MAX_BYTES + 1)
            final_url = response.geturl()
        if len(body) > MAX_BYTES:
            return [], False, "搜狗搜索页超过 4 MB 安全限制"
        text = body.decode("utf-8", errors="replace")
        if contains_captcha(text, final_url):
            return [], True, "搜狗返回验证页；已停止本轮搜索，不绕过验证"
        parser = SogouResultsParser(target["searchUrl"])
        parser.feed(text)
        parser.close()
        return parser.items, False, None
    except urllib.error.HTTPError as error:
        if error.code in {403, 429}:
            return [], True, f"搜狗返回 HTTP {error.code}；已停止本轮搜索"
        return [], False, f"搜狗 HTTP {error.code}"
    except Exception as error:  # Network/source errors are persisted as warnings, not fatal.
        return [], False, f"{type(error).__name__}: {str(error)[:180]}"


def atomic_write(payload: dict) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".model-evaluations-", suffix=".json", dir=OUTPUT.parent)
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


def collect(now: datetime | None = None, dry_run: bool = False, skip_sogou: bool = False) -> dict:
    now = now or datetime.now(timezone.utc)
    previous = load_json(OUTPUT, {})
    models = load_json(MODELS_PATH, [])
    updates_data = load_json(UPDATES_PATH, {})
    aipick_data = load_json(AIPICK_PATH, {})
    targets = recent_targets(models, updates_data.get("items", []), now)
    state = previous.get("searchState", {}) if isinstance(previous.get("searchState"), dict) else {}
    query_state = state.get("queries", {}) if isinstance(state.get("queries"), dict) else {}
    warnings = []
    new_items = aipick_candidates(aipick_data, targets, now)

    state["lastRunAt"] = iso(now)
    state["queries"] = query_state
    blocked_until = parse_datetime(state.get("blockedUntil"))
    sogou_status = "skipped" if skip_sogou else "ok"
    searches = 0

    if skip_sogou:
        warnings.append("本次运行跳过搜狗网络请求")
    elif blocked_until and blocked_until > now:
        sogou_status = "blocked"
        warnings.append("搜狗处于 24 小时退避期；本次不发起请求")
    else:
        if blocked_until:
            state.pop("blockedUntil", None)
        for target in targets:
            if searches >= MAX_SEARCHES_PER_RUN:
                warnings.append(f"本轮达到 {MAX_SEARCHES_PER_RUN} 次搜狗查询上限，剩余模型下次再查")
                break
            query_info = query_state.get(target["id"], {})
            last_searched = parse_datetime(query_info.get("lastSearchedAt"))
            if last_searched and now - last_searched < SEARCH_INTERVAL:
                continue
            target["lastSearchedAt"] = iso(now)
            raw_results, blocked, error = fetch_sogou(target)
            searches += 1
            query_state[target["id"]] = {
                "lastSearchedAt": iso(now),
                "status": "blocked" if blocked else "warning" if error else "ok",
                "resultCount": len(raw_results),
                "candidateCount": 0,
                "error": error,
            }
            if error:
                warnings.append(f"{target['name']}: {error}")
            if blocked:
                sogou_status = "blocked"
                state["blockedUntil"] = iso(now + CAPTCHA_COOLDOWN)
                break
            if error:
                sogou_status = "warning"
                continue
            for result in raw_results:
                candidate = sogou_candidate(result, target, now)
                if candidate:
                    new_items.append(candidate)
            query_state[target["id"]]["candidateCount"] = sum(
                1 for item in new_items if item.get("targetId") == target["id"] and item.get("sourceType") == "sogou-wechat"
            )

    existing_items = previous.get("items", []) if isinstance(previous.get("items"), list) else []
    merged = {str(item.get("id")): item for item in existing_items if isinstance(item, dict) and item.get("id")}
    for item in new_items:
        merged[item["id"]] = item
    items = sorted(merged.values(), key=lambda item: item.get("publishedAt") or item.get("collectedAt") or "", reverse=True)

    aipick_status = "ok" if aipick_data.get("items") else "missing"
    payload = {
        "schema": "ai-creator-radar-model-evaluations/1",
        "generatedAt": iso(now),
        "sourceNotes": {
            "aipick": "AIPick 近 7 天精选中的公开评测候选；保留其来源与原始链接。",
            "sogou": "搜狗微信搜索只读取搜索结果页的标题、摘要、公众号名和发布时间；不抓正文；遇到验证页停止并退避 24 小时。",
        },
        "status": {
            "aipick": {"status": aipick_status, "checkedAt": aipick_data.get("fetchedAt"), "candidateCount": sum(1 for item in new_items if item.get("sourceType") == "aipick")},
            "sogou": {"status": sogou_status, "checkedAt": iso(now), "searchesThisRun": searches, "warnings": warnings, "blockedUntil": state.get("blockedUntil")},
        },
        "targets": targets,
        "items": items,
        "searchState": state,
    }
    if not dry_run:
        atomic_write(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect recent model-evaluation candidates without reading article full text.")
    parser.add_argument("--dry-run", action="store_true", help="Collect and validate without writing the snapshot.")
    parser.add_argument("--skip-sogou", action="store_true", help="Use only the existing AIPick snapshot.")
    args = parser.parse_args()
    result = collect(dry_run=args.dry_run, skip_sogou=args.skip_sogou)
    print(f"Model evaluations: {len(result['targets'])} recent models; {len(result['items'])} retained candidates; "
          f"AIPick {result['status']['aipick']['candidateCount']}; Sogou {result['status']['sogou']['status']} "
          f"({result['status']['sogou']['searchesThisRun']} searches).")
    for warning in result["status"]["sogou"]["warnings"]:
        print("Warning:", warning)
    if args.dry_run:
        print("Validated without writing.")
    else:
        print(f"Saved to {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
