# Pitfalls Research

**Domain:** Personal weekly AI news digest — automated ingestion, LLM batch pipeline, static dashboard
**Researched:** 2026-05-21
**Confidence:** HIGH (grounded in PROJECT.md constraints, published LLM/RSS research, and recurring failure patterns in personal automation projects)

## Out of Scope as Pitfall Shields

Several PROJECT.md Out of Scope decisions are deliberate guardrails, not missing features:

| Out of Scope Item | Pitfalls It Prevents |
|-------------------|---------------------|
| **Twitter/X ingestion** | Paid API burn (~$100/mo), brittle scraper maintenance, TOS/account-ban risk, duplicate flood from retweet chains |
| **Podcast audio transcription** | Whisper cost explosion (hours of audio/week), pipeline latency blowout, mid-run crash recovery complexity |
| **Q&A chat across archive** | Scope creep into RAG/embedding infra, corpus drift, "fix the digest" deferred in favor of "build the chatbot" |
| **Multi-user / auth** | Premature BYOS framework, secret management complexity, dashboard polish before reading experience validates |
| **Real-time / daily cadence** | 7× ingestion + LLM cost, recency-bias ranking dominance, narrative roll-up becomes shallow |
| **KPI / big-number strip** | Extra LLM pass for marginal value, hallucinated "stats," prompt complexity before core digest works |
| **LinkedIn creator ingestion** | Scraping fragility, login-wall breakage, legal/TOS exposure for a personal tool |

---

## Critical Pitfalls

### Pitfall 1: Runaway LLM Costs

**Category:** LLM Pipeline  
**Severity:** critical

**What goes wrong:**
A weekly digest that should cost $1–3/week silently becomes $10–50/week because every item gets a full-context summary, ranking runs over the entire corpus, and failed retries double-bill. One bad week (HN front-page explosion + long YouTube transcripts) can 10× token usage.

**Why it happens:**
Developers estimate cost on "average week" item counts, not tail weeks. Summarization is applied before dedup (same story summarized 5 times). Full article text + full transcript is sent when RSS snippet would suffice. No hard budget cap or pre-flight token estimate.

**How to avoid:**
- Compute a **pre-flight token budget** before any LLM call: `(new_items × avg_tokens_per_item) + rollup_overhead`; abort or sample if over weekly cap.
- **Dedup before summarize** — never pay to summarize near-duplicates.
- Use a **tiered model strategy**: cheap/fast model for per-item TL;DR + categorization; stronger model only for Top-N ranking and weekly roll-up.
- Log **per-run cost** (input/output tokens × price) to a persistent metrics file; alert if > 2× rolling 4-week average.
- Truncate inputs: RSS description first; fetch full text only when snippet < N chars; cap YouTube transcripts at first K tokens + conclusion heuristic.

**Warning signs:**
- Weekly run cost not logged anywhere
- Item count spikes but digest quality doesn't improve proportionally
- Same headline appearing in 3+ summaries with different wording
- Pipeline runtime grows linearly with total archive size (re-processing old items)

**Phase to address:** Pipeline (primary), Ops (cost observability)

---

### Pitfall 2: Hallucinated or Confidently Wrong Summaries

**Category:** LLM Pipeline  
**Severity:** critical

**What goes wrong:**
Summaries invent quotes, misstate who acquired whom, or describe features the source never mentioned. You read the digest, click through, and the source contradicts the summary. Trust in the product collapses in one week.

**Why it happens:**
LLMs fill gaps when RSS snippets are truncated or paywalled. Multi-document context increases cross-item contamination (details from story A bleed into story B). No grounding constraint in prompts. Research shows multi-doc summarization can produce substantial unfaithful content, especially toward the end of long outputs.

**How to avoid:**
- Prompt contract: **"Only state facts present in the provided text; if insufficient, say 'Source does not provide detail on X'"** — never infer.
- Pass **structured metadata** (title, author, URL, source name) alongside body; require summary to reference source title verbatim.
- For truncated/paywalled items: summarize **headline + available snippet only**, flag `summary_confidence: low` in stored data.
- Spot-check pipeline: randomly sample 3 items/week and compare summary to source (automated or 2-minute manual review).
- Keep summaries short (2–4 sentences) — longer summaries hallucinate more.

**Warning signs:**
- Summaries use phrases like "experts say" or "reportedly" without corresponding source text
- Numbers, dates, or company names appear in summary but not in ingested content
- YouTube summaries describe visual demos not present in transcript

**Phase to address:** Pipeline

---

### Pitfall 3: Silent Pipeline / Cron Failure

**Category:** Operations  
**Severity:** critical

**What goes wrong:**
Sunday morning arrives; no new digest. The cron ran (exit code 0) but processed zero items, or the scheduler never fired, or the job hung on a single feed. You don't notice until Monday. Personal projects have no pager; silence equals success.

**Why it happens:**
Cron assumes the environment is stable. Containers sleep on free tiers. No heartbeat. Logs rotate away. "Success" means no exception, not "digest artifact exists for this week."

**How to avoid:**
- **Dead-man's-switch heartbeat**: ping an external monitor (Healthchecks.io, Cronping, or email) on successful digest publish with week ID in payload.
- Assert **post-conditions**: after run, verify `(digest_file exists) AND (item_count > 0) AND (rollup non-empty)`; fail loudly otherwise.
- Send **failure notification** (email/Slack) on non-zero exit or post-condition failure — not optional for v1.
- Log run start/end, item counts per stage, and duration to durable storage (not stdout-only).
- Schedule with **overlap protection** (lock file or DB advisory lock) so a slow run doesn't double-process.

