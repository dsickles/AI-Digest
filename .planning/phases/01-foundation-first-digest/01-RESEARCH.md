# Phase 1: Foundation + First Digest — Research

**Researched:** 2026-05-21  
**Domain:** Greenfield Python batch pipeline — RSS ingest → SQLite → Gemini per-item TL;DR → plain HTML  
**Confidence:** HIGH (stack/docs verified on PyPI + official docs); MEDIUM (feed-specific GUID quirks, free-tier RPM numbers — verify in AI Studio)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-00a..D-22:** See `.planning/phases/01-foundation-first-digest/01-CONTEXT.md` — Python 3.12+, feedparser, google-genai + `gemini-2.5-flash-lite`, SQLite, structlog; adapter registry; `(source_id, external_id)` PK; hybrid RSS/trafilatura summarizer input; grounding prompt in `summarize_v1.md`; `summary_confidence` column; `pipeline_runs` + `out/last_run.md`; ISO week + `--week` CLI; plain HTML to `out/digest-{week_id}.html`; split CLI subcommands (`ingest`/`summarize`/`render`/`all`); hidden-capability discoverability policy (D-22).

### Claude's Discretion
- Token budgeting / batch-vs-streaming call shape
- `IngestAdapter` protocol + `NormalizedItem` Pydantic shape
- trafilatura vs readability-lxml primary (behavior locked: trafilatura preferred)
- uv vs pip, ruff config, lockfile placement
- `GEMINI_API_KEY` loading mechanism
- Test framework, CI timing, coverage targets (must include `--week` UAT per D-22)

### Deferred Ideas (OUT OF SCOPE)
- In-dashboard force re-summarize button (post-v1)
- All Phase 2–5 features per CONTEXT boundary table
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-01 | Sources in checked-in YAML | `config/sources.yaml` + PyYAML loader; seed URLs locked in D-01 |
| INGEST-02 | Fetch RSS/Substack feeds | feedparser 6.0.12 + httpx User-Agent; three seed feeds verified as RSS/Atom |
| INGEST-07 | Store source_id, external_id, URL, title, publisher, date, raw content | SQLite `items` DDL + `NormalizedItem` field map |
| INGEST-08 | Unique `(source_id, external_id)` | UNIQUE constraint + upsert pattern; GUID stability rules in feedparser deep-dive |
| PIPELINE-01 | Per-item TL;DR grounded in content | google-genai structured JSON + `summarize_v1.md`; degraded sentinel path (D-04/D-05) |
</phase_requirements>

## Phase Boundary Confirmation

**In scope (Phase 1):** Runnable CLI (`python -m pipeline.run [all]`) reading `config/sources.yaml`; three RSS/Atom feeds (D-01); SQLite upsert keyed by `(source_id, external_id)`; per-item Gemini Flash-Lite summaries with hybrid RSS/trafilatura input; plain HTML digest at `out/digest-{week_id}.html`; ISO-week orchestration with `--week` override; debug slice (`structlog`, `out/last_run.md`, `pipeline_runs` table).

**Explicitly out of scope:** YouTube/Reddit/HN/email-RSS adapters (Phase 2); dedup, categorization, ranking, weekly rollup, idempotency hard cap, `pipeline_report.json` (Phase 3); Astro dashboard, archive JSON, pipeline-notes UI (Phase 4); GHA cron, CF Pages deploy, secret scanning, $5/week hard cap, heartbeat (Phase 5).

**Ambiguities for planner:**

| Topic | Tension | Recommendation |
|-------|---------|----------------|
| **PIPELINE-01 wording** | REQUIREMENTS.md says "story cluster"; Phase 1 has no clusters | Treat as **per-item** summary (CONTEXT D-04); clusters arrive Phase 3 |
| **INGEST-06 (per-source isolation)** | Mapped to Phase 2, but PROJECT.md requires one bad source must not break the run | Implement **try/except per source in Phase 1** anyway — ~10 lines, zero Phase-2 rework |
| **Ingest week window** | Unclear if ingest filters by `--week` or ingests full feed | **Ingest all entries from feed** (typical 20–50 items); **summarize/render filter** by `published_at ∈ [week_start, week_end]` UTC |
| **DB path** | STACK.md says `pipeline/data/digest.db`; D-00b says root `data/` gitignored | Use **`data/aidigest.db`** at repo root per D-00b / ARCHITECTURE |
| **Batch API** | STACK.md recommends Batch for cost | **Standard (sync) API for Phase 1** — Batch has no free tier [CITED: ai.google.dev pricing]; ~30 calls/week fits free Standard API |
| **sources table vs YAML-only** | ARCHITECTURE lists Source entity | **YAML is source of truth**; optional `sources` table for FK + ETag cache — planner can defer table to Plan 2 if skeleton uses YAML FK as TEXT |

