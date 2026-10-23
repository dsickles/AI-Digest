# Stack Research

**Domain:** Personal weekly AI news digest — static dashboard + weekly batch ingestion/LLM pipeline  
**Researched:** 2026-05-21  
**Confidence:** HIGH (framework/hosting/ingestion), MEDIUM (YouTube unofficial APIs, Reddit RSS reliability)

## Executive Recommendation

Use a **split monorepo**: Python batch pipeline + Astro static site, orchestrated by **GitHub Actions** on a weekly cron, with digest artifacts **committed to git** and deployed to **Cloudflare Pages**. This matches the product shape (read-only archive, weekly cadence, one user, cost-conscious) better than a full-stack Next.js app with runtime DB.

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub Actions (cron: Sun 08:00 UTC)                       │
│  ┌──────────────┐   ┌─────────────┐   ┌──────────────────┐  │
│  │ Python       │ → │ SQLite      │ → │ digest JSON/MD   │  │
│  │ ingest+LLM   │   │ (ephemeral) │   │ → web/content/   │  │
│  └──────────────┘   └─────────────┘   └────────┬─────────┘  │
│                                                   │ git push  │
│  ┌────────────────────────────────────────────────▼────────┐  │
│  │ Astro build → Cloudflare Pages (static, $0)             │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| **Astro** | 6.3.7 | Static dashboard + archive | Content Collections are a natural fit for weekly digest artifacts; zero JS by default; fast builds; low ops. No server/runtime needed for v1 (no auth). | HIGH |
| **Python** | 3.12+ | Ingestion + LLM pipeline | Best ecosystem for RSS (`feedparser`), YouTube (`yt-dlp`, `youtube-transcript-api`), and LLM SDKs. Single language for all batch work. | HIGH |
| **GitHub Actions** | — | Weekly cron + deploy | Free for public repos; 2,000 min/mo on private Free tier. Handles 15–40 min weekly runs easily. No paid cron tier needed. | HIGH |
| **SQLite** | 3.x (stdlib) | Pipeline state + dedup | Ephemeral working DB during pipeline run: ingested-item hashes, run logs, raw text cache. Not the archive source of truth. | HIGH |
| **Git-committed JSON** | — | Published digest archive | Pipeline writes typed digest files to `web/src/content/digests/`. Git history = full archive. Astro validates via Zod at build. $0 storage. | HIGH |
| **Cloudflare Pages** | — | Static hosting | Free tier, unlimited bandwidth, auto-deploy on push. No cold starts, no server bill. | HIGH |
| **Gemini 2.5 Flash-Lite** | `gemini-2.5-flash-lite` | Per-item summarize/categorize/rank | Cheapest capable model for structured batch work. Batch API: $0.05/M in, $0.20/M out. | HIGH |
| **Gemini 2.5 Flash** | `gemini-2.5-flash` | Weekly narrative roll-up | Better prose quality for the editor's note; still cheap in batch ($0.15/$1.25 per M). One call/week. | HIGH |
| **google-genai** | 2.5.0 | LLM SDK (Python) | Official Google SDK; supports Batch API, structured JSON output. Simpler than LangChain for a linear pipeline. | HIGH |
| **feedparser** | 6.0.12 | RSS/Atom parsing | De-facto standard for heterogeneous/malformed feeds. 15M+ downloads/mo; handles RSS 0.9x–2.0, Atom, CDF. | HIGH |
| **yt-dlp** | 2026.3.17 | YouTube channel listing + subtitle fallback | Lists new uploads via `--flat-playlist --dateafter`; extracts subs when transcript API fails. No API key. | MEDIUM |
| **youtube-transcript-api** | 1.2.4 | YouTube transcript fetch | Fast, no API key, no browser. Primary transcript path. | MEDIUM |
| **Kill the Newsletter** | hosted | Email→Atom bridge | Free, zero signup, purpose-built. v1 default for newsletter ingestion. | HIGH |
| **Tailwind CSS** | 4.3.0 | Styling | Standard utility-first CSS; pairs with shadcn/ui and Astro. | HIGH |
| **shadcn/ui** | CLI 4.8.0 | Dark dashboard UI | Copy-paste Radix primitives (Tabs, Card, Badge, ScrollArea). Full ownership, no runtime dep bloat. Matches reference screenshot IA. | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@astrojs/react` | 5.0.5 | React islands in Astro | Tab switching, client-side archive picker — only where Astro islands need interactivity |
| `@astrojs/tailwind` | 6.0.2 | Tailwind integration | Astro + Tailwind wiring |
| `astro/zod` (built-in) | Astro 6.x | Content schema validation | Validate digest JSON shape at build time |
| `httpx` | 0.28+ | HTTP client (Python) | Fetch RSS, Reddit `.rss`, HN feeds with timeouts/retries |
| `tenacity` | 9.x | Retry decorator (Python) | Per-source retry with backoff; one bad feed must not break run |
| `pydantic` | 2.x | Pipeline data models | Typed ingest records, LLM output parsing |
| `structlog` | 24.x | Structured logging | Observable pipeline runs; log token counts and cost estimates |
| `openai` | 2.37.0 | Fallback LLM SDK | If Gemini quality/caps disappoint on specific sources |
| `@radix-ui/react-tabs` | 1.1.13 | Tab primitives | Briefing + 4 topic tabs via shadcn |
| `lucide-react` | 1.16.0 | Icons | Source-type icons, nav |
| `class-variance-authority` | 0.7.1 | Component variants | shadcn dependency |
| `next-themes` | 0.4.x | Dark mode (optional) | If adding theme toggle; otherwise hard-code dark via CSS variables |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **uv** or **pip + venv** | Python deps | `uv` for fast reproducible lockfile; pin in `pipeline/pyproject.toml` |
| **pnpm** | Node deps | Fast, strict; monorepo-friendly for `web/` |
| **Ruff** | Python lint/format | Single tool replaces flake8+black |
| **Prettier** | Astro/TS/CSS format | Match shadcn conventions |
| **act** (optional) | Local GHA testing | Test weekly workflow before pushing cron |

---

## Dimension-by-Dimension Recommendations

### 1. Web App Framework → **Astro 6.3.x** (Confidence: HIGH)

**Why Astro over alternatives:**

| Option | Verdict |
|--------|---------|
| **Astro** ✅ | Weekly digests are **content**, not dynamic API responses. Content Collections + `getStaticPaths()` give date-browseable archive pages for free. Ships mostly HTML; add React islands only for tab UX. |
| **Next.js 16** | Valid if you want one TS codebase, but adds App Router complexity, server/runtime surface, and Vercel cron coupling you don't need for a read-only personal dashboard. |
| **SvelteKit** | Fine technically, but shadcn/ui ecosystem is React-first; you'd reimplement UI primitives. |
| **Plain static HTML** | Works but unmaintainable as archive grows; no schema validation. |

**Watch out:** Tab navigation can be pure CSS (`:target`, radio tabs) with zero JS, or a small React island. Prefer islands over making the whole site a SPA.

**Out-of-scope impact:** No auth → no NextAuth/Clerk. No Q&A chat → no vector DB client in frontend. No real-time → no WebSocket/SSE infra.

---

### 2. Ingestion Runtime → **Python 3.12+ in GitHub Actions** (Confidence: HIGH)

**Why Python, not Node/TS for pipeline:**
- `feedparser`, `yt-dlp`, `youtube-transcript-api` are Python-native or Python-first
- LLM batch scripts are simpler as a linear Python module than orchestrating across two runtimes
- Node `rss-parser` is fine but you'd still need Python for YouTube anyway → two runtimes for no gain

**Where cron lives:** **GitHub Actions** (primary)

```yaml
# .github/workflows/weekly-digest.yml
on:
  schedule:
    - cron: '0 8 * * 0'   # Sunday 08:00 UTC
  workflow_dispatch: {}     # manual re-run
