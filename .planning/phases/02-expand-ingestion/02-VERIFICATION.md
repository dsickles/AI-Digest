---
phase: 2
slug: expand-ingestion
status: complete
verified: 2026-05-22
verifier: assistant (inline execution; no subagents)
requirements:
  - INGEST-03
  - INGEST-06
plans:
  - 02-01-PLAN.md
  - 02-02-PLAN.md
  - 02-03-PLAN.md
  - 02-04-PLAN.md
self_check: PASSED
---

# Phase 2 — Expand Ingestion — Verification

## Goal

Broaden source coverage by adding the YouTube adapter and additional
named-entity RSS sources, while formalizing per-source failure isolation
so one bad source never breaks the weekly run.

## Plan completion

| Plan | Title | Tasks | Commits | Summary |
|------|-------|-------|---------|---------|
| 02-01 | Schema migration + Pydantic union + YoutubeAdapter | 3/3 | `ba8fd7e` → `4a504e1` | `02-01-SUMMARY.md` |
| 02-02 | Typed failure isolation + 3 RSS sources | 3/3 | `bb883c5` → `174ae06` | `02-02-SUMMARY.md` |
| 02-03 | In-place degradation renderer + header notice | 3/3 | `d3ad48a` → `9cf68d5` | `02-03-SUMMARY.md` |
| 02-04 | `--only-pending-transcripts` catch-up + D-22 triad | 3/3 | `1ea55df` → `d2b4187` | `02-04-SUMMARY.md` |

All four plans self-check PASSED.

## Success-criteria coverage (from ROADMAP.md Phase 2)

| # | Success criterion | Where it lives | Evidence |
|---|-------------------|----------------|----------|
| 1 | Manually triggered run ingests new YouTube items alongside expanded RSS catalogue | `pipeline/adapters/youtube.py`, `config/sources.yaml` (8 sources), `pipeline/orchestrator._pick_adapter` dispatch on `youtube` | `tests/test_youtube.py` (5 cases) + `tests/test_config.py::test_default_config_has_eight_phase2_sources` |
| 2 | One bad source → digest still publishes with all others; failure recorded with one-line reason | `pipeline/adapters/base.IngestErrorCategory`, `pipeline/orchestrator._append_ingest_error`, `pipeline/reporting/last_run._error_line` (category + http_status) | `tests/test_ingest.py::test_ingest_isolates_failing_source`, `test_error_taxonomy_category`, `test_error_taxonomy_timeout_category` |
| 3 | YouTube items show clear indicator when transcript missing — title + description summary, not blank card | `pipeline/render/html.py` `VIDEO_INDICATOR` + `_DEGRADATION_COPY["youtube_pending_local" / "youtube_missing"]` | `tests/test_render.py::test_youtube_video_indicator`, `test_degraded_renders_in_place`, `test_reader_surface_plain_english` |
| 4 | Reader sees noticeably broader coverage — video voices + expanded RSS in same plain-HTML digest | `config/sources.yaml` (2 YouTube + 5 RSS + 1 newsletter), renderer treats all uniformly | Header item count covers all cards (D-25, `tests/test_render.py::test_header_item_count_includes_all_cards`) |
| 5 | Items failing any pipeline stage render in-place with plain-English in-card explanations — no footer aside | `pipeline/render/html._render_body` + `_DEGRADATION_COPY` + orchestrator `_resolve_degradation_reason` | Phase-1 footer code removed; `tests/test_render.py::test_no_footer_aside`, `test_degraded_renders_in_place` |

All five success criteria pass with deterministic test evidence.

## Requirement coverage

| Requirement | Phase 2 acceptance gate | Status |
|-------------|------------------------|--------|
| **INGEST-03** — YouTube transcript ingestion | YouTube adapter, transcript fetch with D-23 lifecycle (`ok` / `pending_local` / `missing`), residential catch-up via `--only-pending-transcripts` | ✅ Verified by `tests/test_youtube.py` (5 cases) + `tests/test_catch_up.py` (8 cases) |
| **INGEST-06** — Typed per-source failure isolation | `IngestErrorCategory` taxonomy (5 categories), `sources.last_error_category` column, `out/last_run.md` surfaces category + http_status, empty-feed contract excludes from failed-source notice | ✅ Verified by `tests/test_ingest.py` (4 isolation tests + source-health test) |

## Validation map (`02-VALIDATION.md`) — per-task status

