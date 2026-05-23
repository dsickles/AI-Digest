# AI Digest

> **Planning gate:** Read `.planning/LOCKED-DIRECTIVES.md` before
> drafting any CONTEXT.md, PLAN.md, ROADMAP.md, or PROJECT.md change.
> Locked rules cannot be overridden by phase decisions; proposals to
> change them must be surfaced as questions, not buried in plan
> documents.

## What This Is

A personal, fully-automated weekly AI news and information digest delivered as a dark-themed dashboard website. It ingests from a curated set of 15–40 sources (blogs, Substacks, YouTube channels, newsletters, Reddit/HN), uses LLMs to summarize, categorize, rank, and write a weekly narrative roll-up, and presents the result as a "Sunday morning read" with a Briefing landing page and topic tabs.

## Core Value

**A coherent narrative of "what happened in AI this week" across all my sources — read in 15 minutes instead of 5+ hours of skimming feeds.** If everything else fails, this single weekly experience must work.

## Editorial Principle

**The digest is a collection of known entities and their takes — not anonymous community signal.** Every source in v1 is a named author or publication I chose to follow (a blog, Substack, newsletter, YouTube creator). Community-curated aggregators (Reddit, Hacker News) and anonymous discussion are deliberately *not* part of v1 because they convey crowd signal rather than an author's perspective, and they violate the "voices I trust" framing that makes the weekly read coherent. The "what is the community buzzing about" question is a genuinely different product surface — captured for v2 as a "community pulse" view, distinct from the per-author digest.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. v1 hypotheses until shipped. -->

#### Ingestion
- [ ] Ingest items from a configured list of RSS-friendly blogs, Substacks, and newsletters (the Editorial Principle naturally selects for sources that publish public RSS feeds)
- [ ] Ingest items from configured YouTube channels (transcripts included)
- [ ] Sources are hard-coded in config for v1 (a single file I edit by hand)

