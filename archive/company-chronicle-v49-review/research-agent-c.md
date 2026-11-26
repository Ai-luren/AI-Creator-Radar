# Agent C：对抗性事实审核报告（抽样，不代表全库复核）

审核对象：下载目录中的 v48 主表及其主信源、交叉链接。审核日期：2026-11-23。范围限于对抗性风险扫描，不修改主表。

## 覆盖与限制

- 主表共有 503 条、20 家厂商；此报告没有逐条检查 503 条正文，不能据此标记全库通过。
- 对 2026 年 9–11 月抽取 13 条主表记录（其中 Qwen 记录包含 Preview 与正式可用两个日期主张，共核对 14 个事实主张）；逐项查看标题/日期/事件性质与所列信源，并另行检索了可替换的官方原始页面。表中明确记录 12 个可由直接官方资料支持的主张、1 个仍需补证主张（GLM-5.4）；PixVerse V6 Max 的日期仅确认 API 能力更新，不确认其为模型首次发布。官方索引/目录是否能证明主张，按具体条目判断，未统一计为支持。
- 另对全库主信源复用、缺少第二链接和证据“独立性”做机器扫描。URL 数量不等于来源独立数；同一厂商新闻稿的翻译版、索引页、模型卡和 API changelog均属厂商官方材料，但需按各自明确写出的内容评价，不能称为独立第三方互证。

## 有实质审核价值的个案

