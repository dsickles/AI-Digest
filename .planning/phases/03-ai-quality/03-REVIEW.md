---
status: issues
phase: 03-ai-quality
depth: standard
files_reviewed: 26
critical: 2
warning: 4
info: 2
generated: 2026-05-22T20:15:00Z
files_reviewed_list:
  - store/migrations/004_dedup_categorize_rank_rollup.sql
  - store/schema.sql
  - store/db.py
  - pipeline/dedup/url.py
  - pipeline/dedup/title_fuzzy.py
  - pipeline/dedup/cluster.py
  - pipeline/llm/exceptions.py
  - pipeline/llm/summarize.py
  - pipeline/llm/categorize.py
  - pipeline/llm/rank.py
  - pipeline/llm/rollup.py
  - pipeline/llm/prompts/categorize_v1.md
  - pipeline/llm/prompts/rank_v1.md
  - pipeline/llm/prompts/rollup_category_v1.md
  - pipeline/llm/prompts/rollup_weekly_v1.md
  - pipeline/budget.py
  - pipeline/cascade.py
  - pipeline/config.py
  - config/digest.yaml
  - pipeline/orchestrator.py
  - pipeline/run.py
  - pipeline/render/html.py
  - pipeline/reporting/pipeline_report.py
  - pipeline/reporting/last_run.py
  - pyproject.toml
  - README.md
---

# Phase 3: AI Quality — Code Review Report

**Reviewed:** 2026-05-22T20:15:00Z  
**Depth:** standard  
**Files Reviewed:** 26 implementation files (union of 03-01…03-05 `key-files`; tests spot-checked)  
**Status:** issues

## Executive summary

Phase 3 delivers the intended architecture — shared `classify_llm_exception`, WeekBudget reservation, hierarchical rollup, Briefing renderer, and LOCKED-01 `_partition_cards` preservation all look sound in isolation. Budget float rounding (Plan 05 auto-fix) and cascade `title_changed` logic in `plan_invalidation` are correct at the pure-function layer.

The dominant risk is **dedup rebuild invalidation**: every `run_all` call rebuilds clusters with new UUIDs, but `delete_clusters_for_week` only removes `cluster_members` and `story_clusters`. Downstream rows in `cluster_summaries` / `cluster_ranks` (and checkpoint skips in rank/rollup) still reference old cluster IDs. A verified reproduction shows the **second `run_all` for the same week crashes with `IntegrityError: FOREIGN KEY constraint failed`** during dedup. This breaks PIPELINE-05/06 idempotency and is a merge blocker.

Secondary gaps: cascade wiring never passes `title_changed=True` (D-68 partial), pre-flight baseline uses the current week not the prior week (D-59), and `pipeline_report.json` mis-attributes summarize cost.

## Findings grouped by severity

### Critical

#### CR-01: Dedup rebuild violates FK — second `run_all` crashes

| Field | Value |
|-------|-------|
| **File** | `store/db.py:410-421`, `pipeline/dedup/cluster.py:112` |
| **Severity** | Critical |
| **Category** | bug |
| **Description** | `delete_clusters_for_week` deletes `story_clusters` rows while `cluster_summaries` and `cluster_ranks` still reference those `cluster_id` values (FK enforced via `PRAGMA foreign_keys = ON`). Every `run_all` calls `_dedup_week`, which always rebuilds clusters. The second run for the same `week_id` raises `sqlite3.IntegrityError`. Reproduced with mocked LLM: first run succeeds; second run fails at dedup. |
| **Suggested fix** | Extend invalidation to delete all cluster-attached artifacts for the week before removing clusters, e.g. add `delete_cluster_artifacts_for_week(conn, week_id)` that deletes `cluster_summaries`, `cluster_ranks`, and optionally `weekly_rollups` for the week, then call it from `delete_clusters_for_week` or immediately before cluster rebuild in `_dedup_week`. |

```python
def delete_cluster_artifacts_for_week(conn: sqlite3.Connection, week_id: str) -> None:
    conn.execute("DELETE FROM cluster_summaries WHERE week_id = ?", (week_id,))
    conn.execute("DELETE FROM cluster_ranks WHERE week_id = ?", (week_id,))
    # Consider rollups when cluster composition drives mini inputs:
    # delete_rollups_for_week(conn, week_id)
```

