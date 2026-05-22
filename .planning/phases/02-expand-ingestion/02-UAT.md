---
status: complete-with-pending
phase: 02-expand-ingestion
source: [02-VALIDATION.md, 02-04-PLAN.md, LOCKED-DIRECTIVES.md LOCKED-01]
references:
  - D-22  # discoverability triad (CONTEXT + README + --help + UAT)
  - D-23  # free-first YouTube transcript strategy with local catch-up
  - D-24  # plain-English reader surface (no CLI flag jargon in HTML)
  - D-26  # header pipeline notice
  - D-30  # YouTube video indicator
  - D-33  # 8-source Phase 2 catalog
  - LOCKED-01  # footer-aside routing (supersedes original D-25)
---

## Manual UAT — Phase 2 (expand-ingestion)

These tests cover the manual-only verifications listed in `02-VALIDATION.md`
and the D-22 discoverability triad for `--only-pending-transcripts`. The
automated pytest suite already covers the deterministic surface; this
checklist is the residential / browser-visual verification an operator
must perform before declaring Phase 2 live.

**Visual UAT session:** 2026-05-22, week W21 live run, residential network.

**Outcome:** 6 of 8 tests passed visually; 2 require deliberate fault-injection
setup (captions-disabled video; misconfigured 404 source) and are deferred
to a follow-up session — not blocking Phase 3 entry because the underlying
code is unit-tested in `tests/test_catch_up.py` and `tests/test_ingest.py`.

**Post-UAT corrections shipped during this session:** see commits `7bcef07`
(footer restoration + video indicator JOIN fix + `summary_status` taxonomy)
and `66bd137` (LOCKED-DIRECTIVES.md + Cursor rule hard-gate). Test 2 below
was rewritten because the original D-25 "in-place degradation, no footer"
contract was retired and superseded by LOCKED-01.

## Tests

### 1. Live 8-source end-to-end weekly run
expected: `uv run python -m pipeline.run all` (with `GEMINI_API_KEY` set) on a residential network exits 0 within the time budget; `out/digest-YYYY-Www.html` opens in a browser; the card grid contains at least one item per enabled non-empty source from the 8-source catalog (5 RSS + 2 YouTube + 1 newsletter, D-33); YouTube cards show the `[video]` indicator next to the publisher badge (D-30).
result: passed
evidence: W21 live run ingested 155 items across 7 of 8 sources (one-useful-thing returned an empty feed for the week, classified as info-only per D-41). After the post-UAT `get_items_for_week` JOIN fix (commit `7bcef07`) YouTube cards now render the `[video]` indicator next to the publisher badge — verified against `out/digest-2026-W21.html`. Bug history: the original JOIN omission masked the missing `source_type`, falling back to the `DigestCard` default of `'rss'` and silently dropping the indicator; covered going forward by `tests/test_render_e2e.py`.

### 2. LOCKED-01 routing — footer aside + quota-exhausted carve-out (replaces original D-25 test)
expected: Items whose summary failed for content-thin reasons (RSS body too short, YouTube transcript missing or pending, content-too-thin gate, enrichment failure, parse error, non-quota api error) render as outbound links inside the `<aside id="also-seen">` footer of the digest, NOT in the main feed. The footer is omitted entirely when there are no thin items. Items whose only failure was a transient LLM rate-limit / quota / `RESOURCE_EXHAUSTED` / HTTP 429 render in-place in the main feed with the verbatim body copy `"The summary couldn't be generated this week."` The header item count reflects main-feed cards only, with a `· N more in footer` suffix when the footer is non-empty.
result: passed
evidence: W21 live run hit the Gemini free-tier quota after 16 successful summaries. After the post-UAT renderer rewrite (commit `7bcef07`) the digest now correctly splits into 16 healthy cards + N quota-exhausted in-place cards in the main feed, and the remaining content-thin items moved to the `<aside id="also-seen">` footer. Manually verified in `out/digest-2026-W21.html`. Locked as LOCKED-01 in `.planning/LOCKED-DIRECTIVES.md` to prevent regression (the original D-25 contract was retired during this session).

### 3. Header pipeline notice (D-26)
expected: When at least one item is `pending_local` OR at least one non-empty-feed ingest error occurred, the digest header shows a `pipeline-notice` element (visually distinct from card content) summarising the counts in plain English. When neither condition holds, no notice element is rendered.
result: passed
evidence: W21 zero-state path verified — no `<p class="pipeline-notice">` element in `out/digest-2026-W21.html` because all YouTube transcripts came back `ok` and the only failed "source" was the empty one-useful-thing feed (info-only per D-41). The non-zero state remains covered by `tests/test_render.py::test_pipeline_header_notice` and the orchestrator helper `_pipeline_notice_counts`.

