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


## 官方发现流（时效性治理 P0-1）

- 近期上新生成视图增加独立的 `pending` 数组，来自已配置官方信源的近 30 天发现记录，仅允许当前模型目录中已有的规范家族 ID（不沿用已退役衍生端点别名）；预告和模型卡更新不得计入正式发布数量。
- 待复核记录保留来源日期和发现时间，未知发布日期不补猜，不写入正式 `releaseEvidence`。已确认记录仍由模型库的结构化证据生成。正式视图与发现流分别展示。
- 自动采集不覆盖已有发布日期和人工发布证据，不将预告或模型卡更新时间当作新版本首发日期。
- 支持视频、图像、语言、音乐、TTS、实时音频六类；智能体工具版本更新仍不混入模型上新。
- `--check` 比较实质内容而非生成时钟，以便稳定检测派生数据是否陈旧。


## 已审核历史证据迁移与完整性检查

- `config/chronicle-release-links.json` 是逐型号明确指定的历史审核迁移清单；不通过摘要或模糊文本匹配推导首发日期。保留既有 `verificationDate`，不伪造本轮重新核验时间。
- `releaseEvidence.evidenceType = audited-chronicle-release` 记录来自既有已确认历史节点的迁移，包含原 auditId、topic ID 与来源。此操作不等于重新打开并核实原文。
- 厂商历史的版本引用限制为相应厂商、标题明确出现的完整名称；摘要中的旧版本对比、泛化版本号和衍生型号不能用作发布日期证据。
- `python3 scripts/audit_model_completeness.py --output /tmp/model-completeness.json` 检查迁移关联并输出缺口，不自动写入型号、日期或许可。缺口也可能是目录中的榜单变体或不在历史范围内的产品，不直接等于遗漏发布。


## 谱系补齐与历史阶段

- 新增历史型号不继承当前型号的许可、榜单别名或当前可用状态；未知信息保留未知。PixVerse C1 作为独立家族，不并入 V6；Hailuo 02 基础模型与具体服务档分开。
- `historicalMilestones[]` 保存有明确证据但不能认作精确正式首发日的事件（月份精度、首次公布、Alpha/预览、早期访问、全面开放、API 可用、官方介绍）。`datePrecision` 保留原始精度；不写入 `releaseDate` 或近期正式上新。详情页单独显示阶段及证据链接。
- 本轮新查官方来源补充 MiniMax Music-01、Eleven Music v2 的 API 可用、Suno v3.5 的早期访问三个节点；旧节点证据迁移保留原审核日期，部分重新查看的来源另标 `sourceRecheckedAt`，不假称全部重新核验。


## 创作者谱系第二批清洗

- 新增 Midjourney Video、Imagen、SeedEdit、Vidu S2 独立家族；补 Midjourney V4/V5/V5.1/V6.1/V8.1、Seedream 5.0 Flash、Qwen Audio Live/TTS Next 等明确型号。新增家族/版本不继承当前型号的榜单、许可或可用状态。
- V8.0/V8.1 Alpha、Imagen 3 首次公布、V4/V5 月份精度、Qwen/Wan 的 API 可用及公测等仍只写历史阶段，不伪造正式发布日期。既有审核记录迁移沿用原核验时间，未重新打开全部官方原文。
- 按明确 auditId 关联已审核事件的版本，保留一条公告对应多个明确型号的情况。当前源配置同步纳入四个新增家族；新增源匹配规则仍需实测。
- Vidu Q2 Image Generation 属独立图像能力但当前档案不足以确定规范型号 ID；保留历史节点，不强行创造型号。Seedance 2.5 日期仍存在冲突，保留待核验；不借用其他代际发布日期。


## 自动发现历史的保护边界

`collect_chronicle_updates.py` 只接受审核配置映射内的已存在厂商、明确模型发布/预告类型与非未来 HTTPS 来源记录；新增节点为待复核，`dateKind=source-date` 不表示确认首发日期。审核 ID、审核日期或非原始待复核状态的记录不被采集覆盖；不同明确模型家族共享官方页仍可独立保留。既有历史节点不删除，待复核数据不等于发布证据。


## 发布证据复核第三批（2026-11-26）

本批在已有 320 个版本、98 个发布证据的基础上，直接复核厂商官方公告、官方仓库及模型卡，补齐 15 个版本证据（113/320）。保留原有历史节点、ID、榜单别名，不将新补证的历史发布视为今日新模型。新增证据的 `verifiedAt` 是本批实际查阅日期；对回溯报道明确列出的模型发布日，`publishedAt` 表示模型事件日期，`sourcePublicationDate` 另存报道页面日期。新补证记录的当前可用性仍需独立验证。未修改已核实的旧证据。

