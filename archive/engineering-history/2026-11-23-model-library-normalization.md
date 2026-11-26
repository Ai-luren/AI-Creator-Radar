# 模型库统一规范

> 状态：原模型库规范已完成。其原始任务范围和“禁止改 CI”约束只适用于当时那一轮；后续批准的跨模块模型引用与日更生成规则以 [`docs/model-data-contract.md`](../../model-data-contract.md) 和 [`docs/model-release-digest-guide.md`](../../model-release-digest-guide.md) 为准。本文件保留作实施历史，不作为后续日更的操作清单。

## 目标

把模型库改为一致的“厂商 → 模型家族 → 版本/变体”结构，补齐已核实的重点型号，并允许按选定的具体评测子榜排序。

## 规则

1. 厂商是归属，不代替模型家族。MiniMax Hailuo 与 MiniMax H3 是不同家族；Kling 视频与 Kling Image 分开；同一家族的具体版本归在同一张家族卡中。
2. `models.json` 每条记录代表一个模型家族，字段为稳定 `id`、`name`、`vendor`、`category`、`versions[]`、`aliases[]`、`watched` 及家族级入口。`versions[]` 的每项保留稳定 `id`、正式型号名、变体/任务、状态、地区/权重、发布日期、型号专属来源、旧 ID 与榜单名称别名。
3. 旧记录 ID 必须迁入某个 `versions[].legacyIds`，不可因家族合并丢失采集器、更新历史或模型评测的引用。
4. 原始排名必须绑定具体 `boardId`，不改写来源名次。后续获批的用户榜由独立生成器写入 `site/data-v4/unified-rankings.json`：同一子任务跨来源须通过共同型号留出校准；多任务类别还需固定共同型号面板；来源、锚点、区间或任务覆盖不足的结果只能标为暂定。模型库关联必须使用经核实的精确版本 ID，不用家族名推断具体变体。
5. 搜索别名不代表发布事实；缺少来源支撑的版本保留为待核验或不录入发布日期。许可、权重开放和预览状态按版本记录，不从一个版本推广到整个家族。
6. 维持现有地区、许可筛选与 V4 本地预览入口；禁止推送、部署或改 CI。

## 本轮范围

- 图片、视频、音乐、TTS、LLM、Agent 六类家族卡。
- 三轮证据核验：模块专家审计、交叉复核具体型号/榜单匹配、整合后检查数据与实际浏览器显示。
- 同步 `site/data-v3/models.json` 与采集器写入的 `site/data/models.json`，使定时采集继续保留结构化版本。
- 更新 V4 模型库展示和本地验证。

## 非目标

- 当时这一轮的模型库数据同步不包含不同评测榜单合算；后续榜单规则见 [`docs/leaderboard-methodology-proposal.md`](../../leaderboard-methodology-proposal.md)。
- 将同一公司的不同生成任务强行并为同一型号家族。
- 修改 GitHub Actions、推送或部署。
