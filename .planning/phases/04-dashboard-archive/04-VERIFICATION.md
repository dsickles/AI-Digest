---
phase: 04-dashboard-archive
verified: 2026-05-23T23:20:00Z
status: gaps_found
score: 34/35 must-haves verified
overrides_applied: 0
gaps:
  - truth: "ARCHIVE-03 — archive index and canonical links reach working week permalink URLs on case-sensitive hosts"
    status: failed
    reason: "Astro content collection IDs are lowercased (2026-w21) while ArchiveList and canonicalDigestUrl emit data.week_id with uppercase W (2026-W21). Built dist has pages at /digest/2026-w21/ but archive links and latest-week canonical tags point to /digest/2026-W21."
    artifacts:
      - path: web/src/components/ArchiveList.astro
        issue: "Line 38 href={`/digest/${week_id}`} uses JSON week_id, not digest.id slug"
      - path: web/src/lib/canonicalUrl.ts
        issue: "Returns /digest/{weekId} without lowercasing to match getStaticPaths params"
      - path: web/src/pages/index.astro
        issue: "canonicalHref={canonicalDigestUrl(data.week_id)} mismatches built permalink path"
      - path: web/src/pages/[topic].astro
        issue: "Same canonical case mismatch for topic permalinks"
    missing:
      - "Derive URL slugs from digest.id (or normalize weekId.toLowerCase()) in canonicalUrl.ts, ArchiveList.astro, index.astro, and [topic].astro"
human_verification:
  - test: "W19/W21 LOCKED-01 routing vs HTML dev preview — run render --week for both weeks; compare footer_aside (thin only) and main_feed quota_exhausted cards against out/digest-*.html"
    expected: "JSON partition matches LOCKED-01; W21 footer_aside has no quota_exhausted titles"
    why_human: "Visual diff across JSON, HTML preview, and rendered Astro pages requires human judgment"
  - test: "Tab navigation with JavaScript disabled — browse /, /edtech, /business, /technical, /digest/2026-w21/edtech"
    expected: "Each tab is a static route; navigation works without client JS"
    why_human: "Browser JS-disabled behavior cannot be verified by grep"
  - test: "Mobile 375×667 on / and /archive — no horizontal scroll; TabBar wraps two rows; header stacks vertically (D-A6c)"
    expected: "No horizontal scrollbar; layout matches UI-SPEC mobile stack order"
    why_human: "Responsive layout requires DevTools viewport inspection"
  - test: "Canonical tags on / and /business — view source for link rel=canonical"
    expected: "After WR-01 fix, canonical hrefs match lowercase /digest/{week}/… paths that actually exist in dist"
    why_human: "Post-fix canonical correctness needs browser view-source on deployed or preview build"
  - test: "Archive index with two weeks — /archive lists W19 and W21 newest-first with excerpts and Read this week links"
    expected: "After WR-01 fix, Read this week links resolve on case-sensitive host; empty clone shows No past digests yet"
    why_human: "Link navigation and excerpt rendering need human click-through"
  - test: "Pipeline notes zero-state DOM absence — Briefing on W21 has no details element; W19 shows details with summary line"
    expected: "Zero-state omits element from DOM (not CSS-hidden); W19 silent-source notes visible"
    why_human: "DOM presence vs CSS hiding requires browser inspector"
  - test: "YouTube play icon contrast (DISPLAY-06) on a main-feed YouTube card"
    expected: "Inline SVG play indicator with sufficient contrast on #141820 card background; no [video] text"
    why_human: "Visual contrast and glyph rendering; committed W19 YouTube item is footer-only (thin)"
  - test: "Deprecated HTML dev preview — render without --no-html-preview still writes out/digest-2026-W21.html"
    expected: "html.py DEPRECATED docstring; dev preview path still callable"
    why_human: "Confirm file presence and side-by-side with Astro output"
---

# Phase 4: Dashboard + Archive Verification Report

