# Phase 2: Expand Ingestion - Pattern Map

**Mapped:** 2026-05-22
**Files analyzed:** 16
**Analogs found:** 15 / 16

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `pipeline/adapters/youtube.py` | adapter | request-response + per-item transform | `pipeline/adapters/rss.py` | exact |
| `store/migrations/002_expand_ingestion.sql` | migration | batch (DDL) | `store/schema.sql` | partial (no migration runner yet) |
| `tests/test_youtube.py` | test | — | `tests/test_ingest.py` | exact |
| `tests/fixtures/feeds/youtube_channel.xml` | fixture | file-I/O | `tests/fixtures/feeds/simon_atom.xml` | exact |
| `tests/test_render.py` | test | — | `tests/test_render.py` (rewrite in place) | exact |
| `tests/test_config.py` | test | — | `tests/test_config.py` | exact |
| `tests/test_ingest.py` | test | — | `tests/test_ingest.py` | exact |
| `tests/test_store.py` | test | — | `tests/test_store.py` | exact |
| `pipeline/config.py` | config | transform (YAML → validated models) | `pipeline/config.py` | exact |
| `pipeline/orchestrator.py` | orchestrator | event-driven (per-source ingest loop) | `pipeline/orchestrator.py` | exact |
| `pipeline/render/html.py` | render | transform (DigestCard → HTML string) | `pipeline/render/html.py` | exact (superseded behavior) |
| `pipeline/reporting/last_run.py` | utility | transform (RunSummary → markdown) | `pipeline/reporting/last_run.py` | exact |
| `pipeline/models.py` | model | transform | `pipeline/models.py` | exact (likely minimal change) |
| `store/db.py` | store | CRUD + batch DDL | `store/db.py` + `store/schema.sql` | exact |
| `config/sources.yaml` | config | file-I/O | `config/sources.yaml` | exact |
| `pyproject.toml` | config | — | `pyproject.toml` | exact |

## Pattern Assignments

### `pipeline/adapters/youtube.py` (adapter, request-response + per-item transform)

**Analog:** `pipeline/adapters/rss.py`

**Imports + module shape** (lines 9–26, 91–98):

```python
from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

import feedparser
import httpx
import structlog

from pipeline.adapters.base import FetchError, IngestAdapter
from pipeline.config import SourceConfig
from pipeline.models import NormalizedItem

logger = structlog.get_logger(__name__)

USER_AGENT = "aidigest/0.1 (+https://github.com/dan-sickles/aidigest)"
HTTP_TIMEOUT_SECONDS = 20.0
```

```python
class RssAdapter(IngestAdapter):
    """Fetch + normalize an RSS or Atom feed into ``NormalizedItem``s."""

    last_http_status: int | None = None

    def fetch(self, source: SourceConfig) -> list[NormalizedItem]:
        log = logger.bind(source_id=source.id, url=source.url)
        log.info("rss.fetch.start")
```

**HTTP fetch + 304 handling** (lines 67–88, 100–104):

```python
def _fetch_bytes(url: str) -> tuple[bytes, int]:
    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": accept_header},
            timeout=HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            response = client.get(url)
            if response.status_code == 304:
                return b"", 304
            response.raise_for_status()
            return response.content, response.status_code
    except httpx.HTTPError as exc:
        raise FetchError(f"http error fetching {url}: {exc}") from exc
```

**Entry loop → NormalizedItem.build** (lines 119–150):

```python
        for entry in feed.entries:
            published_at = _extract_published(entry)
            if published_at is None:
                skipped_no_date += 1
                continue
            canonical_url = entry.get("link") or ""
            external_id = _derive_external_id(entry, canonical_url, published_day)
            body_html = _extract_body(entry)
            item = NormalizedItem.build(
                source_id=source.id,
                external_id=external_id,
                canonical_url=canonical_url,
                title=title,
                publisher=feed_title or source.display_name,
                published_at=published_at,
                raw_content_html=body_html,
            )
            items.append(item)
```

