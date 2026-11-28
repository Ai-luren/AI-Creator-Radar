# 2026-11-28 待复核队列收敛（定向修复）
冻结主分支 2e7bd3a12e03687cf590ba1c6379cf090d125539。社媒只有2条实际待核验（Vidu Facebook 是个人页、Pika 小红书归属未确认），不假造账号或粉丝数字。近期上新有17条待复核，厂商发展史另有已人工确认节点的自动重复。此次不增加采集、表或调度。
- 已复核官方原文：https://community.openai.com/t/gpt-live-1-1-has-arrived-in-the-api/1418537 （11月20 API开放，已有 verifiedStages）；https://www.alibabacloud.com/help/zh/model-studio/newly-released-models （11月23 Qwen Audio 3.1 Live 服务上架，已有英文同日核验）；https://platform.mureka.ai/docs/en/changelog.html （11月12 Remix V9.5 API开放，已核验；11月17 时长参数为功能更新）；https://openai.com/index/devrev-enterprise-self-service （11月4 客户案例，非模型发布）。
- 五条候选的匹配要求完整来源ID/家族/日/原文URL/标题；三条已核验服务阶段仅在对应 verifiedStages 存在时退出待复核，另两条是明确非模型首发。保留原始 model-updates，正式发布及服务阶段记录不变。预计17→12，不把剩余12条强制升级。
- 厂商发展史7条与既有审核节点一一对应的原文、型号、日期重复，另1条 DevRev 案例移出派生历史。要求目标审核ID、日期、原文和已确认状态仍存在，保留人工审核和未确认冲突；每轮生成均执行，避免重采后复发。仅移除派生重复/无关候选，原始观测和审核证据保留。
- 后验须核查完整CI、双浏览器、生产生成和公开版本；剩余真正欠缺证据、不同发布阶段、历史日期冲突仍保留，不能追求表面零待复核。
