# AI Digest

A personal weekly AI digest pipeline. Pulls items from configured RSS sources,
stores them in SQLite, summarizes each with Gemini Flash-Lite, and renders a
plain HTML digest you can open in a browser.

> **Phase 1 complete:** 2–3 RSS sources, per-item TL;DR, plain dark HTML,
> idempotent ingest, degraded-summary handling, `out/last_run.md` debugging.
>
> **Phase 2 complete:** 8-source catalog (5 RSS + 2 YouTube + 1 newsletter),
> YouTube transcript ingestion with cloud → residential catch-up flow
> (`--only-pending-transcripts`), in-place degradation cards, typed
> per-source failure isolation, and a header pipeline-status notice.
>
> Dedup, ranking, and the Astro dashboard land in later phases.

## Prerequisites

- Python **3.12+**
- [`uv`](https://docs.astral.sh/uv/) for dependency management

### Install `uv`

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

`uv` will install Python 3.12 for you on first sync if you don't have it:

```bash
uv python install 3.12
```

## Setup

```bash
# Install dependencies + create .venv
uv sync

# Copy the env template and add your Gemini API key
cp .env.example .env       # macOS / Linux
copy .env.example .env     # Windows (cmd)
```

### Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GEMINI_API_KEY` | For `summarize` / `all` | Google Gemini API key for TL;DR generation |
| `LOG_LEVEL` | No | Override structlog level (default `INFO`) |

Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).
The free tier is sufficient for personal weekly use — `gemini-2.5-flash-lite`
costs fractions of a cent per item at list price.

Add to `.env`:

```env
GEMINI_API_KEY=AIza...
```

Never commit `.env` — it is gitignored.

### Sources configuration

RSS sources live in `config/sources.yaml`. Each entry needs:

- `id` — stable kebab-case identifier (FK in SQLite)
- `type` — `rss` (only type in Phase 1)
- `url` — feed URL
- `display_name` — shown as `[display_name]` badge in the digest
- `enabled` — set `false` to skip a source without deleting it

YouTube channels use `type: youtube` and a `channel_id` (24 characters
starting with `UC`); the adapter derives the feed URL from the channel ID
and pulls per-video transcripts. Phase 2 ships eight sources by default
(five RSS, two YouTube, one newsletter). Edit this file to add or disable
sources before running ingest.

## Run

```bash
uv run python -m pipeline.run all
```

This will:

1. Fetch items from all **enabled** sources in `config/sources.yaml`
2. Upsert them into `data/aidigest.db` (SQLite, gitignored)
3. Generate a TL;DR for each item in the target ISO week via Gemini
4. Write `out/digest-YYYY-Www.html` (gitignored)
5. Write `out/last_run.md` run report (gitignored)

### Subcommands

All subcommands accept `--week YYYY-Www` to target a specific **ISO week in UTC**
(for backfill or replay). When omitted, the current UTC ISO week is used.

| Subcommand | Description |
|------------|-------------|
| `ingest` | Fetch enabled RSS sources and upsert into SQLite (network only) |
| `summarize` | Generate TL;DRs for items in the week window missing a summary (LLM) |
| `render` | Build HTML from existing SQLite data (no network, no LLM) |
| `all` | Run `ingest` → `summarize` → `render` in one pass (**default**) |

Examples:

```bash
# Full weekly run (current UTC week)
uv run python -m pipeline.run all

# Backfill a past week end-to-end
uv run python -m pipeline.run all --week 2026-W19

# Re-render HTML without re-spending LLM tokens
uv run python -m pipeline.run render --week 2026-W19

# Ingest only (no API key needed)
uv run python -m pipeline.run ingest

# Bare invocation aliases `all`
uv run python -m pipeline.run --week 2026-W19
```

### YouTube transcript catch-up

When the weekly run executes from a cloud network (GitHub Actions, a hosted
VM) the YouTube transcript API is often blocked by an "IP blocked" or "too
many requests" response. Those video items still ingest fine — they just
land with `transcript_status='pending_local'`, and their cards in the digest
fall back to the channel description plus a small "transcript wasn't
reachable" note (D-25 in-place degradation).

