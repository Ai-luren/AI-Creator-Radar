# 维护文档

首次接手时先看项目首页的运行方式，再按手头工作读对应指南。当前网站只有 `site/index.html` 一个入口，所有线上数据都从 `site/data/` 加载。

| 要做什么 | 先读 | 关键文件 |
|---|---|---|
| 理解整体目录与发布 | 本页、根目录 `AGENTS.md` | `.github/workflows/update-site.yml`、`.github/workflows/deploy-pages.yml` |
| 修改当前界面与交互 | [设计系统](../DESIGN.md) | `site/index.html`、`tests/test_browser_visual.mjs` |
| 修改模型目录或跨模块模型引用 | [模型数据契约](model-data-contract.md) | `site/data/models.json`、`scripts/link_model_records.py` |
| 审核模型上新与近 30 天列表 | [模型上新指南](model-release-digest-guide.md) | `scripts/build_model_release_digest.py` |
| 修改官方社媒账号快照 | [社媒数据指南](social-monitor-data-guide.md) | `site/data/social-accounts.json` |
| 理解能力榜的来源和展示口径 | [榜单方法审核](leaderboard-methodology-audit-2026-11-25.md)、[榜单规则](../site/ranking-rules.html) | `site/data/reference-rankings.json`、`site/data/maomu-rankings.json` |
| 查看当前原榜规则 | [现行方法审计](leaderboard-methodology-audit-2026-11-25.md)、[榜单规则](../site/ranking-rules.html) | `site/data/unified-rankings.json` 的原榜字段 |
| 查看历史综合榜实验 | [历史方法提案](leaderboard-methodology-proposal.md) | `scripts/build_unified_rankings.py`（现行生成器仍同时执行历史试算，未完成退役） |
| 检查自动更新、漏跑补采和同步范围 | [自动更新说明](automation-runbook.md)、[Cloudflare 运维指南](../ops/cloudflare-watchdog/README.md) | `scripts/plan_refresh.py`、`scripts/scheduler_manifest.py`、`ops/cloudflare-watchdog/wrangler.toml` |

## 当前结构（V3.6）

- 十个入口顺序见 [README](../README.md#功能结构v36) 与 [DESIGN](../DESIGN.md)，教程与案例在最后。
- 四大展示类与音频子类只改变前端映射，数据字段、原榜任务及版本 ID 不迁移。
- 首页正式发布统计、近期上新四种模式（正式发布、待复核、官方公告、产品更新）、最新一天简报、模型库日期倒序，以现行设计规范为准。旧迭代说明已归档，不作为当前开发规则。

## 数据更新原则

- `site/data/` 是唯一的线上数据目录。采集器只写入这里，不再维护 `data-vN` 镜像。
- `models.json` 是模型家族和具体版本的规范目录；发布摘要、评测记录和简报中的模型关联应引用其中的稳定 ID。
- 榜单原始快照保留来源名次和来源说明；生成的综合试算是派生数据，不能回写覆盖原始快照。
- 历史页面和旧数据放在 `archive/`，只作追溯，不作为运行时输入。

文件名按用途分组，保持一个目录和一份在线副本：

- **模型**：`models.json`、`model-updates.json`、`model-monitor-*.json`、`model-evaluations.json`、`model-practice.json`、`model-resource-status.json`、`model-releases-30d.json`。
- **榜单**：`rankings.json`、`ranking-sources.json`、`reference-rankings.json`、`maomu-rankings.json`、`leaderboard-reference-snapshots.json`、`unified-rankings.json`。
- **简报与动态**：`aihot-*.json`、`juya-daily.json`、`feed-items.json`、`topics.json`、`chronicle-updates-status.json`。
- **创作资源**：`aipick-data.json`、`awesome-repos.json`、`tutorials.json`、`resource-sources.json`、`resource-status.json`。
- **创作机会**：`creator-contests.json`、`creator-link-status.json`、`creator-opportunity-discovery.json`。
- **官方社媒**：`social-accounts.json`、`social-platforms.json`、`social-trends.json`。
- **发现与证据**：`cross-platform-discovery.json`、`lead-resolution.json`、`model-intake.json`、`model-release-verification-status.json`、`release-recall-status.json`。
- **运行治理**：`collection-health.json`（尝试、成功和连续失败）、`scheduler-health.json`（到期与可重试边界）、`system-audit.json`（结构和覆盖审计）；线上 `deploy-revision.json` 为发布产物。

## 本地检查

```bash
python3 scripts/preflight.py
python3 -m unittest discover -s tests -v
node --test tests/test_overview.mjs tests/test_scheduler_worker.mjs tests/test_deploy_verified_pages.cjs
python3 scripts/collect_models.py --dry-run
python3 scripts/build_model_release_digest.py
python3 scripts/link_model_records.py
python3 scripts/validate_model_links.py
```

日常文案、来源审核记录保留在 `docs/`；完成任务的临时实施计划归档到 `archive/engineering-history/`，不要把历史叙述加进 `AGENTS.md`。

## 当前生产验收（2026-11-27）

Cloudflare 已部署为正式备用调度器，首次生产补采及 Pages 发布已成功，证据见运行手册。长期稳定性、主分支保护、本机 hook 激活、未核验信源及证据缺口仍需分别跟踪。历史方法提案与审计报告保留当时结论，不作为现行实现说明。


## 仓库卫生

现行文档相对文件链接与退役采集器隔离由 Python 回归测试自动检查。旧版综合新闻采集器及配套材料见 [历史归档](../archive/legacy-news/README.md)，不在生产任务或发布包中运行。
旧版 `site/data/news-today.json` 快照暂保留用于历史追溯，不参与现行简报或全局检索的数据加载；迁移或删除快照须先核查外部引用。
