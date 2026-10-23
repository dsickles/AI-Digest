---
phase: 2
slug: expand-ingestion
status: complete
verified: 2026-05-22
verified_amended: 2026-05-22 (post-UAT corrections)
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
locked_directives_established:
  - LOCKED-01  # footer-aside routing — supersedes original Plan 02-03 D-25
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
| 3 | YouTube items show clear indicator when transcript missing — title + description as outbound footer link | `pipeline/render/html.py` `VIDEO_INDICATOR` + footer aside routing for `youtube_pending_local` / `youtube_missing` items | `tests/test_render.py::test_youtube_pending_local_goes_to_footer`, `tests/test_render_e2e.py::test_youtube_video_indicator_end_to_end` |
| 4 | Reader sees noticeably broader coverage — video voices + expanded RSS in same plain-HTML digest | `config/sources.yaml` (2 YouTube + 5 RSS + 1 newsletter), renderer treats all uniformly | Header item count + footer suffix surfaces both main-feed and footer cards (`tests/test_render.py::test_header_item_count_main_feed_only_with_footer_suffix`) |
| 5 | Items failing any pipeline stage are surfaced to the reader without polluting the main feed | LOCKED-01: `pipeline/render/html._partition_cards()` routes thin items to `<aside id="also-seen">`, quota-exhausted items in-place with locked copy; `pipeline/llm/summarize._classify_llm_exception()` populates `summary_status` | `tests/test_render.py::test_thin_card_goes_to_footer_aside`, `test_quota_exhausted_card_renders_in_main_feed`, `test_api_error_card_goes_to_footer`, `test_footer_link_uses_canonical_url_with_noopener` |

All five success criteria pass with deterministic test evidence.

