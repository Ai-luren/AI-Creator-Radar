"""Classify changed paths without fragile shell regular expressions."""
import os
from pathlib import PurePosixPath
import subprocess

MODEL_FILES = {'model-sources', 'cross-platform-sources', 'release-recall-benchmark', 'chronicle-release-links', 'product-state-sources', 'independent-audit-sources'}
MODEL_SCRIPTS = {'collect_models', 'collect_cross_platform', 'collect_resolve_model_leads', 'collect_release_recall', 'collect_verify_model_releases', 'collect_model_intake', 'collect_chronicle_updates', 'build_model_release_digest', 'collect_event_reconciliation', 'event_identity', 'collect_product_state', 'collect_source_search', 'collect_event_claims', 'collect_independent_audit'}


def scopes(paths):
    paths = set(map(PurePosixPath, paths))
    return {
        'models': any(p.parent == PurePosixPath('config') and p.suffix == '.json' and p.stem in MODEL_FILES or p.parent == PurePosixPath('scripts') and p.suffix == '.py' and p.stem in MODEL_SCRIPTS for p in paths),
        'opportunities': bool(paths & {PurePosixPath('config/creator-opportunity-sources.json'), PurePosixPath('scripts/collect_creator_opportunities.py')}),
    }


def main():
    changed = subprocess.check_output(['git', 'diff', '--name-only', '-z', 'HEAD^1', 'HEAD']).decode('utf-8', errors='surrogateescape').split('\0')
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as out:
        for key, value in scopes(changed).items():
            print(f'{key}={str(value).lower()}', file=out)


if __name__ == '__main__':
    main()
