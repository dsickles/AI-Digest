# Phase 2: Expand Ingestion - Research

**Researched:** 2026-05-22
**Domain:** YouTube + RSS ingestion expansion, per-source failure isolation, in-place HTML degradation
**Confidence:** HIGH (Phase 1 patterns + locked CONTEXT decisions), MEDIUM (youtube-transcript-api exception semantics, SQLite migration wiring)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-23:** Free-first YouTube transcripts via `youtube-transcript-api`; `transcript_status` enum (`ok | pending_local | missing`); local catch-up CLI command
- **D-26:** Top-of-digest pipeline notice under "Updated" timestamp; zero-state hides
- **D-27:** YouTube discovery via `https://www.youtube.com/feeds/videos.xml?channel_id={id}` parsed by feedparser
- **D-28:** Transcript truncation ~6K input tokens; first-4K + last-1K + elision sentinel; `summary_input_truncated` flag
- **D-29:** Two YouTube seed channels (`how-i-ai`, `nate-b-jones`) with verified channel IDs
- **D-25 (project-level):** In-place degradation rendering — remove footer aside; per-card plain-English copy
- **D-33:** Three new RSS sources (`where-your-ed-at`, `bensbites`, `last-week-in-ai`)
- **D-36:** `SourceConfig` Pydantic discriminated union (`RssSource`, `YoutubeSource`)
- **D-39:** Typed error taxonomy in `RunStats.errors`
- **D-40:** Source-health columns on `sources` table
- **D-41:** Empty-feed contract (non-failing, updates `last_success_at`)
- **D-42:** Circuit breaker / retry / per-source timeouts deferred to Phase 5

### Claude's Discretion
- `YoutubeAdapter` class shape (composition vs sibling)
- `transcript_status` column placement (default: `items` table)
- Video content indicator form (D-30)
- Failure-state card copy wording (must stay D-24 plain English)
- Pydantic discriminated-union syntax
- Sanity hard-cap on items-per-feed-parse (~1000 suggested)
- YouTube channel-RSS HTTP behavior (reuse RssAdapter defaults)
- CLI flag name for catch-up (must satisfy D-22 triad)
- Test coverage targets and UAT checklist additions

### Deferred Ideas (OUT OF SCOPE)
- One-click YouTube transcript catch-up button (~4 weeks evaluation)
- Reddit/HN, email→RSS/KTN (v2)
- Dedup, categorization, ranking, Astro dashboard, GHA cron, circuit breaker
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **INGEST-03** | System fetches new uploads from configured YouTube channels and retrieves transcripts where available | D-27 channel RSS + feedparser; D-23 `youtube-transcript-api` v1.2.4 instance API; `YoutubeAdapter` as `IngestAdapter` sibling; video ID from `yt:video:{id}` entry id; transcript text merged into summarize input when `transcript_status=ok` |
| **INGEST-06** | A single failing source does not break the weekly run; failure is recorded | Phase 1 `_ingest` per-source try/except preserved; D-39 extends error dict shape; D-40 persists health; D-41 codifies empty-feed as non-fatal category |
</phase_requirements>

## Summary

Phase 2 extends a working Phase 1 vertical slice (RSS → SQLite → Gemini → plain HTML) along three axes that share the orchestrator and renderer but have different dependency depths. **YouTube ingestion (INGEST-03)** is the largest net-new surface: a discriminated `SourceConfig` union (D-36), additive SQLite columns (`transcript_status`, `summary_input_truncated`, source-health fields), a `YoutubeAdapter` that reuses the RSS HTTP fetch pattern against YouTube's hidden channel Atom feed (D-27), and post-parse transcript fetches via `youtube-transcript-api` 1.2.4 with a three-state lifecycle (D-23). **Failure isolation (INGEST-06)** formalizes what Phase 1 already does informally — per-source try/except in `_ingest` — by adding a typed error taxonomy (D-39), source-health columns written at run finalization (D-40), and an empty-feed contract that records `empty_feed` without failing the run or surfacing reader-facing failure copy (D-41). **Reader surface** is a deliberate rewrite: project-level D-25 supersedes Phase 1 D-05's footer-aside pattern in `pipeline/render/html.py`, adding in-place degraded cards and a top-of-digest aggregate notice (D-26) under the "Updated" timestamp.

