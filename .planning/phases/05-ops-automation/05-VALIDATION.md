---
phase: 5
slug: ops-automation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-24
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (Python pipeline) + vitest/astro test (web, where applicable) + GHA workflow lint via `actionlint` |
| **Config file** | `pyproject.toml` (pytest) · `web/package.json` (Astro/Vite) · Wave 0 installs `actionlint` for workflow validation |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -q && cd web && pnpm test --run && actionlint .github/workflows/*.yml` |
| **Estimated runtime** | ~45–60 seconds (pytest), ~15s (web), ~5s (actionlint) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/<targeted> -x -q`
- **After every plan wave:** Run full suite (pytest + web tests + actionlint)
- **Before `/gsd-verify-work`:** Full suite must be green; manual dry-run UATs in `worker/README.md` executed
- **Max feedback latency:** 60 seconds (quick) · 120 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (populated by planner per task) | — | — | OPS-01..05 / OBS-03 | T-05-XX | (per task) | unit/integration/e2e | (per task) | ✅ / ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_week_bounds_et.py` — covers REQ-OPS-01 (Sun-Sat ET week semantics, DST boundary cases, week-id mapping rule from RESEARCH.md)
- [ ] `tests/test_budget_hard_cap.py` — extended; covers REQ-OPS-05 cross-run spend load from `pipeline_runs`, halt-and-mark behavior writing `summary_status='deferred_budget'` (NOT just `break`), LOCKED-01 routing to `_IN_PLACE_TRANSIENT_STATUSES`
- [ ] `tests/test_retry_transient_only.py` — covers daily-retry CLI filter (`summary_status ∈ {quota_exhausted, api_error, client_init_error}` only; cap-deferred items NOT retried)
- [ ] `tests/test_partition_deferred_budget.py` — covers LOCKED-01 compliance: `deferred_budget` ∈ `_IN_PLACE_TRANSIENT_STATUSES`, never routed to footer
- [ ] `tests/test_marker_file.py` — covers B2 marker write/read roundtrip with `week_id` schema validation
- [ ] `web/src/test/StatusBanner.test.ts` — covers OBS-03 banner copy variants (complete / filling-in N videos / partial - N skipped / cap-hit)
- [ ] `actionlint` installed (Wave 0): `brew install actionlint` or curl-install — verifies all new `.github/workflows/*.yml` syntactically before commit
- [ ] `tests/conftest.py` — extend with `b2_stub_fixture` (rclone-mock) and `healthcheck_stub_fixture` (requests-mock)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| First live Sunday cron + Vercel rebuild chain | OPS-01, OPS-03 | External services (GHA scheduler, B2 connectivity, Vercel build hook) — cannot be reliably mocked end-to-end in a test fixture; must observe in production once | Manual `workflow_dispatch` of `weekly-digest.yml` Saturday evening; verify B2 marker written, digest JSON committed, Vercel deploy live within 3 min |
| Home worker container picks up B2 marker | OPS-01 | Polling loop + real B2 latency + Docker container runtime on operator's home server | After cron success, watch container logs for marker detection within 10 min poll window; verify upgraded JSON commit lands within 30 min of marker write |
| Healthchecks.io "ping missed" alert fires | OBS-03 | Requires Healthchecks.io account + real grace-window timing | Disable a workflow for one Sunday; verify email alert arrives within configured grace window (typically 15 min) |
| DST cron drift (±1h ET) | OPS-01 | Annual event; cannot be tested without time travel or the actual DST switch | Observe first Sunday after each DST switch; verify cron fired at expected absolute UTC time (drift is acceptable per D-B1) |
| Vendor-side $10/month cap (Google Cloud Billing) | OPS-05 (layer 2) | External service configuration outside repo | Set the cap in Google Cloud Billing console; document the screenshot path in `worker/README.md`; cannot CI-test |
| Leak-recovery runbook drill | OPS-04 | One-time dry-run with a deliberately revoked test secret | Follow `.planning/runbooks/leak-recovery.md` end-to-end with a throwaway secret; confirm each step is accurate; capture timings |
| `.env.example` placeholders correctly guide a third-party forker | OPS-04 | Subjective ("does this make sense?") — requires another human attempting fresh setup | Fork the repo on a clean machine, follow `worker/README.md` from scratch, no operator help; document friction points |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (week-bounds-ET, hard-cap-halt, retry-transient-only, partition routing, marker file, StatusBanner, actionlint)
- [ ] No watch-mode flags in CI commands
- [ ] Feedback latency < 60s for quick / < 120s for full
- [ ] `nyquist_compliant: true` set in frontmatter after planner validates per-task entries

**Approval:** pending
