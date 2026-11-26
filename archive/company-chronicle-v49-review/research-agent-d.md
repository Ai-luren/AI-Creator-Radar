# Agent D｜行业覆盖与遗漏检查

审查日期：2026-11-23  
审查对象：v48 主表 503 条记录、20 家既有厂商。未恢复用户此前删除的厂商。

## 覆盖范围与限制

- 已逐行读取 503 个标题、厂商、日期及分类，并按 20 家厂商建立当前收录清单；下表“未见”表示在这 503 条记录中没有对应独立节点。
- 完成了 OpenAI、Google、Meta、阿里巴巴/Qwen 四家的官方目录/型号页定向差集；另对 Anthropic、DeepSeek、腾讯、快手、字节、MiniMax、月之暗面、xAI、Vidu、PixVerse、Midjourney、Mureka、ElevenLabs、Cursor、Suno、智谱做了标题级覆盖扫描和定向抽查。
- 不能据此声称后 16 家已完成官方目录全量差集；特别是众多官方索引为动态页面，网页上的当前型号不能证明首次公开日期。候选遗漏须由主审核继续复核原始公告及事件性质。
- 本报告“确认遗漏”指“官方一手资料确认该型号/分支存在，且 v48 没有对应独立节点”，不等于已核准首发日期，也不自动意味着必须新增。

## 需优先评估的确认遗漏

