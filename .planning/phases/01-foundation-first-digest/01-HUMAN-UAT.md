---
status: partial
phase: 01-foundation-first-digest
source: [01-VERIFICATION.md]
started: 2026-05-22T00:15:00Z
updated: 2026-05-22T00:15:00Z
---

## Current Test

[awaiting human testing — live RSS + Gemini outside Cursor sandbox]

## Tests

### 1. Live three-feed E2E
expected: `uv run python -m pipeline.run all` exits 0 with `GEMINI_API_KEY` set; `out/digest-YYYY-Www.html` exists; `data/aidigest.db` has rows in `items` from all three feeds and matching rows in `item_summaries` with `prompt_version='summarize_v1'`; `pipeline_runs` row finishes with `status='success'` (or `'partial'` if one feed was down) and non-null `finished_at`, `items_fetched`, `cost_usd_estimate`.
result: [pending]

### 2. Browser readability
expected: Opening `out/digest-*.html` in a browser shows dark theme (#0e1116 bg, #e6e6e6 text), max ~720px width, header "AI Digest" + "Week of MMM D – MMM D, YYYY" + "Updated …Z", source badges in `[brackets]`, 2–4 sentence TL;DRs, and source links open in a new tab. Cards sorted newest-first.
result: [pending]

### 3. Multi-publisher digest
expected: The rendered HTML contains cards from at least two of the three configured publishers (Simon Willison, One Useful Thing, Import AI) — confirms multi-source ingest path is exercised end-to-end.
result: [pending]

### 4. Live backfill smoke
expected: `uv run python -m pipeline.run all --week 2026-W19` produces `out/digest-2026-W19.html` whose header reads "Week of May 4 – May 10, 2026"; running the same command twice does not duplicate items in SQLite.
result: [pending]

### 5. Visual grounding sanity
expected: Spot-check 2–3 real TL;DRs against the source articles — no invented facts; clearly thin posts render the `[summary unavailable — content too thin]` line instead of a fabricated summary.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
