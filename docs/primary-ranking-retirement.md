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

## Current consumer inventory and offline output

As of main `f997c19f463e1ff40c658ac09628f3ff1e39bc0a`, the public reader loads `unified-rankings.json` on demand for the six primary boards and model-detail board references. It uses `calculatedAt`, category IDs and primary board metadata/rows, not composite calibrations or category anchors. `ranking_identity.py` and `validate_model_links.py` consume the same primary fields; the freshness planner reads `calculatedAt`. The resource transaction still invokes `build_unified_rankings.py` and backs up its frozen baseline. The candidate now writes a full reader payload only to a caller-specified non-production location; test real-snapshot equivalence, missing boards and no baseline writes. No live schedule changes. Preserve the v4 original code, full output and inputs at the pinned commit above; archive the final legacy production artifacts by blob identity at actual retirement, not a prematurely frozen copy. Production cutover remains gated by the previously agreed independent P1 requirements and exact CI/production acceptance.
