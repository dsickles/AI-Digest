---
status: human_needed
phase: 05-ops-automation
verified_at: 2026-05-29T16:35:00Z
must_haves_total: 32
must_haves_verified: 31
gaps_count: 1
human_verification_count: 8
human_verification:
  - test: "Configure GitHub repo secrets (GEMINI_API_KEY, B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET, HEALTHCHECK_CRON_URL, HEALTHCHECK_SENTINEL_URL) and run weekly-digest via workflow_dispatch with a test week_id"
    expected: "Workflow completes green; web/src/content/digests/{week_id}.json and reports/{week_id}.json committed; Healthchecks weekly-cron check shows start + finish pings"
    why_human: "Requires live cloud secrets, network egress, and external heartbeat dashboard"
  - test: "Observe or manually trigger Sunday 10:00 UTC cron on weekly-digest.yml"
    expected: "Scheduled run fires without operator intervention; same artifact commit + B2 sync path as dispatch"
    why_human: "Cron timing cannot be verified from static YAML alone"
  - test: "Deploy aidigest-worker container on residential-IP host with real .env; wait for Sunday cron marker"
    expected: "Worker detects cron-complete marker, runs --only-pending-transcripts, pushes digest upgrade, deletes marker, pings HEALTHCHECK_WORKER_URL"
    why_human: "Requires live B2 bucket, residential IP, and long-running container"
  - test: "Configure static-host Git integration (e.g. Cloudflare Pages) watching repo web/ root"
    expected: "Git push from cron or worker triggers site rebuild; reader can open digest off-network"
    why_human: "Deploy wiring lives in operator dashboard, not repo code"
  - test: "Create three Healthchecks checks; simulate weekly-digest failure (e.g. bad secret)"
    expected: "Failure ping hits /fail; operator receives email within grace period"
    why_human: "Alert delivery requires external service + operator inbox"
  - test: "Run sentinel.yml manually with a missing prior-week digest file"
    expected: "Job fails; HEALTHCHECK_SENTINEL_URL/fail ping fires with reason body"
    why_human: "End-to-end alert path needs configured sentinel secret + Healthchecks account"
  - test: "Force LLM spend to HARD_CAP_USD=1.0 in a staging run"
    expected: "Partial digest publishes; report budget.hard_cap_hit=true; StatusBanner shows partial_cap variant; deferred items render in-place not footer"
    why_human: "Cap halt requires real LLM calls and spend accumulation across items"
  - test: "First-time B2 bucket bootstrap (empty db/ path)"
    expected: "weekly-digest tolerates missing db, creates schema, pushes db + marker on success"
    why_human: "Object-storage first-run path needs live bucket credentials"
gaps:
  - truth: "worker/rclone.conf explicitly gitignored alongside worker/.env"
    status: partial
    reason: ".gitignore matches `.env` (covers worker/.env) but has no rule for worker/rclone.conf; runtime entrypoint materializes rclone config from env so committed copy is optional, yet operators following rclone.conf.example could accidentally commit credentials"
    artifacts:
      - path: .gitignore
        issue: "Missing worker/rclone.conf entry requested by plan 05-01 secret-hygiene truth"
    missing:
      - "Add `worker/rclone.conf` to .gitignore (one-line hardening)"
---

# Phase 05: Ops & Automation — Verification Report

**Verified:** 2026-05-29T16:35:00Z  
**Status:** human_needed  
**Score:** 31/32 must-haves verified  
**Re-verification:** No — initial verification

## Phase Goal

Unattended weekly runs ship the digest Sunday morning without manual intervention — a cloud-scheduled pipeline does the bulk of the work and auto-publishes; a narrow always-on residential-IP worker runs only the operations cloud IPs structurally cannot (YouTube transcript catch-up). Plus monitoring and spend protection.

(Source: `.planning/ROADMAP.md` § Phase 5)

## Success Criteria Verification

### 1. Cloud-side pipeline runs on schedule + manual trigger; cloud secrets in store, not repo

**PASS**