**Pattern notes:**
- **Copy verbatim:** module docstring style, `USER_AGENT` / `HTTP_TIMEOUT_SECONDS`, `_fetch_bytes` (import from `rss.py` or duplicate), feedparser bozo guard, structlog event names (`*.fetch.start`, `*.fetch.complete`), `last_http_status`, per-entry skip-on-missing-date/link, `NormalizedItem.build`.
- **Diverge:** accept `YoutubeSource` (use `source.feed_url` property, not `source.url`); derive `external_id` from `yt:video:` entry id prefix; **post-parse per-video** `youtube-transcript-api` call; map exceptions → `transcript_status` (`ok` / `pending_local` / `missing`); transcript failure must **not** abort channel RSS success — upsert metadata-only items; when transcript `ok`, replace description in `raw_content` before `NormalizedItem.build`; persist `transcript_status` via store (adapter returns items + status side channel or extended upsert — planner decides). Reuse `_extract_published`, optionally `_fetch_bytes` from rss module.

---

### `store/migrations/002_expand_ingestion.sql` (migration, batch DDL)

**Analog:** `store/schema.sql` (column definitions + naming conventions)

**Baseline column patterns** (lines 3–14, 16–28, 33–46):

```sql
CREATE TABLE IF NOT EXISTS sources (
    source_id       TEXT PRIMARY KEY,
    type            TEXT NOT NULL,
    url             TEXT NOT NULL,
    ...
    last_error      TEXT
);

CREATE TABLE IF NOT EXISTS items (
    item_id         TEXT PRIMARY KEY,
    ...
    content_hash    TEXT NOT NULL,
    ingested_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (source_id, external_id)
);

CREATE TABLE IF NOT EXISTS item_summaries (
    ...
    cost_usd_estimate   REAL,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
```

**Pattern notes:**
- **Copy verbatim:** `TEXT` / `INTEGER` types, ISO timestamp column naming (`last_*_at`), nullable health fields mirror `last_error` nullability.
- **Diverge:** file is **additive ALTER only** — no `CREATE TABLE`. Phase 2 columns per RESEARCH:
  - `sources`: `last_success_at`, `last_item_at`, `last_error_category`
  - `items`: `transcript_status` (default planner: `items` table)
  - `item_summaries`: `summary_input_truncated` (INTEGER 0/1)
- **No Phase 1 migration analog exists** — runner logic lands in `store/db.py` (see below). SQL should use idempotent `ALTER TABLE ... ADD COLUMN` guarded by pragma in Python, not bare rerunnable ALTER (SQLite lacks `IF NOT EXISTS` on columns).

---

### `store/db.py` (store, CRUD + batch DDL)

**Analog:** `store/db.py` + `store/schema.sql`

**init_db baseline apply** (lines 48–58):

```python
def init_db(db_path: Path | str | None = None) -> Path:
    """Apply ``store/schema.sql`` to the target DB, creating it if needed.

    Idempotent — safe to call on every run.
    """
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(path) as conn:
        conn.executescript(schema_sql)
        conn.commit()
    return path
```

**upsert_source mirror pattern** (lines 61–86):

```python
def upsert_source(conn: sqlite3.Connection, source: SourceConfig) -> None:
    conn.execute(
        """
        INSERT INTO sources (source_id, type, url, display_name, tag, enabled)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            type         = excluded.type,
            url          = excluded.url,
            ...
        """,
        (source.id, source.type, source.url, ...),
    )
```

**upsert_item ON CONFLICT** (lines 89–128):

```python
def upsert_item(conn: sqlite3.Connection, item: NormalizedItem) -> str:
    conn.execute(
        """
        INSERT INTO items (...)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, external_id) DO UPDATE SET
            canonical_url = excluded.canonical_url,
            ...
            ingested_at   = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        """,
        (...),
    )
```

**Pattern notes:**
- **Copy verbatim:** `connect()` context manager, `_utcnow_iso()`, `executescript` idempotence comment, upsert conflict style.
- **Diverge:** extend `init_db` to run `store/migrations/002_expand_ingestion.sql` after baseline schema (pragma-guarded column adds); extend `upsert_source` to accept YouTube derived URL (`source.feed_url` when `YoutubeSource`); add `transcript_status` to `upsert_item` INSERT/UPDATE; add `update_source_health(conn, source_id, *, last_success_at, last_item_at, last_error_category)` called from orchestrator finalizer; extend `insert_item_summary` with `summary_input_truncated`. Update `store/schema.sql` in parallel for fresh DBs (migration + schema stay in sync).

---

### `pipeline/config.py` (config, transform)

**Analog:** `pipeline/config.py`

