# 独立调度看门狗（Cloudflare Workers）

这个目录只负责调度，不采集数据，不直接修改 main，不使用 LLM，不依赖 GitHub cron 本身。GitHub 内部采集工作流仍是唯一写入路径。

## 启用前的必要授权（一次）

1. 登录自己的 Cloudflare Dashboard，确认 Workers Free 套餐有空余 cron 配额。
2. 在 GitHub Settings → Developer settings → Fine-grained personal access tokens 创建仅限 Ai-luren/AI-Creator-Radar 的短期可撤销令牌。Repository permissions: Actions Read and write、Contents Read-only；Metadata 默认 Read-only。不要将令牌发到聊天、提交到仓库或放在普通变量。
3. 本机打开本目录，执行 `npx wrangler login`，然后 `npx wrangler deploy`。首次授权验收应先将 DRY_RUN 设置为 true；当前正式配置为 false，无公开 HTTP 路由。
4. 执行 `npx wrangler secret put GITHUB_RADAR_TOKEN`，在交互提示中粘贴令牌。可用 Cloudflare Dashboard 的 Secrets（加密）完成，不要使用明文变量。
5. 在 Cloudflare Cron Events / Workers Logs 验证 dry-run 返回 fresh、active-run、cooldown 或 would-dispatch；确认没有授权错误。再将 DRY_RUN 改为 false 并重新 deploy（不要提交真实令牌）。
6. 验证 GitHub Actions 中出现由外部 API 创建的 workflow_dispatch，scope=due，且生产快照成功提交；连续观察多轮，包括一次原定 cron 不触发时的外部补跑。

## 设计

正式模式每 15 分钟检查一次，2 次只读 API，只有快照超期且没有活动/刚启动的工作流时才 POST dispatch。只读取小型 scheduler-health.json；原始采集成功时间、日报日期仍由 plan_refresh.py 决定。12 分钟冷却，5 分钟超期宽限；GitHub 侧并发锁是最终防重保障。404 仅作为尚无心跳的启动场景；403、429、错误响应、无效时间均 fail closed。缺失或非法的 DRY_RUN 值默认进入演练模式；正式配置明确设为 false。没有公开 webhook、没有服务端持久化凭证，不使用第三方 cron 站点保存令牌。Cloudflare Free 限额和服务条款需以实际账户为准；本代码不代表已经部署或已通过外部实跑。

本地可运行 `node --test tests/test_scheduler_worker.mjs`（从仓库根目录）。撤销：删除 Worker/cron，并撤销细粒度令牌。备用 Mac watchdog 可继续独立使用，避免两个备份同时启用造成重复调度。

参考：https://developers.cloudflare.com/workers/configuration/cron-triggers/
https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event

## 生产运行兼容修复

- 实际 Worker 名称统一为 `ai-creator-radar`，与已授权的部署及 Secret 绑定一致，不再使用旧规划名称。
- Cloudflare Workers 不支持 Fetch 的 redirect:error；改为 redirect:manual 并拒绝所有 3xx 响应，不跟随 Location，不转发令牌。
- 只有明确配置 DRY_RUN=false 才允许 dispatch；缺失或其他值均为演练。首次云端演练已在北京时间 2026-11-27 03:00:58 成功返回 would-dispatch；恢复 15 分钟规则并显式启用生产，仍须验证真实 dispatch 和采集结果。
- 持久化日志配置由 Wrangler 文件管理。已通过 Wrangler secret put 绑定的令牌不得写入仓库。自动部署之后仍需检查实际版本及运行日志，不能以构建成功代替端到端验证。