| Check | Evidence |
|-------|----------|
| `schedule:` + `workflow_dispatch:` | `.github/workflows/weekly-digest.yml:16-25` — cron `0 10 * * 0` and `workflow_dispatch` with optional `week_id` input |
| Mon–Sat daily retry | `.github/workflows/daily-retry.yml:17-19` — cron `0 10 * * 1-6` |
| `pipeline.run all --week` | `.github/workflows/weekly-digest.yml:117` — `uv run python -m pipeline.run all --week "${WEEK_ID}"`; CLI surface in `pipeline/run.py:54-61, 258+` |
| No committed secrets (git history heuristic) | `git log --all -p \| grep -iE "(api[_-]?key\|token\|secret).*=.*[a-zA-Z0-9]{20}"` — no credential matches (one false positive on plan prose mentioning `GEMINI_API_KEY`) |
| Secrets use `${{ secrets.* }}` | All workflow env refs use GitHub secrets syntax — e.g. `weekly-digest.yml:40-43,74-75`; `daily-retry.yml:34-35,58-59`; `sentinel.yml:25`; no plaintext URLs in YAML |
| `active_digest_week_id()` not `current_week_id()` | Grep across `.github/workflows/` — zero `current_week_id` hits; workflows import `active_digest_week_id` |

### 2. Successful run renders digest HTML + auto-publishes to free static host

**PASS (code) / HUMAN-NEEDED (live deploy)**

| Check | Evidence |
|-------|----------|
| Commits digest + report JSON | `weekly-digest.yml:140-152` — `git add web/src/content/digests/ web/src/content/reports/` + push; same in `daily-retry.yml:108-120` |
| rclone sync to object storage | `weekly-digest.yml:103-123,125-137` — pull/push `db/aidigest.db`, upload `markers/cron-complete-{week_id}.json` |
| Static-host integration | `worker/README.md:57-59,78-79,164` — documents Git-integration auto-deploy on push to default branch using generic "static host" terminology; no deploy hook required in repo |

Live Cloudflare Pages / equivalent dashboard wiring cannot be verified from code alone.

### 3. Home-server worker runs `--only-pending-transcripts`; idempotent; resumes after missed cycle

**PASS (code) / HUMAN-NEEDED (runtime)**

| Check | Evidence |
|-------|----------|
| Docker tree coherent | `worker/Dockerfile`, `worker/docker-compose.yml`, `worker/entrypoint.sh` present and wired (`Dockerfile:39` → `entrypoint.sh`) |
| Polls `--only-pending-transcripts` | `worker/entrypoint.sh:129` — `pipeline.run all --only-pending-transcripts --week`; poll loop `214-226` |
| Idempotent marker delete | `entrypoint.sh:119-122,198` — `rclone deletefile` after successful cycle |
| Within-window retry | `entrypoint.sh:221` — failed cycle retries after `POLL_INTERVAL` (600s default) |
| Multi-arch image build | `.github/workflows/build-worker-image.yml:44` — `linux/amd64,linux/arm64` |
| Operator docs | `worker/README.md`, `worker/setup-healthchecks.md` exist |

Note: processing is gated to UTC Sunday 09:00–14:00 (`entrypoint.sh:43-50`) per plan 05-05 — intentional rendezvous window, not 24/7 nightly. Recovery from missing the entire Sunday window requires operator re-trigger (marker persists on B2); within-window crash recovery is automatic.

### 4. Heartbeat + failure-only notifications; missed week obvious within 24h

**PASS (code) / HUMAN-NEEDED (alert delivery)**

| Check | Evidence |
|-------|----------|
| weekly-digest heartbeats | `weekly-digest.yml:50-51` `/start`; `154-166` finish with `spent_usd`; `168-170` `/fail` |
| daily-retry heartbeats | **Intentionally absent** — `daily-retry.yml:4-5` documents "No … Healthchecks pings"; plan 05-06 specifies three checks (cron, worker, sentinel) only |
| worker heartbeats | `worker/entrypoint.sh:153-180` — `HEALTHCHECK_WORKER_URL` start/finish/fail via env var |
| sentinel | `.github/workflows/sentinel.yml` — Mon `0 12 * * 1` (~08:00 ET); verifies digest + report exist; checks `budget.hard_cap_hit`; pings `HEALTHCHECK_SENTINEL_URL` pass/fail |
| No plaintext heartbeat URLs in logs | All pings use env vars (`HEALTHCHECK_*`); setup doc uses placeholder `your-healthchecks-ping-url-here` |
| Reader-visible status | `web/src/components/StatusBanner.astro` + `web/src/lib/copy.ts:97-100` — "Last successful run" from `updated_at` on index and digest pages |