MVP planning should treat these as **dependency facts**, not pre-cut slices: (1) D-36 + schema migrations block YouTube persistence and catch-up CLI; (2) `YoutubeAdapter` + summarize input path block INGEST-03 end-to-end; (3) renderer rewrite blocks D-25/D-26 success criteria but can be tested with fixture `DigestCard`s before live YouTube; (4) D-39/D-40/D-41 share the orchestrator finalizer with YouTube health writes; (5) D-33 RSS rows are config-only once the union loader accepts existing `RssSource` rows unchanged; (6) catch-up CLI (D-23) depends on `pending_local` rows existing in SQLite. Any vertical slice that ships a readable digest must thread `run all` through ingest → summarize → render with the expanded source catalog.

**Primary recommendation:** Implement in waves that each land `python -m pipeline.run all` → `out/digest-{week_id}.html`, starting with schema + config union + `YoutubeAdapter` (even if many cards are `pending_local` on first cloud run), then failure-isolation contract + RSS catalog expansion, then renderer rewrite + header notice, then local catch-up CLI with D-22 discoverability.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| YouTube channel discovery (RSS) | **API / Backend** (adapter) | — | Network fetch + parse; no browser |
| Transcript fetch + status lifecycle | **API / Backend** (adapter + store) | LLM pipeline (truncation at summarize) | Adapter owns fetch; summarize owns token cap (D-28) |
| Source config discriminated union | **API / Backend** (`pipeline/config.py`) | — | Validated at CLI startup |
| Per-source failure isolation + health | **API / Backend** (orchestrator + store) | Reporting (`last_run.md`) | Typed errors in `RunStats`; health columns in SQLite |
| In-place degradation + header notice | **CDN / Static** (HTML renderer) | Orchestrator (card state assembly) | Reader surface; no new runtime |
| Local transcript catch-up | **API / Backend** (CLI subcommand/flag) | — | Hidden capability; residential IP recovery |
| RSS catalog expansion (3 feeds) | **API / Backend** (config YAML) | — | Zero adapter code |

## Project Constraints (from `.cursor/rules/`)

- GSD workflow: phase work should flow through `/gsd-plan-phase` → `/gsd-execute-phase`; direct repo edits outside GSD are discouraged unless user bypasses.
- No project-specific Python style guide beyond existing Phase 1 conventions (Ruff py312, structlog, pydantic v2, lazy imports in orchestrator D-20).
- Commit docs when `commit_docs: true` in `.planning/config.json`.

## Standard Stack

### Core (Phase 2 additions)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **feedparser** | 6.0.12 (already pinned) | Parse YouTube channel Atom + RSS | Same dependency as Phase 1; YouTube `feeds/videos.xml` is Atom with `yt:video:` ids [CITED: STACK.md §3] |
| **youtube-transcript-api** | **1.2.4** (new) | Transcript fetch, no API key | Locked in STACK.md §4; v1.x instance API `YouTubeTranscriptApi().fetch(video_id, languages=['en'])` [VERIFIED: PyPI 2026-01-29] |
| **httpx** | 0.28.x (already pinned) | Channel RSS HTTP | Reuse `RssAdapter` UA/timeout/304 pattern |
| **pydantic** | 2.13.x (already pinned) | Discriminated union on `SourceConfig` | D-36; `Annotated[Union[RssSource, YoutubeSource], Field(discriminator="type")]` |
| **SQLite** | stdlib | `transcript_status`, health columns | Phase 1 store; additive ALTER |