| 厂商 | v48 未见的型号/分支 | 官方证据与证明边界 | 处理建议 |
|---|---|---|---|
| OpenAI | GPT-5 Pro；GPT-5 mini、GPT-5 nano | [OpenAI API 全部模型目录](https://developers.openai.com/api/docs/models/all)将这些列为不同模型型号，目录也区分已弃用/已关闭状态；它证明型号存在和版本分支，不单独证明各自首次发布日期。v48 有 GPT-5 主节点，没有这些独立节点。 | 按“独立型号”规则评估拆分；从 2025-08-07 首发公告及 API changelog 分别核对各分支上线日期，不要把目录当前状态当首发日期。 |
| OpenAI | GPT-5.1-Codex-Mini | 同一[官方模型目录](https://developers.openai.com/api/docs/models/all)列出 GPT-5.1-Codex、Codex-Max、Codex-Mini 为不同型号；v48 记录 Codex-Max，未见 Mini。目录说明其为较小、成本更低的 Codex 分支，但不提供可靠首发日期。 | 候选新增；再找该型号首发公告/API changelog。 |
| Google | Gemini Robotics 1.5、Gemini Robotics 2 / 2.5；Gemini Robotics ER/ER 2、On-Device 分支 | [Gemini Robotics 1.5 公告](https://deepmind.google/blog/gemini-robotics-1-5-brings-ai-into-the-physical-world/)；[Gemini Robotics 2 公告](https://deepmind.google/blog/gemini-robotics-2-brings-whole-body-intelligence-to-robots/)；[Robotics 2.5 公告](https://deepmind.google/blog/gemini-robotics-2-5-accelerates-real-world-physical-intelligence/)；[官方模型卡目录](https://deepmind.google/models/model-cards/)列有 ER 1.6、ER 2、On-Device 2。证据证明存在与发布日期（具体公告页日期），不是普通 Gemini 对话模型的别名。v48 没有 Gemini Robotics 系列独立节点。 | 高优先级补录，按 VLA、具身推理和端侧分支拆分；日期分别用公告，不要合成一个“Gemini Robotics”日期。 |
| Google | Veo 3.1 Lite | [DeepMind 官方模型卡目录](https://deepmind.google/models/model-cards/)列出 Veo 3.1 Lite。v48 有 Veo 3.1、未见 Lite 分支。目录条目标注模型卡更新时间，不足以证明 Lite 的首次公布日。 | 确认型号遗漏；日期和它究竟是模型、服务档位还是 API 型号，需查发布公告/开发者日志后再入库。 |
| Meta | SAM 3.1 | [Meta 官方公告](https://ai.meta.com/blog/segment-anything-model-3/)明确 2026-03-27 发布 SAM 3.1，并描述为可替代 SAM 3 的更新模型；v48 只有 SAM 3，未见 3.1。该来源直接支持型号、日期和效率更新性质。 | 可新增独立模型节点；注明其是 SAM 3 更新版，不误称新家族。 |
| Meta | SAM 3D（对象/场景重建、人形重建分支） | [Meta 原始公告](https://ai.meta.com/blog/sam-3d)明确 2025-11-19 发布 SAM 3D Objects 与 SAM 3D Body，并提供数据、权重、代码等；v48 没有 SAM 3D 节点。 | 高优先级评估单独补录；这是与 SAM 3 同日但不同模型家族的发布。 |
| Meta | Muse Voice Transcribe | [Meta 当前官方模型/开发者目录](https://ai.meta.com/llama/)列出独立语音转写型号及说话人分离、轮次检测能力；v48 没有对应节点。该动态目录证明当前型号存在，不足以确定首发日期。 | 先补查独立首发公告或 API changelog；证实前列入 unresolved 候选，不填猜测日期。 |
| Anthropic | Claude 3.5 Haiku | [Anthropic 2024-10-22 原始发布公告](https://www.anthropic.com/news/3-5-models-and-computer-use)同日宣布升级版 Claude 3.5 Sonnet 和全新 Claude 3.5 Haiku；v48 有 Claude 3.5 Sonnet，无 3.5 Haiku 独立节点。该公告也同时包含 Computer Use Beta，需区分模型与功能事件。 | 按独立型号补录/合并策略复核；日期明确为公告日，摘要需区分 API Beta 与模型发布。 |
| 阿里巴巴 / Qwen | Qwen2.5-Coder（含 32B 等型号） | [Qwen 官方博客](https://qwenlm.github.io/blog/qwen2.5-coder/)记载 2024-09-19 公布 Qwen2.5-Coder；[系列后续公告](https://qwenlm.github.io/blog/qwen2.5-coder-family/)记载 2024-11-12 开放包含 32B 的完整系列。v48 有 Qwen3-Coder，未见 Qwen2.5-Coder。 | 这是重要早期独立代码分支；若收录系列扩展，区分 9/19 首发与 11/12 32B/完整权重发布。 |
| 阿里巴巴 / Qwen | Qwen2.5-Math | [Qwen2.5 官方发布文章](https://qwenlm.github.io/blog/qwen2.5/)明确 Qwen2.5 家族同时包括代码专用 Qwen2.5-Coder 和数学专用 Qwen2.5-Math；v48 未见两者。 | 作为重要专用模型分支核查并补录；须进一步核对其自身日期及是否已有更早预览。 |

## 其他覆盖判断

| 厂商 | 标题扫描结果 / 待查方向 | 结论 |
|---|---|---|
| OpenAI / ChatGPT | 已覆盖 GPT、o 系列、GPT Image、Sora、Whisper、DALL·E、Codex 等；官方模型目录暴露多个独立 API 子型号未入表（上列）。 | **存在确认型号遗漏**；API 名称不应全部机械地视为基础代际，应按独立型号规则筛选。 |
| Google / Gemini Veo | 已覆盖 Gemini、Gemma、Imagen、Veo、Lyria、Genie；官方目录另列 Gemini Robotics、Gemini 3.8 Audio、Gemini 3.5 Audio、EmbeddingGemma 2、DiffusionGemma、Veo 3.1 Lite 等分支，v48 未见独立节点。 | **存在多个确认型号遗漏**；需与既有多模态主线区分。模型卡目录可能显示更新时间，应再回到首次公告核日期。 |
| 阿里巴巴 / Qwen HappyHorse Wan | 已覆盖 Qwen、Wan、HappyHorse、Qwen-Image、Audio 等新节点；旧期 Qwen2.5 专用代码/数学分支未见。 | **存在确认遗漏**。 |
| Minimax / Hailuo | 主表覆盖 abab、M 系、Speech、Music、Hailuo/H3-Image；此轮未完成 MiniMax 官方全部历史公告差集，早期文本/语音首次公开口径仍须主 Agent 核对。 | 暂无本轮已确认新增项；不代表无遗漏。 |
| 智谱 / GLM | 覆盖 GLM、Cog 系列、视觉与语音、多模态和 Agent。 | 未完成官方历史目录全量差集。 |
| 字节跳动 / Seed | 覆盖 Seed、Seedance、Seedream、Seed Audio/Realtime、Seed3D。 | 未完成官方历史目录全量差集；当前模型组合页可能遗漏早期豆包模型/API 变体。 |
| Meta / Llama | 已覆盖 Llama、SAM 1–3、Movie Gen、Muse 家族若干节点；SAM 3.1、SAM 3D 和 Voice Transcribe 尚缺。 | **存在确认遗漏**。 |
| DeepSeek | 覆盖 LLM、Coder、R1、VL、Janus、OCR；需对照官方 GitHub 核实各独立开源型号与专用分支。 | 未完成全量差集。 |
| 快手 / Kling | 覆盖 Kling 视频、Kolors/Kling Image 等；需检查可灵早期模型的 Preview、API 与正式产品日是否被重复或遗漏。 | 未完成全量差集。 |
| 腾讯 / Hy | 覆盖 Hunyuan 语言、图像、视频、3D 和世界模型；需对照混元 Turbo、文生图/视频历史型号目录。 | 未完成全量差集。 |
| 月之暗面 / Kimi | 覆盖 Kimi 主线、代码、音频、多模态；需核实早期 Kimi-VL/Kimi-Audio 各权重变体及 API。 | 未完成全量差集。 |
| xAI / Grok | 覆盖 Grok、Aurora、Imagine、代码和语音；需区分 Grok 型号快照与基础代际。 | 未完成全量差集。 |
| 生数科技 / Vidu | 覆盖 Vidu Q/S 与 Motus 世界模型；需查公司官方产品/API 型号目录是否还有独立图像/数字人支线。 | 未完成全量差集。 |
| 拍我 / PixVerse | 覆盖 V 系列、C1、R 世界模型；需把 API support changelog 与新基础模型首发分开。 | 未完成全量差集；Agent C 已发现 V6 Max 节点事件性质风险。 |
| Midjourney | 覆盖 V1–V8.2、Video；需查官方旧版本目录中 V5.3 等中间版本是否属于重要独立节点，避免快照过录。 | 未完成全量差集。 |
| 昆仑万维 / Mureka | 覆盖 V1–V9.5、Remix；需区分 Remix 功能发布和底层生成模型代际。 | 未完成全量差集；不建议把 Remix V9.5 默认算新基础模型。 |
| ElevenLabs | 覆盖 Eleven v1–v4、Flash/Turbo、Music；需查官方发布日志中的多语种、专业配音和语音转语音独立分支。 | 未完成全量差集。 |
| Cursor | 已有 Composer 主线及 IDE/Agent 产品节点；需确认 Composer 2.5 与模型 ID/后端模型的官方命名。 | 未完成全量差集。 |
| Suno | 覆盖 v1–v6；需核查 v2、早期 Beta 的月份精度以及 v4.5 系列之后模型别名。 | 未完成全量差集。 |

## 建议送入 v49 遗漏表的项目

以下 10 组经官方资料证实存在且 v48 未见对应节点，建议写入 `missing-models-v49.csv` 并交 Agent B/主 Agent 完成事件日期复核：

1. OpenAI GPT-5 Pro、mini、nano。
2. OpenAI GPT-5.1-Codex-Mini。
3. Google Gemini Robotics 1.5/2/2.5 与 ER/On-Device 分支。
4. Google Veo 3.1 Lite。
5. Meta SAM 3.1。
6. Meta SAM 3D。
7. Meta Muse Voice Transcribe。
8. Anthropic Claude 3.5 Haiku。
9. Qwen2.5-Coder。
10. Qwen2.5-Math。

其中 GPT API 的 mini/nano/Pro、Veo Lite 和 Meta 当前目录中的型号可能存在“API 型号/服务档位是否独立历史节点”的口径争议；节点存在已确认，但应经事件类型和首发公告核实后决定如何入库。未列出项目不能据此视为已证明完整。
