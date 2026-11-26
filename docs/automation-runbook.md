# 自动更新与发布说明

## 独立工作流

- **Publish validated GitHub Pages**（`deploy-pages.yml`）：main 的网页/测试/发布配置变更直接验证已提交快照并发布。不访问外部采集来源。定时采集成功提交新数据后显式调用同一个发布流程；GITHUB_TOKEN 的 push 不会自动触发另一个 push 工作流。
- **Refresh radar data**（`update-site.yml`）：定时、手动及采集代码/配置变更时检查到期组。普通 UI 和文档修改不启动全网采集。独立串行；采集期间 main 变更时不覆盖新数据，下一次触发补采。
- PR 的静态、Chromium、WebKit 验证独立运行，取消已被新提交替代的验证；一批修改合成一次提交后开 PR。只有明确浏览器崩溃或断开才允许一次新上下文重试，断言、运行时异常和普通超时仍是失败。

## 调度与新鲜度目标（北京时间）

GitHub cron 尽力而为，不承诺准点；每个定时触发按快照时间检查各组，漏跑可由下一次触发补采。修改采集配置也检查超期组，并强制实际执行模型事务（即使快照仍新鲜），普通 UI/文档变更不触发采集。手动范围保持兼容。

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

## 回归测试时间基准

Node 页面测试默认使用发布清单 windowEnd 对应北京时间当日末尾作为确定性测试时钟，具体时间边界用显式夹具覆盖。增加快照过期 60 天后的合法空状态测试；不修改生产时钟或数据更新时间。此项不代表全部动态数量断言和外部调度问题已解决。

## P0 采集可靠性与独立补偿

- 采集组使用 `scripts/run_collection_batch.py`：模型源、发布清单和发展史作为一项事务；资源、榜单、AIPick、社媒趋势各自独立；维护检查各自独立。超时、子进程失败、JSON 损坏、文件丢失或核心数组结构变化回滚对应事务，其他事务继续。无法恢复的事务错误写入阻断标记，禁止持久化。原有结构、Python、Node 和证据校验仍是强制门禁。
- 批次故障记录在 collection-health.json，连续第三次才生成新的真实持续故障通知，恢复后计数归零；原有可选简报告警规则不变。不把普通无新内容视为失败。
- checkedAt 是尝试时间，lastSuccessfulCheckAt 是最近至少一个模型信源成功读取的时间，lastCompleteCheckAt 是全部请求成功的时间（不代表全网事实完整）。全源失败保留原始更新快照；分组到期检查采用实际成功时间。资源组同时检查 Maomu、统一榜单、AIPick、社媒趋势；维护组检查模型测评。
- `workflow_dispatch` 新增 `scope=due`，按真实快照到期规划，不强行重抓全部。
- 备用调度必须来自 GitHub Cron 之外。已提供 `scripts/refresh_watchdog.py`，在有 GitHub CLI 授权的持续在线机器每 15 分钟运行。检测已有运行、40 分钟冷却期及各组快照，固定同一 main SHA 读取，只有确实到期才调度 `scope=due`。API 异常不发起采集。先执行 `python3 scripts/refresh_watchdog.py --dry-run` 验证，再接入本机 launchd 或独立外部调度器。凭据留在 gh 的安全存储；不得写入仓库。脚本存在不代表已安装或持续在线，必须实际验证。
- 待验证：真实生产采集故障演练、外部备用调度安装和漏跑恢复。GitHub 平台的定时触发仍非实时 SLA。

## 生产实跑门禁

采集代码、配置或采集工作流合入 main 后，模型事务不再受快照冷却期阻挡。必须检查生产 Actions 中模型事务实际执行、数据校验、持久化结果和发布结果；绿色但跳过采集的运行不能作为实跑验收。其他采集组仍按原刷新规划；GitHub 定时漏跑仍须独立调度器补偿。

## P1 官方信源与自动核验

模型事务顺序为采集 → 严格双源核验 → 上新派生视图 → 厂商发展史。新增智谱官方模型发布日志及 Meta AI 官方博客；Niji 英文博客作为第三种官方访问入口之一（不保证 GitHub runner 可访问）。GLM 日志为模型可用性发现，不能单独证实正式首发。只有明确官方双站点结构化发布日期与发布标题一致的最近记录才自动入库；不满足条件保留候选，不使用付费 LLM。独立备用调度仍需要已授权外部执行环境。

## 有效采集率（P1）

- 智谱使用原生 Markdown 日期/型号段落（不从正文提及推测版本）；Midjourney 与 Niji 在原入口受限或零匹配时可降级至官方版本说明，候选仅为 model-card，不能自动提升为正式首发。原入口、每次尝试的错误与匹配数量、实际入口、primaryDegraded 均保留。
- model-monitor-status.json 的 effectiveCoverage 分别记录可访问源、当前实际匹配模型家族的源、去重有效端点、当前有匹配的规范家族、近30天有日期候选家族和缺失家族。零匹配不等于网络故障；旧数据保留不计入当次有效覆盖。近30天候选数不等于已核验发布事件召回率，后者需要独立真值样本。
- 仅明确配置 fallbackOnZeroMatch 的信源才在空结果后尝试备用入口，其他保持原行为。不同格式的备用入口可以配置独立解析器；禁止尝试绕过登录或访问控制。