## Stack Pinning

Verified on PyPI 2026-05-21. Ranges are uv-compatible (`>=` lower bound, `<` next major).

| Package | Pin (recommended) | Role in Phase 1 |
|---------|-------------------|-----------------|
| `feedparser` | `>=6.0.12,<7` | RSS/Atom parse |
| `google-genai` | `>=2.5.0,<3` | Gemini SDK |
| `httpx` | `>=0.28.1,<0.29` | Article fetch (trafilatura path) |
| `tenacity` | `>=9.1.4,<10` | Retry 429/5xx on HTTP + LLM |
| `pydantic` | `>=2.13.4,<3` | `NormalizedItem`, summary schema |
| `structlog` | `>=25.5.0,<26` | Structured stdout logs |
| `trafilatura` | `>=2.0.0,<3` | Primary full-page extract (D-03) |
| `readability-lxml` | `>=0.8.4.1,<0.9` | Fallback extractor only |
| `PyYAML` | `>=6.0.3,<7` | `sources.yaml` loader |
| `python-dotenv` | `>=1.2.2,<2` | Local `.env` for `GEMINI_API_KEY` |
| `ruff` | `>=0.15.14,<0.16` | Lint/format (dev) |
| `pytest` | `>=9.0.3,<10` | Tests (dev) |

**Not in Phase 1 deps:** `yt-dlp`, `youtube-transcript-api`, Astro/shadcn (Phase 4+).

**Python:** `>=3.12` (project constraint). **Tooling:** `uv` with root or `pipeline/pyproject.toml` — lockfile committed.

**Package Legitimacy Audit** (slopcheck unavailable in environment; verified via PyPI + known repos):

| Package | Registry | Source Repo | Disposition |
|---------|----------|-------------|-------------|
| feedparser | PyPI 6.0.12 | github.com/kurtmckee/feedparser | Approved |
| google-genai | PyPI 2.5.0 | github.com/googleapis/python-genai | Approved |
| trafilatura | PyPI 2.0.0 | github.com/adbar/trafilatura | Approved |
| readability-lxml | PyPI 0.8.4.1 | github.com/buriy/python-readability | Approved (fallback only) |

## Library Deep-Dives

### 1. feedparser (INGEST-02, INGEST-07, INGEST-08)

**Entry ID / `external_id` stability** [CITED: feedparser.readthedocs.io/reference-entry-id]

