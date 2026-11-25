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

- **近期上新与模型库**：按模型家族和具体版本查官方发布日期、发布证据、体验入口、演示和教程。
- **创作者能力参考榜**：图片、视频、音乐、语音合成和编程各看一套来源原榜；每榜最多显示 10 个合资格候选。
- **行业简报与官方账号**：阅读 AIHOT、橘鸦和 GoodCase 等来源，查看厂商及创作平台的官方主页快照。
- **厂商发展史**：按时间查看重要产品与模型节点；自动采集的新节点会标明待复核。
- **创作导航与 GitHub 资源**：查找常用工具和精选 Awesome 仓库，保留原始链接与许可证信息。

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
- 官方社媒粉丝数是带日期的人工公开主页快照，不是实时数据。
- GitHub Actions 在北京时间 08:00 和 10:00 刷新可采集数据。推送到 `main` 会先运行采集器测试，通过后才发布 GitHub Pages。
- 榜单生成器 [`scripts/build_unified_rankings.py`](scripts/build_unified_rankings.py) 当前不在 Actions 中运行；采集原始榜单后，需要手动运行它才能重建 V4 主榜与审计数据。

## 本地运行

需要 Python 3.10+，无需额外 Python 依赖。启动本地预览：

```bash
python3 scripts/serve_local.py --port 8080
```

脚本会打开 `http://127.0.0.1:8080/preview-v4.html`。常用维护命令：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/collect_models.py --dry-run
python3 scripts/collect_rankings.py --dry-run
python3 scripts/collect_maomu_rankings.py --dry-run
python3 scripts/build_unified_rankings.py
```

## 数据与隐私边界

- 资讯摘要和来源等级帮助筛选内容，不代表本站对内容作了独立事实背书；缺少一手证据时，不补猜发布日期或版本。
- 浏览器 `localStorage` 只保存模型评测候选的本地整理进度，不会同步到服务器。
- V4 没有个人提示词、收藏或偏好设置页；`site/data/prompts.json` 是旧版页面保留的数据。
- 页面不调用生成式模型推理 API。RSS、公开榜单和其他采集器只按项目配置读取公开来源。

## 关键目录

- `site/preview-v4.html`：V4 工作台页面；生产首页由 GitHub Actions 在发布时生成。
- `site/data/`：正式模型目录与共享数据；`site/data-v3/`、`site/data-v4/` 保存兼容或版本化快照。
- `scripts/`：数据采集、关联、校验和榜单构建脚本。
- `config/`：官方模型来源、RSS 与 GitHub 资源配置。
- `docs/`：数据契约、方法说明和审核记录；`archive/` 保存退役功能和历史资料。

## License

[MIT](LICENSE)
