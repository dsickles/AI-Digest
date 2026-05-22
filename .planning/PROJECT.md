# AI Digest

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
- [ ] Ingest items from a configured list of RSS-friendly blogs / Substacks
- [ ] Ingest items from configured YouTube channels (transcripts included)
- [ ] Ingest email newsletters via an email→RSS bridge (e.g., Kill the Newsletter or similar)
- [ ] Sources are hard-coded in config for v1 (a single file I edit by hand)

#### AI Pipeline (runs weekly)
- [ ] Per-item TL;DR summary for every new item since last digest
- [ ] Auto-categorize each item into one topic: `edtech`, `business`, `technical`, `design`
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
- **Twitter/X ingestion** — Official API is paid (~$100/mo for usable tiers), unofficial scrapers are brittle and TOS-risky. Cost/complexity not justified for v1.
- **Podcast audio transcription** — RSS gives episode metadata, but summarizing means running Whisper over hours of audio weekly. Significant cost and latency; deferred to v2.
- **LinkedIn creator ingestion** — No clean ingestion path; not worth the scraping fragility for v1.
- **Q&A chat across the archive** — Tempting future feature, but v1 is "read the weekly digest," not "interrogate the corpus."
- **Workday-specific content lens** — Reference screenshot included a "Workday Impact" tab; this is a purely personal project, no employer angle in v1.
- **Real-time / hourly / daily cadence** — Weekly is the design constraint; faster cadences would be a different product.
- **KPI / big-number extraction strip** — The reference dashboard has a "5 big numbers" headline strip; deliberately out of scope for v1 (adds AI complexity for marginal value when the narrative roll-up already conveys the week).

## Context

- **Origin**: I follow a lot of AI resources (blogs, Substacks, YouTube, newsletters, Reddit) across multiple topical concerns (edtech, business, technical/coding, design). It takes hours per week to keep up, and I miss things. I want one place that does the work for me.
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
*Last updated: 2026-05-22 — Phase 2 discuss: added Editorial Principle; dropped Reddit/HN from v1 (deferred to v2 community-pulse)*
