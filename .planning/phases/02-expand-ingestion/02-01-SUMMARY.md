---
phase: 02-expand-ingestion
plan: "01"
status: complete
type: execute
wave: 1
requirements:
  - INGEST-03
completed: 2026-05-22
self_check: PASSED
---

# Plan 02-01 — Schema migration + YoutubeAdapter end-to-end

## What shipped

Plan 02-01 delivers the first Phase 2 vertical slice for INGEST-03. After this
plan, `uv run python -m pipeline.run all` ingests three RSS sources plus two
YouTube channels, persists `transcript_status` per item, and renders a digest
that includes YouTube cards alongside RSS cards (renderer polish lands in
plan 02-03 — the cards still render via the Phase 1 path here, just with the
new fields populated).

## Tasks

| Task | Files touched | Commit |
|------|---------------|--------|
| 2-01-01 — Wave 0 (migration runner, dep pin, fixtures) | `pyproject.toml`, `store/schema.sql`, `store/migrations/002_expand_ingestion.sql`, `store/db.py`, `tests/test_store.py`, `tests/fixtures/feeds/youtube_channel.xml`, `uv.lock` | `ba8fd7e` |
| 2-01-02 — Discriminated `SourceConfig` union + two YouTube seed rows | `pipeline/config.py`, `config/sources.yaml`, `tests/test_config.py`, `tests/test_*.py` constructors | `6eae32d` |
| 2-01-03 — YoutubeAdapter + transcript truncation + items.transcript_status | `pipeline/adapters/youtube.py`, `pipeline/orchestrator.py`, `pipeline/llm/summarize.py`, `pipeline/models.py`, `store/db.py`, `tests/test_youtube.py`, `tests/test_pipeline.py` | `4a504e1` |

## Key-files created

- `pipeline/adapters/youtube.py` — `YoutubeAdapter` implementing the
  `IngestAdapter` protocol with injectable transcript fetcher for tests.
- `store/migrations/002_expand_ingestion.sql` — additive DDL for `transcript_status`,
  `summary_input_truncated`, and the three D-40 source-health columns.
- `tests/test_youtube.py` — 7 tests covering channel-RSS parsing, transcript
  lifecycle (`ok` / `pending_local`), adapter registry dispatch, and end-to-end
  `_ingest` write-through.
- `tests/fixtures/feeds/youtube_channel.xml` — offline channel-RSS fixture.

## Decisions honored

- **D-23** — Transcript lifecycle persisted as `transcript_status` on items.
  Cloud-ingest path maps `IpBlocked`, `RequestBlocked`, and `TranscriptsDisabled`
  all to `pending_local`. `missing` is intentionally **never set** here — that
  flip is reserved for the residential catch-up path in plan 02-04.
- **D-27** — Channel discovery via
  `https://www.youtube.com/feeds/videos.xml?channel_id=…` parsed by `feedparser`;
  no `yt-dlp` dependency added.
- **D-28** — `_maybe_truncate_transcript` reshapes inputs over 24 000 chars
  (~6K tokens) into 16K head + 4K tail with an explicit elision sentinel; every
  `SummaryResult` carries `summary_input_truncated` and the
  `item_summaries.summary_input_truncated` column is populated.
- **D-29** — `config/sources.yaml` ships `how-i-ai` (UCRYY7IEbkHLH_ScJCu9eWDQ)
  and `nate-b-jones` (UC0C-17n9iuUQPylguM1d-lQ) with the D-37 tag mapping.
- **D-36** — `SourceConfig` is now `Annotated[Union[RssSource, YoutubeSource],
  Field(discriminator="type")]`. `YoutubeSource.url` aliases `feed_url` so
  `store/db.py` upsert_source stays type-agnostic.
- **D-38** — 1 000-entry feed-parse cap in `YoutubeAdapter` (constant
  `MAX_FEED_ENTRIES`).
- **D-40 (partial)** — Source-health columns (`last_success_at`,
  `last_item_at`, `last_error_category`) land in the migration; orchestrator
  writes them in plan 02-02.
- **D-00c** — YouTube `external_id` uses the `yt:video:{id}` prefix.
- **D-00d** — YoutubeAdapter is a sibling implementation registered in
  `_pick_adapter`; no changes to the `IngestAdapter` protocol.

## Verification

```
uv run pytest tests/test_store.py::test_phase2_schema_migration -x -q   # green
uv run pytest tests/test_config.py::test_union_loads_mixed_sources -x -q  # green
uv run pytest tests/test_youtube.py -x -q                                # 7 green
uv run pytest tests/ -q                                                  # 53 green
uv run ruff check pipeline/ store/ tests/                                # clean
```

E2E `uv run python -m pipeline.run all` was **not** executed in-sandbox (no
real network for the YouTube transcript fetch and GEMINI_API_KEY was not
exercised here); per plan acceptance criteria this is recorded as a manual
UAT in `02-VALIDATION.md` Manual-Only Verifications.

## Self-Check: PASSED

- [x] All tasks executed (3/3)
- [x] Each task committed individually
- [x] All tests green (53/53)
- [x] All ruff checks clean
- [x] D-23/D-27/D-28/D-29/D-36/D-38/D-00c/D-00d satisfied in code or persisted state
- [x] D-40 partial — health columns shipped; orchestrator writes land in plan 02-02

## Deviations

None.

## Handoff to plan 02-02

`items.transcript_status` column exists and is populated for YouTube rows.
Plan 02-02 owns:
- `update_source_health` writes to the D-40 columns from `_ingest`.
- Typed `IngestErrorCategory` taxonomy on `RunStats.errors`.
- Three additional RSS sources (D-33) → 8-source catalog total.

`SUMMARY.md` for plan 02-02 must reflect once 02-02 lands.