### 5. $1/week LLM spend hard cap halts work but still publishes partial digest

**PASS**

| Check | Evidence |
|-------|----------|
| Hard cap $1.00 | `config/digest.yaml:12` — `hard_stop_usd: 1.0`; overridable via `HARD_CAP_USD` env (`pipeline/budget.py:32,180-191`) |
| deferred_budget marking | `pipeline/orchestrator.py:407-465,561` — `_mark_deferred_budget_for_remaining`; `pipeline/render/partition.py:65-73` — in `_IN_PLACE_TRANSIENT_STATUSES` |
| Report fields | `pipeline/reporting/pipeline_report.py:200-201` — `hard_cap_hit`, `deferred_items_count` |
| StatusBanner | `web/src/pages/index.astro:33-38`, `web/src/components/StatusBanner.astro` |
| LOCKED-01 routing | `.planning/LOCKED-DIRECTIVES.md:73-81` — `deferred_budget` in-place amendment |
| Tests | `uv run pytest tests/test_budget_hard_cap.py tests/test_partition_deferred_budget.py -q` → **11 passed** |

ROADMAP SC5 text mentions "$5/week hard cap"; phase 05-CONTEXT and `config/digest.yaml` lock production cap at **$1/week** — implemented value verified.

### 6. Secret hygiene: keys only in cloud secrets and home worker env

**PASS (with one nit gap)**

| Check | Evidence |
|-------|----------|
| `worker/.env` gitignored | `git check-ignore -v worker/.env` → `.gitignore:2:.env` |
| `worker/rclone.conf` gitignored | **GAP (nit)** — not matched by `git check-ignore`; not tracked in git |
| Placeholder examples only | `worker/.env.example:13-41`, `worker/rclone.conf.example:10-14` — `your-*-here` placeholders |
| Repo plaintext key scan | Tracked files: no `sk-`, `ghp_`, or `AIza*` patterns; root `.env` on disk is gitignored and untracked |
| Workflow secret refs | All `${{ secrets.* }}` — see criterion 1 |

### 7. Privacy sweep: generic infrastructure terminology

**PASS**

| Check | Evidence |
|-------|----------|
| No operator identifiers / internal IPs | Grep `worker/`, `.github/workflows/` — no `192.168.*`, `10.*`, personal names, or hostnames |
| Generic terms in Phase 5 docs | `worker/README.md:13-17` — "cloud scheduler, object storage, container runtime, static host" |
| Vendor names scoped to setup | `worker/setup-healthchecks.md`, `worker/.env.example` use necessary env var names (`GEMINI_API_KEY`, `B2_*`); prose in README avoids vendor branding |
| Commit messages | Workflow-generated commits use generic `chore(digest): cloud weekly …` / `home worker transcript catch-up` |

Pre-existing `Gemini` references in older pipeline modules (`pipeline/llm/summarize.py`, etc.) predate Phase 5 and are internal code, not Phase 5 deliverables.

## Requirements Coverage

| Req ID | Plans | Status | Evidence |
|--------|-------|--------|----------|
| OPS-01 | 05-01, 05-02, 05-04, 05-05, 05-06 | **SATISFIED** | `weekly-digest.yml` schedule+dispatch; `daily-retry.yml` Mon–Sat; worker Docker + `build-worker-image.yml`; `sentinel.yml` |
| OPS-02 | 05-01 | **SATISFIED** | `weekly-digest.yml:17-21` `workflow_dispatch` with optional `week_id` |
| OPS-03 | 05-05 | **SATISFIED (code)** | `worker/README.md` static-host Git-integration docs; git push from cron/worker triggers rebuild — live deploy **human** |
| OPS-04 | 05-01, 05-02, 05-05 | **SATISFIED** | Secrets in GHA + `worker/.env.example`; runtime rclone materialization; `.gitignore` covers `.env` |
| OPS-05 | 05-03 | **SATISFIED** | `$1` cap in `config/digest.yaml`; deferred_budget + partial publish path; 11 pytest cases green |
| OBS-03 | 05-03, 05-06 | **SATISFIED (code)** | StatusBanner + last-run timestamp; Healthchecks pings; Monday sentinel — live alert path **human** |