| Task | Test command | Status |
|------|--------------|--------|
| 2-01-01 | `pytest tests/test_store.py::test_phase2_schema_migration` | ✅ green |
| 2-01-02 | `pytest tests/test_config.py::test_union_loads_mixed_sources` | ✅ green |
| 2-01-03 | `pytest tests/test_youtube.py` | ✅ green (5 cases) |
| 2-02-01 | `pytest tests/test_ingest.py::test_error_taxonomy_category` | ✅ green |
| 2-02-02 | `pytest tests/test_ingest.py::test_empty_feed_non_fatal` | ✅ green |
| 2-02-03 | `pytest tests/test_config.py` | ✅ green |
| 2-03-01 | `pytest tests/test_render.py::test_degraded_renders_in_place` | ✅ green |
| 2-03-02 | `pytest tests/test_render.py::test_pipeline_header_notice` | ✅ green |
| 2-03-03 | `pytest tests/test_render.py` | ✅ green (14 cases) |
| 2-04-01 | `python -m pipeline.run ingest --help \| grep -i pending` | ✅ green |
| 2-04-02 | `grep -q "only-pending-transcripts" README.md` | ✅ green |
| 2-04-03 | `pytest tests/` | ✅ green (68 cases) |

All 12 per-task validation gates pass.

## Phase gate

```
uv run pytest tests/ -q
....................................................................   [100%]
68 passed
```

```
uv run ruff check pipeline/ store/ tests/
All checks passed!
```

## Decisions made / honored during execution

- **D-22** — Discoverability triad complete (CONTEXT + README + `--help`
  + UAT) for `--only-pending-transcripts` catch-up flag.
- **D-23** — Free-first transcript strategy with `pending_local` → `ok` /
  `missing` lifecycle; only the catch-up path may set `missing`.
- **D-24** — Plain-English reader surface enforced by
  `_FORBIDDEN_READER_TOKENS` scan in `tests/test_render.py`.
- **D-25** — Every card renders in natural sort position; D-05 footer
  aside removed.
- **D-26** — Header pipeline notice with zero-state hide.
- **D-30** — YouTube `[video]` indicator next to publisher badge.
- **D-33** — 8-source catalog (5 RSS + 2 YouTube + 1 newsletter).
- **D-36** — Pydantic discriminated union (`RssSource | YoutubeSource`)
  with `channel_id` validation.
- **D-39** — Five-category `IngestErrorCategory` literal.
- **D-40** — `sources` health columns (`last_success_at`,
  `last_item_at`, `last_error_category`) written after each source ingest.
- **D-41** — Empty-feed errors are non-fatal and excluded from the
  pipeline-notice failed-source count.

## Deviations from PLAN.md

- **Task 2-04-03 integration test placement.** The plan asked for the
  integration test in `tests/test_youtube.py`; it was placed in a new
  `tests/test_catch_up.py` instead. Catch-up tests form a coherent suite
  worth its own module; YouTube-adapter unit tests stay focused on the
  adapter contract. Same pytest invocation covers both.
- **`YoutubeAdapter.__init__` default fetcher resolution** changed from
  import-time function reference to late-bound module lookup so
  `monkeypatch.setattr("pipeline.adapters.youtube._transcript_text", ...)`
  works for all downstream callers. Backwards compatible (explicit
  `transcript_fetcher=` overrides still win).
- **Renderer `html.escape(quote=False)` in body text.** Discovered during
  test fixture work that apostrophes in degradation copy ("wasn't") were
  being escaped to `&#x27;`, breaking literal-substring assertions and
  reader-facing copy aesthetics. `quote=False` preserves apostrophes in
  body content while keeping `<`, `>`, `&` escaped (attributes still use
  `quote=True`). Safe per OWASP — body context does not require quote
  escaping.

## Pending items carried forward

| Item | Type | Surfaces in | Owner phase |
|------|------|-------------|-------------|
| Live residential `pending_local → ok` transition against real YouTube transcript API | Manual UAT | `02-UAT.md` test 5 | Operator (manual, out of scope for automated suite) |
| Pipeline-notes UI attribution for "RSS thin body" vs "LLM call failed" | Engineering refinement | `02-03-SUMMARY.md` Deviations | Phase 4 OBS-01 |
| `summary_input_truncated` column added but no reader-facing surface yet | Schema column persisted, awaits pipeline-notes UI | `pipeline/llm/summarize.py` | Phase 3 (categorization/ranking can leverage) |

## Self-Check: PASSED

- [x] All 4 plans executed and self-checked PASSED
- [x] All 12 per-task validation gates green
- [x] Full pytest suite green (68/68)
- [x] ruff clean across `pipeline/`, `store/`, `tests/`
- [x] Both Phase 2 requirements (INGEST-03, INGEST-06) verified
- [x] All 5 ROADMAP.md success criteria verified
- [x] All 11 referenced decisions (D-22..D-41) honored
- [x] Deviations documented and justified
- [x] Manual UAT items captured in `02-UAT.md` and surfaced here