**Phase Goal:** Replace plain HTML with the dark tabbed Astro dashboard, full week-indexed archive, and observability surfaced where the reader looks  
**Verified:** 2026-05-23T23:20:00Z  
**Status:** gaps_found  
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Dark dashboard with header (name, week range, Updated) and Briefing + three topic tabs | ✓ VERIFIED | `Header.astro`, `TabBar.astro`, `globals.css` `color-scheme: dark`; build emits `/`, `/edtech`, `/business`, `/technical` |
| 2 | Briefing shows weekly roll-up, numbered Top N, Pipeline notes when signals exist | ✓ VERIFIED | `DigestBriefing.astro` → `WeeklySynthesis`, `BriefingTopN`; W19 dist has `<details>` pipeline notes; W21 `pipeline_notes: null` omits element |
| 3 | Story cards show title, TL;DR, publisher, links (new tab), date, YouTube play icon on cards | ✓ VERIFIED | `Card.astro` `target="_blank" rel="noopener noreferrer"`; `PlayIcon.astro` 16×16 SVG when `source_type === 'youtube'` |
| 4 | Digest JSON archived per week with schema_version 1 and pre-partitioned lists | ✓ VERIFIED | `2026-W21.json` has `schema_version: 1`, `main_feed`, `footer_aside`, `briefing_top_n`, `category_sections`; Zod in `content.config.ts`; `emit_digest_json` calls `_partition_cards` |
| 5 | Archive index newest-first with one-line excerpt | ✓ VERIFIED | `archive.astro` sorts `week_id` desc; `ArchiveList.astro` + `archiveExcerpt.ts` |
| 6 | Week permalink pages render full digest at `/digest/{week}` and `/digest/{week}/{topic}` | ✓ VERIFIED | `getStaticPaths` in `digest/[week].astro` and `[week]/[topic].astro`; 13 pages in build |
| 7 | Archive/canonical URLs resolve on case-sensitive hosts (ARCHIVE-03) | ✗ FAILED | Dist pages at `/digest/2026-w21/`; archive links and canonicals at `/digest/2026-W21` (WR-01) |
| 8 | LOCKED-01 routing only in Python; web has zero routing logic | ✓ VERIFIED | `_partition_cards` in `partition.py`; `web/src` reads pre-partitioned fields only; no `_partition` in web |
| 9 | Pipeline notes emitter: summary_line + details[], zero-state null, 3-week silent threshold | ✓ VERIFIED | `test_pipeline_notes.py` green; W19 JSON has notes; W21 null |
| 10 | `pnpm build` green; dist contains no secrets | ✓ VERIFIED | Build exit 0, 13 pages; grep dist for `GEMINI_API_KEY`/`sk-` empty |
| 11 | Full pytest suite green | ✓ VERIFIED | `.venv/bin/python -m pytest` exit 0 |
| 12 | Mobile-readable layout (DISPLAY-07) | ? UNCERTAIN | Tailwind responsive classes present (`flex-col`, `min-h-11`, `max-w-[720px]`); viewport check deferred to UAT |

