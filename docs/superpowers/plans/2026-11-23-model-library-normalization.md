# 模型库结构与榜单排序 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一模型库为厂商、模型家族、结构化版本三层，并让用户按一个具体评测子榜查看排序。

**Architecture:** `models.json` 保留一个可搜索的模型家族记录，版本与变体放入 `versions[]`，旧型号 ID 与各榜原始型号名均保留在版本映射中。V4 页面按家族显示版本清单，通过独立榜单选择器读取本地猫目、FAI/Arena 数据；排序只使用被选中的单一 `boardId`。

**Tech Stack:** 静态 HTML/CSS/JavaScript、JSON、Python unittest。

**Spec:** `docs/superpowers/specs/2026-11-23-model-library-normalization.md`

## Global Constraints

- 旧记录 ID 必须迁入某个 `versions[].legacyIds`，不可因家族合并丢失采集器、更新历史或模型评测的引用。
- 排名必须绑定一个具体 `boardId`；不跨评测机构、任务或分数口径合并。
- 许可、权重开放和预览状态按版本记录，不从一个版本推广到整个家族。
- 维持现有地区、许可筛选与 V4 本地预览入口；禁止推送、部署或改 CI。

## Review Focus

- 不同任务混入同一模型家族 → 测试 Kling 视频/图像和 MiniMax H3/Hailuo 保持分开。
- 家族合并丢失旧 modelId → 测试每个旧 ID 均出现在版本的 `legacyIds`。
- 子榜名称不一致导致错序 → 用精确 `leaderboardAliases` 匹配，并测试未匹配者置后。
- 榜单分数跨任务不可比较 → 测试切换 `boardId` 后只使用该榜原始名次。
- 采集器覆盖结构化版本 → 测试发布采集同时更新家族当前版本与 `versions[]`。

---

### Task 1: 核验和映射模型家族

**Files:**
- Modify: `site/data-v3/models.json`
- Modify: `site/data/models.json`
- Test: `tests/test_model_library.py`

**Interfaces:**
- Family fields: `id`, `name`, `vendor`, `category`, `versions`, `aliases`, `watched`.
- Version fields: `id`, `name`, `legacyIds`, `leaderboardAliases`, `status`, `releaseDate`, `access`, `accessNote`, `homepage`, `releaseUrl`, `modelCardUrl`, `note`.

- [x] Add schema tests for family uniqueness, non-empty versions, legacy ID preservation, category-specific separation, and required user-named model families.
- [x] Run the schema tests and confirm they fail against the current flat data.
- [x] Normalize 86 legacy model records into vendor families and structured versions; preserve every original record ID.
- [x] Add audited versions and correct family/category errors found in four specialist review rounds.
- [x] Copy the normalized V3 model data to `site/data/models.json` so collectors keep both datasets aligned.
- [x] Run schema tests and JSON validation for both files.

### Task 2: Keep automated collection compatible

**Files:**
- Modify: `scripts/collect_models.py`
- Test: `tests/test_model_collector.py`

**Interfaces:**
- `apply_recent_model_versions(models, items, now)` continues receiving models indexed by stable family `id`.
- A dated collected update appends or refreshes one matching structured version while preserving other family versions.

- [x] Add a regression test showing collected version announcements do not overwrite family history.
- [x] Update collector mutation to maintain `version` compatibility summary and structured `versions[]` record.
- [x] Run collector tests and `python3 scripts/collect_models.py --dry-run`.

### Task 3: Render family cards and board-specific order

**Files:**
- Modify: `site/preview-v4.html`
- Test: `tests/test_model_library.py`

**Interfaces:**
- Model page renders one card per family and a compact list of the family’s versions/variants.
- Ranking selector stores a concrete board ID; each family receives the best rank among its exact version aliases on that board.

- [x] Add schema/mapping assertions for exact rank rows and verify board-switch ordering in the local browser.
- [x] Add a board selector populated from Maomu, reference, and relevant Arena subboards.
- [x] Render the selected board and each version’s exact rank or a clear no-ranking label.
- [x] Keep region/access filters, search, and existing model details usable.
- [x] Run all unit tests, validate JSON, and check inline JavaScript syntax.

### Task 4: Three-round cross-check and browser acceptance

**Files:**
- Review: `site/data-v3/models.json`, `site/data/models.json`, `site/preview-v4.html`

**Interfaces:**
- Specialist reviewers cover video, image, and audio/TTS; primary agent checks LLM, Agent families, and ranking mappings.

- [x] Round 1: module experts compare normalized records and added versions against official releases and independent sources.
- [x] Round 2: agents cross-check family boundaries, variants, and ranking aliases; resolve disagreements with source evidence.
- [x] Round 3: run schema/collector tests and browser-check video, image, and audio categories plus an image-board switch; a fourth cross-check round resolved further exact-row mismatches.
- [x] Record unresolved source/date and no-ranking cases as pending/explicitly unranked rather than guessing.
