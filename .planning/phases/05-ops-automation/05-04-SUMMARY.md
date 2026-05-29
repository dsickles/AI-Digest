---
phase: 05-ops-automation
plan: "04"
subsystem: pipeline-ops+gha
tags: [daily-retry, transient-retry, github-actions, rclone, d-b4, d-b9, d-68, ops-01]

requires:
  - phase: 05-ops-automation
    provides: cross-run WeekBudget counter + deferred_budget filter semantics (from plan 05-03)
  - phase: 05-ops-automation
    provides: weekly-digest rclone B2 sync pattern (from plan 05-02)

provides:
  - pipeline.run summarize --retry-transient-only CLI flag (D-22 README + --help)
  - pipeline.orchestrator.TRANSIENT_RETRY_STATUSES + retry_transient_summaries entry point
  - _summarize_week_items retry_transient_only filter (quota_exhausted/api_error/client_init_error only)
  - .github/workflows/daily-retry.yml Mon–Sat cron 0 10 * * 1-6 + workflow_dispatch
  - daily-retry B2 db pull/push + summarize retry + explicit render + digest JSON commit (D-68)
affects: [05-05-worker-container, 05-06-sentinel-heartbeat]

tech-stack:
  added: []
  patterns:
    - "Transient-only retry deletes prior item_summaries row before re-insert so UNIQUE constraint allows recovery"
    - "Daily-retry workflow mirrors weekly-digest rclone materialization but skips CLOUD_CRON_MODE marker and Healthchecks pings (D-B4)"
    - "Explicit render step after summarize retry ensures web/src/content/digests/{week_id}.json updates even when cascade path is narrow"

key-files:
  created:
    - .github/workflows/daily-retry.yml
    - .planning/phases/05-ops-automation/05-04-SUMMARY.md
  modified:
    - pipeline/run.py
    - pipeline/orchestrator.py
    - README.md
    - tests/test_retry_transient_only.py

key-decisions:
  - "TRANSIENT_RETRY_STATUSES exported as frozenset on orchestrator — single source of truth for CLI filter, tests, and future worker docs"
  - "retry_transient_summaries thin wrapper around run_summarize(retry_transient_only=True) satisfies Wave 0 stub entry-point contract without duplicating finalize logic"
  - "Retry mode deletes existing summary row before re-summarize — insert_item_summary is insert-only; delete-then-insert is simpler than an upsert helper for this one call site"
  - "daily-retry resolves week via getattr(active_digest_week_id, current_week_id) until plan 05-06 lands ET week bounds"
  - "Explicit render step after summarize in daily-retry.yml — guarantees digest JSON commit observable after transient recovery (D-68 mandate)"

patterns-established:
  - "Mon–Sat cloud retry is summarize-only + render — never ingest, never marker write, never heartbeat ping"
  - "Filter tests seed item_summaries with status sentinels and monkeypatch summarize_item to assert call set without LLM network"

requirements-completed:
  - OPS-01

duration: ~35min
completed: 2026-05-29
---

# Phase 05 Plan 04: Daily Transient Retry + `--retry-transient-only` Summary

**Mon–Sat cloud workflow retries only transient LLM summarize failures (`quota_exhausted`, `api_error`, `client_init_error`), shares the cross-run weekly spend counter with Sunday cron, and commits upgraded digest JSON after an explicit render pass.**

## Performance

- **Duration:** ~35 min (two atomic commits)
- **Completed:** 2026-05-29
- **Tasks:** 2 (5-04-01 CLI + orchestrator filter + tests · 5-04-02 daily-retry.yml)
- **Files modified:** 5 + 1 created (daily-retry.yml)

## Accomplishments

- **`--retry-transient-only` on `pipeline.run summarize`.** New flag with D-22 help text on the summarize subcommand and an Operations section in root `README.md`. Only valid with `summarize` — no ingest path runs in this mode.
- **`TRANSIENT_RETRY_STATUSES` filter in orchestrator.** When `retry_transient_only=True`, `_summarize_week_items` skips items without summaries, skips `deferred_budget` / `ok` / other non-transient statuses, and re-bills only rows in `{quota_exhausted, api_error, client_init_error}`. Prior failed rows are deleted before re-insert. Budget cap from plan 05-03 still applies via `WeekBudget.from_config`.
- **`retry_transient_summaries` entry point.** Thin wrapper exported in `__all__` for the daily-retry workflow and Wave 0 contract tests.
- **`daily-retry.yml` GHA workflow.** Schedule `0 10 * * 1-6` plus `workflow_dispatch`. Mirrors weekly-digest rclone.conf materialization and B2 `aidigest.db` pull/push. Runs `summarize --retry-transient-only` then `render --week` before git commit of `web/src/content/digests/` and `web/src/content/reports/`. No Healthchecks curls, no cron-complete marker (D-B4). `actionlint` clean.

## Task Commits

1. **Task 5-04-01: `--retry-transient-only` CLI and orchestrator filter** — `3bd5dac` (feat). 4 files (`pipeline/run.py`, `pipeline/orchestrator.py`, `README.md`, `tests/test_retry_transient_only.py`). 5/5 pytest cases green; `--help` lists flag.
2. **Task 5-04-02: daily-retry.yml workflow with object-storage sync** — `252cae8` (feat). 1 file (`.github/workflows/daily-retry.yml`). Grep verification + `actionlint` exit 0.

## Files Created/Modified

**Created (2):**
- `.github/workflows/daily-retry.yml`
- `.planning/phases/05-ops-automation/05-04-SUMMARY.md` (this file)

**Modified (4):**
- `pipeline/run.py` — `_RETRY_TRANSIENT_HELP`, `_add_retry_transient_only_arg`, summarize dispatch + validation
- `pipeline/orchestrator.py` — `TRANSIENT_RETRY_STATUSES`, `retry_transient_only` param on `_summarize_week_items` / `run_summarize`, delete-then-reinsert retry path, `retry_transient_summaries` wrapper
- `README.md` — Daily transient LLM retry section with examples
- `tests/test_retry_transient_only.py` — Wave 0 RED stub → 5-case GREEN suite with seeded SQLite filter proofs

## Decisions Made

Captured in frontmatter `key-decisions`. Most consequential: explicit render in daily-retry ensures digest JSON commit is observable even when summarize alone does not trigger full D-68 cascade re-emit.

## Deviations from Plan

None — plan 05-04 executed as written.

## Issues Encountered

- **`actionlint` not on PATH in sandbox.** Installed via Homebrew for workflow verification; lint passed on final YAML shape.

## User Setup Required

Same secrets as weekly-digest (`GEMINI_API_KEY`, `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET`). First Mon–Sat scheduled run is the integration test; `workflow_dispatch` ahead of schedule recommended.

## Next Phase Readiness

Plan **05-05** (worker Docker + GHCR) is independent and can proceed in parallel. Plan **05-06** (sentinel + heartbeat) depends on daily-retry + worker patterns but not on new code from this plan.

## Self-Check: PASSED

- FOUND: `.github/workflows/daily-retry.yml`
- FOUND: `.planning/phases/05-ops-automation/05-04-SUMMARY.md`
- FOUND: commit `3bd5dac`
- FOUND: commit `252cae8`

---
*Phase: 05-ops-automation*
*Plan: 04 — Mon–Sat daily retry + --retry-transient-only*
*Completed: 2026-05-29*
