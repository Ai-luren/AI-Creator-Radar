# 模型信息互通约定

## 权威记录

- `site/data/models.json` 是模型家族与具体版本的唯一权威目录；采集器和页面都直接使用它，不维护版本化副本。
- 家族 ID 全局唯一。版本 ID 只在所属家族内唯一，跨模块引用必须同时写 `modelFamilyId` 与 `modelVersionId`。
- 发布日期、许可、权重开放和可用状态属于具体版本。一个版本的结论不能自动套用到同家族其他版本。
- 榜单原始行与原始评测口径保持不变。目录版本里的 `leaderboardAliases` 是经核对的对照关系，不能从榜单分数推导发布日期或许可。

## V3.6 展示分类映射

底层 `category` 仍保留 video、image、llm、music、tts、audio 等原始值。前端主分类按 video、image、llm、audio 排列；audio 主入口汇总 music、tts、audio，子类为 music（音乐生成）、speech（语音）、audio-other（综合音频）。tts 映射至语音；audio 中明确的 ASR/TTS/声音克隆及 Scribe 家族归语音，其他音频归综合音频。该映射仅为展示筛选，不写回数据，不改变模型权威事实。

旧模型库和上新链接 category=tts 转至 speech；category=audio 汇总全部音频。正式发布计数按事件而非型号行计，verifiedStages 与 pending 不计入正式发布，服务开放单独在官方公告展示。无确切子类依据的历史记录仍可在全部音频中查阅。榜单以任务区分，编程不是通用语言能力综合榜，TTS 不代表 ASR 或实时音频。

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
- 底层支持视频、图像、语言、音乐、TTS、音频六类；前端按 V3.6 映射汇总为四大类；智能体工具版本更新仍不混入模型上新。
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


## 图像谱系复核第五批（2026-11-26）

- 新补 GPT Image 1 Mini、1.5、2、2.5 Sunburst、2.5 Flare，Nano Banana 初代、Nano Banana 2 Lite，以及 HunyuanImage 3.0 Instruct 共 8 份发布证据。
- GPT Image 1 保留 2025-04-23 API 上线阶段；官方 API 文档确认 2026-10-23 停用。ChatGPT Image Latest 是滚动 API 名称，不作为固定模型发布事件。
- 补充 Seedream 2.0：官方技术页 2025-03-11 公布，回顾 2024 年 12 月初已接入豆包和即梦；保留月份精度，不据技术页日期猜测首发日。
- Nano Banana 2.1 的 2026-10-06 是官方模型卡更新时间，暂不认定为首发日。Midjourney V7 的 2025-04-03 初次发布与 2025-06-17 默认版本切换分别记录。
- Qwen Image 2.0/2.0 Pro、2.1 Pro/Turbo 与 3.0 Pro 保存明确的国际 API 部署阶段；3.0 Pro 的 2026-07-20 国际部署与 2026-08-06 全球部署分别保存，不能等同基础模型首发。
- Seedream 4.5 首发日、Kling Image O1/3.0 Omni 首发日、Qwen Image Edit 商业 API 名称与公开权重版本映射仍待核验；未强行补证。此前 Qwen Image Edit 的公告时区/日期差异亦需复核。
- 目录现为 324 个版本，125 份结构化发布证据，51 条历史阶段证据。未重新核实全部旧记录。

