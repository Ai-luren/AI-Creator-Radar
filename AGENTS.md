# Project Instructions

## Goal

Maintain a personal AI creator radar focused on trustworthy model updates, video and image creation, and useful creator resources.

## Directory conventions

- `site/` contains the static website and its published assets.
- `site/data/` contains the production site's current data.
- `site/data-v2/` and `site/data-v3/` preserve versioned preview datasets; do not remove historical records during routine updates.
- `scripts/` contains Python collectors; `tests/` contains their unit tests.
- `config/` contains source configuration; `.github/workflows/` contains automation.

## Naming and data rules

- Use stable kebab-case IDs for model and source records.
- Keep public source URLs and model/version facts tied to official vendor pages or official repositories.
- State model-weight access and license limits per specific model; do not generalize a family's license.
- Preserve user-authored data and existing uncommitted changes. Do not commit temporary files, caches, credentials, or personal configuration.

## Social account monitoring

- Before collecting or editing social account snapshots, read [`docs/social-monitor-data-guide.md`](docs/social-monitor-data-guide.md). It defines the account verification, platform coverage, follower count, timestamp, and missing-data rules for `site/data-v4/social-accounts.json`.
- Treat follower counts as manual public-profile snapshots unless a reviewed collector is explicitly implemented; do not imply that this dataset refreshes automatically.

## Verification

- Validate edited JSON with `python3 -m json.tool <file>`.
- Run `python3 -m unittest discover -s tests -v` for collector changes.
- Run `python3 scripts/collect_models.py --dry-run` to inspect official model-source collection without writing data.

## Cleanup

- Do not delete user or historical data as cleanup. Move only confirmed legacy material into the existing archive structure when explicitly needed.
- Keep generated caches and local settings out of Git.
