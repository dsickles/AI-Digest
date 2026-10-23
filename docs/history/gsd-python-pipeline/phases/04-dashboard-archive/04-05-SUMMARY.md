---
phase: 04-dashboard-archive
plan: "05"
subsystem: ui
tags: [astro, pipeline-notes, archive, obs-01, pytest, tailwind]

requires:
  - phase: 04-dashboard-archive
    plan: "04"
    provides: Briefing pages, TabBar, DigestBriefing layout
  - phase: 04-dashboard-archive
    plan: "02"
    provides: digest_json.py pipeline_notes schema and emit_digest_json
provides:
  - OBS-01 pipeline_notes emitter with silent-source threshold and automated tests
  - /archive index newest-first with synthesis excerpt fallback
  - PipelineNotes.astro native details/summary; PartialPublishNotice.astro amber band
  - Mobile overflow-x-hidden and flex-col header stack
affects: [04-06, phase-5-automation]

tech-stack:
  added: []
  patterns:
    - "PipelineNotes mounted once at top of Briefing main — not in Header.astro"
    - "pipeline_notes null omits DOM entirely (D-A4a zero-state)"
    - "Silent sources surface only after 3+ consecutive empty weeks (D-A4b)"
    - "Fetch failures in source_health surfaced without SQLite conn"

key-files:
  created:
    - tests/render/test_pipeline_notes.py
    - web/src/pages/archive.astro
    - web/src/components/ArchiveList.astro
    - web/src/components/PipelineNotes.astro
    - web/src/components/PartialPublishNotice.astro
    - web/src/lib/archiveExcerpt.ts
  modified:
    - pipeline/render/digest_json.py
    - web/src/pages/index.astro
    - web/src/pages/digest/[week].astro
    - web/src/components/DigestBriefing.astro
    - web/src/components/Header.astro
    - web/src/layouts/BaseLayout.astro

key-decisions:
  - "Fetch failure copy runs without conn; silent-source streak queries still require conn"
  - "Archive header omits week meta when content collection is empty"

patterns-established:
  - "archiveExcerpt(): first synthesis sentence or briefing_top_n[0].title"
  - "PartialPublishNotice gates on failure_notice.kind === partial_publish"

requirements-completed: [ARCHIVE-02, ARCHIVE-04, OBS-01, DISPLAY-07]

duration: 25min
completed: 2026-05-23
---

# Phase 4 Plan 05: Archive Index + Pipeline Notes Summary

**Archive index at /archive, native PipelineNotes details/summary on Briefing pages, and OBS-01 emitter tests with 3-week silent-source threshold**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-23T23:00:00Z
- **Completed:** 2026-05-23T23:10:00Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments

- `test_pipeline_notes.py` covers zero-state, 3-week silent-source threshold, fetch failure copy, budget halt, and LOCKED-01 thin exclusion
- `_build_pipeline_notes` surfaces fetch failures without requiring SQLite conn
- `/archive` lists digests newest-first with `Read this week` links and UI-SPEC empty state
- `PipelineNotes.astro` uses native `<details>`/`<summary>`; omitted when `pipeline_notes` is null
- `PartialPublishNotice.astro` renders PARTIAL_PUBLISH_COPY before synthesis on Briefing pages
- Body `overflow-x-hidden w-full`; Header optional week meta for empty archive

## Task Commits

Each task was committed atomically:

1. **Task 1: Complete OBS-01 pipeline_notes emitter + tests** - `d3cdf88` (test)
2. **Task 2: Archive index, PipelineNotes, PartialPublish, mobile responsive classes** - `8b0a928` (feat)

## Files Created/Modified

- `tests/render/test_pipeline_notes.py` - OBS-01 contract tests
- `pipeline/render/digest_json.py` - fetch-failure path outside conn gate
- `web/src/pages/archive.astro` - archive route
- `web/src/components/ArchiveList.astro` - newest-first rows
- `web/src/components/PipelineNotes.astro` - expandable pipeline notes
- `web/src/components/PartialPublishNotice.astro` - budget halt band
- `web/src/lib/archiveExcerpt.ts` - excerpt helper
- `web/src/pages/index.astro`, `web/src/pages/digest/[week].astro` - PipelineNotes mount
- `web/src/layouts/BaseLayout.astro` - mobile overflow guard

## Decisions Made

- Fetch failures use `source_health` snapshot only (no conn); silent-source streak still queries items table
- Archive page uses latest digest week in header when collection non-empty; omits week lines when empty

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fetch failures required SQLite conn**
- **Found during:** Task 1 (pipeline_notes tests)
- **Issue:** `_build_pipeline_notes` only iterated `source_health` when `conn is not None`, so fetch_timeout copy never emitted in report-only contexts
- **Fix:** Moved fetch-failure branch outside conn gate; silent-source branch remains conn-gated
- **Files modified:** `pipeline/render/digest_json.py`
- **Verification:** `pytest tests/render/test_pipeline_notes.py -x -q` green
- **Committed in:** `d3cdf88`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Required for OBS-01 fetch-failure copy contract; no scope creep.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 04-06 can wire remaining phase close-out (validation, human UAT)
- Archive and PipelineNotes ready for live digest JSON with `pipeline_notes` populated

## Self-Check: PASSED

- FOUND: tests/render/test_pipeline_notes.py
- FOUND: web/src/pages/archive.astro
- FOUND: web/src/components/PipelineNotes.astro
- FOUND: web/dist/archive/index.html
- FOUND: commit d3cdf88
- FOUND: commit 8b0a928

---
*Phase: 04-dashboard-archive*
*Completed: 2026-05-23*
