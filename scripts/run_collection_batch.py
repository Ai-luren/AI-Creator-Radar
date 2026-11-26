"""Run dependent collectors transactionally; independent transactions survive failures."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCHES = {
    "models": (420, (("collect_models", "collect_verify_model_releases", "build_model_release_digest", "collect_chronicle_updates", "collect_release_recall"),)),
    "resources": (540, (("collect_resources",), ("collect_rankings", "collect_maomu_rankings", "build_unified_rankings"), ("collect_aipick",), ("collect_social_trends",))),
    "maintenance": (540, (("check_model_resources",), ("check_creator_links",), ("collect_creator_opportunities",), ("collect_model_evaluations",))),
}
BASELINE = Path("config/unified-ranking-baseline.json")


def run_batch(root, transactions, seconds, runner=subprocess.run, clock=time.monotonic):
    """Restore a failed transaction before proceeding; never commit partial writes."""
    data = root / "site/data"
    baseline = root / BASELINE
    deadline = clock() + seconds
    failures = []
    for transaction in transactions:
        name = "+".join(transaction)
        if deadline <= clock():
            failures.append(name)
            print(f"::warning::Collection time budget exhausted before {name}")
            continue
        with tempfile.TemporaryDirectory(prefix="radar-transaction-") as temp:
            backup = Path(temp) / "data"
            shutil.copytree(data, backup)
            old_baseline = baseline.read_bytes() if baseline.exists() else None
            try:
                for script in transaction:
                    remaining = deadline - clock()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(script, seconds)
                    runner([sys.executable, str(root / "scripts" / (script + ".py"))],
                           cwd=root, check=True, timeout=remaining)
                for file in data.rglob("*.json"):
                    current = json.loads(file.read_text(encoding="utf-8"))
                    previous = backup / file.relative_to(data)
                    if previous.exists():
                        old = json.loads(previous.read_text(encoding="utf-8"))
                        if type(current) is not type(old):
                            raise ValueError(f"snapshot root type changed: {file.name}")
                        if isinstance(old, dict):
                            for field in ("items", "boards", "categories", "sources"):
                                if isinstance(old.get(field), list) and not isinstance(current.get(field), list):
                                    raise ValueError(f"snapshot array missing: {file.name}/{field}")
                missing = [p.relative_to(backup) for p in backup.rglob("*.json")
                           if not (data / p.relative_to(backup)).is_file()]
                if missing:
                    raise ValueError(f"snapshot files disappeared: {missing}")
            except (subprocess.SubprocessError, OSError, ValueError) as exc:
                # A rollback failure is a genuine fatal error, not an optional outage.
                shutil.rmtree(data)
                shutil.copytree(backup, data)
                if old_baseline is not None:
                    baseline.write_bytes(old_baseline)
                elif baseline.exists():
                    baseline.unlink()
                failures.append(name)
                print(f"::warning::Rolled back {name}: {type(exc).__name__}: {exc}")
            else:
                print(f"Committed transaction in working tree: {name}")
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("group", choices=BATCHES)
    args = parser.parse_args()
    seconds, transactions = BATCHES[args.group]
    try:
        failures = run_batch(ROOT, transactions, seconds)
    except Exception:
        # A failed rollback or unexpected orchestration exception must block persistence.
        (ROOT / ".radar-collection-fatal").touch()
        raise
    if args.group == "models" and not failures:
        try:
            status = json.loads((ROOT / "site/data/model-monitor-status.json").read_text())
            if status.get("totalSources", 0) and not status.get("successSources", 0):
                # The collector retained the previous data. Preserve the new incident metadata.
                failures.append("all official model sources failed")
        except Exception:
            (ROOT / ".radar-collection-fatal").touch()
            raise
    print("Collection batch failures:", failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
