---
phase: 03-ai-quality
plan: "07"
subsystem: database
tags: [sqlite, pipeline, checkpoint, rank, rollup, integrity]

requires:
  - phase: 03-ai-quality
    provides: delete_cluster_artifacts_for_week (CR-01), per-stage cost fields (WR-03), cascade title_changed (WR-01)
provides:
  - ranks_cover_current_clusters integrity predicate in store/db.py
  - rollup_checkpoint_valid helper
  - _rank_week / _rollup_week skip guards gated on cluster-set coverage
  - tests/test_rank_rollup_checkpoint_integrity.py regression suite
affects: [phase-4-dashboard, pipeline-resume]

tech-stack:
  added: []
  patterns:
    - "Defense-in-depth checkpoint skip: row-exists AND JOIN coverage before skip"
    - "Stale checkpoint path deletes orphan rows then re-runs LLM stage"

key-files:
  created:
    - tests/test_rank_rollup_checkpoint_integrity.py
  modified:
    - store/db.py
    - pipeline/orchestrator.py

key-decisions:
  - "Skip rank/rollup only when ranks_cover_current_clusters is True — not on row count alone"
  - "Stale rank path calls delete_ranks_for_week before re-rank; stale rollup deletes scope row before re-insert"

patterns-established:
  - "CR-02 integrity: cluster_ranks count must equal story_clusters count with no orphan cluster_id refs"

requirements-completed: [PIPELINE-05, PIPELINE-06]

duration: 20min
completed: 2026-05-23
---

# Phase 3 Plan 07: Rank/Rollup Checkpoint Integrity Summary

**Cluster-set integrity gates on rank/rollup skip paths — stale orphan cluster_ranks force LLM re-run (CR-02 closed)**

## Performance

- **Duration:** 20 min
- **Started:** 2026-05-23T12:17:00Z
- **Completed:** 2026-05-23T12:18:11Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `ranks_cover_current_clusters` and `rollup_checkpoint_valid` in `store/db.py`
- Wired `_rank_week` and `_rollup_week` to skip only when rank rows fully JOIN current `story_clusters`
- Five regression tests prove matching coverage, orphan detection, stale rank re-run, and stale weekly rollup re-run
- LOCKED-01 preserved — `pipeline/render/html._partition_cards` untouched

## Task Commits

Each task was committed atomically:

1. **Task 1: ranks_cover_current_clusters helper in store/db.py** - `9b06430` (feat)
2. **Task 2: Wire _rank_week and _rollup_week skip guards + behavioral tests** - `d2d2936` (feat)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified

- `store/db.py` - `ranks_cover_current_clusters`, `rollup_checkpoint_valid`
- `pipeline/orchestrator.py` - skip guards + stale delete before re-run
- `tests/test_rank_rollup_checkpoint_integrity.py` - unit + behavioral CR-02 tests

## Decisions Made

- Rank skip requires both existing rows and full cluster-set coverage; stale path deletes ranks then re-ranks
- Rollup skip (category + weekly) uses the same coverage predicate; stale path deletes the scope row before re-insert to satisfy UNIQUE constraint

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Delete stale weekly/category rollup before re-insert**
- **Found during:** Task 2 (rollup behavioral test)
- **Issue:** Re-running `rollup_weekly` on stale checkpoint attempted INSERT while stale row still existed — UNIQUE constraint on `(week_id, scope, prompt_version)`
- **Fix:** DELETE stale rollup row for the scope before invoking rollup LLM when `ranks_cover_current_clusters` is False
- **Files modified:** `pipeline/orchestrator.py`
- **Verification:** `uv run pytest tests/test_rank_rollup_checkpoint_integrity.py -x -q` exits 0
- **Committed in:** `d2d2936` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Required for correct stale-rollup re-run; no scope creep.

## Issues Encountered

None beyond the stale rollup UNIQUE constraint caught by the behavioral test.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 gap closure complete (19/19 plans)
- CR-02 closed with defense-in-depth complementing CR-01 artifact delete
- Ready for Phase 4 dashboard work

## Self-Check: PASSED

- FOUND: store/db.py ranks_cover_current_clusters
- FOUND: pipeline/orchestrator.py skip guards
- FOUND: tests/test_rank_rollup_checkpoint_integrity.py
- FOUND: commit 9b06430
- FOUND: commit d2d2936

---
*Phase: 03-ai-quality*
*Completed: 2026-05-23*
