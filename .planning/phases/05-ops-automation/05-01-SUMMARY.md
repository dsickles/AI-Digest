---
phase: 05-ops-automation
plan: "01"
subsystem: infra
tags: [github-actions, workflow-dispatch, actionlint, secret-hygiene, wave-0-stubs, dotenv]

requires:
  - phase: 04-dashboard-archive
    provides: web/src/content/digests/ + web/src/content/reports/ archive surface that the cron commits into
  - phase: 02-expand-ingestion
    provides: pipeline.run all CLI + --only-pending-transcripts entry the worker layer will eventually wrap

provides:
  - workflow_dispatch entry point at .github/workflows/weekly-digest.yml — manual trigger, contents:write commit, concurrency-guarded, dispatch-only (no cron yet)
  - secret-hygiene scaffolding: .gitignore covering .env.local / *.pem / *.key / data/*.db; worker/.env.example placeholders for the 7 env vars cron+worker share; worker/README.md operator setup
  - Wave 0 RED stub layer pinning Phase 5 contracts before implementation lands (5 pytest files + 1 vitest file)
  - conftest fixtures b2_stub_fixture (in-memory rclone substitute) + healthcheck_stub_fixture (records ping URLs)
  - actionlint install paths documented and Wave 0 checklist completed
affects: [05-02-cron-schedule, 05-03-budget-cap, 05-04-daily-retry, 05-05-worker-container, 05-06-sentinel-heartbeat]

tech-stack:
  added: [actionlint 1.7.12 operator-local, github-actions ubuntu-latest, astral-sh/setup-uv@v3]
  patterns:
    - "Wave 0 RED stubs: assertion-with-message pattern referencing the target plan (e.g. 'Plan 05-03 must add deferred_budget …') so a future engineer sees the contract before the implementation"
    - "In-memory protocol stubs in conftest (B2 + Healthchecks) so cron/worker/sentinel tests never need the network"
    - "Generic-terminology Privacy Sweep on every new repo-visible file (workflow YAML, env.example, worker/README) — env var names use vendor-prescribed identifiers, prose uses generic terms"
    - "Operator-local tool binaries go in gitignored .tools/ via the official prebuilt-binary install script; alternative Homebrew path documented in the same footnote"

key-files:
  created:
    - .github/workflows/weekly-digest.yml
    - worker/.env.example
    - worker/README.md
    - tests/test_week_bounds_et.py
    - tests/test_budget_hard_cap.py
    - tests/test_retry_transient_only.py
    - tests/test_partition_deferred_budget.py
    - tests/test_marker_file.py
    - web/src/test/StatusBanner.test.ts
  modified:
    - .gitignore
    - tests/conftest.py
    - .planning/phases/05-ops-automation/05-VALIDATION.md

key-decisions:
  - "Dispatch-only workflow this plan; schedule:cron explicitly deferred to plan 05-02 so Wave 1 ships an operator-reachable manual surface without committing to the Sunday-10:00-UTC cadence yet"
  - "Wave 0 stubs land RED with explicit pointer-to-target-plan assertion messages — they document the contract for 05-02..05-06 the moment a future reader runs the failing test"
  - "B2 + Healthchecks fixtures live in conftest.py as plain dataclass-ish in-memory stubs (no requests-mock dependency, no rclone subprocess) — keeps Phase 5 testable without any new test deps"
  - "actionlint is operator-installed (brew or curl-install to .tools/), NOT committed; both install paths documented in 05-VALIDATION.md footnote so any forker can recreate the gate"
  - ".env.example uses vendor-prescribed env var names (GEMINI_API_KEY, B2_KEY_ID, B2_APPLICATION_KEY, GITHUB_TOKEN, HEALTHCHECK_*_URL) per D-B8 — the Privacy Sweep applies to prose and literal bucket/repo names, not to standard secret identifiers"

patterns-established:
  - "Atomic per-task commits with explicit Refs trailer to plan + task id (5-01-01, 5-01-02, 5-01-03)"
  - "Privacy-Sweep-clean public-facing files: workflow YAML and worker/ prose contain no operator-personal detail"
  - "Wave 0 contract = RED stubs + fixtures + lint gate committed BEFORE any implementation plan starts"

requirements-completed:
  - OPS-01
  - OPS-02
  - OPS-04

duration: ~35min
completed: 2026-05-24
---

# Phase 05 Plan 01: Cloud Vertical Slice + Wave 0 RED Stubs Summary

**Manual workflow_dispatch path for the weekly pipeline + Wave 0 failing test layer + secret hygiene scaffolding — every Phase 5 contract pinned before any implementation plan touches code.**

## Performance

- **Duration:** ~35 min (across three atomic commits)
- **Started:** 2026-05-24T21:55Z (UTC)
- **Completed:** 2026-05-24T22:35Z (UTC, approximate based on final commit timestamp)
- **Tasks:** 3 (5-01-01 Wave 0 stubs · 5-01-02 workflow_dispatch + secret hygiene · 5-01-03 actionlint wiring)
- **Files modified:** 12 (9 created + 3 modified)

## Accomplishments

- **Cloud-side dispatch surface exists.** Operators can now hit `Run workflow` on `weekly-digest.yml` from the GitHub UI, supplying an optional `week_id`, and the job will check out the repo, install Python via `uv`, run `pipeline.run all --week …`, and commit any new digest+report JSON via the `github-actions[bot]` identity with `contents:write`. No schedule yet — that comes with plan 05-02.
- **Wave 0 RED stub layer.** Five pytest files and one vitest file fail loudly today and will turn green as plans 05-02..05-06 land. Each stub names the target plan in its assertion message, so a future reader sees the exact contract being pinned (e.g. `"Plan 05-03 must add 'deferred_budget' to pipeline.render.partition._IN_PLACE_TRANSIENT_STATUSES"`).
- **In-memory cron/worker test substrates.** `b2_stub_fixture` and `healthcheck_stub_fixture` give downstream plans a zero-network way to assert the cron→B2-marker→worker rendezvous (D-B3 + D-B5b) and the three-Healthchecks-URL contract (D-B7) without any new test dependency.
- **Secret hygiene scaffolding.** `.gitignore` now covers `.env.local`, `*.pem`, `*.key`, and `data/*.db`. `worker/.env.example` documents the 9 env vars cron+worker share (with placeholder values that fail loudly when unfilled). `worker/README.md` is the operator setup contract, generically worded per the Pre-public-release Privacy Sweep, with a hard link to `.planning/runbooks/leak-recovery.md` as the sole post-leak playbook.
- **Workflow lint gate live.** `actionlint 1.7.12` passes against `.github/workflows/weekly-digest.yml`. The Full suite command in `05-VALIDATION.md` now carries a footnote covering both supported install paths (Homebrew and the official prebuilt-binary curl script to `.tools/`). Wave 0 frontmatter flipped to `wave_0_complete: true`.

## Task Commits

Each task was committed atomically:

1. **Task 5-01-01: Wave 0 RED stubs and B2/healthcheck fixtures** — `aad7bea` (test). 5 new pytest files + 1 vitest file + extended `tests/conftest.py`; all 12 stub assertions fail RED today (5/4/3/1/2 failures per file; matches Wave 0 contract).
2. **Task 5-01-02: workflow_dispatch entry + secret hygiene scaffolding** — `2561fc8` (feat). `.github/workflows/weekly-digest.yml`, `.gitignore`, `worker/.env.example`, `worker/README.md`. Existing pytest suite (189 tests, excluding the Wave 0 stubs) stayed green.
3. **Task 5-01-03: wire actionlint into Wave 0** — `19f158c` (chore). `.tools/` gitignored, footnote added to 05-VALIDATION.md covering both install paths, all Wave 0 checkboxes flipped to checked, frontmatter advanced to `status: wave-0-complete`.

## Files Created/Modified

**Created (9):**
- `.github/workflows/weekly-digest.yml` — dispatch-only workflow with concurrency guard, optional `week_id` input, `contents:write` permission, `astral-sh/setup-uv@v3` install path, `pipeline.run all --week` invocation, and a `github-actions[bot]` commit step that no-ops when the working tree is clean.
- `worker/.env.example` — 9 placeholder env vars covering LLM key, B2 credentials + bucket/remote name + repo name (placeholders only), GitHub PAT + commit-author, three Healthchecks ping URLs, and `WORKER_POLL_INTERVAL_SECONDS`.
- `worker/README.md` — operator setup contract: prerequisites, configuration walk-through, secret-hygiene D-B8 three-layer overview, LLM spend-cap D-B9 overview, ops summary, health-check contract preview, and an explicit list of what this README intentionally does not cover (operator-personal infrastructure stays out of the repo).
- `tests/test_week_bounds_et.py` — REQ-OPS-01 / D-B6b stubs (5 failing assertions): `week_bounds_et`/`active_digest_week_id` existence, Sun-Sat ET window for `2026-W21`, Sunday-morning resolution to the prior week, DST spring-forward day-delta invariant.
- `tests/test_budget_hard_cap.py` — REQ-OPS-05 / D-B9 stubs (4 failing assertions): `deferred_budget` in `_IN_PLACE_TRANSIENT_STATUSES`, `hard_cap_hit` + `deferred_items_count` fields in `pipeline_report.py`, `WeekBudget` halt-and-mark hook, cross-run weekly-spend loader.
- `tests/test_retry_transient_only.py` — D-B4 + D-B9 stubs (3 failing assertions): `--retry-transient-only` in `summarize --help`, orchestrator entry point, explicit `TRANSIENT_RETRY_STATUSES` set that excludes `deferred_budget`.
- `tests/test_partition_deferred_budget.py` — LOCKED-01 routing stub (1 failing assertion + 1 invariant): `deferred_budget` must land inside `_IN_PLACE_TRANSIENT_STATUSES`; `thin` must remain outside.
- `tests/test_marker_file.py` — D-B5b cron-complete marker stubs (2 failing assertions + 1 schema assertion): writer existence, `{week_id, completed_at}` roundtrip, locked filename pattern.
- `web/src/test/StatusBanner.test.ts` — OBS-03 / D-24 reader-copy contract (3 variants + 1 D-24 guard): `complete` / `filling_in` / `partial_cap` copy variants and a no-internal-sentinel guard.

**Modified (3):**
- `.gitignore` — added `.env.local`, `*.pem`, `*.key`, `data/*.db` for D-B8 layer 2 plus `.tools/` for operator-local binaries (actionlint).
- `tests/conftest.py` — added `b2_stub_fixture` and `healthcheck_stub_fixture` (in-memory stubs; zero new test deps; both shape-match the Phase 5 cron/worker/sentinel contracts).
- `.planning/phases/05-ops-automation/05-VALIDATION.md` — Full suite command now carries the actionlint install footnote; all 8 Wave 0 checkboxes flipped to checked; frontmatter advanced to `status: wave-0-complete`, `wave_0_complete: true`.

## Decisions Made

- **`week_id` resolution defers to `current_week_id()` for now**, not `active_digest_week_id()`. The Sun-Sat ET function ships with plan 05-06; until then the workflow uses the existing UTC ISO week. Acceptable for a dispatch-only Wave 1 surface — the operator can supply an explicit `week_id` for any backfill or test run.
- **`actionlint` is operator-installed, not committed.** Two install paths documented (Homebrew + prebuilt-binary curl). The repo carries the contract (footnote + Wave 0 checkbox + the gate in the Full suite command), not the binary itself.
- **`.env.example` uses the vendor-prescribed secret names** (`GEMINI_API_KEY`, `B2_KEY_ID`, `B2_APPLICATION_KEY`, etc.) per D-B8. The Privacy Sweep rule applies to prose and to literal bucket/repo names, not to the standard env var identifiers a forker needs to recognize.
- **`worker/Dockerfile` / `docker-compose.yml` / `entrypoint.sh` deliberately not in this plan.** Plan 05-05 owns them. `worker/README.md` documents the operator-facing surface so the runtime artifacts have a stable home to land into.

## Deviations from Plan

None — plan 05-01 executed exactly as written. The three tasks landed in declared order (Wave 0 stubs first so downstream plans have automated targets; workflow + secret hygiene second so actionlint has a target; actionlint wiring third so the gate is gate-keepable).

## Issues Encountered

- **Pre-existing W21 JSON drift triggered a transient `test_cli_phase3::test_double_render_produces_identical_html` failure** when pytest ran with `-x`. Confirmed pre-existing (failed on the same dirty W21 even with my changes stashed away; passes against the pristine W21). Not introduced by this plan. The W21 JSON modifications remain unstaged in the working tree — they trace to a Phase 4 render-only re-run earlier in this session.
- **`brew install actionlint` hung on network.** Switched to the official prebuilt-binary install script, which finished in ~1 second to `.tools/actionlint`. Both paths now documented in the Wave 0 footnote so forkers can pick whichever works in their environment.

## User Setup Required

None for this plan. Operator setup for the cron + home worker is captured in `worker/README.md` and exercised once plans 05-02..05-05 land.

## Next Phase Readiness

Wave 1 is complete. Wave 2 (plans 05-02 + 05-03) can begin:

- **05-02** (cron schedule + rclone B2 sync + cron-complete marker) has all of its scaffolding in place: `weekly-digest.yml` to extend, `worker/.env.example` documenting `B2_*` placeholders, `tests/test_marker_file.py` waiting RED, `b2_stub_fixture` ready to drive marker tests.
- **05-03** (budget hard cap + LOCKED-01 amendment + StatusBanner) has its Wave 0 contracts pinned: `tests/test_budget_hard_cap.py` / `tests/test_partition_deferred_budget.py` / `web/src/test/StatusBanner.test.ts` are all RED with explicit pointer-to-this-plan assertions.

No blockers. The pre-existing W21 JSON drift is unrelated and can be cleaned up either by recommitting a fresh render or by `git checkout`ing the JSON files at the operator's discretion.

---
*Phase: 05-ops-automation*
*Plan: 01 — Cloud vertical slice + Wave 0 RED stubs*
*Completed: 2026-05-24*
