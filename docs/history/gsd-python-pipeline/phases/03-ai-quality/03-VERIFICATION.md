---
phase: 03-ai-quality
verified: 2026-05-23T12:25:00Z
status: human_needed
score: 4/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 2/5
  gaps_closed:
    - "Re-running the pipeline twice in the same week produces the same digest (idempotent)"
    - "Rank/rollup checkpoints remain valid after dedup rebuild"
  gaps_remaining: []
  regressions: []
must_haves_total: 5
must_haves_passed: 4
must_haves_failed: 0
must_haves_human: 1
requirements_total: 10
requirements_passed: 10
requirements_failed: 0
human_verification:
  - test: "Open out/digest-{week_id}.html from a live run_all with real sources and GEMINI_API_KEY; skim start to finish"
    expected: "Coherent weekly narrative, Top N briefing, category sections, and attributions readable in ~15 minutes; Core Value hypothesis feels testable"
    why_human: "Readability, narrative quality, and 15-minute skim time cannot be verified programmatically"
---

# Phase 3: AI Quality Verification Report

**Phase Goal:** Transform a chronological item list into a curated weekly briefing — deduped story clusters, categorized tabs-ready items, ranked Top N, narrative roll-up, and bounded LLM spend  
**Verified:** 2026-05-23T12:25:00Z  
**Status:** human_needed  
**Re-verification:** Yes — after gap-closure plans 03-06 through 03-10  
**Mode:** mvp

## Executive Summary

Gap-closure execution resolved both merge blockers from the prior verification (CR-01 FK crash on same-week re-run; CR-02 stale rank/rollup skip gates). Warning items WR-01, WR-02, and WR-03 are also closed in code with targeted tests. All 10 phase requirement IDs trace to passing implementation evidence. Full pytest suite passes (154 tests, verifier-run).

**Remaining gate:** ROADMAP SC5 (15-minute human skim / Core Value hypothesis) requires live-source UAT — unchanged from prior report.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Near-duplicate stories collapse into one card with "also covered by" attributions | ✓ VERIFIED | `pipeline/dedup/url.py`, `title_fuzzy.py`, `cluster.py`; `tests/dedup/`, `tests/test_render_dedup_attribution.py` |
| 2 | Each story categorized, ranked; digest opens with weekly narrative + numbered Top N | ✓ VERIFIED | `pipeline/llm/categorize.py`, `rank.py`, `rollup.py`; `pipeline/render/html.py`; `tests/test_render_briefing.py`, `tests/test_render_rollup.py` |
| 3 | Re-running pipeline twice same week is idempotent; crash resume does not re-bill summarized items | ✓ VERIFIED | CR-01/CR-02 fixes below; `tests/test_run_all_twice_same_week.py`; `tests/test_cli_phase3.py::test_partial_summarize_resume_skips_completed` |
| 4 | Structured `pipeline_report.json` per run; LLM spend within $2/week hard stop | ✓ VERIFIED | `pipeline/reporting/pipeline_report.py`; `pipeline/budget.py`; WR-03 per-stage costs; `tests/reporting/`, `tests/budget/` |
| 5 | Human can skim full digest in ~15 minutes; Core Value hypothesis testable | ? HUMAN NEEDED | Renderer structure present; narrative quality requires live run |

**Score:** 4/5 must-haves verified (1 human-deferred)

## Previously Failed Must-Haves — Resolution Evidence

### CR-01 / IN-01 — Same-week `run_all` IntegrityError (PIPELINE-05)

**Prior failure:** `delete_clusters_for_week` removed `story_clusters` while `cluster_summaries` / `cluster_ranks` still referenced deleted cluster IDs.

**Resolution (Plan 03-06):**

