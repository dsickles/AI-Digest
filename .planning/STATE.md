---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 05 Wave 1 complete — 05-01 (workflow_dispatch + Wave 0 RED stubs + secret hygiene) shipped as 3 atomic commits (aad7bea, 2561fc8, 19f158c). Awaiting wave-2 go.
last_updated: "2026-05-24T22:55:00.000Z"
last_activity: 2026-05-24 -- Phase 5 plan 05-01 complete (Wave 1)
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 32
  completed_plans: 27
  percent: 84
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-21)

**Core value:** A coherent narrative of "what happened in AI this week" across all my sources — read in 15 minutes instead of 5+ hours of skimming feeds.
**Current focus:** Phase 05 — Ops & Automation (Wave 1 of 4 complete; awaiting Wave 2 go from operator)

## Current Position

Phase: 05 (ops-automation) — EXECUTING (Wave 1/4 complete)
Plan: 1 of 6 complete (05-01 shipped; 05-02..05-06 pending)
Status: Wave 1 done — checkpoint pause per wave-by-wave gating mode
Last activity: 2026-05-24 -- Phase 5 plan 05-01 complete (Wave 1)

Progress: 27/32 plans complete (5 phases × ~6 plans avg); Phase 05: 1/6 plans (Wave 1 done, Wave 2 next)
Next: Wave 2 = plans 05-02 (cron + B2 marker) + 05-03 (budget cap + StatusBanner) — run in parallel per plan dependency graph

## Performance Metrics

**Velocity:**

- Total plans completed: 5
- Average duration: ~1h 5m
- Total execution time: ~5h 25m

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 5/5 | 5h 25m | 1h 5m |
| 2 | 4/4 | ~3h | ~45m |

**Recent Trend:**

- Last 4 plans (Phase 2): 02-01 (~1h), 02-02 (~45m), 02-03 (~45m), 02-04 (~30m)
- Trend: Phase 2 executed inline (no subagents) due to gsd-sdk/Claude-only incompatibility; sequential atomic commits per task; deviations documented in 02-VERIFICATION.md