**Note on success criterion #5:** This row was rewritten during post-UAT
correction. The original Plan 02-03 D-25 contract ("no footer aside, all
items in-place") was rejected during visual UAT and superseded by LOCKED-01.
See "Post-UAT Corrections" below.

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
| 2-03-01 | `pytest tests/test_render.py` (LOCKED-01 routing) | ✅ green — file rewritten in commit `7bcef07` after UAT; original `test_degraded_renders_in_place` retired with D-25 |
| 2-03-02 | `pytest tests/test_render.py::test_pipeline_header_notice` | ✅ green |
| 2-03-03 | `pytest tests/test_render.py` | ✅ green (full module post-rewrite) |
| 2-04-01 | `python -m pipeline.run ingest --help \| grep -i pending` | ✅ green |
| 2-04-02 | `grep -q "only-pending-transcripts" README.md` | ✅ green |
| 2-04-03 | `pytest tests/` | ✅ green (71 cases post-correction) |

All 12 per-task validation gates pass.

## Phase gate

```
uv run --extra dev pytest tests/ -q
.......................................................................   [100%]
71 passed
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
- **D-25** — **RETIRED post-UAT 2026-05-22.** Original contract was
  "no footer aside, every card in-place". Visual UAT showed this
  produced a noisy main feed dominated by quota-exhausted-and-thin
  cards; user rejected and re-asserted the original Phase 1 D-05
  footer-aside intent. Superseded by **LOCKED-01** with a narrow
  carve-out: only transient LLM-call failures (rate-limit / quota)
  render in-place; everything else returns to the footer aside.
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

## Post-UAT Corrections (2026-05-22)

During the W21 visual UAT session the assistant and user identified two
defects in the as-shipped Phase 2 output and one structural gap. All three
were repaired during the same session before declaring Phase 2 closed.

### Correction 1 — Video indicator regression (commit `7bcef07`)

**Symptom.** YouTube cards in `out/digest-2026-W21.html` rendered without
the `[video]` indicator next to the publisher badge.

**Root cause.** `store/db.get_items_for_week` selected `items.*` but did
NOT join `sources.type`. The orchestrator's `_build_card_from_row` therefore
fell back to the `DigestCard.source_type` default of `'rss'`, silently
suppressing the indicator for every YouTube row. The unit test
`test_youtube_video_indicator` passed because it constructed `DigestCard`
records directly, never exercising the database read path.

**Fix.** Added `JOIN sources ON sources.source_id = items.source_id` and
`SELECT sources.type AS source_type` to `get_items_for_week`. New
end-to-end regression test `tests/test_render_e2e.py::test_youtube_video_indicator_end_to_end`
covers the full DB → renderer path to prevent recurrence.

### Correction 2 — Footer-aside regression + LOCKED-01 (commit `7bcef07`)

**Symptom.** The W21 digest contained 12+ cards in the main feed whose body
copy was either an empty TL;DR or the degradation copy from Plan 02-03 D-25.
This was the intended D-25 behavior but the user rejected it during visual
UAT, re-asserting the Phase 1 D-05 footer-aside intent and noting that
Plan 02-03 should never have been allowed to override a previous user
directive.

**Root cause.** Plan 02-03 D-25 ("in-place degradation, no relegation")
directly contradicted Phase 1 D-05 ("Also seen this week" footer aside)
without surfacing the conflict to the user for resolution.

**Fix — three layers:**

1. **`summary_status` taxonomy** (`store/migrations/003_summary_status.sql`).
   New column on `item_summaries` recording why a summary is unavailable:
   `ok` / `thin` / `quota_exhausted` / `api_error` / `parse_error` /
   `client_init_error`. Old rows have `NULL`; renderer treats `NULL` as
   inferring from `tldr` presence.

2. **LLM-error classification** (`pipeline/llm/summarize._classify_llm_exception`).
   Maps Gemini exceptions to the taxonomy. Rate-limit / quota /
   `RESOURCE_EXHAUSTED` / 429 → `quota_exhausted`; everything else →
   `api_error`.

3. **Renderer rewrite** (`pipeline/render/html._partition_cards`). Single
   source of truth for routing: healthy cards (real `tldr`) and
   `quota_exhausted` cards go in the main feed; everything else goes in
   the `<aside id="also-seen">` footer. Quota-exhausted in-place cards
   render with the locked verbatim copy `"The summary couldn't be generated this week."`

The original W21 digest was re-rendered from the existing DB and verified
visually after the fix.

### Correction 3 — LOCKED-DIRECTIVES.md hard-gate (commit `66bd137`)

**Symptom (structural).** Plan 02-03 had been allowed to silently override a
previous user directive (the Phase 1 D-05 footer). User instructed the
assistant to establish a mechanism that prevents this class of regression
in any future phase.

**Fix.** Created `.planning/LOCKED-DIRECTIVES.md` as the canonical
project-level rules file, with LOCKED-01 as the first entry. Added
`.cursor/rules/locked-directives.mdc` that auto-attaches when planning
files are accessed. Added `<preflight_hard_gate>` blocks to the top of
`.cursor/skills/gsd-plan-phase/SKILL.md`,
`.cursor/skills/gsd-discuss-phase/SKILL.md`, and
`.cursor/skills/gsd-autonomous/SKILL.md` requiring the agent to read
LOCKED-DIRECTIVES.md before any planning work, surface conflicts as
explicit questions, and never bury overrides inside plan documents.

A future agent that drafts a plan touching LOCKED-01 must now stop and
ask, rather than silently overriding.

## Pending items carried forward

| Item | Type | Surfaces in | Owner phase |
|------|------|-------------|-------------|
| Phase 2 UAT tests 6 (confirmed-missing transcripts) + 7b (deliberate 404 source isolation) | Manual fault-injection | `02-UAT.md`, `STATE.md` pending todos | Operator follow-up (non-blocking for Phase 3) |
| Gemini billing decision | Operational | `STATE.md` pending todos | Re-evaluate after Phase 3 dedup ships AND source catalog stabilizes |
| Live residential `pending_local → ok` transition against real YouTube transcript API | Manual UAT | `02-UAT.md` test 5 | Operator (the W21 run hit 16-of-16 transcripts on first try; no pending_local rows existed to catch up) |
| Pipeline-notes UI attribution for "RSS thin body" vs "LLM call failed" | Engineering refinement | `02-03-SUMMARY.md` Deviations | Phase 4 OBS-01 |
| `summary_input_truncated` column added but no reader-facing surface yet | Schema column persisted, awaits pipeline-notes UI | `pipeline/llm/summarize.py` | Phase 3 (categorization/ranking can leverage) |

## Self-Check: PASSED (amended 2026-05-22)

- [x] All 4 plans executed and self-checked PASSED
- [x] All 12 per-task validation gates green (Plan 02-03 tests rewritten post-UAT)
- [x] Full pytest suite green (71/71 post-correction)
- [x] ruff clean across `pipeline/`, `store/`, `tests/`
- [x] Both Phase 2 requirements (INGEST-03, INGEST-06) verified
- [x] All 5 ROADMAP.md success criteria verified (criterion #5 rewritten to LOCKED-01)
- [x] All 11 referenced decisions honored, with D-25 retired in favour of LOCKED-01
- [x] Deviations documented and justified
- [x] Manual UAT executed (6 passed, 2 pending fault-injection setup)
- [x] Post-UAT corrections documented above with commit references
- [x] LOCKED-DIRECTIVES.md hard-gate established to prevent recurrence