**Traceability note:** `.planning/REQUIREMENTS.md` still marks OPS-02, OPS-05, OBS-03 as `[ ]` pending — documentation drift; all six IDs have plan `requirements_addressed` entries and codebase evidence above.

## Must-Haves Coverage

### 05-01 (4/4 truths — 1 nit)

| Truth | Status |
|-------|--------|
| workflow_dispatch + pipeline.run all commits digest/report | PASS — `weekly-digest.yml:117,146-152` |
| Secret hygiene (.gitignore, worker/.env.example placeholders) | **PARTIAL** — `.env` covered; `worker/rclone.conf` not gitignored (nit) |
| Wave 0 test stubs exist and now pass | PASS — `tests/test_budget_hard_cap.py`, `test_partition_deferred_budget.py`, `test_marker_file.py`, `test_week_bounds_et.py`, `test_retry_transient_only.py` all green |
| Generic terminology in new workflow/docs | PASS |

### 05-02 (4/4)

| Truth | Status |
|-------|--------|
| Sunday cron `0 10 * * 0` | PASS — `weekly-digest.yml:23-25` |
| rclone pull/push `db/aidigest.db` | PASS — `weekly-digest.yml:103-123` |
| cron-complete marker to object storage | PASS — orchestrator `pipeline/orchestrator.py:96-127`; upload `weekly-digest.yml:125-137` |
| rclone.conf from secrets at runtime | PASS — `weekly-digest.yml:67-86` |

### 05-03 (6/6)

| Truth | Status |
|-------|--------|
| LOCKED-01 deferred_budget in `_IN_PLACE_TRANSIENT_STATUSES` | PASS — `partition.py:72` |
| $1/week hard cap + deferred_budget + partial publish | PASS — `budget.py`, `orchestrator.py:561` |
| `budget.hard_cap_hit` + `deferred_items_count` in reports | PASS — `pipeline_report.py:200-201` |
| StatusBanner plain-English variants | PASS — `copy.ts:83-95`, vitest in `web/src/test/StatusBanner.test.ts` |
| Last-successful-run visible without scrolling | PASS — `index.astro:33-38`, `copy.ts:109-113` |
| Cross-run spend from `pipeline_runs` SUM | PASS — `budget.py:194-221`, `get_cumulative_week_spend_usd` |

### 05-04 (5/5)

| Truth | Status |
|-------|--------|
| Mon–Sat `daily-retry.yml` cron | PASS — `daily-retry.yml:18-19` |
| `--retry-transient-only` excludes deferred_budget | PASS — `pipeline/run.py:45-50`; orchestrator exclusion `orchestrator.py:78` |
| Shared weekly spend counter | PASS — `budget.py:76-89,194-221` |
| Retry re-emits digest JSON | PASS — `daily-retry.yml:98-103` explicit render step |
| D-22 documented in README + `--help` | PASS — `README.md:192-195`; `pipeline/run.py:45-50` |

### 05-05 (7/7)

| Truth | Status |
|-------|--------|
| Worker polls markers, runs `--only-pending-transcripts` | PASS — `entrypoint.sh:214-226,129` |
| Multi-arch GHCR publish | PASS — `build-worker-image.yml:44-48` |
| PAT from host `.env` only | PASS — `docker-compose.yml:14-16`; `entrypoint.sh:91-99,148-149` |
| Static site auto-deploy documented | PASS — `worker/README.md:57-79` |
| Marker delete after success | PASS — `entrypoint.sh:198,119-122` |
| Reader-confidence Sun 07:00 ET promise | PASS — `worker/README.md:34-42` |
| Vendor billing console cap documented | PASS — `worker/README.md` layer-2 section |

