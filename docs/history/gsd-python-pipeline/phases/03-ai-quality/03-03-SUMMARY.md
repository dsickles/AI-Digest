---
phase: 03-ai-quality
plan: "03"
subsystem: api
tags: [rank, gemini, cluster_ranks, briefing, html-renderer]

requires:
  - phase: 03-ai-quality
    plan: "02"
    provides: cluster_summaries, categorize stage, digest.yaml top_n_briefing, category sections
provides:
  - pipeline/llm/rank.py + rank_v1 prompt (impact>novelty>recency)
  - cluster_ranks table and checkpoint helpers
  - rank orchestrator stage and CLI subcommand
  - numbered Briefing — Top N section at digest top (PIPELINE-03)
  - rank-ordered cards within category sections
affects: [03-04-rollup, 03-05-governance]

tech-stack:
  added: []
  patterns:
    - "Stage-level rank checkpoint — single LLM call per week, skip when rank_v1 rows exist"
    - "Briefing duplicates Top N cards in category sections per DISPLAY-03"
    - "published_at fallback sort on rank LLM api_error/quota_exhausted"

key-files:
  created:
    - pipeline/llm/rank.py
    - pipeline/llm/prompts/rank_v1.md
    - tests/test_rank.py
    - tests/llm/test_rank_determinism.py
    - tests/test_render_briefing.py
  modified:
    - store/migrations/004_dedup_categorize_rank_rollup.sql
    - store/schema.sql
    - store/db.py
    - pipeline/orchestrator.py
    - pipeline/run.py
    - pipeline/render/html.py

key-decisions:
  - "Briefing cards duplicate in category sections (ROADMAP SC #2 / DISPLAY-03 landing pattern)"
  - "Unranked legacy cards fall back to recency sort within category sections"

patterns-established:
  - "rank_week_clusters mirrors categorize with RankResponse + global rank_position post-process"
  - "render_digest reads top_n_briefing from load_digest_config() for Briefing header"

requirements-completed: [PIPELINE-03, PIPELINE-05, PIPELINE-06]

duration: 40min
completed: 2026-05-22
---

# Phase 3 Plan 03: Rank + Briefing Top N Summary

**Flash rank stage with cluster_ranks persistence and numbered Briefing — Top 5 this week at the digest top, category sections sorted by rank**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-05-22T18:20:00Z
- **Completed:** 2026-05-22T18:58:32Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- `cluster_ranks` table with `(cluster_id, week_id, prompt_version)` uniqueness and render-only DB reads (PIPELINE-05)
- `rank_week_clusters` single Gemini Flash call per week; impact>novelty>recency weighting in `rank_v1.md` (D-53, D-61)
- `run_all` order: ingest → dedup → summarize → categorize → **rank** → render; `python -m pipeline.run rank` exposed
- Digest opens with `<section class="briefing">` numbered list capped by `config/digest.yaml` `top_n_briefing: 5` (D-51, D-63)
- Category sections sort by `rank_position` ascending; LOCKED-01 `_partition_cards` unchanged

## Task Commits

1. **Task 1: cluster_ranks schema + rank.py module + rank_v1 prompt** - `3de5d3c` (feat)
2. **Task 2: Rank orchestrator stage + run rank CLI + category section rank sort** - `ec04deb` (feat)
3. **Task 3: Briefing Top N renderer — end-to-end numbered briefing digest** - `709924f` (feat)

## Files Created/Modified

- `pipeline/llm/rank.py` - Weekly single-call ranker with published_at fallback on LLM failure
- `pipeline/llm/prompts/rank_v1.md` - Versioned prompt banning engagement framing (D-31)
- `store/db.py` - insert_cluster_ranks_batch, get_ranks_for_week, get_rank_positions_for_week
- `pipeline/orchestrator.py` - `_rank_week`, `run_rank`, rank_position on DigestCard build path
- `pipeline/render/html.py` - Briefing section, briefing-card class, rank-ordered category sort
- `pipeline/run.py` - `rank` subcommand and updated `all` help text

## Decisions Made

- Briefing Top N cards also appear in their category section (duplicate display per ROADMAP SC #2)
- Rank stage skips LLM when `rank_v1` rows already exist for the week (force flag deferred to 03-05)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None blocking. Live Gemini rank path not exercised in executor environment; unit tests mock the client.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 03-04 (hierarchical rollup): ranked clusters persisted; Briefing HTML structure in place for weekly synthesis slot above briefing
- `cluster_ranks.rank_position` available for rollup input ordering

## Self-Check: PASSED

- FOUND: pipeline/llm/rank.py
- FOUND: pipeline/llm/prompts/rank_v1.md
- FOUND: tests/test_render_briefing.py
- FOUND: .planning/phases/03-ai-quality/03-03-SUMMARY.md
- FOUND: commit 3de5d3c
- FOUND: commit ec04deb
- FOUND: commit 709924f

---
*Phase: 03-ai-quality*
*Completed: 2026-05-22*