**Single-model + validators + loader** (lines 17–62):

```python
SourceType = Literal["rss"]

class SourceConfig(BaseModel):
    id: str = Field(min_length=1)
    type: SourceType
    url: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    tag: str | None = None
    enabled: bool = True

    @field_validator("id")
    @classmethod
    def _id_is_kebab(cls, value: str) -> str:
        ...

class SourcesFile(BaseModel):
    sources: list[SourceConfig]

def load_sources(path: Path | str | None = None) -> list[SourceConfig]:
    ...
    parsed = SourcesFile.model_validate(raw)
    return parsed.sources
```

**Pattern notes:**
- **Copy verbatim:** `DEFAULT_SOURCES_PATH`, `_id_is_kebab`, `_url_has_scheme` on `RssSource`, `SourcesFile` wrapper, `load_sources` / `enabled_sources` signatures and error messages.
- **Diverge:** split into `RssSource` + `YoutubeSource`; `SourceConfig = Annotated[Union[RssSource, YoutubeSource], Field(discriminator="type")]`; grow `SourceType` to `"rss" | "youtube"`; add `channel_id` validator on `YoutubeSource`; add `@property feed_url` on `YoutubeSource`; keep return type `list[SourceConfig]` (union alias). Existing Phase 1 YAML rows parse unchanged as `RssSource`.

---

### `pipeline/orchestrator.py` (orchestrator, event-driven)

**Analog:** `pipeline/orchestrator.py`

**Adapter registry** (lines 75–81):

```python
def _pick_adapter(source_type: str):
    """One-line registry. Phase 2 grows this dict."""
    from pipeline.adapters.rss import RssAdapter

    if source_type == "rss":
        return RssAdapter()
    raise ValueError(f"no adapter registered for source type {source_type!r}")
```

**Per-source try/except + RunStats.errors** (lines 84–143):

```python
def _ingest(sources, conn, log, stats: RunStats) -> list[NormalizedItem]:
    from pipeline.adapters.base import FetchError

    for source in sources:
        upsert_source(conn, source)
        ...
        try:
            adapter = _pick_adapter(source.type)
            fetched = adapter.fetch(source)
            http_status = getattr(adapter, "last_http_status", None)
        except FetchError as exc:
            ...
            stats.errors.append(
                {
                    "phase": "ingest",
                    "source_id": source.id,
                    "error": err_msg,
                }
            )
            continue
```

**Finalize + pipeline_runs** (lines 342–360):

```python
def _finalize(conn, run_id: str, stats: RunStats, *, phase: str) -> None:
    status = "success" if not stats.errors else "partial"
    finalize_pipeline_run(
        conn,
        run_id,
        status=status,
        ...
        errors_json=json.dumps(stats.errors),
    )
    conn.commit()
    _write_last_run(stats, status=status)
```

**Pattern notes:**
- **Copy verbatim:** lazy adapter import in `_pick_adapter`, per-source isolation control flow, `RunStats` dataclass shape, `_finalize` commit ordering, lazy LLM import boundary (D-20).
- **Diverge:** `_pick_adapter` switches on union subtype (`source.type` still works) — add `YoutubeAdapter`; extend `stats.errors` dicts with `category`, `message`, optional `http_status` (D-39); map `FetchError` / httpx timeout → category enum; after successful fetch, apply week-window filter → record `empty_feed` without `continue` abort (D-41); write D-40 health columns per source in same commit as `_finalize`; extend `_build_cards` / `DigestCard` with `source_type`, `transcript_status`, `degradation_reason`, pipeline notice inputs for renderer.

---

### `pipeline/render/html.py` (render, transform)

**Analog:** `pipeline/render/html.py` (Phase 1 D-05 — **behavior to remove**)

**DigestCard + card render (keep structure)** (lines 37–46, 152–169):

```python
@dataclass(frozen=True)
class DigestCard:
    title: str
    publisher: str
    canonical_url: str
    published_at: datetime
    tldr: str | None
    summary_confidence: str  # 'high' | 'low' | 'unavailable'
```

```python
def _render_card(card: DigestCard) -> str:
    title_safe = html.escape(card.title)
    badge_safe = html.escape(f"[{card.publisher}]")
    ...
    return (
        '<article class="card">'
        ...
        f"{tldr_html}"
        "</article>"
    )
```

