# 生产发布独立后验（2026-11-28）

既有 publication_guard.py 在发布前比较 live siteTree，用于避免重复部署及修复旧页面。系统 audit 发生在持久化前，因此其中 productionPublication 必须保持 external-verification-required。Actions deploy API 成功也不直接证明 CDN 已提供正确页面。

新后验复用同一无凭据固定 URL marker 检查，在实际 deploy 完成（或已是 current 的跳过路径）后读取公开 marker，与 checkout 的 site tree 对比，输出 run ID/attempt、expected commit/siteTree、checkedAt、current/stale/unknown 和明确 gate。仅 current 为 pass；stale、unknown、进程超时均报告 unverified，不伪装通过、不因 CDN 暂时延迟触发新的部署或邮件故障风暴。实际部署失败仍由原 workflow 失败处理。整个后验最多12秒进程预算，不写 site/data，不修改单写入者，不新增调度，不把部署状态回填到正在被证明的快照而引发无限更新。记录保留在 Actions 日志和 job summary。仅证明 marker 所声明的站点树匹配，不能证明所有资源或事实正确。

现有 collection-health incidentSummary 当前无 observed failure episodes，自动修复率没有有效分母；不得将 0/0 当作 100%。原文章召回 6/8 与同阶段 8/8 保持独立。