**Warning signs:**
- No digest for current week but no alert received
- Logs show "0 items ingested" with exit 0
- Last successful run timestamp is > 8 days ago
- Cron defined but never tested after deploy/hosting migration

**Phase to address:** Ops (primary), Pipeline (post-condition checks)

---

### Pitfall 4: Mid-Run Crash Loses All Progress

**Category:** Operations  
**Severity:** high

**What goes wrong:**
Pipeline processes 80 items, crashes on item 81 (bad encoding, rate limit, OOM), and restarts from scratch — re-fetching, re-summarizing, re-billing. Or worse: partial digest is published with missing categories.

**Why it happens:**
Monolithic pipeline with no checkpointing. In-memory state only. LLM calls aren't idempotent because prompts include random ordering.

**How to avoid:**
- **Stage-based pipeline** with durable intermediate artifacts: `raw_items.json` → `deduped_items.json` → `summaries.json` → `ranked.json` → `digest.json`.
- Each stage is **idempotent**: skip items already processed (keyed by `(source_id, canonical_url, content_hash)`).
- Use **transactional publish**: write digest to staging path, validate, then atomic rename/swap to live.
- Never publish partial weekly digest; if roll-up fails, keep previous stage artifacts for retry.

**Warning signs:**
- Re-running pipeline re-calls LLM for already-summarized items
- No intermediate files between ingestion and final HTML
- Crash during run means starting `npm run digest` from zero

**Phase to address:** Pipeline (primary), Ops (recovery runbook)

---

### Pitfall 5: Secret / Credential Leakage

**Category:** Operations  
**Severity:** critical

**What goes wrong:**
LLM API keys, Kill-the-Newsletter forwarding addresses, or private RSS bridge URLs end up in the public static site repo, client-side JS, or error pages. A personal tool becomes a credential vending machine.

**Why it happens:**
Static site generators bundle env vars incorrectly. `.env` committed once. Debug endpoints left enabled. Newsletter forwarding addresses treated as non-sensitive.

**How to avoid:**
- **Secrets only in server-side / CI environment** — pipeline runs in GitHub Actions, local cron, or a tiny worker; never in static site build.
- Pre-commit hook or CI check for API key patterns (`sk-`, `OPENAI_`, etc.).
- Separate repos or build contexts: **pipeline repo** (secrets) vs **site repo** (public artifacts only).
- Newsletter bridge addresses are secrets — rotate if exposed; don't embed in rendered HTML.

**Warning signs:**
- API keys in `NEXT_PUBLIC_*` or Vite `VITE_*` vars
- `.env` or `.env.local` in git history
- Digest HTML contains internal fetch URLs or auth tokens in comments/debug blocks

**Phase to address:** Ops (primary), Render (ensure static output is secret-free)

---

### Pitfall 6: RSS Feed Rot and Silent Source Death

**Category:** Ingestion  
**Severity:** high

**What goes wrong:**
3 of 30 sources silently return 404, empty feeds, or HTML login pages. Over a month, half your information diet vanishes. The digest still publishes but gets thinner and more Reddit-heavy without you noticing.

**Why it happens:**
Feed URLs change after platform migrations (Substack → custom domain, WordPress permalink changes). No per-source health tracking. Pipeline catches exceptions per-source but doesn't aggregate "source hasn't contributed in 3 weeks."

**How to avoid:**
- Store **per-source last_success_at, last_item_at, last_error** in source registry.
- Weekly **source health report** in pipeline logs (and optionally in digest footer): "⚠ 3 sources stale."
- Validate feed response: must be XML/RSS, HTTP 200, >0 entries in lookback window or explicit empty-week flag.
- Maintain **known feed URL patterns** per platform (Substack: `{name}.substack.com/feed`) and document manual fix steps in source config comments.

**Warning signs:**
- A favorite newsletter hasn't appeared in digest for 3+ weeks
- Source error count climbs in logs but no human-readable summary
- Feed fetch returns 200 but body is HTML (soft failure)

**Phase to address:** Ingestion (primary), Ops (health alerting)

---

### Pitfall 7: YouTube Transcript Availability Gaps

**Category:** Ingestion  
**Severity:** high

**What goes wrong:**
Configured YouTube channels produce items with title-only summaries ("Transcript unavailable") or pipeline blocks on rate limits. Cloud-hosted fetchers get IP-blocked; official API caps at ~50 captions/day.

**Why it happens:**
Auto-generated captions aren't available on all videos. Undocumented transcript endpoints break without notice. Batch fetching from cloud IPs triggers YouTube blocking. Long videos produce 20K+ token transcripts that blow the LLM budget.

**How to avoid:**
- Treat transcript fetch as **best-effort**: ingest video metadata always; transcript optional with explicit `transcript_status: missing|partial|ok`.
- Run transcript fetch from **residential IP or local cron** (not cloud batch) for v1; defer commercial transcript API unless volume demands it.
- **Rate limit**: max 1 request/2–3 seconds; exponential backoff on 429/blocked.
- Cap transcript length before LLM (e.g., first 6K tokens + last 1K tokens for long talks).
- Fallback summary from **video description + title** when transcript missing — flag as low-confidence.