来源：[OpenAI 更新日志](https://developers.openai.com/api/docs/changelog)、[Google Nano Banana](https://blog.google/products-and-platforms/products/gemini/updated-image-editing-model/)、[Google Nano Banana 2 Lite](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-omni-flash-nano-banana-2-lite/)、[腾讯混元仓库](https://github.com/Tencent-Hunyuan/HunyuanImage-3.0)、[Midjourney 版本文档](https://docs.midjourney.com/hc/en-us/articles/32199405667853-Version)、[Seedream 2.0 技术页](https://seed.bytedance.com/zh/seedream2_0)、[阿里云模型日志](https://www.alibabacloud.com/help/en/model-studio/newly-released-models)。


## 音乐与语音谱系复核第六批（2026-11-26）

- 新补 19 个历史型号（Mureka 13 个、Suno 2 个、Eleven TTS 2 个、Lyria 2 个）、11 份正式发布证据及 21 条历史阶段证据。当前目录 343 版本、136 份正式证据、72 条历史阶段记录。
- [Mureka 官方发展史](https://www.mureka.ai/blog_zh-CN/what-is-mureka.html) 记载 1.0–7.6 的历史进展；内部研发、内测及已有可用记录不能直接当作公开首发。V6/O1（2025-03-26）、V7（2025-07-23）、V7.5（2025-08-15）依据昆仑官网确认；V7.6/O2 的 API 上线日为 2025-12-09。V8、V9、V9.5/O3 分别保留 2026-01、03、07 月份精度；V9.5 的 8 月 28 日增强版更新及 Remix V9.5 的 11 月 12 日 API 开放是不同事件，不将 11 月 16 日回顾文章当作首发日。
- Suno V2 仅确认 2024-05-24 已可选择；V4.5-all 及 V6 Wild/Mini 有官方发布日期。Suno V1、V4.5+ 的准确首发仍待查。
- Eleven Turbo v2.5、Flash v2/v2.5、v3 Conversational 补发布证据；Eleven v3 保留 Alpha、API（2025-08-20）、全面开放（2026-02-02）三个阶段。
- Lyria 初代公布于 2023-11-16；Lyria 2 在 Vertex AI 全面开放于 2025-05-20；RealTime 于 2025-04-24 公布介绍，5 月 20 日开放 API。
- 增加 `development-milestone`（研发阶段）、`documented-availability`（已有可用记录）、`model-update`（模型更新），保持历史证据与发布视图分离；历史日期精度由 datePrecision 表示，不以 stage 猜测。

来源：[昆仑官网](https://www1.kunlun.com/news/3.html)、[Mureka API 日志](https://platform.mureka.ai/docs/en/changelog.html)、[昆仑半年报公告转载](https://epaper.cs.com.cn/zgzqb/html/2026-08/20/nw.D110000zgzqb_20260820_1-B081.htm)、[Suno 更新日志](https://suno.com/release-notes)、[ElevenLabs 官方博客](https://elevenlabs.io/blog)、[Google DeepMind 初代 Lyria](https://deepmind.google/blog/transforming-the-future-of-music-creation/)。
未完成全部音频厂商及旧有记录的再次核验；Mureka TTS V1、Lyria 后续变体、MiniMax Speech、Gemini TTS 等仍需单独核验范围与数据结构。


## 大语言模型谱系复核第七批（2026-11-26）

- 本批新增 60 个型号，补 71 份结构化发布证据（17 份本轮直接核对官方来源，54 份迁移既有人工审核历史记录，后者保留原 verificationDate 与 auditId，并非重新联网核验），新增 3 条历史阶段记录。目录 403 版本、207 份发布证据、75 条历史阶段记录。
- Claude 补初代至 5.x 历史型号，包括 Fable 5、Mythos 5；Mythos 访问受限，不能当作公众可用。Claude 3.5 Sonnet 日期及 Fable/Mythos 5.1 精确日期仍待核验。
- GPT-6.1 原 ID 保留，名称明确为 Sol（原有榜单别名均为 Sol）；补 GPT-6 Astra/Sol/Luna、GPT-4/4.1、GPT-5.4、Codex 历史分支。新型号不继承旧榜单别名。
- DeepSeek V4.1 Pro 仅有预告，纠正已发布标记；9 月 14 日后继续提供的是 V4 Pro。V4.1 Flash 1017 属同代更新，不重复计算基础代际首发。
- Gemini 4 Argon 的 2026-09-30 有限访问与 10-13 扩大开放分开记录，避免混同；Gemini 3.1 Pro 等预览节点另待核验。
- Kimi K2.7 更正为 K2.7 Code；原 ID 与榜单关联保留。K3/K3.1 Pro 的权重开放日期应与模型上线区分；K1.5 以前的历史仍待查。
- GLM 5.2/5.3/5.3 Flash 按既有历史核验迁移；GLM 原榜单关联存在型号粒度混合，暂保留待专项核验。
- Qwen3.5/3.6/3.8 汇总项保留旧 ID 与历史榜单关联，不能套用某个子型号的首发日；新增有明确事件依据的 Plus/Max/Flash Next 等型号。后续需核对原榜单别名映射。
- 本批仅迁移有明确型号、日级日期和已确认审核状态的历史事件；不新增缺乏明确证据的型号，不将预览或快照误算成基础代际首发。全量事实审核及 CI 尚未完成。

官方来源：[OpenAI API 日志](https://developers.openai.com/api/docs/changelog)、[Anthropic 模型公告目录](https://www.anthropic.com/news/models)、[DeepSeek 更新日志](https://api-docs.deepseek.com/updates/)、[Google Argon 有限访问](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-4-argon/)、[Google Argon 扩大开放](https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-argon/)、[Kimi 研究目录](https://www.kimi.ai/blog/)、[Kimi Code 更新日志](https://www.kimi.com/code/docs/en/kimi-code/whats-new.html)。


## 模型身份与证据收口第八批（2026-11-26）

- 修复 PR 信源诊断工作流 YAML 拼接错误。修复后的 [CI 运行](https://github.com/Ai-luren/AI-Creator-Radar/actions/runs/45782748462) 通过 98 项 Python、19 项 JavaScript 测试及模型引用检查（403 个版本）；只读诊断 33/34 源可访问，Niji 返回 403，另有 7 个零匹配源。可访问不等于覆盖完整，未将诊断计为生产采集成功。
- 本批新增 MiniMax M2.1，并核验 17 份正式发布证据：MiniMax M1/M2/M2.1/M2.5/M2.7/M3/M3.1 Flash；Muse Spark、1.1/1.2/1.3、Wonder、Wonder Full、Glimmer；Gemini Omni 1.1 Flash、Veo 3.1 Lite、Seedream 4.5。M1 依据 6 月 19 日官方回顾的“两天前”记录 6 月 17 日，保留原报道日期。Seedream 4.5 依据 2025-12-03 官方 BytePlus 公告，不将模型快照编号当作首发日期。
- GLM-5.3 Flash 与 Qwen3.6 Plus、Qwen3.8 Max/Flash Next 的 27 条原榜别名从错误/粗粒度版本移至明确版本（重复关联去重）；Nex-N2-Pro、Quasar 两种第三方衍生型号的榜单证据移到所属家族 `unresolvedLeaderboardAliases`，原字段保留，不参与精确型号映射。原始榜单数据不删改；派生排名下一次重建后生效。
- `recordKind` 与 `identityReview` 标记 10 条非独立首发身份：代际汇总、滚动 API 名称、评测配置、未标版本别名、服务档位、榜单快照。审核脚本独立统计，禁止为这些条目填造正式首发日期；仍计入原始目录条目及未附正式发布证据总数。该分类是现有证据下的保守处理，不意味着永久排除新证据。
- 本批未删除模型 ID、原始排名或历史记录。所有改动待最新 CI 与生产验证；其余未核实型号、Niji 403、零匹配源及其他厂商的混合榜单映射仍需继续处理。

来源：[MiniMax 官方发布目录](https://www.minimax.io/blog)、[Meta AI 研究目录](https://ai.meta.com/research/)、[Muse Wonder](https://research.meta.ai/blog/muse-wonder)、[Veo 3.1 Lite](https://blog.google/innovation-and-ai/technology/ai/veo-3-1-lite/)、[Gemini Omni 1.1 Flash](https://blog.google/innovation-and-ai/technology/developers-tools/build-with-gemini-omni-1-1-flash/)、[Seedream 4.5](https://www.byteplus.com/en/blog/seedream4-5?type=services)。

## 发布事件展示层（第七轮）

- 版本记录仍为唯一事实数据；前端从 30 天清单派生事件，不重写型号、日期、许可及原始证据。明确的家族、日期和批次成员映射优先；仅同家族、同日期、同一明确官方公告才允许自动归并，不按日期或滚动模型卡猜测。
- 近期上新默认已核实、创作优先；类别顺序视频、图像、音乐、TTS、实时音频、语言。语言按个人关注优先级（OpenAI/Anthropic/Google；其他重点厂商；其他）分组，不是能力排名。纯时间倒序可切换。统计分离事件数和型号数，所有具体证据可展开。
- 音频零记录明确表示证据清单缺口而非没有新模型。本轮不凭聚合报道补写发布日期；音频专项证据补齐另行验证。

## 资讯事件派生视图（第七轮第二批）

首页与行业简报共享综合资讯事件：明确原文 URL、条目身份、精确规范标题及小范围人工核对的等价来源为去重依据；不使用邻近链接或相似词强行合并。不同查询参数、发布说明锚点保留；仅移除已知追踪参数。原始报道、来源、摘要、刊期和发布时间均保留。综合列表日期是资讯来源记录日期，不是正式模型发布日期。首页与已核实发布事件存在精确相同证据链接时不重复展示；原始来源页不删条目。没有使用付费模型 API。

## 音频专项证据与上线阶段（2026-11-26）

- ElevenLabs SFX v3：2026-10-29 官方发布博客（https://elevenlabs.io/blog/sound-effects-v3），11-02 是开发者 API 介绍及全面开放，不重复计算。
- Scribe v3 / v3 Live：2026-11-09 官方更新日志（https://elevenlabs.io/docs/changelog/2026/11/9），11-10 中英官方博客（https://elevenlabs.io/blog/scribe-v3）介绍同一批次。记录最早明确的服务发布证据，两型号保留独立 ID；按 ASR 分类，不混入 TTS。
- Qwen-Audio-3.1-Live 的 11-23 上线已存历史节点（https://docs.qwencloud.com/changelog/models 与 https://www.alibabacloud.com/help/en/model-studio/qwen-audio-3-1-live）；Mureka Remix V9.5 的 11-12 API 全量上线早于 11-16 博客（https://platform.mureka.ai/docs/en/changelog.html 与 https://www.mureka.ai/blog_zh-CN/mureka-remix-v9-5-is-here.html）。仅将两条明确核实的历史阶段派生为 verifiedStages；不写入 releaseDate、releaseEvidence 或正式发布次数，不自动推广普通 API 更新。
- Qwen TTS 3.1 Plus 10-21、Flash 10-12、Next 10-22 均早于 30 天窗口起点 10-28，不能为了填满栏目挪到 11 月；Suno v6 的历史日期仍需按官方原始记录审核。

- Scribe v3 两型号使用显式同批次规则；正式发布与已核实服务上线的计数分开。新增固定历史窗口和派生清单一致性测试。

## 音频最终补核（2026-11-26）

- OpenAI GPT-Live 独立家族：1 / 1 mini 的 2026-07-08 官方 System Card；1.1 的 10-15 产品推出，11-20 开发者公告确认 API 可用（公告日期，不推测更早具体开放时间）；Quip 型号由官方 System Card 确认但独立首发日不推断。API 阶段独立于首发统计。
- ElevenLabs Scribe v3 Live Medical：11-17 官方博客首发，11-23 更新日志确认工作区扩展；后者不算第二次模型发布。新增开发更新日志与 OpenAI 官方开发者公告监控；可访问但零匹配的信源继续明确记录，不宣称全网完备。
- Suno v6 无日期的重复候选仅按精确原标题、固定来源及既有 9-09 正式证据排除，不把发现时间算作新发布。

- GPT-Live 11-20 API 公告补入 OpenAI 发展史，作为 canonical historicalMilestone 的明确审核节点；Scribe Medical 同步历史节点。CI 历史关系校验不降级。

## 自动模型关联精度

资讯、官方更新、教程、社媒等自动引用必须有包含模型身份的完整名称；通用版本号（V4.1、2.5 Flash）及素材编号（Video 1、Audio 2）不能单独作为型号身份。已有具名官方证据可用于精确匹配；无法确定具体版本时宁缺毋滥，不跨厂商猜测。已审核厂商发展史通过明确证据 ID 绑定的短标签不受此限制。引用 ID 存在并不等于事实正确；新增自动关联精度回归检查，不改变原始内容和证据字段。

## P1 自动双源发布核验（第一阶段）

采集器仅把 RSS/Atom 明确 published/pubDate 或 JSON-LD datePublished 作为结构化发布日期证据；updated、列表邻近日期、模型卡及 API 日志仍只用于候选发现。模型事务在生成上新视图之前运行 collect_verify_model_releases.py：当前成功抓取、同一规范家族、明确正式发布标题、两个不同官方站点及不同来源 ID/文章 URL、日级日期一致且无已知冲突才可自动写入 releaseEvidence。自动记录 verificationMethod=automatic-dual-official，保存双方标题、链接、日期来源和采集时间；verifiedAt 是机器核验日期而不是人工审查日期。既有人工证据、历史阶段、身份变体和冲突不覆盖；新型号只允许显式白名单中的简洁数字版本，其他型号保留候选。两条证据不代表独立第三方核验；不推断许可、权重、可用范围。未满足条件的候选保留原发现流，核验状态记录于 site/data/model-release-verification-status.json。厂商发展史仅提升与自动证据来源 ID、日期及家族一致的待复核节点，合并同一事件的两条机器候选；保留双方证据，明确标记“自动双源核验 · 非人工复核”，不覆盖人工审核历史。

## 调度与运行状态契约

`collection-health.json` 记录各采集组最后尝试、最后成功与连续失败次数；`scheduler-health.json` 的 schema 保持 scheduler-health/v1，包含生成时间、下一次可执行到期时间及触发记录。组级 due 表示实际快照到期，eligible 表示满足退避条件可执行，retryAfter 为暂缓边界（无暂缓时 null）。新字段兼容旧快照，不改变模型、版本、发布证据或已有日期。system-audit.json 的 dueScopes 为真实过期组，eligibleScopes 为可立即重试组。不得把调度成功等同于模型事实已核验；详见 [运行手册](automation-runbook.md)。

## P1 事件身份与证据账本（影子层）

`event-reconciliation.json` 是后台对账快照，不是第二份权威模型库。已有正式证据按 family/version + catalog-release 记录，历史阶段使用 historical-*，已验证文章日期使用 article-publication；三者不能互相替代。证据 ID 为完整记录的确定性 SHA-256，保存原始核验时间、日期精度、来源、原记录 ID；重复读取不追加同一事实。旧证据不因访问失败删除，当前引用和历史证据分开；同型号旧新正式日期差异明确列出，不自动选择。已有审核记录迁移不代表本轮重新核验。原始外部线索按唯一精确型号、同报道日关联，仅作候选，不混同阶段，原文链接归属不变，禁止同源重复计证。账本不存第三方全文，不改正式视图。

对账任务 ID 按型号/报道日或未分类线索、历史正式证据缺口生成，保留首次发现和实际探测状态；超出输入窗口不等于修复。关联的原文仅提升已有真实 URL 的探测优先级；缺少任何公开原文的线索仍标记 needs-source，当前未部署额外搜索服务。历史证据更正、撤回和自动晋级规则后续单独验收。

## P1 结构化产品状态差分

`product-state.json` 保存公开目录基线、产品 ID、来源实际检查时间、退避状态和近期变化；不写 `models.json`。初始全量基线不当作今日上新，近期第三方明确日级日期仅为待核验线索。新增、元数据变化、连续两次缺失、重新出现分别记录；大面积消失或接口失败保留最后有效快照。目录缺失不代表停服，第三方日期、创建时间和首次观测不代表正式发布日期。Models.dev 仅选取关注厂商，保留 MIT 来源标注；OpenRouter 只取公开模型与图像目录最小字段，不调用推理 API。不同目录可能共同依赖同一上游，不计独立首发证据。未知身份的新目录变化进入对账任务，不自动创造版本；当前精确名称匹配覆盖有限，待扩展规范身份映射。

## P1 独立新闻索引补证试点

`source-search.json` 保存由当前外部线索、未解决对账任务及未知产品目录身份生成的安全查询和实际索引候选，绝不从固定召回真值或规范库发布 URL 生成生产输入。GDELT DOC 2.0 仅用于发现链接；查询结果标题须匹配明确型号，官方原文候选再次通过现有主机/路径允许列表，索引看到文章的时间不等于文章发布日期或模型首发日。第三方链接仅为报道线索，不视为官方发布证明或独立证据。原始线索不复制来源归属；索引候选独立标记、交给既有解析器核验。未分类模糊标题不强行查询，旧任务保留；无法找到证据不等于已解决。历史超出索引覆盖窗口的缺口仍需另外的档案与结构化证据策略。

索引服务受限时，按精确型号身份复用已存证据账本、实际原文指针及产品目录观测，形成独立的 localContext。只显示已知上下文，不伪造新证据、刷新历史核验时间、将目录存在当成发布日期、将不同阶段等同，或关闭原未解任务。此路径不注入正式召回测量。对账任务关联查询状态和上下文类别。

## P1 事件事实分级（影子判定层）

`event-claims.json` 只消费实际官方来源原始日期观察及恢复原文核验，不使用规范库中已有发布日期制造召回。唯一规范型号匹配、来源配置/原始观测一致性、日期语义先过门禁。明确整句标题可识别公告、正式发布声明、API/全面/预览/服务开放声明；产品集成要求标题和摘要中有同型号同产品的明确肯定表述。未明确的仅为文章日期。所有声明保留原始文章时间、发布者日历日及真实核验时间，`eventDate` 保持 null，不等同首发。相同事实由官方采集与文章恢复同时发现时合并渠道血缘，不作为独立来源计数。单一原文日期改变隔离为待审，不自动挑选。已观察的证据在暂时失联时保留，不假称最新成功。未附正式证据的明确发布声明进入 review candidates，但不直接写权威模型库或自动晋级。

## P1 独立仓库观察覆盖审计

`independent-coverage.json` 从尚未进入原有跨平台采集的 MiniMaxAI、ByteDance-Seed、Wan-AI 公共 Hugging Face 组织目录取得样本（不由现有规范库选样）。按45天创建时间窗口、厂商约束、精确型号名称对账；初次状态和匹配结果永久保留，后续当前匹配单独计数。仓库可能是变体、检查点或非产品，不代表正式发布、权重可用或真实漏报；闭源模型不在此样本覆盖范围。只有明确生成类 pipeline 的样本进入观察覆盖分母，未知类型单列；分页上限仍覆盖整个窗口与否显式记录。缺失身份的审计样本在首次评分冻结后进入补证任务，不直接修改正式模型库，不纳入原固定发布召回指标。

## P1 跨运行正式证据累积

原有 automatic-dual-official 核验门槛不变：仅明确正式发布、结构化发布日期、两条不同官方发布记录、日期一致且身份与阶段无冲突。`model-release-verification-status.json` 增加 proofLedger：仅实际原始来源观测一致、非延期的合格记录持久保存，内容哈希、原始核验时间及信源配置哈希均保留。至少有一条本轮合格原始观测才能使用符合原窗口的历史证明；失联不导致历史证明消失。信源停用/配置变化不再使用旧证明；后续同一原文日期、标题或身份冲突自动隔离，禁止自动选择。历史账本不作为固定召回输入，不放松首发或阶段判定，不覆盖既有人工证据；当前仍只处理原30天窗口，旧历史证据需独立核验。

独立仓库样本增加模型卡角色核验：仅来自原样本仓库的公开 README、精确一级标题和肯定描述；提示词扩展组件还须同组织父模型链接与唯一规范身份一致。明确多研究构件或独立模型检查点仅分类为候选，未自动写首发。原始初次和当前仓库匹配统计不变，辅助组件分类另计；分类保存实际内容哈希、原始来源和首次观察，后续失联不刷新旧验证日期。父模型映射失效则重新待审。

智谱国内研究索引采用限定数字文章路径、精确型号标题、独立原文日期探测；不要求英文发布关键词，不借用邻接索引日期，不从型号猜测 URL。文章日期解析支持精确中文及斜线日期，冲突不择日。该规则仍需要实际 runner 观察，客户端渲染或域名访问失败不计为召回。
