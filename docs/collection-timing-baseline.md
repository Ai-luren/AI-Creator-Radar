# P2-B collection measurement baseline

Read-only candidate: `python scripts/audit_collection_timing.py <downloaded-collect-job-log>`.
No network requests, writes to site/data, new scheduled jobs or changes to
production collection.

## Observed baseline

Production [run 45970377750](https://github.com/Ai-luren/AI-Creator-Radar/actions/runs/45970377750),
collect job 140409067297, 2026-11-27 UTC. Collection and persistence and
the Pages deploy step succeeded. Independent live-site equality is unverified.

| Phase | Start UTC | Next step UTC | Elapsed seconds |
|---|---|---|---:|
| Models | 09:02:31.360 | 09:06:08.305 | 216.945 |
| Model links | 09:06:08.504 | 09:06:49.349 | 40.845 |

Eight model transactions reported successful commits to the working tree;
no model batch failures. The resource and maintenance groups were skipped,
not measured. This is one successful run, not a percentile estimate.
Child process output buffering prevents meaningful individual transaction
duration measurements. HTTP attempt totals and avoided publication counts
are unknown; do not count deferred cached 403/429 records as fresh requests
or test-fixture warnings as production failures.

Next acceptance: collect multiple comparable actual logs, add explicit
monotonic per-transaction timing and real HTTP attempt counts in an isolated
candidate after P1, retain rollback and independent watchdog, compare equal
workload and source coverage, and verify real persistence and deployment.
No budget or freshness policy change is authorized by this measurement.
