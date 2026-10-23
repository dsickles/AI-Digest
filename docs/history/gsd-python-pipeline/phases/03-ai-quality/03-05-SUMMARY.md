---
phase: 03-ai-quality
plan: "05"
subsystem: api
tags: [budget, pipeline-report, cascade, cli, observability]

requires:
  - phase: 03-ai-quality
    plan: "04"
    provides: rollup stage counters, PARTIAL_PUBLISH_COPY constant in html.py
provides:
  - pipeline/budget.py WeekBudget with reservation and hard-stop halt
  - pipeline/reporting/pipeline_report.py schema_version 1 JSON projection
  - pipeline/cascade.py plan_invalidation for content_hash changes
  - CLI flags --top-n --max-cost-usd --rebuild-clusters --rebuild-rollup
  - Extended last_run.md stage and budget lines
affects: [04-dashboard, 05-automation]

tech-stack:
  added: []
  patterns:
    - "WeekBudget can_afford gate before every LLM call; first halt stage preserved"
    - "pipeline_report.json projects RunStats + SQL aggregates (D-09)"
    - "Cascade invalidates summarize/dedup/rank/rollup on catch-up hash flip"

key-files:
  created:
    - pipeline/budget.py
    - pipeline/cascade.py
    - pipeline/reporting/pipeline_report.py
    - tests/budget/test_budget_halt.py
    - tests/reporting/test_pipeline_report_schema.py
    - tests/test_cascade.py
    - tests/test_cli_phase3.py
    - .planning/phases/03-ai-quality/03-UAT.md
  modified:
    - pipeline/orchestrator.py
    - pipeline/render/html.py
    - pipeline/run.py
    - pipeline/reporting/last_run.py
    - README.md

key-decisions:
  - "effective_meta_reservation caps at 50% of cap when cap < configured reservation (tiny-cap UAT)"
  - "halt_if_over_cap preserves first halted_at_stage for reader-facing partial publish attribution"
  - "title_changed triggers dedup even without content_hash change (D-68)"

patterns-established:
  - "write_pipeline_report on every _finalize — per-week + always-latest out/pipeline_report.json"
  - "RunOptions CLI flags threaded through run_all and individual LLM stage runners"

requirements-completed: [OBS-02, PIPELINE-05, PIPELINE-06]

duration: 55min
completed: 2026-05-22
---

# Phase 3 Plan 05: Cost Governance + Structured Reporting Summary

**WeekBudget hard stop with partial-publish notice, schema_version 1 pipeline_report.json every run, cascade invalidation, and Phase 3 CLI/README triad**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-05-22T20:00:00Z
- **Completed:** 2026-05-22T20:55:00Z
- **Tasks:** 3
- **Files modified:** 13

## Accomplishments

- `WeekBudget` enforces $2/week default cap with $0.10 meta reservation; `--max-cost-usd` overrides at CLI
- Summarize halt renders `partial-publish-notice` with `PARTIAL_PUBLISH_COPY`; meta stages run when cap allows (D-60)
- `out/pipeline-report-{week_id}.json` + `out/pipeline_report.json` written every finalize (OBS-02, D-69)
- `plan_invalidation` + catch-up hash wiring; `--rebuild-clusters` / `--rebuild-rollup` flags
- README + `--help` + tests cover dedup/categorize/rank/rollup subcommands and all four flags (D-22)
- Phase 3 complete — all five plans shipped

## Task Commits

1. **Task 1: WeekBudget module + orchestrator integration + partial-publish notice** - `1c72282` (feat)
2. **Task 2: pipeline_report.json projection + cascade invalidation module** - `9ced037` (feat)
3. **Task 3: CLI flags + README/UAT triad + last_run extensions** - `edd9feb` (feat)

## Files Created/Modified

| Area | File | Role |
|------|------|------|
| Budget | `pipeline/budget.py` | Reservation, pre-flight, can_afford, record_spend |
| Report | `pipeline/reporting/pipeline_report.py` | schema_version 1 JSON projection |
| Cascade | `pipeline/cascade.py` | Pure plan_invalidation stage set |
| Orchestrator | `pipeline/orchestrator.py` | Budget gates, cascade, report on finalize |
| Render | `pipeline/render/html.py` | partial-publish-notice header + top_n override |
| CLI | `pipeline/run.py` | Phase 3 flags on subcommands |
| Ops | `pipeline/reporting/last_run.py` | Stage + budget lines |
| Docs | `README.md` | Phase 3 subcommands and flags |
| UAT | `.planning/phases/03-ai-quality/03-UAT.md` | Manual watch list stub |

## Decisions Made

- Float-safe `can_afford` comparisons rounded to 6 decimals
- First `halted_at_stage` preserved when later meta stages also hit cap

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Floating-point summarize pool blocked all LLM at cap 0.01**
- **Found during:** Task 1 (budget halt test)
- **Issue:** `0.01 - 0.009` vs `0.001` estimate failed due to IEEE754
- **Fix:** Round comparisons in `can_afford`; cap effective meta reservation when cap < configured reservation
- **Files modified:** `pipeline/budget.py`
- **Committed in:** `1c72282`

**2. [Rule 1 - Bug] title_changed did not trigger dedup without hash change**
- **Found during:** Task 2 (test_cascade.py)
- **Issue:** `plan_invalidation` required hash change for dedup branch
- **Fix:** `(hash_changed and is_canonical) or title_changed` triggers dedup
- **Files modified:** `pipeline/cascade.py`
- **Committed in:** `9ced037`

## Issues Encountered

None blocking. Full suite 139 tests pass (~76s).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 4 can consume `out/pipeline_report.json` and `out/pipeline-report-{week_id}.json` (OBS-01)
- Phase 5 heartbeat can read always-latest `out/pipeline_report.json` (OBS-03)
- Manual UAT watch list in `03-UAT.md` for first live Phase 3 weeks

## Self-Check: PASSED

- FOUND: pipeline/budget.py
- FOUND: pipeline/cascade.py
- FOUND: pipeline/reporting/pipeline_report.py
- FOUND: tests/budget/test_budget_halt.py
- FOUND: tests/reporting/test_pipeline_report_schema.py
- FOUND: tests/test_cli_phase3.py
- FOUND: .planning/phases/03-ai-quality/03-05-SUMMARY.md
- FOUND: commit 1c72282
- FOUND: commit 9ced037
- FOUND: commit edd9feb

---
*Phase: 03-ai-quality*
*Completed: 2026-05-22*