**Score:** 34/35 must-haves verified (1 failed: permalink URL case on case-sensitive hosts)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pipeline/render/partition.py` | LOCKED-01 router | ✓ VERIFIED | `_partition_cards` routes only `thin` to footer; transient statuses in-place |
| `pipeline/render/digest_json.py` | Pre-partitioned JSON emitter | ✓ VERIFIED | `emit_digest_json` + `_build_pipeline_notes`; wired from orchestrator |
| `web/src/content.config.ts` | Zod collections schema_version 1 | ✓ VERIFIED | digests + reports collections |
| `web/src/pages/index.astro` | Latest-week Briefing | ✓ VERIFIED | Reads collection; no card routing |
| `web/src/pages/archive.astro` | ARCHIVE-02 index | ✓ VERIFIED | Sorted collection + `ArchiveList` |
| `web/src/pages/digest/[week].astro` | Archived Briefing permalinks | ✓ VERIFIED | Static paths from `digest.id` |
| `web/src/components/PipelineNotes.astro` | OBS-01 UI | ✓ VERIFIED | Native `<details>`; absent when null |
| `web/src/content/digests/2026-W21.json` | Integration fixture | ✓ VERIFIED | All required top-level fields present |
| `tests/render/test_pipeline_notes.py` | OBS-01 tests | ✓ VERIFIED | 17 render tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `orchestrator.py` | `digest_json.py` | `emit_digest_json` | ✓ WIRED | Pattern match in orchestrator render path |
| `digest_json.py` | `partition.py` | `_partition_cards` | ✓ WIRED | Called before serialize |
| `pipeline_report.py` | `web/src/content/reports/` | `{week_id}.json` | ✓ WIRED | `DEFAULT_ARCHIVE_DIR`; W19/W21 reports committed |
| `index.astro` | digest JSON | `getLatestDigest()` | ✓ WIRED | `getCollection('digests')` |
| `ArchiveList.astro` | permalink pages | `href=/digest/{week_id}` | ✗ NOT_WIRED | Case mismatch vs `digest.id` routes |
| `index.astro` | canonical permalink | `canonicalDigestUrl(data.week_id)` | ✗ NOT_WIRED | Canonical points to uppercase path |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `index.astro` | `digest.data.briefing_top_n` | `getLatestDigest()` → W21 JSON | Yes | ✓ FLOWING |
| `DigestBriefing.astro` | `data.category_sections[topic]` | Same digest entry | Yes (W19/W21) | ✓ FLOWING |
| `PipelineNotes.astro` | `data.pipeline_notes` | Emitter `_build_pipeline_notes` | Yes (W19); null zero-state (W21) | ✓ FLOWING |
| `ArchiveList.astro` | `digest.data.week_id` for href | JSON field | Yes but wrong slug case for URLs | ⚠️ HOLLOW_PROP |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Astro static build | `cd web && pnpm build` | 13 pages, exit 0 | ✓ PASS |
| Render tests | `.venv/bin/python -m pytest tests/render/ -q` | 17 passed | ✓ PASS |
| Full pytest | `.venv/bin/python -m pytest -q` | exit 0 | ✓ PASS |
| Secret grep on dist | `rg 'GEMINI_API_KEY\|sk-' web/dist` | no matches | ✓ PASS |
| Archive link vs page path | inspect `web/dist/archive/index.html` vs `web/dist/digest/` | links `2026-W21`, dirs `2026-w21` | ✗ FAIL |

### Probe Execution

Step 7c: SKIPPED — no phase-declared probe scripts.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| DISPLAY-01 | Dark header with name, week range, Updated | ✓ SATISFIED | `Header.astro`, dark `globals.css` |
| DISPLAY-02 | Briefing + Edtech/Business/Technical tabs | ✓ SATISFIED | `TabBar.astro` four section tabs + Archive |
| DISPLAY-03 | Briefing roll-up + numbered Top N | ✓ SATISFIED | `WeeklySynthesis`, `BriefingTopN` ordered list |
| DISPLAY-04 | Topic tabs show category stories | ✓ SATISFIED | `[topic].astro` → `CategorySection` |
| DISPLAY-05 | Card metadata (title, TL;DR, publisher, link, date) | ✓ SATISFIED | `Card.astro` |
| DISPLAY-06 | YouTube visual hint on cards | ✓ SATISFIED | `PlayIcon.astro` in `Card.astro`; no ytimg hosts |
| DISPLAY-07 | Mobile-readable | ? NEEDS HUMAN | Responsive Tailwind; UAT test 3 |
| DISPLAY-08 | Source links open new tab | ✓ SATISFIED | `target="_blank" rel="noopener noreferrer"` |
| ARCHIVE-01 | Digest JSON committed as source of record | ✓ SATISFIED | `web/src/content/digests/*.json`; `emit_digest_json` |
| ARCHIVE-02 | Archive index newest-first with excerpt | ✓ SATISFIED | `archive.astro`, `archiveExcerpt.ts` |
| ARCHIVE-03 | Permalink pages for past weeks | ✗ BLOCKED | Pages exist; archive/canonical links broken on case-sensitive hosts (WR-01) |
| ARCHIVE-04 | Past weeks reachable from nav | ✓ SATISFIED | TabBar Archive → `/archive` |
| OBS-01 | Pipeline notes on Briefing | ✓ SATISFIED | Emitter + `PipelineNotes.astro`; tests green |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `pipeline/render/partition.py` | 82–87 | Stale `DigestCard` docstring (WR-02) | ℹ️ Info | Misleading docs; implementation correct |
| `web/src/components/Card.astro` | 18 | Hardcoded degraded copy fallback (WR-03) | ℹ️ Info | Drift risk vs `QUOTA_BODY_COPY` |
| `web/src/components/PipelineNotes.astro` | 16 | Ignores `show: false` (IN-02) | ℹ️ Info | No current emitter path sets false |

No `TBD`/`FIXME`/`XXX` debt markers in phase-modified files.

### Code Review Cross-Reference (04-REVIEW.md)

**WR-01 (week URL case mismatch):** Confirmed in built output — **promoted to gap** (blocks ARCHIVE-03 on Linux/GitHub Pages). Not advisory.

**WR-02–WR-04, IN-01–IN-03:** Maintainability or Phase 5 scope — **advisory**, do not block phase goal once WR-01 is fixed.

### Human Verification Required

See frontmatter `human_verification` (8 items from `04-UAT.md`). Priority after gap closure: archive link click-through (test 5) and canonical tag inspection (test 4) to confirm WR-01 fix.

### Gaps Summary

Phase 4 delivers the Astro dashboard, JSON archive pipeline, LOCKED-01 partition extract, and OBS-01 pipeline notes end-to-end. One functional defect blocks clean exit: **week permalink URL case mismatch** (04-REVIEW WR-01). Astro builds routes at lowercase `digest.id` slugs while archive navigation and latest-week canonical tags use uppercase `week_id` from JSON. This works on case-insensitive macOS dev but breaks "Read this week" and canonical URLs on case-sensitive static hosts (the Phase 5 publish target).

**Fix scope:** Normalize slugs in `canonicalUrl.ts` and pass `digest.id` (not `data.week_id`) in `ArchiveList.astro`, `index.astro`, and `[topic].astro`.

---

_Verified: 2026-05-23T23:20:00Z_  
_Verifier: Claude (gsd-verifier)_
