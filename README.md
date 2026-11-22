# AI Creator Radar

面向 AI 视频创作者的轻量情报站：自动收集模型发布、AI 视频产品竞品动态、开源软件更新，并沉淀可复用的提示词模板。

**公开 RSS / Atom / GitHub Releases → GitHub Actions 定时采集 → JSON 历史归档 → GitHub Pages 静态网站。**

> 不调用 GPT、Claude、Gemini 或其他大模型 API；不需要 API Key；不产生模型 Token 费用。采集摘要直接使用信源提供的描述，不自动翻译、不生成 AI 观点。

## 在线网站

部署完成后访问：

    https://ai-luren.github.io/AI-Creator-Radar/

## 功能

- **今日总览**：资讯数量、重点动态、最近更新。
- **模型上新**：OpenAI、Google DeepMind、Qwen、Hugging Face、Anthropic / DeepSeek 等公开动态。
- **竞品动态**：Higgsfield、Dreamina / 即梦、Kling、TapNow、LibTV、Flova、Updream、ShotLab、Runway、Pika、Luma。
- **提示词库**：人物三视图、角色定妆、场景母图、多机位、分镜关键帧、图生视频、产品 TVC、一致性约束。
- **工具软件**：常用 AI 创作与后期工具目录，并追踪 ComfyUI、Diffusers、yt-dlp 等公开版本更新。
- **信源状态**：逐源显示成功、失败和最近一次采集时间；失败不会清空上次有效数据。
- **收藏**：收藏保存在当前浏览器 localStorage，不需要账号或后端。

## 自动更新

GitHub Actions 默认按北京时间每天四次运行：

| 北京时间 | UTC |
|---|---|
| 08:17 | 00:17 |
| 12:17 | 04:17 |
| 18:17 | 10:17 |
| 22:17 | 14:17 |

GitHub Actions 的定时任务可能有排队延迟，并非秒级准点。也可以在仓库 Actions 页面手动运行 Collect AI intelligence and deploy Pages。

每次运行会：
1. 并发读取启用的 RSS / Atom 信源。
2. 解析标题、原文链接、发布时间和信源提供的摘要。
3. 通过 URL 去重，合并同一文章的来源和标签。
4. 按规则标记“重点 / 关注 / 一般”，不调用模型。
5. 保留最近 60 天、最多 1,500 条记录；单个信源失败时保留上次成功数据。
6. 更新 JSON 并部署 GitHub Pages。

## 部署说明

仓库使用 GitHub Pages 的 **GitHub Actions** 发布方式。无需 Netlify、Vercel、数据库、服务器或外部定时服务。

首次创建仓库后，在 GitHub：
1. 打开 Settings → Pages。
2. Build and deployment → Source 选择 GitHub Actions。
3. 打开 Actions，允许运行 workflow。
4. 手动执行一次 Collect AI intelligence and deploy Pages。
5. 等待部署完成，网站地址为上面的 GitHub Pages URL。

如果 workflow 无法提交采集后的 JSON，检查 Settings → Actions → General → Workflow permissions，允许 Read and write permissions。本仓库 workflow 只需要仓库内 contents: write、pages: write 和 id-token: write。

## 目录结构

    config/sources.json               RSS / Atom / GitHub Releases 信源配置
    scripts/collect.py                纯 Python 标准库采集器
    site/index.html                   无构建步骤的响应式静态网站
    site/data/news.json               自动生成的资讯历史
    site/data/status.json             每个信源的采集状态
    site/data/sources.json            前端展示的信源清单
    site/data/competitors.json        竞品观察名单
    site/data/prompts.json            提示词模板
    site/data/tools.json              软件与工具目录
    .github/workflows/update-site.yml 定时采集与 Pages 部署
    tests/test_collector.py           采集器单元测试

## 修改信源

编辑 config/sources.json，每条信源包含：

- id：唯一 ID。
- name：展示名称。
- category：models、competitors、software 或 industry。
- kind：official、media、discovery 或 github。
- focus：关联模型厂商或竞品名称。
- url：RSS / Atom 地址。
- active：是否启用。
- priority：配置排序优先级。

建议优先添加官方 RSS / Atom。没有公开 RSS 的产品，暂时通过 Google News RSS 搜索发现线索，并在竞品卡片中保留官方入口；搜索结果不是官方声明，发布模型上新视频前请回到厂商公告核实。

## 本地运行

要求 Python 3.10+，不需要安装第三方包：

    python3 -m unittest discover -s tests -v
    python3 scripts/collect.py
    python3 -m http.server 8080 --directory site

打开 http://localhost:8080 预览。

只检查信源而不写入 JSON：

    python3 scripts/collect.py --dry-run

## 设计原则与边界

- 采集公开 RSS / Atom 内容和公开 GitHub Releases；不绕过登录、付费墙、验证码或访问控制。
- 不抓取私人社媒内容；X / 微信等需要登录或付费 API 的内容不在零 Token 首版范围。
- 不调用 LLM，所以不会自动生成中文翻译或编辑性总结。外文内容保留原文标题和来源摘要。
- 关键词优先级只是可解释的规则标签，不等同于人工判断。
- 竞品动态的覆盖率取决于公开信源；没有 RSS 的产品可能漏掉站内公告，建议人工核实官方更新页。
- 收藏仅保存在本地浏览器；清理浏览器数据会清除收藏。

## 关于 AIHOT

本项目参考了 https://github.com/KKKKhazix/AIHOT 所体现的“围绕行业信源建立个人情报站”的思路，但没有复制其代码、提示词、品牌或 Logo。AIHOT 的完整引擎包含数据库和大模型精选流程；本项目选择更轻的 RSS + 静态 JSON 方案，以免引入模型 Token 和服务器成本。

## License

MIT