| Feed | Typical `entry.id` | Stable for D-00c? | Fallback |
|------|------------------|-------------------|----------|
| **Substack** (`importai.substack.com/feed`) | RSS 2.0 `<guid isPermaLink="true">` → post URL | **Yes** — URL-shaped GUID persists across re-fetch | `sha256(url + YYYY-MM-DD)` if guid missing |
| **Simon Willison Atom** | Atom `<id>` URI (often tag: or https://) | **Yes** — Atom IDs are permanent | same hash fallback |
| **One Useful Thing** | Substack-style GUID | **Yes** | same |

**Rules for adapter:**
1. Use `entry.get("id")` or `entry.get("guid")` when non-empty.
2. Treat GUID as **unstable** when RSS 2.0 `guidislink` is false and value is not URL-like — fall back to hash.
3. Never use title alone as external_id (collisions on "Weekly update" posts).

**Published vs updated** [CITED: feedparser date fields]

- **Display + week filter:** prefer `published_parsed` → UTC `datetime`.
- **Fallback chain:** `published_parsed` → `updated_parsed` → `created_parsed`; if all `None`, log warning and **exclude from week window** (or use ingest-time UTC with `summary_confidence=low` — planner pick; default exclude).
- **Do not use `updated` for week membership** when `published` exists — Atom "updated" on old posts would re-include them in wrong weeks.

**Malformed dates:** feedparser sets `bozo=1` on parse issues; `*_parsed` fields become `None` silently. Log `bozo_exception`, keep item with fallback date policy above.

**Encoding** [CITED: feedparser character-encoding detection]

- Rely on feedparser's encoding detection; check `result.encoding` and `result.bozo`.
- If titles/body show mojibake, log `source_id` + `encoding` + URL.
- Optional hardening: fetch bytes via httpx, pass `feedparser.parse(bytes, response_headers=...)` for Content-Type charset.

**Conditional GET (ETag / If-Modified-Since)** [CITED: feedparser.readthedocs.io/http-etag]

- Supported natively: `feedparser.parse(url, etag=prev_etag, modified=prev_modified)`.
- On **304**: `status==304`, `entries==[]`, `debug_message` explains — **not an error**; skip upsert for that source.
- **Phase 1 recommendation:** defer ETag persistence to Plan 2 within phase; skeleton uses unconditional fetch. Store `etag`/`modified` on a `source_fetch_state` column when added.

**Content body extraction from entries:**

```python
def entry_body(entry) -> str:
    if entry.get("content"):
        return entry.content[0].value
    return entry.get("summary", "") or ""
```

Substack full-text feeds put HTML in `content:encoded` → `entry.content`.

### 2. google-genai (PIPELINE-01, D-08 cost estimate)

**Import path & model ID** [CITED: googleapis.github.io/python-genai]

```python
from google import genai
from google.genai import types

client = genai.Client()  # reads GEMINI_API_KEY or GOOGLE_API_KEY
MODEL = "gemini-2.5-flash-lite"

response = client.models.generate_content(
    model=MODEL,
    contents=[system_prompt, user_content],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=SummaryResponse,  # Pydantic model
        max_output_tokens=256,
        temperature=0.2,
    ),
)
# response.parsed when using Pydantic schema
# response.usage_metadata after call — for logging
```

**Structured output:** `response_mime_type="application/json"` + `response_schema` (Pydantic or dict) on `GenerateContentConfig`. Use for D-04 sentinel: `{"summary": str | null, "reason": "thin_content" | null}`.

**Token counting (D-08 pre-flight):** [CITED: googleapis.github.io/python-genai — Count Tokens]

```python
token_info = client.models.count_tokens(model=MODEL, contents=contents)
# token_info.total_tokens — use for cost estimate before send
```

Call `count_tokens` per item (or batched contents) before summarize; log `tokens_in_estimate`. After call, log `response.usage_metadata` for actuals.

**Retry / rate limits:** SDK does **not** auto-retry 429 [ASSUMED from SDK docs — no built-in retry wrapper]. Wrap `generate_content` with **tenacity**: retry `ResourceExhausted` / HTTP 429, exponential backoff (min 4s, max 60s, 3 attempts), sequential calls ~2s apart for free tier headroom.

**Free vs paid quotas (~30 items/week):** [CITED: ai.google.dev/gemini-api/docs/pricing — Gemini 2.5 Flash-Lite Standard]

| Tier | Input | Output | Phase 1 impact |
|------|-------|--------|----------------|
| **Free** | Free of charge | Free of charge | ~30 summaries/week ≪ daily limits |
| **Paid Standard** | $0.10/M tokens | $0.40/M tokens | ~30 items × 2K in + 200 out ≈ **$0.01/run** |

Rate limits (RPM/TPM/RPD) are **tier- and project-specific** — view in [AI Studio rate limit page](https://aistudio.google.com/rate-limit). Flash-Lite has the highest free-tier RPM among 2.5 models [MEDIUM confidence — third-party blogs cite ~30 RPM; verify in AI Studio before load tests].

**Batch API:** Paid only; turnaround hours. **Not appropriate for Phase 1 manual CLI** — use Standard sync API.

**Output truncation:** Set `max_output_tokens=256` (2–4 sentences). Without it, model may still stop early on `finish_reason`; log `finish_reason` if exposed in response. Truncated JSON breaks parsing — validate with Pydantic; on failure, retry once with stricter prompt or mark degraded.

### 3. trafilatura vs readability-lxml (D-03)

| Criterion | trafilatura 2.0 | readability-lxml 0.8 |
|-----------|-----------------|---------------------|
| **License** | Apache 2.0 [CITED: PyPI] | Apache 2.0 |
| **Deps** | lxml, courlan, htmldate, justext, charset_normalizer | lxml, chardet, cssselect, lxml-html-clean |
| **Substack/article pages** | Strong — main-text heuristics + justext cascade [CITED: trafilatura docs/evaluation] | Good on blogs; weaker on SPAs |
| **HN/Reddit (Phase 2)** | HN thread pages OK; Reddit often login-walled — both fail gracefully | Similar limitations |
| **Footprint** | Larger (more deps) but **includes readability algorithm internally** | Smaller alone, but redundant if trafilatura already present |

**Recommendation:** **`trafilatura` primary** per D-03. Add `readability-lxml` only as explicit fallback:

```python
text = trafilatura.extract(html, url=url, include_comments=False, favor_precision=True)
if not text:
    from readability import Document
    text = Document(html).summary()  # then strip HTML tags
```

Do **not** depend on readability alone — trafilatura subsumes it for Phase 2 HN/blog URLs.

**Cold-start:** First `import trafilatura` loads lxml (~200–500ms). Acceptable for weekly CLI; avoid importing in unit tests that don't need it.

### 4. SQLite schema (D-00c, D-06, D-09)

See **Schema** section below for full DDL. Use WAL mode: `PRAGMA journal_mode=WAL` (works on macOS dev and Linux CI). Single-writer pipeline — no concurrent write concern in Phase 1.

## Schema

Copy-pasteable DDL honoring locked decisions:

```sql
-- store/schema.sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    source_id       TEXT PRIMARY KEY,
    type            TEXT NOT NULL,
    url             TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    tag             TEXT,
    enabled         INTEGER NOT NULL DEFAULT 1,
    etag            TEXT,
    last_modified   TEXT,
    last_fetched_at TEXT,
    last_error      TEXT
);

CREATE TABLE IF NOT EXISTS items (
    item_id         TEXT PRIMARY KEY,  -- uuid4 or hex; internal surrogate
    source_id       TEXT NOT NULL REFERENCES sources(source_id),
    external_id     TEXT NOT NULL,
    canonical_url   TEXT NOT NULL,
    title           TEXT NOT NULL,
    publisher       TEXT NOT NULL,
    published_at    TEXT NOT NULL,     -- ISO 8601 UTC
    raw_content     TEXT NOT NULL DEFAULT '',
    content_hash    TEXT NOT NULL,     -- sha256(normalized raw_content); Phase 3 idempotency
    ingested_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_items_published_at ON items(published_at);
CREATE INDEX IF NOT EXISTS idx_items_source_id ON items(source_id);

CREATE TABLE IF NOT EXISTS item_summaries (
    summary_id          TEXT PRIMARY KEY,
    item_id             TEXT NOT NULL REFERENCES items(item_id),
    week_id             TEXT NOT NULL,   -- YYYY-Www summarization pass
    tldr                TEXT,            -- NULL when degraded
    summary_confidence  TEXT NOT NULL CHECK (summary_confidence IN ('high', 'low', 'unavailable')),
    prompt_version      TEXT NOT NULL,   -- e.g. summarize_v1
    model_id            TEXT NOT NULL,   -- gemini-2.5-flash-lite
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    cost_usd_estimate    REAL,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (item_id, week_id, prompt_version)
);

CREATE INDEX IF NOT EXISTS idx_item_summaries_week ON item_summaries(week_id);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id              TEXT PRIMARY KEY,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    week_id             TEXT NOT NULL,
    phase               TEXT NOT NULL CHECK (phase IN ('ingest', 'summarize', 'render', 'all')),
    status              TEXT NOT NULL CHECK (status IN ('running', 'success', 'partial', 'failed')),
    errors_json         TEXT NOT NULL DEFAULT '[]',
    items_fetched       INTEGER NOT NULL DEFAULT 0,
    summaries_written   INTEGER NOT NULL DEFAULT 0,
    items_degraded      INTEGER NOT NULL DEFAULT 0,
    cost_usd_estimate   REAL NOT NULL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_week ON pipeline_runs(week_id);
```

**external_id derivation (application layer, not DB):**

```python
def derive_external_id(entry, canonical_url: str, published_day: str) -> str:
    guid = entry.get("id") or entry.get("guid")
    if guid and (entry.get("guidislink", True) or guid.startswith("http")):
        return guid.strip()
    return hashlib.sha256(f"{canonical_url}|{published_day}".encode()).hexdigest()
```

## Walking Skeleton Slice

**Thinnest E2E path** (one commit / Plan 1 — proves wiring):

```
config/sources.yaml (1 source: simon-willison)
  → python -m pipeline.run all
    → RssAdapter.fetch → NormalizedItem
    → SQLite upsert (1 item)
    → Gemini summarize (1 item, real API key)
    → HTML render (1 card) → out/digest-{week_id}.html
    → pipeline_runs row (phase=all, status=success)
    → structlog lines on stdout
```

| Must be in skeleton | Defer to later plans (same phase) |
|---------------------|-----------------------------------|
| `pyproject.toml` + uv lock; `pipeline/` package layout per D-00b | All three seed sources (add in Plan 2) |
| `config/sources.yaml` (≥1 source) | ETag/Last-Modified conditional GET |
| SQLite schema + `store/db.py` upsert | `readability-lxml` fallback path |
| `IngestAdapter` protocol + `RssAdapter` | Full `out/last_run.md` breakdown (stub OK in skeleton) |
| `NormalizedItem` Pydantic model | trafilatura path + `<500 char` trigger |
| CLI: `all` only (or all four subcommands stubbed) | `--week` backfill + README docs (D-12) |
| Gemini call with `summarize_v1.md` | Degraded-content rendering (D-05) |
| Minimal HTML template (~40 lines CSS) | `ingest`/`summarize`/`render` isolation tests |
| `pipeline_runs` insert | Per-source failure isolation for 3 feeds |
| `.env.example` + gitignore `data/`, `out/`, `.env` | pytest suite + `--week` UAT (D-22) |

**PITFALLS alignment:**
- **#13:** Create `pipeline/llm/prompts/summarize_v1.md` in skeleton; persist `prompt_version` on first summary row.
- **#14:** Phase 1 prompt is per-item only — no rollup; seed grounding language for Phase 3 hierarchical rollup.
- **#25:** Skeleton HTML is intentionally ugly; no Astro, no tab polish.

## Validation Architecture

> Nyquist Dimension 8 — consumed by orchestrator to generate `VALIDATION.md`.

| Component | Validation Signal | Artifact / Proof |
|-----------|-------------------|------------------|
| **RSS fetch** | Unit + contract | `tests/fixtures/feeds/` (recorded XML snippets for Atom + Substack RSS) → adapter returns `NormalizedItem` list; contract test: required fields present |
| **Normalization** | Unit | Tests for `external_id` derivation (guid vs hash), date fallback chain, body extraction from `content` vs `summary` |
| **Store** | Integration | Temp SQLite file: upsert same `(source_id, external_id)` twice → row count 1; FK violations rejected |
| **Summarizer** | Contract + integration | Mock `genai.Client` for unit tests; optional `--live` marker for one real Gemini call in manual/UAT; Pydantic schema accepts sentinel `thin_content` |
| **Renderer** | Unit + smoke | Snapshot or assert HTML contains title, publisher badge, date, link `rel=noopener`; smoke: `render` produces file at `out/digest-{week_id}.html` with `Content-Type` text/html |
| **Orchestrator** | Integration + smoke | `pipeline run all` exit 0; `pipeline_runs.status=success`; `items_fetched >= 1`; re-run ingest → duplicate count unchanged (INGEST-08) |
| **Week override (D-12)** | UAT / integration | `python -m pipeline.run all --week 2026-W19` uses threaded week_id (no `datetime.now()` past CLI entry) — explicit verification checklist item |

**Test framework default:** `pytest` + `pytest-httpx` (optional) for RSS HTTP mocking. Quick run: `pytest tests/ -x -q`. No CI required in Phase 1 skeleton; add `.github/workflows/test.yml` in final Phase 1 plan if desired.

**Wave 0 gaps:** entire `tests/` tree is greenfield — create with first implementation plan.

## Landmines & Anti-patterns

Phase-1-specific issues **not** fully covered in PITFALLS.md:

| Landmine | What happens | Mitigation |
|----------|--------------|------------|
| **Gemini JSON schema strictness** | SDK client rejects schemas with `additionalProperties` [CITED: googleapis/python-genai#1815] | Use Pydantic models; avoid extra fields; test sentinel response parsing early |
| **Free tier → paid tier surprise** | Billing linked → data may train on prompts on free tier [CITED: Gemini terms] | Document; use paid tier for production if privacy matters (Phase 5) |
| **feedparser 304 treated as failure** | Empty `entries` logged as "0 items fetched" error | Check `d.status == 304`; do not increment error count |
| **Substack HTML in raw_content** | Summarizer receives tags/scripts noise | Strip HTML to text before LLM (stdlib `html.parser` or trafilatura on RSS body if already HTML) |
| **Week boundary UTC vs local** | User expects "Sunday read" in local TZ | D-10 locks **UTC** ISO week — document in README; no `datetime.now()` without timezone |
| **SQLite `:memory:` vs file** | Tests pass; WAL/路径 issues in prod | Integration tests use temp file DB on disk |
| **Concurrent CLI runs** | Two `all` commands corrupt WAL | Phase 1: document single-runner; Phase 5 adds lock file |
| **Re-summarize on re-run** | Same week run twice → duplicate summary rows | `UNIQUE(item_id, week_id, prompt_version)` + upsert or skip-if-exists in summarize phase |
| **render touches network** | Violates D-20 | Enforce import boundaries; render module must not import adapters/llm |
| **Cost estimate zero on free tier** | `last_run.md` shows $0 always | Compute list-price estimate from token counts even when billed $0 — useful when billing enabled |

## Open Questions for Planner

| Question | Default recommendation | Why |
|----------|------------------------|-----|
| **Token budgeting / call shape** | Sequential `generate_content` per item; `count_tokens` before each; 2s sleep between calls on free tier | ~30 items/week ≪ RPM limits; Batch API adds latency and requires billing |
| **`IngestAdapter` signature** | `fetch(source: SourceConfig, *, http_client: httpx.Client) -> list[NormalizedItem]`; raise `FetchError` for caller to catch | Keeps adapter stateless; orchestrator owns retry/logging |
| **`NormalizedItem` shape** | Fields: `source_id`, `external_id`, `canonical_url`, `title`, `publisher`, `published_at: datetime`, `raw_content`, `content_hash` | Matches INGEST-07 + ARCHITECTURE normalizer |
| **`.env` loading** | `python-dotenv` in `pipeline/__init__.py` or CLI entry only; `.env` gitignored; `.env.example` with `GEMINI_API_KEY=` | Matches STACK research-default; fails fast if key missing |
| **Test framework** | `pytest`; fixtures dir for feed XML; `@pytest.mark.live` for real Gemini | Standard Python; D-22 `--week` test is plain integration test |
| **Project layout** | Root `pyproject.toml` with package `pipeline` (matches `python -m pipeline.run` in D-19) | Avoid nested `pipeline/pipeline/` confusion |
| **Items with no parseable date** | Skip item + log warning (do not ingest) | Prevents garbage in week-filtered digest |
| **HTML strip before LLM** | Always strip tags from `raw_content` before token count | Substack feeds are HTML-heavy |

## Project Constraints (from .cursor/rules/)

- GSD workflow: phase work via `/gsd-plan-phase` → `/gsd-execute-phase`; direct edits outside GSD only when user explicitly bypasses.
- Stack locked in `.cursor/rules/gsd.mdc` from STACK.md — do not substitute RSS parser or LLM SDK.
- Core value: readable weekly digest in ~15 minutes — Phase 1 validates per-item TL;DR path only.

## Sources

### Primary (HIGH)
- [feedparser ETag/Modified](https://feedparser.readthedocs.io/en/stable/http-etag.html)
- [feedparser entry.id](https://feedparser.readthedocs.io/en/stable/reference-entry-id.html)
- [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/)
- [Gemini 2.5 Flash-Lite pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- PyPI version check 2026-05-21 (feedparser 6.0.12, google-genai 2.5.0, trafilatura 2.0.0)

### Secondary (MEDIUM)
- [trafilatura evaluation / readability cascade](https://github.com/adbar/trafilatura/blob/master/docs/evaluation.rst)
- `.planning/research/PITFALLS.md` #13, #14, #25
- `.planning/research/ARCHITECTURE.md` — PK strategy, build order items 1–3, 5–6

---

## RESEARCH COMPLETE

- **Use Standard (sync) Gemini API, not Batch**, for Phase 1 — free tier has no Batch pricing; ~30 sequential calls/week is trivial; wrap with tenacity for 429.
- **trafilatura primary, readability-lxml optional fallback** — Apache 2.0, better coverage, already cascades readability internally; keep for Phase 2 HN/blog fetches.
- **Walking skeleton = 1 RSS source → 1 DB upsert → 1 real Gemini summary → 1 HTML file**; defer three-source ingest, `--week` UAT, trafilatura path, and ETag caching to subsequent plans within the phase.