### Not in Phase 2

| Avoid | Use Instead | Why |
|-------|-------------|-----|
| **yt-dlp** | Channel RSS + transcript-api | D-27 explicitly excludes yt-dlp for Phase 2 |
| **Paid transcript APIs** | `pending_local` + local catch-up | D-23 free-first |
| **tenacity per-video** (new) | Phase 5 retry policy | D-42 defers backoff; adapter classifies errors |

**Installation:**
```bash
# Add to pyproject.toml dependencies:
# youtube-transcript-api>=1.2.4,<2
uv pip install "youtube-transcript-api>=1.2.4,<2"
```

**Version verification (2026-05-22):**
```bash
pip index versions youtube-transcript-api   # latest 1.2.4
pip index versions feedparser               # 6.0.12 in pyproject
```

## Package Legitimacy Audit

> slopcheck unavailable in research environment — packages verified via PyPI JSON + official GitHub README.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| youtube-transcript-api | PyPI | ~8 yrs (2018→) | High (primary transcript lib) | github.com/jdepoix/youtube-transcript-api | unavailable | Approved — pin 1.2.4 |
| feedparser | PyPI | 20+ yrs | Very high | github.com/kurtmckee/feedparser | n/a (existing) | Already in project |
| pydantic | PyPI | — | Very high | github.com/pydantic/pydantic | n/a (existing) | Already in project |

**Packages removed due to slopcheck [SLOP] verdict:** none  
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
config/sources.yaml (RssSource | YoutubeSource)
        │
        ▼
pipeline.run [ingest|summarize|render|all]  (+ catch-up flag, Phase 2)
        │
        ▼
orchestrator._ingest  ──per-source try/except──▶  adapter.fetch()
        │                    │                         │
        │                    │              ┌──────────┴──────────┐
        │                    │              ▼                     ▼
        │                    │         RssAdapter            YoutubeAdapter
        │                    │         (feed URL)     (channel RSS → transcript API)
        │                    │
        │                    ├──▶ RunStats.errors (D-39 categories)
        │                    └──▶ sources health columns (D-40)
        ▼
store: items (+ transcript_status)  →  item_summaries (+ summary_input_truncated)
        │
        ▼
orchestrator._summarize_week_items  (transcript text when ok; truncation D-28)
        │
        ▼
orchestrator._build_cards  →  DigestCard (+ degradation state, is_video)
        │
        ▼
render_digest  (in-place cards D-25; header notice D-26)
        │
        ▼
out/digest-{week_id}.html
```

### Recommended Project Structure (Phase 2 deltas)

```
pipeline/
├── adapters/
│   ├── base.py          # unchanged protocol
│   ├── rss.py           # unchanged behavior; shared HTTP helpers optionally extracted
│   └── youtube.py       # NEW — channel RSS + transcript lifecycle
├── config.py            # discriminated union (D-36)
├── orchestrator.py      # error taxonomy, health writes, empty-feed, card assembly
├── render/html.py       # REWRITE — D-25/D-26/D-30
├── transcript.py        # optional — truncate + status helpers (planner discretion)
└── run.py               # catch-up flag + --help (D-22)

store/
├── schema.sql           # baseline for fresh DBs
├── migrations/
│   └── 002_expand_ingestion.sql   # ALTER TABLE additive (planner adds)
└── db.py                # apply migrations in init_db; upsert_source health writes

config/sources.yaml      # 3 RSS + 2 YouTube rows (8 enabled total)

tests/
├── fixtures/feeds/youtube_channel.xml
├── test_youtube.py
├── test_render.py       # rewrite assertions for D-25
└── test_config.py       # union + 8 sources
```

### Pattern 1: Discriminated union config (D-36)

**What:** Pydantic v2 union on `type` field; orchestrator dispatches on concrete subtype.  
**When:** Loading `config/sources.yaml` at startup.

```python
# Source: Pydantic v2 docs pattern — Annotated + Field(discriminator="type")
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, field_validator

