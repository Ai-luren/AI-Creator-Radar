# AI 视频创作台

面向 AI 视频创作者的研究工作台：追踪模型上新，查看按任务拆分的能力参考榜，并集中查找官方案例、教程、行业简报和创作资源。

<p>
  <strong><a href="https://ai-luren.github.io/AI-Creator-Radar/">打开线上工作台 ↗</a></strong> ·
  <a href="site/ranking-rules.html">榜单规则</a> ·
  <a href="docs/leaderboard-methodology-audit-2026-11-25.md">方法审核记录</a>
</p>

<p align="center">
  <img src="./assets/readme/hero.svg" width="100%" alt="AI 视频创作台的能力榜单页面：侧栏导航、分类页签、榜单来源快照和保留原始名次的排行表。">
</p>

## 工作台内容

- **今日概览**：默认首页，汇总近7天已核实模型、待复核发现、两份日报刊期、AIHOT 精选和信源检查状态；优先加载必要快照，完整数据在原模块查看。
- **近期上新与模型库**：按模型家族和具体版本查官方发布日期、发布证据、体验入口、演示和教程。
- **创作者能力参考榜**：图片、视频、音乐、语音合成和编程各看一套来源原榜；每榜最多显示 10 个合资格候选；宽屏视频双榜并排。
- **行业简报与官方账号**：阅读 AIHOT 日报、AIHOT 精选与橘鸦等来源，查看八平台粉丝矩阵与已知粉丝合计（跨平台未去重）。
- **厂商发展史**：按时间查看重要产品与模型节点；自动采集的新节点会标明待复核。
- **创作工具与 GitHub 资源**：查找常用工具和精选 Awesome 仓库，保留原始链接与许可证信息。

## 榜单怎么读

主榜沿用各评测来源自己的任务、分数和名次，不把不同机构或任务池的分数相加，也不把偏好榜解释成市场使用量或创作者采用率。

- **图片 · Arena**：文生图用户偏好。
- **视频 · Artificial Analysis**：有声文生和有声图生分开显示，各自保留独立名次。
- **音乐 · Artificial Analysis**：含人声整曲榜。
- **语音合成 · Artificial Analysis**：全量 Provider Voice 榜，包含 ElevenLabs。
- **编程 · Arena Code**：用户偏好榜，不等同于单元测试通过率。

候选筛选不会重排来源名次；视频榜从原榜前 20 名中按基础模型资格、身份核实和家族去重规则筛出最多 10 项。榜单快照日期、区间、样本量和排除理由可在页面中查看。详细口径见[榜单规则](site/ranking-rules.html)。

## 数据来源与更新

- 模型版本与发布日期优先依据厂商公告、官方文档和官方模型卡。
- RSS / Atom 配置在 [`config/resource-sources.json`](config/resource-sources.json)；GoodCase 提供案例与 Prompt 预览，橘鸦提供早报，AIHOT 精选单独保留原始出处。
- GitHub Awesome 模块同步精选仓库的公开元数据，不会自动克隆仓库或复制其中的 Prompt。
- 官方社媒粉丝数由本机任务在北京时间 21:00 采集；其他已配置的动态采集与榜单派生由 GitHub Actions 执行。
- GitHub Actions 按快照新鲜度补采：模型与 AIHOT 精选约 30 分钟、日报约 2 小时、榜单与资源约 6 小时、维护约每日一次；main push 也补采超期组。GitHub 定时任务可能延迟或漏跑，首页标注延迟。详细规则见[运行手册](docs/automation-runbook.md)。
- 原始榜单采集后，Actions 会运行 [`scripts/build_unified_rankings.py`](scripts/build_unified_rankings.py) 重建统一榜单。创作工具与 CPP 目录属于维护型数据；创作机会自动扫描仅发现待审核线索。

## 本地运行

需要 Python 3.10+，无需额外 Python 依赖。启动本地工作台：

```bash
python3 scripts/serve_local.py --port 8080
```

