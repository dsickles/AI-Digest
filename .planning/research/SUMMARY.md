# Project Research Summary

**Project:** AI Digest
**Domain:** Personal weekly AI news digest — batch ingestion, LLM enrichment, static dashboard
**Researched:** 2026-05-21
**Confidence:** HIGH

## Executive Summary

AI Digest is a **batch pipeline + durable store + static publish** product — the same shape as feed-summarizer, feedmeup, and accio-ai. One user, 15–40 sources, weekly cadence, no auth, no runtime database on the read path. Research across all four dimensions converges on a **split monorepo**: Python pipeline (ingest → dedup → LLM → digest JSON) orchestrated by GitHub Actions, Astro static site reading git-committed digest files, deployed to Cloudflare Pages for $0 hosting.

The recommended approach delivers Core Value — *"coherent narrative of what happened in AI this week in 15 minutes"* — by combining per-item LLM summaries, auto-categorization into four personal topics, ranked Briefing Top N, and a weekly narrative roll-up, rendered as a dark tabbed dashboard with a full week-indexed archive. Stack, architecture, and pitfalls all reinforce **dedup-before-LLM**, **store-and-forward checkpointing**, and **per-source error isolation** as non-negotiable pipeline invariants.

Key risks are operational and quality-shaped, not architectural. The top threats for this specific project are: duplicate-story flood from overlapping AI sources (under-dedup), runaway LLM spend on tail weeks without caps, silent cron failure with no heartbeat, hallucinated summaries from truncated RSS, and YouTube transcript failures when the pipeline runs from cloud IPs. Mitigations are concrete: Tier 0–1 dedup before any LLM call, hard weekly cost ceiling with pre-flight token estimates, post-condition checks + dead-man's-switch on publish, snippet-only mode with confidence flags, and best-effort YouTube with metadata fallback.

## Cross-Cutting Tensions

Research dimensions mostly align; these are the points where they reinforce or pull against each other — resolve before requirements lock.

| Tension | Dimensions | Resolution |
|---------|------------|------------|
| **Dedup scope in v1** | FEATURES lists story clustering as gap (P2); ARCHITECTURE + PITFALLS call dedup-before-LLM mandatory | **URL dedupe (Tier 0) + title fuzzy (Tier 1) are v1 P1**, not v1.x. Story-level SimHash/embedding clustering is v1.x. Without Tier 0–1, Briefing Top N and LLM budget both fail. |
| **Source links & attribution** | FEATURES flags as table-stakes gaps; PROJECT.md omits them; ARCHITECTURE data model includes fields; PITFALLS warns on attribution mismatch | **Add to Active Requirements before roadmap.** Zero LLM cost — pure ingestion + render invariant. Blocks trust if missing. |
| **Per-item `published_at`** | FEATURES gap; ARCHITECTURE normalizer owns field; STACK JSON schema includes `publishedAt` | **Add to Active Requirements.** Already in feed metadata; required for archive UX and ranking (recency bias mitigation). |
| **Pipeline host vs YouTube transcripts** | STACK puts full pipeline in GitHub Actions; PITFALLS recommends residential IP for transcript fetch | **Tension — needs decision.** Start with GHA + yt-dlp/transcript-api; expect ≥20% failure rate from cloud. Fallback: metadata-only items with `transcript_status: missing`. v1.x option: local cron for YouTube-only step pushing to shared store. |
| **Ingest cadence** | ARCHITECTURE recommends daily-ish ingest; PROJECT.md + STACK assume weekly single run | **Accept weekly monolithic run for v1 launch** (15 sources). Move to ingest-every-2-days when source count approaches 40 or KTN feed pruning becomes painful. |
| **Archive search** | FEATURES gap (medium QoL); STACK Astro + git JSON makes Pagefind trivial; PROJECT.md silent | **Defer to v1.x** unless requirements lock adds it. Week/month manifest index covers v1 browse UX. |
| **Observability UI vs logs** | FEATURES: ops requirement without presentation spec; PITFALLS: structured `pipeline_report.json` mandatory | **v1 = logs + JSON report artifact**, not dashboard UI. One-line email/heartbeat summary sufficient. |
| **Content-first vs design-first** | STACK specifies shadcn dark theme; PITFALLS warns dashboard perfectionism delays validation | **Parallel track OK:** mock JSON UI can start early, but **two quality digests in ugly HTML before pixel-polish** is the gate. |

