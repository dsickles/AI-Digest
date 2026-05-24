---
status: partial
phase: 04-dashboard-archive
source: ["04-VERIFICATION.md"]
started: 2026-05-24T00:05:03Z
updated: 2026-05-24T00:05:03Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. W19/W21 LOCKED-01 routing vs HTML dev preview
expected: JSON partition matches LOCKED-01; W21 footer_aside has no quota_exhausted titles. Run `render --week 2026-W19` and `render --week 2026-W21`; compare footer_aside (thin only) and main_feed quota_exhausted cards against `out/digest-*.html`.
result: [pending]

### 2. Tab navigation with JavaScript disabled
expected: Each tab is a static route; navigation works without client JS. Browse `/`, `/edtech`, `/business`, `/technical`, `/digest/2026-w21/edtech`.
result: [pending]

### 3. Mobile 375×667 layout on / and /archive
expected: No horizontal scroll; TabBar wraps two rows; header stacks vertically (D-A6c); matches UI-SPEC mobile stack order.
result: [pending]

### 4. Canonical tags on / and /business (view-source)
expected: After WR-01 fix, canonical hrefs match lowercase `/digest/{week}/…` paths that actually exist in dist.
result: [pending]

### 5. Archive index with two weeks
expected: After WR-01 fix, `/archive` lists W19 and W21 newest-first with excerpts; Read this week links resolve on case-sensitive host; empty clone shows "No past digests yet".
result: [pending]

### 6. Pipeline notes zero-state DOM absence
expected: Briefing on W21 has no `<details>` element; W19 shows `<details>` with summary line. Zero-state omits element from DOM (not CSS-hidden).
result: [pending]

### 7. YouTube play icon contrast (DISPLAY-06)
expected: Inline SVG play indicator with sufficient contrast on `#141820` card background on a main-feed YouTube card; no `[video]` text.
result: [pending]

### 8. Deprecated HTML dev preview path
expected: Rendering without `--no-html-preview` still writes `out/digest-2026-W21.html`; `html.py` carries DEPRECATED docstring; dev preview path still callable.
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0
blocked: 0

## Gaps
