# AI视频创作台

面向 AI 视频创作者的研究工作台：集中查看模型上新、厂商历史、能力榜单、官方案例与教程、创作资源和行业动态。

核心原则：**优先复用已经存在的优质数据源，不重复建设新闻库和 Prompt 大全。**

## 工作台模块

- **模型动态 / 模型库**：关注视频、图像和大语言模型正式发布；模型家族、具体版本、官方证据和其他模块的关联共用同一模型目录。
- **模型排行榜**：FAI.Fashion 提供图像、视频和语音快照；Arena 官方 CC BY 4.0 数据集覆盖图像编辑、视频生成 / 编辑和网页生成等榜单；语言、代码、多模态与 Agent 榜单使用 BenchLM 官方实时嵌入。每个子榜显示来源、更新时间和评测方法。
- **AI 早报**：集中查看 AIHOT 精选和橘鸦 AI 早报，分别按北京时间 08:00、10:00 同步。
- **创作案例**：接入 GoodCase.ai RSS，展示案例封面、作者、摘要和 Prompt 预览；完整内容回到原站。
- **Awesome 资源**：通过 GitHub API 同步精选开源仓库的描述、Star、Fork、更新时间和许可证。
- **我的提示词**：人物设定、人物三视图、场景母图、多机位、分镜、单镜头视频、TVC、Seedance 2.5 结构化 Prompt。
- **教程与 Skill**：优先保存模型厂商和平台官方指南、工作流与可安装 Skill。
- **官方案例与教程**：按模型汇总厂商 Demo / 宣传片、官方教程和已核实的官方体验 / API 入口；不收录用户作品，不记录测试结果。
- **创作平台 / 模型排行榜 / 我的收藏 / 偏好设置**：常用入口、个人收藏、编辑和备份。

## 外部资源接入

### RSS / Atom

配置文件：config/resource-sources.json

当前接入：
- 橘鸦 AI 早报：https://daily.juya.uk/rss.xml
- GoodCase.ai：https://goodcase.ai/feed.xml

采集器会提取标题、摘要、原始链接、发布时间、图片、作者和分类。GoodCase 还会把 RSS 中的 Prompt 预览单独拆出来。

RSS 拉取失败时保留上次缓存，不会清空历史。某些站点会因网络线路或反爬策略出现临时连接失败，状态页会区分本次失败与已有缓存。

### GoodCase 公共 API

GoodCase 另提供无需 API Key 的公开 API，支持按分类和关键词检索案例，并提供完整 Prompt、原始来源、热度和复测字段。当前工作台先使用 RSS 作为轻量静态预览；后续可按需接入 API 搜索和案例详情。

接口文档：https://goodcase.ai/connect

### GitHub Awesome 仓库

GitHub API 每日同步精选仓库的元数据：
- LearnPrompt/awesome-seedance
- ai-boost/awesome-image-video-prompts
- cclank/lanshu-awesome-ai-video-kit
- ZeroLu/awesome-seedance
- LichAmnesia/awesome-ad-video-prompts
- ZeroLu/awesome-nanobanana-pro
- UnderleveledBuilder/awesome-short-drama-skills

**不自动克隆整个仓库，也不默认复制仓库中的全部 Prompt。** 工作台只建立索引、显示仓库元数据和原始链接。若未来需要把具体 Prompt 导入个人库，先检查对应文件的 License、作者署名和内容来源。不同仓库的许可证并不相同。

## 自动更新

GitHub Actions 在 `main` 分支推送时发布，并每日按北京时间 **08:00、10:00** 刷新可自动采集的数据。V4 页面直接作为网站首页；旧首页留在 `archive/` 以便回溯。
1. **08:00** 更新官方模型发布与模型库、榜单快照、AIHOT 精选、新模型线索；再从模型目录生成近 30 天发布视图、同步跨模块模型关联并验证引用；将官方模型更新并入厂商发展史，并检查模型卡、API、演示和教程链接。
2. **10:00** 更新 RSS / Atom 订阅、精选 GitHub 仓库元数据和橘鸦 AI 早报。
3. AIHOT 日报在 **08:00** 更新；其余资讯源依各自公开 Feed 与采集时间运行。
4. 搜狗微信只保存搜索结果标题、摘要、账号和日期，不读取文章全文；遇到验证即停止并退避。
5. 保留上次成功缓存；单一信源失败不会覆盖其他来源的数据，也不会把失败时间写成成功更新时间。
6. 公司历史中的自动新增节点仅取厂商一手来源，明确标记为“待复核”；人工核验记录不会被采集器覆盖。
7. 模型资料链接每日检查；受限、限流或网络失败的页面标为“无法确认”，不误报成失效。
8. 官方账号的账号归属和粉丝数仍是人工公开主页快照，页面显示实际快照日期；不会伪装成每日采集。
9. 只有 `main` 分支会发布 GitHub Pages；功能分支手动运行只更新该分支，不发布生产站点。

### 数据准确性边界

