# Stop scheduling unconsumed collectors

The production reader has no load entry for social-trends.json or model-evaluations.json. The latter remains referenced by model linking/validation and its tests; these local references are deliberately preserved for this first retirement phase. The official social account snapshot, AIHOT/AIPick hot topics, app updates and creator opportunities are unrelated and unchanged.

Remove the two network collectors from all automated collection batches and remove their clocks from refresh planning. Leave the last snapshots, manual scripts, original evidence and existing validators intact pending a separate complete consumer/archive audit. Do not treat the retained snapshot timestamps as live updates or turn missing clocks into a refresh incident. The old Google Trends job can fetch eight regional RSS feeds; the old evaluation collector permits up to three Sogou queries per run. These are configured upper bounds, not measured savings. No new scheduler or external requests.

Acceptance: automated groups never invoke the retired collectors, missing snapshots do not trigger refresh, existing readers and independent evidence checks pass, and production persists/publishes normally. Separate archival cleanup requires full reference verification, including local/manual users.

This PR also includes the independently reviewed recent repository card probe changes from #102 (see [recent repository probe policy](recent-repository-probe-policy.md)). Both changes preserve source evidence and do not change the independent sample denominator. Validate together against the current production snapshot to avoid redundant deployment.

## Archival phase

After #103 removed the schedule, the last live scripts, snapshots and the collector-specific historical test are moved byte-for-byte into [retired reading collectors](../archive/retired-reading-collectors/README.md). Live model linking and validation no longer scan the archived evaluation candidates; all active model references and their existing tests remain. The archive is not a runtime dependency. Reproduce the historical code/tests from the pinned pre-archive revision rather than running archived code against live data. Repository references were inspected; local external consumers have not been independently observed.