## Cost Guardrails

Concrete targets derived from PROJECT.md constraints + STACK cost model + PITFALLS prevention strategies.

| Guardrail | Target | Hard ceiling | Enforcement |
|-----------|--------|--------------|-------------|
| **LLM spend** | **$0.50–2.00/week** (~$2–8/mo) | **$5/week** — abort remaining LLM calls | Pre-flight token estimate; dedup-before-summarize; truncate transcripts to 6K tokens; Batch API (Gemini Flash-Lite per-item, Flash for roll-up only); log `usage_metadata` per stage |
| **Hosting + infra** | **$0/mo** | **$5/mo** without explicit justification | Cloudflare Pages (static) + GitHub Actions cron (within free tier); Kill the Newsletter free tier; optional domain ~$1/mo amortized |
| **Total personal budget** | **~$0–3/mo** typical | **$10/mo** triggers architecture review | Weekly `pipeline_report.json` with `{ cost_usd, tokens_in, tokens_out }`; alert if >2× rolling 4-week average |

**Cost drivers to watch:** tail weeks (HN front-page explosion), summarizing before dedup (same story ×5), full YouTube transcripts without truncation, re-processing unchanged items (missing `content_hash` gate).

## Risk Top-5

Ranked by **severity × likelihood for this project** (15–40 overlapping AI sources, weekly GHA cron, personal ops with no pager).

| Rank | Risk | Severity | Likelihood | Why this project | Primary mitigation |
|------|------|----------|------------|------------------|-------------------|
| **1** | **Near-duplicate flood (under-dedup)** | High | **High** | 15–40 AI sources routinely repost the same launches; PROJECT.md Top N will feel broken without clustering | Tier 0 URL + Tier 1 title fuzzy **before LLM**; digest references clusters, not raw items; "Also covered by…" in render |
| **2** | **Runaway LLM costs** | Critical | **Medium–High** | 150 items/week × full transcript context on tail weeks; no cap = silent bill shock | Pre-flight budget; dedup-first; tiered models; truncate inputs; hard-stop at $5/week; skip unchanged via `content_hash` |
| **3** | **Silent pipeline / cron failure** | Critical | **Medium** | Personal project, no pager; GHA schedule can slip or auto-disable after 60 days inactivity | Post-conditions (digest exists, item_count > 0, rollup non-empty); dead-man's-switch heartbeat; failure notification email |
| **4** | **Hallucinated / wrong summaries** | Critical | **Medium** | RSS snippets truncated; paywalled Substacks; multi-item batch contamination | Snippet-only mode + `summary_confidence: low`; grounding prompt contract; one-item-per-call or strict JSON validation; 2–4 sentence cap |
| **5** | **YouTube transcript gaps (cloud IP)** | High | **High** | Pipeline in GHA; unofficial APIs block cloud IPs; long videos blow token budget | Best-effort fetch with rate limits; metadata+description fallback; `transcript_status` flag; cap transcript tokens; consider local fetch path in v1.x |

**Honorable mentions (address in phase planning, not top-5):** secret leakage (preventable via CI-only secrets), RSS feed rot (slow-burn over weeks), dashboard perfectionism (scope discipline), lost-in-the-middle roll-up (hierarchical roll-up pattern).

## Key Findings

### Recommended Stack

Split monorepo: **Python 3.12+ pipeline** + **Astro 6.3 static site**, **GitHub Actions** weekly cron, **SQLite** ephemeral working store, **git-committed digest JSON** as archive source of truth, **Cloudflare Pages** hosting. LLM via **google-genai** + Gemini Batch API (Flash-Lite for per-item, Flash for weekly roll-up). Ingestion: feedparser, yt-dlp + youtube-transcript-api, Kill the Newsletter for email→RSS. UI: Tailwind 4 + shadcn/ui dark dashboard with React islands for tabs.

