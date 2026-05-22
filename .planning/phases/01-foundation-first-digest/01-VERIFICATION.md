---
status: human_needed
phase: 01-foundation-first-digest
verified_at: 2026-05-22T00:10:09Z
must_haves_total: 29
must_haves_verified: 27
must_haves_human: 2
must_haves_gap: 0
requirements_covered: [INGEST-01, INGEST-02, INGEST-07, INGEST-08, PIPELINE-01]
test_count: 41
test_status: passed
---

# Phase 1: Foundation + First Digest Verification Report

**Phase Goal:** Prove the end-to-end path from configured RSS sources to a readable weekly digest — no dedup, no categorization, no dashboard polish  
**Verified:** 2026-05-22T00:10:09Z  
**Status:** human_needed

## Summary

Phase 1 achieves its ROADMAP goal in code: three D-01 RSS sources in `config/sources.yaml`, idempotent `(source_id, external_id)` upsert, per-source failure isolation, hybrid content enrichment with grounding/degraded-summary paths, ISO-week CLI with stage subcommands, plain HTML renderer, structlog + `last_run.md` + `pipeline_runs` observability, and a **41-test green pytest suite** (`uv run pytest -q`). Two plan must-haves and ROADMAP success criterion #1 still require a human with live network + `GEMINI_API_KEY` and a browser — not gaps, because the implementation and hermetic tests are complete.

## ROADMAP Success Criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Manual run on 2–3 RSS/Substack sources → dated weekly digest readable in browser | human_verification | Code: `config/sources.yaml` (3 feeds), `pipeline/run.py` `all` subcommand, `pipeline/render/html.py:155` `digest-{week_id}.html`. Hermetic: `tests/test_pipeline.py::test_run_all_finalizes_pipeline_run`. Live + browser: pending human UAT (sandbox blocks TLS/RSS + Gemini). |
| 2 | Every item shows title, publisher, source link, publication date, 2–4 sentence TL;DR | verified | `pipeline/render/html.py:112-136` card template; `tests/test_render.py::test_all_summarized_cards`, `test_source_badge_bracketed_display_name`, `test_all_anchor_tags_have_rel_noopener`; `pipeline/llm/prompts/summarize_v1.md:33-34` 2–4 sentence rule |
| 3 | Re-running ingestion for same week does not duplicate items | verified | `store/schema.sql:27` `UNIQUE (source_id, external_id)`; `store/db.py:102-109` `ON CONFLICT DO UPDATE`; `tests/test_store.py::test_upsert_idempotent`, `test_upsert_item_is_idempotent` |
| 4 | Summaries flag/degrade when RSS content too thin (no invented facts) | verified | `pipeline/llm/prompts/summarize_v1.md:43-46` thin_content sentinel; `pipeline/llm/summarize.py:190-235` unavailable path; `pipeline/render/html.py:24,118-122` degraded line; `tests/test_summarize.py::test_thin_content_sentinel_returns_unavailable`; `tests/test_render.py::test_degraded_card` |

## Must-Haves by Plan

### Plan 01-01 (Walking Skeleton)

| Claim | Status | Evidence |
|-------|--------|----------|
| `python -m pipeline.run all` exits 0 with GEMINI_API_KEY and produces `out/digest-{week_id}.html` | human_verification | CLI wired in `pipeline/run.py:128-131`; hermetic partial proof in `tests/test_pipeline.py::test_run_all_finalizes_pipeline_run` (mocked adapters/LLM). Full live run requires network + API key outside sandbox. |
| SQLite `data/aidigest.db` contains ≥1 row in `items` after successful run | verified | `tests/test_pipeline.py::test_run_all_finalizes_pipeline_run` (items upserted); `tests/test_store.py` schema + upsert tests |
| `item_summaries` has ≥1 row with `prompt_version` `summarize_v1` | verified | `store/schema.sql:39`; `pipeline/orchestrator.py:244-255`; `tests/test_summarize.py::test_thin_content_persisted_with_unavailable_confidence` |
| HTML digest shows card with title, publisher, date, source link, TL;DR | verified | `tests/test_render.py::test_all_summarized_cards`, `test_source_badge_bracketed_display_name` |
| `config/sources.yaml` defines simon-willison RSS per D-01 | verified | `config/sources.yaml:14-19`; `tests/test_config.py::test_default_config_has_three_d01_sources` |
| Card source links use `target=_blank` `rel=noopener` (D-16) | verified | `pipeline/render/html.py:133`; `tests/test_render.py::test_all_anchor_tags_have_rel_noopener` |

### Plan 01-02 (Three Sources + Idempotency)

