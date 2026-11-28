#!/usr/bin/env python3
"""Run independent existing snapshot gates concurrently, without changing their criteria."""
from __future__ import annotations

import concurrent.futures
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate(root=ROOT, runner=subprocess.run, clock=time.monotonic):
    """Keep rendering and data-audit readers isolated from Python test fixtures."""
    root = Path(root)
    started = clock()
    with tempfile.TemporaryDirectory(prefix="radar-validation-") as directory:
        frozen = Path(directory)
        for name in ("site", "config", "scripts"):
            shutil.copytree(root / name, frozen / name, ignore=shutil.ignore_patterns("__pycache__"))
        (frozen / "tests").mkdir()
        shutil.copy2(root / "tests/test_overview.mjs", frozen / "tests/test_overview.mjs")
        lanes = (
            ("collector-tests", root, [(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")]),
            ("render-and-evidence", frozen, [
                ("node", "--test", "tests/test_overview.mjs"),
                (sys.executable, "scripts/validate_model_links.py"),
                (sys.executable, "scripts/audit_model_completeness.py"),
            ]),
        )

        def run_lane(lane):
            name, cwd, commands = lane
            begin = clock()
            results = []
            for command in commands:
                try:
                    result = runner(command, cwd=cwd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, errors="replace",
                                    timeout=180, check=False)
                    results.append((command, result.returncode, result.stdout or ""))
                except (OSError, subprocess.SubprocessError) as exc:
                    results.append((command, 1, str(exc)))
            return name, round(clock()-begin, 3), results

        # No collector or production writer runs inside either lane.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run_lane, lanes))
        failed = False
        for name, duration, commands in results:
            print(f"Validation lane: {name} {duration:.3f}s", flush=True)
            for command, code, output in commands:
                print("+", " ".join(command), flush=True)
                print(output, end="" if output.endswith("\n") else "\n", flush=True)
                if code:
                    failed = True
                    print(f"::error::Validation gate failed: {name}: exit {code}", flush=True)
        print(f"Snapshot validation wall: {clock()-started:.3f}s", flush=True)
        return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(validate())
