---
phase: 04-dashboard-archive
plan: "04"
subsystem: ui
tags: [astro, static-routes, topic-tabs, archive, play-icon, locked-01]

requires:
  - phase: 04-dashboard-archive
    plan: "03"
    provides: Astro scaffold, TabBar, Card, content collections, Briefing index slice
provides:
  - Static routes for /{topic}, /digest/{week}, /digest/{week}/{topic} via getStaticPaths
  - BriefingTopN, CategorySection, FooterAside, PlayIcon, WeeklySynthesis presentational components
  - topics.ts and canonicalUrl.ts helpers mirroring partition.py
  - Full Briefing layout wired on index and archived week pages
affects: [04-05, 04-06, archive-index, pipeline-notes]

tech-stack:
  added: []
  patterns:
    - "TabBar weekPrefix prop switches latest-week bare URLs vs /digest/{week} permalinks"
    - "Astro reads pre-partitioned category_sections and footer_aside only — no client-side routing"
    - "PlayIcon inline SVG for YouTube; no external thumbnail hosts"

key-files:
  created:
    - web/src/lib/topics.ts
    - web/src/lib/canonicalUrl.ts
    - web/src/lib/copy.ts
    - web/src/components/BackToLatest.astro
    - web/src/components/BriefingTopN.astro
    - web/src/components/CategorySection.astro
    - web/src/components/DigestBriefing.astro
    - web/src/components/FooterAside.astro
    - web/src/components/PlayIcon.astro
    - web/src/components/WeeklySynthesis.astro
    - web/src/pages/[topic].astro
    - web/src/pages/digest/[week].astro
    - web/src/pages/digest/[week]/[topic].astro
  modified:
    - web/src/components/Card.astro
    - web/src/components/Header.astro
    - web/src/components/TabBar.astro
    - web/src/pages/index.astro

key-decisions:
  - "DigestBriefing shared fragment for index and /digest/{week} Briefing pages"
  - "CategorySection variant=topic omits category header on topic tab routes"
  - "Weekly rollup failure derived from weekly_synthesis.status !== ok when text absent"

patterns-established:
  - "canonicalDigestUrl(weekId, topic?) for latest-week canonical link tags"
  - "FooterAside consumes footer_aside[] only — link + meta, no card body (LOCKED-01)"

requirements-completed: [DISPLAY-02, DISPLAY-04, DISPLAY-06, ARCHIVE-03]

duration: 20min
completed: 2026-05-23
---

# Phase 4 Plan 04: Topic Routes + Briefing Components Summary

**Static multi-route tab navigation and full Briefing layout with inline YouTube play glyph and LOCKED-01 footer aside**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-23T23:04:00Z
- **Completed:** 2026-05-23T23:06:00Z
- **Tasks:** 2
- **Files modified:** 18

## Accomplishments

- Pre-rendered route table: `/`, `/{topic}`, `/digest/{week}`, `/digest/{week}/{topic}` (8 pages from one digest week)
- Latest-week pages emit `<link rel="canonical">` to `/digest/{week_id}` permalinks
- Archive-week pages show `← Latest week` back-link and TabBar hrefs prefixed with week permalink
- Full Briefing body: weekly synthesis or rollup-failure copy → Top N → category sections → footer aside
- PlayIcon.astro replaces inline SVG in Card; no `ytimg.com` or `[video]` text in dist

## Task Commits

Each task was committed atomically:

1. **Task 1: Static routes for topics and archived weeks** - `2c24a0e` (feat)
2. **Task 2: BriefingTopN, CategorySection, FooterAside, PlayIcon, WeeklySynthesis** - `959e118` (feat)

**Plan metadata:** `pending` → docs commit below

## Files Created/Modified

- `web/src/lib/topics.ts` — TOPICS enum + labels mirroring partition.py
- `web/src/lib/canonicalUrl.ts` — permalink helper for canonical tags
- `web/src/lib/copy.ts` — BRIEFING_HEADER_TEMPLATE and WEEKLY_ROLLUP_FAILURE_COPY
- `web/src/pages/[topic].astro` — latest-week topic tabs (3 getStaticPaths)
- `web/src/pages/digest/[week].astro` — archived Briefing with BackToLatest
- `web/src/pages/digest/[week]/[topic].astro` — archived topic permalinks
- `web/src/components/DigestBriefing.astro` — shared Briefing main column wiring
- `web/src/components/FooterAside.astro` — LOCKED-01 link-only footer from footer_aside[]
- `web/src/components/PlayIcon.astro` — 16×16 inline SVG for YouTube items

## Decisions Made

- CategorySection `variant="topic"` hides category header on topic tab pages (tab context conveys category per UI-SPEC)
- Partial-publish band rendered in DigestBriefing when failure_notice present (ahead of synthesis)
- Astro lowercases week_id in URL segments (`2026-w21`) — collection id preserved in data

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Initial import paths in `digest/[week].astro` and `digest/[week]/[topic].astro` needed one extra `../` level — fixed before task 1 commit

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 04-05 can add PipelineNotes.astro, PartialPublishNotice extraction, and `/archive` index
- TabBar Archive link exists; archive page not yet built (expected 04-05)
- main_feed[] not surfaced in UI yet (category_sections cover Briefing blocks)

## Self-Check: PASSED

- FOUND: web/src/pages/[topic].astro
- FOUND: web/src/components/PlayIcon.astro
- FOUND: web/dist/edtech/index.html
- FOUND: web/dist/digest/2026-w21/index.html
- FOUND: commit 2c24a0e
- FOUND: commit 959e118

---
*Phase: 04-dashboard-archive*
*Completed: 2026-05-23*
