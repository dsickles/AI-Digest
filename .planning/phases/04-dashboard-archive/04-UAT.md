---
status: testing
phase: 04-dashboard-archive
source: 04-03-SUMMARY.md, 04-04-SUMMARY.md, 04-05-SUMMARY.md, 04-06-SUMMARY.md
started: 2026-05-23T23:15:00Z
updated: 2026-05-23T23:15:00Z
---

## Current Test

number: 1
name: W19/W21 LOCKED-01 routing vs HTML dev preview
expected: |
  Run `uv run python -m pipeline.run render --week 2026-W19` and `--week 2026-W21`
  (render-only logs; no summarize/ingest LLM lines). Compare
  `web/src/content/digests/2026-W21.json` footer_aside (thin RSS only) and
  main_feed quota_exhausted cards against `out/digest-2026-W21.html` from the
  same week. W19 tolerates pre-Phase-3 null cluster fields. W21 footer_aside
  must not contain quota_exhausted titles.
awaiting: user response

## Tests

### 1. W19/W21 LOCKED-01 routing vs HTML dev preview
expected: Backfilled JSON matches LOCKED-01 partition rules; thin items in footer_aside only; quota_exhausted and other transient statuses in main_feed in-place degraded cards; compare against deprecated `out/digest-*.html` when present
result: [pending]

### 2. Tab navigation with JavaScript disabled
expected: Browse `/`, `/edtech`, `/business`, `/technical`, and `/digest/2026-W21/edtech` with JS disabled — each tab is a static route; links navigate without client-side routing
result: [pending]

### 3. Mobile 375px — no horizontal scroll
expected: DevTools 375×667 on `/` and `/archive` — no horizontal scrollbar; TabBar wraps to two rows; header stacks vertically (D-A6c)
result: [pending]

### 4. Canonical tags on `/` and `/business`
expected: View source on `/` and `/business` — each has `<link rel="canonical">` pointing to the dated permalink under `/digest/{week_id}/…` (ARCHIVE-03)
result: [pending]

### 5. Archive index with two weeks
expected: `/archive` lists 2026-W19 and 2026-W21 with "Week of …" headings, synthesis excerpt or fallback, and "Read this week" links. Fresh clone with zero JSON shows "No past digests yet" empty state (UI-SPEC copy)
result: [pending]

### 6. Pipeline notes zero-state DOM absence
expected: On a week with no pipeline signals, Briefing main has no `<details>` pipeline-notes element (not hidden via CSS — absent from DOM). W21 with budget/transcript signals shows `<details>` with summary line
result: [pending]

### 7. YouTube play icon contrast (DISPLAY-05)
expected: Cards with `source_type: youtube` show inline SVG play indicator with sufficient contrast on `#141820` card background; no `[video]` text suffix
result: [pending]

### 8. Deprecated HTML dev preview path
expected: `uv run python -m pipeline.run render --week 2026-W21` (without `--no-html-preview`) still writes `out/digest-2026-W21.html`; module docstring marks `pipeline/render/html.py` as DEPRECATED dev-preview only
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0
blocked: 0

## Gaps

<!-- Populated when issues found during verify-work -->
