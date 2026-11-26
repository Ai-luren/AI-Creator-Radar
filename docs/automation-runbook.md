# 自动更新与发布说明

## 调度与新鲜度目标（北京时间）

生产仅 main 运行。GitHub Actions 的 cron 为尽力而为，并不承诺准点。每次定时触发根据实际持久化快照的时间戳判定各组是否到期；漏跑可在下一次触发补采。普通 main push 也检查超期数据，模型与精选在 push 时采用 2 小时阈值，避免频繁 UI 提交重复采集。

| 采集组 | 计划目标 | 内容 |
| --- | --- | --- |
| 模型 | 每约 30 分钟 | 官方模型发现、发布清单、厂商发展史 |
| 精选 | 每约 30 分钟 | AIHOT 精选 |
| 简报 | 每约 2 小时 | AIHOT 日报、橘鸦早报（刊期由来源决定） |
| 资源 | 每约 6 小时 | RSS、榜单、AIPick、社媒趋势 |
| 维护 | 每约 24 小时 | 模型资源、创作机会链接/候选、评测候选 |
| 普通 main push | 提交时 | 补采超期组、验证、Pages 部署 |

触发时间保留每小时 07、37 分、04:17/10:17/16:17/22:17、10:13；任务执行由 `scripts/plan_refresh.py` 基于快照决定，而不是由 cron 名称决定。缺失、无效、未来时间戳触发补采；不改写来源时间。PR 不写生产数据、不部署。

本机 Codex 自动化“AI 创作台官方账号粉丝快照日更”仍计划每日 21:00 单独采集，未读到则保留原快照；Google Trends 不等于抓取官方账号发帖。本工作流不代替该本机任务，也不承诺其成功。

## 手动操作

Actions → Monitor official AI model releases and deploy Pages → Run workflow → main。scope: `all` 全部、`models` 模型/精选、`resources` 资源/简报、`maintenance` 维护、`deploy-only` 不采集只验证并部署。

本地只读计划：

```sh
python3 scripts/plan_refresh.py --event schedule --output /tmp/radar-refresh-plan.txt
python3 scripts/collect_models.py --dry-run --report /tmp/radar-source-probe.json
```

## 故障与证据

- AIHOT 精选有限重试；两份日报独立采集、原子写入，失败保留旧快照并独立报告红色状态，其他通过验证的数据可发布。橘鸦直接查官方目录，异常回退实时官方 RSS，不用仓库旧 RSS 假装最新刊。
- 其他采集器失败仍可能阻止后续步骤；代码、数据结构及引用校验失败禁止发布。不重跑旧提交覆盖生产。先看 collect、deploy、report-collector-failure 三类结果。
- 官方信源 403、超时、零匹配独立记录，旧记录保留；零匹配不等同网络失败，不能靠猜测补日期。2026-11-26 既有 PR 诊断为 34 个活动信源中 33 个响应成功，Niji 两入口 403，5 个零匹配；该结果不是当前生产成功证明。生产仍需检查实际快照。
- 创作机会链接可达不代表报名开放；正式榜单保留原始快照日期；粉丝快照不是实时独立受众。
- 部署验收：检查 main 最新运行的计划输出、各采集组实际结果、数据提交与 Pages 部署；比对线上抓取时间和来源刊期。一次成功补采不证明未来 cron 准点。

## 维护入口

- [生产工作流](../.github/workflows/update-site.yml)
- [PR 基础验证](../.github/workflows/validate-radar.yml)
- [浏览器验收](../.github/workflows/browser-visual.yml)
- [社媒快照规则](social-monitor-data-guide.md)
- [项目目录说明](README.md)