#### CR-02: Rank/rollup stage checkpoints skip on stale week-level rows

| Field | Value |
|-------|-------|
| **File** | `pipeline/orchestrator.py:596-599`, `772-777`, `823-825` |
| **Severity** | Critical |
| **Category** | bug |
| **Description** | `_rank_week` skips when **any** `cluster_ranks` row exists for `week_id`, without verifying rows join current `story_clusters`. After a successful dedup invalidation fix, if ranks are not deleted, rank would skip while `get_rank_positions_for_week` JOIN returns no positions for new clusters — Briefing section renders empty (`_render_briefing_section` requires `rank_position is not None`). Rollup category minis skip similarly when old `weekly_rollups` rows exist, serving stale narratives from the prior cluster composition. |
| **Suggested fix** | Tie checkpoint skip to cluster set integrity, not row count alone. Options: (a) delete ranks/rollups whenever dedup rebuilds (same helper as CR-01); (b) skip only when `COUNT(cluster_ranks JOIN story_clusters) == COUNT(story_clusters)` for the week; (c) store a cluster-set fingerprint on rank/rollup rows and invalidate on mismatch. |

```python
def ranks_cover_current_clusters(conn, week_id: str, prompt_version: str) -> bool:
    expected = conn.execute(
        "SELECT COUNT(*) AS n FROM story_clusters WHERE week_id = ?", (week_id,)
    ).fetchone()["n"]
    matched = conn.execute(
        """
        SELECT COUNT(*) AS n FROM cluster_ranks cr
        JOIN story_clusters sc ON sc.cluster_id = cr.cluster_id
        WHERE cr.week_id = ? AND cr.prompt_version = ?
        """,
        (week_id, prompt_version),
    ).fetchone()["n"]
    return expected > 0 and matched == expected
```

### Warning

#### WR-01: Cascade never detects title-only changes

| Field | Value |
|-------|-------|
| **File** | `pipeline/orchestrator.py:1110-1117` |
| **Severity** | Warning |
| **Category** | bug |
| **Description** | `_apply_cascade_for_item` always passes `title_changed=False`. D-68 requires dedup when `title_normalized` changes even without `content_hash` change. `plan_invalidation` handles this correctly (Plan 05 auto-fix), but production ingest/catch-up paths never set the flag — RSS title edits won't re-cluster. |
| **Suggested fix** | Compare normalized titles before/after upsert and pass `title_changed=(old_norm != new_norm)` into `plan_invalidation`. |

#### WR-02: Pre-flight baseline queries current week, not prior week

| Field | Value |
|-------|-------|
| **File** | `pipeline/budget.py:109-130` |
| **Severity** | Warning |
| **Category** | bug |
| **Description** | Docstring and D-59 specify prior-week per-item cost for pre-flight projection. `baseline_per_item_from_runs` filters `WHERE week_id = ?` with the **current** week, so first run of a new ISO week always falls back to `$0.001/item`; re-runs same week use prior partial runs instead of last week's actuals. |
| **Suggested fix** | Resolve previous ISO week via `pipeline.week` and query that `week_id`, or `ORDER BY finished_at DESC LIMIT 1` across all weeks with `phase='all'`. |

#### WR-03: `pipeline_report.json` misstates summarize stage cost

| Field | Value |
|-------|-------|
| **File** | `pipeline/reporting/pipeline_report.py:222-229` |
| **Severity** | Warning |
| **Category** | bug |
| **Description** | `stages.summarize.cost_usd` is computed as `stats.cost_usd_estimate - stats.rollup_cost_usd`, but `cost_usd_estimate` also includes categorize and rank spend. Phase 4/5 consumers reading per-stage costs (D-70, OBS-02) will see inflated summarize numbers. |
| **Suggested fix** | Track `summarize_cost_usd`, `categorize_cost_usd`, and `rank_cost_usd` on `RunStats`, or derive summarize cost from `item_summaries.cost_usd_estimate` SQL aggregate for the week. |

