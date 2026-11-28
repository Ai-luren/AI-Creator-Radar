# 正式消费视图与内部审核分离（2026-11-28）
基线 133aab6d7c52549c99e138c49ade38473f477a79；#98 已合并，原始12条近期候选、全部历史、社媒、赛事原数据保留。用户要求正式工作台仅消费已核验资讯，不把审核负担转移给用户。
- 近期上新仅正式 releaseEvidence、verifiedStages 和已核验原帖宣传；移除原始 model-updates 公告直通及待复核 tab，旧 status=pending 回落正式发布。
- 厂商发展史通过同一资格谓词处理列表计数、年份、时间轴和搜索。外部聚合候选不混入；既有人工已审核状态与严格自动双官方核验（含 event ID 与双方证据）保留。旧 review=pending 也回落已核验视图。
- 社媒候选主页不进入搜索或明细；保持平台矩阵缺失为 —，不按零计；只收录已核验主页。赛事自动发现、仅索引或合作方未复核线索留后台，正式赛事只展示 official-page；官方申请入口和实际开放状态仍分开，不能把状态未知改成开放。模型库已确认身份但日期未知的历史型号保留，不伪造日期。
- 独立原文补证：GLM-5-Turbo https://www.zhipuai.cn/en/research/155 为2026-03-15；DeepSeek https://api-docs.deepseek.com/updates/ 的 V4.1 Flash 为2026-09-10、Vision Exp 为2026-08-21；当前未解析的旧记录按发现日进入近期候选，需修复日期区段解析，不是新模型。Scribe v3/v3 Live https://elevenlabs.io/blog/scribe-v3 11-10 公告且已在产品使用；GLM Flash https://autoclaw.z.ai/en/blog/model/glm-5.3-flash/ 11-19 模型介绍；Legal https://autoclaw.z.ai/en/blog/model/GLM-5.3-flashX-Legal/ 11-13 AutoClaw 服务开放；Daybreak https://openai.com/index/daybreak-red-aws-govcloud 为11-04既有安全模型渠道扩展；MiniMax https://www.minimax.cn/blog/minimax-h3-image 明确11-10正式发布权重，原始候选11-03日期冲突需核对既有阶段证据；SFX https://elevenlabs.io/docs/changelog.md 为可用性声明，须与既有首发分开。此轮不擅自改 canonical 事实、不假称候选全部已核实，不把补证记录等同自动召回。
- 不添加数据存储、定时任务或请求。保留后端证据队列、自动双官方核验、审计和生产错误通知。验收要求完整 CI、双浏览器、公开部署证据；待补证后续沿现有流程进行。
