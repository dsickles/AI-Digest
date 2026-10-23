---
phase: 03-ai-quality
plan: "09"
subsystem: testing
tags: [budget, iso-week, pipeline-runs, wr-02, d-59]

requires:
  - phase: 03-ai-quality
    plan: "05"
    provides: WeekBudget, baseline_per_item_from_runs, DEFAULT_BASELINE_PER_ITEM_USD
provides:
  - pipeline/week.py prior_week_id() for ISO week arithmetic
  - baseline_per_item_from_runs queries prior week's pipeline_runs (WR-02 closed)
  - tests/budget/test_baseline_prior_week.py regression coverage
affects: [03-ai-quality-gap-closure, 04-dashboard]

tech-stack:
  added: []
  patterns:
    - "Pre-flight baseline uses W-1 completed run ratio; current-week in-progress rows ignored"

key-files:
  created:
    - tests/budget/test_baseline_prior_week.py
  modified:
    - pipeline/week.py
    - pipeline/budget.py

key-decisions:
  - "prior_week_id via Monday minus 7 days + isocalendar() — handles 53-week years and year boundaries"

patterns-established:
  - "baseline_per_item_from_runs(week_id=W) always binds prior_week_id(W) in SQL"

requirements-completed: [PIPELINE-05]

duration: 8min
completed: 2026-05-23
---

# Phase 3 Plan 09: Prior-Week Pre-Flight Baseline Summary

**WR-02 closed — WeekBudget pre-flight estimates use last week's actual per-item cost from pipeline_runs, not the in-progress current week**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-23T12:05:00Z
- **Completed:** 2026-05-23T12:13:16Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `prior_week_id()` with ISO year-boundary handling (2026-W01 → 2025-W52)
- `baseline_per_item_from_runs` now queries `pipeline_runs` for W-1 per D-59 / RESEARCH Focus Area 6
- Regression tests confirm prior-week ratio wins over current-week rows; DEFAULT fallback when no prior run
- LOCKED-01 compliance — `pipeline/render/html.py` untouched

## Task Commits

Each task was committed atomically:

1. **Task 1: prior_week_id + fix baseline_per_item_from_runs** - `549828d` (feat)
2. **Task 2: Unit test — baseline reads W-1 pipeline_runs** - `2503be2` (test)

**Plan metadata:** pending (docs commit)

## Files Created/Modified

- `pipeline/week.py` - `prior_week_id()` helper
- `pipeline/budget.py` - prior-week SQL bind in `baseline_per_item_from_runs`
- `tests/budget/test_baseline_prior_week.py` - WR-02 regression tests

## Decisions Made

None - followed plan as specified

## Deviations from Plan

None - plan executed exactly as written

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- WR-02 accuracy gap closed; remaining Phase 3 gap-closure plans (CR-01, CR-02, WR-01, WR-03) still open
- Pre-flight estimates will reflect last week's spend on first run of a new ISO week when prior `pipeline_runs` row exists

## Self-Check: PASSED

- FOUND: pipeline/week.py
- FOUND: pipeline/budget.py
- FOUND: tests/budget/test_baseline_prior_week.py
- FOUND: 549828d
- FOUND: 2503be2

---
*Phase: 03-ai-quality*
*Completed: 2026-05-23*