**Phase 1 footer pattern (DELETE)** (lines 147–150, 180–198, 221–223):

```python
def _is_displayable(card: DigestCard) -> bool:
    return card.tldr is not None and card.summary_confidence != "unavailable"

def _render_pipeline_notes(omitted: list[DigestCard]) -> str:
    ...
    return (
        '<aside class="pipeline-notes" aria-label="Pipeline notes">'
        ...
        "</aside>"
    )
```

**Pattern notes:**
- **Copy verbatim:** `html.escape` on all reader strings (T-01-02), `_CSS` card/header tokens, `_format_week_header` / `_format_updated`, `<article class="card">` outer shell, `rel="noopener"` on links, structlog `render_complete`.
- **Diverge (D-25):** remove `_is_displayable`, `_render_pipeline_notes`, `OMITTED_SECTION_HEADING`, `.pipeline-notes` CSS, displayed-vs-omitted partition; **every** card renders as `<article>`; degraded body copy from `degradation_reason` or state enum templates (plain English per D-24); header item count = **total** cards.
- **Diverge (D-26):** add pipeline notice `<p class="pipeline-notice">` under `.updated` in header; hide at zero-state; exclude `empty_feed` from notice aggregation (D-41).
- **Diverge (D-30):** small video indicator on source badge when `source_type == "youtube"`.

---

### `pipeline/reporting/last_run.py` (utility, transform)

**Analog:** `pipeline/reporting/last_run.py`

**Error line formatter** (lines 40–47):

```python
def _error_line(err: dict[str, str]) -> str:
    parts = [err.get("phase", "unknown")]
    if err.get("source_id"):
        parts.append(err["source_id"])
    if err.get("item_id"):
        parts.append(err["item_id"][:8])
    parts.append(err.get("error", "unknown error"))
    return " · ".join(parts)
```

**Pattern notes:**
- **Copy verbatim:** `RunSummary` dataclass, markdown section structure, `_fmt_ts`, no secrets in output (T-01-01).
- **Diverge:** render D-39 `category` in human-readable form on technical surface (e.g. `fetch_http_error · bad-source · message`); prefer `message` field over legacy `error` key when present; optional `http_status` suffix. Keep plain dict shape — no new dataclass required if orchestrator populates consistently.

---

### `pipeline/models.py` (model, transform)

**Analog:** `pipeline/models.py`

**NormalizedItem contract** (lines 34–89):

```python
class NormalizedItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    canonical_url: str = Field(min_length=1)
    ...
    raw_content: str = ""
    content_hash: str = Field(min_length=64, max_length=64)

    @classmethod
    def build(cls, *, source_id: str, external_id: str, ..., raw_content_html: str) -> NormalizedItem:
        text = strip_html(raw_content_html)
        return cls(..., raw_content=text, content_hash=hash_content(text))
```

**Pattern notes:**
- **Copy verbatim:** `NormalizedItem` fields and validators unchanged per CONTEXT (YouTube uses same shape).
- **Diverge (planner discretion):** `transcript_status` likely **not** on `NormalizedItem` — store column set at `upsert_item` time from adapter metadata; if cleaner, add optional `transcript_status: str | None = None` on a wrapper or extend `build` kwargs — default stays items table column via db layer.

---

### `config/sources.yaml` (config, file-I/O)

**Analog:** `config/sources.yaml`

**Row shape** (lines 13–31):

```yaml
sources:
  - id: simon-willison
    type: rss
    url: https://simonwillison.net/atom/everything/
    display_name: Simon Willison
    tag: technical
    enabled: true
```

**Pattern notes:**
- **Copy verbatim:** comment header style, kebab-case `id`, `display_name` / `tag` / `enabled` fields, file order = fetch order.
- **Diverge:** add 3 RSS rows (D-33) with same `type: rss` shape; add 2 YouTube rows with `type: youtube`, `channel_id` (no `url` in YAML); update header comment (drop stale Reddit/HN mention). Total 8 enabled sources; tags per D-37.

---

### `pyproject.toml` (config)

**Analog:** `pyproject.toml`

**Dependency pin pattern** (lines 7–19):

```toml
dependencies = [
    "feedparser>=6.0.12,<7",
    "httpx>=0.28.1,<0.29",
    ...
]
```

