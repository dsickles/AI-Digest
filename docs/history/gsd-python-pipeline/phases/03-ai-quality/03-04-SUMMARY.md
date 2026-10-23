---
phase: 03-ai-quality
plan: "04"
subsystem: api
tags: [rollup, gemini, weekly_rollups, synthesis, html-renderer]

requires:
  - phase: 03-ai-quality
    plan: "03"
    provides: cluster_ranks, Briefing Top N HTML slot above categories
provides:
  - pipeline/llm/rollup.py + rollup_category_v1 / rollup_weekly_v1 prompts
  - weekly_rollups table and checkpoint helpers
  - rollup orchestrator stage and CLI subcommand
  - weekly synthesis + category mini-rollup renderer (PIPELINE-04)
affects: [03-05-governance]

tech-stack:
  added: []
  patterns:
    - "Hierarchical rollup — 4 category Flash minis + 1 weekly synthesis from minis only (D-55)"
    - "Stage-level rollup checkpoint — skip when prompt_version rows exist"
    - "Render reads narrative_md from DB only; weekly failure shows one-line notice"

key-files:
  created:
    - pipeline/llm/rollup.py
    - pipeline/llm/prompts/rollup_category_v1.md
    - pipeline/llm/prompts/rollup_weekly_v1.md
    - tests/test_rollup.py
    - tests/llm/test_rollup_voice.py
    - tests/test_render_rollup.py
  modified:
    - store/migrations/004_dedup_categorize_rank_rollup.sql
    - store/schema.sql
    - store/db.py
    - pipeline/orchestrator.py
    - pipeline/run.py
    - pipeline/render/html.py

key-decisions:
  - "Weekly synthesis input is four mini paragraphs only — not raw cluster lists (PITFALLS #14)"
  - "Failed category mini rollups omit paragraph silently; failed weekly shows WEEKLY_ROLLUP_FAILURE_COPY"

patterns-established:
  - "rollup_category / rollup_weekly mirror summarize exception taxonomy via classify_llm_exception"
  - "Document order in main: weekly synthesis/failure → briefing → category sections with mini openers"

requirements-completed: [PIPELINE-04, PIPELINE-05, PIPELINE-06]

duration: 45min
completed: 2026-05-22
---

# Phase 3 Plan 04: Hierarchical Rollup Summary

**Four Flash category minis plus weekly synthesis persisted in weekly_rollups — editor note and section openers render from DB**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-05-22T19:05:00Z
- **Completed:** 2026-05-22T19:50:00Z
- **Tasks:** 3
- **Files modified:** 13

## Accomplishments

- `weekly_rollups` table with scope discriminator (`category:*` + `weekly`) and token/cost metadata (D-04)
- `rollup_category` / `rollup_weekly` using `gemini-2.5-flash` at temperature 0.3 with D-57 ban list in prompts
- `run_all` order: … → rank → **rollup** → render; `python -m pipeline.run rollup` exposed (D-19)
- Digest `<main>` opens with weekly synthesis or plain-English failure notice, then Briefing, then categories with mini openers
- LOCKED-01 preserved — rollup uses separate render helpers; `_partition_cards` unchanged

## Task Commits

1. **Task 1: weekly_rollups schema + rollup.py + both rollup prompts** - `5d63a29` (feat)
2. **Task 2: Rollup orchestrator stage + run rollup CLI** - `14b09f6` (feat)
3. **Task 3: Weekly synthesis + mini-rollup renderer** - `664809a` (feat)

## Files Created/Modified

- `pipeline/llm/rollup.py` - Hierarchical five-call rollup with prose output and failure degradation
- `pipeline/llm/prompts/rollup_category_v1.md` - 80–120 word mini prompt with ban list
- `pipeline/llm/prompts/rollup_weekly_v1.md` - 150–200 word synthesis from four minis only
- `store/db.py` - get_rollup, insert_weekly_rollup, get_rollups_for_week, delete_rollups_for_week
- `pipeline/orchestrator.py` - `_rollup_week`, `run_rollup`, RunStats rollup counters
- `pipeline/render/html.py` - weekly-synthesis, rollup-failure-notice, category-mini-rollup sections

## Decisions Made

- Weekly synthesis never receives raw cluster lists — only stored mini paragraphs (D-55)
- Re-run skips existing rollup rows when prompt_version matches (PIPELINE-05 stage checkpoint)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None blocking. Live Gemini rollup path not exercised in executor environment; unit tests mock the client.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 03-05 (cost governance + pipeline_report.json): rollup stage counters available on RunStats
- `PARTIAL_PUBLISH_COPY` constant reserved in html.py for 03-05 partial-publish header

## Self-Check: PASSED

- FOUND: pipeline/llm/rollup.py
- FOUND: pipeline/llm/prompts/rollup_category_v1.md
- FOUND: pipeline/llm/prompts/rollup_weekly_v1.md
- FOUND: tests/test_render_rollup.py
- FOUND: .planning/phases/03-ai-quality/03-04-SUMMARY.md
- FOUND: commit 5d63a29
- FOUND: commit 14b09f6
- FOUND: commit 664809a

---
*Phase: 03-ai-quality*
*Completed: 2026-05-22*
