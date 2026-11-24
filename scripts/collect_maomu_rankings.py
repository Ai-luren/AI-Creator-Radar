#!/usr/bin/env python3
"""Collect Maomu's publicly rendered model ranking tables into local JSON."""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "site/data-v4/maomu-rankings.json"
BASE_URL = "https://maomu.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AI-Creator-Radar/1.0)"}

GROUPS = [
    {
        "id": "language",
        "name": "语言模型",
        "boards": [
            ("llm-aa", "Artificial Analysis · 智能指数", "/rank/models?limit=200"),
            ("llm-benchlm", "BenchLM · 综合与专项", "/rank/models/benchlm?limit=200"),
            ("llm-stats", "LLM Stats · 综合", "/rank/models/llm-stats?limit=200"),
            ("llm-livebench", "LiveBench · 综合", "/rank/models/livebench?limit=200"),
            ("llm-arena-text", "Arena · 文本偏好", "/rank/models/arena-text?limit=200"),
            ("llm-coding", "Arena · 编程能力", "/rank/models/coding?limit=200"),
            ("llm-agents", "Arena · 智能体能力", "/rank/models/agents?limit=200"),
            ("llm-reasoning", "推理能力", "/rank/models/reasoning?limit=200"),
            ("llm-mathematics", "数学能力", "/rank/models/mathematics?limit=200"),
            ("llm-open-models", "开放模型", "/rank/models/open-models?limit=200"),
        ],
    },
    {
        "id": "image",
        "name": "图片生成",
        "boards": [
            ("image-aa-t2i", "Artificial Analysis · 文生图", "/rank/models/image-generation?limit=200"),
            ("image-aa-edit", "Artificial Analysis · 图片编辑", "/rank/models/image-editing?limit=200"),
            ("image-arena-t2i", "Arena · 文生图", "/rank/models/arena-image-generation?limit=200"),
            ("image-arena-edit", "Arena · 图片编辑", "/rank/models/arena-image-editing?limit=200"),
        ],
    },
    {
        "id": "video",
        "name": "视频生成",
        "boards": [
            ("video-aa-t2v", "Artificial Analysis · 文生视频", "/rank/models/video-generation?limit=200"),
            ("video-aa-i2v", "Artificial Analysis · 图生视频", "/rank/models/image-to-video?limit=200"),
            ("video-arena-t2v", "Arena · 文生视频", "/rank/models/arena-video-generation?limit=200"),
            ("video-arena-i2v", "Arena · 图生视频", "/rank/models/arena-image-to-video?limit=200"),
        ],
    },
    {
        "id": "multimodal",
        "name": "多模态理解",
        "boards": [
            ("multimodal-benchlm", "BenchLM · 多模态理解", "/rank/models/multimodal?limit=200"),
            ("multimodal-vision", "Arena · 视觉理解", "/rank/models/vision?limit=200"),
            ("multimodal-documents", "Arena · 文档理解", "/rank/models/documents?limit=200"),
        ],
    },
]

BOARD_DESCRIPTIONS = {
    "llm-aa": "用综合指数快速查看模型整体能力、速度和成本，适合初筛，不代表某项具体任务。",
    "llm-benchlm": "看模型总能力以及推理、数学、编程等专项表现，适合按任务找强项。",
    "llm-stats": "综合比较语言模型能力及推理、编程等细项，适合快速横向筛选。",
    "llm-livebench": "用持续更新的题目比较模型通用能力，尽量减少训练数据记忆带来的影响。",
    "llm-arena-text": "用户对两个匿名回答投票，排名反映大家更喜欢哪个模型的回答。",
    "llm-coding": "通过匿名编程回答对战，比较用户更认可哪个模型写出的代码。",
    "llm-agents": "比较模型执行多步任务的表现，不等同于单轮聊天能力。",
    "llm-reasoning": "重点比较模型解决逻辑和推理问题的能力。",
    "llm-mathematics": "重点比较模型解数学题、计算和证明问题的表现。",
    "llm-open-models": "筛选开放权重或开放许可模型，方便寻找可自行部署的选择。",
    "image-aa-t2i": "用盲测偏好比较文字生成图片的效果，并展示样本量和参考价格。",
    "image-aa-edit": "用相同输入图和编辑要求比较模型修改图片的效果。",
    "image-arena-t2i": "用户对匿名文生图结果投票，排名反映社区偏好。",
    "image-arena-edit": "用户对匿名图片编辑结果投票，比较按要求修改图片的表现。",
    "video-aa-t2v": "用盲测偏好比较文字生成视频的效果。",
    "video-aa-i2v": "用盲测偏好比较图片生成视频的效果，关注动作和主体保持。",
    "video-arena-t2v": "用户对匿名文生视频结果投票，排名反映大家更喜欢哪段视频。",
    "video-arena-i2v": "用户对匿名图生视频结果投票，比较画面动起来后的效果和稳定性。",
    "multimodal-benchlm": "比较模型看图、读图表等理解能力，并提供综合、编程和推理分数作参考。",
    "multimodal-vision": "通过匿名看图问答对战，比较模型理解图片并回答问题的表现。",
    "multimodal-documents": "通过匿名文档任务对战，比较模型读取和提取文档信息的能力。",
}