**Core technologies:**
- **Astro 6.3 + Content Collections** — weekly digests are content, not API responses; Zod validation at build; zero runtime cost
- **Python pipeline in GHA** — native ecosystem for RSS, YouTube, LLM batch; single language for all batch work
- **SQLite + git JSON** — dedup/state during run; published archive in `web/src/content/digests/`; git history = free backup
- **Gemini 2.5 Flash-Lite / Flash (batch)** — ~$0.05–0.50/week LLM at 150 items; structured JSON output for categories and ranks
- **Cloudflare Pages** — $0 hosting, unlimited bandwidth, auto-deploy on push

See [STACK.md](./STACK.md) for full version pins, alternatives, and install commands.

### Expected Features

PROJECT.md Active Requirements cover the core differentiators well (weekly narrative roll-up, four topic tabs, LLM ranking, multi-format ingestion, full archive). Feature research confirms scope discipline — Twitter, podcasts, Q&A chat, KPI strip, multi-user are correctly deferred.

**Must have (table stakes) — covered in PROJECT.md:**
- Multi-source automated ingestion (RSS, YouTube, Reddit/HN, email→RSS)
- Per-item LLM summary, auto-categorization, Briefing Top N, weekly roll-up
- Dark tabbed dashboard (Briefing + 4 topics), week-range header, full archive
- Weekly cadence, per-source failure resilience, bounded LLM cost

**Must have (table stakes) — GAPS to add before requirements lock:**

| Gap | Severity | Recommendation |
|-----|----------|------------------|
| **Canonical source link on every item** | HIGH | Add to Presentation: title + summary + tap-through URL |
| **Publisher attribution** (name, favicon, content type badge) | MEDIUM | Add to Presentation; store `display_name` + `source_type` from config |
| **Per-item `published_at`** | MEDIUM | Add to Presentation; already in ARCHITECTURE normalizer |
| **URL-level dedupe minimum** | MEDIUM–HIGH | Add to Ingestion or AI Pipeline; Tier 0 before LLM |
| **Archive search** | MEDIUM | Defer v1.x (Pagefind on Astro is low-effort when needed) |

**Should have (competitive — v1 if time, else v1.x):**
- Story-level dedupe/clustering (Tier 1 title fuzzy minimum for v1)
- Pipeline source-health summary ("3 sources stale this week")
- Edition slug / shareable URL (`/digest/2026-W21`)

**Defer (v2+):**
- Q&A chat, Twitter/X, podcast transcription, multi-user/BYO sources, KPI strip, audio/TTS, email delivery of edition

See [FEATURES.md](./FEATURES.md) for competitor matrix and dependency graph.

### Architecture Approach

**Batch pipeline → SQLite store → dedup → LLM enrich → digest JSON → SSG publish.** Adapters never call LLM; renderer never fetches RSS. Store is the only cross-run memory. Pipeline order: ingest → normalize → persist → **dedup → summarize/categorize → rank → rollup → export JSON → Astro build → deploy**.

**Major components:**
1. **Source Config** (`config/sources.yaml`) — declarative source list; v2 adds DB without changing adapters
2. **Ingest Adapters** — one per type (rss, youtube, reddit, hn, email_rss); per-source try/except
3. **Store (SQLite)** — items, clusters, summaries, digests, pipeline runs; `(source_id, external_id)` PK
4. **Dedup Engine** — Tier 0 URL + Tier 1 title fuzzy before LLM; clusters referenced in digest
5. **LLM Pipeline** — summarize, categorize, rank, hierarchical weekly roll-up
6. **Publisher** — exports typed JSON to Content Collections; triggers static build
7. **Orchestrator** — single CLI entry + GHA workflow; stage checkpoints for idempotent resume

See [ARCHITECTURE.md](./ARCHITECTURE.md) for data model, build order, and failure modes.

### Critical Pitfalls

Beyond the Risk Top-5, phase planning should embed these invariants from [PITFALLS.md](./PITFALLS.md):

1. **Dedup before LLM** — never pay to summarize near-duplicates; watch over-dedup merging distinct angles (category-aware merge rules)
2. **Stage checkpointing** — idempotent stages keyed by `content_hash`; transactional publish; no partial digest
3. **Secrets in CI only** — KTN URLs and API keys never in static output or public repo
4. **Ranking quality** — explicit impact > novelty > recency; source tier weights; hierarchical roll-up to avoid lost-in-the-middle
5. **Scope discipline** — single YAML config file, no BYOS framework, content-first before dashboard polish