class RssSource(BaseModel):
    id: str
    type: Literal["rss"]
    url: str
    display_name: str
    tag: str | None = None
    enabled: bool = True

class YoutubeSource(BaseModel):
    id: str
    type: Literal["youtube"]
    channel_id: str
    display_name: str
    tag: str | None = None
    enabled: bool = True

    @field_validator("channel_id")
    @classmethod
    def _channel_id_format(cls, v: str) -> str:
        import re
        if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", v):
            raise ValueError(f"invalid YouTube channel_id: {v!r}")
        return v

    @property
    def feed_url(self) -> str:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={self.channel_id}"

SourceConfig = Annotated[Union[RssSource, YoutubeSource], Field(discriminator="type")]
```

**SQLite `sources.url`:** Store derived feed URL for YouTube at `upsert_source` time (`source.feed_url`) — column stays NOT NULL; YAML never stores it (per D-36).

### Pattern 2: YoutubeAdapter mirrors RssAdapter fetch shell

**What:** HTTP GET channel Atom feed → feedparser → `NormalizedItem` per entry → per-video transcript call.  
**external_id:** Prefer `entry.id` strip `yt:video:` prefix; fallback parse `watch?v=` from link (D-00c).  
**raw_content:** Video description from `media:description` / summary; when transcript `ok`, replace or prepend transcript text for summarize (planner: **replace description with transcript body when ok** keeps `_is_thin` gate meaningful).

```python
# Transcript fetch — youtube-transcript-api 1.2.4 instance API
# Source: https://pypi.org/project/youtube-transcript-api/ [VERIFIED]
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    IpBlocked,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)

api = YouTubeTranscriptApi()
fetched = api.fetch(video_id, languages=["en"])
text = " ".join(snippet.text for snippet in fetched)
```

**Exception → `transcript_status` mapping (planner must codify in adapter):**

| Exception / condition | Status | Notes |
|----------------------|--------|-------|
| Success | `ok` | Persist transcript text |
| `IpBlocked`, `RequestBlocked` | `pending_local` | Cloud IP; catch-up eligible [CITED: library README] |
| `TranscriptsDisabled` on **cloud** weekly run | `pending_local` | Often false positive from IP block [CITED: PITFALLS #7, GitHub #395] |
| `TranscriptsDisabled` after **local** catch-up retry | `missing` | Never retry |
| `VideoUnavailable`, no captions confirmed | `missing` | Title+description only |

### Pattern 3: Transcript truncation at summarize (D-28)

**What:** Before LLM call, if token estimate > ~6000, reshape to first ~4000 + `[... middle content omitted ...]` + last ~1000 tokens; set `summary_input_truncated=True` on `item_summaries`.  
**Don't hand-roll tokenizer:** Use conservative char heuristic (~4 chars/token → 24K chars cap) matching STACK/PITFALLS; tune in config constant.

### Pattern 4: In-place degradation renderer (D-25)

**What:** Every item → `<article class="card">`; body copy reflects state via enum → plain-English template (D-24). Remove `_is_displayable`, `_render_pipeline_notes`, `OMITTED_SECTION_HEADING`, `.pipeline-notes` CSS. Header count = **total** cards.

**Extend `DigestCard` (planner):**
```python
@dataclass(frozen=True)
class DigestCard:
    title: str
    publisher: str
    canonical_url: str
    published_at: datetime
    tldr: str | None
    summary_confidence: str
    source_type: str = "rss"          # "youtube" for D-30 indicator
    transcript_status: str | None = None  # ok | pending_local | missing
    degradation_reason: str | None = None  # pre-rendered plain English for card body
