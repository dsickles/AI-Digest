---
phase: 01-foundation-first-digest
plan: "03"
subsystem: pipeline
tags: [python, trafilatura, readability-lxml, gemini, grounding, summary_confidence, html, pytest]

requires:
  - phase: 01-foundation-first-digest
    plan: "02"
    provides: three-source ingest, stable item_id upsert, orchestrator seams
provides:
  - Hybrid RSS + trafilatura content enrichment (D-03) via pipeline/content_enrich.py
  - Grounding prompt with thin_content sentinel in summarize_v1.md (D-04, PITFALLS #13)
  - summary_confidence high|low|unavailable persistence on item_summaries (D-06)
  - Inline degraded cards with [summary unavailable — content too thin] (D-05, D-15)
  - Hermetic summarize + render tests with mocked Gemini and httpx
affects:
  - 01-04 (CLI subcommands inherit enrichment-aware summarize path)
  - 01-05 (pytest suite expansion — test_summarize.py anchor)
  - Phase 3 (per-item grounding seed for PITFALLS #14 hierarchical rollup)

tech-stack:
  added:
    - trafilatura 2.x, readability-lxml 0.8.x
  patterns:
    - prepare_input_text(item, httpx_client) → (text, enrichment_triggered) with 500-char skip gate
    - Fetch failures log structlog context and return RSS snippet without raising
    - SummaryResponse Optional summary + reason; thin_content → unavailable confidence
    - Enrichment + final text < 500 chars → low confidence on successful summary
    - Degraded cards render inline with html.escape on all dynamic fields

key-files:
  created:
    - pipeline/content_enrich.py
    - tests/test_summarize.py
  modified:
    - pyproject.toml
    - uv.lock
    - pipeline/llm/summarize.py
    - pipeline/orchestrator.py
    - pipeline/render/html.py
    - tests/test_render.py

key-decisions:
  - "Keep summarize_v1 prompt_version — prompt text already contained thin_content sentinel; no bump needed"
  - "Degraded items render as full inline cards per D-15, replacing footer-only 'Also seen this week' partition from 01-01"

patterns-established:
  - "Hermetic enrichment tests: httpx_mock for fetch, monkeypatch trafilatura.extract, patch pipeline.llm.summarize.prepare_input_text for summarize integration"
  - "DEGRADED_SUMMARY_LINE constant in html.py for the exact D-05 sentinel string"

requirements-completed:
  - PIPELINE-01

duration: ~45min
completed: 2026-05-21
---

# Phase 1, Plan 01-03: Trafilatura + Grounding Sentinel + Degraded Cards Summary

**Hybrid trafilatura enrichment, Gemini thin_content sentinel with summary_confidence persistence, and inline degraded HTML cards that never omit thin-content items.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-05-21T19:50Z
- **Completed:** 2026-05-21T20:00Z
- **Tasks:** 3 (3 commits)
- **Files modified:** 8
- **Test count:** 29 pytest cases, all passing
- **Lint:** ruff clean

## Accomplishments

- `prepare_input_text` skips fetch when RSS body ≥ 500 chars; otherwise fetches canonical URL with trafilatura + readability fallback
- `summarize_item` wires enrichment, maps thin_content to `summary_confidence='unavailable'`, and sets `low` when enrichment fired but text stays under 500 chars
- Renderer shows every item as a card; degraded path displays literal `[summary unavailable — content too thin]` inline (D-15)
- Orchestrator passes `canonical_url`, `item_id`, `source_id` into summarize for enrichment
- Seven new hermetic tests in `test_summarize.py`; render tests updated for inline degraded cards

## Task Commits

Each task was committed atomically:

1. **Task 1: Hybrid content enrichment with trafilatura** — `3c29311` (feat)
2. **Task 2: Grounding prompt, sentinel schema, confidence enum** — `bc0857a` (test)
3. **Task 3: Degraded card rendering** — `cf7f80c` (feat)

**Plan metadata:** `d9e5dbc` (docs: complete plan)

## Files Created/Modified

| File | Purpose |
|------|---------|
| `pipeline/content_enrich.py` | D-03 hybrid input: trafilatura + readability fallback |
| `pipeline/llm/summarize.py` | Enrichment wiring, confidence enum paths |
| `pipeline/orchestrator.py` | Pass enrichment fields to summarize_item |
| `pipeline/render/html.py` | Inline degraded cards with D-05 sentinel |
| `tests/test_summarize.py` | Mocked Gemini + enrichment hermetic tests |
| `tests/test_render.py` | Degraded card assertions (literal text, escape, noopener) |
| `pyproject.toml` / `uv.lock` | trafilatura + readability-lxml runtime deps |

## Decisions Made

- Kept `summarize_v1` prompt_version — existing prompt already documented thin_content sentinel
- Replaced footer-only omitted-items UX from Plan 01-01 with inline degraded cards per D-15

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Patch target for prepare_input_text in tests**
- **Found during:** Task 2 (test_enrichment_low_confidence_when_text_still_short)
- **Issue:** Patching `pipeline.content_enrich.prepare_input_text` did not intercept the import in summarize.py
- **Fix:** Patch `pipeline.llm.summarize.prepare_input_text` instead
- **Files modified:** `tests/test_summarize.py`
- **Committed in:** `bc0857a`

**2. [Rule 3 - Blocking] Ruff import order in summarize.py**
- **Found during:** Task 2 verification
- **Issue:** httpx/content_enrich import block failed I001
- **Fix:** `ruff check --fix pipeline/llm/summarize.py`
- **Committed in:** `3c29311` (included in task 1 commit via fix before commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Test patch target and lint fix required for verification; no scope change.

## Issues Encountered

None beyond auto-fixed items above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Wave 3 complete; ready for Plan 01-04 (`--week` ISO override, CLI subcommands, README/UAT)
- Live trafilatura fetch should be validated manually outside sandbox (TLS-intercept environments may differ from CI)

## Self-Check: PASSED

- `pipeline/content_enrich.py` — FOUND
- `tests/test_summarize.py` — FOUND
- Commits `3c29311`, `bc0857a`, `cf7f80c` — FOUND

## Post-execution correction (2026-05-22)

The Task 3 "inline degraded cards" deliverable in commit `cf7f80c`
**regressed** the user's post-Plan-01-01 decision (commit `8fcbd96`) to
collapse thin items into a single `Also seen this week` footer aside.
The plan was written to literal D-05 wording without flagging the
conflict with the live-digest tweak the user had already made.

Reverted in commit `5f8e9f0` (`fix(01-03): restore footer 'Also seen
this week' for thin items`). D-05 in `01-CONTEXT.md` rewritten to lock
the footer behavior as the final form so future renderer work can't
re-regress without amending the decision first. Test suite expanded from
41 → 43 covering: thin items go to footer not `<article>`, header item
count reflects displayed count (not total), XSS escape on skipped-item
titles in the footer.

The grounding-prompt + `summary_confidence` enum + content-enrichment
work from this plan (Tasks 1 and 2) is unaffected and remains in force.

---
*Phase: 01-foundation-first-digest*
*Completed: 2026-05-21*  
*Post-execution correction: 2026-05-22 — footer regression fix (`5f8e9f0`)*