**Pattern notes:**
- **Copy verbatim:** semver lower pin + major upper bound, same section ordering.
- **Diverge:** add `"youtube-transcript-api>=1.2.4,<2"` after feedparser block (RESEARCH verified version).

---

### `tests/test_youtube.py` (test)

**Analog:** `tests/test_ingest.py`

**Fixture fetch via monkeypatch** (lines 19–39, 42–52):

```python
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "feeds"

def _fetch_fixture(name: str, monkeypatch: pytest.MonkeyPatch) -> list[NormalizedItem]:
    body = (FIXTURES / name).read_bytes()
    monkeypatch.setattr(
        "pipeline.adapters.rss._fetch_bytes",
        lambda _url: (body, 200),
    )
    return RssAdapter().fetch(_source("fixture-source", url=f"https://example.com/{name}"))
```

**Pattern notes:**
- **Copy verbatim:** `FIXTURES` path constant, monkeypatch `_fetch_bytes`, assert `NormalizedItem` field presence, 304 empty test shape.
- **Diverge:** target `YoutubeAdapter`; monkeypatch `youtube_transcript_api.YouTubeTranscriptApi.fetch` for status lifecycle tests; assert `yt:video:` external_id extraction; test `IpBlocked` → `pending_local`, `TranscriptsDisabled` cloud → `pending_local`, success → `ok`. Use `YoutubeSource` from union config helper.

---

### `tests/fixtures/feeds/youtube_channel.xml` (fixture)

**Analog:** `tests/fixtures/feeds/simon_atom.xml`

**Minimal Atom entry** (lines 1–11):

```xml
<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Simon Willison's Weblog</title>
  <entry>
    <id>tag:simonwillison.net,2026:/2026/May/18/test/</id>
    <title>Fixture Atom Entry</title>
    <link href="https://simonwillison.net/2026/May/18/test/" rel="alternate"/>
    <published>2026-05-18T12:00:00Z</published>
```

**Pattern notes:**
- **Copy verbatim:** small single-entry feed, fixed UTC date, inline HTML description.
- **Diverge:** use YouTube channel Atom namespace — `xmlns:yt="http://www.youtube.com/xml/schemas/2015"`, entry id `yt:video:dQw4w9WgXcQ`, link to `watch?v=`, `media:group` / summary for description. One entry sufficient for unit parse test.

---

### `tests/test_render.py` (test — full rewrite)

**Analog:** `tests/test_render.py` (invert assertions)

**Helper + header test to keep** (lines 23–57):

```python
def _card(*, title: str = "Test Title", ..., confidence: str = "high", ...) -> DigestCard:
    return DigestCard(...)

def test_header_contains_week_of(tmp_path: Path) -> None:
    out = render_digest(week_id="2026-W19", ...)
    body = out.read_text(encoding="utf-8")
    assert "Week of" in body
    assert "Updated 20" in body
```

**Footer assertions to invert** (lines 117–136):

```python
def test_degraded_item_goes_to_footer_not_article(tmp_path: Path) -> None:
    ...
    assert body.count('<article class="card">') == 0
    assert OMITTED_SECTION_HEADING in body
```

**Pattern notes:**
- **Keep:** `_card` helper pattern, `tmp_path` render_digest calls, D-16 `rel="noopener"` test, D-18 week header, sort order, XSS escape test (adapt for in-card degraded copy).
- **Replace:** footer/aside tests → `test_degraded_renders_in_place` (degraded item **is** `<article>`, no `pipeline-notes`); `test_pipeline_header_notice` (D-26 visible/hidden); header count = total not displayed-only; remove imports of `OMITTED_SECTION_HEADING`, `DEGRADED_SUMMARY_LINE` when constants deleted.

---

### `tests/test_config.py` (test — extend)

**Analog:** `tests/test_config.py`

**Default config load test** (lines 12–32):

```python
def test_default_config_has_three_d01_sources() -> None:
    sources = load_sources()
    assert len(sources) == 3
    ids = {s.id for s in sources}
    assert ids == {"simon-willison", "one-useful-thing", "import-ai"}
```

**Invalid URL rejection** (lines 35–43):

```python
def test_invalid_url_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        load_sources(bad)
```

**Pattern notes:**
- **Copy verbatim:** `tmp_path` YAML fixtures, `ValidationError` pattern, `enabled_sources` order test.
- **Diverge:** update default count 3 → 8; add `test_union_loads_mixed_sources` with inline YAML containing `type: youtube` + `channel_id`; add invalid `channel_id` rejection test; use `isinstance(s, RssSource)` / `YoutubeSource` checks.

