# AI Digest

A personal weekly AI digest pipeline. Pulls items from configured RSS sources,
stores them in SQLite, summarizes each with Gemini Flash-Lite, and renders a
plain HTML digest you can open in a browser.

> Phase 1 walking skeleton: one RSS source (Simon Willison's blog), one real
> Gemini call per item, plain HTML output. More sources, dedup, ranking, and
> a dashboard land in later phases.

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
# then edit .env and paste your key:
#   GEMINI_API_KEY=AIza...
```

Get a Gemini API key from <https://aistudio.google.com/apikey> (free tier is
plenty for the walking skeleton — `gemini-2.5-flash-lite` costs pennies).

## Run

```bash
uv run python -m pipeline.run all
```

This will:

1. Fetch items from all enabled sources in `config/sources.yaml`
2. Upsert them into `data/aidigest.db` (SQLite, gitignored)
3. Generate a TL;DR for each item via Gemini
4. Write `out/digest-YYYY-Www.html` (gitignored)

Open the digest in your browser:

```bash
# macOS
open out/digest-*.html

# Linux
xdg-open out/digest-*.html

# Windows (PowerShell)
ii out/digest-*.html
```

## Test

```bash
uv run pytest
```

## Layout

```
pipeline/        Application code (adapters, LLM, render, orchestrator, CLI)
store/           SQLite schema + helpers
config/          sources.yaml — checked-in source list
tests/           pytest suite
data/            SQLite working store (gitignored)
out/             Generated digest HTML (gitignored)
.planning/       GSD planning artifacts (roadmap, phases, research)
```

## Security

- `.env` is gitignored — **never** commit your Gemini API key.
- All HTML output escapes user-derived strings (titles, summaries, publishers).
- Source links open with `target="_blank" rel="noopener"` to prevent
  `window.opener` phishing.

## Project status

Phase 1 of 5 — see `.planning/ROADMAP.md` for the full plan.
