# Project Instructions

## Goal

Maintain a personal AI creator radar focused on trustworthy model updates, video and image creation, and useful creator resources. The user should consume information, not perform recurring fact correction, missing-release discovery, or engineering maintenance. P1 data reliability takes precedence; P2 remains frozen until explicitly reopened.

## Directory conventions

- `site/index.html` is the single website entry point; `site/assets/` contains published assets.
- `site/data/` is the single live data directory. Keep the canonical model registry at `site/data/models.json`.
- `archive/` contains read-only historical pages, datasets, research, and completed engineering notes; current code must not depend on archived files.
- `scripts/` contains Python collectors and builders; `tests/` contains their unit tests; `config/` contains source configuration; `.github/workflows/` contains automation.
- Project Skills live under `.agents/skills/<short-name>/`.

## Naming and data rules

- Use stable kebab-case IDs for model and source records.
- Keep public source URLs and model/version facts tied to official vendor pages or official repositories.
- Follow [`docs/model-data-contract.md`](docs/model-data-contract.md) for cross-module IDs, provenance, and generated release views.
- State model-weight access and license limits per specific model; do not generalize a family's license.
- Preserve user-authored data and existing uncommitted changes. Do not commit temporary files, caches, credentials, or personal configuration.
- Before collecting or editing social account snapshots, read [`docs/social-monitor-data-guide.md`](docs/social-monitor-data-guide.md); it defines the rules for `site/data/social-accounts.json`.

## Verification

- GitHub is the canonical engineering and validation environment. A local clone and its pre-push hook remain useful but are not prerequisites for GitHub-only maintenance. The Mac's 21:00 local collection task is a separate input; do not require Desktop Commander or an always-online Mac for cloud collection, engineering validation, or publication.
- For a local Git push, required offline gate: `python3 scripts/preflight.py` before pushing. For API-based changes, batch-reviewed changes into an isolated PR branch; require the exact revision's full GitHub validation and Chromium/WebKit checks before merging. Never write unvalidated engineering changes directly to main. A failed candidate remains isolated; do not repeatedly push speculative fixes as a substitute for diagnosis. If canonical input or digest logic changed, run `python3 scripts/preflight.py --repair-digest`, review the generated diff and commit all related files atomically. A consistent snapshot must not have its window or timestamp rewritten just to pass checks.
- Install the repository pre-push hook once per clone (`python3 scripts/preflight.py --install-hook`), with actionlint on PATH. The hook checks the exact commit rather than uncommitted local files. API-based writers bypass local hooks and must validate their complete candidate tree using the GitHub PR checks when local execution is unavailable; distinguish pre-merge checks from actual production collection. Do not bypass the hook to force an invalid push.

- Validate edited JSON with `python3 -m json.tool <file>`.
- Run `python3 -m unittest discover -s tests -v` for collector or data-path changes.
- Run `python3 scripts/collect_models.py --dry-run` to inspect official model-source collection without writing data.
- After model collection, run `python3 scripts/build_model_release_digest.py`, `python3 scripts/link_model_records.py`, and `python3 scripts/validate_model_links.py` to regenerate the 30-day view and verify shared references.

- For UI changes, use the four primary categories in this order: video, image, llm, audio; keep contextual audio subcategories and canonical source category values separate. Formal-release counts exclude service stages and pending records. Keep tutorials and cases last in navigation.
- Before merging, require the applicable Python and Node suites, reference checks, and both browser engines on the exact candidate revision. Batch coherent changes into one PR commit where practical. Use GitHub logs and artifacts for failure diagnosis; never suppress real failures or disable notification workflows. Report the actual execution environment and distinguish passed, skipped, and pending checks.
- Test date-dependent rendering against controlled time or the actual snapshot; legitimate empty states must not fail.
- Update README, DESIGN and affected guides together. Archive superseded documentation verbatim; remove only proven unused code/assets. Preserve compatibility routes, source datasets and evidence.
- Before changing collection schedules, follow [`docs/automation-runbook.md`](docs/automation-runbook.md); preserve actual snapshot timestamps and test missed-run recovery.
- For UI changes, follow [`DESIGN.md`](DESIGN.md) and verify both Chromium and WebKit responsive layouts.