```

| Cron host | Verdict | Cost |
|-----------|---------|------|
| **GitHub Actions** ✅ | 15–40 min weekly run fits easily. Public repo = free minutes. Private Free = 2,000 min/mo. | $0 (public) / within free tier (private) |
| Vercel Cron | Hobby: 1×/day max, 10s timeout. Pro needed for flexibility. | $20/mo for Pro |
| Cloudflare Workers Cron | Good for short jobs; Python not native (Workers = JS/Wasm). Would require porting pipeline. | $0 but wrong language |
| Fly Machines / Railway | Always-on or scheduled machines; overkill for weekly batch. | $5–7/mo minimum |

**Watch out:** GHA schedules are UTC-only and can slip 5–15 min at peak. Fine for "Sunday morning read." Workflows auto-disable after 60 days of repo inactivity on free accounts — push occasionally or use `workflow_dispatch`.

**Node/TS role:** Frontend build only (`pnpm build` in `web/`).

---

### 3. RSS/Feed Library → **feedparser 6.0.12** (Confidence: HIGH)

**Why:** "Ultra-liberal" parsing philosophy handles malformed Substack/RSS variants, encoding issues, and mixed Atom/RSS feeds. Battle-tested since 2004; actively maintained (6.0.12 on PyPI as of 2026-05-21).

**Usage pattern:**
```python
import feedparser
feed = feedparser.parse(url, request_headers={"User-Agent": "AIDigest/1.0"})
for entry in feed.entries:
    ...
