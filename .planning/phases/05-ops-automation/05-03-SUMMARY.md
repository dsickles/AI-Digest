---
phase: 05-ops-automation
plan: "03"
subsystem: pipeline-budget+web-banner
tags: [hard-cap, deferred-budget, locked-01, status-banner, zod-schema, vitest, obs-03, ops-05]

requires:
  - phase: 05-ops-automation
    provides: weekly-digest.yml + worker/.env.example + Wave 0 RED stubs (from plan 05-01)

provides:
  - pipeline.budget.WeekBudget cross-run weekly spend counter (load_weekly_spend, get_cumulative_week_spend_usd)
  - HARD_CAP_USD env override with cap_override > env > config precedence
  - WeekBudget.deferred_items + mark_deferred_budget(item_id) tracking
  - orchestrator._mark_deferred_budget_for_remaining at cap-halt seam (writes summary_status='deferred_budget' for unprocessed canonical items)
  - pipeline_report budget.hard_cap_hit + budget.deferred_items_count fields
  - digest_json DigestDocument.pending_transcripts_count emitted at build time
  - LOCKED-01 amendment — deferred_budget routes to in-place degraded card (never footer)
  - web bannerCopy() variant resolver (complete / filling_in / partial_cap) with priority ordering
  - web/src/components/StatusBanner.astro reader-confidence banner mounted on index + digest/[week]
  - content.config.ts reports.budget tightened from z.record to explicit budgetSchema
  - vitest devDependency + pnpm test script in web/
affects: [05-04-daily-retry (shares cross-run spend counter), 05-05-worker-container (env knobs documented), 05-06-sentinel-heartbeat (StatusBanner reads ROADMAP-SC4 timestamp)]

tech-stack:
  added: [vitest 3.2.4 (dev-only)]
  patterns:
    - "Cross-run weekly counter via SQL aggregate over pipeline_runs.cost_usd_estimate — shared by cron + daily-retry workflows"
    - "Env-var > config precedence with silent fallback on invalid values (CI knob without yaml churn)"
    - "Halt-and-mark: at cap halt, persist deferred_budget rows for every un-summarized canonical item so the digest still shows context rather than silently dropping content"
    - "LOCKED-01 amendment protocol: code change to _IN_PLACE_TRANSIENT_STATUSES and LOCKED-DIRECTIVES.md ship in the same commit; QUOTA_BODY_COPY untouched"
    - "Astro reader-surface contracts via Zod: tighten z.record to explicit z.object so the build fails loudly when the pipeline emits an incomplete report"
    - "Pure-TS variant resolver tested with vitest, Astro template is a thin shell — keeps test coverage decoupled from Astro's renderer"

key-files:
  created:
    - web/src/components/StatusBanner.astro
    - .planning/phases/05-ops-automation/05-03-SUMMARY.md
  modified:
    - pipeline/budget.py
    - pipeline/orchestrator.py
    - pipeline/render/partition.py
    - pipeline/render/digest_json.py
    - pipeline/reporting/pipeline_report.py
    - config/digest.yaml
    - .planning/LOCKED-DIRECTIVES.md
    - web/package.json
    - web/pnpm-lock.yaml
    - web/src/content.config.ts
    - web/src/lib/copy.ts
    - web/src/pages/index.astro
    - web/src/pages/digest/[week].astro
    - web/src/test/StatusBanner.test.ts
    - tests/test_budget_hard_cap.py

