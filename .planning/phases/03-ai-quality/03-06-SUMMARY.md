---
phase: 03-ai-quality
plan: "06"
subsystem: database
tags: [sqlite, fk, dedup, idempotency, pytest]

requires:
  - phase: 03-ai-quality
    provides: story_clusters, cluster_summaries, cluster_ranks, weekly_rollups schema and dedup rebuild
provides:
  - delete_cluster_artifacts_for_week FK-safe cascade before cluster delete
  - delete_clusters_for_week as single dedup rebuild entry point
  - test_run_all_twice_same_week integration regression for CR-01/IN-01
affects: [03-07, 03-08, 03-10, PIPELINE-05, PIPELINE-06]

tech-stack:
  added: []
  patterns:
    - "FK-safe artifact delete order: cluster_ranks → cluster_summaries → weekly_rollups → cluster_members → story_clusters"

key-files:
  created:
    - tests/test_run_all_twice_same_week.py
  modified:
    - store/db.py
    - tests/dedup/test_cluster.py

key-decisions:
  - "Fold artifact delete into delete_clusters_for_week rather than new call sites in run_dedup_for_week (single rebuild entry point)"

patterns-established:
  - "Dedup rebuild clears all week-scoped cluster-attached rows before story_clusters delete (migration 004 FK order)"

requirements-completed: [PIPELINE-05, PIPELINE-06]

duration: 8min
completed: 2026-05-23
---

# Phase 3 Plan 6: Cluster Artifact FK Delete Summary

**FK-safe cluster artifact cascade before dedup rebuild closes CR-01; integration test proves same-week run_all idempotency (IN-01)**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-23T12:13:00Z
- **Completed:** 2026-05-23T12:14:20Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `delete_cluster_artifacts_for_week` deleting `cluster_ranks`, `cluster_summaries`, and `weekly_rollups` for all prompt versions before cluster row removal
- Extended `delete_clusters_for_week` to invoke artifact delete first — `run_dedup_for_week` unchanged (single entry point)
- Unit test seeds FK-linked artifact graph and asserts clean delete without `IntegrityError`
- Integration test runs mocked `run_all` twice for `2026-W21`; second run succeeds with `Briefing — Top` in digest HTML

## Task Commits

Each task was committed atomically:

1. **Task 1: delete_cluster_artifacts_for_week + fold into delete_clusters_for_week** - `948820f` (fix)
2. **Task 2: Integration test — run_all twice same week (IN-01)** - `4b8e8a3` (test)

**Plan metadata:** `51b715b` (docs: complete plan)

## Files Created/Modified

- `store/db.py` - `delete_cluster_artifacts_for_week`; extended `delete_clusters_for_week`
- `tests/dedup/test_cluster.py` - `test_delete_clusters_for_week_clears_artifact_tables`
- `tests/test_run_all_twice_same_week.py` - end-to-end same-week double `run_all` regression

## Decisions Made

- Artifact invalidation stays inside `delete_clusters_for_week` so orchestrator and dedup module share one rebuild entry point (no duplicate delete logic in `pipeline/dedup/cluster.py`)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CR-01 and IN-01 closed; same-week re-run path unblocked for dedup stage
- CR-02 (rank/rollup stale skip guards) remains for plan 03-07
- Wave 2 gap closure (03-08) unblocked

## Self-Check: PASSED

- FOUND: store/db.py
- FOUND: tests/test_run_all_twice_same_week.py
- FOUND: tests/dedup/test_cluster.py (artifact test)
- FOUND: 948820f
- FOUND: 4b8e8a3

---
*Phase: 03-ai-quality*
*Completed: 2026-05-23*
