# AI Digest — Home Worker

The home worker is a small container that completes the weekly AI digest
after the cloud cron has run. It exists for one reason: the cloud cannot
retrieve YouTube transcripts reliably from data-center IP ranges, so a
process on a residential IP picks up where the cron left off.

Plans 05-01..05-06 build this runtime incrementally. This README documents
what the worker is, what it needs, and how to set it up safely. Phase 5
plan 05-05 lands the actual `Dockerfile`, `docker-compose.yml`, and the
polling `entrypoint.sh`.

> **Public-repo Privacy Sweep:** this document uses generic terms
> (cloud scheduler, object storage, container runtime, static host).
> No hardware vendor, hostname, or network-topology detail belongs in
> this file. Operator-specific values live only in the host-mounted
> `.env` (which is gitignored) and in repo secrets.

## Architecture in one paragraph

A cloud-scheduled job runs the full pipeline weekly. When it finishes it
writes the project's working SQLite database back to a shared
object-storage bucket and drops a small `cron-complete-{week_id}.json`
marker. The home worker polls that bucket on a short interval; when it
sees the marker it pulls the database, fetches the missing YouTube
transcripts, summarizes them, and pushes an upgraded digest JSON to the
repository. The static host watches the repository and rebuilds the
public site on each push. The reader sees a partial digest after the
cron finishes and the complete digest after the home worker finishes.

The full sequence diagram lives in
[`.planning/phases/05-ops-automation/05-CONTEXT.md`](../.planning/phases/05-ops-automation/05-CONTEXT.md).

## Reader-confidence promise (D-B6a)

