---
phase: 03-ai-quality
plan: "08"
subsystem: pipeline
tags: [cascade, dedup, normalize_title, ingest, sqlite]

# Dependency graph
requires:
  - phase: 03-ai-quality
    provides: plan_invalidation title_changed branch and delete_cluster_artifacts_for_week (03-06)
provides:
  - Title-aware _apply_cascade_for_item with normalize_title comparison
  - Ingest pre-upsert lookup via get_item_by_source_external
  - Cascade hook on in-window re-ingest when title or hash shifts
affects: [03-07, 03-10, phase-4]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pre-upsert item lookup for stable item_id + title/hash delta detection"
    - "title_changed computed in orchestrator, not hardcoded in plan_invalidation call"

key-files:
  created:
    - tests/test_cascade_wiring.py
  modified:
    - store/db.py
    - pipeline/orchestrator.py
    - tests/test_cascade.py

key-decisions:
  - "03-08: title_changed derived from normalize_title(old) != normalize_title(new) when both titles supplied; else False"
  - "03-08: ingest passes week_id into _ingest so in-window re-ingests invoke cascade before dedup stage"

patterns-established:
  - "WR-01: RSS headline edits without body hash change trigger STAGE_SUMMARIZE + STAGE_DEDUP via cascade"

requirements-completed: [PIPELINE-06]

# Metrics
duration: 15min
completed: 2026-05-23
---

# Phase 03 Plan 08: Title Cascade Wiring Summary

**Normalized title comparison on ingest and catch-up closes WR-01 — editorial RSS headline fixes invalidate summaries and dedup without touching the renderer.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-23T12:14:20Z
- **Completed:** 2026-05-23T12:15:26Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `get_item_by_source_external` for pre-upsert title/hash lookup
- `_apply_cascade_for_item` computes `title_changed` via `normalize_title` instead of hardcoded `False`
- Ingest loop invokes cascade for in-window items when a prior row existed
- Catch-up path passes `old_title`/`new_title` from the pending row
- WR-01 closed with pure `plan_invalidation` test and orchestrator wiring test

## Task Commits

Each task was committed atomically:

1. **Task 1: Title comparison in _apply_cascade_for_item + ingest hook** - `5dd3f2a` (feat)
2. **Task 2: Tests — plan_invalidation + orchestrator summary invalidation** - `e733fdc` (test)

## Files Created/Modified

- `store/db.py` — `get_item_by_source_external` helper
- `pipeline/orchestrator.py` — title-aware cascade + ingest/catch-up wiring
- `tests/test_cascade.py` — `test_title_change_invalidates_summarize`
- `tests/test_cascade_wiring.py` — orchestrator deletes `item_summaries` on title-only cascade

## Decisions Made

- Thread `week_id` into `_ingest` so cascade invalidation runs during ingest, not only catch-up
- Title comparison only when both `old_title` and `new_title` are explicitly passed (catch-up passes unchanged title → `title_changed=False`)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- WR-01 closed; 03-10 (WR-03 cost attribution) and 03-07 (CR-02 checkpoint guards) unblocked
- LOCKED-01 preserved — `_partition_cards` untouched

## Self-Check: PASSED

- FOUND: tests/test_cascade_wiring.py
- FOUND: store/db.py get_item_by_source_external
- FOUND: commit 5dd3f2a
- FOUND: commit e733fdc

---
*Phase: 03-ai-quality*
*Completed: 2026-05-23*
