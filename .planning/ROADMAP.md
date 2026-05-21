# Roadmap: AI Digest

## Overview

Ship a personal weekly AI digest in five vertical slices — each phase ends with a digest you can actually read, then thickens one layer of the stack. Phase 1 proves the ugly-but-working path (RSS → store → per-item LLM summary → plain HTML). Phases 2–3 widen sources and add dedup, categorization, ranking, and narrative roll-up with cost guardrails. Phase 4 replaces plain HTML with the dark Astro dashboard, full archive, and observability surfaced in the UI. Phase 5 wraps unattended weekly automation: GitHub Actions cron, Cloudflare Pages deploy, secrets hygiene, heartbeat, and hard LLM spend caps.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation + First Digest** - Minimal end-to-end weekly digest from 2–3 RSS sources, per-item TL;DR only, plain HTML
- [ ] **Phase 2: Expand Ingestion** - YouTube, Reddit/HN, and email→RSS adapters with per-source failure isolation
- [ ] **Phase 3: AI Quality** - Dedup-before-LLM, categorization, ranking, weekly roll-up, checkpoints, and cost guardrails
- [ ] **Phase 4: Dashboard + Archive** - Dark Astro dashboard with tabs, full week archive, and pipeline notes in the UI
- [ ] **Phase 5: Ops & Automation** - GHA weekly cron, auto-deploy, secrets, heartbeat, and hard LLM spend ceiling

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

- [ ] 01-02-PLAN.md — All 3 D-01 sources + idempotent upsert + per-source failure isolation

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 01-03-PLAN.md — trafilatura fallback, grounding sentinel, summary_confidence, degraded cards

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 01-04-PLAN.md — `--week` ISO override, CLI subcommands, README/UAT discoverability (D-22)

**Wave 5** *(blocked on Wave 4 completion)*

- [ ] 01-05-PLAN.md — structlog, `last_run.md`, `pipeline_runs` metrics, HTML polish, pytest suite

**Notes:** Deliberately constrained — no Astro, no archive, no dedup, no categorize/rank/rollup. Content-first gate per PITFALLS #25: two readable digests in ugly HTML before dashboard polish. Hallucination mitigation starts here (snippet-only mode, grounding prompt) even though full confidence flags land in Phase 3.

### Phase 2: Expand Ingestion

**Goal:** Broaden source coverage to the full v1 ingestion surface while keeping per-source failures from breaking the weekly run
**Mode:** mvp
**Depends on:** Phase 1
**Requirements:** INGEST-03, INGEST-04, INGEST-05, INGEST-06
**Success Criteria** (what must be TRUE):

  1. A manually triggered weekly run ingests new items from YouTube channels (with transcripts or explicit metadata-only fallback), Reddit/HN, and email→RSS newsletters alongside RSS blogs
  2. When one configured source fails (404, rate limit, empty feed), the digest still publishes with items from all other sources and the failure is recorded with a one-line reason
  3. YouTube items appear in the digest with a clear indicator when transcript is missing (title + description summary, not a blank card)
  4. The human reader sees noticeably broader coverage — video, forum, and newsletter voices appear alongside blog posts in the same plain-HTML digest

**Plans:** TBD

**Notes:** Addresses PITFALLS #7 (YouTube transcript gaps from cloud IP — best-effort fetch + `transcript_status` flag), #15 (HN/Reddit outbound URL unwrapping), #21 (rate limiting). KTN feed URLs treated as secrets even in dev. Research flag: YouTube cloud vs local fetch decision may need a spike during planning.

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

**Plans:** TBD

**Notes:** Primary mitigation phase for Risk Top-5 items #1 (under-dedup), #2 (runaway LLM costs — pre-flight budget, dedup-before-summarize, tiered models, $5/week hard cap), #4 (hallucinated summaries — grounding prompts, confidence flags, hierarchical roll-up per PITFALLS #14). Prompts versioned in files with `prompt_version` in digest metadata (PITFALLS #13).

### Phase 4: Dashboard + Archive

**Goal:** Replace plain HTML with the dark tabbed Astro dashboard, full week-indexed archive, and observability surfaced where the reader looks
**Mode:** mvp
**Depends on:** Phase 3
**Requirements:** DISPLAY-01, DISPLAY-02, DISPLAY-03, DISPLAY-04, DISPLAY-05, DISPLAY-06, DISPLAY-07, DISPLAY-08, ARCHIVE-01, ARCHIVE-02, ARCHIVE-03, ARCHIVE-04, OBS-01
**Success Criteria** (what must be TRUE):

  1. The live site is a dark-themed dashboard with header (project name, week date range, "Updated" timestamp) and tabbed navigation: Briefing + Edtech / Business / Technical / Design
  2. Briefing tab shows the weekly roll-up, numbered Top N stories, and a "Pipeline notes" section listing any sources that failed or were skipped this week
  3. Each story card displays title, TL;DR, publisher attribution(s), source link(s) opening in a new tab, publication date, and a visual hint for YouTube/video content
  4. Every past weekly digest is preserved as committed JSON, browseable via a "Past Weeks" archive index (newest first, one-line excerpt) with permalink pages that render the full digest as it appeared
  5. The site is readable on desktop and modern mobile without layout breakage — the Sunday-morning read experience matches the reference dashboard intent

**Plans:** TBD
**UI hint:** yes

**Notes:** Content-first gate satisfied — wire real digest JSON only after Phase 3 produces quality output. Archive uses per-week JSON + manifest index (PITFALLS #19). Static output must contain zero secrets (PITFALLS #5).

### Phase 5: Ops & Automation

**Goal:** Unattended weekly runs with deploy, monitoring, and spend protection — the digest is ready Sunday morning without manual intervention
**Mode:** mvp
**Depends on:** Phase 4
**Requirements:** OPS-01, OPS-02, OPS-03, OPS-04, OPS-05, OBS-03
**Success Criteria** (what must be TRUE):

  1. The pipeline runs on a GitHub Actions weekly cron schedule and can also be triggered manually via workflow_dispatch for testing or recovery
  2. A successful run commits the new digest JSON, builds the Astro site, and auto-deploys to Cloudflare Pages — hosting stays on a free or near-free tier
  3. API keys and newsletter bridge URLs live only in CI secrets / gitignored config — never in the repo or static site output (pre-commit or CI secret scan passes)
  4. A heartbeat / "last successful run" timestamp is visible on the site; a missed week is obvious within 24 hours (dead-man's-switch ping on successful publish)
  5. If LLM spend hits the hard cap ($5/week), the pipeline halts remaining LLM work and still publishes whatever digest content is complete — partial success beats silence

**Plans:** TBD

**Notes:** Primary mitigation for Risk Top-5 #3 (silent cron failure — post-conditions, heartbeat, failure notification) and #5 (secret leakage). GHA schedule slip (5–15 min) acceptable; overlap protection via lock file. Free-tier hosting on CF Pages + GHA (PITFALLS #23).

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation + First Digest | 1/5 | In progress (Wave 1 done) | - |
| 2. Expand Ingestion | 0/TBD | Not started | - |
| 3. AI Quality | 0/TBD | Not started | - |
| 4. Dashboard + Archive | 0/TBD | Not started | - |
| 5. Ops & Automation | 0/TBD | Not started | - |

---
*Roadmap created: 2026-05-21*
*Mode: Vertical MVP — every phase ships a readable digest*