脚本会打开 `http://127.0.0.1:8080/`。常用维护命令：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/collect_models.py --dry-run
python3 scripts/collect_rankings.py --dry-run
python3 scripts/collect_maomu_rankings.py --dry-run
python3 scripts/build_unified_rankings.py
```

## 数据与隐私边界

- 资讯摘要和来源等级帮助筛选内容，不代表本站对内容作了独立事实背书；缺少一手证据时，不补猜发布日期或版本。
- 浏览器 `localStorage` 只保存模型评测候选整理进度和个人偏好，不会同步到服务器。
- 页面不调用生成式模型推理 API。RSS、公开榜单和其他采集器只按项目配置读取公开来源。

## 关键目录

- `site/index.html`：唯一工作台入口；`site/assets/` 是页面静态资源。
- `site/data/`：当前页面与采集器共用的唯一数据目录。
- `scripts/`、`config/`：采集与构建脚本、来源配置。
- `docs/`：维护指南与榜单方法；`archive/`：只读历史材料与已完成工程记录。
- `.agents/skills/`：本项目专用 Skills。

目录职责与维护文档入口见 [`docs/README.md`](docs/README.md)。

## License

[MIT](LICENSE)

## 检索与分享

顶部“全局搜索”（⌘K / Ctrl+K）检索本地已收录的模型、新闻、历史、教程、官方账号和创作者计划；页面内筛选独立保留。支持复制地址栏链接分享当前模块、筛选与具体模型版本，例如 `?view=models&model=seedance&version=seedance-2-0`。不需要额外 API 或账户。

## 创作机会与实战资源

创作机会汇总比赛与既有 CPP/创作者计划，按公开截止日期与证据状态筛选；本地记录关注、准备、已提交等进度。比赛来源需人工复核，第三方目录只作为发现入口。教程与案例增加通用原创提示词模板、官方提示词指南、社区案例节选及基于官方资料的模型选型；不调用推理 API。

创作机会链接在每日维护中做 HTTP 连通性检测；与实际开放报名和资格审查无关。新增赛事仍需官方规则人工核对。

## 运行与验证

首页仅加载概览快照；其他页面及全局索引按需下载，当前页面生命周期复用请求。开发 PR 运行 `Validate radar changes`，需要联网诊断时手动勾选 `probe_sources`；main 的定时采集部署工作流独立运行。测试失败不会被忽略，也不会关闭 GitHub 通知。浏览器布局测试仍独立保留。

### 正式环境手动验证

在 main 分支的 Actions → Monitor official AI model releases and deploy Pages → Run workflow 中选择 `scope`：

- `models`：模型发现、近期上新、厂商历史与 AIHOT 精选。
- `resources`：榜单、简报、资源、创意与社媒趋势。
- `maintenance`：链接检查与模型评测候选。
- `all`：执行所有采集任务（默认）。
- `deploy-only`：只验证现有数据并重新发布 Pages，不采集、不提交数据。

AIHOT 精选及两份日报失败时保留旧快照并独立报告；其他通过校验的数据可发布。其他采集器、结构校验或部署失败仍会阻止相应流程。

生产验收需分别记录 main 首次 push 部署、models/resources/maintenance 定时运行及数据时间戳，并核对线上快照。手动触发成功不代表定时触发成功。

### 官方信源可靠性

Google AI 专项 RSS（`https://blog.google/innovation-and-ai/technology/ai/rss/`）取代返回 HTML 的旧 `/feed/`；总站 RSS 为失败时的备选。Niji 优先英文官方博客，中文为备选；仅提取明确编号的发布文章链接，不从目录推断发布日期。候选仍需人工审核，已有模型证据不被自动覆盖。

官方模型采集对 HTTP 408、429、5xx 和部分暂时性连接错误最多重试一次；403 和解析错误不重复请求，配置了备用入口时尝试备用入口。状态快照保留主入口、实际入口、尝试记录和最后成功时间。合法空 RSS 不算网络故障，也不因无新增模型自动切换来源。涉及模型采集器或信源配置变更的 PR 自动执行只读联网诊断并上传报告；诊断完成不等于所有来源均健康。

### 创作机会自动发现与申请状态

每日到期维护任务执行 `scripts/collect_creator_opportunities.py`。6 个公开比赛索引与 7 个公开创作者计划页面配置在 `config/creator-opportunity-sources.json`。不使用付费 API/LLM，不登录、不提交表单、不访问用户私人数据。每页有超时与体积上限；仅同站且符合路径及标题/slug 关键词的链接进入待审核池（最多 180 条，45 天保留期限），不会自动填造奖金、日期或资格。失败与零匹配独立记录；暂时失败不立即删除旧候选。官方页面线索也必须人工复核才能进入正式赛事。首次扫描前数据为显式空快照。

`creator-contests.json` 是人工审核的赛事清单（12 项）；`social-platforms.json` 中 30 个创作者计划入口保留原 ID 与链接，其中 6 项已补本轮有日期的 `applicationReview`。开放、仅有申请入口、关闭、邀请制和待确认分别表示不同证据，不将链接可达或自动识别的文字视为实时开放。正式状态超过 14 天自动降级为待复核；与同一证据页面的自动信号冲突时亦降级。原申请进度仍保存在浏览器，不自动申请。未核实的 24 项保持待确认；地区/版权/资格和实际表单提交能力需独立核对。

```sh
python scripts/collect_creator_opportunities.py --dry-run
python scripts/collect_creator_opportunities.py --report /tmp/opportunities-probe.json
python scripts/check_creator_links.py --dry-run
```

PR 触及采集器或配置时会进行只读联网诊断并上传 artifact；实际生产快照需 main 首次维护任务生成。诊断成功仅表示扫描过程完成，不表示所有外部页面可访问或报名开放。
