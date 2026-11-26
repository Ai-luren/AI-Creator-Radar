# Project Instructions

## Goal

Maintain a personal AI creator radar focused on trustworthy model updates, video and image creation, and useful creator resources.

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

- Required offline gate: `python3 scripts/preflight.py` before pushing. If canonical input or digest logic changed, run `python3 scripts/preflight.py --repair-digest`, review the generated diff and commit all related files atomically. A consistent snapshot must not have its window or timestamp rewritten just to pass checks.
- Install the repository pre-push hook once per clone (`python3 scripts/preflight.py --install-hook`), with actionlint on PATH. The hook checks the exact commit rather than uncommitted local files. API-based writers bypass local hooks and must validate their complete staged tree independently; never use remote CI for repeated patch debugging. Do not bypass the hook to force an invalid push.

- Validate edited JSON with `python3 -m json.tool <file>`.
- Run `python3 -m unittest discover -s tests -v` for collector or data-path changes.
- Run `python3 scripts/collect_models.py --dry-run` to inspect official model-source collection without writing data.
- After model collection, run `python3 scripts/build_model_release_digest.py`, `python3 scripts/link_model_records.py`, and `python3 scripts/validate_model_links.py` to regenerate the 30-day view and verify shared references.

- For UI changes, use the four primary categories in this order: video, image, llm, audio; keep contextual audio subcategories and canonical source category values separate. Formal-release counts exclude service stages and pending records. Keep tutorials and cases last in navigation.
- Before pushing, run the applicable Python and Node suites, reference checks, and both browser engines. Batch verified changes into one commit; never use remote CI as an iterative debugger. Do not suppress real failures or disable notification workflows. If local verification is unavailable, state the limitation and do not claim it passed.
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
- Run `node --test tests/test_overview.mjs tests/test_scheduler_worker.mjs` and the Python suite for scheduler changes; a Node mock is not a Cloudflare runtime acceptance test. Do not enable both independent fallback schedulers simultaneously. Main protection and local hook installation must be verified separately; preserve the validated automated data-writer path.
