---
status: issues-found
phase: 05-ops-automation
depth: standard
created: 2026-05-29T17:45:00Z
critical_count: 0
warning_count: 4
info_count: 4
---

## Summary

Plan 05-06 delivers ET week helpers (`week_bounds_et`, `active_digest_week_id`), Healthchecks heartbeats on the Sunday cron and home worker, a Monday sentinel workflow, and operator setup docs. The core `week_bounds_et` / `active_digest_week_id` math is internally consistent with the Saturday-ending `week_id` rule and behaves correctly for Sunday cron, Monday sentinel, and Mon–Sat daily-retry targeting (each returns the digest week processed on the most recent Sunday). Security review passed: heartbeat URLs are referenced only via `${{ secrets.HEALTHCHECK_*_URL }}` env vars, never echoed in workflow steps, and `sentinel.yml` has `permissions: contents: read` only.

Gaps remain: `week_bounds_et` is not yet consumed by the pipeline orchestrator (item filtering still uses UTC `week_bounds()`), Wave 0 validation tests for DST fall-back and midnight ET boundaries are missing, and one worker README sentence misattributes the StatusBanner to plan 05-06. Workflow YAML quality is solid (timeouts, concurrency, failure pings on cron/sentinel; daily-retry intentionally omits heartbeats per D-B4).

## Critical

*(none)*

## Warning

pipeline/week.py:72-84 — `week_bounds_et` not wired into item filtering — **Warning** — Workflows and `active_digest_week_id()` now resolve archive `week_id` using the D-B6b Saturday-ending ET rule, but `pipeline/orchestrator.py`, `dedup/cluster.py`, and `reporting/pipeline_report.py` still call `week_bounds(week_id)` (UTC ISO Mon–Sun). For `2026-W21`, `week_bounds_et` covers Sun 2026-05-17 00:00 ET – Sat 2026-05-23 23:59 ET while `week_bounds` covers Mon 2026-05-18 00:00 UTC – Sun 2026-05-24 23:59 UTC — a ~1-day skew at each end. Items published near Sunday midnight ET can be included or excluded incorrectly despite correct `week_id` resolution in GHA. — **Suggested fix:** Switch orchestrator/dedup/report paths to `week_bounds_et(week_id)` and convert bounds to UTC for `published_at` SQL filters (or add a thin wrapper that returns UTC-aware bounds from ET semantics). Add an integration test asserting a Sunday-evening ET item lands in the expected digest week.

tests/test_week_bounds_et.py:60-66 — DST spring-forward test is weak — **Warning** — `test_week_bounds_et_dst_boundary_spring_forward` only asserts `(end.date() - start.date()).days == 6`, which passes even if start/end wall times or UTC offsets are wrong. It does not verify the window spans the expected calendar dates across the US spring-forward transition (2026-W10 / March 2026). — **Suggested fix:** Assert concrete `start`/`end` datetimes for a week straddling the 2nd Sunday in March (e.g. `2026-W10`: Sun 2026-03-01 00:00 EST → Sat 2026-03-07 23:59:59 EST) and optionally assert `(end.astimezone(UTC) - start.astimezone(UTC)).total_seconds()` equals seven 24-hour periods minus the DST gap.

tests/test_week_bounds_et.py — Missing Wave 0 boundary cases — **Warning** — `05-VALIDATION.md` Wave 0 requires DST boundary cases and ET Sun–Sat semantics; tests cover one Sunday-morning `active_digest_week_id` fixture and spring-forward day-delta only. Missing: DST fall-back (November), late-Saturday vs early-Sunday around midnight ET for `active_digest_week_id`, and at least one Mon–Sat fixture documenting that daily-retry targets the week published on the most recent Sunday. — **Suggested fix:** Add parametrized fixtures, e.g. `Sat 2026-05-23 23:30 ET → 2026-W21`, `Sun 2026-05-24 00:30 ET → 2026-W21`, `Wed 2026-05-20 10:00 ET → 2026-W20` (last Sunday cron week), and a fall-back week bounds test for `2025-W45` (Nov 2–8 2025).