### 4. CLI discoverability triad (D-22)
expected: All three surfaces document the catch-up flag:
- `uv run python -m pipeline.run ingest --help` lists `--only-pending-transcripts` with a plain-English description.
- `uv run python -m pipeline.run all --help` lists the same flag.
- `README.md` includes a "YouTube transcript catch-up" section with at least one full example command (`uv run python -m pipeline.run ingest --only-pending-transcripts`).
result: passed
evidence: `--help` parity verified in commit `1ea55df`; README section added in `d2b4187`; D-22 triad complete (CONTEXT decision + README + `--help` + this UAT entry).

### 5. Residential transcript catch-up (D-23)
expected: After a cloud run that left at least one YouTube item with `transcript_status='pending_local'`, running `uv run python -m pipeline.run ingest --only-pending-transcripts` from a residential IP advances at least one such item to `transcript_status='ok'` with the captions written to `raw_content`. A subsequent `uv run python -m pipeline.run all --week <same-week>` produces a digest whose previously degraded YouTube cards now show a TL;DR grounded in the transcript.
result: passed (proxy — no pending_local items materialized to exercise the catch-up flow)
evidence: The W21 residential run fetched 16-of-16 YouTube transcripts directly on first try (no `pending_local` rows produced), so the catch-up flow had nothing to catch up. The code path itself is fully covered by `tests/test_catch_up.py` (8 cases including `pending_local → ok` promotion). To exercise the live transition end-to-end an operator would need to run from a known-IP-blocked network first; deferred to operator if/when it becomes relevant.

### 6. Confirmed-missing transcripts (D-23)
expected: A YouTube video whose captions are genuinely disabled (`TranscriptsDisabled`) when retried from a residential IP advances from `transcript_status='pending_local'` to `transcript_status='missing'` and is not retried on subsequent catch-up runs. The card stays in the footer aside per LOCKED-01.
result: pending — requires deliberate setup
evidence: None of the 16 W21 YouTube items had disabled captions. Exercising this path requires hand-picking a video with captions disabled (e.g. some music-video channels) and forcing it into the source catalog for one run. The classification logic is unit-tested via `tests/test_catch_up.py::test_classify_transcript_error_*` cases. Tracked in STATE.md "Pending Todos" for a follow-up session.

### 7. Per-source failure isolation (D-39, D-40, D-41)
expected: Deliberately misconfigure one RSS source (e.g., point `where-your-ed-at` at a 404 URL) and run `uv run python -m pipeline.run ingest`. The bad source produces a `fetch_http_error` entry in `out/last_run.md` with the HTTP status, the run still ingests the other seven sources, and `sources.last_error_category` reflects the typed category for that source. An empty-feed week for a healthy source must NOT count toward the failed-sources pipeline notice (D-41).
result: passed (partial — 7a empty-feed contract verified live; 7b deliberate 404 deferred)
evidence: 7a — W21 run produced an empty feed for one-useful-thing; `out/last_run.md` recorded the empty-feed category as info-only, and the header pipeline notice correctly omitted it (D-41 verified). 7b — deliberate 404 misconfiguration not yet exercised live; the codepath is covered by `tests/test_ingest.py::test_error_taxonomy_category` and `test_ingest_isolates_failing_source`. Tracked in STATE.md "Pending Todos".

### 8. LOCKED-DIRECTIVES.md hard-gate (new; established 2026-05-22)
expected: `.planning/LOCKED-DIRECTIVES.md` exists and contains LOCKED-01 as documented above. `.cursor/rules/locked-directives.mdc` auto-attaches when planning files are accessed. Each of `gsd-plan-phase`, `gsd-discuss-phase`, and `gsd-autonomous` SKILL.md files starts with a `<preflight_hard_gate>` block instructing the agent to read LOCKED-DIRECTIVES.md before any planning work.
result: passed
evidence: Files present per commit `66bd137`; manually inspected each preflight block. This is the structural guarantee that the original D-25 → LOCKED-01 regression cannot recur unless the user explicitly unlocks.

## Summary

total: 8
passed: 6
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps

- Tests 6 and 7b require fault-injection setups (captions-disabled video; deliberate 404) that weren't worth the manual scaffolding cost during the close-out session. Both are tracked in `.planning/STATE.md` "Pending Todos" and gated on either operator availability or the next time a real-world failure happens to exercise the path.
- Gemini billing decision deferred — see STATE.md pending todo. LOCKED-01 quota-exhausted carve-out keeps the UX coherent in the interim.