#### WR-04: Redirect fetch follows attacker-controlled URLs (SSRF surface)

| Field | Value |
|-------|-------|
| **File** | `pipeline/dedup/url.py:87-93` |
| **Severity** | Warning |
| **Category** | security |
| **Description** | `resolve_final_url` issues GET requests to item `canonical_url` values from RSS/YouTube feeds. Timeout (5s) limits hang but not internal-network probing. Orchestrator disables redirects in dedup (`fetch_redirects=False`) for CI, but the function remains callable. |
| **Suggested fix** | Restrict schemes to `http`/`https`, block private/link-local IP ranges after redirect resolution, or keep redirect fetch opt-in only (current orchestrator default). Document threat model in code comment. |

### Info

#### IN-01: Missing integration test for same-week re-run idempotency

| Field | Value |
|-------|-------|
| **File** | `tests/` (gap — no `test_run_all_twice_same_week.py`) |
| **Severity** | Info |
| **Category** | testing |
| **Description** | 139 tests pass but none assert two consecutive `run_all` calls for the same `week_id` succeed with stable Briefing/rank output. CR-01 would have been caught immediately. |
| **Suggested fix** | Add integration test: mock LLM, run `run_all` twice, assert no exception, `rank_join count == cluster count`, Briefing section present. |

#### IN-02: Orphan `cluster_summaries` rows accumulate per dedup rebuild

| Field | Value |
|-------|-------|
| **File** | `store/db.py:540-571` |
| **Severity** | Info |
| **Category** | bug |
| **Description** | Even when categorize re-runs for new cluster IDs, old summary rows remain keyed to deleted cluster IDs. Render JOINs hide them, but DB grows and `_categorize_distribution` counts may include stale rows if not joined to live clusters. |
| **Suggested fix** | Resolved by CR-01 artifact deletion; optionally filter `_categorize_distribution` through `JOIN story_clusters`. |

## Patterns / themes

1. **Stage checkpoint vs. cluster identity** — Meta stages (rank, rollup) use week-level "rows exist?" skips suited to stable cluster IDs, but dedup deliberately mints new UUIDs every rebuild (D-67). Checkpoint logic and dedup invalidation were designed independently; they must be unified.

2. **LLM exception taxonomy is consistent** — `classify_llm_exception` is shared; summarize/categorize/rank/rollup all map quota vs api errors uniformly. LOCKED-01 `_partition_cards` is unchanged; quota carve-out preserved.

3. **Budget gating looks correct post float fix** — `can_afford` rounding, `effective_meta_reservation_usd` cap, and `meta_stages_allowed()` after summarize halt match D-60. No runaway-cost path found beyond the dedup re-run crash (which prevents completion, not overspend).

4. **Cascade pure function vs. orchestrator wiring** — `pipeline/cascade.py` logic is sound; production only invokes it from YouTube catch-up with `title_changed=False` and without `membership_changed` / `top_n_composition_changed` detection on normal ingest.

5. **Renderer and migration quality** — HTML escaping on new reader strings, migration 004 `CREATE IF NOT EXISTS`, WAL mode, and `_ensure_pipeline_runs_phases` idempotent rebuild are well executed.

## Recommendation

**Do not merge Phase 3 until CR-01 and CR-02 are fixed and covered by an integration test (IN-01).** The FK crash on the second weekly run is a hard failure of PIPELINE-05/06 — the normal GHA/cron path will re-run the same `week_id` multiple times per week.

Suggested fix order:

1. Add `delete_cluster_artifacts_for_week` and call it from dedup rebuild (fixes CR-01, CR-02, IN-02).
2. Harden rank/rollup skip checks to validate cluster coverage (defense in depth for CR-02).
3. Wire `title_changed` in cascade application (WR-01).
4. Correct `pipeline_report` stage cost attribution (WR-03) before Phase 4 OBS-01 consumption.

WR-02 and WR-04 can ship as follow-up if time-constrained, but WR-02 affects pre-flight accuracy on first run of each new week.

---

_Reviewed: 2026-05-22T20:15:00Z_  
_Reviewer: Claude (gsd-code-reviewer)_  
_Depth: standard_
