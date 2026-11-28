#!/usr/bin/env python3
"""Collect public RSS feeds and GitHub resource metadata for the creator workbench."""
from __future__ import annotations

import concurrent.futures
import email.utils
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "resource-sources.json"
FEED_DATA = ROOT / "site" / "data" / "feed-items.json"
REPO_DATA = ROOT / "site" / "data" / "awesome-repos.json"
STATUS_DATA = ROOT / "site" / "data" / "resource-status.json"
SOURCES_DATA = ROOT / "site" / "data" / "resource-sources.json"
USER_AGENT = "AI-Creator-Workbench/1.0 (+https://github.com/Ai-luren/AI-Creator-Radar)"
MAX_FEED_ITEMS = 60
MAX_DESCRIPTION = 1200


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        if data and data.strip():
            self.parts.append(data.strip())

    def text(self):
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


def strip_html(value: str) -> str:
    parser = TextOnly()
    try:
        parser.feed(value or "")
        parser.close()
        return html.unescape(parser.text())
    except Exception:
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def direct_text(element: ET.Element, names: set[str]) -> str:
    for child in list(element):
        if local_name(child.tag) in names:
            value = " ".join(part.strip() for part in child.itertext() if part.strip())
            if value:
                return value
    return ""


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    raw = html.unescape(str(value)).strip()
    iso = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except ValueError:
        pass
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError):
        return None


def first_link(item: ET.Element, base: str) -> str:
    for child in list(item):
        if local_name(child.tag) == "link":
            href = child.attrib.get("href")
            if href and child.attrib.get("rel", "alternate") in {"alternate", ""}:
                return urljoin(base, href.strip())
            if child.text and child.text.strip():
                return urljoin(base, child.text.strip())
    for child in list(item):
        if local_name(child.tag) in {"guid", "id"} and child.text:
            if child.attrib.get("isPermaLink", "true").lower() != "false":
                return urljoin(base, child.text.strip())
    return base


def image_url(item: ET.Element) -> str | None:
    for node in item.iter():
        tag = local_name(node.tag)
        if tag == "enclosure" and node.attrib.get("url"):
            return node.attrib["url"]
        if tag in {"content", "thumbnail"} and node.attrib.get("url") and (
            "image" in node.attrib.get("type", "").lower() or tag == "thumbnail"
        ):
            return node.attrib["url"]
    return None


def parse_feed_bytes(body: bytes, source: dict, now_iso: str) -> list[dict]:
    if len(body) > 4 * 1024 * 1024:
        raise ValueError("RSS feed exceeds 4 MB safety limit")
    root = ET.fromstring(body)
    entries = [node for node in root.iter() if local_name(node.tag) in {"item", "entry"}]
    results = []
    for entry in entries[:MAX_FEED_ITEMS]:
        title = strip_html(direct_text(entry, {"title"}))
        if not title:
            continue
        description = direct_text(entry, {"encoded", "content", "description", "summary"})
        if not description:
            description = direct_text(entry, {"description", "summary"})
        description = strip_html(description)[:MAX_DESCRIPTION]
        published = parse_date(direct_text(entry, {"pubdate", "published", "updated", "date", "created"}))
        link = first_link(entry, source["url"])
        guid = direct_text(entry, {"guid", "id"}) or link
        identity = hashlib.sha256((source["id"] + "|" + guid).encode("utf-8")).hexdigest()[:20]
        creator = strip_html(direct_text(entry, {"creator", "author", "name"}))
        prompt_preview = None
        summary = description
        if source.get("id") == "goodcase":
            match = re.search(r"(?:Prompt\s*预览|Prompt\s*Preview)\s*[:：]\s*(.*)$", description, flags=re.I)
            if match:
                prompt_preview = match.group(1).strip()[:620]
                summary = description[:match.start()].strip()
            if not creator:
                author_match = re.match(r"^([^：:]{1,48})[：:]\s*(.*)$", summary)
                if author_match:
                    creator = author_match.group(1).strip()
                    summary = author_match.group(2).strip()
        categories = [strip_html(child.text or "") for child in list(entry) if local_name(child.tag) == "category" and child.text]
        results.append({
            "id": identity,
            "sourceId": source["id"],
            "sourceName": source["name"],
            "category": source["category"],
            "title": title[:240],
            "summary": summary[:MAX_DESCRIPTION],
            "promptPreview": prompt_preview,
            "publishedAt": published,
            "url": link,
            "imageUrl": urljoin(link.rstrip("/") + "/", image_url(entry)) if image_url(entry) else None,
            "creator": creator[:100] if creator else None,
            "tags": categories[:8],
            "discoveredAt": now_iso,
        })
    return results