```426:449:store/db.py
def delete_cluster_artifacts_for_week(conn: sqlite3.Connection, week_id: str) -> None:
    """Remove rank/summary/rollup rows for ``week_id`` before cluster delete.
    ...
    """
    conn.execute("DELETE FROM cluster_ranks WHERE week_id = ?", (week_id,))
    conn.execute("DELETE FROM cluster_summaries WHERE week_id = ?", (week_id,))
    conn.execute("DELETE FROM weekly_rollups WHERE week_id = ?", (week_id,))


def delete_clusters_for_week(conn: sqlite3.Connection, week_id: str) -> None:
    """Remove all cluster rows for ``week_id`` before a deterministic rebuild."""
    delete_cluster_artifacts_for_week(conn, week_id)
    ...
```

**Tests:**

- `tests/dedup/test_cluster.py::test_delete_clusters_for_week_clears_artifact_tables` — all four artifact tables empty after delete
- `tests/test_run_all_twice_same_week.py::test_run_all_twice_same_week_no_integrity_error` — two consecutive `run_all` calls succeed; digest contains `Briefing — Top`; `pipeline_report.json` written

### CR-02 — Stale rank/rollup checkpoint skip

**Prior failure:** `_rank_week` / `_rollup_week` skipped on week-level row existence without validating ranks JOIN current `story_clusters`.

**Resolution (Plan 03-07):**

```624:630:pipeline/orchestrator.py
    existing = get_ranks_for_week(conn, week_id, PROMPT_VERSION)
    if existing:
        if ranks_cover_current_clusters(conn, week_id, PROMPT_VERSION):
            log.info("rank.skip_existing", count=len(existing))
            return
        log.info("rank.stale_checkpoint", count=len(existing))
        delete_ranks_for_week(conn, week_id, PROMPT_VERSION)
```

```652:687:store/db.py
def ranks_cover_current_clusters(
    conn: sqlite3.Connection,
    week_id: str,
    prompt_version: str = "rank_v1",
) -> bool:
    ...
```

Rollup category and weekly skip paths gate on `ranks_cover_current_clusters` and delete stale rollup rows before re-run (`orchestrator.py` L806-819, L865-876).

**Tests:** `tests/test_rank_rollup_checkpoint_integrity.py` (5 tests) — orphan rank rows force rank re-run and weekly rollup re-run.

### WR-01 — `title_changed` cascade wiring

**Resolution (Plan 03-08):** Ingest and catch-up pass `old_title` / `new_title` into `_apply_cascade_for_item`; `title_changed` computed via `normalize_title` comparison (`orchestrator.py` L247-279, L1164-1174).

**Test:** `tests/test_cascade_wiring.py::test_apply_cascade_title_only_deletes_summary`

### WR-02 — Pre-flight baseline uses prior ISO week

**Resolution (Plan 03-09):** `baseline_per_item_from_runs` queries `prior_week_id(week_id)` (`pipeline/budget.py` L110-136; `pipeline/week.py` `prior_week_id`).

**Tests:** `tests/budget/test_baseline_prior_week.py` (year boundary + prior-week ratio + fallback)

### WR-03 — Per-stage cost attribution in pipeline report

**Resolution (Plan 03-10):** `RunStats` fields `summarize_cost_usd`, `categorize_cost_usd`, `rank_cost_usd`; `build_pipeline_report` projects them authoritatively (`pipeline/orchestrator.py` L99-102; `pipeline/reporting/pipeline_report.py` L222-238).

**Test:** `tests/reporting/test_pipeline_report_schema.py::test_stage_summarize_cost_excludes_categorize_and_rank`

## Requirement Traceability