## Implications for Roadmap

Suggested phase structure aligned with ARCHITECTURE build order, STACK choices, FEATURE gaps, and pitfall prevention. Phases are sequenced so each produces a testable artifact.

### Phase 1: Pipeline Foundation
**Rationale:** Everything depends on source config contract and normalized item store (ARCHITECTURE critical path steps 1–2).
**Delivers:** `config/sources.yaml` + schema validation; SQLite schema; `NormalizedItem` model; orchestrator skeleton; manual `run ingest` CLI.
**Addresses:** Hard-coded source config (PROJECT.md); source attribution fields in data model (FEATURES gap prep).
**Avoids:** Hard-coded sources in adapter code (Pitfall anti-pattern); BYOS framework too early.

### Phase 2: RSS Ingestion + Resilience
**Rationale:** RSS + email-RSS covers majority of 15–40 sources; proves store upsert and per-source isolation before LLM spend.
**Delivers:** RSS/email-RSS adapters; URL canonicalization; per-source error logging; `published_at`, canonical URL, publisher name on every item.
**Addresses:** RSS/Substack/newsletter ingestion; **source links + attribution + per-item dates** (FEATURES gaps — add to requirements here).
**Avoids:** All-or-nothing pipeline; RSS truncation hallucinations (snippet-only fallback); rate limiting aborts.