| 节点 | 对抗性结论 | 证据与边界 |
|---|---|---|
| PixVerse V6 Max，2026-10-22 | **部分确认/事件措辞需收窄。** 所列主信源只证明 PixVerse API changelog 当天增加 `V6-max` 对 T2V/I2V 的支持，不能单独证明该独立模型家族于当天“首次发布/上线”。所列第二链接是第三方 serverless-provider 综述，不能有效支持首发日或模型身份。 | [官方 API changelog](https://docs.platform.pixverse.ai/changelog-2394996m0) 原文为 “Added V6-max support for Text-to-Video and Image-to-Video.” 建议节点改为“V6-max API 支持加入”，将日期标成 API 文档/服务能力日期；若保留模型首发口径，需补官方产品公告或首发可用证据。 |
| Muse Ember，2026-11-09 | **事实可确认，但 v48 所列证据组合薄弱。** `ai.meta.com/llama/` 是 Meta 模型/产品目录，所列两个次链接是第三方跟踪站，不能独立证明首发日。此轮找到了更合适的官方公告。 | [Meta Research 原始公告](https://research.meta.ai/blog/muse-ember) 明确标题、发布日期 November 9, 2026，并称模型当日推出；它可替换通用目录作为主信源。第三方链接最多是线索，不构成强交叉证明。 |
| Muse Spark Open，2026-10-15 | **型号/日期/开放权重事件可确认；v48 链接需替换。** 主表使用通用 Llama 页面及第三方目录/排行榜，不足以支持特定首发事件。 | [Meta Research 原始公告](https://research.meta.ai/blog/muse-spark-open) 明确 10 月 15 日发布权重、可从 Hugging Face 获取及 816B 总参数/42B 激活参数。此公告同时支持型号、日期、开放权重；第三方榜单不是必要证据。 |
| Qwen4-Max Preview，2026-11-11；Qwen4-Max，2026-11-16 | **阶段日期区分合理。** 这两天对应 Preview 与正式可用，不能合并成同一个“首发日期”。 | [Alibaba Cloud Token Plan product updates](https://www.alibabacloud.com/help/en/model-studio/token-plan-product-updates) 分别列出 11 月 11 日 preview 与 11 月 16 日 available；此页是单一厂商官方来源，若第二链接只是同一更新索引的语言翻译，不应计作独立证据。 |
| GPT-Live-1.1 / Quip，2026-10-15 | **日期与事件口径可确认，但注意 API 后续阶段。** v48 节点标题说在 ChatGPT Voice 推出，适用于 10 月 15 日；不要把 11 月 19 日 API changelog 的 API 更新反写为首发日期。 | [OpenAI ChatGPT release notes](https://help-lb.openai.com/en/articles/6825453-chatgpt-release-notes) 标明 10 月 15 日在 ChatGPT Voice rollout；[GPT-Live-1.1 system card](https://deploymentsafety.openai.com/gpt-live-1-1/alignment) 支持模型家族、Quip 关系与语音模型属性。两项是 OpenAI 自有材料，非独立外部来源。API changelog 记录的是不同事件阶段。 |
| Nano Banana 2.1，2026-10（主表日期精度） | **型号、图像生成/编辑属性及月份有官方支持；model card 发布日不应自动等同于首次公开公告日。** | [Google DeepMind model card](https://deepmind.google/models/model-cards/nano-banana-2-1/) 明确标注 2026-10-06、系列归属及图像输出；本轮未找到更早/同期独立产品公告，故只确认官方模型卡日期，不确认它就是首次公开发布日。 |
| Gemini 4 Hydrogen，2026-11-12 | **型号及卡片发布日期确认；模型卡及目录不能作为两个独立来源。** | [Gemini 4 Hydrogen model card](https://deepmind.google/models/model-cards/gemini-4-hydrogen/) 标明 11 月 12 日发布；[官方模型卡目录](https://deepmind.google/models/model-cards/) 将条目列作 updated 12 November。两页互相支持官方日期/型号，但为同一厂商资料，且目录“updated”不等于首次公告。 |
| Gemini 4 Neon，2026-11-18 | **型号和公告日有直接官方支持。** | [Google 原始公告](https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-neon/) 标题及正文说明 11 月 18 日推出。DeepMind model-card 目录只佐证卡片更新日，不代表独立发布来源。 |
| GPT-6.2 Astra / Sol，2026-11-17 | **型号、日期及 API/产品上线阶段确认。** | [OpenAI 原始公告](https://openai.com/index/introducing-gpt-6-2-astra-sol/) 和 [GPT-6.2 system card](https://deploymentsafety.openai.com/gpt-6-2-astra-sol) 均标明 11 月 17 日；二者为同厂资料，前者支持公告/可用性，后者支持安全分类/模型事实，不构成独立组织来源。 |
| Claude Fable 5.2 / Mythos 5.2，2026-11-09 | **型号、同底层模型关系与公告日期确认。** | [Anthropic 原始公告](https://www.anthropic.com/claude-fable-and-mythos-5-2) 明确日期并说明两个名称共享 underlying model；[官方 models index](https://www.anthropic.com/news/models) 可辅助定位但属于同厂目录，不是独立来源。应避免拆成两条基础模型代际。 |
| GPT-6 Cyber，2026-11-05 | **事件有官方原始材料支持，但主表用 API changelog 作唯一主证据不够精准。** | [OpenAI 原始公告](https://openai.com/index/introducing-gpt-6-cyber/) 与 [system card](https://deploymentsafety.openai.com/gpt-6-cyber) 均标注 11 月 5 日；API 文档只支持 API 模型可用/接入，不应取代首次公告证据。若摘要说“可用”，需说明受限于获批 Daybreak Red 客户，不应写成面向所有用户公开开放。 |
| Mureka Remix V9.5，2026-11-16 | **型号、日期可由官方文章确认，但它是 Remix 专项模型，不等同于 Mureka 全系生成模型 V9.5。** | [Mureka 原始文章](https://www.mureka.ai/blog_en/mureka-remix-v9-5-is-here.html) 标明 11 月 16 日，并明确 API 参数 `mureka-9.5` 以及对应 Remix endpoint。主表已有“Remix”限定是关键，摘要/类别应持续保留该限定。该条 v48 未提供第二链接。 |
| GLM-5.4（主表称 2026-11-23） | **此轮未能从所列链接之外取得足够的第二条独立/官方入口。** 官方博客链接与 AutoClaw 官方子域是否为不同发布主体，需要进一步核实；AutoClaw 型号目录若只是转载/分发目录，只能佐证型号存在，未必证明首发日或发布性质。 | 暂不能据此认定错误；请补查官方新闻原文、版本索引/官方仓库提交，并记录官网页面发布时间。 |

## 系统性证据问题（来自 503 条主表机器扫描）

- 74 条交叉链接字段为空。
- 368 条的 v48 第二证据效力字段仍为“存量链接：本轮未逐一核对其证据效力”；因此不能据此声称第二证据覆盖率已经人工核实。
- 103 条主信源 URL 形态含有 `models`、`release-notes`、`changelog`、`/llama/`、`/company` 或 `/updates/` 等目录/索引特征。这不是错误计数，但这类页面必须确认保留了所主张的历史日期及具体事件，不能只因列有型号就证明日期。
- 被反复复用的主信源包括 Alibaba Cloud `newly-released-models` 19 条、`z.ai/company` 11 条、OpenAI API changelog 9 条、Mureka `what-is-mureka` 历史文章 8 条、Midjourney Legacy Features 7 条、`kimi.ai/blog/` 首页 6 条、Meta `/llama/` 4 条、PixVerse changelog 4 条。索引类链接可以是便利入口；若正文不固定或不写首次日期，应优先将节点的具体原始发布文作为主信源，并保留索引为辅助证据。
- 多条 Google I/O / Anthropic / OpenAI 节点共用一份厂商大公告。它可以是多个型号同日发布的共同一手来源，但多个节点链接到同一页面不能算每个事实各有两条来源；次链接若是同文转载/目录，也不能冒充独立外部证据。
- 历史页面当前显示的更新时间、目录页面的“last updated”不能自动推导为模型首次发布日。对后续补写的模型卡尤其需要用同期公告或带历史日期的 API changelog 定义事件阶段。

## 建议进入 v49 的处理

1. 优先替换 Muse Ember、Muse Spark Open、GPT-6 Cyber 等有精确官方首发公告的泛目录主信源。
2. PixVerse V6 Max 将事件类型收窄到“API 支持/服务能力”，或暂标部分确认并等待官方首次公告，不将 API 支持日期直接冒充模型发布日。
3. 将 368 条“第二证据未审效力”保留为未完成证据审核；不能按 URL 数目自动转成通过。
4. 把单一厂商官方互证与独立外部来源分开记录。官方第二入口可以补强事实，但 `independent_source` 不应设为真。
5. 对 2026 年索引型来源建立主张级验收：是否明示型号、日期、事件类型、阶段、受众范围。任何一项未被明示，都应缩小核验结论。
