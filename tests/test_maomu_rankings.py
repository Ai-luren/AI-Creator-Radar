import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.collect_maomu_rankings import BOARD_DESCRIPTIONS, GROUPS, RankingHTMLParser, _find_evaluation_source, normalize_rows


class MaomuRankingCollectorTests(unittest.TestCase):
    def test_each_visible_board_has_a_plain_language_explanation(self):
        board_ids = [board[0] for group in GROUPS for board in group["boards"]]
        self.assertEqual(len(board_ids), 21)
        self.assertEqual(set(board_ids), set(BOARD_DESCRIPTIONS))
        self.assertNotIn("llm-response-latency", board_ids)
        self.assertFalse({"llm-long-context", "llm-low-cost", "llm-fastest"} & set(board_ids))

    def test_reads_evaluation_source_from_ranking_header_only(self):
        html = '''<script>fake text: 评测来源 should not be considered</script>
        <header class="ranking-heading"><h1>视频模型</h1><p>描述</p>
        <div><span>评测来源 <strong>Artificial Analysis · 文生视频</strong></span>
        <span>采集 / 更新 <time>2026-11-21</time></span></div></header>'''
        self.assertEqual(_find_evaluation_source(html), "Artificial Analysis · 文生视频")

    def test_parses_ssr_model_rows_and_metrics(self):
        html = '''<h1>AI 视频生成模型排行榜</h1><table><thead><tr>
        <th>排名</th><th>模型 / 开发机构</th><th>Elo 评分</th><th>样本</th><th>95% CI</th>
        </tr></thead><tbody><tr class="rank-table-row" data-rank="1">
        <td>01</td><th class="rank-model"><span>U</span><span><a href="/models/example">Video Model X</a><small>Studio · 原榜 #4</small></span></th>
        <td class="rank-score"><strong>1175</strong><small>Elo 评分</small></td>
        <td class="rank-metric-cell"><small>样本</small><b>8,531</b></td>
        <td class="rank-metric-cell"><small>95% CI</small><b>±12</b></td>
        <td class="rank-origin"><a href="/models/example">详情</a></td>
        </tr></tbody></table>'''
        parsed = RankingHTMLParser()
        parsed.feed(html)
        rows = normalize_rows(parsed.rows)
        self.assertEqual(parsed.h1_text, "AI 视频生成模型排行榜")
        self.assertEqual(parsed.headings, ["排名", "模型 / 开发机构", "Elo 评分", "样本", "95% CI"])
        self.assertEqual(rows[0]["name"], "Video Model X")
        self.assertEqual(rows[0]["provider"], "Studio")
        self.assertEqual(rows[0]["originalRank"], "4")
        self.assertEqual(rows[0]["score"], "1175")
        self.assertEqual(rows[0]["metrics"][0], {"label": "样本", "value": "8,531"})
        self.assertEqual(rows[0]["detailUrl"], "https://maomu.com/models/example")

    def test_deduplicates_same_provider_and_model_but_keeps_distinct_models(self):
        row = {
            "rank": "1",
            "cells": [
                {"class": ["rank-position"], "text": "01", "links": [], "small": [], "strong": [], "bold": []},
                {"class": ["rank-model"], "text": "Video X", "links": [{"href": "/m/x", "text": "Video X"}], "small": ["Studio"], "strong": [], "bold": []},
                {"class": ["rank-score"], "text": "100 Elo", "links": [], "small": ["Elo"], "strong": ["100"], "bold": []},
            ],
        }
        duplicate = {**row, "rank": "2"}
        different_provider = {**row, "rank": "3", "cells": [row["cells"][0],
            {**row["cells"][1], "small": ["Other Studio"]}, row["cells"][2]]}
        self.assertEqual(len(normalize_rows([row, duplicate, different_provider])), 2)


if __name__ == "__main__":
    unittest.main()
