# AI Creator Workbench

个人 AI 创作工作台：把模型上新、AI 早报、真实创作案例、开源 Prompt 仓库、自己的提示词和教程入口放在一个地方。

核心原则：**优先复用已经存在的优质数据源，不重复建设新闻库和 Prompt 大全。**

## 工作台模块

- **模型动态 / 模型库**：关注常用视频、图片、语言和音乐模型；自动检查官方版本发布。
- **AI 早报**：订阅公开 RSS，当前接入橘鸦 AI 早报；展示摘要、发布时间和原文链接。
- **创作案例**：接入 GoodCase.ai RSS，展示案例封面、作者、摘要和 Prompt 预览；完整内容回到原站。
- **Awesome 资源**：通过 GitHub API 同步精选开源仓库的描述、Star、Fork、更新时间和许可证。
- **我的提示词**：人物设定、人物三视图、场景母图、多机位、分镜、单镜头视频、TVC、Seedance 2.5 结构化 Prompt。
- **教程与 Skill**：优先保存模型厂商和平台官方指南、工作流与可安装 Skill。
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

GitHub Actions 每天北京时间 **08:20** 运行：
1. 检查官方模型版本发布。
2. 拉取 RSS / Atom 订阅。
3. 同步精选 GitHub 仓库元数据。
4. 保留上次成功缓存；单一信源失败不会覆盖其他来源的数据。
5. 更新静态数据后部署 GitHub Pages。

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
    python3 -m http.server 8080 --directory site

打开 http://localhost:8080 预览。

## 目录结构

    config/model-sources.json             官方模型监控信源
    config/resource-sources.json          RSS 与 GitHub Awesome 资源配置
    scripts/collect_models.py             官方模型发布采集器
    scripts/collect_resources.py          RSS 与 GitHub 元数据采集器
    site/index.html                       个人 AI 创作工作台
    site/preview-v2.html                  V2 预览页面（读取 site/data-v2/）
    site/preview-v3.html                  V3 预览页面（读取 site/data-v3/）
    site/data/models.json                 模型目录
    site/data/model-updates.json          模型发布历史
    site/data/model-monitor-status.json   模型信源状态
    site/data/feed-items.json             RSS 内容缓存
    site/data/resource-sources.json       浏览器展示的订阅源目录
    site/data/resource-status.json        RSS / GitHub 同步状态
    site/data/awesome-repos.json           Awesome 仓库元数据
    site/data/prompts.json                个人初始提示词模板
    site/data/tutorials.json              官方教程和 Skill
    site/data/platforms.json              常用创作平台
    site/data-v2/                         V2 预览专用静态数据
    site/data-v3/                         V3 预览专用静态数据（当前预览版本）
    tests/                                采集器单元测试
    archive/legacy-news/                  旧版泛资讯数据，仅供回滚参考

## License

MIT
