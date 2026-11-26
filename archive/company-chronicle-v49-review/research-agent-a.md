# Agent A — 模型谱系独立研究记录

审核输入：`/Users/ailuren/Downloads/company-chronicles-model-product-v48.csv`（503 条，20 个厂商主题）。本记录只给出模型谱系层面的独立发现和待查项，不修改主表。检索日期：2026-11-23。项目规范要求以官方公告、官方模型目录和开发者文档为模型事实依据。

## 覆盖方式与边界

先逐厂商枚举主表标题，检视通用语言模型、代码/小型/推理分支、多模态、图像、视频、音频、音乐及世界模型等谱系；再对可见的官方产品目录/模型卡/发布记录做定向比对。重点交叉检查 Google、OpenAI、Meta、DeepSeek 四家官方目录，以及各家主表最新型号。该轮不是对全部 503 条逐个重新核实首发日期，也不能据此将未列出的家族宣告为“完整”。部分官方页面是滚动更新的目录，只能证明页面当前列出的型号存在，不能单独证明首次公开日期。

## 已发现的候选漏项

| 厂商 | 主表现状 | 官方目录交叉比对结果 | 建议与证据 |
|---|---|---|---|
| Google / Gemini Veo | 已覆盖 Gemini 4 Neon、Hydrogen、Carbon、Argon；视频/图像/音乐和 Genie 已有较多条目。 | DeepMind 官方模型卡目录列有 **Gemini 3.8 Audio**（Live、Live Extended Thinking、Flash TTS、Flash-Lite TTS），主表未见；官方发布页称其基于 Gemini 3 Pro，含多种独立语音端点。另官方 2026-11-10 发布 **Gemini Robotics 2.5**，主表未见；官方机器人目录另列 Robotics ER 2、On-Device 2，需判定是否作为独立版本节点。官方新闻索引也列 **EmbeddingGemma 2**，主表未见。 | 可作为补录候选，逐条再找首次公告/发布日期后才入库。来源：[DeepMind Model Cards](https://deepmind.google/models/model-cards/)，[Gemini 3.8 Audio card](https://deepmind.google/models/model-cards/gemini-3-8-audio/)，[Gemini Robotics 2.5 announcement](https://deepmind.google/blog/gemini-robotics-2-5-accelerates-real-world-physical-intelligence/)，[Robotics directory](https://deepmind.google/models/gemini-robotics/)，[DeepMind news](https://deepmind.google/blog/)。目录分别证明家族/型号存在；Robotics 新闻页明确 2026-11-10 引入 2.5。 |
| OpenAI / ChatGPT | 已有 GPT-5、5.1、5.2、5.3、5.4、5.5、5.6 和 Codex 支线，但 GPT-5 条目没有拆出 Pro、mini、nano。 | OpenAI GPT-5 首发公告明示 **GPT-5 Pro** 同日推出；官方模型目录列出 GPT-5 mini/nano；主表未见这些独立型号。官方模型目录还列出 **GPT-5.1-Codex-Mini**，主表未见。它们是专名产品/型号分支，适合独立记录或在谱系节点明确列出。 | 首发日和具体发布阶段应分别从官方原始公告/开发者 changelog 核实，不可直接以当前模型目录日期替代。[Introducing GPT-5](https://openai.com/index/introducing-gpt-5/)，[OpenAI API model catalog](https://developers.openai.com/api/docs/models/all)，[GPT-5.1 for developers](https://openai.com/index/gpt-5-1-for-developers/)。首发文证明 GPT-5 Pro 同日推出；模型目录证明各型号存在；开发者公告证明 Codex Mini 分支存在。 |
| Meta / Llama | 旧 Llama 主代际已列至 Llama 4；2026 年 Muse 家族已补入 Spark、Glimmer、Image、Video 多项。 | Meta 官方开发者产品目录当前另列 **Muse Wonder、Muse Wonder Full、Muse Voice Transcribe、SAM 3.1**，主表未见。目录可证明型号/产品存在，但不一定是首次公告页；Muse Wonder Full 可能是产品内变体，需核实是否足够独立；SAM 3.1 是否计入该“AI 模型与产品史”应统一纳入规则。 | 对确认有独立版本/发布事件的条目再补原始公告和日期；不要把 Meta 页面滚动目录更新日写成首发日。[Meta AI developer models](https://ai.meta.com/Llama/)。 |
| DeepSeek | 已有 V4 Preview、Pro、V4.1 Flash 等主线。 | 官方 changelog 明确 V4.1 Flash 于 2026-09-10 发布，10-17 是 V4.1-Flash-1017 更新并保留 API 别名；主表 9-10 条目与首发口径一致。**V4.1-Flash-1017 不宜自动作为独立基础模型代际**。官方透明度中心给出 V4 首发日期和型号，适合与新闻页互证。 | 可将 10-17 更新作为备注或功能更新，不另立模型代际，除非维护规则明确收录快照。来源：[DeepSeek API Changelog](https://api-docs.deepseek.com/updates/)，[DeepSeek Transparency Center](https://deepseek.com/en/transparency/)，[V4.1 Flash release](https://deepseek.com/en/news/deepseek-v4-1-flash/)。 |

## 谱系风险提示

1. **当前型号目录不等于首发证据。** OpenAI、Meta、Google 的模型目录滚动变化，只能证明目前条目存在；需结合日期明确的原始公告或 changelog 填写事件日。
2. **变体粒度有混用风险。** GPT-5 Pro / mini / nano、GPT-5.1-Codex-Mini 等具独立名称与用途；DeepSeek 的 `-1017` 更新则更像服务快照/更新标记。入库规则应按“公开独立型号/发布事件”区分，而不是只按字符串新增记录。
3. **Google 早期史应区别架构/研究节点与可用模型。** 主表包括 Transformer、BERT 等历史技术节点，也应统一说明是否收录论文/研究模型；不能只对当代产品模型要求逐项拆分。
4. **Meta 的新品牌谱系已从 Llama 转 Muse。** 若目标是“模型与产品发展史”，官方模型目录中语音、图像与代理模型都是潜在覆盖面；当前条目只覆盖部分 Muse 型号。
5. 其它厂商（阿里、MiniMax、智谱、字节、Anthropic、快手、腾讯、Kimi、xAI、生数、PixVerse、Midjourney、Mureka、ElevenLabs、Cursor、Suno）的主表已呈现多个历史代际和分支。此轮未对这些厂商逐条穷尽其官网目录，因此不能据此断言无遗漏；尤其需要另行查找早期基础模型首发页、非旗舰端点、音频/实时/轻量分支及官方更新日志。

## 与来源直接对应的核验结论

- Google DeepMind 当前模型卡索引列出 Gemini 4 Neon、Hydrogen、Carbon、Omni 1.2 Flash、Argon、Nano Banana 2.1、Gemini 3.8 Audio、Gemini 3.8 Flash、Gemini Omni Flash；多数已在主表，但 3.8 Audio 缺项。卡片页面发布日期不能替代各型号实际首次公开日。
- DeepMind 官方 2026-11-10 Robotics 新闻明确介绍 Gemini Robotics 2.5，阐述其为 VLA；主表没有该型号/事件。
- OpenAI 官方 GPT-5 首发文章把 GPT-5 Pro 称为同日发布的 GPT-5 变体；开发者官方目录可见 GPT-5 mini/nano 和 GPT-5.1-Codex-Mini。主表没有独立型号记录。
- Meta 官方目录可见 Muse Wonder、Muse Wonder Full、Muse Voice Transcribe、SAM 3.1；主表无同名条目。需再核原始发布日期及其中哪些应单列。
- DeepSeek 官方 changelog 记载 V4.1 Flash 首发日及后续 `1017` 版本更新，适合反向防止将更新快照误记为新代际。

## 未解决项

- 上表新增候选以外的 16 家厂商未完成“官方全目录逐项差集”；无法可靠统计所有遗漏总数。
- Meta 官方滚动模型目录当前没有为每项提供统一发布日期；Muse Wonder 系列、Muse Voice Transcribe、SAM 3.1 的首次发布时间需逐项追原始公告。
- Google EmbeddingGemma 2 的确切公告日期/独立模型节点价值需按原始发布材料确认。
- OpenAI GPT-5 mini/nano 的首次发布时间与其是否应拆成两条，须以同日首发公告和 API changelog 作证。
- 对 20 家的最早公开模型，本报告仅由主表提取其已列节点，未构成逐厂商的“最早发布模型”最终判定。