To recover those items, run the pipeline a second time **from a residential
network** (your laptop on home Wi-Fi, a coffee-shop hotspot — anywhere the
transcript API works without a paid proxy):

```bash
# Retry only the pending YouTube transcripts; skip RSS sources entirely
uv run python -m pipeline.run ingest --only-pending-transcripts

# Same, then re-summarize and re-render for the current week
uv run python -m pipeline.run all --only-pending-transcripts

# Catch-up for a specific past week
uv run python -m pipeline.run all --only-pending-transcripts --week 2026-W19
```

The flag is a no-op when nothing is pending. On a successful transcript
fetch the item's `transcript_status` flips to `ok` and its `raw_content` is
replaced with the captions, so the next `summarize` pass produces a
transcript-grounded TL;DR. If the YouTube API confirms a video has no
captions (`TranscriptsDisabled`) the catch-up path advances the status to
`missing` — that's the only path in the codebase that may set `missing`, so
those items will not be retried by future catch-up runs.

### Manual browser check

Open the digest and confirm readability (dark theme, week header, source badges):

```bash
# macOS
open out/digest-*.html

# Linux
xdg-open out/digest-*.html

# Windows (PowerShell)
ii out/digest-*.html
```

## Debugging

Every pipeline subcommand overwrites `out/last_run.md` with a markdown report:

- Run metadata (`week_id`, phase, started/finished timestamps, status)
- Per-source table (items fetched, one-line errors)
- Totals (`summaries_written`, `items_degraded`)
- LLM section (`llm_calls`, `cost_usd_estimate`)
- Errors bullet list (one line per failure)

After a run:

```bash
cat out/last_run.md
```

The report never contains your API key or full article bodies. For deeper
inspection, query `data/aidigest.db` — the `pipeline_runs` table holds
`finished_at`, counters, and `errors_json`.

Structured logs go to stdout (key=value on TTY, JSON when piped). Ingest and
summarize events include `source_id`; summarize events include token counts
and `cost_usd_estimate`.

## Test

```bash
uv run pytest tests/ -x -q
uv run ruff check .
```

Live end-to-end (`uv run python -m pipeline.run all` with real feeds + API key)
requires network access outside sandboxed CI and is a manual follow-up. Corporate
TLS interception may require OS trust-store configuration (see Plan 01-01).

## Phase 1 success criteria (manual checklist)

Use this after a live run to confirm Phase 1 ROADMAP intent:

- [ ] **Readable digest:** `out/digest-YYYY-Www.html` opens in a browser; header
      shows "Week of …" range and "Updated …" UTC timestamp; dark theme ~720px width
- [ ] **Grounded TL;DRs:** Each card shows title, `[publisher]` badge, link,
      publication date, and a 2–4 sentence summary (or degraded sentinel for thin RSS)
- [ ] **Idempotent ingest:** Running `ingest` or `all` twice for the same week does
      not duplicate items (same `source_id` + `external_id` upserts in place)
- [ ] **Graceful degradation:** Thin RSS bodies show
      `[summary unavailable — content too thin]` inline — no invented facts

## Layout

```
pipeline/        Application code (adapters, LLM, render, orchestrator, CLI)
store/           SQLite schema + helpers
config/          sources.yaml — checked-in source list
tests/           pytest suite
data/            SQLite working store (gitignored)
out/             Generated digest HTML + last_run.md (gitignored)
.planning/       GSD planning artifacts (roadmap, phases, research)
```

## Security

- `.env` is gitignored — **never** commit your Gemini API key.
- All HTML output escapes user-derived strings (titles, summaries, publishers).
- Source links open with `target="_blank" rel="noopener"` to prevent
  `window.opener` phishing.
- `out/last_run.md` and structlog output must not contain API keys or full
  article bodies at INFO level.

## Project status

**Phases 1–2 of 5 — complete.** See `.planning/ROADMAP.md` for Phase 3+
(Reddit/HN, dedup, Astro dashboard, GHA automation).