| Claim | Status | Evidence |
|-------|--------|----------|
| `config/sources.yaml` lists all three D-01 sources | verified | `config/sources.yaml:14-31`; `tests/test_config.py::test_default_config_has_three_d01_sources` |
| Re-running ingest does not increase row count for duplicate `(source_id, external_id)` | verified | `store/db.py:89-128`; `tests/test_store.py::test_upsert_idempotent` |
| One feed URL failure does not abort other sources | verified | `pipeline/orchestrator.py:98-143`; `tests/test_ingest.py::test_ingest_isolates_failing_source` |
| Digest HTML can contain cards from multiple publishers after `pipeline.run all` | human_verification | Multi-source ingest path in `pipeline/orchestrator.py:91-174`; no hermetic test with three distinct publishers in one HTML file — requires live E2E |
| `items` table has no category column; tag in `sources.yaml` only (D-02) | verified | `store/schema.sql:16-28` (no `category` on `items`); `config/sources.yaml:11` tag on source rows |

### Plan 01-03 (Grounding + Degraded Summaries)

| Claim | Status | Evidence |
|-------|--------|----------|
| Prompt forbids facts not in input; thin input returns sentinel not fabrication (D-04) | verified | `pipeline/llm/prompts/summarize_v1.md:30-46`; `tests/test_summarize.py::test_thin_content_sentinel_returns_unavailable` |
| RSS body under 500 chars triggers trafilatura fetch of `canonical_url` (D-03) | verified | `pipeline/content_enrich.py:18,49-100`; `tests/test_summarize.py::test_prepare_input_text_uses_trafilatura_extract` |
| `item_summaries.summary_confidence` is high, low, or unavailable (D-06) | verified | `store/schema.sql:38`; `pipeline/llm/summarize.py:151-235`; `tests/test_summarize.py::test_success_summary_returns_high_confidence` |
| Degraded items render `[summary unavailable — content too thin]` inline (D-05) | verified | `pipeline/render/html.py:24,118-122`; `tests/test_render.py::test_degraded_card`, `test_mixed_cards_all_render_inline` |
| ROADMAP #4: no invented facts when content thin | verified | Same as above + `tests/test_render.py::test_only_thin_items_still_render_cards` |

### Plan 01-04 (CLI + ISO Week)

| Claim | Status | Evidence |
|-------|--------|----------|
| CLI exposes ingest, summarize, render, all; bare invocation aliases all (D-19) | verified | `pipeline/run.py:57-81,112`; `tests/test_pipeline.py::test_bare_cli_aliases_all_with_week` |
| All subcommands accept `--week YYYY-Www` threaded to orchestrator (D-11) | verified | `pipeline/run.py:37-44,86-91,113-131`; `tests/test_pipeline.py::test_week_override_threads_to_orchestrator` |
| No module below `run.py` calls `datetime.now()` for `week_id` | verified | `week_id` flows as parameter only in orchestrator/render; `datetime.now()` in `pipeline/week.py:18` (current week default), `pipeline/render/html.py:159` (Updated timestamp only), `pipeline/orchestrator.py:72,328` (run timestamps). Grep confirms no week_id derivation from `now()` outside `week.py`. |
| `render` subcommand performs no network and no LLM (D-20) | verified | `pipeline/orchestrator.py:470-520`; `tests/test_pipeline.py::test_render_does_not_call_llm`, `test_render_import_does_not_load_adapters_or_llm` |
| README Manual run documents `--week` with two example invocations (D-12, D-22) | verified | `README.md:108-111` |
| `--help` mentions backfill for `--week` (D-12) | verified | `pipeline/run.py:31-34` `_WEEK_HELP` |
| `week_id` ISO `YYYY-Www`; `parse_week_id` validates; `week_bounds` Monday–Sunday UTC (D-10) | verified | `pipeline/week.py`; `tests/test_week.py` (5 tests including `test_week_bounds_2026_w19_exact`) |

### Plan 01-05 (Observability + Polish)

| Claim | Status | Evidence |
|-------|--------|----------|
| structlog emits key=value logs with source_id, duration_ms, token fields (D-07) | verified | `pipeline/logging_config.py`; `pipeline/orchestrator.py:96-152,207-240`; `tests/test_pipeline.py::test_ingest_logs_include_source_id` |
| Each run overwrites `out/last_run.md` with counts, LLM calls, cost, errors (D-08) | verified | `pipeline/reporting/last_run.py`; `pipeline/orchestrator.py:317-339`; `tests/test_pipeline.py::test_write_last_run_md` |
| `pipeline_runs` populated with finished_at, items_fetched, summaries_written, items_degraded, cost_usd_estimate (D-09) | verified | `store/schema.sql:50-62`; `store/db.py:236`; `tests/test_pipeline.py::test_run_all_finalizes_pipeline_run` |
| HTML header shows AI Digest, Week of MMM D – MMM D YYYY, Updated UTC ISO8601 (D-18) | verified | `pipeline/render/html.py:98-105,186-189`; `tests/test_render.py::test_header_contains_week_of` |
| Cards sorted newest-first; source badge per D-14; inline CSS ~40 lines per D-17 | verified | `pipeline/render/html.py:39-89,157`; `tests/test_render.py::test_cards_sorted_newest_first`, `test_source_badge_bracketed_display_name` |
| Full pytest suite green; README complete for Phase 1 manual workflow | verified | `uv run pytest -q` → 41 passed; `README.md` Manual run + UAT checklist |