worker/README.md:38-41 — Incorrect plan attribution for StatusBanner — **Warning** — README states "Plan 05-06 wires the reader-facing banner" but plan 05-06 scope is ET week bounds, heartbeats, and sentinel (`05-06-SUMMARY.md`, `05-06-PLAN.md`). StatusBanner was an earlier phase deliverable (OBS-03 / plan 05-05 area). Misattribution will confuse operators tracing which plan to verify. — **Suggested fix:** Replace with "Plan 05-05 (StatusBanner) surfaces…" or remove the plan number and cite OBS-03 only.

## Info

worker/entrypoint.sh:155,173,179 — Heartbeat curl failures silently ignored — **Info** — `ping_worker_start`, `ping_worker_finish`, and `ping_worker_fail` append `|| true`, so Healthchecks outages do not fail the worker cycle and leave no log line when curl fails. Fail-path `/fail` ping can be lost while the operator sees "Cycle failed" in stderr only. — **Suggested fix:** Log a one-line warning on non-zero curl exit (without printing the URL), e.g. `curl ... || log "heartbeat ping failed (curl exit $?)"`.

.github/workflows/weekly-digest.yml:50-51 — Heartbeat start is hard-fail — **Info** — If `HEALTHCHECK_CRON_URL` is unset or Healthchecks is unreachable, the start ping fails and aborts the entire digest job before pipeline work. This is defensible for ops visibility but means a heartbeat misconfiguration blocks digest delivery entirely. — **Suggested fix:** Document in `worker/setup-healthchecks.md` §3 that a missing cron secret prevents the pipeline from running; optionally add `continue-on-error: true` on the start ping only if digest delivery should proceed without heartbeat (trade-off against D-B7).

README.md:283-301 — Operations section omits heartbeat pointer — **Info** — Root README Operations documents D-B6b week boundaries clearly (window, Saturday-ending rule, example, `active_digest_week_id` consumers) but does not mention the three Healthchecks checks or link to `worker/setup-healthchecks.md`. Operators reading only the root README may miss heartbeat setup. — **Suggested fix:** Add one sentence under Operations: "Heartbeat setup (three Healthchecks checks): see `worker/setup-healthchecks.md`."

tests/test_week_bounds_et.py:1-10 — Stale RED-stub header comments — **Info** — Module docstring and several test docstrings still say tests "are expected to FAIL until Plan 05-06 implements" the functions, but implementation is complete and tests pass. — **Suggested fix:** Update docstrings to describe ongoing regression coverage rather than RED-stub intent.

tests/reporting/test_pipeline_report_schema.py:108 — Regression fix verified — **Info** — `cap_usd` assertion correctly updated from `2.0` to `1.0` to match D-B9 hard cap (`fix(05-03)`). No defects found in the regression fix itself.

## Files Reviewed

- `pipeline/week.py`
- `.github/workflows/weekly-digest.yml`
- `.github/workflows/daily-retry.yml`
- `.github/workflows/sentinel.yml`
- `worker/entrypoint.sh`
- `worker/setup-healthchecks.md`
- `worker/README.md`
- `tests/test_week_bounds_et.py`
- `README.md` (Operations section)
- `tests/reporting/test_pipeline_report_schema.py`

### Security & workflow checklist (passed)

| Check | Result |
|-------|--------|
| `HEALTHCHECK_*_URL` never echoed in GHA run logs | Pass — URLs only in `env:` and curl targets |
| Secrets use `${{ secrets.HEALTHCHECK_*_URL }}` | Pass — `weekly-digest.yml:43`, `sentinel.yml:25` |
| `sentinel.yml` permissions | Pass — `contents: read` only (`sentinel.yml:12-13`) |
| `timeout-minutes` on jobs | Pass — cron 30, retry 20, sentinel 10 |
| Concurrency groups | Pass — all three workflows |
| Failure heartbeats | Pass — cron and sentinel ping `/fail` on `if: failure()`; daily-retry intentionally none (D-B4) |
| actionlint clean | Pass per `05-06-SUMMARY.md` self-check |