| Requirement | Description | Status | Code / Test Evidence |
|-------------|-------------|--------|----------------------|
| **DEDUP-01** | URL canonicalization before dedup | PASS | `pipeline/dedup/url.py`; `tests/dedup/test_url_canonical.py` |
| **DEDUP-02** | Title fuzzy clustering via RapidFuzz | PASS | `pipeline/dedup/title_fuzzy.py`; `tests/dedup/test_title_fuzzy.py`, `test_cluster.py` |
| **DEDUP-03** | Cluster preserves all source attributions | PASS | migration 004 DDL; `get_cluster_members`; `tests/test_render_dedup_attribution.py` |
| **DEDUP-04** | Dedup before LLM summarize | PASS | `run_all` stage order; `tests/test_pipeline_dedup_order.py` |
| **PIPELINE-02** | LLM categorize into four topics | PASS | `pipeline/llm/categorize.py`; `tests/test_categorize.py`, `tests/llm/test_categorize_golden.py` |
| **PIPELINE-03** | Rank and select Top N for Briefing | PASS | `pipeline/llm/rank.py`; `tests/test_rank.py`, `tests/test_render_briefing.py` |
| **PIPELINE-04** | Weekly narrative roll-up | PASS | `pipeline/llm/rollup.py`; `tests/test_rollup.py`, `tests/test_render_rollup.py` |
| **PIPELINE-05** | Pipeline idempotent on re-run | PASS | `tests/test_run_all_twice_same_week.py`; `tests/test_cli_phase3.py::test_double_render_produces_identical_html` |
| **PIPELINE-06** | Crash-safe checkpointing | PASS | Summarize item skip; rank/rollup integrity gates; partial resume in `tests/test_cli_phase3.py` |
| **OBS-02** | Structured run report with cost/errors | PASS | `pipeline/reporting/pipeline_report.py`; per-stage costs; `tests/reporting/test_pipeline_report_schema.py` |

**Requirements score:** 10/10 satisfied

## Key Link Verification

| From | To | Via | Status |
|------|-----|-----|--------|
| `pipeline/dedup/cluster.py` | `store/db.py` | `delete_clusters_for_week` → `delete_cluster_artifacts_for_week` first | ✓ WIRED |
| `pipeline/orchestrator.py` | `store/db.py` | `ranks_cover_current_clusters` before rank/rollup skip | ✓ WIRED |
| `pipeline/orchestrator.py` | `pipeline/cascade.py` | `title_changed` from ingest title comparison | ✓ WIRED |
| `pipeline/budget.py` | `pipeline/week.py` | `prior_week_id` in baseline lookup | ✓ WIRED |
| `pipeline/reporting/pipeline_report.py` | `RunStats` | `stats.summarize_cost_usd` (not total − rollup) | ✓ WIRED |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Same-week double run_all | `uv run pytest tests/test_run_all_twice_same_week.py -q` | exit 0 | ✓ PASS |
| Rank/rollup stale checkpoint | `uv run pytest tests/test_rank_rollup_checkpoint_integrity.py -q` | exit 0 | ✓ PASS |
| WR-03 stage costs | `uv run pytest tests/reporting/test_pipeline_report_schema.py::test_stage_summarize_cost_excludes_categorize_and_rank -q` | exit 0 | ✓ PASS |
| Full regression | `uv run pytest -q --tb=no` | 154 passed | ✓ PASS |

## Anti-Patterns Scan

No `TBD` / `FIXME` / `XXX` markers in gap-closure modified files (`store/db.py`, `pipeline/orchestrator.py`, `pipeline/budget.py`, `pipeline/reporting/pipeline_report.py`, `pipeline/week.py`). No stub handlers or hardcoded empty render paths found in verified artifacts.

## Human Verification Required

1. **15-minute skim test** — Run `uv run python -m pipeline.run all --week {current}` with live feeds and `GEMINI_API_KEY`. Open `out/digest-{week}.html`. Confirm weekly narrative + Top N + categories tell a coherent "what happened in AI this week" story within ~15 minutes.

2. **Visual Briefing quality** — Confirm Top N items are genuinely distinct stories and ranked by perceived importance.

3. **Budget behavior under real volume** — After a full week of 8 sources, confirm total cost in `out/pipeline_report.json` stays under `$2.00` and partial-publish notice appears if cap hit mid-run.

## Recommendation

**Automated verification passes.** Phase 3 code meets all ROADMAP success criteria except SC5 (subjective reader experience). Proceed to Phase 4 after human UAT on a live digest, or accept SC5 deferral per project workflow.

---

_Verified: 2026-05-23T12:25:00Z_  
_Verifier: Claude (gsd-verifier)_
