# 模型信息互通约定

## 权威记录

- `site/data/models.json` 是模型家族与具体版本的权威目录；`site/data-v3/models.json` 是兼容副本，采集器写入后必须保持一致。
- 家族 ID 全局唯一。版本 ID 只在所属家族内唯一，跨模块引用必须同时写 `modelFamilyId` 与 `modelVersionId`。
- 发布日期、许可、权重开放和可用状态属于具体版本。一个版本的结论不能自动套用到同家族其他版本。
- 榜单原始行与原始评测口径保持不变。目录版本里的 `leaderboardAliases` 是经核对的对照关系，不能从榜单分数推导发布日期或许可。

## 官方发布证据

具体版本的 `releaseEvidence` 包含：

- `eventId`：稳定的发布事件标识；
- `publishedAt`：官方公告或模型卡明确给出的发布日期；
- `sourceUrl`、`sourceName`、`evidenceType`：可复核的一手来源；
- `verifiedAt`：最近人工核对日期；
- `summary`、`access`、`category`：对应版本的公开说明。

`site/data-v4/model-releases-30d.json` 是生成视图，不是第二份人工主数据。运行 `python3 scripts/build_model_release_digest.py`，只从有发布日期和完整官方证据的目录版本生成。多型号同批发布时，逐型号保留版本 ID 和来源，不合成一个虚构的模型版本。

## 跨模块关联

- 结构化引用写 `modelFamilyId` 和 `modelVersionId`；无法确认具体版本时只关联家族，不能猜版本。
- `scripts/link_model_records.py` 为行业简报、厂商节点、社媒动态、创作导航、评测候选等记录添加 `modelMentions`（版本级精确名称）或 `modelFamilyMentions`（家族级名称）。当前只链接视频、图像、语言和音乐模型，跳过智能体工具；这些字段表示文本提及关系，不改变记录本身的来源和事实结论。
- 未能唯一关联的模型资料保留 `modelLinkStatus: "unresolved"`，不要以模糊字符串相似度强行合并。
- 前端从这些 ID 提供目录详情入口。缺少引用表示没有已核实关联，不等于该模型没有资料、榜单或账号。

## 更新与检查

模型采集之后按顺序运行：

```sh
python3 scripts/build_model_release_digest.py
python3 scripts/link_model_records.py
python3 scripts/validate_model_links.py
```

验证器检查家族/版本引用、发布证据字段以及 30 天上新条目的归属。GitHub 日更工作流执行同一组步骤，并同步生成的发布视图。
