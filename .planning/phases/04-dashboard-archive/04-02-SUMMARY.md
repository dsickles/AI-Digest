---
phase: 04-dashboard-archive
plan: "02"
subsystem: api
tags: [python, pydantic, json, archive, locked-01, astro]

requires:
  - phase: 04-dashboard-archive
    plan: "01"
    provides: partition.py canonical LOCKED-01 router
provides:
  - pipeline/render/digest_json.py with emit_digest_json and DigestDocument models
  - orchestrator JSON publish path to web/src/content/digests/
  - pipeline report archive copy to web/src/content/reports/
  - render CLI flags --no-html-preview and --web-out
affects: [04-03, 04-04, astro-scaffold, backfill]

tech-stack:
  added: []
  patterns:
    - "Pre-partitioned digest JSON with schema_version 1; Astro is presentational only"
    - "Dual publish: deprecated HTML preview optional; canonical JSON always emitted"

key-files:
  created:
    - pipeline/render/digest_json.py
    - tests/render/test_digest_json_schema.py
    - tests/render/test_digest_json_partition_parity.py
    - web/src/content/digests/.gitkeep
    - web/src/content/reports/.gitkeep
  modified:
    - pipeline/orchestrator.py
    - pipeline/reporting/pipeline_report.py
    - pipeline/render/__init__.py
    - pipeline/run.py
    - .gitignore

key-decisions:
  - "pipeline_notes built in Python with UI-SPEC copy; silent-source uses consecutive empty-week query"
  - "write_pipeline_report archives to web/src/content/reports/{week_id}.json by default"
  - "run_render always emits JSON; HTML preview skippable via --no-html-preview"

patterns-established:
  - "emit_digest_json mirrors render_digest orchestration but outputs Pydantic-validated JSON"
  - "_publish_render_outputs centralizes dual HTML+JSON publish in orchestrator"

requirements-completed: [ARCHIVE-01, OBS-01]

duration: 20min
completed: 2026-05-23
---

# Phase 4 Plan 02: Digest JSON Publish Path Summary

**Pydantic digest JSON emitter with LOCKED-01 pre-partitioned lists, orchestrator wiring, report archive, and render CLI flags**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-23T23:20:00Z
- **Completed:** 2026-05-23T23:40:00Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Created `digest_json.py` with `DigestDocument`, `emit_digest_json`, and pipeline_notes builder using UI-SPEC copy templates
- Wired `run_render` and `run_all` to emit `web/src/content/digests/{week_id}.json` after card build (no LLM on render path)
- Extended `write_pipeline_report` to archive `{week_id}.json` under `web/src/content/reports/`
- Added `--no-html-preview` and `--web-out` on render subcommand; updated `.gitignore` for Astro build artifacts
- Contract tests verify schema_version 1, partition parity, and briefing top-N cap

## Task Commits

Each task was committed atomically:

1. **Task 1: digest_json.py Pydantic models and emit_digest_json** - `52062ba` (feat)
2. **Task 2: Wire orchestrator, report archive, CLI flags, gitignore** - `216a227` (feat)

**Plan metadata:** pending (docs commit follows)

## Files Created/Modified

- `pipeline/render/digest_json.py` - Pydantic models and LOCKED-01 JSON emitter with pipeline_notes
- `pipeline/orchestrator.py` - `_publish_render_outputs` dual publish; `digest_json_path` on RunStats
- `pipeline/reporting/pipeline_report.py` - Third write target for Astro report archive
- `pipeline/run.py` - Render flags and digest_json path in stats output
- `pipeline/render/__init__.py` - Exports `emit_digest_json`
- `.gitignore` - Ignores web/node_modules, web/.astro, web/dist
- `web/src/content/digests/.gitkeep` - Archive directory placeholder
- `web/src/content/reports/.gitkeep` - Report archive directory placeholder
- `tests/render/test_digest_json_schema.py` - Schema contract tests
- `tests/render/test_digest_json_partition_parity.py` - LOCKED-01 list parity tests

## Decisions Made

- Basic pipeline_notes from pipeline_report in Plan 02; full OBS-01 silent-source threshold tests deferred to Plan 04-05 per roadmap
- `partial_publish` failure_notice driven by budget.halted in run_all; render-only path defaults False (matches prior HTML behavior)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added Path import to pipeline/run.py**
- **Found during:** Task 2 verification
- **Issue:** `--web-out` flag used `type=Path` without importing Path
- **Fix:** Added `from pathlib import Path`
- **Files modified:** pipeline/run.py
- **Committed in:** 216a227

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required for CLI to load; no scope change.

## Issues Encountered

None beyond the missing Path import caught during verify.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 04-03 can scaffold Astro with Zod schema mirroring `DigestDocument`
- Backfill via `python -m pipeline.run render --week YYYY-Www` writes committed JSON under `web/src/content/`
- Plan 04-05 will extend pipeline_notes tests (zero-state, 3+ week silent-source)

---
*Phase: 04-dashboard-archive*
*Completed: 2026-05-23*

## Self-Check: PASSED

- FOUND: pipeline/render/digest_json.py
- FOUND: .planning/phases/04-dashboard-archive/04-02-SUMMARY.md
- FOUND: commit 52062ba
- FOUND: commit 216a227