### Phase 3: Dedup + LLM Core
**Rationale:** Dedup must precede LLM (ARCHITECTURE + PITFALLS + STACK cost model). Core value lives here.
**Delivers:** Tier 0–1 dedup; summarize + categorize (Flash-Lite batch); cost logging + weekly cap; `content_hash` skip gate; grounding prompts + confidence flags.
**Addresses:** Per-item TL;DR, auto-categorization, bounded LLM cost.
**Avoids:** Runaway costs (#2 risk); near-duplicate flood (#1 risk); hallucinated summaries (#4 risk); prompt drift (versioned prompt files).

### Phase 4: Digest Assembly + Export
**Rationale:** Produces the JSON contract the UI consumes; ranking + roll-up need full week context.
**Delivers:** Rank + Top N selection; hierarchical weekly roll-up (Flash); `WeeklyDigest` JSON export to `web/src/content/digests/`; `pipeline_report.json`.
**Addresses:** Briefing Top N, weekly narrative roll-up, week-range + updatedAt metadata.
**Avoids:** Lost-in-the-middle roll-up; recency bias; mid-run crash data loss (checkpointed stages).

### Phase 5: Dashboard MVP
**Rationale:** Can start with mock JSON after Phase 1 schema known (ARCHITECTURE parallel track); wire real data after Phase 4.
**Delivers:** Astro + Tailwind + shadcn dark theme; Briefing landing + 4 topic tabs; item cards with link, source badge, date; archive index (year → month → week).
**Addresses:** Dark dashboard, tabbed navigation, full archive browse, week-range header.
**Avoids:** Dashboard perfectionism (ship readable before pixel-perfect); unwieldy archive (per-week JSON + manifest index).

### Phase 6: Extended Ingestion (YouTube, Reddit, HN)
**Rationale:** Highest fragility sources isolated after RSS happy path validates pipeline (ARCHITECTURE steps 9–10).
**Delivers:** YouTube adapter (yt-dlp + transcript-api + fallback); Reddit/HN adapters with rate limits; HN/Reddit outbound URL unwrapping.
**Addresses:** YouTube transcripts, Reddit/HN ingestion.
**Avoids:** YouTube transcript gaps (#5 risk); attribution mismatch (discussion URL vs article); IP blocks (per-domain rate limiter).

### Phase 7: Ops + Automation
**Rationale:** Unattended weekly runs require heartbeat, deploy, and observability — last because it wraps working pipeline.
**Delivers:** GHA weekly workflow (cron + workflow_dispatch); Cloudflare Pages deploy; dead-man's-switch heartbeat; failure notifications; source health report in logs; secret scanning CI.
**Addresses:** Weekly cadence, pipeline resilience, cost observability, privacy (no leaked secrets).
**Avoids:** Silent cron failure (#3 risk); secret leakage; free-tier hosting breakage; GHA schedule slip (post-condition checks, not minute-precision).

### Phase Ordering Rationale

- **Config → store → RSS → dedup → LLM → digest JSON → UI** matches ARCHITECTURE critical path and FEATURE dependency graph (roll-up requires summaries requires ingestion).
- **Dedup in Phase 3, not deferred**, despite FEATURES marking story clustering as P2 — URL + title dedup is cheap and blocks both cost and UX failure modes.
- **UI at Phase 5, extended ingest at Phase 6** lets Core Value validate on RSS-only digest before YouTube/Reddit complexity.
- **Ops last** wraps a proven CLI; avoids debugging cron + LLM + YouTube simultaneously.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 6 (YouTube):** Cloud vs local transcript fetch decision; yt-dlp breakage patterns; rate limit tuning — MEDIUM confidence integrations
- **Phase 6 (Reddit):** OAuth vs `.rss` endpoint tradeoffs; current rate limits — MEDIUM confidence
- **Phase 3 (LLM):** Prompt golden-set for categorization consistency; hierarchical roll-up structure — validate with 10 fixture items

Phases with standard patterns (skip research-phase):
- **Phase 1–2:** feedparser + SQLite + YAML config — well-documented (feedmeup, feed-summarizer precedents)
- **Phase 5:** Astro Content Collections + shadcn — HIGH confidence, extensive docs
- **Phase 7:** GHA cron + CF Pages deploy — established pattern from STACK research

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | Official docs verified for Astro, feedparser, Gemini pricing, CF Pages, GHA billing |
| Features | **HIGH** | Competitor features verified from product pages; gap analysis cross-checked against PROJECT.md |
| Architecture | **HIGH** | Patterns validated against feed-summarizer, feedmeup, accio-ai; aligns with chosen stack |
| Pitfalls | **HIGH** | Grounded in PROJECT.md constraints + published LLM/RSS research + recurring automation failures |

**Overall confidence:** **HIGH**

### Gaps to Address Before Requirements Lock

Human reviewer should decide on these before `/gsd-new-project` requirements phase completes:

1. **Add Presentation requirements:** canonical URL, publisher name/badge, per-item `published_at` on every card — table stakes per FEATURES research; zero implementation risk.
2. **Add Ingestion requirement:** URL-level dedupe minimum (Tier 0); strongly recommend Tier 1 title fuzzy for v1 — ARCHITECTURE + PITFALLS + FEATURES align; PROJECT.md currently silent.
3. **YouTube transcript strategy:** accept GHA cloud failures with metadata fallback for v1, or block Phase 6 on local/residential fetch design — STACK vs PITFALLS tension.
4. **Archive search:** explicitly defer to v1.x in Out of Scope or add as v1.x Active — prevents scope creep during Phase 5.
5. **Heartbeat provider:** pick dead-man's-switch service (Healthchecks.io, email, etc.) during Phase 7 planning — PITFALLS marks as non-optional for v1.
6. **Weekly cost ceiling value:** confirm $5/week hard cap vs PROJECT.md "few dollars" — recommend $5 hard / $2 target.

## Sources

### Primary (HIGH confidence)
- [STACK.md](./STACK.md) — Astro, Python, Gemini Batch, CF Pages, feedparser, yt-dlp, KTN
- [FEATURES.md](./FEATURES.md) — competitor matrix, gap analysis, MVP definition
- [ARCHITECTURE.md](./ARCHITECTURE.md) — component boundaries, data model, build order, dedup tiers
- [PITFALLS.md](./PITFALLS.md) — 27 pitfalls mapped to phases with prevention strategies
- [PROJECT.md](../PROJECT.md) — core value, active requirements, out of scope, constraints

### Secondary (MEDIUM confidence)
- [feedmeup](https://github.com/paddedzero/feedmeup) — GHA + RapidFuzz dedup + Astro pattern
- [feed-summarizer](https://github.com/rcarmo/feed-summarizer) — SQLite pipeline + SimHash dedup
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) — Flash-Lite/Flash batch rates
- Liu et al., "Lost in the Middle" (TACL 2024) — roll-up input structuring

---
*Research completed: 2026-05-21*
*Ready for roadmap: yes*