*Updated after each plan completion*

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| Phase 04 P01 | 04-01 | 15min | 2 | 4 |
| Phase 04 P02 | 04-02 | 20min | 2 | 10 |
| Phase 04 P03 | 04-03 | 25min | 2 | 19 |
| Phase 04 P04 | 04-04 | 20min | 2 | 18 |
| Phase 04 P05 | 04-05 | 25min | 2 | 12 |
| Phase 04 P06 | 04-06 | 20min | 2 | 8 |
| Phase 04 P07 | 04-07 | 5min | 1 | 4 |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: Vertical MVP mode — 5 phases, each ends with a readable digest
- Phase 1 deliberately minimal: RSS-only, per-item TL;DR, plain HTML (no Astro/archive/dedup)
- Dedup + full AI pipeline in Phase 3; dashboard in Phase 4; automation in Phase 5
- **01-01:** truststore (not certifi-only) for SSL — uses OS-native trust store on mac/Windows/Linux; fixes corporate-MITM TLS-intercept; cross-platform-safe
- **01-01:** Land `sources` table from RESEARCH schema day-one (not YAML-as-FK-text); items.source_id has real FK from start
- **01-01:** upsert_item preserves item_id on `(source_id, external_id)` collision so item_summaries FK stays stable across re-ingests
- **01-01:** Pre-flight thin-content gate (<30 words) skips LLM call before Gemini; correctly degraded 5/30 Datasette release-note items in live test
- **01-02:** upsert_item uses SQLite ON CONFLICT DO UPDATE with ingested_at refresh — single round-trip idempotency (INGEST-08)
- **01-02:** HTTP 304 Not Modified is success with zero new items, not FetchError
- **01-02:** FetchError remains in adapters/base.py; orchestrator catches per-source without aborting run
- **01-03:** Hybrid enrichment via trafilatura when RSS body < 500 chars; readability-lxml fallback; fetch failures log and continue with snippet
- **01-03:** thin_content sentinel → summary_confidence unavailable; enrichment + short text → low; success → high
- **01-03:** Degraded items render inline as cards with [summary unavailable — content too thin] (D-15), not footer-only
- **01-04:** week_bounds inclusive Mon 00:00 UTC through Sun 23:59:59 UTC; parse_week_id validates ISO week existence
- **01-04:** CLI subcommands ingest|summarize|render|all; bare invocation aliases all (D-19); render path lazy-imports LLM/adapters (D-20)
- **01-04:** --week YYYY-Www threaded from run.py only; orchestrator stage functions accept week_id str with no datetime.now()
- **01-05:** configure_structlog() in logging_config.py; TTY ConsoleRenderer / pipe JSONRenderer
- **01-05:** out/last_run.md overwritten per subcommand; never writes API keys or full article bodies
- **01-05:** HTML header D-18 "Week of …" from week_bounds; [display_name] badges; cards sorted newest-first
- **02-01:** Custom SQLite migration runner with `_strip_sql_line_comments`; idempotent on duplicate-column errors
- **02-01:** `SourceConfig = Annotated[Union[RssSource, YoutubeSource], Field(discriminator="type")]` with `channel_id` regex validation
- **02-01:** Transcript-input truncation cap (`TRANSCRIPT_INPUT_CHAR_CAP`) + `summary_input_truncated` column for downstream attribution
- **02-02:** `IngestErrorCategory` literal (5 categories) drives both `out/last_run.md` rows and `sources.last_error_category` column
- **02-02:** Empty-feed errors are non-fatal and excluded from the pipeline-notice failed-source count (D-41)
- **02-03:** D-05 footer aside removed; `_DEGRADATION_COPY` catalog supplies 5 plain-English reader-surface strings (D-24)
- **02-03:** Header `pipeline-notice` element renders only when pending or failed counts are positive (D-26 zero-state hide)
- **02-03:** `html.escape(quote=False)` for body text preserves apostrophes; attribute context still uses `quote=True`
- **02-04:** Only the catch-up path (`catch_up=True`) may flip `TranscriptsDisabled` to `missing` — cloud ingest never sets `missing`
- **02-04:** `YoutubeAdapter.__init__` resolves default `transcript_fetcher` at call time via module lookup so tests can monkeypatch `_transcript_text` globally
- **02-post-UAT (2026-05-22):** **LOCKED** in PROJECT.md: thin / unsummarizable items go to `<aside id="also-seen">` footer with outbound links only; quota-exhausted / 429 / RESOURCE_EXHAUSTED is the ONLY carve-out that earns an in-place "summary couldn't be generated this week" card. Supersedes Phase 1 D-05 and Phase 2 D-25 (both were renderer-design mistakes I introduced in plans; the locked rule overrides any future phase plan). Backed by `item_summaries.summary_status` column (migration 003), `_classify_llm_exception` in summarize.py, and `_partition_cards` in render/html.py.
- **03-03:** Flash rank stage with cluster_ranks persistence; numbered Briefing — Top N at digest top; category sections sorted by rank_position; `_partition_cards` unchanged (LOCKED-01)
- **03-09:** WR-02 closed — `baseline_per_item_from_runs` queries prior ISO week via `prior_week_id()`; first-run pre-flight uses last week's cost/summaries ratio; renderer untouched (LOCKED-01)
- **03-06:** CR-01/IN-01 closed — `delete_cluster_artifacts_for_week` clears ranks/summaries/rollups before cluster delete; `test_run_all_twice_same_week` proves same-week `run_all` idempotency; renderer untouched (LOCKED-01)
- **03-08:** WR-01 closed — `normalize_title` comparison in `_apply_cascade_for_item`; ingest pre-upsert lookup + in-window cascade hook; title-only edits invalidate `item_summaries` and trigger dedup; renderer untouched (LOCKED-01)
- **03-10:** WR-03 closed — `RunStats` per-stage cost fields; `pipeline_report.json` projects `summarize_cost_usd`/`categorize_cost_usd`/`rank_cost_usd` authoritatively; renderer untouched (LOCKED-01)
- **03-07:** CR-02 closed — `ranks_cover_current_clusters` gates rank/rollup skip; stale orphan `cluster_ranks` or weekly rollup force LLM re-run; renderer untouched (LOCKED-01)
- **04-01:** partition.py is canonical LOCKED-01 router; html.py deprecated dev-preview re-export only
- **04-01:** PARTIAL_PUBLISH_COPY reconciled to UI-SPEC long form in partition.py
- **04-02:** digest_json.py emits pre-partitioned JSON with schema_version 1; HTML preview optional via --no-html-preview
- **04-02:** write_pipeline_report archives to web/src/content/reports/{week_id}.json by default
- **04-03:** Astro 6 + Tailwind 4 scaffold; Zod content collections; `/` Briefing slice with header, tabs, Top N cards (DISPLAY-01, 03, 05, 08)
- [Phase 04]: 04-03: pnpm-workspace.yaml allowBuilds for esbuild/sharp under pnpm 11
- [Phase 04]: 04-03: Briefing index reads briefing_top_n and weekly_synthesis from collection only (LOCKED-01)
- [Phase ?]: 04-04: Static routes /{topic} and /digest/{week}/… with TabBar weekPrefix; DigestBriefing shared layout
- [Phase 04]: 04-05: PipelineNotes in Briefing main only; /archive index; OBS-01 tests; fetch failures without conn
- [Phase 04]: 04-06: Phase 4 exit gate — W19/W21 backfill via render-only CLI; emit_digest_json anchor in LOCKED-DIRECTIVES
- [Phase 04]: 04-07: WR-01 closed — permalink slugs from digest.id + canonicalDigestUrl.toLowerCase(); LOCKED-01 routing untouched
- **05-01 (2026-05-24):** Wave 1 vertical slice shipped — `.github/workflows/weekly-digest.yml` is dispatch-only (cron explicitly deferred to 05-02); Wave 0 RED stub layer pins all Phase 5 contracts before any implementation lands (5 pytest + 1 vitest files, each assertion names its target plan); `b2_stub_fixture` + `healthcheck_stub_fixture` give downstream plans a zero-dependency network-free way to test cron/worker/sentinel; `actionlint` is operator-installed via Homebrew **or** the official prebuilt-binary curl script to gitignored `.tools/` (both paths documented in 05-VALIDATION.md footnote)
- **05-01 (2026-05-24):** `worker/.env.example` uses vendor-prescribed env var names (D-B8) — Privacy Sweep applies to prose and literal bucket/repo names, not to standard secret identifiers a forker must recognize
- **Phase 05 discuss-phase (2026-05-24):** 9 decisions locked (D-B1..B9). Cloud scheduler = GHA cron (D-B1). Static publish = Vercel Hobby + Git integration (D-B2). Shared SQLite storage = Backblaze B2 + rclone (D-B3). Cloud-side daily retry = Mon–Sat GHA workflow scoped to transient LLM failures (D-B4). Home worker = multi-arch Docker container (D-B5a) handing off via B2 marker rendezvous, not self-hosted GHA runner (D-B5b — public-repo PR-fork attack surface). Reader-confidence promise = complete digest by Sun 07:00 ET (D-B6a); week boundary = Sun 00:00 ET – Sat 23:59 ET (D-B6b). Heartbeat = Healthchecks.io 3 checks + GHA failure email + Monday sentinel (D-B7). Secret hygiene = repo secrets + host `.env` + fine-grained PAT (annual rotation) + GitHub native scanning, no pre-commit hook (D-B8). LLM spend caps = $1/week app-side + $10/month vendor-side, graceful degrade on hit, cap-deferred items abandoned (no auto-backfill) (D-B9). New sentinel status `summary_status='deferred_budget'` added to `_IN_PLACE_TRANSIENT_STATUSES`. Architecture diagram: Mermaid sequence diagram with 8 actors (Cron, Backblaze, Sources, Gemini, Home Worker, GitHub, Vercel, Reader).

