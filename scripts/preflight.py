#!/usr/bin/env python3
"""Offline validation and deterministic repair of the derived release view."""
from __future__ import annotations

import argparse
import ast
from datetime import date
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DIGEST = Path('site/data/model-releases-30d.json')


def sync_digest(path, build, repair=False):
    """Use the stored window; never advance freshness just to pass a test."""
    actual = json.loads(path.read_text(encoding='utf-8'))
    expected = build(date.fromisoformat(actual['windowEnd']))
    def semantic(doc):
        return {k: v for k, v in doc.items() if k != 'updatedAt'}
    if semantic(actual) == semantic(expected):
        return False
    if not repair:
        raise ValueError('Release digest is stale; run python3 scripts/preflight.py --repair-digest')
    # Keep the old file intact if serializing or replacing the new file fails.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            json.dump(expected, file, ensure_ascii=False, indent=2)
            file.write('\n')
            file.flush()
            os.fchmod(file.fileno(), path.stat().st_mode & 0o777)
            file.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return True


def run(*args):
    print('+', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(args), cwd=ROOT, check=True)


def static_checks():
    for directory in ('scripts', 'tests'):
        for path in sorted((ROOT / directory).rglob('*.py')):
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    for directory in ('config', 'site/data'):
        for path in sorted((ROOT / directory).rglob('*.json')):
            json.loads(path.read_text(encoding='utf-8'))
    lint = shutil.which('actionlint')
    if not lint:
        raise ValueError('actionlint is required; install it before pushing (see docs/automation-runbook.md)')
    workflows = sorted((ROOT / '.github/workflows').glob('*.y*ml'))
    run(lint, '-shellcheck=', '-pyflakes=', *map(str, workflows))
    for path in sorted((ROOT / 'scripts').glob('*.sh')) + [ROOT / '.githooks/pre-push']:
        run('bash', '-n', str(path))


def install_hook():
    current = subprocess.run(['git', 'config', '--get', 'core.hooksPath'], cwd=ROOT, capture_output=True, text=True)
    if current.returncode not in (0, 1):
        raise ValueError('Cannot inspect existing Git hook settings')
    if current.returncode == 0 and current.stdout.strip() != '.githooks':
        raise ValueError('Existing core.hooksPath retained; integrate .githooks/pre-push manually')
    # Do not silently replace an existing default custom hook.
    if current.returncode == 1:
        hooks = subprocess.check_output(['git', 'rev-parse', '--git-path', 'hooks'], cwd=ROOT, text=True).strip()
        if any(p.is_file() and not p.name.endswith('.sample') for p in (ROOT / hooks).glob('*')):
            raise ValueError('Existing Git hooks retained; integrate .githooks/pre-push manually')
    run('git', 'config', '--local', 'core.hooksPath', '.githooks')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repair-digest', action='store_true')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--digest-only', action='store_true')
    mode.add_argument('--static-only', action='store_true')
    mode.add_argument('--install-hook', action='store_true')
    args = parser.parse_args()
    if args.install_hook:
        if args.repair_digest:
            parser.error('--install-hook cannot repair data')
        install_hook()
        return 0
    if not args.digest_only:
        static_checks()
    from build_model_release_digest import build
    changed = sync_digest(ROOT / DIGEST, build, args.repair_digest)
    print('Release digest: rebuilt' if changed else 'Release digest: consistent')
    if not (args.digest_only or args.static_only):
        run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v')
        run('node', '--test', 'tests/test_overview.mjs', 'tests/test_scheduler_worker.mjs', 'tests/test_deploy_verified_pages.cjs')
        for script in ('validate_model_links', 'audit_model_completeness', 'audit_radar_system'):
            run(sys.executable, f'scripts/{script}.py')
        for script in ('check_creator_links', 'collect_creator_opportunities'):
            run(sys.executable, f'scripts/{script}.py', '--dry-run')
        with tempfile.TemporaryDirectory() as directory:
            run(sys.executable, 'scripts/plan_refresh.py', '--event', 'schedule', '--output', str(Path(directory) / 'plan.txt'))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError) as exc:
        print(f'Preflight failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