**Warning signs:**
- All YouTube items fail transcript fetch after deploy to cloud
- Transcript errors cluster at end of channel batch (rate limit signature)
- Summaries of 2-hour podcasts cost more than all blog summaries combined

**Phase to address:** Ingestion (primary), Pipeline (truncation + fallback)

---

### Pitfall 8: Near-Duplicate Flood (Under-Dedup)

**Category:** Dedup & Ranking  
**Severity:** high

**What goes wrong:**
GPT-5 launch appears 8 times from HN, Reddit, 3 blogs, and 2 Substacks. Digest feels redundant; Top-N is the same event with different URLs. Reader stops after item 3.

**Why it happens:**
Dedup keyed only on exact URL match. Same story has different URLs (tracking params, AMP, syndication). Title-only matching misses reworded headlines. Dedup runs after summarization (already paid and committed).

**How to avoid:**
- **Multi-signal dedup**: normalized URL (strip UTM) + title fuzzy match (Jaccard/Levenshtein > 0.85) + optional embedding cosine similarity for same-week items.
- **Cluster, don't delete**: group near-duplicates; pick canonical item (prefer original source > HN > Reddit); show "Also covered by: …" in render, not separate summaries.
- Run dedup **before** any LLM call.
- For HN/Reddit link posts, dedup against **outbound URL**, not discussion URL.

**Warning signs:**
- Top 10 briefing items share >50% topical overlap when read aloud
- Same company/product name in 4+ headlines
- Token spend scales with "big news weeks" faster than unique story count

**Phase to address:** Pipeline (dedup stage), Ingestion (normalize URLs)

---

### Pitfall 9: Over-Dedup Loses Signal

**Category:** Dedup & Ranking  
**Severity:** high

**What goes wrong:**
Aggressive clustering merges legitimately distinct takes (e.g., "OpenAI pricing change" business analysis vs. "implementation impact" technical post). Edtech angle on a model release disappears because a business blog posted first.

**Why it happens:**
Similarity threshold too low. Single canonical pick without topic-aware clustering. Embeddings treat "same event" as "same story" even when angles differ.

**How to avoid:**
- Dedup clusters on **(event, source_tier)** not global merge — allow **max 2 items per cluster** if categories differ (`business` vs `technical`).
- Use **category as dedup gate**: only merge if same category OR similarity > 0.95.
- When merging, preserve **best summary per category** rather than one winner-takes-all.
- Manual override hook in source config: `never_dedup_with: [source_ids]` for opinion sources.

**Warning signs:**
- Topic tabs feel empty during big news weeks while Briefing is repetitive
- Distinct authors with distinct theses collapsed to one bullet
- Dedup log shows merges you disagree with on spot-check

**Phase to address:** Pipeline

---

### Pitfall 10: Recency Bias Overwhelms Importance

**Category:** Dedup & Ranking  
**Severity:** high

**What goes wrong:**
Friday's minor tool launch beats Monday's substantive regulatory shift in Top-N because ranking weights `published_at` heavily. Weekly roll-up reads like "what dropped in the last 48 hours."

**Why it happens:**
Default sort is chronological. LLM ranking prompt says "most important" but context window orders items by date. HN/Reddit items from Saturday dominate the batch.

**Why it happens (continued):**
No explicit "slow-burn" signal. Importance inferred from engagement (HN points) which favors hype cycles.

**How to avoid:**
- Separate **candidate pool** (all week) from **ranking input** (deduped clusters, max ~40 items) — shuffle or stratify by day before sending to ranker.
- Ranking prompt: explicit criteria weights — **impact > novelty > recency**; include cluster size as "multiple sources covered this."
- Boost items with **cross-source corroboration** (appears in 2+ independent sources after dedup).
- Penalize single-source low-engagement items published in last 6 hours (likely unvetted hype).

**Warning signs:**
- Top 5 always from last 48 hours of the week
- Important Monday story missing from Briefing but present buried in topic tab
- Roll-up narrative front-loads Friday news

**Phase to address:** Pipeline

---

### Pitfall 11: Hype Beats "Boring but Important"

**Category:** Dedup & Ranking  
**Severity:** high

**What goes wrong:**
Flashy product demos outrank policy changes, security advisories, or incremental edtech research. Digest optimizes for engagement-shaped signals (HN points, sensational titles) not your stated topic priorities.

**Why it happens:**
LLM rankers favor vivid, concrete stories. Reddit/HN engagement proxies are baked into ingested metadata. No explicit "boringness bonus" for regulatory/academic sources.

**How to avoid:**
- **Source tier weights** in config: e.g., `regulatory`, `research`, `primary` blogs > aggregators > discussion threads.
- Ranking rubric in prompt with **topic-specific criteria** (edtech: pedagogical impact; technical: engineering consequence).
- Reserve **2 of Top-N slots** for "slow news" candidates (items from tier-1 sources regardless of engagement).
- Post-rank sanity check: if all Top-N are from HN/Reddit, re-run ranker with discussion sources excluded.

**Warning signs:**
- Every week reads like a product launch newsletter
- Security/policy items only appear if they went viral
- Your highest-trust sources rarely hit Briefing

**Phase to address:** Pipeline

