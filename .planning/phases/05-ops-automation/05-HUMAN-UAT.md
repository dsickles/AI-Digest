---
status: partial
phase: 05-ops-automation
source: ["05-VERIFICATION.md"]
started: 2026-05-29T16:40:00Z
updated: 2026-05-29T16:40:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Configure GitHub repo secrets and run weekly-digest via workflow_dispatch
expected: Workflow completes green; `web/src/content/digests/{week_id}.json` and `reports/{week_id}.json` are committed; Healthchecks weekly-cron check shows start + finish pings.
result: [pending]

### 2. Observe or manually trigger Sunday 10:00 UTC cron on weekly-digest.yml
expected: Scheduled run fires without operator intervention; same artifact commit + B2 sync path as dispatch.
result: [pending]

### 3. Deploy aidigest-worker container on residential-IP host with real .env; wait for Sunday cron marker
expected: Worker detects cron-complete marker, runs `--only-pending-transcripts`, pushes digest upgrade, deletes marker, pings `HEALTHCHECK_WORKER_URL`.
result: [pending]

### 4. Configure static-host Git integration (e.g., Cloudflare Pages) watching repo web/ root
expected: Git push from cron or worker triggers site rebuild; reader can open digest off-network.
result: [pending]

### 5. Create three Healthchecks checks; simulate weekly-digest failure (e.g., bad secret)
expected: Failure ping hits `/fail`; operator receives email within grace period.
result: [pending]

### 6. Run sentinel.yml manually with a missing prior-week digest file
expected: Job fails; `HEALTHCHECK_SENTINEL_URL/fail` ping fires with reason body.
result: [pending]

### 7. Force LLM spend to HARD_CAP_USD=1.0 in a staging run
expected: Partial digest publishes; report `budget.hard_cap_hit=true`; StatusBanner shows `partial_cap` variant; deferred items render in-place, not in footer.
result: [pending]

### 8. First-time B2 bucket bootstrap (empty db/ path)
expected: `weekly-digest` tolerates missing db, creates schema, pushes db + marker on success.
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0
blocked: 0

## Gaps

- **`worker/rclone.conf` not explicitly gitignored** (severity: nit) — `.gitignore` covers `worker/.env` via the `.env` rule but lacks a rule for `worker/rclone.conf`. Runtime entrypoint materializes rclone config from env vars, so the committed file is optional, but operators following `rclone.conf.example` could accidentally commit credentials. Suggested fix: add `worker/rclone.conf` to `.gitignore`. Source: 05-VERIFICATION.md.
