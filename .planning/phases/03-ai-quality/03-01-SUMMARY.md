---
phase: 03-ai-quality
plan: "01"
subsystem: database
tags: [rapidfuzz, dedup, sqlite, union-find, html-renderer]

requires:
  - phase: 02-expand-ingestion
    provides: items table, summary_status routing, orchestrator stage pattern
provides:
  - story_clusters + cluster_members schema (migration 004)
  - pipeline/dedup/ Tier 0 URL + Tier 1 fuzzy + union-find engine
  - ingest → dedup → summarize → render pipeline order
  - canonical-only LLM summarize gate
  - "Also covered by" attribution on clustered canonical cards
  - python -m pipeline.run dedup subcommand
affects: [03-02-categorize, 03-03-rank, 03-05-governance]

tech-stack:
  added: [rapidfuzz>=3.13.0]
  patterns:
    - "Deterministic stage-level dedup checkpoint (delete/rebuild per week_id)"
    - "Canonical representative gate before summarize_item()"
    - "AlsoCoveredMember tuple on DigestCard for D-64 attribution"

key-files:
  created:
    - store/migrations/004_dedup_categorize_rank_rollup.sql
    - pipeline/dedup/url.py
    - pipeline/dedup/title_fuzzy.py
    - pipeline/dedup/cluster.py
    - tests/dedup/
    - tests/test_pipeline_dedup_order.py
    - tests/test_render_dedup_attribution.py
    - tests/render/test_partition_cards_phase3.py
  modified:
    - pyproject.toml
    - store/schema.sql
    - store/db.py
    - pipeline/orchestrator.py
    - pipeline/run.py
    - pipeline/render/html.py
    - pipeline/reporting/last_run.py

key-decisions:
  - "D-43 token_set_ratio at 0.85 (compare >= 85.0) with NFKC title normalization"
  - "D-44 same ISO week window via week_bounds"
  - "D-45 canonical = longest raw_content; tie-break published_at then item_id"
  - "D-67 dedup is deterministic stage checkpoint — full week rebuild each run"
  - "Redirect fetch disabled in orchestrator dedup path (fetch_redirects=False) for hermetic CI"

patterns-established:
  - "Cluster tables + delete/rebuild idempotency per week_id"
  - "Render shows canonical cards only; non-canonical members appear in also-covered-by line"

requirements-completed: [DEDUP-01, DEDUP-02, DEDUP-03, DEDUP-04, PIPELINE-05, PIPELINE-06]

duration: 45min
completed: 2026-05-22
---

# Phase 3 Plan 01: Dedup Foundation Summary

**Tier 0/1 dedup-before-LLM with union-find clustering, canonical-only summarize, and plain-English "Also covered by" attribution in the digest HTML**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-05-22T14:45:00Z
- **Completed:** 2026-05-22T15:30:00Z
- **Tasks:** 3
- **Files modified:** 18

## Accomplishments

- Migration 004 adds `story_clusters` and `cluster_members`; fresh schema and existing DBs both support `dedup` pipeline phase
- RapidFuzz `token_set_ratio` at threshold 0.85 collapses same-story items before any LLM call
- `run_all` order is ingest → dedup → summarize (canonical only) → render; `python -m pipeline.run dedup` exposed
- Canonical cards render `Also covered by [Source B], [Source C]` with escaped names and `rel=noopener` links
- LOCKED-01 `_partition_cards` routing unchanged; Phase 3 regression tests added at HEAD

## Task Commits

1. **Task 1: migration 004, rapidfuzz, URL/fuzzy modules + unit tests** - `8bec669` (feat)
2. **Task 2: cluster engine + orchestrator dedup + canonical-only summarize** - `980efa3` (feat)
3. **Task 3: renderer attribution + LOCKED-01 tests + last_run counters** - `76216c3` (feat)

## Files Created/Modified

- `pipeline/dedup/url.py` - Tier 0 URL canonicalization with tracking-param deny-list
- `pipeline/dedup/title_fuzzy.py` - NFKC title normalization + RapidFuzz match at 0.85
- `pipeline/dedup/cluster.py` - Union-find clustering engine writing cluster tables
- `store/migrations/004_dedup_categorize_rank_rollup.sql` - Cluster DDL
- `store/db.py` - Cluster CRUD helpers + idempotent pipeline_runs phase expansion
- `pipeline/orchestrator.py` - `_dedup_week`, `run_dedup`, summarize canonical gate, card enrichment
- `pipeline/render/html.py` - `ALSO_COVERED_*` constants and `.also-covered-by` rendering
- `pipeline/reporting/last_run.md` path via `last_run.py` - `clusters_created` / `items_clustered` counters

## Decisions Made

- Disabled HTTP redirect follow during orchestrator dedup (`fetch_redirects=False`) to keep integration tests hermetic; `resolve_final_url` remains available for future opt-in
- When no clusters exist for a week (legacy render-only path), all items treated as canonical for backward compatibility

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pipeline_runs CHECK constraint migration via Python helper**
- **Found during:** Task 1
- **Issue:** SQLite cannot ALTER CHECK to add `dedup` phase; plain SQL migration alone would fail on re-run
- **Fix:** Added `_ensure_pipeline_runs_phases()` in `store/db.py` with idempotent table rebuild
- **Files modified:** store/db.py
- **Committed in:** `8bec669`

**2. [Rule 1 - Bug] Monkeypatch recursion in dedup-order test**
- **Found during:** Task 2
- **Issue:** Test wrapper imported patched `_dedup_week` causing RecursionError
- **Fix:** Capture real function reference before monkeypatch
- **Files modified:** tests/test_pipeline_dedup_order.py
- **Committed in:** `980efa3`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** No scope change; correctness/idempotency preserved

## Issues Encountered

- Full `pytest tests/` including live Gemini tests not run in executor environment; dedup/render suite (84 tests) green with `--ignore=tests/test_summarize.py`

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 03-02 (categorize): cluster tables exist; canonical cards identified per week
- `config/digest.yaml` threshold knob deferred to 03-02 per D-46

## Self-Check: PASSED

- FOUND: store/migrations/004_dedup_categorize_rank_rollup.sql
- FOUND: pipeline/dedup/cluster.py
- FOUND: .planning/phases/03-ai-quality/03-01-SUMMARY.md
- FOUND: commit 8bec669
- FOUND: commit 980efa3
- FOUND: commit 76216c3

---
*Phase: 03-ai-quality*
*Completed: 2026-05-22*