def parse_feed(source: dict, now_iso: str) -> list[dict]:
    request = urllib.request.Request(source["url"], headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    })
    with urllib.request.urlopen(request, timeout=12) as response:
        body = response.read(4 * 1024 * 1024 + 1)
    return parse_feed_bytes(body, source, now_iso)


def fetch_repo(repo: dict, now_iso: str) -> tuple[dict, str | None]:
    name = repo["repo"]
    url = "https://api.github.com/repos/" + name
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read(512 * 1024))
        license_info = payload.get("license") or {}
        result = dict(repo)
        result.update({
            "url": payload.get("html_url") or "https://github.com/" + name,
            "description": repo.get("description") or payload.get("description") or "",
            "stars": payload.get("stargazers_count"),
            "forks": payload.get("forks_count"),
            "updatedAt": payload.get("updated_at"),
            "pushedAt": payload.get("pushed_at"),
            "license": repo.get("licenseOverride") or license_info.get("spdx_id") or license_info.get("name"),
            "defaultBranch": payload.get("default_branch"),
            "archived": bool(payload.get("archived")),
            "metadataCheckedAt": now_iso,
            "metadataStatus": "ok",
        })
        return result, None
    except Exception as exc:
        fallback = dict(repo)
        fallback.setdefault("url", "https://github.com/" + name)
        fallback["metadataStatus"] = "cached"
        return fallback, f"{type(exc).__name__}: {str(exc)[:160]}"


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)



# Deliberately narrow creative-product lanes. Topic search is recent activity,
# not GitHub Trending or proof of usefulness. General LLM frameworks are out.
RESEARCH_LANES = (
    ("image", "topic:image-generation", r"image generation|image editing|image-generation|image-editing|character design|turnaround|图像生成|图像编辑|三视图|场景设定"),
    ("video", "topic:ai-video", r"storyboard|previs|shot planning|filmmak|video edit|video generat|cinematic|camera control|ai.video|分镜|白模|运镜|视频生成"),
    ("audio", "topic:audio-processing", r"stem separation|audio separation|sound effect|audio generat|music generat|speech synthesis|word.level timestamp|lip.sync|音轨|音效|语音合成"),
    ("workflow", "topic:comfyui-workflow", r"comfyui|comfy workflow|creative workflow|storyboard workflow|multi.model|创作工作流"),
    ("component", "topic:video-editor", r"video editor|video editing|timeline|video render|video composit|video editing|视频剪辑|时间线"),
    ("prompt", "topic:prompt-engineering", r"image prompt|video prompt|image generation|video generat|seedance|seedream|storyboard|turnaround|图像提示词|视频提示词|人物设定"),
)
REPO_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9_.-]+")
RESEARCH_LIMIT = 36


def repo_identity(url):
    try:
        u = urlsplit(str(url or ""))
        path = u.path.strip("/")
        if (u.scheme != "https" or u.netloc.lower() != "github.com"
                or not REPO_NAME.fullmatch(path)
                or any(p in {".", ".."} for p in path.split("/"))
                or path.split("/")[0].lower() in {"topics", "search", "orgs", "users", "marketplace", "settings", "collections", "sponsors"}):
            return None
        return path
    except ValueError:
        return None


def research_lane(text, preferred=None):
    text = str(text or "")[:2000]
    for lane, _, pattern in sorted(RESEARCH_LANES, key=lambda x: x[0] != preferred):
        if re.search(pattern, text, re.I):
            return lane
    return None


