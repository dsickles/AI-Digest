---
status: gaps_found
phase: 03-ai-quality
verified_at: 2026-05-22T20:30:00Z
must_haves_total: 5
must_haves_passed: 2
must_haves_failed: 2
must_haves_human: 1
requirements_total: 10
requirements_passed: 8
requirements_failed: 2
gaps:
  - truth: "Re-running the pipeline twice in the same week produces the same digest (idempotent)"
    status: failed
    reason: "delete_clusters_for_week removes story_clusters while cluster_summaries and cluster_ranks still reference old cluster_id values; second run_all raises sqlite3.IntegrityError at dedup"
    artifacts:
      - path: store/db.py
        issue: "delete_clusters_for_week (L410-421) does not delete cluster_summaries or cluster_ranks before DELETE FROM story_clusters"
      - path: pipeline/dedup/cluster.py
        issue: "run_dedup_for_week always calls delete_clusters_for_week before rebuild (L112)"
    missing:
      - "Add delete_cluster_artifacts_for_week deleting cluster_summaries, cluster_ranks, and weekly_rollups for week_id before cluster delete"
      - "Integration test test_run_all_twice_same_week asserting no exception and stable briefing output"
  - truth: "Rank/rollup checkpoints remain valid after dedup rebuild"
    status: failed
    reason: "_rank_week and _rollup_week skip when any week-level row exists without verifying rows JOIN current story_clusters; latent after CR-01 fix if ranks/rollups not cleared"
    artifacts:
      - path: pipeline/orchestrator.py
        issue: "_rank_week L596-599 skip on get_ranks_for_week count; _rollup_week L772-777 L823-825 skip on get_rollup existence"
    missing:
      - "Delete rank/rollup rows on dedup rebuild (same helper as CR-01) and/or ranks_cover_current_clusters integrity check before skip"
score: 2/5 must-haves verified (2 human-deferred)
overrides_applied: 0
human_verification:
  - test: "Open out/digest-{week_id}.html from a live run_all with real sources and GEMINI_API_KEY; skim start to finish"
    expected: "Coherent weekly narrative, Top N briefing, category sections, and attributions readable in ~15 minutes; Core Value hypothesis feels testable"
    why_human: "Readability, narrative quality, and 15-minute skim time cannot be verified programmatically"
---

# Phase 3: AI Quality Verification Report

**Phase Goal:** Transform a chronological item list into a curated weekly briefing — deduped story clusters, categorized tabs-ready items, ranked Top N, narrative roll-up, and bounded LLM spend  
**Verified:** 2026-05-22T20:30:00Z  
**Status:** gaps_found  
**Mode:** mvp

## Executive Summary

Phase 3 delivers the full pipeline architecture on the **first** `run_all` pass: Tier 0/1 dedup, canonical-only summarize, LLM categorize/rank/rollup, Briefing renderer, WeekBudget governance, and `pipeline_report.json`. Automated tests (139 passed) cover dedup, categorization, ranking, rollup rendering, budget halt, and partial summarize resume.

**Merge blocker:** A second `run_all` for the same ISO week crashes with `IntegrityError: FOREIGN KEY constraint failed` during dedup rebuild (CR-01, independently reproduced). This breaks PIPELINE-05/06 for the normal GHA/cron re-run path. Rank/rollup stage checkpoints use week-level row-exists skips that would serve stale data if dedup invalidation were partial (CR-02).

## Goal-Backward Analysis (ROADMAP Success Criteria)

### SC1 — Near-duplicate stories collapse into one card with "also covered by" attributions

**Verdict: PASS**