```

### Pattern 5: Typed ingest errors (D-39)

**What:** Extend `RunStats.errors` entries:

```python
{
    "category": "fetch_http_error",  # enum
    "source_id": "bad-feed",
    "phase": "ingest",
    "message": "http error fetching ...",
    "http_status": "404",  # optional
}
```

**Categories:** `fetch_timeout | fetch_http_error | parse_error | empty_feed | adapter_internal`

Map existing `FetchError` + httpx timeouts → categories in `_ingest`. **`empty_feed`:** fetch succeeded, zero items in **week window** after filter (D-41) — not a run failure; still update `last_success_at`.

### Pattern 6: Source-health writes (D-40)

At `_finalize` / post-`_ingest` per source (same SQLite commit as `pipeline_runs`):
- `last_success_at` — fetch completed without `FetchError`/adapter crash
- `last_item_at` — at least one item upserted this run (any publish date)
- `last_error_category` — nullable; set on failure, cleared on success

Phase 1 `sources.last_error` free-text can remain; D-40 adds structured category column.

### Anti-Patterns to Avoid

- **Treating `TranscriptsDisabled` as always `missing` on first ingest** — causes false "no captions" on GHA/cloud (PITFALLS #7).
- **Footer-aside for degraded items** — violates D-25; breaks 12 existing render tests that assert D-05 (must rewrite tests, not adapter).
- **Editing `schema.sql` only without ALTER for existing DBs** — Phase 1 `init_db` runs `CREATE IF NOT EXISTS`; existing `data/aidigest.db` won't gain columns without migration runner.
- **Per-video FetchError aborting channel** — transcript failure is per-item; channel RSS success should still upsert metadata-only items.
- **Empty-feed triggering D-26 notice** — D-41 explicitly excludes empty-feed from reader-facing pipeline notice.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YouTube upload discovery | Custom scraper / yt-dlp | Channel Atom URL + feedparser | D-27; ~15 recent videos sufficient |
| Transcript download | Innertube DIY | youtube-transcript-api 1.2.4 | Maintained; documents IP-block exceptions |
| Config polymorphism | Manual `if type ==` dict parsing | Pydantic discriminated union | D-36; validation at load |
| HTML templating engine | Jinja2 for Phase 2 | Keep string builder + `html.escape` | Phase 1 precedent; Phase 4 replaces |
| Token counting | Exact Gemini tokenizer | Char heuristic + config cap | Good enough for D-28 guardrail |
| Retry/circuit breaker | Per-source tenacity wrapper | Phase 5 (D-42) | Explicitly deferred |

## MVP Vertical-Slice Dependency Facts

Use these to cut 2–4 plans; **do not require this ordering** if a plan bundles dependencies differently.

| Fact | Blocks | Unblocks digest when |
|------|--------|---------------------|
| F1: D-36 union + YAML 8 sources | Adapter dispatch, config tests | RSS-only digest with 6 feeds (no YouTube yet) |
| F2: SQLite migration (`transcript_status`, health cols, `summary_input_truncated`) | YouTube persist, catch-up, health | — |
| F3: `YoutubeAdapter` + registry | INGEST-03 | YouTube cards in digest (incl. pending_local) |
| F4: Summarize uses transcript when `ok`; truncation D-28 | Quality YouTube TL;DRs | Full YouTube success path |
| F5: D-39 + D-40 + D-41 in orchestrator | INGEST-06 formal | `last_run.md` categories; health columns |
| F6: Renderer rewrite D-25 + D-26 + D-30 | Success criteria #5, #3 UX | Reader-correct degradation display |
| F7: Catch-up CLI D-23 + D-22 | Recovery workflow | pending_local → ok after local re-run |

**Natural merge points:** F1+F2+F3 → first YouTube digest; F5+F33 config rows → expanded catalog + isolation; F6 often pairs with F4 for coherent card copy; F7 is last (depends F2+F3).

## Common Pitfalls

### Pitfall 1: TranscriptsDisabled ≠ missing on cloud

**What goes wrong:** Digest permanently marks videos "no captions" when YouTube blocked the IP.  
**Why:** Library raises `TranscriptsDisabled` when caption JSON absent — same symptom as IP block.  
**How to avoid:** Map cloud-block exceptions to `pending_local`; reserve `missing` for local catch-up failure or explicit no-track confirmation.  
**Warning signs:** 100% YouTube items `missing` after GHA run; same videos work locally.  
**Phase:** 2 ingest + catch-up CLI

### Pitfall 2: Schema drift on existing SQLite files

**What goes wrong:** `init_db` no-ops on existing tables; new columns never appear; runtime SQL errors.  
**How to avoid:** Add `store/migrations/002_*.sql` + idempotent `ALTER TABLE ... ADD COLUMN` guarded by pragma check in `init_db`.  
**Phase:** 2 Plan 01 (before adapter)

### Pitfall 3: Renderer test suite encodes superseded D-05

**What goes wrong:** Plan passes ingest tests but render tests still assert footer-aside.  
**How to avoid:** Rewrite `tests/test_render.py` in same plan as `html.py` rewrite; grep for `OMITTED_SECTION_HEADING`.  
**Phase:** 2 renderer plan

### Pitfall 4: Empty-feed vs fetch failure conflation

**What goes wrong:** Silent source conflated with broken source in UI.  
**How to avoid:** D-41: `empty_feed` updates health, no D-26/D-25 failure copy; real failures use other categories.  
**Phase:** 2 orchestrator

### Pitfall 5: RSS feed rot undetected (PITFALLS #6)

**What goes wrong:** New sources added but stale feeds unnoticed until digest thins.  
**How to avoid:** D-40 columns enable Phase 4/5 alerting; Phase 2 writes them correctly on every run.  
**Phase:** 2 orchestrator (write path only)

## Code Examples

### YouTube channel RSS entry parsing

```python
# entry.id == "yt:video:dQw4w9WgXcQ"  [CITED: wprssaggregator.com YouTube RSS format]
video_id = entry.id.split(":")[-1] if entry.get("id", "").startswith("yt:video:") else ""
media = entry.get("media_thumbnail")  # feedparser normalizes media:group
description = entry.get("summary", "") or ""
```

### Shared HTTP fetch (reuse from rss.py)

```python
# pipeline/adapters/rss.py — USER_AGENT, 20s timeout, 304 → []
body, status = _fetch_bytes(youtube_source.feed_url)
feed = feedparser.parse(body)
```

### Pydantic union loader

```python
class SourcesFile(BaseModel):
    sources: list[SourceConfig]

