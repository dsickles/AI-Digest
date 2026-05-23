# Roadmap: AI Digest

## Overview

Ship a personal weekly AI digest in five vertical slices — each phase ends with a digest you can actually read, then thickens one layer of the stack. Phase 1 proves the ugly-but-working path (RSS → store → per-item LLM summary → plain HTML). Phases 2–3 widen sources and add dedup, categorization, ranking, and narrative roll-up with cost guardrails. Phase 4 replaces plain HTML with the dark Astro dashboard, full archive, and observability surfaced in the UI. Phase 5 wraps unattended weekly automation: a cloud-scheduled pipeline runs the bulk of the weekly job and auto-publishes the digest to a free off-network static host; a narrow always-on residential-IP worker runs only the operations that cloud IPs structurally cannot (YouTube transcript catch-up via Plan 02-04's `--only-pending-transcripts` path). Plus secrets hygiene, heartbeat, failure-only notifications, and hard LLM spend caps.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation + First Digest** - Minimal end-to-end weekly digest from 2–3 RSS sources, per-item TL;DR only, plain HTML *(2026-05-21)*
- [x] **Phase 2: Expand Ingestion** - YouTube adapter, 8-source catalog, typed failure isolation, in-place degradation renderer, and residential transcript catch-up *(2026-05-22)*
- [x] **Phase 3: AI Quality** - Dedup-before-LLM, categorization, ranking, weekly roll-up, checkpoints, and cost guardrails (completed 2026-05-22)
- [ ] **Phase 4: Dashboard + Archive** - Dark Astro dashboard with tabs, full week archive, and pipeline notes in the UI
- [ ] **Phase 5: Ops & Automation** - Cloud-scheduled weekly pipeline + residential-IP transcript worker, auto-publish to free static host, secrets, heartbeat, failure-only notifications, and hard LLM spend ceiling

## Phase Details

### Phase 1: Foundation + First Digest

**Goal:** Prove the end-to-end path from configured RSS sources to a readable weekly digest — no dedup, no categorization, no dashboard polish
**Mode:** mvp
**Depends on:** Nothing (first phase)
**Requirements:** INGEST-01, INGEST-02, INGEST-07, INGEST-08, PIPELINE-01
**Success Criteria** (what must be TRUE):

  1. Running the pipeline manually on 2–3 configured RSS/Substack sources produces a dated weekly digest file a human can open and read in a browser
  2. Every item in the digest shows title, publisher name, source link, publication date, and a 2–4 sentence TL;DR grounded in the fetched content
  3. Re-running ingestion for the same week does not create duplicate items (same story keyed by source + external ID)
  4. Summaries flag or degrade gracefully when RSS content is too thin to summarize (no invented facts)

**Plans:** 5 plans

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Walking Skeleton: scaffold + 1 RSS source → SQLite → Gemini → HTML (`01-SKELETON.md`) *(2026-05-21)*

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — All 3 D-01 sources + idempotent upsert + per-source failure isolation *(2026-05-21)*

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — trafilatura fallback, grounding sentinel, summary_confidence, degraded cards *(2026-05-21)*

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-04-PLAN.md — `--week` ISO override, CLI subcommands, README/UAT discoverability (D-22) *(2026-05-21)*

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 01-05-PLAN.md — structlog, `last_run.md`, `pipeline_runs` metrics, HTML polish, pytest suite *(2026-05-21)*

**Notes:** Deliberately constrained — no Astro, no archive, no dedup, no categorize/rank/rollup. Content-first gate per PITFALLS #25: two readable digests in ugly HTML before dashboard polish. Hallucination mitigation starts here (snippet-only mode, grounding prompt) even though full confidence flags land in Phase 3.

### Phase 2: Expand Ingestion

**Goal:** Broaden source coverage by adding the YouTube adapter and additional named-entity RSS sources (per PROJECT.md Editorial Principle), while formalizing per-source failure isolation so one bad source never breaks the weekly run
**Mode:** mvp
**Depends on:** Phase 1
**Requirements:** INGEST-03, INGEST-06
**Success Criteria** (what must be TRUE):

  1. A manually triggered weekly run ingests new items from YouTube channels (with transcripts or explicit metadata-only fallback) alongside the expanded RSS source set
  2. When one configured source fails (404, rate limit, empty feed), the digest still publishes with items from all other sources and the failure is recorded with a one-line reason
  3. YouTube items appear in the digest with a clear indicator when transcript is missing (title + description summary, not a blank card)
  4. The human reader sees noticeably broader coverage — video voices appear alongside the expanded set of blog/newsletter voices in the same plain-HTML digest
  5. Items that fail any pipeline stage (transcript fetch, summary, full-text enrichment) render in-place in their natural sort position with plain-English in-card explanations — no footer aside, no relegation (per the project Reader-surface language policy and In-place degradation rendering rules)

**Plans:** 4 plans

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Schema migration + config union + YoutubeAdapter → first digest with YouTube items (INGEST-03) *(2026-05-22)*

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — Typed failure isolation + 3 new RSS sources → eight-source digest with categorized errors in last_run.md (INGEST-06) *(2026-05-22)*

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-03-PLAN.md — Renderer rewrite: in-place degradation (D-25) + header pipeline notice (D-26); supersedes Phase 1 D-05 *(2026-05-22)*

**Wave 4** *(blocked on Waves 1 + 3 completion)*

- [x] 02-04-PLAN.md — Local catch-up CLI `--only-pending-transcripts` + D-22 discoverability triad (INGEST-03 recovery) *(2026-05-22)*

**Notes:** Addresses PITFALLS #7 (YouTube transcript gaps from cloud IP — best-effort fetch + `transcript_status` flag; cloud-first with local catch-up path). Phase 2 also rewrites the Phase-1 renderer to remove the "Also seen this week" footer aside (Phase 1 D-05 is superseded by the project-level in-place degradation rule). PITFALLS #15 (HN/Reddit URL unwrapping) and #21 (rate limiting for forum sources) no longer apply to v1 — Reddit/HN dropped per Editorial Principle (see INGEST-V2-04 community pulse). PITFALLS #5 (KTN secret URL management) no longer applies to v1 — email→RSS/KTN dropped per Editorial Principle observation that fitting newsletters all publish public RSS (see INGEST-V2-05).

### Phase 3: AI Quality

**Goal:** Transform a chronological item list into a curated weekly briefing — deduped story clusters, categorized tabs-ready items, ranked Top N, narrative roll-up, and bounded LLM spend
**Mode:** mvp
**Depends on:** Phase 2
**Requirements:** DEDUP-01, DEDUP-02, DEDUP-03, DEDUP-04, PIPELINE-02, PIPELINE-03, PIPELINE-04, PIPELINE-05, PIPELINE-06, OBS-02
**Success Criteria** (what must be TRUE):

  1. Near-duplicate stories from overlapping sources collapse into one card with "also covered by" attributions — Briefing Top N no longer fills with five variants of the same launch
  2. Each story is categorized into exactly one topic (`edtech`, `business`, `technical`, `design`) and ranked; the digest opens with a weekly narrative roll-up followed by a numbered Top N on the Briefing view
  3. Re-running the pipeline twice in the same week produces the same digest (idempotent); killing the run mid-way and resuming does not re-bill already-summarized items
  4. A structured `pipeline_report.json` accompanies each run (items ingested, deduped, LLM calls, cost USD, errors) and LLM spend stays within the $2/week target with a configurable hard stop
  5. The human reader can skim the full digest in ~15 minutes and get a coherent sense of "what happened in AI this week" — the Core Value hypothesis is testable

**Plans:** 10 plans (5 shipped + 5 gap closure)

Plans:
**Wave 1**

- [x] 03-01-PLAN.md — Dedup foundation: migration 004, Tier 0/1 dedup, canonical-only summarize, "Also covered by" attribution (DEDUP-01..04)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02-PLAN.md — Categorize: shared exceptions, cluster_summaries, digest.yaml, per-category sections (PIPELINE-02)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-03-PLAN.md — Rank + Briefing Top N: cluster_ranks, numbered Briefing section (PIPELINE-03)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 03-04-PLAN.md — Hierarchical rollup: 4 minis + weekly synthesis, editor's note + section openers (PIPELINE-04)

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 03-05-PLAN.md — Cost governance + pipeline_report.json + cascade + CLI flags (OBS-02, PIPELINE-05/06)

**Gap closure** *(verification gaps CR-01..CR-02, WR-01..WR-03, IN-01)*

**Wave 1** *(parallel — no file overlap)*

- [x] 03-06-PLAN.md — FK-safe cluster artifact delete + run_all twice integration test (PIPELINE-05/06 → CR-01, IN-01) *(2026-05-23)*
- [x] 03-09-PLAN.md — Prior-week pre-flight baseline (PIPELINE-05 → WR-02) *(2026-05-23)*

**Wave 2** *(blocked on 03-06)*

- [x] 03-08-PLAN.md — Wire cascade title_changed on ingest (PIPELINE-06 → WR-01) *(2026-05-23)*

**Wave 3** *(blocked on 03-08)*

- [x] 03-10-PLAN.md — Per-stage cost attribution in pipeline_report.json (OBS-02 → WR-03) *(2026-05-23)*

**Wave 4** *(blocked on 03-06, 03-08, 03-10)*

- [x] 03-07-PLAN.md — Rank/rollup checkpoint integrity guards (PIPELINE-05/06 → CR-02) *(2026-05-23)*

**Notes:** Primary mitigation phase for Risk Top-5 items #1 (under-dedup), #2 (runaway LLM costs — pre-flight budget, dedup-before-summarize, tiered models, $5/week hard cap), #4 (hallucinated summaries — grounding prompts, confidence flags, hierarchical roll-up per PITFALLS #14). Prompts versioned in files with `prompt_version` in digest metadata (PITFALLS #13).

### Phase 4: Dashboard + Archive

**Goal:** Replace plain HTML with the dark tabbed Astro dashboard, full week-indexed archive, and observability surfaced where the reader looks
**Mode:** mvp
**Depends on:** Phase 3
**Requirements:** DISPLAY-01, DISPLAY-02, DISPLAY-03, DISPLAY-04, DISPLAY-05, DISPLAY-06, DISPLAY-07, DISPLAY-08, ARCHIVE-01, ARCHIVE-02, ARCHIVE-03, ARCHIVE-04, OBS-01
**Success Criteria** (what must be TRUE):

  1. The live site is a dark-themed dashboard with header (project name, week date range, "Updated" timestamp) and tabbed navigation: Briefing + Edtech / Business / Technical
  2. Briefing tab shows the weekly roll-up, numbered Top N stories, and a "Pipeline notes" section listing any sources that failed or were skipped this week
  3. Each story card displays title, TL;DR, publisher attribution(s), source link(s) opening in a new tab, publication date, and a visual hint for YouTube/video content
  4. Every past weekly digest is preserved as committed JSON, browseable via a "Past Weeks" archive index (newest first, one-line excerpt) with permalink pages that render the full digest as it appeared
  5. The site is readable on desktop and modern mobile without layout breakage — the Sunday-morning read experience matches the reference dashboard intent

**Plans:** 4/6 plans executed

Plans:
**Wave 1**

- [x] 04-01-PLAN.md — Extract partition.py, LOCKED-01 doc anchors, REQUIREMENTS 3-tab reconciliation

**Wave 2** *(blocked on Wave 1)*

- [x] 04-02-PLAN.md — digest_json emitter, orchestrator/report wiring, CLI flags, contract tests (ARCHIVE-01, OBS-01)

**Wave 3** *(blocked on Wave 2)*

- [x] 04-03-PLAN.md — Astro 6 + Tailwind 4 scaffold, Zod collections, `/` Briefing slice (DISPLAY-01, 03, 05, 08)

**Wave 4** *(blocked on Wave 3)*

- [x] 04-04-PLAN.md — Static tab + archive routes, Card/Footer/PlayIcon components (DISPLAY-02, 04, 06, ARCHIVE-03)

**Wave 5** *(blocked on Waves 2 + 4)*

- [ ] 04-05-PLAN.md — Archive index, PipelineNotes UI, OBS-01 emitter completion (ARCHIVE-02, 04, OBS-01, DISPLAY-07)

**Wave 6** *(blocked on Wave 5)*

- [ ] 04-06-PLAN.md — Backfill W19 + W21, full pytest + pnpm build gate, README/UAT (integration)

**UI hint:** yes

**Notes:** Content-first gate satisfied — wire real digest JSON only after Phase 3 produces quality output. Archive uses per-week JSON + manifest index (PITFALLS #19). Static output must contain zero secrets (PITFALLS #5).

### Phase 5: Ops & Automation

**Goal:** Unattended weekly runs ship the digest Sunday morning without manual intervention — a cloud-scheduled pipeline does the bulk of the work and auto-publishes; a narrow always-on residential-IP worker runs only the operations cloud IPs structurally cannot (YouTube transcript catch-up). Plus monitoring and spend protection.
**Mode:** mvp
**Depends on:** Phase 4
**Requirements:** OPS-01, OPS-02, OPS-03, OPS-04, OPS-05, OBS-03
**Runtime architecture (locked 2026-05-23; scope corrected same day, see PROJECT.md Blocking Dependencies):** Cloud-primary pipeline (GHA cron or equivalent) runs ingest → dedup → summarize → categorize → rank → rollup → render → publish. A second narrow worker on the operator's always-on home server (residential IP) drains the YouTube transcript backlog by periodically running `--only-pending-transcripts` against the shared SQLite DB. The original draft of this phase had the home server hosting the whole pipeline; that over-applied the residential-IP requirement, since only YouTube transcript fetching is structurally blocked. The corrected scope leaves the home worker maximally narrow — it's not load-bearing for non-YouTube content, an RSS-only week wouldn't need it to run at all, and a missed worker cycle lags transcripts by one window without breaking anything else. Plan 02-04's `pending_local` machinery is now the load-bearing architectural seam, not a vestigial workaround.
**Success Criteria** (what must be TRUE):

  1. The cloud-side pipeline runs on a schedule (Sunday morning + a daily transient-failure retry) and supports manual trigger (`python -m pipeline.run all --week …`); cloud secrets live in the cloud provider's secret store, never in the repo
  2. A successful run renders the new digest HTML and auto-publishes it to a free off-network static host — reader can open the digest from anywhere without being on the home network or having any operator-side device awake
  3. The home-server worker runs `--only-pending-transcripts` on its own schedule (e.g. nightly), drains the pending YouTube backlog, and writes back to the shared SQLite DB; the worker is idempotent, recovers from a missed cycle without intervention, and is intentionally non-load-bearing for non-YouTube content
  4. A heartbeat / "last successful run" timestamp is visible on the published site; failure-only notifications fire when a Sunday cloud run misses or when the home worker hasn't checked in for >N days; a missed week is obvious within 24 hours
  5. If LLM spend hits the hard cap (default $5/week — confirm during plan), the pipeline halts remaining LLM work and still publishes whatever digest content is complete — partial success beats silence
  6. Code/secret hygiene: API keys (`GEMINI_API_KEY`, publish-target token) live in cloud secrets and home-worker-local env only — never in the repo, the static site, or any commit message (pre-commit or build-time secret scan passes on both sides)
  7. All Phase 5 deliverables (deployment docs, code comments, commit messages, container/script files if any) use generic infrastructure terminology — no vendor/model names, no first-person operator identifiers, no home-network specifics — per PROJECT.md "Pre-public-release Privacy Sweep". Deviation in this phase becomes scrub work later; honoring the constraint up front keeps the eventual public-release gate small.

**Phase 5 discuss decisions (open):**

- **Cloud scheduler:** GHA cron (default — free, already trusted as source of truth) vs. Cloudflare Workers Cron vs. one-of-the-cheap-cron-as-a-service options. Decided during `/gsd-discuss-phase 5`.
- **Static-publish target:** Cloudflare Pages (default candidate — free, off-network, simple Wrangler CLI) vs. GitHub Pages (free but requires public repo at the free tier; ties timing to the public-release plan). Decided during `/gsd-discuss-phase 5`.
- **Shared SQLite location and sync:** Cloud-primary store with the home worker syncing DB down → drains transcripts → syncs DB up (rsync/rclone/git-LFS/blob storage) is the leading default — keeps the home worker maximally narrow. Alternative: home-worker-primary store with the cloud reading/writing via tunneled connection. Decided during `/gsd-discuss-phase 5`.
- **Plan 02-04 catchup disposition:** Confirmed as the load-bearing home-worker entry point under this architecture. Open sub-decision: also run a transient-failure retry pass for non-transcript items in the cloud cycle (separate from the home worker).
- **Home-worker runtime:** Docker container vs. a thin Python venv invoked by the OS scheduler. Either works; pick the option that fits the home server's existing workload during plan. (Hardware/SKU details intentionally omitted from this doc per privacy sweep.)

**Plans:** TBD (decomposed during `/gsd-plan-phase 5`)

**Notes:** Primary mitigation for Risk Top-5 #3 (silent cron failure — post-conditions, heartbeat, failure-only notification) and #5 (secret leakage). The cloud-primary + residential-worker split came from a Phase 3 architectural correction (2026-05-23): the original "home server hosts the whole pipeline" framing over-applied the residential-IP requirement, which only matters for YouTube transcript fetching (PITFALLS #7, structural). Cloud reliability + zero-host cost wins for everything else; the home server stays narrow and replaceable. RSS-only subscribers (or weeks with no YouTube items in the feed) wouldn't need the home-worker leg at all.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation + First Digest | 5/5 | Complete | 2026-05-21 |
| 2. Expand Ingestion | 4/4 | Complete | 2026-05-22 |
| 3. AI Quality | 5/10 | Gap closure | 2026-05-22 |
| 4. Dashboard + Archive | 4/6 | In Progress|  |
| 5. Ops & Automation | 0/TBD | Not started | - |

---
*Roadmap created: 2026-05-21*
*Last updated: 2026-05-23 — Phase 3 visual UAT closed: LOCKED-01 refined to RSS-thin-only footer, design category cut from v1, Phase 5 runtime architecture locked to cloud-primary + residential-IP transcript worker (corrected from initial "home-server hosts everything" framing); 175 pytest tests green*
*Mode: Vertical MVP — every phase ships a readable digest*