- 当公开版本 HTML 仍无法读取时，尝试官方帮助中心公开文章 JSON API，仅解析文章正文，禁止使用页面 updated_at 作为模型发布日。Qwen 首页零匹配时可使用官方 Qwen3.8 仓库 News；ElevenLabs 开发日志增加原生 Markdown 明确日期及型号标题解析。以上均保留候选性质。日志逐项输出异常入口和匹配数量，便于追查真实失败位置。

## 真实发布事件召回审计（P1）

固定首批八个官方公告样本见 config/release-recall-benchmark.json（独立查阅官方页面，非随机、非全量）。按公告事件而不是型号行计数，严格要求官方文章 URL、规范家族、全部目标型号标题模式、精确日期；本轮命中和仅历史保留分开，目录已确认与自动采集召回分开。冲突、缺日期、身份错误、漏采逐事件追踪；另设三个负样本。样本不反向注入采集数据、不写模型事实。每次模型事务生成 site/data/release-recall-status.json；缺漏报告不会阻止已有健康快照提交。

有限几个官方目录启用最多五篇文章详情复核，限配置的 HTTPS 官方主机；文章明确日期纠正列表误提取的候选日期并保留旧日期。不自动认定首发，article-explicit-date 不属于双源正式核验证据类型。教程、评测不再进入发布候选及新增发展史，既有人工历史节点不删除。Anthropic 增加官方模型公告分类。PR 源诊断可用 collect_release_recall.py --probe /tmp/radar-source-probe.json --dry-run 对照样本。

## 跨平台信源发现（P1）

新增 ElevenLabs、Qwen 官方 RSS；快手公司新闻、Z.ai 官方博客作为额外第一方入口。跨平台发现独立事务读取开源项目生成的 GitHub Raw RSS（Alan Turing Institute、Olshansk）、LLM World、LLM Releases、RSSHub 公共实例，以及 Hugging Face 四个官方组织的公开模型列表；不需要 Token、账号或自建服务器。外部来源单独输出 site/data/cross-platform-discovery.json，记录线索、来源、时间语义、官方原文 URL（严格主机/路径允许列表）、错误及首次/最近发现时间；官方仓库创建时间不等于模型首发时间。辅助源故障不阻止官方模型事务；不将外部 RSS、HF 上传直接写入权威模型库、正式发布或历史。后续可基于线索中的官方原文进一步核验，绝不以外部新闻或生成日期直接晋级。RSSHub 公共实例仅为可选项，失败保留记录。未部署 RSSHub/RSS-Bridge 容器；无需额外付费服务。

## 情报闭环与故障隔离（P1）

结构化辅助数据优先采用开放许可的 LLM World JSON（CC BY 4.0，数据源与许可证随线索保留），只读取事件明确关联的一手链接。辅助源连续失败指数退避，保留上次成功和实际尝试时间。辅助发现、官方原文恢复、派生上新、召回审计组成独立事务；失败不回滚已经成功的官方采集事务。每轮最多核验 12 个允许列表中的官方文章 URL，禁止跨站跳转，严格匹配文章标题、唯一模型家族及明确发布日期；日期冲突、教程、合作案例和未知身份不升级。成功观测保留来源、线索 ID、首次核验日期与最近核验时间，重试失败不伪造成功时间。恢复候选只进入待复核流，不写正式 releaseEvidence，不把外部发布日期、仓库创建日或文章发布日期自动等同首发。样本审计另计直接采集与原文恢复联合命中，避免把缓存当本轮抓取。刷新计划纳入新增快照，缺失快照会触发补跑。此阶段未部署外部调度器或自建 RSSHub。

## 已有简报与官方候选共享补证（P1）

AIHOT 精选、AIHOT 日报、橘鸦早报和现有官方候选索引直接读取仓库快照，不重复下载。仅模型类条目进入线索池；保留原始链接、报道日期/期号日期、实际快照观测时间及来源。只在标题明确包含规范模型名时提供翻译辅助提示，不按相似度猜型号；未经允许列表确认的社媒、仓库、媒体链接保留为未核验线索。将精选采集置于模型事务之前；仅简报更新时也独立运行补证事务。每轮预留最多四个重试位置，避免新线索长期挤占待补查文章。只有原文读取临时失败才保留历史成功观测；成功读取却发现日期/身份冲突时撤回旧候选。弱列表日期通过同一文章 URL、家族、标题与唯一明确文章日期更正派生视图，原始 model-updates.json 及人工已审历史/正式模型证据不改写；结构化来源日期冲突仍须审计。新增补证事务独立健康监测。