```

**Per-source resilience:** Wrap each source in try/except; log and continue. Never fail the whole run on one feed.

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `rss-parser` (Node) in pipeline | Forces Node runtime; less tolerant of malformed feeds | `feedparser` |
| `fastfeedparser` | Faster but newer; benchmark discrepancies on edge-case feeds | `feedparser` for v1; revisit if perf matters at 100+ sources |
| Raw `xml.etree` | Reinventing 20 years of feed quirks | `feedparser` |

**HN:** `https://hnrss.org/` custom feeds (front page, keyword search) — RSS, no API key.  
**Reddit:** Native `https://www.reddit.com/r/{sub}/.rss` — works but rate-limited (Confidence: MEDIUM). Weekly polling of 3–5 subs is usually fine; add delays and User-Agent. If blocked, drop Reddit source gracefully (already a flaky-ingestion pattern).

---

### 4. YouTube Ingestion → **yt-dlp + youtube-transcript-api** (Confidence: MEDIUM)

**Two-step pattern:**

1. **List new uploads** (yt-dlp):
```bash
yt-dlp --flat-playlist --print "%(id)s\t%(upload_date)s\t%(title)s" \
  --dateafter now-7days --skip-download \
  "https://www.youtube.com/@Channel/videos"
```

2. **Fetch transcript** (youtube-transcript-api):
```python
from youtube_transcript_api import YouTubeTranscriptApi
transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
```

3. **Fallback** when captions missing or API blocked:
```bash
yt-dlp --write-auto-subs --sub-lang en --skip-download --sub-format vtt VIDEO_URL
```

| Avoid | Why |
|-------|-----|
| YouTube Data API v3 | Quota limits, API key management, unnecessary for personal use |
| Paid transcript APIs (AssemblyAI, etc.) | Cost not justified when captions exist |
| Innertube scraping by hand | yt-dlp already wraps this; don't maintain your own |
| Downloading full video audio | Out of scope (podcast transcription deferred to v2) |

**Watch out:** YouTube unofficial APIs break periodically. Pin `yt-dlp` version but allow Dependabot bumps. Log transcript failures per video; include metadata-only items in digest with a "no transcript" flag rather than skipping silently.

---

### 5. Email-to-RSS Bridge → **Kill the Newsletter** (hosted) (Confidence: HIGH)

| Service | Cost | Verdict |
|---------|------|---------|
| **Kill the Newsletter** ✅ | Free | Default for v1. Creates Atom feed + forwarding address. No account. |
| Self-hosted KTN (`jtsang4/kill-the-newsletter`) | ~$0 on existing VPS | Fallback if publishers block the public service |
| Feedbin | $5/mo | Full RSS reader platform — overkill when you only need Atom output |
| Buttondown | $9+/mo | Newsletter *sending* platform, not email→RSS conversion |
| Mailbrew / Stoop | Discontinued or different product category | Not applicable |

**Kill the Newsletter gotchas (from official docs):**
- Some publishers block KTN addresses → workaround: subscribe with personal email, forward to KTN address via filter
- Old entries are pruned when feed exceeds size limit → **pipeline must ingest weekly**, not rely on old entries staying in feed
- Feeds are not shareable (security by design) — fine for personal use
- Cannot reply-to-confirm subscriptions — contact publisher or use personal email + forward

