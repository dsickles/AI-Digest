---
phase: 05-ops-automation
plan: "02"
subsystem: infra
tags: [github-actions, cron, rclone, backblaze-b2, object-storage, marker-rendezvous, sqlite-sync]

requires:
  - phase: 05-ops-automation
    provides: weekly-digest.yml dispatch-only entry, worker/.env.example placeholders, tests/test_marker_file.py RED stub (all from plan 05-01)

provides:
  - pipeline.orchestrator.write_cron_complete_marker(week_id, markers_dir) — writes markers/cron-complete-{week_id}.json
  - CLOUD_CRON_MODE env-var gate around the marker write so local manual runs never produce one
  - run_all success-path hook for the gated marker write (no behavioral change when env unset)
  - Sunday 10:00 UTC cron schedule on weekly-digest.yml (D-B1)
  - Runtime rclone.conf materialization from B2_KEY_ID / B2_APPLICATION_KEY secrets (chmod 600, never committed)
  - SQLite round-trip: pull `db/aidigest.db` before pipeline, push back after, with first-run tolerance
  - Cron-complete marker upload to `markers/` path (rclone copy never sync — RESEARCH Pitfall 4)
affects: [05-04-daily-retry, 05-05-worker-container, 05-06-sentinel-heartbeat]

tech-stack:
  added: [rclone (Ubuntu apt), GHA scheduler cron, marker-file rendezvous protocol]
  patterns:
    - "Env-var-gated side effect: orchestrator helpers that touch shared object-storage gate on CLOUD_CRON_MODE=1 so local runs are inert"
    - "rclone copy NEVER sync for shared buckets that mix DB + marker objects"
    - "rclone B2 backend: Application Key ID → rclone.account, Application Key → rclone.key (master Account ID returns 401)"
    - "First-run bucket tolerance: swallow the rclone-copy exit when no prior DB exists; init_db bootstraps from scratch on the next pipeline step"

key-files:
  created:
    - .planning/phases/05-ops-automation/05-02-SUMMARY.md
  modified:
    - pipeline/orchestrator.py
    - .github/workflows/weekly-digest.yml
    - tests/test_marker_file.py

key-decisions:
  - "Marker writer lives on pipeline.orchestrator (not a new pipeline.markers module) — it's a one-function helper that imports nothing exotic; a new module would be premature factoring"
  - "CLOUD_CRON_MODE=1 chosen as the gate over a config flag — env var matches how GHA workflows naturally signal context, and any other value (0, true, yes, empty) is treated as not-cloud for least-surprise"
  - "rclone B2 remote alias is hard-coded as `b2` (not configurable) — it's a workflow-internal name; configurable would force operators to keep two strings in sync"
  - "Marker-upload step exits non-zero when the marker is missing — defensive guard against a pipeline that finalized but skipped the orchestrator hook (would be a regression we want to surface loudly)"
  - "Commit message changes from 'chore(digest): manual weekly' to 'chore(digest): cloud weekly' on scheduled runs so git log distinguishes scheduled vs dispatched at-a-glance"

patterns-established:
  - "Env-var-gated orchestrator side effects with logged-and-swallowed failures (the gated helper must never break a successful pipeline run)"
  - "Workflow secrets-to-file materialization with umask 077 + explicit chmod 600 belt-and-suspenders"
  - "Test-suite-first marker contract: the Wave 0 RED stub from 05-01-01 became the test that gates the 05-02-01 implementation"

requirements-completed:
  - OPS-01

duration: ~25min
completed: 2026-05-27
---

# Phase 05 Plan 02: Sunday Cron + Object-Storage Rendezvous Summary

**Loaded the cloud half of the cron→home-worker handoff: Sunday 10:00 UTC schedule, runtime rclone.conf, SQLite round-trip through Backblaze B2, and the cron-complete marker that signals the residential-IP worker to drain YouTube transcripts.**

## Performance

- **Duration:** ~25 min (across two atomic commits)
- **Started:** 2026-05-27T19:35Z (approx.)
- **Completed:** 2026-05-27T20:00Z (approx.)
- **Tasks:** 2 (5-02-01 marker writer + gating · 5-02-02 cron + rclone + marker upload)
- **Files modified:** 3 (orchestrator + test extension + workflow)

## Accomplishments

- **Sunday cron schedule live.** `weekly-digest.yml` now runs on `0 10 * * 0` (Sun 10:00 UTC, ±1h ET drift accepted per D-B1) alongside the dispatch-only entry from 05-01. The schedule comment documents the ET intent so a future maintainer doesn't try to "fix" the drift.
- **Cron-complete marker writer in orchestrator.** `write_cron_complete_marker(week_id, markers_dir)` validates `week_id` through `parse_week_id`, mkdir -p's the markers directory, and writes `{week_id, completed_at}` JSON with a UTC ISO timestamp. The home worker (plan 05-05) will poll for this exact filename pattern.
- **CLOUD_CRON_MODE gate.** A new env-var-gated helper (`_maybe_write_cron_complete_marker`) only writes the marker when `CLOUD_CRON_MODE=1`. Local manual `pipeline.run all` invocations never produce a marker the worker might pick up. Failures are logged and swallowed so a marker-write hiccup cannot break an otherwise-successful pipeline run.
- **Object-storage round-trip.** The workflow installs `rclone` via apt, materializes `~/.config/rclone/rclone.conf` at job runtime from `B2_KEY_ID` + `B2_APPLICATION_KEY` secrets (`chmod 600`), pulls `db/aidigest.db` before the pipeline (with first-run tolerance), and copies it back after. `B2_BUCKET` is also a secret — no literal bucket name lands in committed YAML (Privacy Sweep).
- **Marker upload step is defensively loud.** After the pipeline succeeds, the workflow `rclone copy`s the cron-complete marker to `markers/` and exits non-zero if the orchestrator did not produce one — a missing marker after a "successful" pipeline would be a regression we want to surface immediately.
- **Test layer flipped GREEN.** `tests/test_marker_file.py` went from 2 failing assertions (Wave 0 RED) to 5 passing tests covering writer existence, roundtrip shape, filename pattern, env-var-name constant, and the gate's behavior across five non-`"1"` values (unset / `0` / `true` / `yes` / `false` all skip; only exact `"1"` writes).