## Requirement Coverage

| Req ID | Declaring Plans | Code + Test Evidence |
|--------|-----------------|----------------------|
| INGEST-01 | 01-01, 01-02 | `config/sources.yaml`; `pipeline/config.py` Pydantic schema; `tests/test_config.py` |
| INGEST-02 | 01-01, 01-02 | `pipeline/adapters/rss.py`; `tests/test_ingest.py` (Atom + Substack fixtures) |
| INGEST-07 | 01-01, 01-02 | `store/schema.sql:16-28` columns; `pipeline/models.py` `NormalizedItem`; `tests/test_ingest.py::test_rss_adapter_parses_atom_fixture` |
| INGEST-08 | 01-02 | `store/db.py:102` `ON CONFLICT`; `store/schema.sql:27`; `tests/test_store.py::test_upsert_idempotent` |
| PIPELINE-01 | 01-01, 01-03, 01-04, 01-05 | `pipeline/llm/summarize.py`; `pipeline/llm/prompts/summarize_v1.md`; `tests/test_summarize.py`, `tests/test_render.py` |

## Key-Link Spot Checks

| From | To | Via pattern | Matched? | Where |
|------|-----|-------------|----------|-------|
| `pipeline/adapters/rss.py` | `store/db.py` | `upsert_item` | Yes (indirect) | Adapter returns items; `pipeline/orchestrator.py:157` calls `upsert_item` |
| `pipeline/llm/summarize.py` | `store/db.py` | `item_summaries` | Yes | `pipeline/orchestrator.py:244` `insert_item_summary` |
| `pipeline/render/html.py` | `out/digest-*.html` | `digest-.*\.html` | Yes | `pipeline/render/html.py:155` |
| `pipeline/orchestrator.py` | `pipeline/adapters/rss.py` | `except.*FetchError\|except.*Exception` | Yes | `pipeline/orchestrator.py:102,123` |
| `store/db.py` | `items` | `UNIQUE \(source_id, external_id\)` | Yes | `store/schema.sql:27`; `store/db.py:102` |
| `pipeline/content_enrich.py` | `pipeline/llm/summarize.py` | `trafilatura\.extract` | Yes | `pipeline/content_enrich.py:100`; imported via `prepare_input_text` in `summarize.py:23` |
| `pipeline/llm/summarize.py` | `pipeline/render/html.py` | `summary unavailable` | Yes | `pipeline/render/html.py:24` `DEGRADED_SUMMARY_LINE` |
| `pipeline/run.py` | `pipeline/orchestrator.py` | `run_ingest\|run_summarize\|run_render\|run_all` | Yes | `pipeline/run.py:117-131` |
| `pipeline/orchestrator.py` | `pipeline/render/html.py` | render must not import adapters | Yes | `pipeline/render/html.py` has no adapter/LLM imports; `tests/test_pipeline.py::test_render_import_does_not_load_adapters_or_llm` |
| `pipeline/orchestrator.py` | `pipeline_runs` | `UPDATE pipeline_runs` | Yes | `store/db.py:236` `finalize_pipeline_run`; called from `pipeline/orchestrator.py:350` |
| `pipeline/orchestrator.py` | `out/last_run.md` | `last_run\.md` | Yes | `pipeline/orchestrator.py:323` `write_last_run_md`; `pipeline/reporting/last_run.py:12` |

## Human Verification Items

1. **Live three-feed E2E:** With `GEMINI_API_KEY` set, run `uv run python -m pipeline.run all` against the three configured feeds. Confirm exit 0, `out/digest-YYYY-Www.html` exists, and SQLite has items + `summarize_v1` summaries.
2. **Browser readability:** Open `out/digest-*.html` in a browser; confirm dark theme, ~720px width, Week-of header, source badges, TL;DR prose, and links open in a new tab.
3. **Multi-publisher digest:** After live E2E, confirm the HTML contains cards from at least two of the three publishers (Simon Willison, One Useful Thing, Import AI).
4. **Live backfill smoke:** Run `uv run python -m pipeline.run all --week 2026-W19`; confirm `out/digest-2026-W19.html` and header "Week of May 4 – May 10, 2026".
5. **Visual grounding sanity:** Spot-check 2–3 real TL;DRs against source articles — no invented facts; thin posts show degraded line instead of fabrication.

## Gaps

*(none — all code paths present; remaining items are human/live-env verification only)*

## Final Verdict

**Status: `human_needed`** — Phase 1 implementation is complete and **41/41 tests pass**. All five requirement IDs are covered in declared plans with matching code and tests. ROADMAP criteria #2–#4 are verified in code. Criterion #1 and two plan must-haves (live full pipeline + multi-publisher browser digest) require human confirmation with live RSS and Gemini outside the TLS-intercepted sandbox; these are not implementation gaps.

---

_Verified: 2026-05-22T00:10:09Z_  
_Verifier: goal-backward phase verification (Phase 1)_