仍缺发布证据的 207 个版本并非 207 个已知正式发布遗漏。审核脚本输出厂商维度、类别和互斥的处理队列：已有日期缺证、历史阶段证据、智能体产品范围、榜单身份待核验、第三方衍生型号、预览阶段、其余发布来源待查。分类依据是现有字段，仅用于安排审核，不是最终型号性质判断；不自动新增或删除版本。

```sh
python3 scripts/audit_model_completeness.py --output /tmp/model-completeness.json
```

### 保留冲突与阶段边界

| 型号 | 已见证据 | 当前决定 |
| --- | --- | --- |
| Seedance 2.5 | [官方首页](https://seed.bytedance.com/en/) 标注 2026-11-16；[正式发布文章](https://seed.bytedance.com/en/blog/one-take-creation-flexible-referencing-introducing-seedance-2-5) 标注 2026-07-31 | 日期冲突，暂不写入正式发布证据 |
| HunyuanVideo 1.5 | [专用仓库](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5) 与 [模型卡](https://huggingface.co/tencent/HunyuanVideo-1.5) 记载 2025-11-20 开放代码和权重；[主仓库](https://github.com/Tencent-Hunyuan/HunyuanVideo) 与 [官方许可证](https://huggingface.co/tencent/HunyuanVideo-1.5/blob/main/LICENSE) 标注 2025-11-21 | 区分发布阶段和时区可能性；不任选首发日 |
| Kling 3.0 / Omni | [2026-02-05 官方公告](https://ir.kuaishou.com/news-releases/news-release-details/kling-ai-launches-30-model-ushering-era-where-everyone-can-be/) 明确当时仅 Ultra 用户提前体验 | 不把提前体验日期冒充全面开放日 |
| Kling 2.6 Pro | [官方 2.6 公告](https://ir.kuaishou.com/news-releases/news-release-details/kling-ai-launches-video-26-model-simultaneous-audio-visual) 记载基础 2.6 于 2025-12-03 发布 | 尚需核实 Pro 端点或服务档位身份，不直接套用基础型号日期 |
| Kling 2.1 | [官方财报](https://ir.kuaishou.com/news-releases/news-release-details/kuaishou-technology-announces-second-quarter-and-interim-2025) 明确 2025-05 发布 | 仅有月份精度，不补猜日期 |

本批核验 15 个版本，不代表已重新核实 320 个版本。旧有榜单条目、服务档位、发布证据以及历史里程碑未全面重新联网审核。


## 视频谱系复核第四批（2026-11-26）

- 补齐 Hailuo 2.3 Fast（2025-10-28）、Wan 2.6 视频系列、Wan2.6-image 与 Wan2.6-T2I（2025-12-16）共 4 份正式发布证据。
- 新增 PixVerse V5、V5.5、Vidu Q2 Pro Fast 三个已证实的独立型号；不继承榜单别名及许可。
- 将 PixVerse V5/V5.5/V5.6 的 API 发布日、Vidu Q2 Pro/Turbo/Pro Fast 与 Q3 Pro/Turbo 的 API 开放日、Kling 3.0/3.0 Omni 提前体验日、初代 Kling 测试日记录为有明确阶段的历史事件。来源：[PixVerse 更新日志](https://docs.platform.pixverse.ai/changelog-2394996m0)、[Vidu 更新日志](https://platform.vidu.com/docs/api-reference/updates)、[Kling 3.0 公告](https://ir.kuaishou.com/news-releases/news-release-details/kling-ai-launches-30-model-ushering-era-where-everyone-can-be/)。
- Vidu Q2 的 2025-09-30 是厂商公告日；官方 API 记录 9 月 24 日已有 Pro/Turbo，[第三方 9 月 25 日已公布接入](https://www.prnewswire.com/news-releases/pollo-ai-has-launched-vidu-q2-and-kling-2-5-turbo-ai-video-models-empowering-creators-with-studio-level-cinematics-302566885.html)。保留公告阶段，不把公告日当作唯一首发日。
- Seedance 1.0 官方技术报告 2025-06-11 使用基础家族名，[BytePlus 月度目录](https://docs.byteplus.com/vi/docs/modelark/model-release-announcement-2025?redirect=1) 同时列出 Seedance 1.0 Pro 的版本标签与 API 上线记录；不能将技术报告日期或标签日期直接写成 Pro 首发日。Seedance 2.5 冲突继续保留。
- 本批最终目录 323 个版本，117 个结构化正式发布证据，39 条历史阶段证据；206 个版本仍无正式发布证据，其中含新补齐的历史 API 型号。尚未完成全厂商重新核验。