**Privacy:** Store KTN feed URLs in GitHub Secrets or private config, not in public repo. URLs contain inbox identifiers.

---

### 6. LLM Provider/SDK → **Google Gemini via google-genai** (Confidence: HIGH)

**Primary:** `gemini-2.5-flash-lite` (batch) for per-item work  
**Secondary:** `gemini-2.5-flash` (batch) for weekly narrative roll-up  
**SDK:** `google-genai` 2.5.0 — plain Python, structured JSON output, Batch API

**Why not LangChain / Vercel AI SDK:**
- Pipeline is a linear 4-step script (summarize → categorize → rank → rollup), not an agent graph
- LangChain adds dependency weight and abstraction leak for zero benefit at this scale
- Vercel AI SDK is TypeScript-first; pipeline is Python

**Fallback:** `openai` SDK with `gpt-4o-mini` via Batch API if Gemini quality disappoints on specific content types.

**Cost model (weekly, generous estimate):**

| Step | Tokens (est.) | Model (batch) | Cost |
|------|---------------|---------------|------|
| Per-item summarize+categorize × 150 items | 450K in / 45K out | Flash-Lite | ~$0.03 |
| Top-N ranking (single call) | 50K in / 2K out | Flash-Lite | ~$0.003 |
| Weekly narrative roll-up | 80K in / 4K out | Flash | ~$0.017 |
| **Total** | | | **~$0.05–0.50/wk** |

Well within "a few dollars per week" constraint. Log `usage_metadata` per call; emit a cost summary at end of pipeline run.

**Structured output:** Use JSON schema / `response_mime_type="application/json"` for category enum (`edtech|business|technical|design`) and ranked item lists — avoids fragile regex parsing.

| Avoid | Why |
|-------|-----|
| GPT-4o / Claude Sonnet for all items | 10–50× cost for marginal quality gain on TL;DRs |
| Real-time API for batch work | Batch API = 50% discount; weekly cadence has no latency requirement |
| LangChain | Over-engineering for linear pipeline |

**Out-of-scope impact:** No Whisper/audio → no transcription LLM costs. No Twitter → no enrichment calls. No RAG/chat → no embedding model or vector DB costs.

---

### 7. Storage → **SQLite (ephemeral) + Git-committed digest JSON** (Confidence: HIGH)

**Two-layer storage:**

| Layer | What | Where | Purpose |
|-------|------|-------|---------|
| **Working store** | Raw items, content hashes, ingest timestamps, LLM run logs | `pipeline/data/digest.db` (SQLite, gitignored) | Dedup across weeks; "what's new since last run" |
| **Published archive** | Weekly digest artifacts (items, rankings, roll-up, metadata) | `web/src/content/digests/2026-W21.json` (committed) | Source of truth for site + full git history |

**Why not other options:**

| Option | Verdict |
|--------|---------|
| **JSON in repo** ✅ | Archive requirement met; Astro Content Collections validate at build; $0; git blame/history for free |
| SQLite only | Site would need runtime DB or rebuild hack; wrong for static hosting |
| Turso / Neon / Supabase | Adds remote DB, connection strings, and cost for a single-user read-only site. Revisit for v2 multi-user |
| CMS (Sanity, Contentful) | Monthly cost + complexity for content you generate yourself |

**Digest JSON schema (sketch):**
```json
{
  "weekStart": "2026-05-18",
  "weekEnd": "2026-05-24",
  "updatedAt": "2026-05-25T08:00:00Z",
  "rollup": "...",
  "topN": ["item-id-1", "item-id-2"],
  "items": [{ "id", "title", "source", "url", "category", "summary", "publishedAt" }]
}
```

**Watch out:** Transcripts can be large — store full text in SQLite only; commit **summaries** to JSON, not raw 30K-token transcripts (keeps repo lean).

---

### 8. Hosting → **Cloudflare Pages + GitHub Actions** (Confidence: HIGH)