Open the digest with confidence after **7am ET on Sunday** — by then,
every story including videos has been summarized. The complete weekly
digest is live by **Sunday 07:00 ET** on a healthy run. Plan 05-06 wires
the reader-facing banner that surfaces whichever state the digest is
currently in ("complete" / "filling in N videos" / "partial — N items
skipped this week"). A reader landing before 07:00 ET sees an honest
status; a reader landing after sees the complete week.

## Prerequisites

The worker assumes the operator has, in any order:

- A **shared object-storage bucket** the cloud job and the worker can both
  read and write. Two top-level paths are used: `db/aidigest.db` for the
  SQLite working file, and `markers/cron-complete-{week_id}.json` for the
  handoff signal. Any S3-compatible provider works; this project ships
  `rclone` configuration examples under `worker/rclone.conf.example`.
- A **container runtime** capable of running an `amd64` or `arm64` Linux
  container with a mounted `.env` file and outbound HTTPS. A laptop, a
  Raspberry Pi, a cloud VM — any always-on host with the runtime
  installed will do.
- A **static host** with a Git integration that auto-deploys the contents
  of `web/` on every push to the default branch.
- A **GitHub fine-grained personal access token** scoped to this single
  repository with the `contents:write` permission. Set its expiration to
  one year; the project's secret-rotation cadence is annual, anchored to
  the GitHub expiration email (D-B8).
- A **heartbeat service** with three checks created: weekly cron, weekly
  worker, and weekly sentinel. Use whichever provider you prefer — the
  workflow YAMLs and worker entry point both ping URLs supplied via
  environment variables.

## Configuration

1. Copy `worker/.env.example` to a host-mounted `.env` outside the cloned
   repo (`~/aidigest/.env` is the recommended location). `chmod 600` it.
2. Fill in real values for every variable. The file is **never** committed.
   Lines starting with `your-…-here` are placeholders that will fail at
   startup, so a misconfigured worker fails loudly rather than silently.
3. Mirror the same secrets into the repository's GitHub Actions secrets
   so the cloud cron and the worker share configuration. Use the same
   environment-variable names on both sides.
4. Configure the static host's Git integration in its dashboard. No
   deploy hook or custom CI step is required — the host watches the
   repository directly.

## Secret hygiene (D-B8)

This project is built for a public repository. Secret hygiene has three
defensive layers and an explicit recovery runbook:

- **Layer 1 — never commit secrets.** All cloud-side secrets live in GitHub
  Actions repo secrets. All home-worker secrets live in the host-mounted
  `.env`. The repo only ships placeholders in `worker/.env.example`.
- **Layer 2 — leak prevention.** `.gitignore` covers `.env`, `.env.local`,
  `*.pem`, `*.key`, and `data/*.db`. The post-push secret-scanning provided
  by GitHub is the sole automatic safety net — there is no local
  pre-commit hook by design.
- **Layer 3 — post-leak recovery.** Follow
  [`.planning/runbooks/leak-recovery.md`](../.planning/runbooks/leak-recovery.md)
  step by step the moment a secret is exposed. The runbook is the only
  thing the operator should reach for; it walks revocation, replacement,
  redeployment, and audit in order.

## LLM spend caps (D-B9)

Two independent caps protect against runaway spend:

- **App-side, weekly.** The pipeline halts new LLM calls at $1.00/week
  (well above the project's observed $0.05–$0.10/week normal). Remaining
  items are marked as deferred and rendered in the digest as honest
  "skipped this week — spend cap reached" cards. Plan 05-03 implements
  this cap; the reader banner names the state explicitly.
- **Vendor-side, monthly (layer 2).** In your LLM vendor's billing
  console, configure a **monthly catch-all cap** with a default alert
  threshold of **$10/month**. This is catastrophe control outside the
  repository — the app-side weekly cap is the operational control. A
  screenshot of your billing-console alert setup is optional; keep
  operator-specific console URLs in local notes only.

Cap-deferred items from a prior week are **abandoned permanently**. They
are not retried by the daily-retry workflow. Cap hits are anomalies and
should be visible signals, not smeared across weeks.

## Container image and start

Multi-arch images (`linux/amd64`, `linux/arm64`) publish to your
container registry when `worker/**` changes (workflow
`.github/workflows/build-worker-image.yml`). Substitute **owner** and
**image name** from your registry dashboard — do not hardcode hostnames
in operator notes committed to this repo.

```bash
# Pull (substitute REGISTRY/OWNER from your container-registry dashboard)
docker pull REGISTRY/OWNER/aidigest-worker:latest

# One-time: host .env outside the clone
cp worker/.env.example ~/aidigest/.env
chmod 600 ~/aidigest/.env
# Edit ~/aidigest/.env — see worker/.env.example for every variable.

# Start via compose (from repo root)
export AIDIGEST_ENV_FILE=~/aidigest/.env
export AIDIGEST_DATA_DIR=~/aidigest/data
export WORKER_IMAGE=REGISTRY/OWNER/aidigest-worker:latest
docker compose -f worker/docker-compose.yml up -d

# Logs
docker compose -f worker/docker-compose.yml logs -f aidigest-worker
```

The compose file mounts `AIDIGEST_ENV_FILE` read-only from a path **outside**
the cloned repository and sets `restart: unless-stopped`.

### Fine-grained PAT (D-B8)

Issue a **fine-grained personal access token** in GitHub settings:

- **Repository access:** this repository only (one repo).
- **Permissions:** `contents: write` only — no admin, no workflows, no packages.
- **Expiration:** one year; rotate annually when GitHub sends the expiration
  email (same sitting as object-storage and LLM keys).

Store the token as `GITHUB_TOKEN` in the host `.env` only. It is never baked
into the image or committed.

### Static host auto-deploy (OPS-03)

Connect the repository once in your **static host** dashboard: project root
`web/`, default branch, standard Git integration. **No deploy hook** and no
custom CI deploy step — every `git push` that touches digest JSON triggers an
automatic rebuild. The partial digest push (cloud cron) and the complete
digest push (home worker) use the same mechanism.

## Operations

The container ships with `rclone`, Python 3.12, and the project
dependencies pre-installed. `entrypoint.sh` runs an idle polling loop on a
configurable interval (`WORKER_POLL_INTERVAL_SECONDS`, default 600s) during
the Sunday UTC processing window. When it observes the cron-complete marker
for the current week it pulls the database with `rclone copy` (never `sync`),
runs `python -m pipeline.run all --only-pending-transcripts`, writes the
database back, commits the upgraded JSON, deletes the marker on object
storage, and pings the worker heartbeat URL when configured.

Idempotency is structural: a duplicate cycle finds no marker and exits
immediately. Stopping the container mid-cycle is safe — the next
restart picks up wherever the marker state left off.

### First dry-run (before relying on Sunday automation)

1. **Cloud cron:** trigger `.github/workflows/weekly-digest.yml` via
   `workflow_dispatch` once. Confirm object-storage DB sync, digest commit,
   marker upload, and static-host rebuild.
2. **Home worker:** with the container running, manually upload a
   `cron-complete-{week_id}.json` marker (or wait for a real cron run).
   Watch logs for DB pull → catch-up → git push → marker delete.
3. **Reader check:** load the public site — YouTube items should upgrade
   from degraded placeholders to full summaries after the worker push.

## Health checks and alerting (D-B7)

The cron, the worker, and the Monday sentinel each ping a separate
heartbeat URL at start and at finish. The sentinel additionally verifies
that the prior Sunday's digest landed and that the spend cap was not hit;
its alert is the operator's single Monday-morning signal that something
needs attention. Workflow-level failures are caught separately by the
built-in failure email from the CI provider.

Plan 05-06 walks the operator through one-time heartbeat setup in
[`worker/setup-healthchecks.md`](setup-healthchecks.md).

The Monday sentinel (`.github/workflows/sentinel.yml`) runs at 12:00 UTC
each Monday (~08:00 ET). It confirms the prior week's digest JSON exists,
that `budget.hard_cap_hit` is false in the matching report, and pings the
third heartbeat check. Run it manually from the Actions tab to validate
after wiring secrets.

## What this README does not cover

- **Operator-personal infrastructure.** Hostnames, network topology,
  drive layouts, and similar specifics belong in your own operator
  notes, not in this repository.