## Cleanup

- Do not delete user-authored or historical data. Move confirmed retired material into `archive/` and keep a short explanation of its status.
- Keep generated caches and local settings out of Git.

## Production operations

- GitHub Actions is the only production data writer. Cloudflare Worker `ai-creator-radar` is the deployed independent watchdog, configured in `ops/cloudflare-watchdog/wrangler.toml`; keep the 15-minute cadence and do not edit dashboard schedules independently. The GitHub token belongs only in a runtime Secret. Rotate it before expiry; never log or commit it.
- Treat PR validation, cloud deployment, actual dispatch, persisted heartbeat and live Pages publication as separate gates. Record raw overdue state separately from retry eligibility. Do not hide a stale group or reduce real incident reporting to make checks green.
- Run `node --test tests/test_overview.mjs tests/test_scheduler_worker.mjs tests/test_deploy_verified_pages.cjs` and the Python suite for scheduler changes; a Node mock is not a Cloudflare runtime acceptance test. Do not enable both independent fallback schedulers simultaneously. Main protection and local hook installation must be verified separately; preserve the validated automated data-writer path.

- Keep retired broad-news code/config/tests under the historical archive, not the active collector directories. Run the repository hygiene tests with the normal Python suite; validate current documentation links and do not revive obsolete data outputs.

- P1 event reconciliation is a shadow layer: preserve historical evidence and real original verification times; distinguish article, lifecycle and canonical release facts. Related leads only prioritize existing probes; never invent a source or promote a reported date. Keep fixed benchmark metrics unchanged. See docs/model-data-contract.md.


## Source strategy

- Optimize effective event coverage, not HTTP success or source count. When an endpoint is denied, empty or repeatedly unproductive, prefer genuinely independent permitted alternatives and reuse existing aggregated clues before writing new scrapers.
- Use AIHOT and other aggregators for discovery, not canonical release truth. Respect their published access and reuse rules; do not mirror or bulk redistribute. Prefer targeted queries, original publisher links, conditional requests and bounded retry; independently validate model identity, date and stage.
- Before adding a collector or audit layer, compare a configuration change, a reused adapter, and simpler cross-domain approaches. Measure unique verified contribution, latency and request/maintenance cost; remove only demonstrably redundant routes, preserve evidence and negative controls. Do not repeatedly repair one blocked URL when an equivalent publisher source works.

- Prefer AIHOT for model/industry discovery, AIPick for creator-oriented complementary discovery, and Juya or direct official sources for gaps. Shared framework or a repeated original URL never constitutes an independent confirmation. Reuse one adapter and shared budget rather than duplicate collectors. Free public reading APIs do not authorize wholesale public redistribution; keep new aggregator use bounded to original links and separately verified facts.

- Prioritize AI product design and video creation intelligence for aggregation competitors: model integration, feature and workflow changes, new product forms and creative capabilities; exclude price/credit/discount-only updates. Use first-party changelogs and New drops as direct sources, not only social coverage; distinguish upstream vendor model releases from downstream platform adoption. Reuse AIHOT and AIPick as primary discovery; preserve original story links and independent provider ranks, do not equate discussion metrics or editorial picks with post views. Keep creator news separate from canonical model facts; no bulk public mirror without permission.

- Extend first-party product sources through the shared app-update adapter and configured brand roles. A navigation-only source or stale changelog is a coverage gap, not successful monitoring. Preserve original calendar days, first observations, distinct model integration and product update types; avoid duplicate data stores and new scheduling groups.

- Prefer AIHOT + AIPick selected information first for competitor research; run direct changelog probes only for observed coverage gaps, preserve existing evidence and separate feature versus model-integration signals. A brand mention or a positive sample is not proof of exhaustive coverage. Avoid duplicate crawling and prioritize product design relevance over raw source volume.

- Prioritize unattempted monitored brand/provider pairs with bounded independent request budgets. Personal direct-browser selected reading is not a public data mirror or proxy; verify real CORS, keep fallback links and never certify unsupported providers.