---

### Pitfall 12: Inconsistent LLM Categorization

**Category:** LLM Pipeline  
**Severity:** high

**What goes wrong:**
Same story type lands in `business` one week and `technical` the next. Topic tabs feel arbitrary. Items with dual relevance get forced into wrong bucket.

**Why it happens:**
Four categories have fuzzy boundaries (AI business news vs. AI engineering). Temperature > 0 or batch inference non-determinism. Category definitions live only in prompt prose, not structured rules.

**How to avoid:**
- **temperature=0** for categorization; process items individually if batch inference causes drift.
- Provide **3–5 few-shot examples per category** in prompt, refreshed when errors found.
- Output **constrained enum** (`edtech|business|technical|design`) with JSON schema validation; retry on invalid.
- Log category distribution weekly; alert if any tab is <10% or >50% of items (distribution drift).
- Allow **primary + secondary** category in data model; render in primary tab, cross-link in secondary.

**Warning signs:**
- Same source consistently miscategorized
- Week-over-week category counts swing wildly without news cycle explanation
- You mentally re-sort items while reading

**Phase to address:** Pipeline

---

### Pitfall 13: Prompt Drift Without Versioning

**Category:** LLM Pipeline  
**Severity:** high

**What goes wrong:**
You tweak the ranking prompt to fix one bad week; next week's summaries change tone, categories shift, and you can't reproduce last month's output. Debugging becomes impossible.

**Why it happens:**
Prompts edited inline in code without version tags. Model provider silently updates model version behind same API name (`gpt-4o` today ≠ `gpt-4o` six months ago).

**How to avoid:**
- Store prompts in **versioned files** (`prompts/summary_v3.txt`); record `prompt_version + model_id` in every digest artifact.
- Pin **model version strings** in config (`gpt-4o-2024-08-06`), not aliases.
- Changelog entry when prompt changes; keep previous version for one month rollback.
- Golden-set regression: 10 fixed items re-processed on prompt change; diff summaries before deploy.

**Warning signs:**
- Can't tell which prompt produced March digest
- Quality shift correlates with unrelated code change
- No `prompt_version` field in stored digest JSON

**Phase to address:** Pipeline, Ops (artifact metadata)

---

### Pitfall 14: Lost-in-the-Middle in Weekly Roll-Up

**Category:** LLM Pipeline  
**Severity:** high

**What goes wrong:**
Weekly narrative roll-up mentions Monday/Tuesday stories and Friday stories but skips mid-week important items. Editor's note feels incomplete when you know something big dropped on Wednesday.

**Why it happens:**
Research-documented U-shaped attention in long contexts — models favor start and end of prompt. Dumping 40 full summaries into one roll-up prompt guarantees middle items are underrepresented.

**How to avoid:**
- **Hierarchical roll-up**: summarize per-category first (4 short paragraphs) → synthesize category summaries into weekly narrative (max ~2K tokens input).
- Or: roll-up input = **Top-N headlines + 1-line summary each**, not full text.
- Explicit prompt instruction: **"Cover each day of the week; name any cluster with 3+ sources."**
- Include structured **week timeline** (date → top clusters) as JSON input, not prose blob.

**Warning signs:**
- Roll-up mentions only 60% of Briefing items
- Mid-week items in Top-N absent from editor's note
- Roll-up quality degrades as item count grows

**Phase to address:** Pipeline

---

### Pitfall 15: Mismatched Item-to-Source Attribution

**Category:** LLM Pipeline  
**Severity:** high

**What goes wrong:**
Summary attached to wrong URL, author credited incorrectly, or HN discussion link shown instead of original article. Click-through goes to unrelated page.

**Why it happens:**
Batch prompts mix multiple items; model confuses metadata fields. Redirect chains resolve to different final URL than displayed. Reddit/HN wrapper URLs not unwrapped before storage.

**How to avoid:**
- **One item per LLM call** for summarization (or strict JSON array with indexed fields validated post-hoc).
- Store immutable **`item_id`** separate from display fields; validate LLM output `item_id` matches input.
- Resolve **canonical URL** at ingestion (follow redirects once; store final URL).
- Unwrap HN/Reddit **outbound links** at ingestion; keep discussion URL as secondary `discussion_url` field.

**Warning signs:**
- Summary mentions source A's framing but links to source B
- Click-through rate drops because links feel "wrong"
- HN items link to `news.ycombinator.com` instead of article

**Phase to address:** Ingestion (URL normalization), Pipeline (attribution validation)

---

### Pitfall 16: Generic "Slop" Summaries and Roll-Ups

**Category:** UX / Reading Experience  
**Severity:** high

**What goes wrong:**
Every summary ends with "This could have significant implications for the AI landscape." Roll-up reads like SEO boilerplate. Digest is technically correct but **unreadable** — you stop opening it.

**Why it happens:**
Default LLM voice is generic assistant. Prompts ask for "summary" without voice constraints. No anti-slop negative examples. Weekly roll-up prompt mirrors tech-media clichés.

**How to avoid:**
- Prompt **voice guide**: concrete, terse, no hedging filler; ban list (`game-changer`, `landscape`, `it's worth noting`, `delve`).
- Require **one specific detail** per summary (number, name, quote, or concrete claim from source).
- Roll-up prompt: **"Write as a sharp editor, not a press release"** + include 2 bad examples to avoid.
- Optionally: few-shot with **your own past blurbs** if you have a preferred style.