def curated_repo_pointers(snapshots, now):
    """Use selected recent original repo URLs only, never rehost aggregator copy."""
    seen = set()
    rows = []
    for provider, snapshot in snapshots:
        for item in snapshot.get("items", []):
            if not isinstance(item, dict) or item.get("selected") is not True:
                continue
            day = parse_date(item.get("publishedAt"))
            if not day or not now-timedelta(days=7) <= datetime.fromisoformat(day) <= now:
                continue
            links = item.get("links") or {}
            if not isinstance(links, dict) or links.get("story"):
                continue
            repo = repo_identity(links.get("original"))
            lane = research_lane(item.get("title"))
            if repo and lane and repo.lower() not in seen:
                rows.append((repo, provider, lane, day))
                seen.add(repo.lower())
    return sorted(rows, key=lambda x:x[3], reverse=True)


def github_json(url):
    # Public GitHub metadata only. Do not execute repository code.
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read(2*1024*1024+1)
    if len(raw)>2*1024*1024:
        raise ValueError("GitHub response exceeds size limit")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Unexpected GitHub schema")
    return data


def search_creative_repos(query, now):
    q = query+" pushed:>="+(now-timedelta(days=7)).date().isoformat()+" archived:false fork:false"
    payload = github_json("https://api.github.com/search/repositories?"+urlencode({
        "q":q,"sort":"updated","order":"desc","per_page":20,
    }))
    rows=payload.get("items")
    if not isinstance(rows, list) or len(rows)>20:
        raise ValueError("Unexpected search results")
    return rows


def candidate_repo(payload, provider, now, preferred=None):
    if not isinstance(payload, dict) or payload.get("archived") is not False or payload.get("fork") is not False or payload.get("private") is not False:
        return None
    repo=payload.get("full_name")
    if not isinstance(repo,str) or repo_identity(payload.get("html_url"))!=repo:
        return None
    description=str(payload.get("description") or "")[:500]
    topics=payload.get("topics") or []
    if not isinstance(topics,list) or not all(isinstance(t,str) for t in topics):
        return None
    category=research_lane(description+" "+" ".join(topics), preferred)
    stars=payload.get("stargazers_count")
    pushed=parse_date(payload.get("pushed_at"))
    if not category or type(stars) is not int or stars<0 or not pushed or datetime.fromisoformat(pushed)>now:
        return None
    # Keep repo candidates in the reading window by actual repository activity;
    # a new post about a stale repo does not imply active maintenance.
    if provider=="GitHub Search" and datetime.fromisoformat(pushed)<now-timedelta(days=7):
        return None
    license_info=payload.get("license") or {}
    if not isinstance(license_info,dict):
        return None
    return {"repo":repo,"url":payload["html_url"],"description":description,
            "researchCategory":category,"provider":provider,
            "stars":stars,"pushedAt":pushed,"license":license_info.get("spdx_id"),
            "metadataCheckedAt":now.isoformat(timespec="seconds"),
            "review":"metadata-only","archived":False}


def observed_stars(row, previous, now):
    """Actual sampled star counts only, not an inferred trend ranking."""
    current=row.get("stars")
    if type(current) is not int or current<0:
        return row
    cutoff=now-timedelta(days=7)
    history={}
    for point in previous.get("starObservations", []):
        stamp=parse_date(point.get("at"))
        if stamp and cutoff<=datetime.fromisoformat(stamp)<=now and type(point.get("stars")) is int and point["stars"]>=0:
            history[stamp]=point["stars"]
    stamp=now.isoformat(timespec="seconds").replace("+00:00","Z")
    history[stamp]=current
    points=[{"at":k,"stars":v} for k,v in sorted(history.items())][-32:]
    row={**row,"starObservations":points}
    if len(points)>1:
        row["observedStarChange"]={"from":points[0]["at"],"to":stamp,"delta":current-points[0]["stars"]}
    else:
        row.pop("observedStarChange",None)
    return row


