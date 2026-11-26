# 模型信息互通约定

## 权威记录

- `site/data/models.json` 是模型家族与具体版本的唯一权威目录；采集器和页面都直接使用它，不维护版本化副本。
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

`site/data/model-releases-30d.json` 是生成视图，不是第二份人工主数据。运行 `python3 scripts/build_model_release_digest.py`，只从有发布日期和完整官方证据的目录版本生成。多型号同批发布时，逐型号保留版本 ID 和来源，不合成一个虚构的模型版本。

## 跨模块关联

- 结构化引用写 `modelFamilyId` 和 `modelVersionId`；无法确认具体版本时只关联家族，不能猜版本。
- `scripts/link_model_records.py` 为行业简报、厂商节点、社媒动态、创作工具、评测候选等记录添加 `modelMentions`（版本级精确名称）或 `modelFamilyMentions`（家族级名称）。当前只链接视频、图像、语言和音乐模型，跳过智能体工具；这些字段表示文本提及关系，不改变记录本身的来源和事实结论。
- 未能唯一关联的模型资料保留 `modelLinkStatus: "unresolved"`，不要以模糊字符串相似度强行合并。
- 前端从这些 ID 提供目录详情入口。缺少引用表示没有已核实关联，不等于该模型没有资料、榜单或账号。

## 当前能力榜展示

- `site/data/unified-rankings.json` 是由 `python3 scripts/build_unified_rankings.py` 生成的派生视图；当前页面读取各类别的 `primaryLeaderboard`，视频另读取 `primaryLeaderboards` 下的文生/图生任务榜，不读取审计用的跨榜综合行。
- 当前来源为：图片 Arena 文生图、视频 AA 有声文生与有声图生、音乐 AA 含人声榜、语音合成 AA 全量 Provider Voice、编程 Arena Code。分数和名次沿用各自原榜，不跨评测机构或任务池相加。
- 每类最多显示 10 个合资格候选，保留来源的模型名、厂商、rank、rankRange、原始分数、区间和样本量。视频两个任务榜分别从各自 AA 原榜前 20 名中筛选基础模型及家族代表版本，再最多显示 10 个；来源名次不重新编号。
- `site/data/leaderboard-reference-snapshots.json` 保存当前参考榜快照。页面区分数据快照时间与来源核对时间；静态偏好榜不代表实时抓取、市场使用量或创作者采用率。
- 音乐器乐榜和含人声榜是不同评测池；当前主表只显示含人声榜。TTS 使用全量 Provider Voice，包含 ElevenLabs；编程榜的 Arena 偏好分不等同隐藏代码测试通过率。
- 展示和排除规则见 [`../site/ranking-rules.html`](../site/ranking-rules.html)，方法审计与不确定性边界见 [`leaderboard-methodology-audit-2026-11-25.md`](leaderboard-methodology-audit-2026-11-25.md)。

## 历史跨榜试算规则（仅审计）

- `site/data/unified-rankings.json` 是派生视图，由 `python3 scripts/build_unified_rankings.py` 读取现有榜单快照生成；不得把它反写到原始来源数据。
- 综合行优先绑定明确的 `modelFamilyId` 与 `modelVersionId`。无法唯一映射的来源名仍显示为独立榜单行，不按模糊名称合并。
- 新榜只在同一任务的共同型号校准通过后合并来源；多任务类别还须有至少 20 个精确共同型号作为冻结锚点面板，各任务相对同一面板标准化后再等权合成。未通过来源或锚点门槛时只作参考/暂定。
- 跨来源校准锚点按精确模型版本 ID，或规范厂商加完全一致的型号名匹配；未知厂商、身份冲突和重复身份不成为锚点。冻结来源基线记录评测版本与方法元数据指纹；上游版本或口径变化时来源暂停计分，待人工复核并升方法版本。
- 该版本锁依赖上游快照的版本标签和方法描述；若上游未更新元数据而静默更改方法，无法自动发现。`Arena latest` 等滚动标签需要人工核对。
- 正式名次要求至少两个独立来源、至少三分之二任务覆盖、至少一个任务有交叉来源校准和可计算的综合区间。综合区间按完全正相关方式传播来源 CI 与校准残差，但当前不含锚点面板估计误差，页面必须披露。
- 视频文生与图生使用独立有声 Elo 池，页面分开显示，不把两池分数合并；无声任务不纳入当前视频榜。音频模式未核实的榜单仅作参考，不参与分数。
- `config/unified-ranking-baseline.json` 保存各来源榜首轮冻结基线和类别锚点面板。已存在的基线不随普通刷新改写；评测刻度或方法改变时须升方法版本并审核新旧连接。
- 来源校准系数、锚点逐型号分数、输入快照哈希和评测口径指纹均被冻结留档；普通刷新只检查固定映射的漂移，不静默重拟。经官方来源核实的厂商别名记录在 `config/unified-ranking-vendor-aliases.json`；身份冲突时不合并且不计分。

## 更新与检查

模型采集之后按顺序运行：

```sh
python3 scripts/build_model_release_digest.py
python3 scripts/link_model_records.py
python3 scripts/validate_model_links.py
```

验证器检查家族/版本引用、发布证据字段以及 30 天上新条目的归属。GitHub 日更工作流执行同一组步骤，并同步生成的发布视图。
