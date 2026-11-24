# AI 模型与产品发展史 v49 审核报告

> 此报告由 `build_v49.py` 根据 v49 CSV 自动统计生成。所有计数取自交付文件。

## 当前统计

- 历史节点：512；厂商：20
- 本轮逐条记录有核实日期：512
- 完全通过核验：351
- 日期错误修正：5
- 型号及分类错误修正：5
- 事件标题/口径修订：7
- 新增模型：9（其余 10 条官方目录差集候选仍待逐项核对日期与纳入规则）
- 删除或合并重复节点：0
- 仍缺乏可靠证据或未解决：151
- 尚未经过独立重新审核：0
- v48 主表缺少第二链接：74
- v48 基线标注“待逐条复核”：243；“沿用既有核验（未再次逐条核验）”：122
- v48 第二证据效力尚未逐一核对：368；已有人工匹配官方第二入口：59
- 事实审核通过率：68.6%
- 第二证据效力已判定记录覆盖：512/512（100.0%）
- 证据链接本轮打开并核对：765/1484（51.5%）
- 尚待解决或证据不足的节点：151
- v49 厂商/日期/标题重复节点数：0
- v49 日期格式合法记录：512/512

## 状态分布

- 存在冲突：需要复核：23
- 已确认：型号、日期与事件性质：351
- 确认错误：已纠正：10
- 证据不足：暂不采信：6
- 部分确认：型号存在，日期或阶段不确定：122

## 来源与基线

- 主表 SHA-256：`b3e7bfe164ab122045e44e13860be38f9f57d1c96aa517463d1eba7ba523eed5`
- 历史审核 SHA-256：`836ab60af369c09c02f5295aace028873f7db990c962b05427bfa3abbf1f3e82`
- 证据登记 SHA-256：`8b08dbbc5e1c38dadeecb8c17499a8b9d63f28f9563fd1b0f8207845402ef4b6`
- 输入文件保留在原路径；本报告不把 v48 既有结论视为本轮核验。
- 历史资料与模型遗漏检查截止：2026-11-23；v49 合并、变更记录与最终验收日期：2026-11-24（Asia/Shanghai）。

## 审核输入映射控制

- 唯一原始节点审核构成为：初始审核 24 条；Agent A/B/C/D 分别提交 124/113/83/159 条；9 条 v49 新增模型另行核验，合计覆盖 512/512。
- `review-quarantine.csv` 保存 45 个不计入覆盖的隔离项 ID 与原因，包括 1 条错配（ID 指向 xAI Grok 4.6，但结论与来源属于 OpenAI GPT 初代研究）及重复映射项。审核结论按规范化稳定记录 ID 与主表行对应，不按 URL 数或历史状态计数。

## 专家报告与主要发现

- **Agent A（谱系，124 条唯一审核输入）**：定向比对 Google、OpenAI、Meta、DeepSeek 目录并复核 MiniMax、GLM、Qwen、Vidu、ElevenLabs、Seed、Cursor 等行。核实独立专用分支与快照边界；`DeepSeek V4.1-Flash-1017` 是更新快照，不另立基础代际；修正 Gemini 1.5 Flash 主链接误指 Gemini 1.5 Pro，并将 5/14 模型/API 预览与 7/25 消费者端上线分开。A8 还区分 Tongyi Qianwen 首次公开与后续权重开放，指出 GLM-4-9B/GLM-130B 的官方历史时间线冲突。全库目录差集并未穷尽每家厂商全部历史产品。
- **Agent B（信源/日期，113 条唯一审核输入）**：逐页区分首次公告、Preview、API 与产品 rollout。将 GPT-5.1 首次公告定为 2025-11-12（11-13 是 API）；确认 GPT-6 Astra 与 Grok 4.6 的日期但限定为有限/受限访问；识别 GPT-5.5 公告/API 日期、Grok 4.5 API/公告、Grok Bot公告/changelog、Mureka V7.0/V7.5 与 Vidu新闻稿日期的阶段差异。遇官网正文不可读或滚动目录无历史日时保留部分确认。
- **Agent C（对抗性复核，83 条唯一审核输入）**：重点质疑日期口径、型号与产品混淆、重复模型和来源伪独立。指出 GLM-5.4 次证据不足、PixVerse V6 Max 现有证据只支持 API 新增；对 Google Nano Banana、Deep Think、Lyria 阶段进行区分；并指出 BERT 重复URL、Imagen 重定向和滚动索引不能证明首发日期。其覆盖是抽样对抗复核，不是对 512 条的第二次独立全量审阅。
- **Agent D（遗漏/覆盖与复核，159 条唯一审核输入）**：扫描全部初始标题并对 OpenAI、Google、Meta、Qwen 等目录作定向差集，另行核验腾讯/Kling、PixVerse/Vidu、GLM 等。确认 Qwen-Image-Edit 日期应为 2025-08-18；修正智谱清言产品上线日 2023-08-10→2023-08-31；发现同日公告/产品阶段差异、Google Gemini Flash 源链接错配，以及 GLM-4-9B/GLM-130B 历史首发日期冲突。Google 7/21同日公告遗漏 Gemini 3.5 Flash Cyber，已依官方来源单独补录为有限访问试点模型。尚未补录的目录候选和纳入粒度争议见 `missing-models-v49.csv`。

四位专家的概览报告和分批审核 CSV 均保存在 `v49/`。Agent A/B/C/D 的审核输入计数合计 479 条，另有初始主审批次 24 条；重复映射列入隔离表，不重复计数。官方目录确认型号存在，不自动确认发布日期或独立历史节点资格。

## 数据验收

验收脚本 `validate_v49.py` 的最近一次结果：**全部通过**。

- expected_node_count_includes_additions: 通过
- expected_20_vendors: 通过
- vendor_whitelist_preserved: 通过
- all_dates_legal: 通过
- no_duplicate_vendor_date_title: 通过
- audit_one_to_one_and_consistent: 通过
- stable_record_ids_unique_and_complete: 通过
- audit_status_enum_valid: 通过
- all_substantive_changes_logged: 通过
- records_within_2026_11_23_cutoff: 通过
- all_outputs_utf8_readable: 通过
- v48_source_still_present: 通过
- expected_output_files_present: 通过