## Task Commits

Each task was committed atomically:

1. **Task 5-02-01: cron-complete marker writer + CLOUD_CRON_MODE gate** — `42177c9` (feat). `pipeline/orchestrator.py` gains `write_cron_complete_marker` (public), `_maybe_write_cron_complete_marker` (internal gated helper), `CLOUD_CRON_MODE_ENV`, and `DEFAULT_MARKERS_DIR` exports. `tests/test_marker_file.py` extended from 3 to 5 tests (Wave 0 stub now GREEN + 2 new gate-behavior assertions).
2. **Task 5-02-02: Sunday cron + object-storage rendezvous + marker upload** — `e7d5458` (feat). `.github/workflows/weekly-digest.yml` extended with the cron schedule, rclone install + config materialization, DB pull/push, marker upload, and a defensive missing-marker check. `actionlint` clean.

## Files Created/Modified

**Modified (3):**
- `pipeline/orchestrator.py` — added `os` + `parse_week_id` imports, `CLOUD_CRON_MODE_ENV` / `DEFAULT_MARKERS_DIR` module constants, `write_cron_complete_marker` (public), `_maybe_write_cron_complete_marker` (internal), and a call site in `run_all`'s success path immediately after `_finalize`. `__all__` extended.
- `.github/workflows/weekly-digest.yml` — added `on.schedule`, top-of-job env (`CLOUD_CRON_MODE=1`, `B2_BUCKET` from secret), rclone install step, runtime rclone.conf materialization, data/markers `mkdir -p`, DB pull (first-run-tolerant), DB push-back, marker upload (defensive), commit message disambiguator for scheduled runs.
- `tests/test_marker_file.py` — file docstring updated from "Wave 0 RED stub" to current behavior contract; added `test_cloud_cron_mode_env_var_exported` and `test_maybe_write_cron_complete_marker_respects_gate` (uses `monkeypatch.chdir`+`setenv` to verify the env-value matrix).

**Created (1):**
- `.planning/phases/05-ops-automation/05-02-SUMMARY.md` (this file)

## Decisions Made

- **Marker writer lives on `pipeline.orchestrator` rather than a new `pipeline.markers` module.** The stub had a fallback path for a new module; pulling in a fresh top-level module for a one-function helper would be premature factoring. The orchestrator already owns the run-finalization seam where the marker write fires.
- **The env-var gate uses exact-match `"1"`.** Other plausible values (`"0"`, `"true"`, `"yes"`, `"false"`, empty string) all skip. Tests cover the matrix explicitly so a future env-var refactor cannot silently change the truthiness rule.
- **`rclone copy` everywhere, never `sync`.** This is RESEARCH Pitfall 4 made explicit in workflow comments — `sync` would delete other objects in the destination (including the worker's not-yet-consumed markers).
- **B2 bucket name is a secret.** Privacy Sweep applies to the YAML; the bucket name and the rclone credentials all live in repo secrets. The remote alias `b2` IS hard-coded — that's an internal-to-the-workflow string, not a vendor leak.
- **Defensive marker-upload step (`exit 1` if marker missing).** Trades silent partial success for loud failure. A run that finalized "successfully" without producing a marker would indicate the orchestrator hook regressed; surfacing it as a workflow failure is preferable to a silent home-worker desync.

## Deviations from Plan

None — plan 05-02 executed exactly as written. Two tasks landed in the declared order (marker writer first so the workflow had a real artifact to upload; workflow extension second so actionlint had a final shape to check).

## Issues Encountered

None.

## User Setup Required

External services need configuration before the Sunday cron can succeed end-to-end:

- **Backblaze B2 (or any S3-compatible alternative):** create a bucket, generate an Application Key scoped to that bucket, store `B2_KEY_ID` / `B2_APPLICATION_KEY` / `B2_BUCKET` in GitHub repo secrets.
- **Gemini API key:** already covered by 05-01's secret-hygiene setup — `GEMINI_API_KEY` repo secret.

Both are documented in `worker/README.md` Prerequisites. The first scheduled Sunday after this plan lands is the integration test; manually `workflow_dispatch` ahead of Sunday once to validate end-to-end before relying on the schedule.

## Next Phase Readiness

Wave 2's first plan complete. Plan 05-03 (`$1`/week hard cap + `deferred_budget` LOCKED-01 amendment + Astro StatusBanner) is independently executable — it touches `pipeline/budget.py`, `pipeline/render/partition.py`, `pipeline/render/digest_json.py`, `pipeline/reporting/pipeline_report.py`, `pipeline/orchestrator.py` (shared with this plan), and the web/ Astro surface. No conflicts with this plan's orchestrator changes — 05-02 added a finalize hook, 05-03 will add a cap-halt path inside `_summarize_week_items`.

No blockers.

---
*Phase: 05-ops-automation*
*Plan: 02 — Sunday cron + object-storage rendezvous + marker upload*
*Completed: 2026-05-27*
