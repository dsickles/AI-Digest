---
phase: 01-foundation-first-digest
plan: "04"
subsystem: infra
tags: [argparse, iso-week, cli, backfill, pytest]

requires:
  - phase: 01-foundation-first-digest
    provides: orchestrator run_all, week.py skeleton, argparse entry
provides:
  - ISO week parse_week_id validation and inclusive Sunday week_bounds
  - run_ingest / run_summarize / run_render / run_all stage functions
  - CLI subcommands with --week backfill threading (D-19, D-20, D-21)
  - README Manual run / backfill section and integration tests (D-12, D-22)
affects: [01-05, phase-5-cron]

tech-stack:
  added: []
  patterns:
    - "week_id threaded from CLI only; datetime.now() confined to week.py and render footer"
    - "Lazy adapter/LLM imports in orchestrator for render import purity (D-20)"

key-files:
  created:
    - tests/test_pipeline.py
  modified:
    - pipeline/week.py
    - pipeline/orchestrator.py
    - pipeline/run.py
    - store/db.py
    - README.md
    - tests/test_week.py

key-decisions:
  - "week_bounds returns inclusive Sunday 23:59:59 UTC (not half-open Monday) per D-10"
  - "Lazy imports in orchestrator instead of package split — render path stays LLM-free"

patterns-established:
  - "CLI subcommands ingest|summarize|render|all; bare invocation aliases all (D-19)"
  - "render subcommand uses _build_cards_from_db — no LLM or adapter imports at module load"

requirements-completed: [PIPELINE-01]

duration: 45min
completed: 2026-05-21
---

# Phase 1 Plan 04: ISO Week CLI and Subcommands Summary

**Argparse subcommands with `--week YYYY-Www` backfill threading, lazy render/LLM import boundary, and README discoverability tests**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-05-21T23:50:00Z
- **Completed:** 2026-05-21T00:10:00Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- `parse_week_id` validates `YYYY-Www` regex plus ISO week existence; `week_bounds('2026-W19')` returns Mon 2026-05-04 00:00 UTC through Sun 2026-05-10 23:59:59 UTC
- Orchestrator split into `run_ingest`, `run_summarize`, `run_render`, `run_all` — each accepts `week_id: str` only; adapters/LLM imported lazily inside ingest/summarize paths
- CLI exposes `ingest`, `summarize`, `render`, `all` with global `--week`; bare `python -m pipeline.run` aliases `all` (D-19)
- README documents backfill with two `--week 2026-W19` examples and subcommands table (D-12, D-22)
- Integration tests verify `--week` threading and render/LLM isolation

## Task Commits

1. **Task 1: ISO week utilities and parameter threading** - `809e190` (refactor)
2. **Task 2: CLI subcommands ingest summarize render all** - `2f458ab` (feat)
3. **Task 3: README discoverability and --week integration test** - `d2f07dd` (test)

**Plan metadata:** `c48987b` (docs: complete plan)

## Files Created/Modified

- `pipeline/week.py` — inclusive Sunday `week_bounds`; `parse_week_id` ISO validation
- `pipeline/orchestrator.py` — four public stage functions; lazy adapter/LLM imports; `_build_cards_from_db` for render-only path
- `pipeline/run.py` — subcommand argparse; `--week` on parent and subcommands; bare → `all`
- `store/db.py` — inclusive `published_at <= week_end` filter
- `README.md` — Manual run / backfill section with subcommands table
- `tests/test_week.py` — exact 2026-W19 bounds assertions; invalid ISO week 2021-W53
- `tests/test_pipeline.py` — CLI threading, render/LLM isolation, subprocess import audit

## Decisions Made

- Kept single `orchestrator.py` module with lazy imports rather than splitting into a package — satisfies D-20 import audit without structural churn
- Changed `week_bounds` from half-open Mon→Mon to inclusive Mon→Sun 23:59:59 per plan task 1 and D-10 wording

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Import audit test polluted sys.modules**
- **Found during:** Task 3 (test suite run)
- **Issue:** In-process `sys.modules` clearing in `test_render_import_does_not_load_adapters_or_llm` caused `test_enrichment_low_confidence_when_text_still_short` to fail (patch on `prepare_input_text` no longer applied)
- **Fix:** Moved import audit to a subprocess so the main test process module cache stays intact
- **Files modified:** `tests/test_pipeline.py`
- **Verification:** `uv run pytest -x -q` — 34 passed
- **Committed in:** `d2f07dd`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Test isolation fix required for suite green; no production code scope change.

## Issues Encountered

- Live `all --week 2026-W19` E2E skipped in sandbox (requires network + Gemini key) — manual follow-up per plan verification notes

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 01-05 (structlog hardening, `last_run.md`, `pipeline_runs` metrics, HTML polish, expanded pytest) can proceed on Wave 5
- `--week` backfill operable from CLI and docs; render path confirmed LLM-free for fast HTML iteration

## Self-Check: PASSED

- `pipeline/week.py` — FOUND
- `pipeline/run.py` — FOUND
- `tests/test_pipeline.py` — FOUND
- Commits `809e190`, `2f458ab`, `d2f07dd`, `c48987b` — FOUND

---
*Phase: 01-foundation-first-digest*
*Completed: 2026-05-21*