def load_sources(path: Path | None = None) -> list[SourceConfig]:
    ...
    return SourcesFile.model_validate(raw).sources
```

### Week-window empty-feed check (orchestrator)

```python
# After adapter.fetch + upsert, filter items by week_bounds(week_id)
in_window = [i for i in fetched if week_start <= i.published_at <= week_end]
if fetch_succeeded and len(in_window) == 0:
    record_error(category="empty_feed", ...)  # D-41 — continue other sources
```

### Header pipeline notice (D-26)

```python
# Plain English aggregate — hide when zero pending_local and zero fetch failures
# Example: "2 video summaries will fill in when refreshed from a different network."
# Do NOT mention CLI flags (D-24)
```

## State of the Art

| Old (Phase 1) | Current (Phase 2) | Impact |
|---------------|-------------------|--------|
| D-05 footer-aside degradation | D-25 in-place cards | Rewrite renderer + tests |
| `SourceConfig` single shape | Discriminated union | Mechanical YAML wrap for RSS rows |
| `RunStats.errors` free-text only | D-39 `category` field | Extend `last_run.md` lines |
| RSS-only adapters | + `YoutubeAdapter` | New dependency youtube-transcript-api 1.2.4 |
| `get_transcript()` class method (pre-1.0) | `YouTubeTranscriptApi().fetch()` instance API | Use 1.2.x API only [VERIFIED: PyPI README] |

**Deprecated:** STACK.md two-step yt-dlp listing for Phase 2 (superseded by D-27 channel RSS).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `TranscriptsDisabled` on cloud weekly run → `pending_local` not `missing` | Pattern 2 | False "no captions" copy |
| A2 | Derived feed URL stored in SQLite `sources.url` for YouTube | Pattern 1 | upsert_source NOT NULL violation |
| A3 | Transcript text replaces description in `raw_content` when `ok` | Pattern 2 | Summaries based on short descriptions |
| A4 | Char-based ~4 chars/token heuristic acceptable for D-28 | Pattern 3 | Occasional over-limit Gemini calls |
| A5 | Week-window filter for D-41 applied in orchestrator post-fetch | Pattern 5 | empty_feed false positives |

## Open Questions

1. **Extract shared `_fetch_bytes` to `adapters/http.py`?**  
   - What we know: RssAdapter and YoutubeAdapter need identical HTTP behavior.  
   - Recommendation: Optional refactor; duplicate import from rss module acceptable for minimal diff.

2. **Catch-up CLI shape: flag vs subcommand?**  
   - What we know: D-23 placeholder `--only-pending-transcripts`; D-22 requires README + `--help` + UAT.  
   - Recommendation: Flag on `ingest` or `all` that skips non-YouTube sources and only re-fetches `pending_local` — planner picks name.

3. **Confirm seed feed URLs live?**  
   - Locked URLs in D-33/D-29; integration tests should hit real feeds outside sandbox (manual UAT).  
   - Recommendation: Plan includes one live `run ingest` verification task.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | pipeline | ✓ (pyproject) | ≥3.12 | — |
| uv / pip + venv | deps | ✓ | — | pip install |
| pytest + dev extras | validation | ✓ (pyproject) | pytest 9.x | `uv sync --dev` |
| GEMINI_API_KEY | summarize E2E | user-provided | — | Skip LLM in unit tests |
| Network | RSS/YouTube live tests | ✓ | — | Fixture XML for unit tests |
| slopcheck | package audit | ✗ | — | Manual PyPI + GitHub verify |

**Missing dependencies with no fallback:** none for Phase 2 implementation.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥9.0.3 ([VERIFIED: pyproject.toml]) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_youtube.py tests/test_ingest.py -x -q` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INGEST-03 | Channel RSS parses to NormalizedItem + video id | unit | `uv run pytest tests/test_youtube.py::test_youtube_adapter_parses_channel_fixture -x` | ❌ Wave 0 |
| INGEST-03 | Transcript ok → status + text persisted | unit | `uv run pytest tests/test_youtube.py::test_transcript_ok -x` | ❌ Wave 0 |
| INGEST-03 | IpBlocked → pending_local | unit | `uv run pytest tests/test_youtube.py::test_transcript_ip_blocked_pending -x` | ❌ Wave 0 |
| INGEST-06 | One source FetchError; others succeed | unit | `uv run pytest tests/test_ingest.py::test_ingest_isolates_failing_source -x` | ✅ extend for category |
| INGEST-06 | Error entry includes `category` | unit | `uv run pytest tests/test_ingest.py::test_error_taxonomy_category -x` | ❌ Wave 0 |
| INGEST-06 | empty_feed does not fail run | unit | `uv run pytest tests/test_ingest.py::test_empty_feed_non_fatal -x` | ❌ Wave 0 |
| D-36 | Union loads RSS + YouTube YAML | unit | `uv run pytest tests/test_config.py::test_union_loads_mixed_sources -x` | ❌ Wave 0 |
| D-25 | Degraded item renders in `<article>` not aside | unit | `uv run pytest tests/test_render.py::test_degraded_renders_in_place -x` | ❌ rewrite |
| D-26 | Header notice visible when pending; hidden at zero | unit | `uv run pytest tests/test_render.py::test_pipeline_header_notice -x` | ❌ Wave 0 |
| D-40 | Migration adds columns idempotently | unit | `uv run pytest tests/test_store.py::test_phase2_schema_migration -x` | ❌ Wave 0 |
| D-23 | Catch-up flag documented in --help | smoke | `uv run python -m pipeline.run ingest --help \| grep -i pending` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_<module>.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -q`
- **Phase gate:** Full suite green + manual UAT (live ingest, browser digest, catch-up from residential IP)

### Wave 0 Gaps

- [ ] `tests/test_youtube.py` — INGEST-03 adapter + transcript lifecycle
- [ ] `tests/fixtures/feeds/youtube_channel.xml` — offline channel RSS
- [ ] `tests/test_render.py` — rewrite for D-25/D-26 (remove D-05 footer assertions)
- [ ] `tests/test_config.py` — union + 8 source rows
- [ ] `tests/test_ingest.py` — `category` field + empty_feed contract
- [ ] `tests/test_store.py` — additive migration idempotency
- [ ] `store/migrations/002_expand_ingestion.sql` — ALTER columns
- [ ] `pipeline/adapters/youtube.py` — target module
- [ ] `pyproject.toml` — add youtube-transcript-api pin

### Manual UAT (human_verify_mode: end-of-phase)

- [ ] `uv run python -m pipeline.run all` produces digest with Phase 1 RSS + 3 new RSS + YouTube cards
- [ ] Browser: no "Also seen this week" footer; degraded YouTube/RSS items in-place with plain English
- [ ] Header notice appears when pending_local > 0; absent when fully ok
- [ ] README + `--help` document catch-up flag (D-22)
- [ ] Local catch-up converts at least one `pending_local` → `ok` (if cloud run created pending rows)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — personal tool, no auth |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | **yes** | Pydantic union + channel_id regex; `html.escape` on all render strings (existing T-01-02) |
| V6 Cryptography | no | No new crypto |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via RSS/YouTube titles in HTML | Tampering → Spoofing | `html.escape` on all reader strings (Phase 1 pattern) |
| SSRF via malicious source URL | Spoofing | URLs only from checked-in YAML; pydantic http(s) scheme validators |
| Secret leakage in digest | Information disclosure | No transcript API keys; GEMINI only in env (Phase 1) |
| Untrusted XML (feedparser) | DoS | Item cap ~1000/feed (D-38 discretion); 20s HTTP timeout |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/02-expand-ingestion/02-CONTEXT.md` — locked decisions D-23–D-42
- Phase 1 code: `pipeline/adapters/rss.py`, `pipeline/orchestrator.py`, `pipeline/render/html.py`, `store/db.py`
- [PyPI youtube-transcript-api 1.2.4](https://pypi.org/project/youtube-transcript-api/) — API + IP block docs
- `.planning/research/STACK.md` §3, §4, §7
- `.planning/research/PITFALLS.md` #6, #7, #13

### Secondary (MEDIUM confidence)
- [YouTube channel RSS format](https://www.wprssaggregator.com/youtube-rss-feed/) — `yt:video:` entry ids
- [GitHub jdepoix/youtube-transcript-api #395](https://github.com/jdepoix/youtube-transcript-api/issues/395) — TranscriptsDisabled vs IP block
- `.planning/research/ARCHITECTURE.md` — adapter/store boundaries

### Tertiary (LOW — validate in implementation)
- Char/token ratio for D-28 truncation — tune against one long podcast video in UAT

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — feedparser in repo; youtube-transcript-api verified on PyPI; CONTEXT locks versions
- Architecture: **HIGH** — extends Phase 1 adapter registry + orchestrator patterns verbatim
- Pitfalls: **MEDIUM** — transcript exception semantics are operationally noisy; mitigation locked in D-23

**Research date:** 2026-05-22  
**Valid until:** 2026-06-22 (stable stack); 2026-06-08 for youtube-transcript-api behavior (fast-moving)
