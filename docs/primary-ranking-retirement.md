# P2-A2: source-native leaderboard retirement candidate

The production resource batch still invokes the historical v4 composite
experiment even though the public interface displays source-native primary
boards. This candidate adds a read-only projection and equivalence tests; it
does not change the production generator, data schema, ranking policy, scores,
source snapshots, frozen baselines, or deployment.

Acceptance for subsequent retirement:
- Exact equality of all six primary task boards, including original ranks,
  exclusions, score intervals, metadata, and audited model/version links.
- Inventory every active consumer of the current output and baseline, including
  validation, resource freshness, model links, global search, scripts and docs.
- Preserve historical composite artifacts and their original inputs in archive.
- Switch production only in a separate atomic PR after P1 gates and full CI;
  verify live output and rollback without recomputing or discarding history.
- Keep the same authoritative source snapshots. Never promote cross-pool
  composite scores or make missing source rows appear valid.