**Warning signs:**
- Summaries interchangeable — swap titles and nobody notices
- Roll-up could apply to any week in 2025
- You read original sources anyway because digest adds no value

**Phase to address:** Pipeline (prompts), Render (display formatting helps scannability)

---

### Pitfall 17: Summaries Don't Match Source Tone

**Category:** UX / Reading Experience  
**Severity:** medium

**What goes wrong:**
Snarky blog post summarized in corporate neutral tone. Research paper reads like a product announcement. Mismatch increases cognitive load when clicking through.

**Why it happens:**
Single global prompt for all source types. No source-type hint (academic, newsletter, HN discussion, video).

**How to avoid:**
- Pass **`source_type`** hint in prompt (`blog|newsletter|video|discussion`).
- Lighter touch for opinion sources: **"Preserve author's stance; do not neutralize criticism or enthusiasm."**
- Don't oversell research as news; tag `tone: academic` in metadata for render styling (optional italic lead-in).

**Warning signs:**
- Every item sounds written by the same corporate comms team
- Controversial takes flattened to "some debate exists"

**Phase to address:** Pipeline

---

### Pitfall 18: Dead Links in Archive

**Category:** UX / Reading Experience  
**Severity:** medium

**What goes wrong:**
Six-month-old digest links 404, paywall, or redirect to homepage. Archive becomes a graveyard; "remind me what happened in March" fails.

**Why it happens:**
No link checking at publish or browse time. URLs were redirect-wrapped at ingestion. Paywalled content links break when free preview expires.