def discover_repos(snapshots, previous, curated, now, fetcher=github_json, searcher=search_creative_repos):
    """One lookup for an existing original pointer OR one scoped API search per
    existing resources run; cache candidates and back off on service failures."""
    stamp=now.isoformat(timespec="seconds")
    excluded={r["repo"].lower() for r in curated}
    rows={r["repo"].lower():r for r in previous.get("items", [])
          if isinstance(r,dict) and isinstance(r.get("repo"),str)
          and r["repo"].lower() not in excluded
          and parse_date(r.get("metadataCheckedAt"))
          and now-timedelta(days=14)<=datetime.fromisoformat(parse_date(r["metadataCheckedAt"]))<=now}
    index=int(previous.get("nextLane",0))%len(RESEARCH_LANES)
    state={k:v for k,v in previous.items() if k!="items"}
    retry=parse_date(previous.get("nextAttemptAt"))
    if retry and datetime.fromisoformat(retry)>now:
        return {**state,"items":list(rows.values()),"deferred":True}
    pointers=[p for p in curated_repo_pointers(snapshots,now)
              if p[0].lower() not in excluded and p[0].lower() not in rows
              and p[0].lower() not in previous.get("recentPointerAttempts",[])]
    attempts=list(previous.get("recentPointerAttempts",[]))[-24:]
    lane,query,_=RESEARCH_LANES[index]
    try:
        if pointers:
            repo,provider,lane,_=pointers[0]
            attempts=(attempts+[repo.lower()])[-24:]
            payload=fetcher("https://api.github.com/repos/"+repo)
            if str(payload.get("full_name","")).lower()!=repo.lower():
                raise ValueError("Repository identity changed")
            payloads=[payload]
        else:
            provider="GitHub Search"
            payloads=searcher(query,now)
            index=(index+1)%len(RESEARCH_LANES)
        if not isinstance(payloads,list):
            raise ValueError("Invalid discovery result")
        added=0
        for payload in payloads[:20]:
            row=candidate_repo(payload,provider,now,lane)
            if not row or row["repo"].lower() in excluded:
                continue
            key=row["repo"].lower()
            prior=rows.get(key,{})
            rows[key]=observed_stars({**row,"firstObservedAt":prior.get("firstObservedAt") or stamp},prior,now)
            added+=1
        state.update(status="ok",checkedAt=stamp,lastSuccessAt=stamp,
                     lastProvider=provider,lastLane=lane,lastMatched=added,
                     nextAttemptAt=None,error=None,consecutiveFailures=0)
    except (OSError, ValueError, TypeError) as exc:
        failures=int(previous.get("consecutiveFailures",0))+1
        state.update(status="cached",checkedAt=stamp,error=f"{type(exc).__name__}: {str(exc)[:160]}",
                     consecutiveFailures=failures,nextAttemptAt=(now+timedelta(hours=min(48,6*2**min(failures-1,3)))).isoformat())
    state.update(nextLane=index,recentPointerAttempts=attempts,deferred=False,
                 policy="One bounded selected pointer or scoped GitHub API search. Metadata candidates, not verified features or adoption recommendations. Star change uses actual observations.")
    items=sorted(rows.values(),key=lambda x:(x["metadataCheckedAt"],x["repo"]),reverse=True)[:RESEARCH_LIMIT]
    return {**state,"items":items}


