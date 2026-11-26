# 自动更新与发布说明

## 独立工作流

- **Publish validated GitHub Pages**（`deploy-pages.yml`）：main 的网页/测试/发布配置变更直接验证已提交快照并发布。不访问外部采集来源。定时采集成功提交新数据后显式调用同一个发布流程；GITHUB_TOKEN 的 push 不会自动触发另一个 push 工作流。
- **Refresh radar data**（`update-site.yml`）：定时、手动及采集代码/配置变更时检查到期组。普通 UI 和文档修改不启动全网采集。独立串行；采集期间 main 变更时不覆盖新数据，下一次触发补采。
- PR 的静态、Chromium、WebKit 验证独立运行，取消已被新提交替代的验证；一批修改合成一次提交后开 PR。只有明确浏览器崩溃或断开才允许一次新上下文重试，断言、运行时异常和普通超时仍是失败。

## 调度与新鲜度目标（北京时间）

GitHub cron 尽力而为，不承诺准点；每个定时触发按快照时间检查各组，漏跑可由下一次触发补采。修改采集配置也检查超期组。手动范围保持兼容。

| 组 | 目标 |
| --- | --- |
| 模型、AIHOT 精选 | 约 30 分钟 |
| 两份日报 | 北京时间 08:05/08:15、10:05/10:15 优先，按刊期独立补采 |
| 榜单及资源 | 约 6 小时 |
| 维护 | 约 24 小时 |

触发保留每小时 07、37 分，资源 04:17/10:17/16:17/22:17，维护 10:13。快照缺失、无效、未来时间触发补采。社媒粉丝仍由本机任务每天 21:00 尝试更新；不伪造数据或快照时间。

## 手动操作

Actions → Publish validated GitHub Pages → Run workflow → main：仅重新验证和发布。
Actions → Refresh radar data → Run workflow → main：`all`、`models`、`resources`、`maintenance`；旧 `deploy-only` 范围转调独立发布流程。

## 故障和通知

- 已提交的有效快照始终可用于独立网页发布。真实代码、数据结构、共享引用、发布权限错误仍阻止相关流程，不能以忽略测试制造成功。
- AIHOT 精选有限重试；两份日报独立、原子写入。失败保留旧快照和日期，记录 warning；`site/data/collection-health.json` 记录三条简报来源的尝试、最后成功及连续失败次数，第三次连续失败在 Actions 摘要和日志中记录一次持续故障 warning，不将可降级信源异常伪装成整个工作流失败，也不触发失败邮件；后续同一事件不重复升级告警，成功恢复后重新计数。跳过不计失败。其他采集器的内部信源警告仍见相应状态文件；未知脚本异常不隐藏。
- 官方信源 403、超时、零匹配应独立记录；零匹配不代表网络失败。模型发现不自动认定新版本首发。链接可达不代表报名开放，粉丝快照不代表独立受众。
- 数据先验证再提交；禁止 force push。并发 main 更新时放弃本轮过时结果，后续补采；权限等非并发推送失败必须报告。
- 发布包以运行 ID 与重试序号命名，上传后有限轮询 Actions API，确认唯一同名包、未过期且 ID 与本次上传一致，再交给 Pages；旧尝试的同名默认包不参与新发布。调用方只在发布任务增加 Actions 只读权限。元数据持续不可见仍明确失败，不伪造成功。遇到旧版同名包冲突，应启动新的独立发布，不重复重跑旧流程。
- 部署通过 Pages 环境后可读取线上 `deploy-revision.json` 确认实际发布的 commit。只通过 PR 测试不等于已经部署；定时准点和外部来源可用性不可保证。

## 提交门禁

本地先运行下面的验证，再完成 Chromium 与 WebKit 检查，最后集中提交。不得因暂时无法运行本地测试而声称通过，不用连续远端提交调试，不修改真实故障报警策略来掩盖失败。验证不代表定时调度按计划触发；漏跑和数据新鲜度另查。

## 本地验证

```sh
python3 -m unittest discover -s tests -v
node --test tests/test_overview.mjs
python3 scripts/plan_refresh.py --event schedule --output /tmp/radar-refresh-plan.txt
python3 scripts/collect_models.py --dry-run --report /tmp/radar-source-probe.json
```

浏览器测试使用 CI 同版本 Playwright 1.56.1；在仓库根目录安装隔离依赖并启动静态服务：

```sh
npm install --prefix /tmp/radar-browser --no-save --package-lock=false playwright@1.56.1
/tmp/radar-browser/node_modules/.bin/playwright install chromium webkit
python3 -m http.server 8765 --bind 127.0.0.1 --directory site
```

另一个终端执行：

```sh
RADAR_BROWSER_DEPS=/tmp/radar-browser RADAR_SCREENSHOTS=/tmp/radar-chromium RADAR_BROWSER_ENGINE=chromium node tests/test_browser_visual.mjs
RADAR_BROWSER_DEPS=/tmp/radar-browser RADAR_SCREENSHOTS=/tmp/radar-webkit RADAR_BROWSER_ENGINE=webkit node tests/test_browser_visual.mjs
```

- [独立发布](../.github/workflows/deploy-pages.yml)
- [生产采集](../.github/workflows/update-site.yml)
- [PR 验证](../.github/workflows/validate-radar.yml)
- [浏览器验收](../.github/workflows/browser-visual.yml)
- [社媒采集](social-monitor-data-guide.md)


## 日报刊期优先

AIHOT 08:05、08:15，橘鸦 10:05、10:15（北京时间）计划触发只采集到期日报；常规定时继续补采其他过期组。以当天刊期而非单纯抓取时间决定到期；当天刊期成功即停止重复抓取，尚未出现且距上次成功抓取约十分钟则再次检查。日报优先于慢速资源采集。GitHub cron 可能漏跑，尚不承诺准点，需要实际观测。