key-decisions:
  - "hard_cap_hit aliases halted today but stays as a separate reader-surface field so semantics can diverge (e.g. a future soft cap) without renaming the StatusBanner-consumed field"
  - "get_cumulative_week_spend_usd sums status IN ('success','partial','failed') — failed-run partial spend still hit the wallet and must count against the cap; phase IN ('all','summarize') excludes isolated run_render to avoid double-counting"
  - "Halt-and-mark loop walks ALL rows (not just rows[halt_index:]) and skips items with existing summaries — same canonical-without-summary set falls out regardless of halt point, and the code is simpler than tracking halt indices"
  - "deferred_budget routes in-place (not footer) per LOCKED-01: it's a transient signal exactly like quota_exhausted, so the reader UX matches"
  - "bannerCopy variant precedence: partial_cap > filling_in > complete — matches the reader anxiety hierarchy (cap hit is the loudest signal; pending transcripts are a soft 'more is coming'; complete is the steady state)"
  - "hardCapHit with zero deferred items falls back to 'complete' rather than 'partial_cap' — defensive guard against degenerate signals from earlier-run cap hits that already drained their work"
  - "Negative pendingTranscriptsCount / deferredItemsCount are clamped to zero so a malformed report cannot make the banner disagree with the actual digest contents"
  - "pending_transcripts_count emitted as a top-level digest JSON field rather than nested under pipeline_notes — pipeline_notes can be null when there's nothing else worth surfacing, and the banner needs the count regardless"
  - "Zod budgetSchema tightened to explicit fields; old z.record(string,unknown) silently accepted any shape and would have let a regression that drops hard_cap_hit slip through to readers as 'always complete'"
  - "vitest 3.2.4 chosen over 4.x — 4.x dropped Node 18 support; 3.2.4 works with the existing Astro 6.3.7 / Vite 5 stack out of the box"

patterns-established:
  - "Phase-5 reader-surface schema tightening: any new pipeline_report field consumed by Astro lands in content.config.ts as an explicit zod field, never z.record"
  - "Halt-and-mark vs halt-and-break: when a budget gate halts work, persist a sentinel status for every un-processed item so downstream renderers see context, not gaps"
  - "Pure-TS variant resolver + thin Astro shell — Astro components stay structurally simple, vitest covers behavior, the same function is the source of truth for both renderer and tests"

requirements-completed:
  - OPS-05
  - OBS-03 (banner half — heartbeat half delivered in 05-06)

duration: ~95min
completed: 2026-05-29
---

# Phase 05 Plan 03: $1/Week Cap + `deferred_budget` + StatusBanner Summary

**Hard cap halts LLM, marks unprocessed canonical items `deferred_budget`, still publishes the partial week, and the new reader-confidence banner surfaces complete / filling-in / partial — N items skipped framing with the last-successful-run timestamp on index and permalink pages.**

## Performance

- **Duration:** ~95 min (three atomic commits)
- **Completed:** 2026-05-29
- **Tasks:** 3 (5-03-01 budget cap + deferred_budget + report fields · 5-03-02 LOCKED-01 amendment · 5-03-03 StatusBanner + Zod schema + vitest)
- **Files modified:** 15 + 1 created (StatusBanner.astro)
- **Tests added/extended:** 11 budget-cap cases + 11 StatusBanner cases — 22 net new assertions, all green

## Accomplishments

- **$1/week hard cap with cross-run cumulative spend.** `pipeline.budget.WeekBudget.from_config(conn, week_id)` now seeds `spent_usd` from `get_cumulative_week_spend_usd`, which SUMs `pipeline_runs.cost_usd_estimate` across `success`/`partial`/`failed` rows for the active week. The Sunday cron and the Mon–Sat daily-retry workflow now share one bucket per D-B4 + D-B9. Cap precedence is `cap_override` (CLI) > `HARD_CAP_USD` env (CI/operator runtime knob) > `config/digest.yaml`; invalid env values silently fall back so a typo never crashes a run. `config/digest.yaml` `pipeline.hard_stop_usd` flipped from 2.0 to 1.0.
- **Halt-and-mark instead of halt-and-break.** When the cap fires inside `_summarize_week_items`, the new `_mark_deferred_budget_for_remaining` helper walks every canonical row and inserts an `item_summaries` row with `summary_status='deferred_budget'` for each one that lacks a summary. Pre-existing summaries (including those from prior daily-retry runs) are never overwritten. The budget object accumulates the deferred ids so the reporter can emit `deferred_items_count` without a second SQL aggregate.
- **Report JSON gains banner-driving fields.** `pipeline_report.budget` now carries `hard_cap_hit` (bool) and `deferred_items_count` (int). `hard_cap_hit` aliases `halted` today but kept as a separate field so semantics can diverge (a future soft cap) without renaming the StatusBanner-consumed field. The `_SUMMARY_STATUS_KEYS` aggregate tuple gains `deferred_budget` so the SQL group-by exposes the count to digest pipeline notes too.
- **LOCKED-01 amendment in-band with the code change.** `pipeline/render/partition._IN_PLACE_TRANSIENT_STATUSES` gains `deferred_budget`; `.planning/LOCKED-DIRECTIVES.md` LOCKED-01 amendment timestamp + history bullet + in-place bucket entry all land in the same commit as the code change. `QUOTA_BODY_COPY` is NOT reworded — the spend-cap framing lives on `StatusBanner.astro` (reader surface), never in the card body.
- **`StatusBanner.astro` + variant copy resolver.** `web/src/lib/copy.ts#bannerCopy` is the pure-TS resolver with the three locked variants (complete / filling_in / partial_cap) and a deterministic priority order matching the reader anxiety hierarchy. The `.astro` component is a thin shell with variant-keyed border accents (neutral / blue / amber); both signals appear in `data-variant` on the root `<aside>` and the rendered `<time datetime="...">` line carries the original ISO timestamp verbatim so the page source is machine-parseable.
- **Reader-surface schema tightened.** `content.config.ts` reports.budget replaced permissive `z.record(string, unknown)` with explicit `budgetSchema` so a regression that drops a banner field fails the Astro build instead of silently rendering "complete" forever. Digests collection gains `pending_transcripts_count z.number().int().nonnegative().default(0)` — backwards-compatible default keeps older digest JSONs valid.
- **vitest wired into `web/`.** Added vitest 3.2.4 as a dev-only dependency with `pnpm test` script. All 11 StatusBanner cases pass; the Wave 0 RED stub from plan 05-01 is now part of an 11-case suite covering variant resolution, plural/singular noun agreement, defensive clamping, and timestamp round-trip through `new Date()`.
- **Live verification on the W21 build.** With the pre-existing W21 report carrying `hard_cap_hit: true / deferred_items_count: 4` (artifact of the cap integration test), the built `dist/index.html` shows the StatusBanner rendering as `partial_cap` with the text *"Partial week — 4 items skipped this week after the weekly spend cap was reached."* and a `<time datetime="2026-05-27T20:10:52Z">` line. End-to-end verified against real report data.

