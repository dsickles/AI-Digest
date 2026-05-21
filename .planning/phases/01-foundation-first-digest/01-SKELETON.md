# Walking Skeleton — AI Digest

**Phase:** 1 — Foundation + First Digest  
**Generated:** 2026-05-21

## Capability Proven End-to-End

Running `python -m pipeline.run all` with a valid `GEMINI_API_KEY` fetches Simon Willison's Atom feed, upserts at least one item into SQLite, generates one real Gemini Flash-Lite TL;DR, and writes `out/digest-{week_id}.html` that opens in a browser showing one readable card.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Language / runtime | Python 3.12+ CLI batch pipeline | Best RSS + LLM ecosystem; matches STACK.md and D-00a |
| Package layout | Root `pyproject.toml`; importable package `pipeline/` + `store/` per D-00b | Enables `python -m pipeline.run`; avoids nested `pipeline/pipeline/` |
| Working store | SQLite at `data/aidigest.db` (gitignored), WAL mode | Ephemeral ingest/summary state; ARCHITECTURE store-and-forward pattern |
| Ingest contract | `IngestAdapter` protocol + `NormalizedItem` Pydantic model | Phase 2 adapters plug in without store changes (D-00d) |
| Item identity | `UNIQUE(source_id, external_id)` with GUID-or-hash derivation (D-00c) | Idempotent re-ingest; INGEST-08 foundation |
| LLM | `google-genai` → `gemini-2.5-flash-lite`, structured JSON output | Cost-bounded per-item summaries; D-00a |
| Prompts | Versioned file `pipeline/llm/prompts/summarize_v1.md`; `prompt_version` on `item_summaries` | PITFALLS #13; D-04 seed |
| Phase 1 renderer | Plain HTML to `out/digest-{week_id}.html` (gitignored) | PITFALLS #25 content-first; Astro deferred to Phase 4 |
| Orchestration entry | `python -m pipeline.run all` (subcommand split in Plan 04) | Proves ingest → summarize → render wiring |
| Secrets | `GEMINI_API_KEY` via `.env` + `python-dotenv`; `.env` gitignored | ASVS: no keys in repo |
| Tooling | `uv` lockfile, `pytest`, `ruff` (dev) | RESEARCH stack pinning |

## Stack Touched in Phase 1 (Skeleton)

- [x] Project scaffold (`pyproject.toml`, `pipeline/`, `store/`, `config/`, `tests/`, `.env.example`, `.gitignore`)
- [x] Config — `config/sources.yaml` with one RSS source (`simon-willison`, D-01 partial)
- [x] Database — SQLite schema + one real upsert into `items`
- [x] Ingest — `RssAdapter` + `feedparser` fetch
- [x] LLM — one real Gemini call → one `item_summaries` row
- [x] UI artifact — one HTML file with one card (minimal inline CSS)
- [x] Observability stub — `structlog` stdout + `pipeline_runs` row on success
- [ ] Deployment — local CLI only (GHA + CF Pages = Phase 5)

## Out of Scope (Deferred Within Phase 1)

- Second and third RSS sources (`one-useful-thing`, `import-ai`) → Plan 01-02
- Idempotent re-ingest verification across 3 feeds → Plan 01-02
- `trafilatura` full-fetch fallback, grounding sentinel, `summary_confidence`, degraded cards → Plan 01-03
- `--week YYYY-Www` threading, README/UAT, CLI subcommand split → Plan 01-04
- Full `structlog` config, `out/last_run.md`, HTML header polish, pytest suite → Plan 01-05
- Dedup, categorization, ranking, weekly rollup → Phase 3
- Astro dashboard, archive JSON, pipeline-notes UI → Phase 4
- GHA cron, Cloudflare deploy, secret scanning, heartbeat → Phase 5

## Verification (Human)

```bash
export GEMINI_API_KEY=...   # or use .env
python -m pipeline.run all
open out/digest-$(date -u +%G-W%V).html   # macOS; week_id is current ISO week UTC
```

Expect: dark-ish readable page, one card with title, publisher badge, date, link, and 2–4 sentence TL;DR.

## Subsequent Slice Plan (Phase 1 Plans 02–05)

| Plan | Vertical slice added |
|------|---------------------|
| 01-02 | All 3 seed sources + per-source failure isolation + idempotent upsert (INGEST-08) |
| 01-03 | Hybrid content fetch, grounding prompt, confidence enum, degraded rendering |
| 01-04 | ISO week override, CLI `ingest\|summarize\|render\|all`, discoverability (D-22) |
| 01-05 | Debuggability (`last_run.md`, `pipeline_runs` richness), HTML header polish, pytest suite |