### Pending Todos

| Todo | Surfaces in | Captured | Note |
|------|-------------|----------|------|
| ~~**Gemini billing decision — DEFERRED, trigger updated 2026-05-22 by Phase 3 discuss D-62**~~ | ~~Post-Phase-3 (after 1–2 live weeks of observed post-dedup volume)~~ | ~~2026-05-22 (post Phase 2 visual UAT); updated 2026-05-22 (Phase 3 discuss D-62)~~ | **CLOSED 2026-05-24 by Phase 05 D-B9.** Decision: stay on Gemini free tier; $1/week app-side cap is well below free-tier daily quota and observed normal weekly spend ($0.05–$0.10). Upgrade to paid only if a week's normal spend approaches free-tier limit (currently no such signal). |
| **Pre-public-release documentation set** | Public-release plan (post-Phase-5, before flipping repo visibility) | 2026-05-24 (Phase 05 discuss) | Produce `.planning/ARCHITECTURE.md` (top-level synthesis of system architecture across all 5 phases, citing phase contexts as source-of-truth for phase-scoped decisions), `README.md` (project entry point — what / why / how to read / how to fork), and any supporting "how to read this repo" / changelog / screenshots assets. Operates alongside the Privacy Sweep gate in PROJECT.md. Full target list in PROJECT.md "Pre-public-release Documentation" section. |
| **Live three-feed E2E re-run** | Manual / Plan 01-02 verification | 2026-05-21 (Plan 01-02) | Run `python -m pipeline.run all` twice outside sandbox; confirm item count stable across re-ingest for all three D-01 feeds. |
| **Live backfill UAT** | Manual / Plan 01-04 verification | 2026-05-21 (Plan 01-04) | Run `python -m pipeline.run render --week 2026-W19` outside sandbox; confirm `out/digest-2026-W19.html` produced. |
| **Browser digest UAT** | Manual / Plan 01-05 | 2026-05-21 (Plan 01-05) | Open `out/digest-*.html`; confirm dark theme, Week of header, badges, rel=noopener links. |
| **Phase 2 manual UAT tests 6 (confirmed-missing transcripts) + 7b (deliberate 404 source isolation)** | `02-UAT.md` | 2026-05-22 (Phase 2 close-out) | Tests 1–5, 7a passed visually during 8-source live run. Tests 6 + 7b require deliberate setup (find a captions-disabled YouTube video; misconfigure one RSS source URL) and are deferred to a follow-up session — not blocking Phase 3 entry since the underlying code is unit-tested. |

