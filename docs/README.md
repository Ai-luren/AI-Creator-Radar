# 维护文档

首次接手时先看项目首页的运行方式，再按手头工作读对应指南。当前网站只有 `site/index.html` 一个入口，所有线上数据都从 `site/data/` 加载。

| 要做什么 | 先读 | 关键文件 |
|---|---|---|
| 理解整体目录与发布 | 本页、根目录 `AGENTS.md` | `.github/workflows/update-site.yml` |
| 修改模型目录或跨模块模型引用 | [模型数据契约](model-data-contract.md) | `site/data/models.json`、`scripts/link_model_records.py` |
| 审核模型上新与近 30 天列表 | [模型上新指南](model-release-digest-guide.md) | `scripts/build_model_release_digest.py` |
| 修改官方社媒账号快照 | [社媒数据指南](social-monitor-data-guide.md) | `site/data/social-accounts.json` |
| 理解能力榜的来源和展示口径 | [榜单方法审核](leaderboard-methodology-audit-2026-11-25.md)、[榜单规则](../site/ranking-rules.html) | `site/data/reference-rankings.json`、`site/data/maomu-rankings.json` |
| 查看综合榜实验与审计依据 | [榜单方法提案](leaderboard-methodology-proposal.md) | `scripts/build_unified_rankings.py`、`site/data/unified-rankings.json` |
| 检查每日自动更新和同步范围 | [自动更新说明](automation-runbook.md) | `.github/workflows/update-site.yml` |

## 数据更新原则

- `site/data/` 是唯一的线上数据目录。采集器只写入这里，不再维护 `data-vN` 镜像。
- `models.json` 是模型家族和具体版本的规范目录；发布摘要、评测记录和简报中的模型关联应引用其中的稳定 ID。
- 榜单原始快照保留来源名次和来源说明；生成的综合试算是派生数据，不能回写覆盖原始快照。
- 历史页面和旧数据放在 `archive/`，只作追溯，不作为运行时输入。

文件名按用途分组，保持一个目录和一份在线副本：

- **模型**：`models.json`、`model-updates.json`、`model-monitor-*.json`、`model-evaluations.json`、`model-practice.json`、`model-resource-status.json`、`model-releases-30d.json`。
- **榜单**：`rankings.json`、`ranking-sources.json`、`reference-rankings.json`、`maomu-rankings.json`、`leaderboard-reference-snapshots.json`、`unified-rankings.json`。
- **简报与动态**：`aihot-*.json`、`juya-daily.json`、`feed-items.json`、`news-today.json`、`topics.json`、`chronicle-updates-status.json`。
- **创作资源**：`aipick-data.json`、`awesome-repos.json`、`tutorials.json`、`resource-sources.json`、`resource-status.json`。
- **官方社媒**：`social-accounts.json`、`social-platforms.json`、`social-trends.json`。

## 本地检查

```bash
python3 -m unittest discover -s tests -v
python3 scripts/collect_models.py --dry-run
python3 scripts/build_model_release_digest.py
python3 scripts/link_model_records.py
python3 scripts/validate_model_links.py
```

日常文案、来源审核记录保留在 `docs/`；完成任务的临时实施计划归档到 `archive/engineering-history/`，不要把历史叙述加进 `AGENTS.md`。
