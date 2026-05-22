---
phase: 03-ai-quality
plan: "02"
subsystem: api
tags: [categorize, gemini, cluster_summaries, html-renderer, digest-yaml]

requires:
  - phase: 03-ai-quality
    plan: "01"
    provides: story_clusters schema, canonical-only summarize, dedup orchestrator
provides:
  - pipeline/llm/exceptions.py shared classify_llm_exception
  - pipeline/llm/categorize.py + categorize_v1 prompt
  - cluster_summaries table and checkpoint helpers
  - config/digest.yaml + load_digest_config()
  - categorize orchestrator stage and CLI subcommand
  - per-category section HTML renderer (PIPELINE-02)
affects: [03-03-rank, 03-04-rollup, 03-05-governance]

tech-stack:
  added: []
  patterns:
    - "Item-level categorize checkpoint via get_existing_cluster_summary skip"
    - "D-49 source-tag fallback with category_confidence observability strings"
    - "Category sections with fixed enum order and Title Case CATEGORY_LABELS"

key-files:
  created:
    - pipeline/llm/exceptions.py
    - pipeline/llm/categorize.py
    - pipeline/llm/prompts/categorize_v1.md
    - config/digest.yaml
    - tests/test_categorize.py
    - tests/llm/test_categorize_golden.py
    - tests/test_render_categories.py
  modified:
    - pipeline/llm/summarize.py
    - pipeline/config.py
    - pipeline/orchestrator.py
    - pipeline/run.py
    - pipeline/render/html.py
    - store/migrations/004_dedup_categorize_rank_rollup.sql
    - store/schema.sql
    - store/db.py

key-decisions:
  - "Uncategorized render-only cards fall back to technical section for readable legacy path"
  - "category_confidence stored as TEXT to hold model floats and D-49 sentinel strings"

patterns-established:
  - "categorize_cluster mirrors summarize_item with CategorizeResult + per-row commit"
  - "render_digest groups _partition_cards main feed into category-section blocks"

requirements-completed: [PIPELINE-02, PIPELINE-05, PIPELINE-06]

duration: 35min
completed: 2026-05-22
---

# Phase 3 Plan 02: Categorize Summary

**Shared LLM exception taxonomy, Flash-Lite cluster categorization with source-tag fallback, and digest HTML grouped into Edtech/Business/Technical/Design sections**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-05-22T19:00:00Z
- **Completed:** 2026-05-22T19:35:00Z
- **Tasks:** 3
- **Files modified:** 15

## Accomplishments

- `classify_llm_exception` extracted to `pipeline/llm/exceptions.py`; summarize imports shared helper (LOCKED-01)
- `cluster_summaries` table with `(cluster_id, week_id, prompt_version)` uniqueness and checkpoint skip
- `categorize_cluster` at temperature 0 with D-49 fallbacks (`fallback_source_tag`, `quota_exhausted_fallback`)
- `config/digest.yaml` lands with `top_n_briefing: 5` and pipeline cost knobs
- `run_all` order: ingest → dedup → summarize → **categorize** → render; `python -m pipeline.run categorize` exposed
- Main feed renders fixed-order category sections with Title Case headers (D-65: label on h2 only)

## Task Commits

1. **Task 1: Shared exceptions + categorize module + schema** - `5fbb03b` (feat)
2. **Task 2: digest.yaml + orchestrator categorize stage + CLI** - `97e296e` (feat)
3. **Task 3: Per-category section renderer** - `76f7ca4` (feat)

## Files Created/Modified

- `pipeline/llm/exceptions.py` - Shared quota/api exception classifier
- `pipeline/llm/categorize.py` - Flash-Lite categorize stage with structured JSON enum
- `pipeline/llm/prompts/categorize_v1.md` - Versioned prompt with source_typically_covers hint (D-48)
- `config/digest.yaml` - Runtime knobs for briefing size, dedup threshold, budget caps
- `store/db.py` - get_existing_cluster_summary, insert_cluster_summary, category map helpers
- `pipeline/orchestrator.py` - `_categorize_week_clusters`, `run_categorize`, run_all wiring
- `pipeline/render/html.py` - CATEGORY_LABELS sections replacing flat chronological main list

## Decisions Made

- Cards without stored category (render-only legacy path) bucket into `technical` so digest stays readable before categorize runs
- `category_confidence` column is TEXT to store both numeric model confidence and D-49 sentinel strings

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None blocking. Full live Gemini categorize path not exercised in executor environment; unit tests mock the client.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 03-03 (rank + Briefing Top N): `cluster_summaries.category` populated; digest sections grouped
- `load_digest_config().top_n_briefing` available for rank/Briefing renderer

## Self-Check: PASSED

- FOUND: pipeline/llm/categorize.py
- FOUND: config/digest.yaml
- FOUND: tests/test_render_categories.py
- FOUND: .planning/phases/03-ai-quality/03-02-SUMMARY.md
- FOUND: commit 5fbb03b
- FOUND: commit 97e296e
- FOUND: commit 76f7ca4

---
*Phase: 03-ai-quality*
*Completed: 2026-05-22*