#### AI Pipeline (runs weekly)
- [ ] Per-item TL;DR summary for every new item since last digest
- [ ] Auto-categorize each item into one topic: `edtech`, `business`, `technical`
- [ ] Rank items and pick a "Top N" for the Briefing landing page
- [ ] Generate a weekly narrative roll-up (editor's note) tying the week together

#### Presentation
- [ ] Dark-themed dashboard website, visually inspired by the reference screenshot
- [ ] Tabbed navigation: `Briefing` landing + `Edtech` / `Business` / `Technical` / `Design`
- [ ] Tools and creator content (YouTube videos, etc.) are surfaced inside relevant topic tabs, not as separate tabs
- [ ] Each digest is dated by week range ("Week of MMM D – MMM D, YYYY") with an "Updated" timestamp
- [ ] Full archive — every past weekly digest is browseable by date

#### Operations
- [ ] Pipeline runs on a weekly cadence (target: end-of-week / Sunday morning ready)
- [ ] Resilient to single-source failures (one bad RSS feed doesn't break the digest)
- [ ] LLM cost stays bounded and observable (not a runaway bill)

### Out of Scope

<!-- Explicit boundaries with reasoning to prevent re-adding. -->

- **Multi-user / accounts / auth** — v1 is just for me; hard-coded source list. Future evolution may turn this into a framework where others bring their own sources, but not in v1.
- **Reddit / Hacker News ingestion (v1)** — Violates the Editorial Principle (known entities and their takes, not anonymous community signal). The value HN/Reddit *would* add is "what's the crowd buzzing about," which is a different product surface — captured as a v2 community-pulse enhancement, not retrofitted into the per-author digest.
- **Email→RSS bridge / Kill the Newsletter (v1)** — Empirically, every newsletter that fits the Editorial Principle so far publishes a public RSS feed (Substack, beehiiv, custom). The KTN bridge is only needed for the residual "email-only" slice (corporate forwards, paid-tier-only content, smaller authors who never moved to Substack). Deferred to v2 as an opt-in extension if a genuinely email-only source enters the picture; not worth the per-source setup tax (subscription confirmation flows, secret URL management) without a real source forcing the issue.
- **Twitter/X ingestion** — Official API is paid (~$100/mo for usable tiers), unofficial scrapers are brittle and TOS-risky. Cost/complexity not justified for v1.
- **Podcast audio transcription** — RSS gives episode metadata, but summarizing means running Whisper over hours of audio weekly. Significant cost and latency; deferred to v2.
- **LinkedIn creator ingestion** — No clean ingestion path; not worth the scraping fragility for v1.
- **Q&A chat across the archive** — Tempting future feature, but v1 is "read the weekly digest," not "interrogate the corpus."
- **Workday-specific content lens** — Reference screenshot included a "Workday Impact" tab; this is a purely personal project, no employer angle in v1.
- **Real-time / hourly / daily cadence** — Weekly is the design constraint; faster cadences would be a different product.
- **KPI / big-number extraction strip** — The reference dashboard has a "5 big numbers" headline strip; deliberately out of scope for v1 (adds AI complexity for marginal value when the narrative roll-up already conveys the week).

## Context

- **Origin**: I follow a lot of AI resources (blogs, Substacks, YouTube, newsletters, Reddit) across multiple topical concerns (edtech, business, technical/coding). It takes hours per week to keep up, and I miss things. I want one place that does the work for me. (Design was originally a fourth concern; cut from v1 scope on 2026-05-23 — UX/product/design tooling stories now route to `technical`.)
- **Reference inspiration**: A weekly AI digest dashboard (Google Apps Script under `script.google.com/a/macros/workday.com/...`) seen elsewhere — dark theme, tabbed layout, weekly date range header, numbered ranked stories with rich summaries. I want to build my own version, not migrate this one.
- **Architectural commitment**: Fully automated ingestion + LLM processing. I should not be hand-curating items into a sheet each week — the whole point is that the machine does the work.
- **Future evolution hint**: v1 hard-codes my source list, but the architecture should not preclude turning this into a "bring your own sources" framework later. Keep source config decoupled from code where reasonable.

## Constraints

- **Tech stack**: Chef's choice — defer to research phase to propose a stack; I'll push back if I disagree. Bias toward modern, well-documented, low-ops choices.
- **Cost**: Personal-use scale. LLM spend should be observable and bounded (a few dollars per week is fine; tens of dollars per week needs justification). Hosting should run on a free or cheap tier.
- **Source list size**: 15–40 sources. Architecture should not collapse at 100+ if v2 expands.
- **Cadence**: Weekly. Pipeline must finish in a window that lets the digest be "ready Sunday morning."
- **Reliability**: One flaky source must not break the entire digest run.
- **Privacy**: Personal-only, no auth for v1, but the site shouldn't accidentally leak anything sensitive (e.g., raw API keys, private newsletter forwarding addresses).
- **Public-release opsec**: The repo is intended to be made public when v1 ships. Anything that identifies the user's specific home infrastructure (NAS vendor/model, OS/orchestrator product names that imply hardware, home-network specifics, RAM/disk specifics) must be scrubbed before flipping the repo visibility — see the dedicated "Pre-public-release Privacy Sweep" section below for categories, files, and commit-history strategy. New content (docs, code, Dockerfiles, deployment scripts) should use generic terminology from the start so the eventual scrub stays bounded.

## Blocking Dependencies & Active Risks

These are external dependencies whose failure mode degrades or blocks the
core value proposition. They must be solved (or have a documented
acceptance) before the project ships beyond personal-laptop use. New
phase plans must check this section and propose resolutions if they
touch a listed dependency.

| Dependency / Risk | Failure mode observed | Status | Notes / acceptance criteria |
|---|---|---|---|
| **Gemini API free-tier quota** is too small for a full weekly run | Phase 3 Week 21 run hit `RESOURCE_EXHAUSTED` mid-summarize; 3 of 28 items came back `quota_exhausted` (now in-place degraded per LOCKED-01 v2). Weekly run with full source list will routinely exceed free RPM. | **Open** — surfaced 2026-05-23 | Acceptable resolutions in priority order: (a) upgrade `GEMINI_API_KEY` to a paid tier (highest-quota path, simplest code change — none); (b) implement `--retry-quota` flag that sleeps + re-runs the summarize stage on the next-day quota window; (c) plug in a fallback LLM provider (OpenAI / Claude) for items that 429 on Gemini. The current code already classifies and persists `summary_status='quota_exhausted'`, so any of (a)–(c) lands cleanly. Minimum bar before "ship": the weekly run completes summarize for ≥95% of canonical items without manual intervention. |
| **YouTube transcript availability from cloud IPs** | `youtube_transcript_api` and equivalents (yt-dlp transcript path, Innertube endpoints) are actively blocked on AWS/GCP/Azure/Fly/Render/Railway and most other cloud egress ranges. YouTube treats this as adversarial traffic and the block is structural, not a config knob. Plan 02-04 worked around it by deferring transcripts (`transcript_status='pending_local'`) and catching up from a residential IP. The "v1 ships unattended" requirement makes this a hard architectural input, not a deferred concern. | **Resolved as architectural decision 2026-05-23** | **Chosen approach: Path 1 — self-hosted runtime on the user's QNAP TS-464 NAS.** The QNAP is always-on, sits behind a residential IP, has Container Station for Docker, and is already owned (zero hardware/ongoing cost). The entire pipeline (ingest, summarize, categorize, rank, rollup, render) runs on the QNAP via a scheduled container; only the static HTML is published to a free off-network host. Plan 02-04's `pending_local` catchup machinery loses most of its purpose under this model since transcripts always succeed first-pass; final disposition (retire vs. repurpose as transient-failure retry) is a Phase 5 decision. The static-publish target (Cloudflare Pages vs. GitHub Pages vs. QNAP WebStation) is also a Phase 5 decision. Alternatives considered and rejected: third-party transcript services (~$10/mo, vendor lock); residential proxy + Whisper (~$40/mo, overkill); GHA cron from cloud IPs (the original Phase 5 assumption — would have produced silent YouTube degradation forever). |

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Weekly cadence (not daily/real-time) | Matches the "Sunday morning read" experience; reduces ingestion + LLM cost; allows narrative roll-up to be meaningful | — Pending |
| Fully automated pipeline (vs. AI-assisted human curation) | The whole point is to remove the manual work; otherwise it's just a fancier Pocket | — Pending |
| Hard-coded source list in v1 (vs. multi-user / "bring your own sources") | Ship fast for the one user who matters (me); revisit "framework" framing after v1 validates the experience | — Pending |
| Briefing landing + 4 topic tabs (vs. mirror reference screenshot's tabs) | Reference mixed topics and content-types; cleaner to have one IA dimension (topics) and weave tools/creators inside each topic | — Pending |
| Defer Twitter/X and podcast transcription to v2 | Twitter API cost + scraper fragility; podcast audio transcription is expensive and slow. Both add risk without proportional value to v1 | — Pending |
| Full archive of past weekly digests (vs. current-only or rolling window) | Cheap to keep, valuable for "remind me what happened in March," reinforces "weekly newspaper" mental model | — Pending |
| Tech stack TBD by research | I'm a developer but don't want to bias the architecture before seeing what's actually best in 2026 | — Pending |
| Drop Reddit/HN from v1 ingestion; defer to v2 as "community pulse" | Sources violate the Editorial Principle ("known entities and their takes, not anonymous community signal"); the crowd-aggregation question is a genuinely different product surface that deserves its own treatment, not a forced fit into the per-author digest | Adopted 2026-05-22 during Phase 2 discuss |
| Drop email→RSS bridge (KTN) from v1; defer to v2 | The newsletters that fit the Editorial Principle (Ed Zitron, Ben's Bites, Last Week in AI, Import AI, One Useful Thing, etc.) all publish public RSS feeds. KTN's residual use case is email-only sources, which haven't surfaced as v1 needs. Avoids per-source subscription/confirmation tax and secret-URL management until a real email-only source forces it | Adopted 2026-05-22 during Phase 2 discuss |
| Cut `design` category from v1; collapse design-tooling stories into `technical` | Phase 3 visual UAT showed the active source list wasn't producing a coherent design lane — the real design-coverage publishers were already covered by `technical` (UX/product/design tooling, creative tools). A near-empty fourth section diluted the briefing without adding signal. Code anchors updated together: `pipeline/llm/categorize.Category`, `VALID_CATEGORIES`, `pipeline/llm/rollup.CATEGORY_ORDER`, `pipeline/llm/rank.CATEGORY_ORDER`, `pipeline/render/html.CATEGORY_ORDER`/`CATEGORY_LABELS`, `pipeline/config._VALID_CATEGORY_TAGS`, `pipeline/llm/prompts/categorize_v1.md`, `pipeline/llm/prompts/rollup_weekly_v1.md`, `pipeline/orchestrator._rollup_week` by_category dict. Restoration is a coordinated change across this same set if a future milestone re-introduces the lane | Adopted 2026-05-23 during Phase 3 visual UAT |
| **LOCKED — Footer-aside is RSS-thin-only** (PROJECT-level directive, NOT overridable by phase plans) | The Sunday-morning read experience requires the main feed to be curated TL;DRs only — but the footer is reserved for RSS items that are genuinely too short to summarize (`summary_status='thin'`), nothing else. Every other "no summary this week" reason — LLM quota exhausted, API error, parse error, client init error, YouTube transcript not yet fetched — renders in-place in the main feed as a degraded card with the locked body `"The summary couldn't be generated this week."` so the reader keeps the publisher, video badge, date, and category context. The 2026-05-22 lock had grouped all "couldn't summarize" causes into the footer; that produced a Phase 3 visual UAT regression where long-form videos with successful transcripts but quota-exhausted summarize calls landed next to genuinely-thin RSS stubs in the footer, which is the wrong reader signal. The 2026-05-23 refinement narrows the footer to `thin` only. **This rule supersedes any phase-level decision (D-05, D-25, the 2026-05-22 lock).** Code anchor: `pipeline/render/html._IN_PLACE_TRANSIENT_STATUSES` is the locked set of statuses that earn the in-place degraded card; only `thin` falls through to the footer aside. | Locked 2026-05-22; refined 2026-05-23 after Phase 3 visual UAT |

## Pre-public-release Privacy Sweep

The repo is private today and is intended to be made public when v1 ships. Before flipping visibility, scrub any user-identifying infrastructure detail. Two motivations:

1. **Personal opsec** — the user doesn't want "this person runs a [specific vendor/model] at home" surfaceable to anyone with the repo URL.
2. **Project portability** — a generically-described self-hosted runtime is more reusable for other readers who land on the repo and want to adapt it.

### Categories to scrub

- **Hardware vendor and model names** — replace with neutral terms ("home server", "self-hosted machine", "always-on Linux box", "operator's NAS").
- **OS / orchestrator product names that imply specific hardware** — replace with generic equivalents ("Docker host", "container runtime", "system cron"). Avoid product names whose presence is a fingerprint.
- **First-person references that identify the operator** — "the user's NAS" → "the operator's home server"; "my laptop" → "a development machine".
- **Home-network details** — internal IPs, VPN/tunnel names, ISP details, geographic hints.
- **RAM/disk specifics tied to a specific model** — keep capability statements ("≥4 GB RAM recommended") but drop framing that points at a particular SKU.

### Files to audit (non-exhaustive — start here, expand as the project grows)

- `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/LOCKED-DIRECTIVES.md`, `.planning/phases/**/*.md`
- `README.md` and any deployment / ops doc that lands during Phase 5
- Any `Dockerfile`, `docker-compose.yml`, deployment script, or systemd / cron unit
- Code comments and module docstrings
- **Commit history** — see below

### Commit-history strategy

Pre-public-release commits already reference identifying detail (e.g. the Phase 5 architecture commit `a003925` and the RAM-confirm commit `d2143fc`). Two acceptable approaches:

1. **Squash before push to public remote** — reset to a clean single commit (or small handful of phase-grouped commits) on a fresh branch with generic messages; push that as the public history. Cleanest; loses development granularity. Usually right for v1 personal projects.
2. **`git filter-repo` rewrite** — rewrite specific phrases across history, force-push the rewritten branch. Preserves granularity; carries rewrite risk and requires extra care if the repo has been pushed to multiple remotes.

Pick during the public-release plan. Either way, do this *before* flipping visibility — once a public push happens with identifying detail, only history-rewrite is recoverable, and the original commits live in any clone someone made in the meantime.

### Gate

The repo's `public` flag is the only thing that matters. No `gh repo edit --visibility public`, no fork-and-rename, no transfer to a public org until this section is satisfied with a written checklist completion in the public-release plan.

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-22 — Phase 2 discuss: added Editorial Principle; dropped Reddit/HN from v1 (→ v2 community-pulse); dropped email→RSS/KTN from v1 (→ v2 if email-only source emerges)*
