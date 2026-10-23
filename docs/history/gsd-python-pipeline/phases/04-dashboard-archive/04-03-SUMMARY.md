---
phase: 04-dashboard-archive
plan: "03"
subsystem: ui
tags: [astro, tailwind, zod, briefing, static-site, dark-theme]

requires:
  - phase: 04-dashboard-archive
    plan: "02"
    provides: digest JSON emitter and web/src/content/digests archive path
provides:
  - Astro 6 + Tailwind 4 web scaffold with Zod-validated content collections
  - Briefing landing at / with header, tabs, and numbered Top N cards
  - BaseLayout, Header, TabBar, Card components and week formatting helpers
affects: [04-04, 04-05, 04-06, topic-routes, archive-routes]

tech-stack:
  added: [astro@6.3.7, tailwindcss@4.3.0, @tailwindcss/vite@4.3.0, @astrojs/check]
  patterns:
    - "Content collections validate committed JSON at build; Astro reads pre-partitioned fields only"
    - "@tailwindcss/vite plugin (not @astrojs/tailwind); shadcn-shape CSS variables in globals.css"

key-files:
  created:
    - web/package.json
    - web/pnpm-lock.yaml
    - web/src/content.config.ts
    - web/src/styles/globals.css
    - web/src/layouts/BaseLayout.astro
    - web/src/components/Header.astro
    - web/src/components/TabBar.astro
    - web/src/components/Card.astro
    - web/src/pages/index.astro
    - web/src/lib/latestWeek.ts
    - web/src/lib/formatWeekRange.ts
  modified:
    - web/src/content/digests/2026-W21.json

key-decisions:
  - "pnpm approve-builds for esbuild/sharp via pnpm-workspace.yaml (pnpm 11 build-script gate)"
  - "@astrojs/check added as devDependency for astro check verification"
  - "2026-W21 digest/report JSON from pipeline render used as build smoke data"

patterns-established:
  - "getLatestDigest sorts week_id descending; formatWeekRange mirrors html.py _format_week_header"
  - "Card.astro same outer article structure for all summary_status; degraded_body slot only"

requirements-completed: [DISPLAY-01, DISPLAY-03, DISPLAY-05, DISPLAY-08]

duration: 25min
completed: 2026-05-23
---

# Phase 4 Plan 03: Astro Scaffold + Briefing Slice Summary

**Astro 6 + Tailwind 4 static site with Zod-validated digest collections and latest-week Briefing at /**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-23T22:53:00Z
- **Completed:** 2026-05-23T23:02:30Z
- **Tasks:** 2
- **Files modified:** 19

## Accomplishments

- Scaffolded `web/` with Astro 6.3.7, Tailwind 4 via `@tailwindcss/vite`, and Node 22 `.nvmrc`
- `content.config.ts` Zod schemas mirror `DigestDocument` (schema_version 1, pre-partitioned arrays) plus reports collection
- Dark theme CSS variables copied verbatim from UI-SPEC into `globals.css`
- `/` renders latest week Briefing: header (project name, week range, Updated), TabBar, weekly synthesis when present, numbered Top N cards
- External card links use `target="_blank" rel="noopener noreferrer"` (DISPLAY-08)
- `pnpm build` succeeds with `dist/index.html` containing 2026-W21 Briefing content

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold web/ with Astro 6, Tailwind 4, content collections** - `69dd420` (feat)
2. **Task 2: BaseLayout, Header, TabBar, Card, index Briefing slice** - `fc72c23` (feat)

**Plan metadata:** `0d16c74` (docs: complete plan)

## Files Created/Modified

- `web/package.json` - Astro 6 + Tailwind 4 dependencies; pnpm scripts
- `web/pnpm-lock.yaml` - Locked dependency tree
- `web/pnpm-workspace.yaml` - Approved esbuild/sharp build scripts
- `web/src/content.config.ts` - digests + reports Zod collections with glob loaders
- `web/src/styles/globals.css` - shadcn-shape dark tokens + Tailwind @theme
- `web/src/lib/latestWeek.ts` - newest week_id sort over getCollection
- `web/src/lib/formatWeekRange.ts` - Week of MMM D – MMM D, YYYY formatting
- `web/src/layouts/BaseLayout.astro` - 720px-ready shell, canonical link slot
- `web/src/components/Header.astro` - project name, week range, Updated, TabBar embed
- `web/src/components/TabBar.astro` - Briefing + topic tabs + Archive static links
- `web/src/components/Card.astro` - D-25 symmetric card; noopener external links
- `web/src/pages/index.astro` - latest-week Briefing from collection entry.data only

## Decisions Made

- Used `pnpm-workspace.yaml` allowBuilds for esbuild/sharp after pnpm 11 blocked postinstall scripts
- Added `@astrojs/check` devDependency so `pnpm astro check` runs non-interactively
- Rendered `2026-W21` digest JSON via pipeline for real collection smoke (not a hand fixture)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pnpm 11 build-script approval for esbuild/sharp**
- **Found during:** Task 1 (`pnpm install` / `pnpm astro check`)
- **Issue:** pnpm 11 ignored postinstall scripts; astro check failed on install gate
- **Fix:** `pnpm approve-builds esbuild sharp`; committed `pnpm-workspace.yaml` and `web/.npmrc`
- **Files modified:** web/pnpm-workspace.yaml, web/.npmrc
- **Verification:** `pnpm install` exits 0; build scripts run
- **Committed in:** `69dd420`

**2. [Rule 2 - Missing Critical] @astrojs/check for verification**
- **Found during:** Task 1 verify (`pnpm astro check`)
- **Issue:** Astro prompted interactively to install @astrojs/check
- **Fix:** `pnpm add -D @astrojs/check`
- **Files modified:** web/package.json, web/pnpm-lock.yaml
- **Verification:** `pnpm astro check` exits 0
- **Committed in:** `69dd420` (lockfile updated in scaffold commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical for verify)
**Impact on plan:** Required for local/CI build and plan verification commands. No scope creep.

## Issues Encountered

- `corepack` not on PATH; installed pnpm globally via npm instead
- Node on machine is v25 (`.nvmrc` pins 22 for team consistency)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 04-04 can add topic routes, main_feed, footer aside, PipelineNotes on Briefing
- Tab links to `/edtech`, `/business`, `/technical`, `/archive` exist but target pages not yet built (expected)
- PlayIcon inline SVG included in Card for YouTube items (DISPLAY-06 partial — dedicated PlayIcon.astro deferred to 04-04)

## Self-Check: PASSED

- FOUND: web/src/content.config.ts
- FOUND: web/dist/index.html (after build)
- FOUND: commit 69dd420
- FOUND: commit fc72c23

---
*Phase: 04-dashboard-archive*
*Completed: 2026-05-23*
