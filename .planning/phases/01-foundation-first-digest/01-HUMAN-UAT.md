---
status: passed
phase: 01-foundation-first-digest
source: [01-VERIFICATION.md]
started: 2026-05-22T00:15:00Z
updated: 2026-05-22T01:02:00Z
approved_by: user
approved_at: 2026-05-22T01:02:00Z
---

## Current Test

[all human tests complete — user approved]

## Tests

### 1. Live three-feed E2E
expected: `uv run python -m pipeline.run all` exits 0 with `GEMINI_API_KEY` set; `out/digest-YYYY-Www.html` exists; `data/aidigest.db` has rows in `items` from all three feeds and matching rows in `item_summaries` with `prompt_version='summarize_v1'`; `pipeline_runs` row finishes with `status='success'` and non-null `finished_at`, `items_fetched`, `cost_usd_estimate`.
result: passed
evidence: 70 items_fetched (simon-willison 30 + one-useful-thing 20 + import-ai 20), all HTTP 200, 1 summary written (rest cached from prior runs), cost $0.000426, status success, out/digest-2026-W21.html rendered with 11 inline cards + 5 footer-link items.

### 2. Browser readability
expected: Opening `out/digest-*.html` in a browser shows dark theme, ~720px width, "AI Digest" + "Week of …" header, source badges in `[brackets]`, 2–4 sentence TL;DRs, source links open in a new tab, cards sorted newest-first.
result: passed
evidence: User-confirmed dark theme, "AI Digest" + "Week of" header, bracketed publisher badges, real-prose summaries, and the "Also seen this week" footer (after the 01-03 inline-regression was reverted in `5f8e9f0`).

### 3. Multi-publisher digest
expected: Rendered HTML contains cards from at least two of the three configured publishers.
result: passed
evidence: User confirmed `[Simon Willison]` and `[Import AI]` badges visible. `[One Useful Thing]` absent for W21 because OUT published nothing in the May 18–24 window (verified in SQLite: `one-useful-thing` 0/20 items in window). Multi-source ingest path is exercised end-to-end.

### 4. Live backfill smoke
expected: `uv run python -m pipeline.run all --week 2026-W19` produces `out/digest-2026-W19.html` whose header reads "Week of May 4 – May 10, 2026"; running the same command twice does not duplicate items in SQLite.
result: passed
evidence: Three consecutive runs of `--week 2026-W19`: items_fetched stayed at 70, summaries_written dropped 1 → 0 → 0, cost_usd_estimate dropped $0.000704 → $0.000000 → $0.000000, render output stable at 1 card. Idempotency proven; W19-window filter works.

### 5. Visual grounding sanity
expected: Spot-check 2–3 real TL;DRs against the source articles — no invented facts; thin posts render the `[summary unavailable — content too thin]` line instead of a fabricated summary.
result: passed
evidence: User spot-checked summaries against source articles and approved.

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

*(none)*
