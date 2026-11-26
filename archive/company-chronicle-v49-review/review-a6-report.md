# A6 独立复核简报

覆盖 21 条非 MiniMax、Qwen、腾讯、OpenAI、Anthropic 记录：Google 4、Meta 5、智谱/GLM 5、ElevenLabs 4、生数/Vidu 3。逐条对照主表日期/标题、既有主次链接，并检查官方发布稿、公司时间线、官方 GitHub/模型目录及生命周期阶段。记录 ID 按主题与源表行号标准化；已对全部现有 review CSV 检查行号后缀，无重叠。审核时间：2026-11-24。

状态统计：确认错误并给出修正 2 条；已确认 15 条；部分确认 4 条。CSV 为 20 列，21 条数据行，列宽一致。

主要发现：

- Google Gemini 1.5 Flash 主信源原来链接到 Gemini 1.5 Pro 的 2024-02-15 公告。改用 2024-05-14 官方 I/O 公告；并区分模型公开预览与 2024-07-25 Gemini 产品端上线。
- Gemini 1.5 初次公告属于 Pro 受限 Preview；Gemma 初代是开放权重发布。两者日期和事件阶段可由官方原始公告确认。
- Meta Llama 4 Scout/Maverick 已发布，Behemoth 当时仍在训练；Muse Image 发布与 Muse Video Preview 是同一公告中的不同阶段。SAM 3 是图像/视频分割模型，不应归成生成模型。
- GLM-4 官方时间线支持 2024-01-25，但主表原交叉链接实际是无关页面；已注明修正链接。ChatGLM3 原交叉 URL 实际打开为 CogAgent 新闻；精确首发日暂保持部分确认。ChatGLM 与 ChatGLM-6B 开源版本应分清。
- Eleven Multilingual v1/v2 与 Turbo v2 是不同语音分支。Monolingual v1 的模型专属首发日未找到，不能从平台 Beta 日期反推。Eleven Music 是音乐生成产品/模型能力，API 于 2025-08-18 后续开放，不属于 TTS 型号家族。
- Vidu 1.5、2.0、Q1、Q2 的新闻稿均为厂商提供给 PRNewswire 的原始发布材料，属于一手厂商供稿而非独立媒体核验。API 上线、同代功能更新和不同模态扩展均与基础模型发布时间分开记录。

文件：`v49/review-a6.csv`。