def main() -> int:
    config = load_json(CONFIG, {"feeds": [], "repositories": []})
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    old_feeds = load_json(FEED_DATA, {"generatedAt": None, "items": []})
    old_repos = load_json(REPO_DATA, {"generatedAt": None, "items": []})
    old_status = load_json(STATUS_DATA, {"feeds": [], "repositories": []})
    write_json(SOURCES_DATA, {
        "feeds": config.get("feeds", []),
        "repositories": config.get("repositories", []),
    })
    old_feed_items = old_feeds.get("items", [])
    old_by_id = {item.get("id"): item for item in old_feed_items if item.get("id")}
    old_feed_status = {item.get("id"): item for item in old_status.get("feeds", [])}
    old_repo_by_id = {item.get("id"): item for item in old_repos.get("items", [])}
    feed_status = []
    repo_status = []
    feed_success = 0
    repo_success = 0

    active_feeds = [x for x in config.get("feeds", []) if x.get("active", True)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, max(1, len(active_feeds)))) as pool:
        futures = {pool.submit(parse_feed, source, now_iso): source for source in active_feeds}
        for future in concurrent.futures.as_completed(futures):
            source = futures[future]
            previous = old_feed_status.get(source["id"], {})
            try:
                items = future.result()
                feed_success += 1
                for item in items:
                    old_by_id[item["id"]] = item
                feed_status.append({
                    "id": source["id"], "name": source["name"], "url": source["url"],
                    "website": source.get("website"), "archiveUrl": source.get("archiveUrl"),
                    "status": "ok", "checkedAt": now_iso, "lastSuccessAt": now_iso,
                    "itemCount": len(items), "error": None,
                })
            except Exception as exc:
                feed_status.append({
                    "id": source["id"], "name": source["name"], "url": source["url"],
                    "website": source.get("website"), "archiveUrl": source.get("archiveUrl"),
                    "status": "error", "checkedAt": now_iso,
                    "lastSuccessAt": previous.get("lastSuccessAt"),
                    "itemCount": previous.get("itemCount", 0),
                    "error": f"{type(exc).__name__}: {str(exc)[:180]}",
                })

    repos_config = config.get("repositories", [])
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(repos_config)))) as pool:
        futures = {pool.submit(fetch_repo, repo, now_iso): repo for repo in repos_config}
        repo_items = []
        for future in concurrent.futures.as_completed(futures):
            repo = futures[future]
            try:
                result, error = future.result()
            except Exception as exc:
                result, error = dict(repo), str(exc)[:180]
            previous = old_repo_by_id.get(repo["id"], {})
            if result.get("metadataStatus") != "ok" and previous:
                result = {**previous, **{k: v for k, v in result.items() if v is not None}}
                result["metadataStatus"] = "cached"
            if result.get("metadataStatus") == "ok":
                repo_success += 1
                result = observed_stars(result, previous, now)
            repo_items.append(result)
            repo_status.append({
                "id": repo["id"], "repo": repo["repo"],
                "status": "ok" if result.get("metadataStatus") == "ok" else "cached",
                "checkedAt": now_iso, "error": error,
            })

    feed_items = list(old_by_id.values())
    feed_items.sort(key=lambda x: x.get("publishedAt") or x.get("discoveredAt") or "", reverse=True)
    feed_items = feed_items[:400]
    repo_items.sort(key=lambda x: x.get("priority", 999))
    feed_status.sort(key=lambda x: x["name"])
    repo_status.sort(key=lambda x: x["repo"])

    write_json(FEED_DATA, {"generatedAt": now_iso, "items": feed_items})
    snapshots = [(name, load_json(ROOT / "site/data" / filename, {})) for name,filename in
                 (("AIHOT","aihot-items.json"),("AIPick","aipick-data.json"))]
    discovery=discover_repos(snapshots,old_repos.get("researchDiscovery",{}),repos_config,now)
    write_json(REPO_DATA, {"generatedAt": now_iso, "items": repo_items, "researchDiscovery": discovery})
    write_json(STATUS_DATA, {
        "checkedAt": now_iso,
        "feedCount": len(active_feeds),
        "feedSuccess": feed_success,
        "feedFailed": len(active_feeds) - feed_success,
        "repositoryCount": len(repos_config),
        "repositorySuccess": repo_success,
        "feeds": feed_status,
        "repositories": repo_status,
        "researchDiscovery": {k:v for k,v in discovery.items() if k not in {"items","recentPointerAttempts"}},
    })
    print("Creative repository discovery:",json.dumps({k:v for k,v in discovery.items() if k not in {"items","recentPointerAttempts"}},ensure_ascii=False))
    print(f"Resources: {feed_success}/{len(active_feeds)} RSS feeds OK; {repo_success}/{len(repos_config)} GitHub repos refreshed.")
    for item in feed_status:
        print(f"[{item['status'].upper()}] {item['name']}: {item['itemCount']} items" + (f" — {item['error']}" if item.get("error") else ""))
    for item in repo_status:
        print(f"[{item['status'].upper()}] {item['repo']}" + (f" — {item['error']}" if item.get("error") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