| Target | Cost | Verdict |
|--------|------|---------|
| **Cloudflare Pages** ✅ | $0 | Unlimited bandwidth, custom domain, auto-deploy on push. Best fit for Astro static output. |
| GitHub Pages | $0 | Also fine; CF Pages has better preview deploys and analytics |
| Vercel | $0 hobby | Works for Astro, but cron limits push you toward paid tier for pipeline |
| Fly.io / Railway | $5+/mo | Unnecessary always-on compute |
| Pure GHA → gh-pages | $0 | Valid; CF Pages DX is slightly better |

**Deploy flow:**
1. GHA runs Python pipeline
2. Commits updated `web/src/content/digests/*.json` + `pipeline/data/` artifacts (optional: upload SQLite as GHA artifact for debugging, not deployed)
3. Runs `pnpm build` in `web/`
4. Deploys `web/dist/` to Cloudflare Pages via `cloudflare/pages-action`

**Total hosting cost: $0/mo** on free tiers.

---

### 9. Styling / UI → **Tailwind CSS 4 + shadcn/ui** (Confidence: HIGH)

**Why this combo:**
- Reference screenshot = dark dashboard with tabs, cards, ranked list — maps directly to shadcn Tabs + Card + Badge
- Copy-paste model = no component library lock-in; customize to match reference aesthetic
- Radix primitives = accessible tab panels out of the box

**Why not alternatives:**

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Tremor | Chart/KPI-focused; reference KPI strip is out of scope; wrong abstraction for narrative digest | shadcn Card + typography |
| Catalyst (Tailwind UI) | Paid ($), less community momentum than shadcn | shadcn/ui (free) |
| Plain CSS | Slower to match polished dark dashboard reference | Tailwind + shadcn |
| MUI / Chakra | Heavy runtime, harder to get "editorial dark" aesthetic | shadcn + CSS variables |

**Dark theme approach:** Define shadcn CSS variables in `:root` with dark values (no toggle needed for v1). Use `--background: 222.2 84% 4.9%` style tokens. Optional `next-themes` if you add light mode later.

**Astro integration:** Use `@astrojs/react` islands for interactive Tabs; everything else static HTML.

---

## Installation

