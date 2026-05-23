---
status: partial
phase: 03-ai-quality
source: [03-VERIFICATION.md]
started: 2026-05-23T12:25:00Z
updated: 2026-05-23T13:23:00Z
---

## Current Test

[awaiting fresh digest run]

## Tests

### 1. Live digest 15-minute skim — Core Value hypothesis
expected: Coherent weekly narrative, Top N briefing, category sections, and attributions readable in ~15 minutes; Core Value hypothesis feels testable
result: blocked
why_human: Readability, narrative quality, and 15-minute skim time cannot be verified programmatically. Run `pipeline.run_all` with real sources and `GEMINI_API_KEY`, open `out/digest-{week_id}.html`, skim start to finish.
blocker: Most recent digest (`out/digest-2026-W21.html`, mtime 2026-05-22 09:14) predates Phase 3 plans 03-02..03-05 render wiring. Need a fresh run after fixing UAT-FOLLOWUP-01.

## Summary

total: 1
passed: 0
issues: 0
pending: 0
skipped: 0
blocked: 1

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
status: observation
severity: medium
reported: 2026-05-23T13:23:00Z
detail: |
  The only digest in `out/` (`digest-2026-W21.html`) was generated 2026-05-22 09:14,
  before plans 03-02..03-05 wired briefing/categories/rollup into the renderer.
  Current `pipeline/render/html.py` already implements:
    - `_render_briefing_section` (lines 554+)
    - `_render_category_sections` (lines 528+)
    - weekly + per-category rollup paragraphs (via `pipeline/llm/rollup.py`)
  Resolution: re-run `pipeline.run_all` for current week after UAT-FOLLOWUP-01
  is fixed. Not a code defect on its own.