| Evidence | Location |
|----------|----------|
| URL canonicalization strips `utm_*` and tracking params | `pipeline/dedup/url.py` L8-34, L49-80 |
| RapidFuzz `token_set_ratio` at threshold 0.85 | `pipeline/dedup/title_fuzzy.py` L21-32; `config/digest.yaml` L4-5 |
| Union-find clustering + canonical pick (longest content) | `pipeline/dedup/cluster.py` L76-138 |
| Dedup before summarize; non-canonical members skip LLM | `pipeline/orchestrator.py` L323-335, L336-352; `tests/test_pipeline_dedup_order.py` |
| "Also covered by" attribution on clustered cards | `pipeline/render/html.py` L50; `tests/test_render_dedup_attribution.py` |
| Cluster integration | `tests/dedup/test_cluster.py` |

Briefing Top N will not fill with duplicate launch variants when dedup runs successfully on the first pass.

### SC2 — Each story categorized into one topic, ranked; digest opens with weekly narrative + numbered Top N

**Verdict: PASS** (first-run path)

| Evidence | Location |
|----------|----------|
| Exactly one category enum per cluster in `cluster_summaries` | `store/migrations/004_*.sql` L29-31; `pipeline/llm/categorize.py` |
| Global rank positions persisted | `pipeline/llm/rank.py`; `store/db.py` `insert_cluster_ranks_batch` |
| Weekly synthesis precedes Briefing section | `pipeline/render/html.py` L628-636; `tests/test_render_rollup.py::test_weekly_synthesis_precedes_briefing` |
| Numbered "Briefing — Top 5 this week" | `tests/test_render_briefing.py::test_briefing_section_top_five_from_ten_ranked_clusters` |
| Category sections with Title Case labels | `tests/test_render_categories.py` |
| `top_n_briefing: 5` configurable | `config/digest.yaml` L2; CLI `--top-n` in `tests/test_cli_phase3.py` |

Renderer reads DB only for rank/rollup (PIPELINE-05 render idempotency verified in `tests/test_cli_phase3.py::test_double_render_produces_identical_html`).

### SC3 — Same-week re-run idempotent; crash resume does not re-bill summarized items

**Verdict: FAIL**

| Sub-requirement | Status | Evidence |
|-----------------|--------|----------|
| Summarize checkpoint skips existing rows | PASS | `pipeline/orchestrator.py` L336-352; `tests/test_cli_phase3.py::test_partial_summarize_resume_skips_completed` |
| Dedup deterministic rebuild | PASS (single run) | `tests/dedup/test_cluster.py`; dedup is LLM-free |
| **Second `run_all` same week** | **FAIL** | Reproduced: first run OK, second run `IntegrityError` at `store/db.py:421` |
| Rank/rollup checkpoint integrity after rebuild | **FAIL (latent)** | `_rank_week` L596-599 skips on any `cluster_ranks` row; `_rollup_week` L772-777 skips on existing rollup without cluster-set validation |

**CR-01 reproduction (verifier-run, mocked LLM):**

```
First run: OK  (clusters=1 cluster_summaries=1 cluster_ranks=1)
Second run: IntegrityError: FOREIGN KEY constraint failed
  at delete_clusters_for_week → DELETE FROM story_clusters
```

Root cause: `delete_clusters_for_week` (`store/db.py:410-421`) deletes `cluster_members` and `story_clusters` but leaves `cluster_summaries` and `cluster_ranks` referencing deleted cluster IDs. FK enforcement (`PRAGMA foreign_keys = ON`) blocks the delete.

**CR-02:** Code review finding confirmed in source — rank skip uses `if existing:` on week-level count (`orchestrator.py:596-599`), not a JOIN against live `story_clusters`. Even attempting manual cluster delete with stale rank rows triggers FK failure, demonstrating coupled artifact invalidation is required.

### SC4 — Structured `pipeline_report.json` per run; LLM spend within $2/week with hard stop

**Verdict: PARTIAL FAIL**