---

### `tests/test_ingest.py` (test — extend)

**Analog:** `tests/test_ingest.py`

**Per-source isolation** (lines 85–136):

```python
def test_ingest_isolates_failing_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ...
    monkeypatch.setattr("pipeline.orchestrator._pick_adapter", _fake_pick)
    items = _ingest([good_source, bad_source], conn, MagicMock(), stats)
    assert len(items) == 1
    assert len(stats.errors) == 1
    assert stats.errors[0]["source_id"] == "bad-source"
```

**Pattern notes:**
- **Copy verbatim:** `_source()` helper (update for union types), `_ingest` direct call with `init_db` + `connect`, fake adapter via `_pick_adapter` monkeypatch.
- **Diverge:** add `test_error_taxonomy_category` asserting `category` key; add `test_empty_feed_non_fatal` — successful fetch, zero in-window items, run continues, `category=empty_feed`, no run failure.

---

### `tests/test_store.py` (test — extend)

**Analog:** `tests/test_store.py`

**Schema + idempotence** (lines 36–63):

```python
def test_apply_schema_creates_items_table(apply_schema: Path) -> None:
    expected = {"sources", "items", "item_summaries", "pipeline_runs"}
    ...

def test_upsert_idempotent(apply_schema: Path) -> None:
    with connect(apply_schema) as conn:
        upsert_source(conn, source)
        first_id = upsert_item(conn, item)
        second_id = upsert_item(conn, item)
```

**Pattern notes:**
- **Copy verbatim:** `apply_schema` fixture from `conftest.py`, `_make_source` / `_make_item` helpers, assert single row after duplicate upsert.
- **Diverge:** add `test_phase2_schema_migration` — call `init_db` twice on same DB, `PRAGMA table_info(sources/items/item_summaries)` confirms new columns exist; second `init_db` does not error (idempotent migration).

---

## Shared Patterns

### IngestAdapter protocol + FetchError
**Source:** `pipeline/adapters/base.py`  
**Apply to:** `youtube.py`, orchestrator error mapping

```python
class FetchError(Exception):
    """Raised by an adapter when a fetch fails non-recoverably."""

@runtime_checkable
class IngestAdapter(Protocol):
    def fetch(self, source: SourceConfig) -> list[NormalizedItem]:
        ...
```

Channel-level failures → `FetchError` → D-39 category. Per-video transcript failures → **not** `FetchError`.

### Per-source isolation in orchestrator
**Source:** `pipeline/orchestrator._ingest`  
**Apply to:** all adapters including YouTube

```python
        try:
            adapter = _pick_adapter(source.type)
            fetched = adapter.fetch(source)
        except FetchError as exc:
            ...
            continue
```

### html.escape on reader surface
**Source:** `pipeline/render/html.py` `_render_card`  
**Apply to:** all new degradation copy + D-26 header notice

```python
title_safe = html.escape(card.title)
tldr_html = f'<p class="card-tldr">{html.escape(card.tldr or "")}</p>'
```

### pytest fixtures for SQLite
**Source:** `tests/conftest.py`  
**Apply to:** `test_store.py`, extended ingest tests

```python
@pytest.fixture
def apply_schema(temp_sqlite_path: Path) -> Path:
    from store.db import init_db
    init_db(temp_sqlite_path)
    return temp_sqlite_path
```

### Technical vs reader language split
**Source:** `pipeline/reporting/last_run.py` vs `pipeline/render/html.py`  
**Apply to:** D-39 categories in `last_run.md`; plain English only in HTML (D-24).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| *(none)* | — | — | All Phase 2 files map to Phase 1 shipped code |

**Note:** `store/migrations/002_expand_ingestion.sql` has **partial** analog only — Phase 1 uses `schema.sql` + `init_db` without numbered migrations. Executor must **invent** migration runner pattern on top of `init_db`, using `schema.sql` column defs as the naming/type reference.

---

## Metadata

**Analog search scope:** `pipeline/`, `store/`, `tests/`, `config/`, `pyproject.toml`  
**Files scanned:** 28 Python/YAML/SQL/test files  
**Pattern extraction date:** 2026-05-22
