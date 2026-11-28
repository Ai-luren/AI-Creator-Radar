# Stop scheduling unconsumed collectors

The production reader has no load entry for social-trends.json or model-evaluations.json. The latter remains referenced by model linking/validation and its tests; these local references are deliberately preserved for this first retirement phase. The official social account snapshot, AIHOT/AIPick hot topics, app updates and creator opportunities are unrelated and unchanged.

Remove the two network collectors from all automated collection batches and remove their clocks from refresh planning. Leave the last snapshots, manual scripts, original evidence and existing validators intact pending a separate complete consumer/archive audit. Do not treat the retained snapshot timestamps as live updates or turn missing clocks into a refresh incident. The old Google Trends job can fetch eight regional RSS feeds; the old evaluation collector permits up to three Sogou queries per run. These are configured upper bounds, not measured savings. No new scheduler or external requests.

Acceptance: automated groups never invoke the retired collectors, missing snapshots do not trigger refresh, existing readers and independent evidence checks pass, and production persists/publishes normally. Separate archival cleanup requires full reference verification, including local/manual users.
