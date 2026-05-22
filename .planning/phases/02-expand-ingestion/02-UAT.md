---
status: pending
phase: 02-expand-ingestion
source: [02-VALIDATION.md, 02-04-PLAN.md]
references:
  - D-22  # discoverability triad (CONTEXT + README + --help + UAT)
  - D-23  # free-first YouTube transcript strategy with local catch-up
  - D-24  # plain-English reader surface (no CLI flag jargon in HTML)
  - D-25  # in-place degradation cards
  - D-26  # header pipeline notice
  - D-30  # YouTube video indicator
  - D-33  # 8-source Phase 2 catalog
---

## Manual UAT — Phase 2 (expand-ingestion)

These tests cover the manual-only verifications listed in `02-VALIDATION.md`
and the D-22 discoverability triad for `--only-pending-transcripts`. The
automated pytest suite already covers the deterministic surface; this
checklist is the residential / browser-visual verification an operator
must perform before declaring Phase 2 live.

## Current Test

[not yet started — run after merging phase 2 and pulling locally]

## Tests

### 1. Live 8-source end-to-end weekly run
expected: `uv run python -m pipeline.run all` (with `GEMINI_API_KEY` set) on a residential network exits 0 within the time budget; `out/digest-YYYY-Www.html` opens in a browser; the card grid contains at least one item per enabled non-empty source from the 8-source catalog (5 RSS + 2 YouTube + 1 newsletter, D-33); YouTube cards show the `[video]` indicator next to the publisher badge (D-30).
result: pending
evidence:

### 2. In-place degradation (D-25)
expected: For any source that returns a thin body or whose YouTube transcript could not be fetched, the card still renders in natural sort position (no separate "Also seen this week" footer); the degraded card body is a plain-English clause from the D-24 reader-surface catalog ("transcript wasn't reachable…", "summary is unavailable…", etc.) — no `pending_local`, `transcript_status`, or CLI-flag jargon appears anywhere in the rendered HTML.
result: pending
evidence:

### 3. Header pipeline notice (D-26)
expected: When at least one item is `pending_local` OR at least one non-empty-feed ingest error occurred, the digest header shows a `pipeline-notice` element (visually distinct from card content) summarising the counts in plain English. When neither condition holds, no notice element is rendered.
result: pending
evidence:

### 4. CLI discoverability triad (D-22)
expected: All three surfaces document the catch-up flag:
- `uv run python -m pipeline.run ingest --help` lists `--only-pending-transcripts` with a plain-English description.
- `uv run python -m pipeline.run all --help` lists the same flag.
- `README.md` includes a "YouTube transcript catch-up" section with at least one full example command (`uv run python -m pipeline.run ingest --only-pending-transcripts`).
result: pending
evidence:

### 5. Residential transcript catch-up (D-23)
expected: After a cloud run that left at least one YouTube item with `transcript_status='pending_local'`, running `uv run python -m pipeline.run ingest --only-pending-transcripts` from a residential IP advances at least one such item to `transcript_status='ok'` with the captions written to `raw_content`. A subsequent `uv run python -m pipeline.run all --week <same-week>` produces a digest whose previously degraded YouTube cards now show a TL;DR grounded in the transcript.
result: pending
evidence:

### 6. Confirmed-missing transcripts (D-23)
expected: A YouTube video whose captions are genuinely disabled (`TranscriptsDisabled`) when retried from a residential IP advances from `transcript_status='pending_local'` to `transcript_status='missing'` and is not retried on subsequent catch-up runs. The card stays degraded in-place with the D-24 missing-transcript copy.
result: pending
evidence:

### 7. Per-source failure isolation (D-39, D-40, D-41)
expected: Deliberately misconfigure one RSS source (e.g., point `where-your-ed-at` at a 404 URL) and run `uv run python -m pipeline.run ingest`. The bad source produces a `fetch_http_error` entry in `out/last_run.md` with the HTTP status, the run still ingests the other seven sources, and `sources.last_error_category` reflects the typed category for that source. An empty-feed week for a healthy source must NOT count toward the failed-sources pipeline notice (D-41).
result: pending
evidence:

## Summary

total: 7
passed: 0
issues: 0
pending: 7
skipped: 0
blocked: 0

## Gaps

*(filled in during execution)*
