---
phase: 05-ops-automation
plan: "05"
subsystem: infra
tags: [docker, rclone, github-actions, ghcr, multi-arch, home-worker, object-storage, ops-automation]

requires:
  - phase: 05-ops-automation
    plan: "02"
    provides: rclone copy rendezvous pattern, cron-complete marker filename contract, CLOUD_CRON_MODE gate

provides:
  - worker/Dockerfile multi-stage Python 3.12 + uv + rclone + git runtime
  - worker/entrypoint.sh polling loop (600s) with --only-pending-transcripts catch-up
  - worker/docker-compose.yml with env_file outside repo and data volume
  - worker/rclone.conf.example placeholder remote section
  - .github/workflows/build-worker-image.yml linux/amd64 + linux/arm64 GHCR publish
  - worker/README.md container start, PAT, static-host Git integration, D-B6a/D-B9 docs

affects: [05-06-sentinel-heartbeat, public-release]

tech-stack:
  added: [Docker multi-stage build, docker/build-push-action@v7, rclone deletefile, fine-grained PAT git push]
  patterns:
    - "Clone-on-first-run git workspace at /repo with pipeline venv from image /app/.venv"
    - "Sunday UTC 09:00-14:00 processing window with always-on 600s poll loop"
    - "Marker JSON week_id validation before processing (anti-spoof)"
    - "rclone copy never sync for shared object-storage bucket"

key-files:
  created:
    - .dockerignore
    - worker/Dockerfile
    - worker/docker-compose.yml
    - worker/entrypoint.sh
    - worker/rclone.conf.example
    - .github/workflows/build-worker-image.yml
    - .planning/phases/05-ops-automation/05-05-SUMMARY.md
  modified:
    - worker/README.md

key-decisions:
  - "Git clone to /repo on first start — baked image lacks .git; PAT push uses x-access-token remote URL at runtime only"
  - "B2_REMOTE_NAME defaults to b2 to match cloud cron rclone alias; operator can override via .env"
  - "Sunday UTC 09:00-14:00 window gates processing; poll loop stays always-on with 600s sleep"
  - "README uses REGISTRY/OWNER placeholders — no literal registry hostnames in committed operator docs"

patterns-established:
  - "Home worker: marker poll → rclone copy db down → only-pending-transcripts → copy db up → git push → rclone deletefile marker"
  - "Multi-arch worker image CI: repo-root context, worker/Dockerfile, GHCR tags :latest and :sha-{sha}"

requirements-completed:
  - OPS-01
  - OPS-03
  - OPS-04

duration: 35min
completed: 2026-05-29
---

# Phase 05 Plan 05: Home Worker Docker + GHCR Multi-Arch Summary

**Multi-arch home-worker container polls object-storage markers every 600s, runs `--only-pending-transcripts`, pushes digest JSON via fine-grained PAT, and publishes via GHCR build workflow.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-05-29T14:53Z (approx.)
- **Completed:** 2026-05-29T15:29Z
- **Tasks:** 2 (5-05-01 worker runtime · 5-05-02 build-worker-image.yml)
- **Files modified:** 8

## Accomplishments

- **Home worker runtime assembled.** Multi-stage `worker/Dockerfile` ships Python 3.12, frozen uv deps, rclone, git, and `web/` tree. `.dockerignore` excludes secrets and generated artifacts from image layers.
- **Polling entrypoint implements D-B5b rendezvous.** `entrypoint.sh` materializes rclone.conf from env, polls every 600s during Sunday UTC 09:00–14:00, validates marker JSON `week_id`, runs `pipeline.run all --only-pending-transcripts`, uses `rclone copy` (never sync), commits/pushes digest JSON with PAT, deletes marker via `rclone deletefile`, and leaves a Healthchecks finish-ping hook for 05-06.
- **Operator docs extended.** `worker/README.md` documents container start, REGISTRY/OWNER image pull placeholders, fine-grained PAT (`contents:write`, one repo, one year), static-host Git integration auto-deploy (OPS-03), D-B6a reader-confidence promise, D-B9 $10/month vendor billing catch-all cap, and first dry-run procedure — no literal bucket or registry hostnames in README prose.
- **Multi-arch CI publish path.** `.github/workflows/build-worker-image.yml` builds `linux/amd64,linux/arm64` on `worker/**` changes with `packages: write`, pushes `aidigest-worker:latest` and `:sha-{sha}` to GHCR. `actionlint` clean.

## Task Commits

Each task was committed atomically:

1. **Task 5-05-01: worker/ Docker image, compose, entrypoint poll loop** — `890a8fa` (feat)
2. **Task 5-05-02: build-worker-image.yml multi-arch container-registry publish** — `c5ec9ad` (feat)

## Files Created/Modified

**Created (7):**
- `.dockerignore` — excludes `.env`, `data/`, `.git`, planning tree from build context
- `worker/Dockerfile` — multi-stage builder + runtime with rclone/git
- `worker/docker-compose.yml` — env_file outside repo, data volume, restart policy
- `worker/entrypoint.sh` — poll loop, catch-up, git push, marker delete
- `worker/rclone.conf.example` — placeholder B2 remote ini
- `.github/workflows/build-worker-image.yml` — multi-arch GHCR publish

**Modified (1):**
- `worker/README.md` — container start, PAT, static host, dry-run, D-B6a/D-B9

## Decisions Made

- **Clone-on-first-run at `/repo`** — the image cannot ship `.git`; entrypoint shallow-clones `GITHUB_REPO` with PAT and runs pipeline from that tree while using `/app/.venv` for Python packages.
- **Marker JSON validation** — filename match alone is insufficient (T-05-05-03); entrypoint downloads marker body and asserts `week_id` field matches before processing.
- **Generic registry placeholders in README** — `REGISTRY/OWNER/aidigest-worker` pattern keeps committed docs privacy-sweep compliant; GHCR host appears only in workflow YAML (operator-facing dashboard reference).

## Deviations from Plan

None — plan 05-05 executed exactly as written.

## Issues Encountered

None.

## User Setup Required

Before the home worker can run end-to-end:

- **Container registry:** enable GHCR (or substitute registry) and pull `aidigest-worker:latest` after the build workflow runs once.
- **Host `.env`:** copy `worker/.env.example` outside the repo, `chmod 600`, fill object-storage keys, `GEMINI_API_KEY`, fine-grained PAT, `GITHUB_REPO`, heartbeat URLs.
- **Static host:** connect repo `web/` root via Git integration (one-time dashboard step).
- **Vendor billing console:** set $10/month catch-all cap (D-B9 layer 2) outside the repo.

First dry-run steps are documented in `worker/README.md`.

## Next Phase Readiness

Plan 05-06 (sentinel + heartbeat wiring) can proceed — entrypoint has placeholder comments for `/start` ping and finish curl using `HEALTHCHECK_WORKER_URL`. No blockers for 05-06.

Wave 2 plan 05-05 complete. Remaining Phase 5 plan: 05-06.

---
*Phase: 05-ops-automation*
*Plan: 05 — Home worker Docker + GHCR multi-arch*
*Completed: 2026-05-29*

## Self-Check: PASSED

- FOUND: worker/Dockerfile
- FOUND: worker/entrypoint.sh
- FOUND: worker/docker-compose.yml
- FOUND: worker/rclone.conf.example
- FOUND: .github/workflows/build-worker-image.yml
- FOUND: .planning/phases/05-ops-automation/05-05-SUMMARY.md
- FOUND: commit 890a8fa
- FOUND: commit c5ec9ad
