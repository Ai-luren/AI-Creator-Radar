# 自动更新说明

## 每日运行

`.github/workflows/update-site.yml` 每天 02:00 UTC（北京时间 10:00）运行一次。工作流测试后依次刷新模型发布、厂商发展史、资源状态、RSS / Awesome、榜单原始快照、统一榜单、AIHOT / 橘鸦简报、AIPick、模型评测候选和 Google Trends，再关联并校验模型引用。数据有变化时提交到 `main`；在 `main` 上还会发布 GitHub Pages。

普通 `main` push 只运行测试并发布 Pages，不启动重复采集。本机 Codex 自动化 `AI 创作台官方账号粉丝快照日更` 每天北京时间 21:00 单独更新官方账号粉丝 / 订阅快照。它开始前先读取 GitHub 最新状态，避免拿过期快照覆盖远端数据。

RSS / Awesome 资源采集先于橘鸦简报，因为后者会使用本轮资源列表。任务按顺序执行，任一步失败都会跳过后续步骤；需要即时刷新时可在 Actions 手动运行 `workflow_dispatch`。GitHub 定时任务可能延迟启动。

## 自动更新范围

- GitHub Actions 运行工作流中明确列出的采集器，只覆盖配置好的来源。
- 官方社媒粉丝快照由本机 Ego Lite 任务采集，不由 GitHub Actions 抓取。
- Google Trends 更新社媒趋势，不等于自动抓取官方账号发帖。
- 创作工具与 CPP 目录是人工核实的维护型数据，目前没有可靠的自动发现采集器。
- 统一榜单由原始榜单快照派生；来源失败时需查看 Action 日志，不应把旧快照当作新数据。

## 维护入口

- 工作流：[`../.github/workflows/update-site.yml`](../.github/workflows/update-site.yml)
- 社媒快照规则：[`social-monitor-data-guide.md`](social-monitor-data-guide.md)
- 项目数据目录说明：[`README.md`](README.md)
