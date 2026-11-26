"""Independent, read-only-until-due watchdog for a machine with an authorized gh CLI.

Never stores a token, writes data, forces a push, or queues duplicate active runs.
Run every 15 minutes from an external scheduler, not from the GitHub Actions cron.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from scripts.plan_refresh import GROUPS, plan
except ModuleNotFoundError:
    from plan_refresh import GROUPS, plan

REPO = "Ai-luren/AI-Creator-Radar"
WORKFLOW = "update-site.yml"
COOLDOWN = timedelta(minutes=40)


def check(gh, repo, now, dry_run=False, invoke=subprocess.run):
    def api(endpoint, raw=False):
        args = [gh, "api"]
        if raw:
            args += ["-H", "Accept: application/vnd.github.raw+json"]
        return invoke(args + [endpoint], check=True, capture_output=True, text=True, timeout=35).stdout

    runs = json.loads(api(f"repos/{repo}/actions/workflows/{WORKFLOW}/runs?branch=main&per_page=20"))["workflow_runs"]
    if any(run["status"] != "completed" for run in runs):
        return "active-run"
    if runs:
        newest = max(datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")) for run in runs)
        if now - newest < COOLDOWN:
            return "cooldown"
    with tempfile.TemporaryDirectory(prefix="radar-watchdog-") as directory:
        data = Path(directory)
        files = sorted({name for inputs in GROUPS.values() for name, _ in inputs} | {"collection-health.json"})
        # Pin all reads to the same main commit. No mixed snapshot during a data push.
        sha = json.loads(api(f"repos/{repo}/branches/main"))["commit"]["sha"]
        for name in files:
            try:
                body = api(f"repos/{repo}/contents/site/data/{name}?ref={sha}", raw=True)
            except subprocess.CalledProcessError as exc:
                if "HTTP 404" not in (exc.stderr or ""):
                    raise
                continue  # a genuinely missing input is due
            json.loads(body)  # malformed API responses must not cause a dispatch storm
            (data / name).write_text(body, encoding="utf-8")
        due = [key for key, value in plan(data, "schedule", now=now).items() if value]
    if not due:
        return "fresh"
    if dry_run:
        return "would-dispatch: " + ", ".join(due)
    invoke([gh, "workflow", "run", WORKFLOW, "--repo", repo, "--ref", "main", "-f", "scope=due"],
           check=True, capture_output=True, text=True, timeout=35)
    return "dispatched: " + ", ".join(due)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gh", default="gh")
    parser.add_argument("--repo", default=REPO)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    try:
        print(now.isoformat(), check(args.gh, args.repo, now, args.dry_run))
    except (subprocess.SubprocessError, OSError, ValueError, KeyError) as exc:
        # An API/auth/network failure is not evidence that the production scheduler is stale.
        print(now.isoformat(), "watchdog check failed:", type(exc).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
