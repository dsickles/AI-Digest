---
phase: 04-dashboard-archive
plan: "01"
subsystem: api
tags: [python, locked-01, partition, render, docs]

requires:
  - phase: 03-ai-quality
    provides: DigestCard records, summary_status taxonomy, partition regression tests
provides:
  - pipeline/render/partition.py as canonical LOCKED-01 router module
  - html.py deprecated dev-preview wrapper re-exporting partition symbols
  - LOCKED-DIRECTIVES and REQUIREMENTS aligned to three topic tabs
affects: [04-02, digest_json, astro-dashboard]

tech-stack:
  added: []
  patterns:
    - "LOCKED-01 routing centralized in partition.py; html.py thin re-export only"
    - "PARTIAL_PUBLISH_COPY reconciled to UI-SPEC long form in partition constants"

key-files:
  created:
    - pipeline/render/partition.py
  modified:
    - pipeline/render/html.py
    - .planning/LOCKED-DIRECTIVES.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "partition.py is primary LOCKED-01 anchor; digest_json.py will import same router in Plan 04-02"
  - "PARTIAL_PUBLISH_COPY updated to UI-SPEC verbatim string during extract (not deferred)"
  - "REQUIREMENTS DISPLAY-02/04 reconciled to Briefing + three topic tabs per 2026-05-23 design cut"

patterns-established:
  - "Canonical card routing lives in pipeline.render.partition; html.py marked DEPRECATED dev-preview"

requirements-completed: [ARCHIVE-01]

duration: 15min
completed: 2026-05-23
---

# Phase 4 Plan 01: Partition Extract Summary

**LOCKED-01 card routing extracted to `partition.py` with html.py as deprecated re-export and spec docs reconciled to three topic tabs**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-23T23:00:00Z
- **Completed:** 2026-05-23T23:15:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `pipeline/render/partition.py` with `DigestCard`, `_partition_cards`, category constants, and UI-SPEC `PARTIAL_PUBLISH_COPY` — zero routing behavior change
- Rewired `html.py` to import from `partition.py` with DEPRECATED dev-preview banner; kept `render_digest` and HTML builders in place
- Updated LOCKED-01 code anchors to cite `partition._partition_cards` as primary router
- Reconciled REQUIREMENTS DISPLAY-02 and DISPLAY-04 to Briefing + Edtech/Business/Technical (no Design tab)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract partition.py and rewire html.py re-exports** - `ed2efef` (feat)
2. **Task 2: Update LOCKED-01 code anchors and reconcile REQUIREMENTS tab count** - `e039c9c` (docs)

**Plan metadata:** `pending` (docs commit follows)

## Files Created/Modified

- `pipeline/render/partition.py` - Canonical LOCKED-01 router, card types, and reader-surface copy constants
- `pipeline/render/html.py` - DEPRECATED dev-preview HTML renderer; re-exports partition symbols
- `.planning/LOCKED-DIRECTIVES.md` - LOCKED-01 code anchors point at partition module
- `.planning/REQUIREMENTS.md` - DISPLAY-02/04 three-tab reconciliation + design-cut note

## Decisions Made

- Moved `PARTIAL_PUBLISH_COPY` to UI-SPEC long form during extract (plan-specified; supersedes old budget-estimate wording)
- Left existing tests importing from `html.py` unchanged — backward-compatible re-exports preserve compatibility

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 04-02 can implement `digest_json.py` importing `_partition_cards` from `partition.py`
- `tests/budget/test_budget_halt.py` still asserts old `PARTIAL_PUBLISH_COPY.split(";")` shape — may need update when budget-halt copy is next touched (out of scope for this plan)

---
*Phase: 04-dashboard-archive*
*Completed: 2026-05-23*

## Self-Check: PASSED

- FOUND: pipeline/render/partition.py
- FOUND: .planning/phases/04-dashboard-archive/04-01-SUMMARY.md
- FOUND: commit ed2efef
- FOUND: commit e039c9c