| Sub-requirement | Status | Evidence |
|-----------------|--------|----------|
| Report written each successful run | PASS | `pipeline/reporting/pipeline_report.py`; `tests/reporting/test_pipeline_report_schema.py` |
| Schema v1 with stages, budget, source_health | PASS | `build_pipeline_report` L204-242; test asserts `schema_version == 1`, `budget.cap_usd == 2.0` |
| Hard stop $2/week configurable | PASS | `config/digest.yaml` L7-9; `WeekBudget` in `pipeline/budget.py`; `tests/budget/test_budget_halt.py` |
| Meta reservation + partial publish | PASS | `pipeline/budget.py` L51-106; budget halt test |
| **Report on re-run** | **FAIL** | Second `run_all` crashes before `_finalize` / `write_pipeline_report` |
| Summarize stage cost attribution | WARNING | `pipeline_report.py` L227-229: `cost_usd_estimate - rollup_cost_usd` includes categorize+rank spend (WR-03) |

Pre-flight baseline uses current week not prior week (`budget.py:109-122`, WR-02) — accuracy gap, not a blocker for cap enforcement.

### SC5 — Human reader can skim full digest in ~15 minutes; Core Value hypothesis testable

**Verdict: HUMAN NEEDED**

Implementation provides weekly synthesis, Top N briefing, and category sections in plain HTML. Narrative quality, pacing, and skim-time are subjective and require a human with live sources + `GEMINI_API_KEY`.

## Requirement Traceability

| Requirement | Description | Status | Code / Test Evidence |
|-------------|-------------|--------|----------------------|
| **DEDUP-01** | URL canonicalization before dedup | PASS | `pipeline/dedup/url.py`; `tests/dedup/test_url_canonical.py` |
| **DEDUP-02** | Title fuzzy clustering via RapidFuzz | PASS | `pipeline/dedup/title_fuzzy.py`; `tests/dedup/test_title_fuzzy.py`, `test_cluster.py::test_fuzzy_title_merge` |
| **DEDUP-03** | Cluster preserves all source attributions | PASS | `cluster_members` DDL; `get_cluster_members`; `tests/test_render_dedup_attribution.py` |
| **DEDUP-04** | Dedup before LLM summarize | PASS | `run_all` stage order; `tests/test_pipeline_dedup_order.py`, `test_non_canonical_member_skips_summary_row` |
| **PIPELINE-02** | LLM categorize into one of four topics | PASS | `pipeline/llm/categorize.py`; `tests/test_categorize.py`, `tests/llm/test_categorize_golden.py` |
| **PIPELINE-03** | Rank and select Top N for Briefing | PASS | `pipeline/llm/rank.py`; `tests/test_rank.py`, `tests/test_render_briefing.py` |
| **PIPELINE-04** | Weekly narrative roll-up | PASS | `pipeline/llm/rollup.py`; `tests/test_rollup.py`, `tests/test_render_rollup.py` |
| **PIPELINE-05** | Pipeline idempotent on re-run | **FAIL** | Render-only idempotency passes; full `run_all` twice crashes (CR-01). No `test_run_all_twice_same_week` |
| **PIPELINE-06** | Crash-safe checkpointing | **FAIL** | Summarize resume PASS; full pipeline re-run FAIL at dedup; rank/rollup stale-skip risk (CR-02) |
| **OBS-02** | Structured run report with cost/errors | PARTIAL | Report schema PASS; per-stage summarize cost misattributed (WR-03); re-run cannot complete |

## Gaps (Closure Plan)

1. **CR-01 — FK crash on second weekly run** (Critical)  
   - **Missing:** `delete_cluster_artifacts_for_week` deleting `cluster_summaries`, `cluster_ranks`, and `weekly_rollups` before `story_clusters`.  
   - **Files:** `store/db.py`, call from `pipeline/dedup/cluster.py` or `delete_clusters_for_week`.  
   - **Test:** `tests/test_run_all_twice_same_week.py` — mock LLM, run `run_all` twice, assert no exception and briefing section present.

2. **CR-02 — Stale rank/rollup checkpoints** (Critical, defense-in-depth)  
   - **Missing:** Cluster-set integrity check before rank/rollup skip, or artifact deletion bundled with dedup rebuild.  
   - **Files:** `pipeline/orchestrator.py` (`_rank_week`, `_rollup_week`).

