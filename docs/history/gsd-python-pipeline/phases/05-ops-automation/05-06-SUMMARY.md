---
phase: 05-ops-automation
plan: "06"
subsystem: infra
tags: [github-actions, healthchecks, timezone, sentinel, ops]

requires:
  - phase: 05-ops-automation
    provides: week.py UTC helpers, weekly-digest.yml, daily-retry.yml, worker entrypoint, budget.hard_cap_hit in reports
provides:
  - ET Sun-Sat digest week boundaries (week_bounds_et, active_digest_week_id)
  - Heartbeat pings on cron and home worker (start/end/fail)
  - Monday sentinel workflow verifying digest JSON and spend cap
  - Operator heartbeat setup guide (worker/setup-healthchecks.md)
affects: [phase-05-verify, operator-runbook]

tech-stack:
  added: [zoneinfo America/New_York ET week helpers]
  patterns: [Saturday-ending ISO week_id for ET digest window, Healthchecks curl via env secrets only]

key-files:
  created:
    - .github/workflows/sentinel.yml
    - worker/setup-healthchecks.md
  modified:
    - pipeline/week.py
    - README.md
    - .github/workflows/weekly-digest.yml
    - .github/workflows/daily-retry.yml
    - worker/entrypoint.sh
    - worker/README.md

key-decisions:
  - "Saturday-ending rule: week_id is ISO week of the Saturday ending the Sun-Sat ET window"
  - "active_digest_week_id on Mon-Sat returns ISO week of Saturday before most recent Sunday (retry/sentinel target)"
  - "Heartbeat URLs stored as secrets and referenced only via env vars — never echoed in workflow logs"

patterns-established:
  - "GHA workflows resolve WEEK_ID via active_digest_week_id() not current_week_id()"
  - "Healthchecks: /start at job start, POST spent_usd on success, /fail on failure"
  - "Monday sentinel verifies digest file exists and budget.hard_cap_hit is false"

requirements-completed: [OPS-01, OBS-03]

duration: 15min
completed: 2026-05-29
---

# Phase 05 Plan 06: ET Week Bounds + Heartbeat + Sentinel Summary

**ET-correct Sun-Sat digest windows, Healthchecks heartbeats on cron/worker, and a Monday sentinel that verifies the prior week's digest landed without a spend-cap hit**

## Performance

- **Duration:** 15 min
- **Started:** 2026-05-29T16:20:00Z
- **Completed:** 2026-05-29T16:35:00Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Implemented `week_bounds_et` and `active_digest_week_id` with Saturday-ending ISO week_id rule (D-B6b); all Wave 0 RED tests green
- Wired Healthchecks start/end/fail pings into `weekly-digest.yml` and `worker/entrypoint.sh`; switched WEEK_ID resolution to `active_digest_week_id` in cron and daily-retry workflows
- Added `sentinel.yml` (Mon 12:00 UTC + workflow_dispatch) verifying digest/report JSON and pinging `HEALTHCHECK_SENTINEL_URL`
- Created `worker/setup-healthchecks.md` documenting three checks with grace-window guidance

## Task Commits

Each task was committed atomically:

1. **Task 1: week_bounds_et and active_digest_week_id** - `28cbd45` (feat)
2. **Task 2: Heartbeat pings in weekly-digest and worker entrypoint** - `79c2c1e` (feat)
3. **Task 3: sentinel.yml Monday verification workflow** - `5f1ea10` (feat)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified

- `pipeline/week.py` - `week_bounds_et`, `active_digest_week_id`, ET constant
- `README.md` - Operations section documenting ET week semantics
- `.github/workflows/weekly-digest.yml` - heartbeat pings, `active_digest_week_id`
- `.github/workflows/daily-retry.yml` - direct `active_digest_week_id` resolution
- `.github/workflows/sentinel.yml` - Monday digest verification + heartbeat
- `worker/entrypoint.sh` - worker heartbeat start/end/fail, `active_digest_week_id`
- `worker/setup-healthchecks.md` - operator guide for three checks
- `worker/README.md` - sentinel workflow cross-link

## Decisions Made

None beyond plan — Saturday-ending rule and heartbeat shape followed D-B6b/D-B7 as specified.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

Configure three Healthchecks.io ping URLs as GitHub secrets (`HEALTHCHECK_CRON_URL`, `HEALTHCHECK_SENTINEL_URL`) and home-worker env (`HEALTHCHECK_WORKER_URL`). See [`worker/setup-healthchecks.md`](../../worker/setup-healthchecks.md).

## Next Phase Readiness

Plan 05-06 completes the Phase 5 ops automation wave. Ready for phase-level verification (`/gsd-verify-work 05`) and milestone close-out if all plans have summaries.

## Self-Check: PASSED

- `uv run pytest tests/test_week_bounds_et.py tests/test_week.py -x -q` → 10 passed
- `actionlint .github/workflows/weekly-digest.yml .github/workflows/daily-retry.yml .github/workflows/sentinel.yml` → exit 0
- key-files.created exist on disk
- git log contains 3 `(05-06)` task commits

---
*Phase: 05-ops-automation*
*Completed: 2026-05-29*
