---
phase: 02-expand-ingestion
plan: "03"
status: complete
type: execute
wave: 3
requirements:
  - INGEST-03
completed: 2026-05-22
self_check: PASSED
---

# Plan 02-03 — In-place degradation renderer + header pipeline notice

## What shipped

Plan 02-03 supersedes Phase 1 D-05 with the project-level D-25 in-place
degradation contract. Every digest item now renders as `<article
class="card">` in natural sort position; degraded items keep their slot and
carry plain-English copy (D-24). A new header `pipeline-notice` (D-26)
surfaces pending-local + failed-source counts, hidden at zero state.

## Tasks

| Task | Files touched | Commit |
|------|---------------|--------|
| 2-03-01 — Rewrite `tests/test_render.py` (TDD RED) | `tests/test_render.py` | `d3ad48a` |
| 2-03-02 — Rewrite `pipeline/render/html.py` | `pipeline/render/html.py` | `7918077` |
| 2-03-03 — Orchestrator card assembly + pipeline-notice counts | `pipeline/orchestrator.py` | `9cf68d5` |

## Symbols removed (Phase 1 D-05 superseded)

- `_render_pipeline_notes`
- `OMITTED_SECTION_HEADING`
- `_is_displayable`
- `DEGRADED_SUMMARY_LINE`
- `.pipeline-notes` CSS block
- Footer-oriented tests (`test_degraded_item_goes_to_footer_not_article`,
  `test_only_thin_items_show_empty_main_and_footer`,
  `test_no_omitted_means_no_footer_section`, etc.)

## Symbols added

- `DigestCard.source_type`, `transcript_status`, `degradation_reason`
- `render_digest(pipeline_notice_pending_count=..., pipeline_notice_failed_source_count=...)`
- `_render_pipeline_notice` helper (plain-English clauses, zero-state hide)
- `.pipeline-notice` + `.video-indicator` + `.card-degraded` CSS
- Orchestrator: `_DEGRADATION_COPY` template catalog,
  `_resolve_degradation_reason`, `_build_card_from_row`,
  `_pipeline_notice_counts`

## Decisions honored

- **D-25** — Every card renders in place; header item count is the total card
  count, not displayed-only.
- **D-26** — Header `pipeline-notice` element appears only when pending or
  failed counts are positive.
- **D-24** — `_FORBIDDEN_READER_TOKENS` scan in
  `tests/test_render.py::test_reader_surface_plain_english` codifies the
  reader-surface language policy and is asserted against the live HTML.
- **D-30** — YouTube cards carry a small `<span class="video-indicator">
  [video]</span>` next to the publisher badge; RSS cards do not.
- **D-41** — Empty-feed errors are explicitly excluded from the failed-source
  count in `_pipeline_notice_counts`.

## Verification

```
uv run pytest tests/test_render.py -x -q                            # 14 green
uv run pytest tests/ -q                                             # 60 green
uv run ruff check pipeline/ store/ tests/                           # clean
```

`uv run python -m pipeline.run render --week 2026-W19` against the seeded
DB is reserved for manual UAT — the test suite already proves the absence
of `Also seen this week`, `pipeline-notes`, and the forbidden D-24 token
list.

## Self-Check: PASSED

- [x] All tasks executed (3/3)
- [x] Each task committed individually (TDD ordering preserved)
- [x] All tests green (60/60); 14 D-25/D-26/D-24/D-30 tests in `test_render.py`
- [x] All ruff checks clean
- [x] D-05 footer aside fully removed; D-25 in-place contract live
- [x] D-26 header notice with zero-state hide
- [x] D-24 reader-surface policy enforced in tests

## Deviations

`_resolve_degradation_reason` cannot distinguish "RSS thin source body" from
"LLM call failed" using only the `(source_type, transcript_status,
summary_confidence, has_tldr)` tuple available at card-assembly time — both
collapse to `_DEGRADATION_COPY["summary_failed"]`. Phase 4 OBS-01 ("Pipeline
notes" UI) is the right place to layer richer attribution, and the
`item_summaries.summary_input_truncated` column plus the D-39 error
taxonomy give it enough signal to make the distinction visible without
re-deriving from raw messages. No reader-facing impact today.

## Handoff to plan 02-04

The renderer, orchestrator, and pipeline-notice contract are stable. Plan
02-04 owns:
- CLI flag `--only-pending-transcripts` on `ingest` and `all` subparsers.
- Orchestrator catch-up path that re-fetches transcripts for items where
  `transcript_status == 'pending_local'` and (only on this path) flips to
  `missing` after `TranscriptsDisabled`.
- README section + UAT entry satisfying the D-22 discoverability triad.
- Full pytest suite as the phase gate (`uv run pytest tests/ -q`).
