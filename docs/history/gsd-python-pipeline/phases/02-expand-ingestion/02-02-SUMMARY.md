---
phase: 02-expand-ingestion
plan: "02"
status: complete
type: execute
wave: 2
requirements:
  - INGEST-06
completed: 2026-05-22
self_check: PASSED
---

# Plan 02-02 — Typed failure isolation + 8-source catalog

## What shipped

Plan 02-02 completes INGEST-06 (one bad feed cannot break the run) and
populates the D-40 source-health columns that Phase 4 OBS-01 and Phase 5
heartbeat will consume. After this plan, ``config/sources.yaml`` ships the
eight-source target catalog and every ``RunStats.errors`` entry carries a
typed D-39 category.

## Tasks

| Task | Files touched | Commit |
|------|---------------|--------|
| 2-02-01 — Typed ingest error taxonomy + last_run.md surfacing | `pipeline/adapters/base.py`, `pipeline/adapters/rss.py`, `pipeline/adapters/youtube.py`, `pipeline/orchestrator.py`, `pipeline/reporting/last_run.py`, `tests/test_ingest.py` | `bb883c5` |
| 2-02-02 — Source-health writes + empty-feed contract | `store/db.py`, `pipeline/orchestrator.py`, `tests/test_ingest.py` | `77d110a` |
| 2-02-03 — Expand RSS catalog to eight sources | `config/sources.yaml`, `tests/test_config.py` | `174ae06` |

## Key changes

- `pipeline/adapters/base.IngestErrorCategory` — closed five-value Literal.
- `pipeline/adapters/base.FetchError` — accepts ``category`` (default
  ``fetch_http_error``) and optional ``http_status``; RSS + YouTube adapters
  raise with the correct category at the throw site.
- `pipeline/adapters/rss._fetch_bytes` — splits `httpx.TimeoutException` into
  ``fetch_timeout``, `HTTPStatusError` into ``fetch_http_error`` with
  ``http_status``; bozo-parse failures use ``parse_error``.
- `pipeline/orchestrator._ingest` — takes ``week_bounds_iso`` so it can count
  in-window items and emit ``empty_feed`` per D-41. Each iteration ends with
  ``update_source_health`` (D-40).
- `store/db.update_source_health` — selective-column writer; empty string for
  ``last_error_category`` clears to NULL on success.
- `pipeline/reporting/last_run._error_line` — prefers ``category`` and
  ``http_status`` so out/last_run.md reads like
  ``fetch_http_error · ingest · bad-source · http 404 · message``.

## Decisions honored

- **D-39** — Typed error taxonomy: ``category`` populated on every
  RunStats.errors entry; legacy ``error`` key preserved for backward compat.
- **D-40** — `sources.last_success_at`, `last_item_at`, `last_error_category`
  written on every ingest iteration.
- **D-41** — `empty_feed` recorded as non-fatal; `last_success_at` still
  advances; remaining sources continue.
- **D-42** — Explicitly deferred to Phase 5 with an inline docstring note on
  `_ingest`.
- **D-33** — `where-your-ed-at`, `bensbites`, `last-week-in-ai` rows added with
  the locked URLs.
- **D-37** — Tags applied per CONTEXT.
- **D-31** — All eight sources are named-entity publishers (editorial
  principle gate).

## Verification

```
uv run pytest tests/test_ingest.py::test_ingest_isolates_failing_source -x -q   # green
uv run pytest tests/test_ingest.py::test_error_taxonomy_category -x -q          # green
uv run pytest tests/test_ingest.py::test_empty_feed_non_fatal -x -q             # green
uv run pytest tests/test_config.py -x -q                                        # green (8 sources)
uv run pytest tests/ -q                                                         # 58 green
uv run ruff check pipeline/ store/ tests/                                       # clean
```

Live 8-source `uv run python -m pipeline.run all` was **not** executed in
sandbox — recorded as manual UAT per `02-VALIDATION.md`.

## Self-Check: PASSED

- [x] All tasks executed (3/3)
- [x] Each task committed individually
- [x] All tests green (58/58)
- [x] All ruff checks clean
- [x] D-39 / D-40 / D-41 surfaced in code and tests
- [x] D-42 deferral documented in source

## Deviations

The `tests/test_ingest.py::test_error_taxonomy_timeout_category` test verifies
the timeout path by monkeypatching `_fetch_bytes` to raise a `FetchError` with
`category="fetch_timeout"` rather than exercising the real
`httpx.TimeoutException → FetchError` translation. The RSS adapter's mapping
itself is verified by code review of `pipeline/adapters/rss._fetch_bytes`. A
follow-up integration test against `httpx_mock` could exercise the live
mapping if Phase 3 needs the higher confidence.

## Handoff to plan 02-03

`items.transcript_status` and the D-39 error taxonomy are now available for
the renderer rewrite. Plan 02-03 owns:
- `DigestCard` extension with `source_type`, `transcript_status`,
  `degradation_reason` (D-25 in-place cards).
- Removal of Phase 1 D-05 footer aside (`_render_pipeline_notes`,
  `OMITTED_SECTION_HEADING`, `_is_displayable`, `.pipeline-notes` CSS).
- Header `pipeline-notice` (D-26) reflecting pending-local + fetch-failed
  counts.
- YouTube `[video]` glyph (D-30).