**How to avoid:**
- Store **Wayback Machine snapshot URL** or `archive.org` link alongside canonical URL for items at ingest time (best-effort HEAD to archive.org save).
- At render: `rel="nofollow"` external links; optional async link-check job monthly on archive (flag broken, don't delete).
- For paywalled items: summary must stand alone; link labeled **"may require subscription."**

**Warning signs:**
- Clicking archive items frequently lands on 404
- No secondary URL stored besides original

**Phase to address:** Ingestion (archive URL), Render (link presentation), Ops (optional link checker)

---

### Pitfall 19: Unwieldy Archive After 6 Months

**Category:** UX / Reading Experience  
**Severity:** medium

**What goes wrong:**
Archive page loads all weeks; navigation is a endless scroll. Finding "that edtech story from February" requires full-text hunt across huge HTML files. Site slows down.

**Why it happens:**
Archive implemented as single JSON dump or unbounded static pages. No index by month/topic. Full-text search deferred indefinitely.

**How to avoid:**
- **Paginated archive**: year → month → week hierarchy; max 20 weeks visible per index page.
- Store **per-week JSON** + lightweight **manifest index** (`archive-index.json` with week, date range, top headlines).
- Pre-render topic tags in index for skim navigation (no search engine required for v1).
- Keep each week's artifact self-contained (<500KB) for fast load.

**Warning signs:**
- Archive page > 2MB
- Browser tab hangs opening `/archive`
- No way to jump to month without scrolling

**Phase to address:** Render (primary), Ops (artifact size monitoring)

---

### Pitfall 20: Full-Text-Not-in-RSS Truncation

**Category:** Ingestion  
**Severity:** high

**What goes wrong:**
Feed gives 150-char teaser; summarizer invents the rest. Or fetcher pulls page HTML and ingests nav/footer ads as content.

**Why it happens:**
Assumption that RSS `content:encoded` is full text. Lazy HTML fetch without readability extraction. Paywall stops fetch mid-article.

**How to avoid:**
- Detect **truncation**: if `len(content) < 500` and no `content:encoded`, attempt **readability extraction** fetch (Mozilla Readability, trafilatura).
- If fetch fails or paywall detected: **snippet-only mode** with explicit flag; never full summary.
- Strip boilerplate via readability library, not raw `innerText`.

**Warning signs:**
- Summaries far longer than visible RSS snippet when source clicked
- Summaries mention site navigation ("Subscribe to our newsletter")
- High hallucination rate on specific paywalled Substacks

**Phase to address:** Ingestion (primary), Pipeline (snippet-only fallback)

---

### Pitfall 21: Rate Limiting and IP Blocks

**Category:** Ingestion  
**Severity:** high

**What goes wrong:**
Reddit API returns 429; HN Algolia throttles; full-text fetches trigger Cloudflare blocks. Pipeline aborts entirely instead of degrading gracefully.

**Why it happens:**
Burst requests from cloud IP. No per-domain rate limiter. Shared default User-Agent blocked.

**How to avoid:**
- **Per-domain rate limiter** (token bucket): e.g., 1 req/sec for fetch, 30 req/min for Reddit.
- Identify with honest **User-Agent** string including contact/project URL.
- **Exponential backoff** with jitter; max 3 retries per item.
- Continue-on-failure: rate-limited source skipped this run, not whole pipeline.

**Warning signs:**
- Failures cluster at same source type (all Reddit or all fetches)
- Works locally, fails in CI/cloud
- 429/403 in logs without retry metrics

**Phase to address:** Ingestion, Ops (retry metrics)

---

### Pitfall 22: robots.txt / TOS Overreach

**Category:** Ingestion  
**Severity:** medium

**What goes wrong:**
Aggressive full-text scraping gets IP banned or creates guilt/legal nagging for a personal tool. Reddit ToS changes break unofficial access.

**Why it happens:**
Treating "I can fetch it" as "I should fetch it." Using Reddit API beyond free tier limits without OAuth. Scraping sites that block RSS specifically to force app usage.

**How to avoid:**
- **RSS-first, fetch-second**: only fetch full text when RSS insufficient and robots.txt allows (`User-agent: *` Disallow check).
- Prefer **official APIs** (HN Firebase, Reddit OAuth) over HTML scraping.
- Respect **`Crawl-delay`** where present.
- Out of Scope items (Twitter, LinkedIn) exist partly because **no clean ToS path** — don't re-introduce via scraping backdoors.

**Warning signs:**
- HTML scraping for sites that offer full RSS
- No robots.txt check before fetch
- Using unofficial Reddit endpoints without fallback plan

**Phase to address:** Ingestion

**Out of Scope protection:** Twitter/X and LinkedIn remain out — scraping them is the primary TOS failure mode this project avoids.

---

### Pitfall 23: Free-Tier Hosting Platform Changes

**Category:** Operations  
**Severity:** high

**What goes wrong:**
Site goes dark because Vercel hobby limits changed, Render free tier sleeps or blocks SMTP/cron, GitHub Actions minutes exhausted. Personal project breaks on vendor policy, not your code.

**Why it happens:**
Architecture coupled to free-tier quirks (serverless cron, edge functions with tight limits). No uptime monitoring. Static site + pipeline not separable.

**How to avoid:**
- **Static site on durable free hosting** (GitHub Pages, Cloudflare Pages) — pipeline produces artifacts, host serves files only.
- Run pipeline on **GitHub Actions scheduled workflow** (2,000 min/mo free) or local cron with push-to-host — not on sleeping web dyno.
- Pin dependencies; monitor **host status RSS/blogs** for providers you use.
- Document **5-minute migration path** to alternate host (export env vars, change DNS/CNAME).

**Warning signs:**
- Pipeline and site on same free web service that sleeps after 15 min
- No external uptime check on published URL
- Deploy breaks after platform email about "policy update"

**Phase to address:** Ops

---

### Pitfall 24: Building BYOS Framework Before Personal v1

**Category:** Scope / Abandonment  
**Severity:** high

**What goes wrong:**
Three months in: source registry UI, plugin API, and config schema exist, but you haven't read a single satisfying weekly digest. Project becomes a framework with no consumer.

**Why it happens:**
"Future evolution hint" in PROJECT.md misread as v1 requirement. Developer comfort with abstractions over shipping. Premature generalization is fun; curating sources is tedious.

**How to avoid:**
- v1 source list = **single YAML/JSON file**, edited by hand. No UI.
- Abstraction rule: **Rule of three** — don't generalize until 3 concrete source types force the same interface.
- Definition of done = **you read digest Sunday morning for 4 consecutive weeks**, not "architecture supports N sources."
- Hard-coded is fine; **decouple** via file, not plugin system.

**Warning signs:**
- More code in `plugins/` than in `prompts/`
- Adding a source requires code change + release, but building "source admin" feels urgent
- No digest published in last 2 weeks while "refactoring ingestion"

**Phase to address:** Ingestion (config simplicity), all phases (scope discipline)

**Out of Scope protection:** Multi-user/auth explicitly deferred — the main force pushing BYOS framework too early.

---

### Pitfall 25: Dashboard Perfectionism Delays Reading Experience

**Category:** Scope / Abandonment  
**Severity:** high

**What goes wrong:**
Dark theme polish, animations, and tab transitions consume weeks. Summaries are wall-of-text in a pretty shell. Core value — **15-minute coherent narrative** — never validated.

**Why it happens:**
Visual work is satisfying and demo-able; prompt tuning is messy. Reference screenshot sets high design bar. "Looks done" triggers false completion.

**How to avoid:**
- **Content-first milestone**: ugly HTML that renders week's JSON is acceptable v0; theme comes after 2 good digests.
- Timebox design phase; use **fixed layout template** (Briefing list + 4 tabs) — no custom CMS.
- UAT question: **"Did I read this instead of opening Feedly?"** — not "does it match screenshot pixels."

**Warning signs:**
- CSS commits outnumber prompt/pipeline commits 3:1
- Digest content unchanged for weeks while UI churns
- You show friends the dashboard but don't read it yourself

**Phase to address:** Render (after Pipeline produces good JSON)

---

### Pitfall 26: Scope Creep Into Deferred Features

**Category:** Scope / Abandonment  
**Severity:** high

**What goes wrong:**
"Just one Twitter source," "quick podcast transcript for this one show," "small chat box to ask about the archive." Each adds a failure domain; v1 never ships.

**Why it happens:**
Real sources live on deferred platforms. Feature creep feels incremental. Out of Scope list erodes one exception at a time.

**How to avoid:**
- **Written gate**: new source type or feature requires updating PROJECT.md Out of Scope → Active with explicit cost/latency estimate.
- Keep a **Someday.md** backlog — capture idea, don't implement.
- When tempted by Twitter/podcasts/chat, re-read **Core Value**: coherent weekly narrative in 15 minutes.

**Warning signs:**
- Branch named `feature/twitter` or `experimental/rag-chat`
- Pipeline runtime or cost doubled for one marginal source
- Weekly digest quality unchanged but complexity up

**Phase to address:** All phases (process); resist in Ingestion/Pipeline

**Out of Scope protection:** Twitter/X, podcast transcription, Q&A chat — each maps to a specific cost/complexity trap documented above.

---

### Pitfall 27: No LLM Cost / Error Observability

**Category:** Operations  
**Severity:** high

**What goes wrong:**
You discover $47 OpenAI bill weeks later. Error rate climbed to 30% but logs weren't checked. Can't answer "which stage is expensive?"

**Why it happens:**
Observability treated as enterprise luxury. stdout logging only. Provider dashboard is the only metrics surface.

**How to avoid:**
- Emit **`pipeline_report.json`** every run: `{ tokens_in, tokens_out, cost_usd, items_by_stage, errors_by_source, duration_sec }`.
- Append to **`metrics/history.csv`** for trend charts (even a spreadsheet view helps).
- Set **weekly cost ceiling** in config; hard-stop LLM calls when exceeded.
- Dashboard or email: one-line Sunday summary — "Digest ready: 34 items, $2.14, 2 source warnings."

**Warning signs:**
- Don't know last week's LLM cost within $1
- Errors only visible by tailing ephemeral CI logs
- No structured report artifact per run

**Phase to address:** Ops (primary), Pipeline (instrument each stage)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Summarize from RSS snippet only (no full-text fetch) | Faster ingest, lower fetch risk | Thin summaries for teaser-only feeds | v1 launch; upgrade fetch for high-trust sources only |
| Single LLM model for all stages | Simpler config | Higher cost or lower roll-up quality | Never for roll-up/ranking if budget matters — tier models early |
| Exact-URL dedup only | Ships in an hour | Duplicate flood on big news weeks | Week 1 only; fuzzy dedup before second digest |
| No link archive (Wayback) | Less ingestion code | Dead archive links in 6 months | v1 if summaries are self-contained; add within 3 months |
| Static JSON archive (no search) | Zero search infra | Hard to find old stories | v1 acceptable with week/month index |
| Manual spot-check instead of automated eval | No eval harness build | Quality regressions slip through | First 4 weeks while golden set is built |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **Substack RSS** | Assuming paid Substacks expose full feed | Free: `{name}.substack.com/feed`; paid: email→RSS bridge only |
| **Kill the Newsletter / email→RSS** | Treating bridge URL as public | Bridge URL is secret; rotate if leaked; expect 15–60 min delivery delay |
| **YouTube transcripts** | Running batch fetch from cloud IP | Local/residential fetch with rate limits; metadata-only fallback |
| **Hacker News** | Using discussion URL as canonical | Unwrap `url` field; store `hn_discussion_url` separately |
| **Reddit** | Anonymous JSON endpoints without rate limits | OAuth app + token refresh; respect 60 req/min; cache post IDs |
| **LLM provider** | Using model alias (`gpt-4o`) without version pin | Pin dated model ID; log in digest metadata |
| **GitHub Actions cron** | Assuming `schedule` runs exactly on time | Can delay 15–60 min; don't depend on minute-precision; use workflow dispatch for manual rerun |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Re-summarize entire archive each week | Cost/runtime grows with archive age | Process only `published_at > last_run` items | ~10 weeks in |
| Single JSON file for all archives | Multi-MB load, slow render | Per-week files + manifest index | ~6 months (~26 weeks) |
| Embedding all items for dedup | GPU/API cost rivals summarization | Title fuzzy match first; embeddings only for ambiguous pairs | >100 items/week |
| Full transcript to LLM | 20K+ tokens per video | Truncate + summarize in two passes | Any long podcast/video channel |
| Synchronous fetch of 40 sources | Pipeline timeout on slow source | Parallel fetch with per-source timeout (30s) | First flaky network week |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| LLM API key in static site bundle | Key scraped from public JS; surprise bill | Pipeline-only secrets; static output has zero keys |
| Newsletter bridge URL in git | Attacker subscribes junk to your digest email | Env var or gitignored secrets file |
| Public repo with `sources.yaml` containing private feeds | Leaks what you read / paid subscriptions | Separate private config repo or gitignored overlay |
| Verbose error pages in production | Stack traces expose paths, env hints | Generic error surface on site; details in private logs only |
| Unauthenticated manual trigger endpoint | Anyone runs your $$$ pipeline | Protect rerun endpoint with secret header or local-only |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Wall of identical-length summaries | Scan fatigue; skip digest | Vary display: Top-N expanded, rest collapsed one-liners |
| No "why ranked here" | Briefing feels arbitrary | One-line rank reason from LLM ("3 sources, regulatory impact") |
| Missing source name on card | Can't trust attribution | Always show source favicon/name + date |
| Weekly roll-up above fold only | Topic readers miss narrative | Briefing tab leads with roll-up; topic tabs link back |
| Updated timestamp without week range | Confusion on which week is live | Prominent "Week of MMM D – MMM D" header per PROJECT.md |

---

## "Looks Done But Isn't" Checklist

- [ ] **Ingestion:** All 15–40 sources have `last_success_at` within 7 days — verify health report
- [ ] **Ingestion:** HN/Reddit items link to original article, not discussion page only
- [ ] **Pipeline:** Dedup runs *before* LLM — verify token count drops on duplicate-heavy week
- [ ] **Pipeline:** `prompt_version` + `model_id` stored in digest JSON
- [ ] **Pipeline:** Weekly roll-up covers items from Mon–Sun, not just weekend
- [ ] **Render:** Archive index paginates by month — verify load time < 2s at week 26
- [ ] **Ops:** Heartbeat fired on last successful run — verify external monitor green
- [ ] **Ops:** `pipeline_report.json` exists with cost within budget cap
- [ ] **Ops:** Static site contains no env secrets — run grep for `sk-`, `API_KEY`

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Runaway LLM costs | LOW | Enable hard cap; re-run from deduped checkpoint with cheaper model |
| Hallucinated summaries | MEDIUM | Re-run affected items snippet-only mode; add confidence flags retroactively |
| Silent cron failure | LOW | Manual workflow dispatch; fix heartbeat; backfill missing week from checkpoints |
| Mid-run crash | LOW | Resume from last stage artifact; idempotent item keys prevent re-billing |
| RSS source death | LOW | Update URL in config; optional manual browser find feed |
| YouTube transcript block | MEDIUM | Switch fetch to local IP; metadata-only until unblocked |
| Near-duplicate flood | MEDIUM | Lower similarity threshold; re-run dedup + ranking only |
| Over-dedup | MEDIUM | Raise threshold; allow 2 per cluster across categories; re-render |
| Bad week ranking | LOW | Re-run ranking stage with adjusted prompt (version bump) |
| Dead archive links | HIGH | Batch archive.org snapshot backfill; label broken links |
| Free tier breakage | MEDIUM | Migrate static to Cloudflare Pages; pipeline to GitHub Actions |
| Scope creep | HIGH | Revert to last good digest; move features to Someday.md |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Runaway LLM costs | Pipeline, Ops | `pipeline_report.json` cost < weekly cap for 4 weeks |
| Hallucinated summaries | Pipeline | 3-item/week spot-check passes; low-confidence flags on thin sources |
| Silent cron failure | Ops | Heartbeat monitor green; missing week triggers alert |
| Mid-run crash loses work | Pipeline | Kill -9 mid-run; resume completes without duplicate LLM calls |
| Secret leakage | Ops, Render | Secret scan CI clean; view-source shows no keys |
| RSS feed rot | Ingestion, Ops | Stale-source report; 0 sources silent >21 days |
| YouTube transcript gaps | Ingestion | ≥80% of videos have transcript or explicit fallback |
| Near-duplicate flood | Pipeline | Max 1 canonical per cluster in Briefing |
| Over-dedup | Pipeline | Distinct angles preserved in different topic tabs |
| Recency bias | Pipeline | Top-N includes item from Mon–Wed in heavy news week (test fixture) |
| Hype over importance | Pipeline | Tier-1 source appears in Top-N at least 1× per month |
| Inconsistent categorization | Pipeline | Same golden items categorize identically across 3 runs |
| Prompt drift | Pipeline, Ops | `prompt_version` in digest; golden-set diff on change |
| Lost-in-the-middle roll-up | Pipeline | Roll-up mentions ≥80% of Top-N items |
| Attribution mismatch | Ingestion, Pipeline | 100% click-through lands on matching domain |
| Slop summaries | Pipeline | Ban-list scan; human reads full digest without fatigue |
| Tone mismatch | Pipeline | Opinion sources retain stance in spot-check |
| Dead links | Ingestion, Render | Optional monthly link check <20% broken |
| Unwieldy archive | Render | Week-26 archive index loads <2s |
| RSS truncation | Ingestion | Paywalled items flagged; no inventing beyond snippet |
| Rate limiting | Ingestion | Pipeline completes with 1 source in 429 backoff |
| robots.txt / TOS | Ingestion | Fetch obeys Disallow; official APIs preferred |
| Free-tier hosting break | Ops | Static site on Pages; pipeline on Actions — survives dyno sleep |
| BYOS too early | Ingestion | Single config file; no plugin UI |
| Dashboard perfectionism | Render | 2 quality digests before theme polish |
| Scope creep | All | No Out-of-Scope features in git main |
| No observability | Ops | Know last run cost within $0.50 without opening provider dashboard |

---

## Sources

- PROJECT.md — Out of Scope reasoning, cost/cadence constraints, core value definition
- Liu et al., "Lost in the Middle: How Language Models Use Long Contexts" (TACL 2024) — U-shaped attention in long-context roll-ups
- Multi-document summarization hallucination research (arXiv 2410.13961) — cross-item contamination and unfaithful summaries
- Feedly Engineering — near-duplicate detection at scale (LSH, clustering vs dedup)
- MITRE / standard shingling literature — near-duplicate news detection
- youtube-transcript-api GitHub issues — cloud IP blocking, rate limits, undocumented endpoints
- Cron monitoring guides (Cronping, Watchflow, AgentMinds VPS patterns) — silent failure modes
- Render/Vercel/Heroku free-tier change post-mortems (2022–2025) — platform policy breakage
- vLLM batch inconsistency issue #5898 — categorization non-determinism at batch size > 1
- LLM batch prompting cost reduction (Coleman; HN LLM spend threads) — tiered/batch strategies

---
*Pitfalls research for: Personal weekly AI news digest (AIDigest)*
*Researched: 2026-05-21*