## Task Commits

1. **Task 5-03-01: $1/week hard cap + deferred_budget marking + report fields** — `921008a` (feat). 6 files (`pipeline/budget.py`, `pipeline/orchestrator.py`, `pipeline/reporting/pipeline_report.py`, `pipeline/render/digest_json.py`, `config/digest.yaml`, `tests/test_budget_hard_cap.py`). 10/11 tests green at this commit; the one waiting test was the LOCKED-01 contract gated on 5-03-02.
2. **Task 5-03-02: LOCKED-01 amendment — deferred_budget routes in-place** — `01dcec8` (feat). 2 files (`pipeline/render/partition.py`, `.planning/LOCKED-DIRECTIVES.md`). Flipped the last test green; 31 Python tests across budget + render + partition all GREEN at this commit.
3. **Task 5-03-03: StatusBanner + Zod budget schema + page mount + vitest** — `3093613` (feat). 9 files including the new `web/src/components/StatusBanner.astro`. 11 vitest cases pass; `pnpm build` clean; the rendered HTML inspected for the `partial_cap` variant + ISO timestamp.

## Files Created/Modified

**Created (2):**
- `web/src/components/StatusBanner.astro`
- `.planning/phases/05-ops-automation/05-03-SUMMARY.md` (this file)

**Modified (15):**
- `pipeline/budget.py` — `HARD_CAP_USD_ENV` constant, `WeekBudget.deferred_items` field, `mark_deferred_budget(item_id)` method, `load_weekly_spend(conn, week_id)` static, `from_config(conn, week_id)` now seeds `spent_usd` from prior runs, new `get_cumulative_week_spend_usd(conn, week_id)` aggregate, new `_hard_cap_from_env()` parser
- `pipeline/orchestrator.py` — `_mark_deferred_budget_for_remaining` helper + cap-halt-path call site
- `pipeline/render/partition.py` — `_IN_PLACE_TRANSIENT_STATUSES` adds `"deferred_budget"`
- `pipeline/render/digest_json.py` — `DigestDocument.pending_transcripts_count`, pipeline-notes detail line for cap-deferred items
- `pipeline/reporting/pipeline_report.py` — `_SUMMARY_STATUS_KEYS` adds `"deferred_budget"`, budget block adds `hard_cap_hit` + `deferred_items_count` (both branches: with and without `budget` object)
- `config/digest.yaml` — `pipeline.hard_stop_usd` 2.0 → 1.0 with HARD_CAP_USD override docstring
- `.planning/LOCKED-DIRECTIVES.md` — LOCKED-01 amendment timestamp + history bullet + in-place bucket entry
- `tests/test_budget_hard_cap.py` — Wave 0 RED stub → 11-case suite (4 contracts + 4 env/cumulative + 1 end-to-end + 2 derived)
- `web/package.json` + `web/pnpm-lock.yaml` — vitest devDep + `test` script
- `web/src/content.config.ts` — explicit `budgetSchema`, digests.`pending_transcripts_count` field
- `web/src/lib/copy.ts` — `bannerCopy`, `formatLastSuccessfulRun`, `StatusBannerInput`/`StatusBannerCopy`/`StatusBannerVariant` types
- `web/src/pages/index.astro` — fetches matching report from `getCollection('reports')`, mounts `<StatusBanner />` first in `<main>`
- `web/src/pages/digest/[week].astro` — `getStaticPaths` carries `report` prop; same banner mount
- `web/src/test/StatusBanner.test.ts` — Wave 0 RED stub → 11-case suite (variants + priority + clamping + plurals + timestamp round-trip)

