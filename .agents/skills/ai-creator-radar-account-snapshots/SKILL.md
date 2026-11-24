---
name: ai-creator-radar-account-snapshots
description: Read dated public follower-count snapshots for verified official accounts in the AI Creator Radar using local Ego Lite, then safely update the project dataset and GitHub when requested.
---

# AI 创作台官方账号快照

用于更新当前仓库 `site/data-v4/social-accounts.json` 中已核验官方主页的公开粉丝 / 订阅数。它记录的是带日期的公开主页快照，不是实时统计。

## 采集范围

- 开始前读取项目的 `AGENTS.md` 和 `docs/social-monitor-data-guide.md`。
- 只访问 `status: "verified"` 且有 `url` 的已有账号，不搜索、猜测或新增账号，不改账号归属和官方链接。
- 平台范围以数据文件 `trackedPlatforms` 为准。按页面实际显示的平台和 handle 核对身份后再读取数字。
- 只录粉丝数或订阅数。不要把关注数、获赞、播放量、作品数或粉丝列表当作粉丝数。

## 通过 Ego Lite 读取

- 使用本机 Ego Lite 浏览器和现有登录状态读取公开主页；按当前安装的 `ego-browser` Skill 操作。
- 只读取普通浏览器页面实际显示的公开资料。不要提取或导出 Cookie、密码、Token、私信或其他非公开数据；不要调用绕过登录、验证码、访问限制或平台风控的接口和技巧。
- 页面要求登录、出现验证码 / 安全验证、被限流，或没有显示足够资料确认账号时，停止该平台本轮剩余页面的尝试。保留受阻账号原有数字和快照日期，继续其他平台，并在结果中如实列出受阻数量。
- 不为追求完成率而用搜索摘要或旧页面缓存冒充当日主页读数。

### 先对准粉丝数字段

主页头部经常连续显示关注数、粉丝数、获赞数等多个数字。先找到标签，再读取紧跟该标签的数值；不要按屏幕上的第一个或第二个数字猜字段。

- 抖音：读取“粉丝”后面的数字；“关注”后的数字是关注数。
- B站：读取“粉丝数”后的数字。
- 小红书、Instagram、TikTok：读取“粉丝”后的数字。
- X：读取“关注者”或英文 `followers`；不要读“正在关注” / `following`。
- YouTube：读取“位订阅者”或英文 `subscribers`。
- Facebook：只读明确标注“粉丝” / `followers` 的数字。“好友” / `friends` 和点赞 / 心情数都不能当粉丝数。若主页没有显示粉丝数字，保留原值和日期。

页面刚打开时可能只显示导航、标题或消息入口。先等待主页资料区域加载，再核对平台名、handle 和数字标签；如果仍无粉丝数字，就按未读取处理，不从其他数字推算。

## 写入规则

- 只在页面可确认官方 handle 且粉丝数直接可见时更新 `followers`、`followersDisplay`、`snapshotLabel`；`snapshotLabel` 写实际读取日期和平台。
- 对 `93.2K`、`8.8万` 等约数按页面显示精度换算，并在 `note` 标记平台约数；不要虚构更高精度。
- 写入前抽查每个平台至少一条记录，确认保存的原始数值来自正确的粉丝 / 订阅标签，而不是相邻的关注数、获赞数或好友数。
- 失败、看不到数字或身份不符时，原值和原快照日期不变；不能写 `0` 或把当天日期写成成功快照。
- 只有所有已核验且有主页链接的账号均完成当日核查，才能把顶层 `updatedAt` 改成当天。部分完成时只更新成功账号的快照日期，顶层日期保持不变。
- 保留其他字段和历史数据，原子写入 JSON，并运行：

  ```bash
  python3 -m json.tool site/data-v4/social-accounts.json >/dev/null
  ```

## 同步到 GitHub

仅在用户明确要求同步或运行其每日自动化时执行：

1. 先确认 `origin/main` 最新版本及目标 JSON 没有并发改动；不要覆盖冲突。
2. 只提交 `site/data-v4/social-accounts.json`，绝不使用 `git add -A`，不纳入其他工作区文件。
3. 仅用普通 fast-forward 更新和普通 push；遇到冲突、认证失败或非快进拒绝时停止，不强推。
4. 没有实际数据变化就不创建空提交。
5. 汇报本轮按平台成功 / 受阻数量、实际更新时间和 GitHub 同步结果；不把部分采集描述为全量完成。
6. Push 成功只代表仓库同步完成。若要报告网站已更新，需另外检查 GitHub Actions / Pages 部署结果；代码推送、工作流通过和站点部署是不同状态。
