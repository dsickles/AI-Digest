---
phase: 04-dashboard-archive
plan: "07"
subsystem: ui
tags: [astro, canonical-url, archive, static-site, case-sensitivity]

requires:
  - phase: 04-dashboard-archive
    provides: Astro digest routes using digest.id slugs from content collections
provides:
  - Lowercase permalink slugs aligned with getStaticPaths across archive and canonical links
  - WR-01 gap closure for ARCHIVE-03 on case-sensitive static hosts
affects: [phase-5-publish, github-pages]

tech-stack:
  added: []
  patterns:
    - "URL slugs derive from digest.id (collection ID), not data.week_id JSON field"
    - "canonicalDigestUrl normalizes weekId with toLowerCase() as defense-in-depth"

key-files:
  created: []
  modified:
    - web/src/lib/canonicalUrl.ts
    - web/src/components/ArchiveList.astro
    - web/src/pages/index.astro
    - web/src/pages/[topic].astro

key-decisions:
  - "Fix slug case in web layer only — LOCKED-01 partition routing and Python emitters untouched"

patterns-established:
  - "Permalink hrefs and rel=canonical tags must match dist/digest/{digest.id}/ directory names case-exactly"

requirements-completed: [ARCHIVE-03]

duration: 5min
completed: 2026-05-23
---

# Phase 4 Plan 07: WR-01 Permalink Slug Normalization Summary

**Lowercase week permalink slugs via digest.id and canonicalDigestUrl.toLowerCase() so archive links and SEO canonicals match Astro-built routes on case-sensitive hosts**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-23T19:58:00Z
- **Completed:** 2026-05-23T20:00:00Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments

- Closed WR-01 from 04-VERIFICATION.md — archive Read this week hrefs and latest-week canonical tags use lowercase slugs matching `getStaticPaths` (`digest.id`)
- ARCHIVE-03 unblocked for Linux/GitHub Pages without touching LOCKED-01 partition routing
- Dist grep gate passes: no uppercase `2026-W` in archive hrefs; canonical tags on `/` and `/business` point to existing `dist/digest/2026-w*/` paths

## Task Commits

Each task was committed atomically:

1. **Task 1: WR-01 — normalize week URL slugs to digest.id (ARCHIVE-03)** - `98a5555` (fix)

**Plan metadata:** pending (docs commit)

## Files Created/Modified

- `web/src/lib/canonicalUrl.ts` — `weekId.toLowerCase()` before path interpolation
- `web/src/components/ArchiveList.astro` — href uses `digest.id`; removed unused `week_id` destructure
- `web/src/pages/index.astro` — `canonicalDigestUrl(digest.id)`
- `web/src/pages/[topic].astro` — `canonicalDigestUrl(digest.id, topicParam)`

## Decisions Made

None — followed plan as specified. LOCKED-01 compliance: zero edits under `pipeline/render/` or LOCKED-DIRECTIVES.md.

## Deviations from Plan

None - plan executed exactly as written

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 4 permalink URL truth can pass on re-verification
- Human UAT items in 04-VERIFICATION.md (archive click-through, canonical view-source) can confirm fix in browser
- Phase 5 publish target (case-sensitive static host) no longer blocked by slug mismatch

---
*Phase: 04-dashboard-archive*
*Completed: 2026-05-23*

## Self-Check: PASSED

- FOUND: web/src/lib/canonicalUrl.ts
- FOUND: web/src/components/ArchiveList.astro
- FOUND: web/src/pages/index.astro
- FOUND: web/src/pages/[topic].astro
- FOUND: commit 98a5555
