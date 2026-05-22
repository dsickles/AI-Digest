---
phase: 01-foundation-first-digest
plan: "05"
subsystem: testing
tags: [structlog, markdown, html, pytest, sqlite, observability]

requires:
  - phase: 01-foundation-first-digest
    provides: orchestrator, render, summarize, CLI subcommands from plans 01-01–01-04
provides:
  - configure_structlog() with TTY/JSON renderers
  - out/last_run.md run report writer
  - pipeline_runs finalized metrics on every subcommand
  - D-18 HTML header + D-17 inline CSS polish
  - Full Phase 1 pytest suite (41 tests)
affects: [phase-2-expand-ingestion, phase-3-ai-quality, phase-5-ops]

tech-stack:
  added: []
  patterns:
    - "structlog at CLI boundary only; TTY ConsoleRenderer / pipe JSONRenderer"
    - "RunSummary → last_run.md overwritten per subcommand"
    - "ingest_fetch_* / summarize_* / render_complete log event names"

key-files:
  created:
    - pipeline/logging_config.py
    - pipeline/reporting/last_run.py
  modified:
    - pipeline/run.py
    - pipeline/orchestrator.py
    - pipeline/llm/summarize.py
    - pipeline/adapters/rss.py
    - pipeline/render/html.py
    - tests/test_pipeline.py
    - tests/test_render.py
    - README.md

key-decisions:
  - "Moved inline structlog setup from run.py to logging_config.configure_structlog()"
  - "last_run.md written on success and failure paths for all four subcommands"
  - "HTML badge format [display_name] per D-14; week header uses portable day formatting (no %-d)"
  - "Live E2E with real feeds + GEMINI_API_KEY documented as manual follow-up (sandbox TLS)"

patterns-established:
  - "Observability: structured logs + last_run.md + pipeline_runs row — substrate for Phase 3 pipeline_report.json"
  - "Hermetic run_all test mocks adapters/LLM; asserts pipeline_runs.finished_at and counters"

requirements-completed: [PIPELINE-01]

duration: 55m
completed: 2026-05-21
---

# Phase 1 Plan 05: Observability + HTML Polish Summary

**structlog D-07 logging, last_run.md D-08 report, pipeline_runs metrics, D-18 week header, and green Phase 1 pytest suite**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-05-21T12:00:00Z (approx)
- **Completed:** 2026-05-21T12:55:00Z (approx)
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- `configure_structlog()` with TTY-aware ConsoleRenderer / JSONRenderer; called from CLI entry
- `ingest_fetch_start/complete`, `summarize_start/complete`, `render_complete` events with source_id, tokens, cost
- `write_last_run_md()` overwrites `out/last_run.md` per subcommand with per-source table + LLM section
- HTML header: "AI Digest", "Week of May 4 – May 10, 2026", "Updated …Z"; dark theme ~720px; `[publisher]` badges
- 41 pytest tests green; README documents full Phase 1 workflow + manual success checklist

## Task Commits

1. **Task 1: structlog + pipeline_runs metrics** — `4660bc1` (feat)
2. **Task 2: last_run.md writer** — `3c9ffe0` (feat)
3. **Task 3: HTML polish + tests + README** — `2dd04dc` (feat)

**Plan metadata:** pending (docs commit)

## Files Created/Modified

- `pipeline/logging_config.py` — structlog configuration (D-07)
- `pipeline/reporting/last_run.py` — RunSummary + markdown writer (D-08)
- `pipeline/orchestrator.py` — fetch timing logs, per-source stats, last_run hook, card sort
- `pipeline/render/html.py` — D-17/D-18 header and styling
- `tests/test_pipeline.py` — run_all metrics + structlog source_id + last_run unit test
- `tests/test_render.py` — Week of, rel=noopener, sort, badge tests
- `README.md` — Phase 1 workflow, debugging, success criteria checklist

## Decisions Made

- Used portable `strftime('%b') + day` instead of `%-d` for cross-platform week header dates
- Kept CSS at ~40 lines (trimmed from Plan 01-01 skeleton) while preserving dark theme contract
- Did not run live `pipeline.run all` in sandbox — documented as manual UAT (TLS/network)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] last_run.md on failure paths**
- **Found during:** Task 2
- **Issue:** Plan implied write on completion; exception handlers only finalized DB
- **Fix:** `_write_last_run(stats, status="failed")` in all four subcommand except blocks
- **Files modified:** `pipeline/orchestrator.py`
- **Committed in:** `3c9ffe0`

**2. [Rule 3 - Blocking] structlog caplog test replaced with capture_logs**
- **Found during:** Task 1
- **Issue:** caplog did not capture structlog PrintLogger output when log param was MagicMock
- **Fix:** Use `structlog.testing.capture_logs` with real bound logger
- **Files modified:** `tests/test_pipeline.py`
- **Committed in:** `4660bc1`

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 blocking)
**Impact on plan:** No scope creep; both required for acceptance criteria.

## Issues Encountered

None blocking. Live three-feed E2E and browser UAT remain manual (see 01-VALIDATION.md).

## User Setup Required

None beyond existing `.env` + `uv sync`. Live run requires `GEMINI_API_KEY` and network outside corporate TLS-intercept sandboxes.

## Next Phase Readiness

- Phase 1 complete — ready for Phase 2 discuss/plan (YouTube, Reddit/HN, email→RSS adapters)
- `pipeline_runs` + `last_run.md` provide observability substrate for Phase 3 `pipeline_report.json`
- Pending manual: live E2E twice for idempotency UAT; browser check of digest HTML

## Self-Check: PASSED

- pipeline/logging_config.py — FOUND
- pipeline/reporting/last_run.py — FOUND
- Commits 4660bc1, 3c9ffe0, 2dd04dc — FOUND
- pytest 41/41 green, ruff clean — VERIFIED

---
*Phase: 01-foundation-first-digest*
*Completed: 2026-05-21*