### Blockers/Concerns

- YouTube transcript reliability from GHA cloud IPs — **shipped in Phase 2 via D-23** (cloud→residential catch-up via `--only-pending-transcripts`; only path that may set `missing`); residual risk is operational and tracked in `02-UAT.md` manual UAT test 5
- ~~Heartbeat provider (Healthchecks.io vs email) — decide during Phase 5 planning~~ — **CLOSED 2026-05-24 by Phase 05 D-B7.** Both: Healthchecks.io for ping-based failure modes (skipped runs, mid-run crashes) + GHA built-in email for workflow-errored failures.
- `gsd-sdk` / Claude-Agent-SDK incompatibility with Cursor — **resolved 2026-05-22 by Phase 3 discuss D-71**: Phase 3 continues inline execution (Phase 2 was 30% faster per plan than Phase 1 subagent mode); pipeline deliverable stays Cursor-independent; Cursor `Task` available for parallel read-only work (research, audits) if needed

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-05-24T16:30:00.000Z
Stopped at: Phase 05 discuss-phase complete — produced 05-CONTEXT.md, 05-DISCUSSION-LOG.md, and `.planning/runbooks/leak-recovery.md`. Architecture sequence diagram locked.
Resume file: `.planning/phases/05-ops-automation/05-CONTEXT.md`
Pending operator follow-ups: 02-UAT.md tests 6 + 7b (fault-injection, opportunistic); Phase 3 learnings extraction skipped — institutional knowledge lives in 03-XX-SUMMARY.md, 03-VERIFICATION.md, 03-HUMAN-UAT.md, and PROJECT.md Key Decisions for now
