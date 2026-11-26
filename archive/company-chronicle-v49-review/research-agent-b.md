# Agent B 独立报告：官方信源与发布日期复核

审查对象：`/Users/ailuren/Downloads/company-chronicles-model-product-v48.csv`，按主表标题与主/次链接定向核对。检索日期：2026-11-23（页面显示日期按页面自身时区/标注记录）。

## 覆盖范围与限制

本报告独立审阅 19 个具体节点/节点组：OpenAI GPT、GPT-2、InstructGPT、DALL·E 2、GPT-6 Cyber、GPT-6 Rosalind、GPT-6.1 Sol、GPT-6.1 Terra、ChatGPT Space；Google Transformer、BERT、Imagen、Nano Banana 2.1、Gemini 3.8 Flash、Gemini 4 Carbon；Qwen4-Max Preview/正式上线；Seedream 5.5；Mureka V9.5（8 月）和 Mureka Remix V9.5（11 月）。其中有些节点只完成初始证据审阅，故下表明确区分确认、部分确认与证据不足。**这不是 503 条的全库逐条复核**，也没有把未打开的存量证据记为已核验。

## 逐项发现

| 主表节点 | 结论 | 证据实际证明了什么 / 处理建议 |
|---|---|---|
| OpenAI GPT 初代，2018-06-11 | 已确认：型号、日期、事件性质（公开研究介绍） | [OpenAI 原始文章](https://openai.com/index/language-unsupervised/) 页面标注 June 11, 2018，说明发布了可在多个任务微调的语言模型系统；正文未把它命名为“GPT-1”，故“GPT 初代”宜作后见谱系称呼。 |
| GPT-2，2019-02-14 | 已确认：型号、日期、事件性质（首次公告/分阶段公开） | [OpenAI 原始公告](https://openai.com/index/better-language-models/) 标注 Feb 14, 2019，明示模型叫 GPT-2、是 GPT 后继、当时仅先发布小模型/论文，完整权重暂不发布。后续文章只能证明后续过程，不可单独替代首发证据。 |
| InstructGPT，2022-01-27 | 部分确认：日期正确，事件标签需精确化 | [OpenAI 文章](https://openai.com/index/instruction-following/) 明示该日发布，但同时称这些模型此前已在 API beta 超过一年，该日是设为 API 默认模型。主表标题“发布”容易误读为首次公开；建议改为“成为 API 默认模型（此前已 beta）”，备注保留更早 beta 日期尚待定位。 |
| DALL·E 2，2022-04-06 | 部分确认 | [OpenAI 当前模型页](https://openai.com/index/dall-e-2/) 确认模型/研究系统和先向有限用户预览、7 月扩至 beta，但当前页面未在抓取正文里显示发布日期。表中 Reuters 链接与 OpenAI 日期相同，但单靠新闻稿不能代替原始公告。建议保留 2022-04-06 为公告/有限预览，补上页面发布日期可见的 OpenAI 原始材料或论文记录。 |
| Transformer 架构，2017-06-12 | 部分确认：需把事件性质落在论文公开 | [Google 回顾时间线](https://blog.google/innovation-and-ai/products/google-ai-ml-timeline/) 是回顾性汇总，不能单独当作当年首发公告；所列 [arXiv 论文](https://arxiv.org/abs/1706.03762) 可支撑论文公开日期。建议将标题/事件说明写成“Attention Is All You Need 论文公开”，而不是泛称“架构提出”而不注明论文事件。 |
| BERT 开源，2018-11 | 证据不足：次链接重复 | 主表主信源与交叉链接是同一篇 [Google Research 文章](https://research.google/blog/open-sourcing-bert-state-of-the-art-pre-training-for-natural-language-processing/)，不能算双证据；当前页面抽取正文未给出事件日期，需检索网页存档/当年 GitHub commit/论文版本来支撑日期和“开源”事件。暂不应以重复 URL 标记双源通过。 |
| Imagen 初代，2022-05-23 | 证据不足：主链接已重定向 | 主表所列 [imagen.research.google](https://imagen.research.google/) 目前不可作为历史事件证据；所列 DeepMind Imagen 页现已重定向到 Gemini Image/Nano Banana 产品页。应替换为 2022 年 Google Research 初始公告/论文页面或存档；在替换前标证据不足。 |
| Nano Banana 2.1，2026-10 | 部分确认 | [Google DeepMind 模型卡](https://deepmind.google/models/model-cards/nano-banana-2-1/) 标“Published 6 October 2026”，可确认型号与卡片发布日期，但**模型卡发布日期不必然是首次公开/上线日**。主表精度仅到月份，暂无找到更早首发公告；保留月份可暂用，事件性质注明“模型卡/目录可确认，首次公告待查”。 |
| Gemini 3.8 Flash 与 Flash Cyber，2026-09-02 | 已确认：公告日及型号 | [Google 原始公告](https://blog.google/innovation-and-ai/models-and-research/gemini-models/3-8-flash-and-3-8-flash-cyber/) 明确 Sep 02, 2026、两种型号及可用安排；[DeepMind 模型卡索引](https://deepmind.google/models/model-cards/) 能辅助核对型号，但属于同一厂商二手目录，不是独立来源。公告已足以支持首次宣布日期，GA/API 阶段需分别记录。 |
| Gemini 4 Carbon，2026-10-28 | 部分确认：日期是宣布，不是广泛可用 | [Google 原始公告](https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-carbon/) 写明 Oct 28 为 announce；[后续可用公告](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-4-carbon-now-available/) 标 Nov 10 才面向开发者、企业、科学家和消费者提供。若主表只记“模型”节点，日期可保留但事件需标首次公布；不要写成 GA 日期。 |
| Qwen4-Max Preview 2026-11-11 / 正式服务 2026-11-16 | 已确认：阶段清楚 | Alibaba Cloud [Token Plan 更新](https://www.alibabacloud.com/help/en/model-studio/token-plan-product-updates) 明确 Preview 于 11 月 11 日开放、正式 Qwen4-Max 于 11 月 16 日可用；这是同厂官方两入口，能交叉印证具体服务阶段，但非独立出版方。当前“newly released models”页面会持续更新、页面更新时间不是历史首发时间，需保留上述 dated changelog 作为关键日期依据。 |
| Seedream 5.5，2026-11-09 | 已确认：官方公告日期、型号 | [ByteDance Seed 原始文章](https://seed.bytedance.com/zh/blog/more-realistic-images-more-stable-editing-across-100-rounds-introducing-seedream-5-5) 页面标 2026-11-09 并明说当天推出 Seedream 5.5；其[视觉文章索引](https://seed.bytedance.com/en/blog_list/visual) 可证明目录收录，但两者同源，不能充当独立外部佐证。 |
| ChatGPT Space，主表 2026-09-29 | 部分确认：公告与 rollout 混写 | [OpenAI DevDay Recap](https://openai.com/index/devday-2026-recap/) 明确 9 月 29 日介绍 ChatGPT Space；[ChatGPT release notes](https://help.openai.com/en/articles/6825453-chatgpt-release-notes) 则写明全球向 Plus rollout 是 11 月 20 日。故 9 月 29 日可作为“宣布/向 Pro、Business、Enterprise 提供”的日期，不应不加阶段地称为全面推出。两条来源都属于 OpenAI，非独立信源。 |
| GPT-6.1 Sol，2026-09-29 | 已确认：型号、日期、API 发布；需换证据 | [OpenAI API Changelog](https://developers.openai.com/api/docs/changelog) 明示 Sep 29 Released GPT-6.1 Sol；[OpenAI Research Releases 索引](https://openai.com/research/index/release/) 同日列其官方发布文章。主表当前引用 GPT-6 Astra 页和 All Models 目录并不能独立证明该模型首发日期，应换成上述两条精确来源。 |
| GPT-6.1 Terra，2026-10-26 | 已确认 | [OpenAI Model Release Notes](https://help.openai.com/en/articles/9624314-model-release-notes) 与 [API Changelog](https://developers.openai.com/api/docs/changelog) 均标 Oct 26；官方发布文章题为 [Introducing GPT-6.1 Terra](https://openai.com/index/introducing-gpt-6-1-terra/)。模型发布和产品/API 可用当天，证据是厂商多渠道材料，不是第三方独立来源。 |
| GPT-6 Rosalind，2026-10-30 | 已确认：型号、日期、定向访问状态 | [OpenAI Model Release Notes](https://help.openai.com/en/articles/9624314-model-release-notes) 记 Oct 30 并写明受限研究访问；[System Card Addendum](https://deploymentsafety.openai.com/gpt-rosalind-6) 同日说明模型性质/限制。应避免把有限访问描述成一般公开 GA。 |
| GPT-6 Cyber，2026-11-05 | 已确认：公告日、型号、访问状态 | [OpenAI 原始发布](https://openai.com/index/introducing-gpt-6-cyber/) 与 [System Card](https://deploymentsafety.openai.com/gpt-6-cyber) 均标 Nov 5；两者证明限定 Daybreak Red 用户访问，不是开放 API。建议第二证据补 System Card，当前单有通用 changelog 不足以支持受限可用描述的全部细节。 |
| Mureka V9.5，2026-08-28 | 已确认：模型/产品升级公告 | [Mureka 原文](https://www.mureka.ai/blog_en/mureka-v9-5-model-changes.html) 标 Published August 28 2026，明确 V9.5 模型变化。模型首次生成开放时点仍未由这篇说明确定，若记录的是发布公告日期，摘要应如此表达。 |
| Mureka Remix V9.5，2026-11-16 | 部分确认：事件实质是独立 Remix 模型/功能发布，不是生成底座 V9.5 首发 | [Mureka Remix V9.5 原文](https://www.mureka.ai/blog_en/mureka-remix-v9-5-is-here.html) 标 Published November 16 2026，称其为 Remix 模型，说明 API 参数 `mureka-9.5` 与上传/重混用法；另有 [8 月 V9.5 文章](https://www.mureka.ai/blog_en/mureka-v9-5-model-changes.html) 已记录生成模型 V9.5。因此两节点可以并存，但 11 月条目必须保持“Remix V9.5 功能/专用 remix 模型”，不可归并为基座 V9.5 首次发布。 |

## 证据结构问题（对全库的处理建议）

1. 初步数据统计：503 条里 243 条状态仍为“待逐条复核”、122 条明确沿用旧审核、另有 2 条首发日待查；74 条主表第二链接字段为空。另有 368 条第二证据效力字段写“本轮未逐一核对”，59 条写有人工匹配第二入口。故主表状态及 URL 数量不能直接换算成“已逐条复核”或“有效双证据覆盖率”。
2. 重复 URL、同一官方文章的不同语言/追踪参数，以及 changelog 与新闻稿互引，不是独立来源。可记录为同一厂商的不同官方证据载体，但应把独立发布方计数分开。
3. 官方产品/model index 属于活文档；它通常支持“当前存在/当前服务”，如果无日期行或版本历史，不能证明首次公开日。模型卡发布日期也只证明卡片发布，不自动证明模型首发。
4. 同一型号的首次宣布、预览、API、正式服务/GA、产品端逐步 rollout、开放权重是不同时间点。推荐 evidence 表按“事件性质”分条，不把其中一个日期替代其他生命周期日期。
5. 老记录主信源失效/重定向时保留原 URL 只能追溯“曾经填写过”，不代表仍有可审阅证据；记录访问障碍及替代档案，不给绿色状态。

## 可交给合并 Agent 的修复建议

- 追加行级审查时，只有直接核对到相应页面且页面证明对应事件/日期的记录才计入“本次逐条审核”。本次报告只覆盖上述 19 个具体节点/节点组，余下 484 条未由 Agent B 重验。
- 修正或备注：InstructGPT 的事件阶段；ChatGPT Space 的 9/29 announcement 与 11/20 Plus rollout；Gemini 4 Carbon 的 announce 与 availability；Mureka 11/16 Remix V9.5 与 8/28 V9.5 基础生成模型的区分；GPT-6.1 Sol 的错误泛化次证据。
- 把重复的 BERT 主/次 URL 记为“同一材料”，并把 Imagen 旧链接重定向标为失效/证据不足；不要据此推断事实为假。
- 不建议仅凭这些样本向主数据直接批量写入确认；由合并 Agent 将本报告中的证据效力纳入 `evidence-v49.csv` 与逐条审计结论。