- 采集优先使用厂商官方页面、官方 RSS / API、官方代码仓库或榜单发布方的原始数据，并尽量保留可回查的原始链接。
- 行业资讯采用来源等级、同事件归并和重复内容去重；摘要与来源等级用于帮助筛选，不代表本站对内容真实性作了独立背书。方法参考 [AIHOT 开源项目](https://github.com/KKKKhazix/AIHOT)，不复用其品牌或将其数据当作本站事实。
- 自动写入厂商发展史的模型事件会标注“待复核”；人工整理内容不会被自动采集覆盖。来源没有明确证据时，不自动补齐发布日期、能力结论或模型版本。
- 榜单保留各自的评测来源、样本范围和更新时间；不同榜单不混成同一套绝对分数。非官方推断、账号粉丝数等无法可靠自动更新的数据，仍显示其快照日期或待核验状态。
- 每日更新表示“在来源可访问时刷新公开快照”，不保证上游每天发布新内容，也不代表所有字段都是实时数据。社交账号粉丝数仍为人工快照。

工作流文件：.github/workflows/update-site.yml

## 个人数据与隐私

- 预置模型、教程、平台、订阅源和 Awesome 资源目录随静态网站发布。
- 你在网页编辑模式新增的模型、提示词、图片、平台和收藏保存在当前浏览器 localStorage。
- 个人新增内容不会自动写入 GitHub 仓库，也不会自动上传到服务器。
- 建议定期在“偏好设置”导出个人配置备份。
- 本项目不调用 GPT、Claude、Gemini 等大模型 API，不消耗模型 Token。

## 本地运行

要求 Python 3.10+，不需要第三方 Python 依赖：

    python3 -m unittest discover -s tests -v
    python3 scripts/collect_models.py --dry-run
    python3 scripts/collect_resources.py
    python3 scripts/collect_rankings.py --dry-run
    python3 scripts/collect_maomu_rankings.py --dry-run
    python3 scripts/collect_aihot.py
    python3 scripts/collect_aipick.py
    python3 scripts/collect_model_evaluations.py
    python3 scripts/build_model_release_digest.py
    python3 scripts/link_model_records.py
    python3 scripts/validate_model_links.py
    python3 scripts/serve_local.py --port 8080

启动命令会自动打开 AI视频创作台；如果服务已经运行，再次启动会直接打开现有页面。也可以在 macOS Finder 中双击项目根目录的启动命令。直接双击 HTML 时，若本机服务已运行会自动跳转；若服务未运行，请先启动本机服务。

本机预览页面与 JSON 响应均禁用浏览器缓存，刷新时会读取磁盘上的最新文件。AIHOT 榜单与主题摘要可由本机代理按需读取；GitHub Pages 显示 GitHub Actions 保存的快照，不依赖本机代理。

## 目录结构

    config/model-sources.json             官方模型监控信源
    config/resource-sources.json          RSS 与 GitHub Awesome 资源配置
    scripts/collect_models.py             官方模型发布采集器
    scripts/collect_resources.py          RSS 与 GitHub 元数据采集器
    scripts/collect_rankings.py            FAI.Fashion 与 Arena 榜单快照采集器
    scripts/collect_maomu_rankings.py      猫目模型榜单公开页面采集器
    scripts/serve_local.py                 本地静态网站与 AIHOT 榜单只读代理
    scripts/collect_aihot.py               AIHOT 精选动态采集与本地快照更新
    scripts/collect_aipick.py              AIPick 视频选题与热点采集器
    scripts/collect_model_evaluations.py   新模型评测候选采集器（AIPick + 搜狗微信摘要）
    scripts/build_model_release_digest.py  从模型目录生成近 30 天正式发布视图
    scripts/link_model_records.py          为其他模块生成可核实的模型关联
    scripts/validate_model_links.py         校验模型引用、发布证据与兼容副本
    site/index.html                       AI视频创作台发布首页
    site/preview-v2.html                  V2 预览页面（读取 site/data-v2/）
    site/preview-v3.html                  V3 预览页面（保留基线，读取 site/data-v3/）
    site/preview-v4.html                  V4 工作台源页面
    site/data/models.json                 模型家族、版本及官方发布证据权威目录
    site/data/model-updates.json          模型发布历史
    site/data/model-monitor-status.json   模型信源状态
    site/data/reference-rankings.json     生产页读取的外部榜单快照
    site/data/feed-items.json             RSS 内容缓存
    site/data/resource-sources.json       浏览器展示的订阅源目录
    site/data/resource-status.json        RSS / GitHub 同步状态
    site/data/awesome-repos.json           Awesome 仓库元数据
    site/data/prompts.json                个人初始提示词模板
    site/data/tutorials.json              官方教程和 Skill
    site/data-v4/model-practice.json       V4 官方模型演示案例与体验 / API 入口
    site/data-v4/platforms.json            常用创作平台
    site/data-v4/model-releases-30d.json   从权威目录生成的近 30 天发布视图
    site/data-v2/                         V2 预览专用静态数据
    site/data-v3/                         V3 基础静态数据（模型、榜单、主题与早报）
    site/data-v3/reference-rankings.json  V3 / V4 共用的外部榜单快照
    site/data-v4/social-accounts.json      官方社媒账号、公开粉丝快照与宣传动态
    site/data-v4/aihot-items.json          AIHOT 最近 24 小时精选动态快照
    site/data-v4/maomu-rankings.json       猫目四类模型榜单及各来源子榜数据
    site/data-v4/aipick-data.json          AIPick 最近 7 天选题与热点快照
    site/data-v4/model-evaluations.json   近期视频 / 图像模型评测候选快照
    site/data-v4/platforms.json            V4 创作导航（含国内外社交媒体分类）
    tests/                                采集器单元测试
    archive/legacy-news/                  旧版泛资讯数据，仅供回滚参考
    archive/follow-builders/               已退役信源说明与最后一份采集快照

## 当前页面与数据范围

- `site/index.html` 与 `site/preview-v4.html` 是同一工作台页面；GitHub Actions 发布前会将 V4 源页面复制到首页。
- 页面基础数据沿用 `site/data-v3/`，社媒账号、创作导航和近 30 天模型上新视图使用 `site/data-v4/`。模型权威目录位于 `site/data/models.json`，`site/data-v3/models.json` 是必须同步的兼容副本；详细约定见 [`docs/model-data-contract.md`](docs/model-data-contract.md)。
- 行业简报、厂商节点、官方社媒动态、创作导航和评测候选只在已核实到目录家族或版本时才链接视频、图像、语言或音乐模型详情；智能体工具不建立模型库关联。具体版本未确认时不猜版本；没有关联表示目前未建立经核实的链接，不代表该模块不存在相关信息。
- 「近 30 天模型上新」是模型权威目录的生成视图，只显示有正式发布日期和完整官方证据的视频、图像及大语言模型新版本；生成规则见 [`docs/model-release-digest-guide.md`](docs/model-release-digest-guide.md)。
- V4 榜单按类别和子榜展示：猫目四类子榜、FAI.Fashion 与 Arena 数据在本地绘制；BenchLM 通过官方嵌入加载，其余无法本地展示的榜单保留原站入口。各榜单保留独立分数口径、来源与更新时间。
- 猫目榜单采集器读取猫目公开页面已渲染的表格，保留猫目标注的来源评分口径、更新时间和子榜；包含语言模型、图片生成、视频生成、多模态理解四类。重复的同机构同名条目在单个子榜内去重，不合并不同评测来源的分数。
- AIHOT 精选已作为 AI 早报中的一个栏目；失败时显示 `site/data-v4/aihot-items.json`。运行 `python3 scripts/collect_aihot.py` 可手动刷新快照。采集参考 AIHOT 开源项目的来源等级、原始出处保留与事件去重方法；本站不调用 AIHOT 的品牌或 Logo。
- 厂商发展史每日并入官方模型更新；新自动节点标记“待复核”，与人工核验的历史记录分开统计。
- 模型资料中的官方链接每日检查可访问状态；检查不会自动改写模型说明或 API 地址。
- “模型上新与宣传”页以厂商正式模型发布为主记录，关联已收录的官方宣传视频；另列模型厂商与模型聚合平台的官方视频原帖。搜索结果和未核验链接不作为视频原帖展示。评测候选采集器及其历史数据仍保留，但不再作为该页面的内容来源。
- 当前社媒监控覆盖 26 个模型厂商与模型聚合平台品牌：即梦 AI、可灵 AI、Higgsfield、MiniMax（海螺 AI）、Vidu、HappyHorse、PixVerse（拍我 AI）、Seko AI、Flova AI、Pollo AI、LibTV、TapNow、YouArt、Krea、Pexo AI、Updream、ShotLab、RunningHub、Renoise、OiiOii、OpenArt、Leonardo.Ai、Adobe Firefly、Google Flow、Pika、Runway。各品牌统一展示抖音、B站、小红书、X、Instagram、TikTok、YouTube、Facebook，共 208 个平台位。国内筛选显示抖音、B站、小红书；海外筛选显示 X、Instagram、TikTok、YouTube、Facebook。没有可确认官方主页的位置显示“暂无”；账号来源、备注、关联主页和其他互动指标可在卡片详情中查看。粉丝 / 订阅数仍为带实际查看日期的人工公开主页快照。
- 粉丝 / 订阅数是人工公开主页快照，不是实时数据；每个账号保留实际快照日期。1 万以上显示“万”，不足 1 万显示原始数值；无账号不记为 0。粉丝数尚未自动采集，也不生成虚假的增长曲线。
- 微博与 LinkedIn 不在当前覆盖范围；已移除或恢复的账号历史保存在 `social-accounts.json` 的 `archive` 字段中。创作导航另含国内外社交媒体与社区入口。

## License

MIT
