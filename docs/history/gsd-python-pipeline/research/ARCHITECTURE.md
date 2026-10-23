# Architecture Research

**Domain:** Personal weekly AI news digest — ingestion, LLM summarization, static dashboard
**Researched:** 2026-05-21
**Confidence:** HIGH (patterns validated across multiple production/open-source reference systems; stack-specific choices remain MEDIUM until stack research completes)

## Standard Architecture

### System Overview

Personal digest systems at this scale (1 user, 15–40 sources, weekly cadence) converge on a **batch pipeline + durable store + static publish** pattern. Real references: [feed-summarizer](https://github.com/rcarmo/feed-summarizer) (SQLite → LLM → static HTML/RSS), [feedmeup](https://github.com/paddedzero/feedmeup) (GitHub Actions → Python → Astro content collection), [accio-ai](https://github.com/krxthx/accio-ai) (LangGraph DAG → Jinja2/JSON), [CondenseIt](https://github.com/wildlifechorus/condenseit) (SQLite + adapter-per-source + web UI). None of these need real-time serving or multi-tenant auth for v1.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATION (weekly trigger)                        │
│                    cron / GitHub Actions / local CLI `run`                    │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                    │ invokes
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              PIPELINE RUNNER                                  │
│  ingest → normalize → persist → dedup/cluster → LLM enrich → build digest    │
│                              → render static assets                           │
└───┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬───────────┘
    │         │         │         │         │         │         │
    ▼         ▼         ▼         ▼         ▼         ▼         ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
│ Source │ │Ingest  │ │ Store  │ │ Dedup  │ │  LLM   │ │ Digest │ │ Publisher│
│ Config │ │Adapters│ │SQLite/ │ │Engine  │ │Pipeline│ │Builder │ │ (SSG)    │
│ YAML   │ │        │ │ JSON   │ │        │ │        │ │        │ │          │
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────┬─────┘
                                                                          │
                                                                          ▼
                                                              ┌───────────────────┐
                                                              │ Static site host  │
                                                              │ (Pages / Blob /   │
                                                              │  nginx + dist/)   │
                                                              └───────────────────┘
```

**Read path (Sunday morning):** Browser → CDN/static host → pre-built HTML/JSON. No database at request time.

### Component Responsibilities

| Component | Responsibility | Owns | Talks to | Typical implementation |
|-----------|----------------|------|----------|------------------------|
| **Source Config** | Declarative list of feeds/channels; adapter type, URLs, priority, enabled flag | `sources.yaml` schema | Ingest adapters (read-only) | YAML/JSON in repo; validated at startup |
| **Ingest Adapters** | Fetch raw items per source type; map to common shape; per-source error isolation | Network I/O, retries, rate limits | Source Config (in), Normalizer (out) | One class/module per type: `rss`, `youtube`, `reddit`, `hn`, `email_rss` |
| **Normalizer** | Canonical fields: title, url, published_at, body_text, author, media, source_ref | Field mapping rules | Adapters (in), Store (out) | Pure functions; URL canonicalization |
| **Store** | Durable items, summaries, digests, run logs; idempotency keys | SQLite (or JSON files for ultra-minimal v0) | All pipeline stages | SQLite + WAL; Drizzle/Prisma/raw SQL |
| **Dedup Engine** | Collapse same-story coverage; produce StoryCluster | Cluster membership, canonical item | Store (read/write) | URL match → title fuzzy → optional SimHash |
| **LLM Pipeline** | Per-item TL;DR, category, ranking signals; weekly narrative | Prompts, token budgets, model calls | Store (read/write) | Batched calls; structured JSON output |
| **Digest Builder** | Select Top N, assemble week snapshot, assign tabs | `WeeklyDigest` record + item ordering | Store, Dedup, LLM | Deterministic + one rollup LLM call |
| **Publisher / Renderer** | Write digest pages + archive index; optional JSON API for frontend | `dist/` or `content/digests/` | Digest Builder (in), static host (out) | Astro/Next SSG reading JSON/MD |
| **Orchestrator** | Schedule, run phases in order, emit metrics/cost | Run state, failure aggregation | All of the above | Single CLI entrypoint or GH Action workflow |

### Component Boundaries (what talks to what)

```
sources.yaml ──read──▶ Orchestrator
                          │
                          ├──▶ Ingest Adapters ──▶ Normalizer ──▶ Store (items)
                          │                                      │
                          ├──▶ Dedup Engine ◀──read── Store       │
                          │         │                            │
                          │         └──write──▶ Store (clusters) │
                          │                                      │
                          ├──▶ LLM Pipeline ◀──read── Store       │
                          │         └──write──▶ Store (summaries)│
                          │                                      │
                          ├──▶ Digest Builder ◀──read── Store     │
                          │         └──write──▶ Store (digests)  │
                          │                                      │
                          └──▶ Publisher ◀──read── Store/digest  │
                                    └──write──▶ dist/ + git commit (optional)
```

**Rules that keep boundaries clean:**
- Adapters never call the LLM.
- Renderer never fetches RSS or calls the LLM.
- Store is the only cross-run memory; pipeline stages are stateless aside from run logs.
- Dedup runs **before** per-item LLM summarization on new items (or merges summaries post-hoc if reprocessing — pick one; pre-LLM is cheaper).

## Recommended Project Structure

```
aidigest/
├── config/
│   ├── sources.yaml              # v1 hard-coded source list (human-edited)
│   └── sources.schema.json       # JSON Schema validation
├── pipeline/
│   ├── orchestrator.py           # or run.ts — single entry: ingest → publish
│   ├── adapters/
│   │   ├── base.py               # IngestAdapter protocol
│   │   ├── rss.py
│   │   ├── youtube.py
│   │   ├── reddit.py
│   │   ├── hackernews.py
│   │   └── email_rss.py          # Kill the Newsletter / similar feed URLs
│   ├── normalize.py
│   ├── dedup/
│   │   ├── url.py                # canonical URL grouping
│   │   └── title_fuzzy.py        # RapidFuzz-style clustering
│   ├── llm/
│   │   ├── summarize.py
│   │   ├── categorize.py
│   │   ├── rank.py
│   │   └── weekly_rollup.py
│   ├── digest_builder.py
│   └── publisher/
│       └── export_digest.py      # writes JSON consumed by site build
├── store/
│   ├── schema.sql
│   ├── migrations/
│   └── db.py
├── web/                          # Astro or Next static app
│   ├── src/pages/
│   │   ├── index.astro           # latest Briefing redirect or render
│   │   ├── digest/[weekId].astro # archive pages
│   │   └── archive.astro         # date picker / list
│   ├── src/components/
│   └── content/digests/          # generated JSON or MD (git-tracked archive)
├── data/
│   └── aidigest.db               # local SQLite (gitignored; backed up separately)
└── .github/workflows/
    └── weekly-digest.yml         # optional: cron + deploy
```

### Structure Rationale

- **`config/` vs `pipeline/adapters/`:** Config declares *what*; adapters declare *how*. v2 multi-user adds `user_id` to config rows without renaming adapters.
- **`store/` separate from `pipeline/`:** Enables re-running LLM or render without re-fetching feeds.
- **`web/content/digests/`:** Git-tracked digest snapshots give a free, durable archive and match feedmeup's content-collection pattern.
- **Single orchestrator:** Avoids microservices overhead at personal scale; matches feed-summarizer and accio-ai.

## Data Model

### Entity Relationship Sketch

```
Source (1) ──< Item (many)
                  │
                  ├── optional ──▶ StoryCluster (many items → 1 cluster)
                  │
                  └── 1:1 ──▶ ItemSummary (LLM output per item/cluster)
                  
WeeklyDigest (1) ──< DigestEntry (many) ──▶ Item or StoryCluster
       │
       └── 1:1 ──▶ WeeklyRollup (narrative text)
```

### Core Entities

| Entity | Purpose | Key fields |
|--------|---------|------------|
| **Source** | Configured origin | `id` (slug), `type`, `url`, `display_name`, `default_weight`, `enabled`, `tags[]` |
| **Item** | One ingested artifact | See PK strategy below |
| **StoryCluster** | Dedup group for same story | `cluster_id`, `canonical_item_id`, `member_item_ids[]`, `canonical_url` |
| **ItemSummary** | LLM per-item output | `item_id` or `cluster_id`, `tldr`, `category`, `rank_score`, `model`, `content_hash`, `processed_at` |
| **WeeklyDigest** | Immutable week snapshot | `week_id`, `week_start`, `week_end`, `status`, `published_at`, `updated_at` |
| **DigestEntry** | Item placement in a digest | `digest_id`, `cluster_id`, `tab`, `rank`, `is_top_n` |
| **WeeklyRollup** | Editor's note | `digest_id`, `narrative_md`, `model`, `token_count` |
| **PipelineRun** | Observability + idempotency | `run_id`, `started_at`, `phase`, `status`, `errors_json`, `cost_usd` |

### Primary Key Strategy for Items

Sources use incompatible native IDs. Use a **two-level key**:

1. **Stable internal PK:** `item_id` = UUID or `hash(source_id + external_id)` where `external_id` is type-specific:
   | Source type | `external_id` derivation |
   |-------------|--------------------------|
   | RSS/Atom/email-RSS | `guid` if present and stable; else `sha256(canonical_url + published_date_day)` |
   | YouTube | `video_id` from URL or feed |
   | Reddit | `{subreddit}/{post_id}` |
   | Hacker News | `{hn_id}` (integer story id) |

2. **Unique constraint:** `UNIQUE(source_id, external_id)` — prevents re-ingest duplicates.

3. **Secondary indexes for dedup:**
   - `canonical_url` — normalized (strip UTM, lowercase host, resolve redirects once at ingest)
   - `url_hash` = `sha256(canonical_url)`
   - `published_at`, `title_normalized`

4. **StoryCluster PK:** `cluster_id` = UUID; assigned during dedup pass. Digest references **clusters**, not raw items, so three RSS entries about the same launch become one card with "also covered by …" links.

**Why not URL-only as PK?** Reddit/HN often link to the same article with different discussion URLs; syndicated posts differ in tracking params; YouTube has no shared URL with blog coverage. URL is a strong *dedup signal*, not a universal PK.

### WeeklyDigest Idempotency Keys

- **`week_id`:** ISO week or explicit range slug, e.g. `2026-W20` or `2026-05-12_2026-05-18` (matches UI "Week of MMM D – MMM D").
- **`UNIQUE(week_id)`** on `weekly_digests` — second run in the same week **updates** the draft row or no-ops based on `status`:
  - `draft` → replace contents
  - `published` → require `--force` flag to rebuild (accidental double-Sunday protection)
- **Item processing idempotency:** `ItemSummary.content_hash` = hash of normalized body; skip LLM if hash unchanged and `processing_version` matches.
- **Digest item selection:** store `digest_id + cluster_id` unique; rebuild replaces entries in a transaction.

## Pipeline Orchestration

### Recommended: Continuous-ish Ingest + Weekly Aggregation

| Phase | Cadence | Rationale |
|-------|---------|-----------|
| **Ingest + normalize + persist** | Daily (or 2–3×/week) OR at start of weekly job | Spreads fetch failures; avoids Sunday 40-feed thundering herd; matches feed-summarizer's continuous fetch + periodic publish |
| **Dedup on new items** | After each ingest | Keeps store clean before LLM spend |
| **LLM summarize/categorize** | Weekly (only `items WHERE NOT summarized`) | Cost bounded to new content |
| **Rank + rollup + publish** | Weekly | Narrative needs full week context |

**Alternative (simpler v0):** Single weekly cron does ingest → everything. Acceptable for 15 sources; gets painful at 40+ (feedmeup runs full fetch weekly but logs per-feed errors).

### Weekly Cycle (step-by-step data flow)

```
1. START RUN (week_id = current ISO week, timezone = user-local)
2. INGEST: for each enabled Source → Adapter.fetch() → Normalizer → UPSERT items
   - On source failure: log to pipeline_runs.errors, continue
3. DEDUP: new/changed items since last dedup → assign/update StoryClusters
4. LLM (items): for each cluster without summary (or stale content_hash):
   - batch summarize + categorize → UPSERT item_summaries
5. DIGEST BUILD:
   - window = [week_start, week_end)
   - candidates = clusters with published_at in window
   - rank → pick Top N per Briefing + per tab
   - one LLM call for weekly narrative rollup
   - UPSERT weekly_digest + digest_entries (transaction)
6. PUBLISH:
   - export digest JSON/MD to web/content/digests/{week_id}.json
   - run site SSG (astro build / next export)
   - deploy static assets
7. MARK published_at, write cost/token totals
```

### Idempotency Placement

| Layer | Mechanism |
|-------|-----------|
| Item ingest | `UNIQUE(source_id, external_id)` upsert |
| LLM | `content_hash` + `processing_version` gate |
| Weekly digest | `UNIQUE(week_id)`; transactional replace of `digest_entries` |
| Static publish | Content-addressed filenames; rebuild overwrites same paths |
| Git commit (if used) | Check diff before commit; same week_id file → idempotent content |

Re-running the job twice in one week should produce **one** digest page with the latest data, not duplicate archive entries.

## Dedup Strategy

### What Similar Products Do

| Project | Approach | Notes |
|---------|----------|-------|
| **feedmeup** | RapidFuzz title similarity (0.8 threshold) + max 2 per domain | Cheap; good for 40 feeds |
| **feed-summarizer** | SimHash on summary text; optional BM25/FTS5 fallback | Merges near-duplicates; surfaces all source links |
| **accio-ai** | LLM batch dedup after enhance/validate | Higher quality, higher cost |
| **CondenseIt** | Optional embedding similarity for ranking (not hard dedup) | Overkill for v1 |
| **Feedly engineering** | LSH + clustering at scale | Enterprise pattern; not needed here |

### Recommended Tiered Strategy for AI Digest v1

```
Tier 0 (free): Exact URL match after canonicalization
    → same canonical_url → same cluster

Tier 1 (cheap): Cross-source title fuzzy match (RapidFuzz ratio ≥ 0.85)
    → feedmeup pattern; merge if same story within 7-day window

Tier 2 (optional v1.5): SimHash on title + first 500 chars of body
    → feed-summarizer pattern; catches reworded headlines

Tier 3 (defer v2): Embedding cosine clustering
    → accio-ai / Feedly territory; use if Tier 0–1 leave obvious dupes
```

**Presentation rule:** One card per cluster; show primary source + "Also: Source B, HN discussion" links. Summarize **once per cluster** (canonical item = longest body or highest-priority source).

**When to skip dedup:** Never skip entirely — without it, Briefing Top N fills with "GPT-5 rumor" × 5. But don't block shipping on SimHash; URL + fuzzy title is enough for v1.

## Render Strategy

### Recommendation: Pipeline-Exported JSON + Static Site Generation

| Option | Fit for this project | Archive | Cost |
|--------|---------------------|---------|------|
| **SSG at pipeline end (recommended)** | Excellent | Each week → JSON/MD in repo or blob; site rebuild indexes all | Hosting ~free (GitHub Pages, Cloudflare Pages) |
| **Dynamic SSR + DB** | Poor fit | Easy query-by-date, but needs always-on server + DB for 1 user | Violates low-ops constraint |
| **ISR / on-demand revalidation** | Overkill | Useful for multi-tenant SaaS, not single-user weekly | Adds platform coupling |

**Pattern (feedmeup + accio-ai):** Pipeline writes structured digest files → frontend build reads all weeks → generates `/digest/2026-W20`, `/archive`, tab routes.

**Archive requirement:** Git-tracked `content/digests/*.json` is the archive of record. The site is a **view** over that corpus. Rebuild from scratch anytime. Optional: export static HTML per week for offline reading (accio-ai HTML output).

**"Updated" timestamp:** Set in digest JSON at publish time; renderer displays it on Briefing header.

**No runtime LLM, no runtime RSS** on the public site — security and cost win.

## Source Config Evolution (v1 → v2)

### v1: YAML in Repo

```yaml
# config/sources.yaml
version: 1
defaults:
  enabled: true
  fetch_interval_hours: 24
sources:
  - id: simon-willison
    type: rss
    url: https://simonwillison.net/atom/everything/
    display_name: Simon Willison
    weight: 1.2
    tags: [technical]

  - id: ai-channel
    type: youtube
    channel_id: UC...
    display_name: "Some AI Channel"
    tags: [technical, design]

  - id: localllama
    type: reddit
    subreddit: LocalLLaMA
    sort: hot
    min_score: 50
    tags: [technical]

  - id: hn-ai
    type: hackernews
    query: AI OR LLM
    tags: [technical, business]

  - id: ben-newsletter
    type: email_rss
    url: https://kill-the-newsletter.com/feeds/xxxx
    tags: [business]
```

**Validation:** JSON Schema at startup; fail fast on unknown `type`.

**Adapter registry:**

```python
ADAPTERS = {
  "rss": RssAdapter,
  "youtube": YouTubeAdapter,
  "reddit": RedditAdapter,
  "hackernews": HackerNewsAdapter,
  "email_rss": RssAdapter,  # same parser, different config label
}

def get_adapter(source: SourceConfig) -> IngestAdapter:
    return ADAPTERS[source.type](source)
```

### v2: Bring Your Own Sources (no rewrite)

| v1 | v2 change |
|----|-----------|
| YAML file | `sources` DB table with same columns + `user_id` |
| Single `config/sources.yaml` | Admin UI or API writes rows |
| Hard-coded `defaults` | Per-user defaults row |
| Adapter registry | **Unchanged** — still keyed by `type` |
| Validation schema | **Unchanged** — validate DB rows same as YAML |

**Do not** embed fetch logic in YAML beyond declarative params. **Do not** hard-code source lists in Python. The orchestrator loads `List[SourceConfig]` from a `SourceRepository` interface with two impls: `YamlSourceRepository` (v1), `DbSourceRepository` (v2).

OPML import (CondenseIt pattern) becomes a converter → `SourceConfig` rows.

## Architectural Patterns

### Pattern 1: Adapter + Normalized Item (Hexagonal Ingest)

**What:** Each source type implements `fetch(since) → RawItem[]`; normalizer maps to `NormalizedItem`.

**When to use:** Always — required for RSS + YouTube + Reddit + HN coexistence.

**Trade-offs:** +20% upfront code; saves rewrite when adding podcasts in v2.

### Pattern 2: Store-and-Forward Pipeline

**What:** Persist raw items immediately; LLM and digest stages read from DB.

**When to use:** Weekly LLM budget control, re-run digest without re-fetch, debugging.

**Trade-offs:** SQLite file to backup; trivial at personal scale.

**Reference:** feed-summarizer `fetcher → SQLite → summarizer → publisher`.

### Pattern 3: Content-as-Data Static Publish

**What:** Digest is a JSON document; site build is pure function of all digest files.

**When to use:** Full archive, cheap hosting, no auth.

**Trade-offs:** Rebuild time grows linearly with weeks (~52 files/year is negligible).

### Pattern 4: Tiered Dedup Before LLM

**What:** Deterministic dedup first; LLM only on cluster representatives.

**When to use:** Cost-conscious weekly batch (this project).

**Trade-offs:** May miss subtle "same event, different angle" merges until Tier 2 SimHash added.

## Data Flow

### Weekly Pipeline Flow

```
[Cron/Manual Trigger]
        ↓
[Orchestrator] ──reads──▶ sources.yaml
        ↓
[For each Source] ──▶ [Adapter] ──▶ [Normalizer] ──▶ UPSERT items
        ↓ (failures → run log, continue)
[Dedup Engine] ──▶ UPSERT story_clusters
        ↓
[LLM: summarize/categorize] ──▶ UPSERT item_summaries  (skip if content_hash match)
        ↓
[Digest Builder: rank + select Top N]
        ↓
[LLM: weekly rollup narrative]
        ↓
[UPSERT weekly_digest + entries]  (transaction, week_id unique)
        ↓
[Export JSON] ──▶ web/content/digests/{week_id}.json
        ↓
[SSG build] ──▶ dist/
        ↓
[Deploy static host]
```

### Read Path (User Sunday Morning)

```
Browser GET /
    ↓
Static host serves pre-built HTML
    ↓
Briefing page loads digest JSON (embedded at build or fetched as static asset)
    ↓
Tab click → client route or separate static pages per tab (all pre-rendered)
    ↓
Archive → /archive lists week_id slugs from build-time glob of content/digests/
```

## Suggested Build Order

| Order | Component | Depends on | Rationale |
|-------|-----------|------------|-----------|
| 1 | Source config schema + YAML loader | — | Everything reads source list; establishes adapter contract |
| 2 | Normalized item model + SQLite schema | 1 | Stable contract for all adapters |
| 3 | RSS/email-RSS adapter + ingest CLI | 1, 2 | Covers majority of 15–40 sources; proves store upsert |
| 4 | Dedup Tier 0–1 (URL + title) | 3 | Before LLM to avoid paying for duplicates |
| 5 | LLM summarize + categorize | 3, 4 | Core value; can test on RSS-only data |
| 6 | Weekly digest builder + rollup | 5 | Produces structured JSON matching UI needs |
| 7 | Static site shell (dark theme, tabs) with mock JSON | — | Can parallel after step 2 schema known; wire real data at 6 |
| 8 | Publisher export + archive routes | 6, 7 | Full archive browseable |
| 9 | YouTube adapter | 2 | Transcript edge cases isolated |
| 10 | Reddit + HN adapters | 2 | API/rate-limit complexity last among ingest |
| 11 | Orchestrator + scheduler + observability | all | GitHub Action or cron wrapping existing CLI |
| 12 | Failure UX (error log page, partial digest badges) | 11 | Polish once happy path works |

**Critical path:** config → store → RSS ingest → dedup → LLM → digest JSON → render.

**Parallelizable:** Frontend mock (7) while pipeline (3–6) matures.

## Failure Modes & Degradation

| Failure | Detection | Degradation behavior |
|---------|-----------|---------------------|
| **RSS feed down / 404** | HTTP error per adapter | Skip source; log `source_id`, status, timestamp to `pipeline_runs.errors` and optional `content/errors/` page; digest proceeds |
| **Malformed RSS** | Parse exception | Same as above; never abort whole run (feedmeup pattern) |
| **YouTube transcript missing** | Empty transcript API | Fallback: summarize from title + description; if still empty, skip item |
| **Reddit/HN rate limit** | 429 | Exponential backoff; reduce `limit` param; if still failing, skip source this run |
| **LLM rate limit** | 429 from provider | Backoff + smaller batches; feed-summarizer uses bisection on batch size |
| **LLM content filter / refusal** | Provider error | Skip item; log; do not retry infinitely |
| **LLM budget exceeded** | Token/cost counter pre-check | Stop after current batch; publish **partial digest** with banner "N items pending summarization" |
| **Dedup false positive** | Manual review | v1: tune fuzzy threshold; v2: split cluster in config override |
| **Digest build crash mid-transaction** | DB rollback | `weekly_digest.status = draft`; no publish until complete |
| **SSG build failure** | CI exit code | Keep previous deployed static site live; alert via Action notification |
| **Single category empty** | Zero items in tab | Show empty state for tab; Briefing still publishes from other tabs |

**Principle (from PROJECT.md):** One flaky source must not break the entire digest. **Partial success > no digest.**

**Observability minimum:** Per-run log with items fetched / summarized / skipped / cost USD; matches accio-ai `FETCHED/KEPT/REJECTED` trace and CondenseIt Admin → Logs.

## Scaling Considerations

| Scale | Architecture adjustments |
|-------|-------------------------|
| **v1 (1 user, 40 sources, 52 digests/year)** | Monolith CLI + SQLite + SSG; no changes needed |
| **v2 (100 sources, preference learning)** | Add embedding cache table; optional CondenseIt-style ranking weights |
| **v2 (multi-user SaaS)** | `user_id` on sources/digests; Postgres; SSR or ISR for per-user routes; auth layer — **explicitly out of v1** |

### Scaling Priorities (if scope grows)

1. **First bottleneck:** LLM cost/time → batching, dedup-before-LLM, skip unchanged `content_hash`.
2. **Second bottleneck:** Ingest wall-clock → parallel adapter fetch with per-domain rate limits.

## Anti-Patterns

### Anti-Pattern 1: LLM-First Ingest

**What people do:** Send every RSS entry directly to GPT without storage or dedup.

**Why it's wrong:** Runaway cost; no archive reproducibility; can't re-render UI without re-spending.

**Do this instead:** Store-and-forward; dedup; summarize once per cluster.

### Anti-Pattern 2: URL as Sole Primary Key

**What people do:** `PRIMARY KEY (url)`.

**Why it's wrong:** HN/Reddit discussion URLs ≠ article URLs; syndication creates multiple URLs for one story.

**Do this instead:** `(source_id, external_id)` PK + `canonical_url` for dedup.

### Anti-Pattern 3: Dynamic Site for a Weekly Personal Digest

**What people do:** Next.js SSR + Postgres on a VPS "for flexibility."

**Why it's wrong:** Always-on cost; complexity unrelated to weekly read pattern.

**Do this instead:** Static publish; DB exists only for pipeline, not readers.

### Anti-Pattern 4: Hard-Coded Sources in Adapter Code

**What people do:** `RSS_URLS = [...]` inside `rss.py`.

**Why it's wrong:** Blocks v2 multi-user; mixes config with logic.

**Do this instead:** YAML + `SourceRepository` abstraction + adapter registry.

### Anti-Pattern 5: All-or-Nothing Pipeline

**What people do:** Fail entire run if one feed errors.

**Why it's wrong:** Violates core reliability requirement.

**Do this instead:** Per-source try/except; aggregate errors; publish partial digest.

## Integration Points

### External Services

| Service | Integration pattern | Notes |
|---------|---------------------|-------|
| RSS/Atom feeds | HTTP conditional GET (ETag/Last-Modified) | feed-summarizer pattern reduces bandwidth |
| YouTube | Channel RSS + transcript API/library | Transcript gaps common; fallback required |
| Reddit | OAuth API or `.json` endpoints | Rate limits; respect ToS |
| Hacker News | Firebase API / Algolia | Public, generous limits |
| Email newsletters | Kill the Newsletter → RSS URL | Treat as `email_rss` type |
| LLM provider | Batched chat completions, JSON mode | Track tokens per run; cap max items |
| Static host | GitHub Actions → Pages, or rclone to blob | feed-summarizer Azure Blob pattern |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Adapters ↔ Store | NormalizedItem DTO | Adapters unaware of SQL |
| LLM ↔ Store | Item/cluster IDs + text fields | Prompts live in `pipeline/llm/prompts/` |
| Pipeline ↔ Web | JSON files in `content/digests/` | Schema version field for forward compatibility |
| Orchestrator ↔ CI | CLI exit codes + artifact upload | `0` = publish; `1` = hard fail; `2` = partial success |

## Sources

- [feed-summarizer](https://github.com/rcarmo/feed-summarizer) — SQLite pipeline, SimHash dedup, static HTML/RSS publish, conditional fetch ([ARCHITECTURE.md](https://github.com/rcarmo/feed-summarizer/blob/main/docs/ARCHITECTURE.md), [MERGE_TUNING.md](https://github.com/rcarmo/feed-summarizer/blob/main/docs/MERGE_TUNING.md))
- [feedmeup](https://github.com/paddedzero/feedmeup) — GitHub Actions weekly cron, RapidFuzz dedup, Gemini summarization, Astro content collection
- [accio-ai](https://github.com/krxthx/accio-ai) — LangGraph DAG pipeline, config/sources.py separation, HTML+JSON render
- [CondenseIt](https://github.com/wildlifechorus/condenseit) — Multi-adapter ingest, YAML→SQLite source evolution, budget tracking
- [Feedly engineering — clustering & dedup](https://feedly.com/engineering/posts/reducing-clustering-latency) — LSH/dedup-before-cluster at scale (conceptual reference)
- [OpenClaw tech news digest guide](https://openclawconsult.com/lab/openclaw-tech-news-digest) — Two-tier deterministic-then-LLM pipeline pattern
- `.planning/PROJECT.md` — AI Digest requirements, constraints, v1/v2 source config decision

---
*Architecture research for: AI Digest — personal weekly AI news dashboard*
*Researched: 2026-05-21*