3. **WR-03 — pipeline_report summarize cost misattribution** (Warning)  
   - **Missing:** Track per-stage costs on `RunStats` or derive summarize cost from `item_summaries` aggregate.  
   - **Files:** `pipeline/reporting/pipeline_report.py`, `pipeline/orchestrator.py`.

4. **WR-01 — Cascade title_changed never wired** (Warning)  
   - **Missing:** Compare normalized titles on ingest; pass `title_changed=True` to `plan_invalidation`.  
   - **Files:** `pipeline/orchestrator.py` `_apply_cascade_for_item` L1115.

5. **WR-02 — Pre-flight baseline uses current week** (Warning)  
   - **Files:** `pipeline/budget.py` `baseline_per_item_from_runs`.

6. **IN-01 — No integration test for same-week re-run** (Info)  
   - Would have caught CR-01.

## Human Verification Items

1. **15-minute skim test** — Run `uv run python -m pipeline.run all --week {current}` with live feeds and `GEMINI_API_KEY`. Open `out/digest-{week}.html`. Confirm weekly narrative + Top N + categories tell a coherent "what happened in AI this week" story within ~15 minutes.

2. **Visual Briefing quality** — Confirm Top N items are genuinely distinct stories (not near-duplicates that dedup missed) and ranked by perceived importance.

3. **Budget behavior under real volume** — After a full week of 8 sources, confirm total cost in `out/pipeline_report.json` stays under `$2.00` and partial-publish notice appears if cap hit mid-run.

## Test Evidence

```
uv run pytest -v --tb=no
======================== 139 passed in 87.96s ========================
```

Phase 3-specific coverage includes:

- Dedup: `tests/dedup/` (5 files), `tests/test_pipeline_dedup_order.py`
- Categorize: `tests/test_categorize.py`, `tests/llm/test_categorize_golden.py`
- Rank: `tests/test_rank.py`, `tests/llm/test_rank_determinism.py`
- Rollup: `tests/test_rollup.py`, `tests/test_render_rollup.py`
- Briefing: `tests/test_render_briefing.py`
- Budget: `tests/budget/test_budget_halt.py`
- Report: `tests/reporting/test_pipeline_report_schema.py`
- CLI/idempotency (partial): `tests/test_cli_phase3.py`
- LOCKED-01 regression: `tests/render/test_partition_cards_phase3.py`

**Gap in test suite:** No test exercises consecutive `run_all` for the same `week_id` through dedup → rank → render (CR-01).

## CONTEXT.md Decision Honor Check

| Decision | Honored? | Notes |
|----------|----------|-------|
| Dedup before summarize (D-67) | Yes | Orchestrator stage order verified |
| Hierarchical rollup 4+1 calls (D-55) | Yes | `_rollup_week` category loop + weekly |
| $2 hard stop + $0.10 meta reservation (D-59/D-60) | Yes | `config/digest.yaml`, `WeekBudget` |
| Briefing Top N at top of main (DISPLAY-03) | Yes | Renderer + tests |
| LOCKED-01 footer routing unchanged | Yes | `test_partition_cards_phase3.py` |
| Same-week idempotent re-run (PIPELINE-05) | **No** | CR-01 |

## Recommendation

**Do not treat Phase 3 as complete until CR-01 and CR-02 are fixed and covered by an integration test.** First-run functionality is solid; the re-run path used by cron/GHA is broken.

Suggested fix order (matches `03-REVIEW.md`):

1. `delete_cluster_artifacts_for_week` + call before cluster rebuild  
2. Harden rank/rollup skip checks (cluster coverage fingerprint)  
3. Add `test_run_all_twice_same_week`  
4. Fix pipeline_report stage cost attribution before Phase 4 OBS-01 consumption

---

_Verified: 2026-05-22T20:30:00Z_  
_Verifier: Claude (gsd-verifier)_
