---
status: partial
phase: 03-ai-quality
source: [03-VERIFICATION.md]
started: 2026-05-23T12:25:00Z
updated: 2026-05-23T14:30:00Z
---

## Current Test

[awaiting fresh digest run after gap-closure batch 2]

## Tests

### 1. Live digest 15-minute skim — Core Value hypothesis
expected: Coherent weekly narrative, Top N briefing, category sections, and attributions readable in ~15 minutes; Core Value hypothesis feels testable
result: partial
why_human: Readability, narrative quality, and 15-minute skim time cannot be verified programmatically. Run `pipeline.run all` with real sources and `GEMINI_API_KEY`, open `out/digest-{week_id}.html`, skim start to finish.
notes: |
  User's first-pass UAT (2026-05-23 mid-morning) confirmed Top 5 briefing
  and category sections render correctly. Five follow-up items surfaced —
  see Gaps section. Three are now resolved (Shorts filter, footer routing
  bug, design category cut); one is captured as a forward-looking risk
  in PROJECT.md (LLM quota); one is deferred to Phase 4 (tabbed UI).
  Re-run pending after batch 2 commits to confirm:
    - 3 quota_exhausted YouTube videos render in-place degraded (not in footer)
    - footer contains only RSS-thin items
    - no design category section
    - no YouTube Shorts

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps

### UAT-FOLLOWUP-01 — YouTube Shorts ingested and summarized
status: resolved
resolved_in: e47844e — fix(03): skip YouTube Shorts at ingest
resolved_at: 2026-05-23T13:30:00Z
severity: high
reported_by: human-uat
reported: 2026-05-23T13:23:00Z
detail: |
  YouTube Shorts (URLs containing `/shorts/`) currently flow through ingest, get
  summarized, and appear as full cards in the digest. Examples in
  `out/digest-2026-W21.html`:
    - https://www.youtube.com/shorts/qevGU6MR1rk
    - https://www.youtube.com/shorts/aJmu2tKa2Us
    - https://www.youtube.com/shorts/CgsOqhYgl1E
    - https://www.youtube.com/shorts/-mxQBSCMKVg
    - https://www.youtube.com/shorts/OQlf4UwugBg
    - https://www.youtube.com/shorts/a6GOGmzJ-OU
    - https://www.youtube.com/shorts/x9_2NGUmQdo
    - https://www.youtube.com/shorts/hYDJnwgJr4Y
    - https://www.youtube.com/shorts/_rLgj8VcaVU
    - https://www.youtube.com/shorts/WwpDswEjTXg
required_behavior: |
  Shorts must be skipped entirely at ingest:
    - Not summarized (no LLM tokens spent on them)
    - Not categorized / ranked / rolled up
    - Not included in the "Also seen this week" footer
    - Detected by `canonical_url` containing `/shorts/` or `youtube.com/shorts/`
suggested_files:
  - pipeline/adapters/youtube.py (drop entries whose link contains /shorts/)
  - pipeline/adapters/rss.py (drop RSS items pointing at youtube.com/shorts/)
  - tests/adapters/test_youtube_shorts_filter.py (new — assert dropped at ingest)

### UAT-FOLLOWUP-02 — Stale digest blocks visual UAT
status: resolved
severity: medium
reported: 2026-05-23T13:23:00Z
resolved_at: 2026-05-23T14:00:00Z
detail: |
  The only digest in `out/` (`digest-2026-W21.html`) was generated 2026-05-22 09:14,
  before plans 03-02..03-05 wired briefing/categories/rollup into the renderer.
  Resolution: user re-ran `pipeline.run all` and confirmed Top 5 briefing +
  category sections render correctly.