class RankingHTMLParser(HTMLParser):
    """Extract table headings, row cells, links and small/bold metric labels."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict] = []
        self.headings: list[str] = []
        self.all_text = ""
        self.page_title = ""
        self.h1_text = ""
        self.meta_date = ""
        self._in_title = False
        self._in_h1 = False
        self._in_thead = False
        self._in_header_cell = False
        self._header_text = ""
        self._row: dict | None = None
        self._cell: dict | None = None
        self._anchor: dict | None = None
        self._marked: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        classes = (attrs_map.get("class") or "").split()
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
        elif tag == "thead":
            self._in_thead = True
        elif tag == "th" and self._in_thead:
            self._in_header_cell = True
            self._header_text = ""
        elif tag == "tr" and attrs_map.get("data-rank"):
            self._row = {"rank": attrs_map.get("data-rank"), "cells": []}
        elif tag in ("td", "th") and self._row is not None:
            self._cell = {"class": classes, "text": "", "links": [], "small": [], "strong": [], "bold": []}
        elif tag == "a" and self._cell is not None:
            self._anchor = {"href": attrs_map.get("href"), "text": ""}
        elif tag in ("small", "strong", "b") and self._cell is not None:
            self._marked = {"tag": tag, "text": ""}

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if not value:
            return
        self.all_text = (self.all_text + " " + value).strip()
        if self._in_title:
            self.page_title += value
        if self._in_h1:
            self.h1_text += value
        if self._in_header_cell:
            self._header_text += value
        if self._cell is not None:
            self._cell["text"] = (self._cell["text"] + " " + value).strip()
        if self._anchor is not None:
            self._anchor["text"] = (self._anchor["text"] + " " + value).strip()
        if self._marked is not None:
            self._marked["text"] = (self._marked["text"] + " " + value).strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "th" and self._in_header_cell:
            if self._header_text:
                self.headings.append(self._header_text)
            self._in_header_cell = False
        elif tag == "thead":
            self._in_thead = False
        elif tag == "a" and self._anchor is not None and self._cell is not None:
            self._cell["links"].append(self._anchor)
            self._anchor = None
        elif tag in ("small", "strong", "b") and self._marked is not None and self._cell is not None:
            key = {"small": "small", "strong": "strong", "b": "bold"}[tag]
            if self._marked["text"]:
                self._cell[key].append(self._marked["text"])
            self._marked = None
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row["cells"].append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def _clean_provider(value: str) -> tuple[str, str | None]:
    match = re.search(r"\s*[·|]\s*原榜\s*#?(\d+)\s*$", value)
    original_rank = match.group(1) if match else None
    return re.sub(r"\s*[·|]\s*原榜\s*#?\d+\s*$", "", value).strip(), original_rank


def _normal_key(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.casefold())


def normalize_rows(raw_rows: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_rows:
        cells = raw.get("cells", [])
        if len(cells) < 3:
            continue
        model_cell = next((cell for cell in cells if "rank-model" in cell["class"]), cells[1])
        score_cell = next((cell for cell in cells if "rank-score" in cell["class"]), cells[2])
        links = model_cell.get("links", [])
        name = (links[0].get("text") if links else "") or model_cell.get("text", "")
        name = re.sub(r"\s+", " ", name).strip()
        provider_cell = model_cell.get("small", [])
        provider, original_rank = _clean_provider(provider_cell[0] if provider_cell else "")
        key = (_normal_key(provider), _normal_key(name))
        if not name or key in seen:
            continue
        seen.add(key)
        score_values = score_cell.get("strong", [])
        score_labels = score_cell.get("small", [])
        metrics = []
        for cell in cells:
            if "rank-metric-cell" not in cell["class"]:
                continue
            label = cell.get("small", [""])[0]
            values = cell.get("bold", [])
            value = values[0] if values else cell.get("text", "")
            if label and value:
                metrics.append({"label": label, "value": value})
        detail_cell = next((cell for cell in cells if "rank-origin" in cell["class"]), None)
        detail_href = detail_cell["links"][0].get("href") if detail_cell and detail_cell["links"] else None
        normalized.append({
            "rank": int(raw["rank"]),
            "name": name,
            "provider": provider or "未注明",
            "originalRank": original_rank,
            "score": score_values[0] if score_values else "",
            "scoreLabel": score_labels[0] if score_labels else "评分",
            "metrics": metrics,
            "detailUrl": urljoin(BASE_URL, detail_href) if detail_href else "",
        })
    return normalized


def fetch_board(board_id: str, name: str, path: str, timeout: int = 20) -> dict:
    url = urljoin(BASE_URL, path)
    last_error = None
    for attempt in range(3):
        try:
            request = Request(url, headers=HEADERS)
            with urlopen(request, timeout=timeout) as response:
                html = response.read().decode("utf-8", "replace")
            break
        except Exception as exc:
            last_error = exc
            if attempt == 2:
                raise
            time.sleep(0.8 * (attempt + 1))
    else:
        raise last_error or RuntimeError("Could not fetch board")
    parser = RankingHTMLParser()
    parser.feed(html)
    rows = normalize_rows(parser.rows)
    if not rows:
        raise ValueError("榜单页面未解析到有效行")
    method = " · ".join(parser.headings)
    return {
        "id": board_id,
        "name": name,
        "url": url,
        "source": parser.h1_text or parser.page_title,
        "evaluationSource": _find_evaluation_source(html),
        "description": BOARD_DESCRIPTIONS.get(board_id, "比较该评测任务下的模型表现；请按页面标注的评分口径理解排名。"),
        "headers": parser.headings,
        "method": method,
        "updatedAt": _find_updated_date(html),
        "collectedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "rows": rows,
        "rowCount": len(rows),
    }


def _find_updated_date(html: str) -> str:
    match = re.search(r"(?:采集\s*/\s*更新|更新)\s*[：:]?\s*(20\d{2}-\d{2}-\d{2})", html)
    return match.group(1) if match else ""


def _find_evaluation_source(html: str) -> str:
    heading = re.search(r'<header[^>]*class="[^"]*ranking-heading[^"]*"[^>]*>(.*?)</header>', html, re.S)
    if not heading:
        return "猫目整理"
    plain = re.sub(r"<!--.*?-->", " ", heading.group(1), flags=re.S)
    plain = html_lib.unescape(re.sub(r"<[^>]+>", " ", plain))
    plain = re.sub(r"\s+", " ", plain)
    match = re.search(r"评测来源\s*(.*?)\s*采集\s*/\s*更新", plain)
    if match:
        return match.group(1).strip()
    return "猫目整理"


def load_previous() -> dict:
    if not OUTPUT.exists():
        return {"source": "猫目", "sourceUrl": f"{BASE_URL}/rank", "categories": []}
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"source": "猫目", "sourceUrl": f"{BASE_URL}/rank", "categories": []}


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect publicly rendered Maomu ranking tables.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report without writing JSON.")
    parser.add_argument("--board", help="Collect one board by ID.")
    args = parser.parse_args()
    previous = load_previous()
    old_categories = {category.get("id"): category for category in previous.get("categories", [])}
    old_boards = {board.get("id"): board for category in old_categories.values()
                  for board in category.get("boards", [])}
    new_categories = []
    success_count = error_count = 0

    for group in GROUPS:
        boards = []
        for board_id, name, path in group["boards"]:
            if args.board and args.board != board_id:
                old = old_boards.get(board_id)
                if old:
                    boards.append(old)
                continue
            try:
                board = fetch_board(board_id, name, path)
                boards.append(board)
                success_count += 1
                print(f"[OK] {group['name']} / {name}: {board['rowCount']} 条，更新 {board['updatedAt'] or '未注明'}")
            except Exception as exc:
                error_count += 1
                old = old_boards.get(board_id)
                if old:
                    boards.append(old)
                print(f"[WARN] {group['name']} / {name}: {type(exc).__name__}: {str(exc)[:180]}（保留上次数据）")
            if not args.board:
                time.sleep(0.15)
        new_categories.append({"id": group["id"], "name": group["name"], "boards": boards})

    output = {
        "source": "猫目",
        "sourceUrl": f"{BASE_URL}/rank",
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "successfulBoards": success_count,
        "failedBoards": error_count,
        "categories": new_categories,
    }
    print(f"Maomu rankings: {success_count} 成功，{error_count} 失败（失败项保留旧数据）。")
    if not args.dry_run:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        temp = OUTPUT.with_suffix(".json.tmp")
        temp.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        temp.replace(OUTPUT)
        print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0 if success_count else 1


if __name__ == "__main__":
    sys.exit(main())