### 05-06 (6/6)

| Truth | Status |
|-------|--------|
| `week_bounds_et` + `active_digest_week_id` | PASS — `pipeline/week.py:72+`; tests `test_week_bounds_et.py` |
| GHA workflows use `active_digest_week_id()` | PASS — all three pipeline workflows |
| Monday sentinel + 24h alert slice | PASS — `sentinel.yml`; `setup-healthchecks.md` |
| Three heartbeat checks (cron, worker, sentinel) | PASS — wired in respective files |
| Sentinel verifies digest + `hard_cap_hit` false | PASS — `sentinel.yml:51-77` |
| ET boundaries unambiguous for sentinel | PASS — Saturday-ending rule in `week.py:8-12` |

## Gaps

### 1. `worker/rclone.conf` not in `.gitignore`

**Severity:** nit  
**Description:** Plan 05-01 secret-hygiene truth expects both `worker/.env` and `worker/rclone.conf` gitignored. The global `.env` rule covers `worker/.env`, but `worker/rclone.conf` has no explicit rule. Runtime path materializes config from env (`entrypoint.sh:26-41`, `weekly-digest.yml:67-86`), so no committed copy is required — risk is operator copying `rclone.conf.example` into `worker/rclone.conf` and accidentally staging it.  
**Suggested next step:** Add `worker/rclone.conf` to `.gitignore`.

## Human Verification Items

1. **GitHub secrets + manual dispatch** — Configure all repo secrets; run `weekly-digest` via Actions UI; confirm digest JSON commit and Healthchecks cron pings.

2. **Sunday cron fire** — Wait for or simulate scheduled `0 10 * * 0` run; confirm unattended execution.

3. **Home worker end-to-end** — Deploy container with real B2 + PAT; confirm marker rendezvous, transcript catch-up, git push, marker deletion, worker heartbeat.

4. **Static host live deploy** — Connect repo to Cloudflare Pages (or equivalent); confirm push → public URL update.

5. **Healthchecks failure alert** — Induce workflow failure; confirm email/notification within grace period.

6. **Sentinel missing-digest drill** — Run sentinel with absent prior-week JSON; confirm `/fail` ping and alert.

7. **Spend cap staging run** — Run pipeline against real LLM with `$1` cap; confirm partial publish + StatusBanner + in-place deferred cards.

8. **Empty B2 bootstrap** — First cloud run against empty bucket; confirm tolerant db pull and successful marker upload.

## Cross-Cutting Checks

| Check | Result |
|-------|--------|
| Full pytest | `uv run pytest -q` → **215 passed**, exit 0 |
| Budget/partition subset | 11 passed |
| actionlint | `actionlint .github/workflows/*.yml` → exit 0 (v1.7.12) |

## Files Inspected

- `.planning/ROADMAP.md`, `REQUIREMENTS.md`, `LOCKED-DIRECTIVES.md`
- `.planning/phases/05-ops-automation/05-{01..06}-{PLAN,SUMMARY}.md`, `05-CONTEXT.md`, `05-VALIDATION.md`
- `.github/workflows/weekly-digest.yml`, `daily-retry.yml`, `sentinel.yml`, `build-worker-image.yml`
- `worker/Dockerfile`, `docker-compose.yml`, `entrypoint.sh`, `README.md`, `setup-healthchecks.md`, `.env.example`, `rclone.conf.example`
- `pipeline/run.py`, `budget.py`, `orchestrator.py`, `week.py`, `render/partition.py`, `reporting/pipeline_report.py`
- `config/digest.yaml`
- `web/src/components/StatusBanner.astro`, `web/src/lib/copy.ts`, `web/src/pages/index.astro`, `web/src/pages/digest/[week].astro`
- `.gitignore`
- `tests/test_budget_hard_cap.py`, `tests/test_partition_deferred_budget.py`, `tests/test_marker_file.py`, `tests/test_week_bounds_et.py`, `tests/test_retry_transient_only.py`

---

_Verified: 2026-05-29T16:35:00Z_  
_Verifier: gsd-verifier (goal-backward analysis)_