## Decisions Made

Captured in frontmatter `key-decisions` above. The most consequential ones:

1. **Cross-run cumulative spend uses `status IN ('success','partial','failed')` and `phase IN ('all','summarize')`** — failed-run spend still hit the wallet, but isolated `run_render` rows are excluded so the counter doesn't double-count post-render reports.
2. **Halt-and-mark walks all rows, not just `rows[halt_index:]`** — the helper already skips items with existing summaries, so the same canonical-without-summary set falls out regardless of halt point. Simpler than threading the halt index through, and provably equivalent because pre-halt items have `item_summaries` rows.
3. **`hardCapHit` with zero deferred items stays 'complete'** — degenerate signal guard. A cap hit on an earlier run that drained its work shouldn't make the banner falsely claim items were skipped this week.
4. **Tighten `content.config.ts` reports.budget from `z.record` to explicit fields** — the old permissive shape would have let a regression that drops `hard_cap_hit` slip through to readers as silent "complete" forever.

## Deviations from Plan

- **`pending_transcripts_count` added to `DigestDocument` as a top-level field** rather than read off `pipeline_notes`. The plan didn't pin a specific data path; this is the simplest one. The digest JSON didn't previously carry a structured count (only `pipeline_notes.summary_line` strings), so emitting an explicit integer at build time avoids string-parsing in Astro.
- **No new `--backfill-deferred` CLI flag stub** — plan called out as Claude's discretion ("Whether `--backfill-deferred` stub appears in help only (deferred v1.5)"). Skipped to keep the surface minimal; can be added in v1.5 if/when auto-backfill is unparked from the deferred-ideas list.

## Issues Encountered

- **`pnpm install` hang inside the sandbox.** First attempt blocked indefinitely on `[ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY]`. Fix: run with `CI=true pnpm install --no-frozen-lockfile --prefer-offline` and `required_permissions: all` to bypass the sandbox EPERM on `node_modules/.pnpm/nanoid/.claude/settings.local.json`. Documented for future plans that need devDep additions.
- **W21 JSON render drift left in place per user instruction** ("leave the files as is for now"). The pre-existing modifications to `web/src/content/{digests,reports}/2026-W21.json` and the two `.gitkeep` files were excluded from this plan's commits. They happen to validate against the new tightened Zod schemas (the report already had `hard_cap_hit` + `deferred_items_count` from the integration test), so they don't block the build.

## User Setup Required

None new for this plan — the Phase 5 secret-hygiene setup from plan 05-01 (`GEMINI_API_KEY`) plus plan 05-02's B2 secrets already cover the cloud-cron path. `HARD_CAP_USD` env override is optional (CI default = config default = 1.0).

## Next Phase Readiness

Wave 2 complete. **Plan 05-04** (Mon–Sat daily retry with `--retry-transient-only`) is independently executable; it shares the cross-run weekly spend counter introduced here, so its budget gate is already wired. **Plan 05-05** (worker Docker container) is independent of 05-04 and can run in parallel.

No blockers; no inter-wave file conflicts ahead. Wave 3 (05-04 + 05-05) is queued.

---
*Phase: 05-ops-automation*
*Plan: 03 — $1/week hard cap + deferred_budget + StatusBanner*
*Completed: 2026-05-29*
