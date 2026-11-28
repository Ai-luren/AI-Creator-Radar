#!/usr/bin/env python3
"""Serve the local site and read AIHOT ranking and topic data on demand.

This is a localhost-only personal reader. AIHOT data is kept in memory for a
short conditional-request cache and is never written into the repository.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
HOST = "127.0.0.1"
CACHE_SECONDS = 0
USER_AGENT = "AI-Creator-Radar local personal reader/1.0"

BOARD_PATHS = {
    "overall": "leaderboard",
    "coding": "leaderboard/category/coding",
    "reasoning": "leaderboard/category/reasoning",
    "professional": "leaderboard/category/professional",
    "knowledge": "leaderboard/category/knowledge",
}
BOARD_LABELS = {
    "overall": "综合",
    "coding": "编程",
    "reasoning": "科研",
    "professional": "专业办公",
    "knowledge": "知识问答",
}
TOPIC_SLUGS = {
    "openai", "anthropic", "google", "deepseek", "qwen", "kimi", "minimax", "zhipu", "xai", "meta",
    "microsoft", "hugging-face", "cursor", "openrouter", "agent", "coding", "reasoning", "multimodal",
    "image-gen", "video", "voice", "embodied", "on-device", "open-source", "engineering", "data-training",
    "safety", "mcp", "model-releases", "product-updates", "papers", "benchmarks", "tutorials", "opinions",
    "trends", "industry", "policy",
}
_cache: dict[str, dict] = {}


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_leaderboard_markdown(markdown: str, category: str, mode: str, source_url: str) -> dict:
    """Convert the published Markdown table into safe, source-linked rows."""
    lines = markdown.splitlines()
    title = next((line[2:].strip() for line in lines if line.startswith("# ")), "AIHOT 模型榜")
    updated = next((line.split("：", 1)[1].split("（", 1)[0].strip() for line in lines if line.startswith("- 更新：")), "")
    evaluations = next((line.split("：", 1)[1].strip() for line in lines if line.startswith("- 评测：")), "")
    description = ""
    after_metadata = False
    for line in lines:
        if line.startswith(("- 评测：", "- 汇率：")):
            after_metadata = True
            continue
        if after_metadata and line.strip() and not line.startswith(("#", "- ", "|")):
            description = line.strip()
            break

    headers: list[str] = []
    rows: list[dict] = []
    in_table = False
    for line in lines:
        if not line.strip().startswith("|"):
            if in_table:
                break
            continue
        cells = _table_cells(line)
        if not headers:
            headers = cells
            in_table = True
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        if len(cells) != len(headers):
            continue
        row = {header: value for header, value in zip(headers, cells)}
        model_cell = row.get("模型", "")
        model_match = re.search(r"\[([^\]]+)\]\((https://aihot\.news/leaderboard/[^)]+)\)", model_cell)
        if model_match:
            row["模型"] = model_match.group(1)
            row["模型链接"] = model_match.group(2)
        rows.append(row)

    if not headers or not rows:
        raise ValueError("AIHOT Markdown did not contain a recognizable ranking table")

    return {
        "source": "AIHOT",
        "sourceUrl": source_url,
        "category": category,
        "categoryLabel": BOARD_LABELS[category],
        "mode": mode,
        "title": title,
        "updatedAt": updated,
        "evaluationSummary": evaluations,
        "description": description,
        "headers": headers,
        "rows": rows,
        "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def get_board(category: str, mode: str, force_refresh: bool = False) -> dict:
    if category not in BOARD_PATHS or mode not in {"rank", "price"}:
        raise ValueError("Unknown leaderboard category or view")
    base_path = BOARD_PATHS[category]
    path = base_path if mode == "rank" else f"{base_path}/prices"
    source_url = f"https://aihot.news/{path}"
    markdown_url = f"{source_url}.md"
    cache_key = f"{category}:{mode}"
    cached = _cache.get(cache_key)
    now = time.monotonic()
    if cached and not force_refresh and now - cached["stored_at"] < CACHE_SECONDS:
        return cached["data"]

    headers = {"User-Agent": USER_AGENT, "Accept": "text/markdown"}
    if cached and cached.get("etag"):
        headers["If-None-Match"] = cached["etag"]
    request = Request(markdown_url, headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            markdown = response.read().decode("utf-8")
            data = parse_leaderboard_markdown(markdown, category, mode, source_url)
            etag = response.headers.get("ETag", "")
    except HTTPError as exc:
        if exc.code == 304 and cached:
            cached["stored_at"] = now
            cached["data"]["fetchedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            return cached["data"]
        raise RuntimeError(f"AIHOT returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"Could not read AIHOT: {exc}") from exc

    _cache[cache_key] = {"data": data, "etag": etag, "stored_at": now}
    return data


class TopicPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.text: list[str] = []
        self._in_title = False
        self._main_depth = 0
        self._skip_depth = 0
        self._chronicle_depth = 0
        self._event: dict | None = None
        self._event_anchor_depth = 0
        self._event_field: dict | None = None
        self._in_time = False
        self._in_kind = False
        self._pending_date = ""
        self._pending_kind = ""
        self.events: list[dict] = []
        self._event_year: int | None = None
        self._previous_month: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "meta" and values.get("name", "").lower() == "description":
            self.description = values.get("content", "") or self.description
        if tag in {"script", "style", "svg"}:
            self._skip_depth += 1
        if tag == "main":
            self._main_depth += 1
        if tag == "section" and values.get("aria-labelledby") == "topic-chronicle":
            self._chronicle_depth = 1
        elif tag == "section" and self._chronicle_depth:
            self._chronicle_depth += 1
        if tag == "time" and self._chronicle_depth:
            self._in_time = True
            # AIHOT exposes the event date on the adjacent <time> element.
            # Prefer its ISO date over reconstructing a year from month labels.
            self._pending_date = (values.get("datetime", "") or "")[:10]
            self._pending_kind = ""
        if tag == "span" and self._event:
            if self._event_field:
                self._event_field["depth"] += 1
            else:
                classes = (values.get("class") or "").split()
                field = "dateText" if "num" in classes else "kind" if "text-ink-4" in classes or "text-accent" in classes else "title" if any(name.startswith("text-ink") and name != "text-ink-4" for name in classes) else ""
                if field:
                    self._event_field = {"field": field, "depth": 1}
        if tag == "span" and self._chronicle_depth and self._pending_date and not self._event:
            span_classes = (values.get("class") or "").split()
            if "text-ink-4" in span_classes or "text-accent" in span_classes:
                self._in_kind = True
        if self._chronicle_depth and tag == "a" and "group/event" in (values.get("class") or "").split():
            self._event = {
                "dateText": self._pending_date,
                "kind": self._pending_kind,
                "title": "",
                "summary": values.get("title", "") or "",
                "url": urljoin("https://aihot.news", values.get("href", "") or ""),
            }
            self._event_anchor_depth = 1
        elif self._event and self._event_anchor_depth:
            self._event_anchor_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "main" and self._main_depth:
            self._main_depth -= 1
        if tag == "time" and self._in_time:
            self._in_time = False
        if tag == "span" and self._in_kind:
            self._in_kind = False
        if self._event_field and tag == "span":
            self._event_field["depth"] -= 1
            if self._event_field["depth"] <= 0:
                self._event_field = None
        if self._event and self._event_anchor_depth:
            self._event_anchor_depth -= 1
        if tag == "a" and self._event:
            event = self._event
            date_text = event.pop("dateText")
            event["date"] = date_text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_text) else _normalize_topic_date(date_text)
            if not event["date"]:
                short_date = re.search(r"(?<!\d)(\d{1,2})月\s*(\d{1,2})日", date_text)
                if short_date:
                    month, day = map(int, short_date.groups())
                    if self._event_year is not None and self._previous_month and month < self._previous_month:
                        self._event_year += 1
                    if self._event_year is not None:
                        event["date"] = f"{self._event_year}-{month:02d}-{day:02d}"
                    self._previous_month = month
            else:
                date_parts = event["date"].split("-")
                self._event_year = int(date_parts[0])
                self._previous_month = int(date_parts[1]) if len(date_parts) > 1 else None
            event["title"] = event["title"].strip()
            if event["date"] and event["title"]:
                self.events.append(event)
            self._event = None
            self._event_anchor_depth = 0
        if tag == "section" and self._chronicle_depth:
            self._chronicle_depth -= 1

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if not value or self._skip_depth:
            return
        if self._in_title:
            self.title += value
        if self._main_depth:
            self.text.append(value)
        if self._in_time:
            # Fallback for source revisions that omit dateTime.
            if not self._pending_date:
                self._pending_date = (self._pending_date + " " + value).strip()
        if self._in_kind:
            self._pending_kind = (self._pending_kind + " " + value).strip()
        if self._event and self._event_field:
            field = self._event_field["field"]
            self._event[field] = (self._event[field] + " " + value).strip()


def _normalize_topic_date(value: str) -> str:
    year_only = re.search(r"(?<!\d)(\d{4})年", value)
    if year_only and not re.search(r"\d{4}年\s*\d{1,2}月", value):
        return year_only.group(1)
    match = re.search(r"(\d{4})年\s*(\d{1,2})月(?:\s*(\d{1,2})日)?", value)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}" + (f"-{int(day):02d}" if day else "")
    match = re.search(r"(\d{4})\.(\d{1,2})(?:\.(\d{1,2}))?", value)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}" + (f"-{int(day):02d}" if day else "")
    return ""


def get_topic(slug: str, force_refresh: bool = False) -> dict:
    if slug not in TOPIC_SLUGS:
        raise ValueError("Unknown AIHOT topic")
    source_url = f"https://aihot.news/topics/{slug}"
    cache_key = f"topic:{slug}"
    cached = _cache.get(cache_key)
    now = time.monotonic()
    if cached and not force_refresh and now - cached["stored_at"] < CACHE_SECONDS:
        return cached["data"]

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    if cached and cached.get("etag"):
        headers["If-None-Match"] = cached["etag"]
    request = Request(source_url, headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            page = response.read().decode("utf-8")
            etag = response.headers.get("ETag", "")
    except HTTPError as exc:
        if exc.code == 304 and cached:
            cached["stored_at"] = now
            cached["data"]["fetchedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            return cached["data"]
        raise RuntimeError(f"AIHOT returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"Could not read AIHOT: {exc}") from exc

    parser = TopicPageParser()
    parser.feed(page)
    if not parser.description or "页面不存在" in parser.title:
        raise RuntimeError("AIHOT topic page did not return topic metadata")
    body_text = " ".join(parser.text)
    count_match = re.search(r"(\d+)\s*条精选", body_text)
    recent_match = re.search(r"近\s*30\s*天\s*(\d+)\s*条", body_text)
    total_match = re.search(r"共收录\s*(\d+)\s*条", body_text)
    update_match = re.search(r"(\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})\s*更新", body_text)
    data = {
        "source": "AIHOT",
        "sourceUrl": source_url,
        "slug": slug,
        "title": re.sub(r"\s*[·|]\s*AIHOT\s*$", "", parser.title),
        "summary": parser.description,
        "featuredCount": int(count_match.group(1)) if count_match else None,
        "recentCount": int(recent_match.group(1)) if recent_match else None,
        "totalCount": int(total_match.group(1)) if total_match else None,
        "updatedAt": update_match.group(1) if update_match else "",
        "milestones": parser.events,
        "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _cache[cache_key] = {"data": data, "etag": etag, "stored_at": now}
    return data



# Private reader only. No public snapshot, credentials, arbitrary proxy, or
# persisted copy. Aggregate provider failure does not erase the other result.
INTEL_PROVIDERS={"AIHOT":"https://aihot.news","AIPick":"https://aipick.news"}
INTEL_MODES={"competitors","vendors","hot","cases"}
_intel_cache={}
_intel_cooldown={}
_intel_lock=__import__("threading").Lock()

def intel_endpoint(provider, mode, term):
    if provider not in INTEL_PROVIDERS or mode not in INTEL_MODES:
        raise ValueError("Unknown intelligence provider or mode")
    if not isinstance(term,str) or len(term)>48 or (term and not re.fullmatch(r"[\w .-]+",term)):
        raise ValueError("Invalid brand query")
    if mode=="hot":
        if term: raise ValueError("Hot board does not accept a brand query")
        return INTEL_PROVIDERS[provider]+"/api/v1/hot-topics"
    from urllib.parse import urlencode
    params={"mode":"selected","window":"7d","by":"published","limit":20}
    if term: params["q"]=term
    elif mode in {"competitors","vendors"}: params["category"]="ai-products" if mode=="competitors" else "ai-models"
    return INTEL_PROVIDERS[provider]+"/api/v1/items?"+urlencode(params)

def get_intel(mode,term,opener=urlopen,clock=time.monotonic):
    endpoints={p:intel_endpoint(p,mode,term) for p in INTEL_PROVIDERS}
    result={}
    from email.utils import parsedate_to_datetime
    from urllib.request import build_opener
    from urllib.request import HTTPRedirectHandler
    class FixedHostRedirect(HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            old=urlsplit(req.full_url);new=urlsplit(newurl)
            if new.scheme!="https" or new.hostname!=old.hostname or new.port not in (None,443) or new.username or new.password:
                raise ValueError("Unexpected upstream redirect")
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    # Default fetcher prevents redirects to arbitrary hosts.
    fetch=build_opener(FixedHostRedirect()).open if opener is urlopen else opener
    with _intel_lock:
        for provider,url in endpoints.items():
            now=clock()
            cached=_intel_cache.get(url,{})
            prior=cached.get("result",{})
            if now<_intel_cooldown.get(provider,0):
                result[provider]={**prior,"error":"上游限流或暂不可用"}
                continue
            if cached and now-cached["time"]<600:
                result[provider]=prior
                continue
            headers={"Accept":"application/json","User-Agent":USER_AGENT}
            if cached.get("etag"):headers["If-None-Match"]=cached["etag"]
            try:
                with fetch(Request(url,headers=headers),timeout=12) as response:
                    raw=response.read(2*1024*1024+1)
                    if len(raw)>2*1024*1024:raise ValueError("Upstream response exceeds size limit")
                    data=json.loads(raw)
                    if not isinstance(data,dict) or not isinstance(data.get("items"),list) or len(data["items"])>(10 if mode=="hot" else 20):
                        raise ValueError("Unexpected upstream response")
                    if any(not isinstance(row,dict) for row in data["items"]):
                        raise ValueError("Unexpected upstream row")
                    entry={"data":data,"observedAt":datetime.now(timezone.utc).isoformat(timespec="seconds")}
                    etag=response.headers.get("ETag","")
                    _intel_cache[url]={"result":entry,"time":now,"etag":etag}
            except HTTPError as exc:
                if exc.code==304 and prior.get("data") is not None:
                    entry={**prior,"validatedAt":datetime.now(timezone.utc).isoformat(timespec="seconds")}
                    _intel_cache[url]={**cached,"result":entry,"time":now}
                else:
                    wait=3600 if exc.code in (403,429) else 600
                    retry=exc.headers.get("Retry-After","") if exc.headers else ""
                    try: wait=max(wait,int(retry) if retry.isdigit() else int((parsedate_to_datetime(retry)-datetime.now(timezone.utc)).total_seconds()))
                    except (ValueError,TypeError,OverflowError):pass
                    _intel_cooldown[provider]=now+wait
                    entry={**prior,"error":"HTTP "+str(exc.code)}
            except (OSError,ValueError,TypeError) as exc:
                _intel_cooldown[provider]=now+600
                entry={**prior,"error":type(exc).__name__}
            result[provider]=entry
        # Bounded private cache; avoid growing into a local historical archive.
        for key in sorted(_intel_cache,key=lambda k:_intel_cache[k]["time"])[:-64]:
            del _intel_cache[key]
    return {"mode":mode,"term":term,"sources":result}


class LocalHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE), **kwargs)

    def end_headers(self) -> None:
        # Local JSON and static assets change during editing. Do not let the
        # browser keep an older copy between refreshes.
        if not urlsplit(self.path).path.startswith("/__local/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def send_local_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        # The upstream reader may keep a short in-process cache, but clients
        # should always revalidate each request.
        self.send_header("Cache-Control", "no-store")
        origin = self.headers.get("Origin", "")
        if origin in {"http://localhost:8080", "http://127.0.0.1:8080"}:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path not in {"/__local/aihot-leaderboard", "/__local/aihot-topic", "/__local/creator-intel"}:
            super().do_GET()
            return

        query = parse_qs(parsed.query)
        force_refresh = query.get("refresh", ["0"])[0] == "1"
        try:
            if parsed.path == "/__local/creator-intel":
                data = get_intel(query.get("mode",["hot"])[0],query.get("term",[""])[0])
            elif parsed.path == "/__local/aihot-leaderboard":
                category = query.get("category", ["overall"])[0]
                mode = query.get("mode", ["rank"])[0]
                data = get_board(category, mode, force_refresh)
            else:
                slug = query.get("slug", [""])[0]
                data = get_topic(slug, force_refresh)
        except ValueError as exc:
            self.send_local_json({"error": str(exc)}, 400)
            return
        except RuntimeError as exc:
            self.send_local_json({"error": str(exc)}, 502)
            return

        self.send_local_json(data)


def main() -> None:
    import argparse
    import threading
    import webbrowser

    parser = argparse.ArgumentParser(description="Run the local AI creator radar.")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--no-open", action="store_true", help="do not open the website in a browser")
    args = parser.parse_args()
    url = f"http://{HOST}:{args.port}/"

    # If the local server is already running, reuse it and open the homepage.
    try:
        with urlopen(url, timeout=0.6) as response:
            if response.status == 200 and "创作情报台".encode("utf-8") in response.read(8192):
                if not args.no_open:
                    webbrowser.open_new_tab(url)
                print(f"Using existing local website: {url}")
                return
    except OSError:
        pass

    server = ThreadingHTTPServer((HOST, args.port), LocalHandler)
    print(f"Local AI Creator Radar: {url}")
    print("Browser caching is disabled; AIHOT requests revalidate against the source on every read.")
    if not args.no_open:
        threading.Timer(0.8, webbrowser.open_new_tab, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