```bash
# ── Web (Astro dashboard) ──
cd web
pnpm create astro@latest . --template basics --install=false
pnpm add @astrojs/react @astrojs/tailwind react react-dom
pnpm add -D tailwindcss @tailwindcss/vite
pnpm dlx shadcn@latest init

# ── Pipeline (Python ingestion + LLM) ──
cd ../pipeline
uv init  # or: python -m venv .venv && source .venv/bin/activate
uv add feedparser httpx tenacity pydantic structlog google-genai yt-dlp youtube-transcript-api
uv add --dev ruff pytest
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Astro | Next.js 16 | You want a single TypeScript monorepo and may add auth/API routes in v2 |
| Python pipeline | Node pipeline | You drop YouTube ingestion and only use RSS (not recommended) |
| GitHub Actions cron | Cloudflare Workers cron | Pipeline ported to TypeScript and runs in <30s (unlikely with LLM batch) |
| Gemini Flash-Lite | GPT-4o mini (batch) | Gemini quality insufficient; OpenAI batch: $0.075/$0.30 per M |
| Kill the Newsletter | Self-hosted KTN | Publishers block public KTN addresses |
| Git JSON archive | Turso + Astro SSR | v2 multi-user with dynamic "current week" without rebuild |
| Cloudflare Pages | Vercel | You already live in Vercel ecosystem and accept no cron on hobby |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Twitter/X API or scrapers** | Out of scope; API ~$100/mo; scrapers brittle (PROJECT.md) | — (skip entirely) |
| **Whisper / audio transcription** | Out of scope; expensive weekly batch (PROJECT.md) | YouTube captions only |
| **LangChain / LlamaIndex** | Agent/RAG frameworks for a linear 4-step script | Plain `google-genai` SDK |
| **Vercel AI SDK** in pipeline | TypeScript; pipeline is Python | `google-genai` or `openai` Python SDK |
| **NextAuth / Clerk / Supabase Auth** | No auth in v1 | Static site, no login |
| **Podcast RSS + audio download** | Metadata-only without transcription adds no summary value | Defer to v2 |
| **LinkedIn scraping** | Out of scope; no clean API | — |
| **Neon/Supabase Postgres** | Overkill for single-user static archive | SQLite + git JSON |
| **Vector DB (Pinecone, etc.)** | Q&A chat out of scope | — |
| **Tremor / Recharts** | KPI strip out of scope; no charts needed in v1 | Typography + cards |
| **rss-parser as primary** | Less tolerant; still need Python for YouTube | feedparser |
| **Innertube DIY** | yt-dlp maintains this for you | yt-dlp |
| **Feedbin ($5/mo)** | Paying for a reader you won't use | Kill the Newsletter (free) |
| **Real-time/cron more than weekly** | Out of scope; increases LLM cost | Weekly GHA cron only |

---

## Stack Patterns by Variant

**If YouTube transcript reliability drops:**
- Fall back to yt-dlp `--write-auto-subs` for every video
- Include title+description-only summary when no captions exist (flag in UI)

**If Kill the Newsletter is blocked by a publisher:**
- Personal email subscribe + Gmail filter forward to KTN address
- Or self-host `ghcr.io/jtsang4/kill-the-newsletter:latest` on a $5 VPS

**If Reddit RSS gets rate-limited:**
- Reduce to 1–2 high-value subs; increase delay between fetches
- Drop Reddit from v1 rather than add OAuth/API complexity

**If LLM costs spike:**
- Truncate transcripts to first 4K tokens before summarization
- Lower `topN` count
- Switch ranking+rollup to Flash-Lite (single quality trade-off)

**If v2 adds multi-user "bring your own sources":**
- Add Turso (SQLite edge) or Neon Postgres for per-user source config + ingest state
- Keep published digests as static JSON or move to SSR with Astro server routes
- Add auth (Clerk or Auth.js) — not before v2

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Astro 6.3.x | `@astrojs/react` 5.0.x | React 19 islands |
| Astro 6.3.x | Tailwind CSS 4.x | Use `@tailwindcss/vite` plugin |
| shadcn CLI 4.8.x | Tailwind 4.x | Init with Tailwind v4 template |
| `google-genai` 2.5.x | `gemini-2.5-flash-lite` | Verify model ID at runtime; Google deprecates preview models periodically |
| `yt-dlp` 2026.x | Python 3.10+ | Pin version; update when YouTube breaks extraction |
| `youtube-transcript-api` 1.2.x | Python 3.8+ | Independent of yt-dlp version |
| Node 22 LTS | Astro 6.x, pnpm 9+ | Use `.nvmrc` |

---

## Estimated Monthly Cost (Personal Use)

| Category | Estimate |
|----------|----------|
| Hosting (CF Pages + GHA) | $0 |
| Email→RSS (KTN) | $0 |
| LLM (Gemini batch, ~4 runs/mo) | $0.20–2.00 |
| Domain (optional) | ~$1/mo amortized |
| **Total** | **~$0–3/mo** |

---

## Sources

- [Astro Content Collections](https://docs.astro.build/en/guides/content-collections/) — archive/build-time pattern (HIGH)
- Context7 `/withastro/astro` — Content Collection loaders, Zod schemas (HIGH)
- [PyPI feedparser 6.0.12](https://pypi.org/project/feedparser/) — version verified 2026-05-21 (HIGH)
- [PyPI yt-dlp 2026.3.17](https://pypi.org/project/yt-dlp/) — version verified (HIGH)
- [PyPI youtube-transcript-api 1.2.4](https://pypi.org/project/youtube-transcript-api/) — version verified (HIGH)
- [Kill the Newsletter official site](https://kill-the-newsletter.com/) — limitations, pruning, blocking (HIGH)
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) — Flash-Lite/Flash batch rates (HIGH)
- [OpenAI API pricing](https://developers.openai.com/api/docs/pricing) — GPT-4o mini batch fallback rates (HIGH)
- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) — free tier minutes (HIGH)
- [hnrss.org](https://hnrss.org/) — HN RSS without API (HIGH)
- npm registry — Astro 6.3.7, Next 16.2.6, Tailwind 4.3.0, shadcn 4.8.0, google-genai 2.5.0 (HIGH)
- WebSearch — Reddit RSS rate limiting, KTN vs Feedbin, yt-dlp channel listing (MEDIUM)

---
*Stack research for: AI Digest — personal weekly AI news dashboard*  
*Researched: 2026-05-21*