### UAT-FOLLOWUP-03 — quota_exhausted items mis-routed to footer
status: resolved
resolved_in: 29972dd — fix(03): propagate summary_status when reconstructing SummaryResult from DB
resolved_at: 2026-05-23T14:00:00Z
severity: high
reported_by: human-uat
reported: 2026-05-23T13:50:00Z
detail: |
  The Week 21 digest had 3 long-form YouTube items in the
  `<aside id="also-seen">` footer that should have rendered in-place as
  degraded cards per LOCKED-01:
    - "Can I get my agents on the phone?" (Ben's Bites, 5354-char body, summary_status=quota_exhausted)
    - "The Prove-It Economy is Here" (Nate B Jones, 24474-char transcript, quota_exhausted)
    - "Why this Claude Code engineer uses HTML files as AI specs" (How I AI, 38204-char transcript, quota_exhausted)
  All three had `summary_status='quota_exhausted'` persisted in
  `item_summaries`. Root cause: `_summarize_week_items` reconstructed the
  in-memory `SummaryResult` from the DB row without passing
  `summary_status`, so the dataclass default ('ok') silently won. With
  `summary_status='ok'` and empty `tldr`, `_partition_cards` fell through
  to the footer.
verification: tests/test_summary_status_propagation.py covers both the
  propagation through `_summarize_week_items` and the `_partition_cards`
  routing for quota_exhausted with empty tldr.

### UAT-FOLLOWUP-04 — LOCKED-01 routing scope refinement
status: resolved
resolved_in: dffcc8f — feat(03): refine LOCKED-01 — footer is RSS-thin only
resolved_at: 2026-05-23T14:15:00Z
severity: high
reported_by: human-uat
reported: 2026-05-23T13:55:00Z
detail: |
  User feedback ("the footer should only include things in rss feeds that
  are too short to summarize. You keep making this mistake on what should
  go in the footer!") narrowed LOCKED-01: the footer aside is reserved
  for `summary_status='thin'` only. Every other "no summary this week"
  reason — quota_exhausted, api_error, parse_error, client_init_error,
  transcript_missing — renders in-place in the main feed with the locked
  body "The summary couldn't be generated this week."
verification: tests/render/test_partition_cards_phase3.py covers the
  full in-place bucket and a mixed-status partition; tests/test_render.py
  module docstring + per-status tests rewritten.
docs_updated:
  - .planning/LOCKED-DIRECTIVES.md (LOCKED-01 v2 with full status table)
  - .planning/PROJECT.md (locked decision row)
  - pipeline/render/html.py (module docstring + _IN_PLACE_TRANSIENT_STATUSES)
  - pipeline/orchestrator.py (_infer_summary_status maps pending_local/missing
    transcripts to new 'transcript_missing' status)

### UAT-FOLLOWUP-05 — Cut design category from v1 scope
status: resolved
resolved_in: 6307bca — feat(03): cut design category from v1
resolved_at: 2026-05-23T14:30:00Z
severity: medium
reported_by: human-uat
reported: 2026-05-23T14:00:00Z
detail: |
  User: "i want to cut 'design' as a category completely for now. update
  all relevant functional documents with this scope cut." Phase 3 visual
  UAT showed the active source list wasn't producing a coherent design
  lane; UX/product/design tooling stories now route to `technical`.
verification: All 175 tests pass; production DB had 0 rows referencing
  `category='design'` so no migration required.
docs_updated:
  - .planning/PROJECT.md (Origin context line, Active Requirements row,
    Key Decisions table)
  - README.md (categorize stage description)
  - 11 code files + 6 test files (full anchor list in commit message)

### UAT-FOLLOWUP-06 — Tabbed UI for digest sections
status: deferred_to_phase_4
severity: low
reported_by: human-uat
reported: 2026-05-23T14:00:00Z
detail: |
  User: "i want the different sections to be tabs on the page rather
  than everything in a single html flow. is now the time to work on that
  design or would that be better done in a later phase?"
disposition: |
  Deferred. Phase 3 owns the data layer (dedup, categorize, rank, rollup,
  in-place degraded routing). Tabbed presentation is a UI/UX concern with
  its own surface area (URL-hash routing vs no-JS, mobile collapse, empty-
  tab states, "All" / "Briefing-only" tabs, keyboard a11y, cross-tab dedup
  attribution). Belongs in the next UI/UX-focused phase. Captured as a
  Phase 4 input rather than splitting Phase 3 scope.

### UAT-FOLLOWUP-07 — LLM quota dependency surfaced as project risk
status: captured_in_project
severity: medium
reported_by: human-uat
reported: 2026-05-23T14:10:00Z
detail: |
  User: "we need a solution for the future. blocking dependencies need
  solutions early in design process!" The Phase 3 Week 21 run hit
  `RESOURCE_EXHAUSTED` on Gemini free-tier mid-summarize; 3 of 28 items
  came back quota_exhausted. The free-tier RPM is structurally too small
  for a full weekly run with the active source list.
disposition: |
  Captured in PROJECT.md "Blocking Dependencies & Active Risks" section
  with three acceptable resolution paths: (a) paid Gemini key, (b)
  --retry-quota CLI flag, (c) fallback LLM provider. Code already
  classifies and persists summary_status='quota_exhausted', so any of
  (a)–(c) lands cleanly. This is a v1-ship blocker per the user's
  feedback but not a Phase 3 code change.
