# 第二轮独立事实抽样复核（2026-11-28）

冻结生产快照：`e972eb3bc7b50c1701208bbfdabacffa9825a3f1`，原表 `site/data/model-releases-30d.json`。与首轮 config/independent-fact-reviews.json 及八事件召回基准不重叠的八个型号记录；选取不同厂商、日期及发布途径，覆盖图片、视频、LLM；七家厂商、两个 Google 型号。抽样有目的性，不是随机样本，不测未收录事件，不代表全库 99%。原始观察在核验前读取，未根据复核结果换样。逐条独立读取原发布者文章或模型卡，不依赖本站采集器和第三方聚合器。判定只覆盖型号、日期和对应的已公开阶段，不证明全球最早可用时间或所有技术说明。不同 API / 产品阶段不可混同。

| 固定记录 ID | 原快照日期 / 证据类型 | 独立原文及复核 | 结论 |
|---|---|---|---|
| cognition-swe-swe-2-flash-20261104 | 2026-11-04 / official-release | [Cognition](https://cognition.com/blog/swe-2-flash)：文章明确 11月4日，SWE-2 Flash 当日可在 Devin Desktop 和 CLI 使用，公开权重并未发布。 | 一致 |
| gemini-gemini-4-carbon-20261110 | 2026-11-10 / official-release | [Google](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-4-carbon-now-available/)：11月10日向更广泛的使用者开放，文章还明确此前已向部分网络安全防御者提供。仅验证广泛开放阶段，不是初次受限开放。 | 一致 |
| gemini-omni-flash-gemini-omni-flash-1-2-20261105 | 2026-11-05 / official-release | [Google](https://blog.google/innovation-and-ai/technology/developers-tools/introducing-gemini-omni-1-2-flash/)：11月5日 Gemini Omni 1.2 Flash 面向 Gemini API 和 Gemini for business 正式可用。 | 一致 |
| mai-code-mai-code-2-flash-20261117 | 2026-11-17 / official-release | [Microsoft](https://microsoft.ai/news/microsoft-ignite-2026/)：11月17日发布，GitHub Copilot 可用；Foundry 为限制访问预览，不得写成 Foundry 正式开放。 | 一致 |
| gpt-image-gpt-image-2-6-flare-20261104 | 2026-11-04 / official-release | [OpenAI](https://openai.com/index/introducing-images-2-6/)：11月4日文章明确 GPT-Image-2.6 Flare 与 Sunburst 可在 API 使用。 | 一致 |
| tencent-hy-mt-hy-mt3-7b-20261124 | 2026-11-24 / official-model-card | [Tencent 模型卡](https://huggingface.co/tencent/Hy-MT3-7B)：News 明确11月24日发布 Hy-MT3-7B 等三款权重到 Hugging Face 和 ModelScope。Apache 2.0。 | 一致 |
| ovhcloud-olala-olala-v1-0-translate-20261119 | 2026-11-19 / official-model-card | [OVHai 模型卡](https://huggingface.co/OVHaiLLM/Olala-v1.0-translate)：License 表明确 Release date 为11月19日，公开权重。 | 一致 |
| inclusionai-ling-ling-3-2-air-20261123 | 2026-11-23 / official-model-card | [官方模型卡](https://huggingface.co/inclusionAI/Ling-3.2-air)确认型号及公开权重；[官方仓库历史](https://huggingface.co/inclusionAI/Ling-3.2-air/commits/main)有11月23日初始提交、权重文件上传活动及 README 更新。但无法证明仓库在当日已对公众开放（创建/上传/公开是不同阶段），模型卡正文无明确日期。 | 日期/开放阶段证据待补；不能据此判错或判通过 |

结果：8 个尝试；7 个严格一致、0 个确认错误、1 个未决。已判定样本 7/7，但全样本可证实比例 7/8；未知不计入严格准确率的正确分子，也不声称全库准确率达标。尚无理由修改七条已确认记录或宣称 Ling 错误。Ling 需找到公开可用日期的直接发布者证明或可审计公共可见性历史，不把建库时间当作正式发布日期。此复核为独立留档，既有 machine-readable 首轮真值和正式门禁不修改；后续如获得明确日期证据，独立追加审计记录，保持原快照和未决状态历史。不得以重测旧八条代替新独立审计。
