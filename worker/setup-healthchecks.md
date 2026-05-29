# Heartbeat setup (Healthchecks.io)

One-time operator guide for the three heartbeat checks that make silent
cron, worker, or sentinel failures obvious within 24 hours (D-B7, OBS-03).

> **Privacy:** ping URLs are secrets. Store them in GitHub Actions repo
> secrets and the home-worker `.env` only — never commit them to the repo.

## 1. Create an account

Sign up at [healthchecks.io](https://healthchecks.io/) (free tier is
sufficient). Notifications are **email-only** in v1; Discord/Slack webhooks
can be added later from the check integrations panel.

## 2. Create three checks

Create one check per row. Use the exact **Name** values so operator notes
stay aligned with workflow comments.

| Name | Grace period | Expected ping |
|------|--------------|---------------|
| `weekly-cron` | 30 minutes | Sunday ~05:00–06:00 ET (cron runs 10:00 UTC) |
| `weekly-home-worker` | 2 hours | Sunday after cloud cron, before ~09:00 ET |
| `weekly-sentinel` | 30 minutes | Monday ~08:00 ET (workflow runs 12:00 UTC) |

**Grace window guidance:** grace should cover GHA schedule jitter (often
5–30 minutes) plus your pipeline runtime. Tighten after a few healthy weeks
if alerts feel slow; widen if you see false positives.

For each check, copy its **Ping URL** (a long opaque HTTPS URL). You will
not need the URL in logs — workflows curl it via environment variables.

## 3. Wire secrets

| Check | GitHub Actions secret | Home worker `.env` |
|-------|----------------------|-------------------|
| `weekly-cron` | `HEALTHCHECK_CRON_URL` | — |
| `weekly-home-worker` | — | `HEALTHCHECK_WORKER_URL` |
| `weekly-sentinel` | `HEALTHCHECK_SENTINEL_URL` | — |

In GitHub: **Settings → Secrets and variables → Actions → New repository
secret**. Paste each ping URL exactly (no `/start` suffix in the secret — the
workflows append path segments as needed).

In the home worker `.env`, set `HEALTHCHECK_WORKER_URL` to the worker check
ping URL.

## 4. Ping semantics

| Actor | Start | Success | Failure |
|-------|-------|---------|---------|
| Sunday cron | `GET …/start` | `POST …` body `spent_usd=<float>` | `GET …/fail` |
| Home worker | `GET …/start` | `POST …` body `spent_usd=<float>` | `GET …/fail` |
| Monday sentinel | — | `GET …` (plain ping) | `GET …/fail` with reason body |

Weekly LLM spend in the cron/worker success body comes from
`web/src/content/reports/{week_id}.json` → `budget.spent_usd`.

## 5. Monday sentinel

The sentinel workflow (`.github/workflows/sentinel.yml`) runs every Monday
at 12:00 UTC (~08:00 ET). It verifies:

1. `web/src/content/digests/{week_id}.json` exists for the ET-resolved prior
   week (`active_digest_week_id`).
2. `web/src/content/reports/{week_id}.json` has `budget.hard_cap_hit=false`.

If either check fails, the workflow pings `HEALTHCHECK_SENTINEL_URL/fail` so
you receive an email alert. A healthy week pings the success URL.

Trigger manually via **Actions → Weekly sentinel → Run workflow** to test
after wiring secrets.

## 6. Verify

1. **Cron:** run `weekly-digest.yml` via `workflow_dispatch`. Confirm the
   `weekly-cron` check shows a start and success ping in Healthchecks.
2. **Worker:** with the container running, process a marker cycle. Confirm
   `weekly-home-worker` start + success pings.
3. **Sentinel:** run `sentinel.yml` via `workflow_dispatch` on a week with
   committed digest JSON. Confirm `weekly-sentinel` success.

Workflow-level errors also trigger GitHub's built-in failure email — that
covers mid-run crashes the heartbeat may miss.

## Regenerating a leaked URL

If a ping URL is exposed, regenerate the check in Healthchecks, update the
matching secret / `.env`, and follow
[`.planning/runbooks/leak-recovery.md`](../.planning/runbooks/leak-recovery.md).
