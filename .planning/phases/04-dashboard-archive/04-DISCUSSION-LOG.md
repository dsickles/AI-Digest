# Phase 4: Dashboard + Archive - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-23
**Phase:** 04-dashboard-archive
**Mode:** default (interactive, no --auto / --power / --analyze / --text / --batch flags)
**Areas discussed:** Render pipeline split, Archive storage & backfill, Tabs + URL routing, Pipeline notes UI, Design system, Mobile / responsive, Video indicator polish

---

## Render pipeline split (Area 1)

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Pipeline writes raw JSON only; Astro re-implements LOCKED-01 in TypeScript | Clean separation; Astro owns presentation end-to-end. Duplicates the locked routing rule across two languages. | |
| (b) Pipeline writes BOTH JSON + HTML; HTML stays canonical; Astro consumes JSON | Belt-and-suspenders; LOCKED-01 lives in one Python place; two renderers to maintain. | |
| (c) Pipeline writes pre-partitioned JSON (LOCKED-01 stays in Python via `_partition_cards`); Astro is a dumb view | LOCKED-01 enforced structurally; Astro can't violate the rule because it never sees routing inputs. Opinionated JSON shape. | ✓ |
| (d) Astro wraps existing HTML (iframe / dangerouslySetInnerHTML) | Zero re-implementation; fails DISPLAY-01/02; rejected. | |

**User's choice:** (c) — Pre-partitioned JSON, LOCKED-01 stays in Python.
**Notes:** Question delivery was interrupted but user confirmed verbally going with the recommendation. Reasoning resonated with user: LOCKED-01 has been broken twice; duplicating the rule across Python + TypeScript is exactly the failure mode the lock exists to prevent. `pipeline/render/html.py` deprecated to dev-preview, not deleted.

---

## Archive storage & backfill (Area 2)

### Sub-decision 2a — Directory layout

| Option | Description | Selected |
|--------|-------------|----------|
| (a) `web/src/content/digests/{week_id}.json` + `web/src/content/reports/{week_id}.json` (Astro Content Collection convention) | Matches stack research + feedmeup reference; Zod validation at build. | ✓ |
| (b) Neutral `archive/` at repo root; Astro reads via loader | Decouples pipeline from Astro project layout. | |
| (c) Pipeline writes to `out/`; build step copies into Astro content | Preserves D-13 unchanged. | |

**User's choice:** (a)
**Notes:** D-13 narrows — `out/` stays gitignored for dev artifacts; canonical archive moves to committed content collection.

### Sub-decision 2b — Backfill existing W19 + W21?

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Backfill both from SQLite; use as integration test | Real archive history; tests emitter against both Phase 1 and Phase 3 era schemas. | ✓ |
| (b) Start fresh from W22 | Simpler; loses two real test cases. | |
| (c) Backfill W21 only | Compromise; arbitrary. | |

**User's choice:** (a)
**Notes:** Backfill IS the integration test. Emitter must tolerate `null` / sensible defaults for older schema rows.

### Sub-decision 2c — schema_version: 1 on per-week JSON?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — mirrors pipeline_report.json; Zod validates | Cheap insurance against future shape changes. | ✓ |
| No — skip; deal with shape changes ad-hoc | | |

**User's choice:** Yes

---

## Tabs + URL routing (Area 3)

### Sub-decision 3a — Tab mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| (a) React island via @astrojs/react + shadcn/Radix Tabs | Polished accessibility; ~30KB JS; deep linking needs extra wiring. | |
| (b) CSS-only via `:target` anchors | Zero JS; URL fragment is tab state; anchor scroll + hand-rolled ARIA. | |
| (c) Distinct static routes per tab (`/digest/[week]/[topic].astro`) | Pure HTML; full SSG; deep-linkable; pre-rendered weeks × tabs. | ✓ |

**User's choice:** (c)
**Notes:** Astro-as-content taken seriously. Eliminates need for `@astrojs/react` for v1.

### Sub-decision 3b — URL shape (first pass and re-ask)

First pass options offered:
| Option | Description | Selected |
|--------|-------------|----------|
| (a) Bare URL = latest; dated URLs for archive | `/` latest Briefing, `/digest/[week]` archive Briefing, etc. | (user asked clarifying question) |
| (b) Symmetric — Briefing has its own slug; `/digest/[week]` redirects to `/digest/[week]/briefing` | All tabs symmetric. | |
| (c) Query param `?tab=…` | Loses static generation per tab. | |

**User asked:** "what does the url for the latest week's topic look like?"

Re-asked with full shapes:
| Option | Latest Briefing | W21 Briefing | Latest Technical | W21 Technical | Selected |
|--------|---|---|---|---|---|
| (i) Bare = latest, fully symmetric | `/` | `/digest/2026-W21` | `/technical` | `/digest/2026-W21/technical` | ✓ |
| (ii) Bare only for Briefing | `/` | `/digest/2026-W21` | `/digest/2026-W21/technical` | `/digest/2026-W21/technical` | |
| (iii) Explicit `/latest/` prefix | `/` | `/digest/2026-W21` | `/latest/technical` | `/digest/2026-W21/technical` | |

**User's choice:** (i)
**Notes:** Bare URLs are the "Sunday morning bookmark" UX. Topic-collision risk is structurally a non-issue (closed enum of 3 topic slugs).

### Sub-decision 3b-extras — Back-link + canonical tag

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — both back-link on archive pages AND canonical tag on latest pages | Tiny details that pay off later for indexing + navigation. | ✓ |
| Back-link only | Skip canonical tag for v1. | |
| Neither | Minimal markup. | |

**User's choice:** Yes (both)

### Sub-decision 3c — What does `/` do?

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Render latest week's Briefing in place | No redirect; build-time picks newest week. | ✓ |
| (b) HTTP redirect to `/digest/[latest-week]` | Extra hop; cleaner symmetry. | |

**User's choice:** (a)

---

## Pipeline notes UI / OBS-01 (Area 4)

### Sub-decision 4a — Placement on Briefing

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Bottom of Briefing, after Top N + mini-rollups | Doesn't steal attention; less discoverable. | |
| (b) Top of Briefing above weekly synthesis, always rendered | Maximum discoverability; pushes content down. | |
| (c) `<details>`-based expandable element at top, building on D-26 | Native HTML; zero JS; accessible; drill-down on demand. | ✓ |
| (d) Sidebar / accordion | Big layout change. | |

**User's choice:** (c)
**Notes:** `<details>`/`<summary>` is native HTML, accessible by default, works on mobile.

### Sub-decision 4b — Which signals surface?

| Option | Description | Selected |
|--------|-------------|----------|
| Recommended set — failed sources + transcript-pending + quota/api/parse/init counts + budget halt; empty-feed only after 3+ silent weeks | Reader-relevant signals; cost numbers stay off. | ✓ |
| More inclusive — also single-week empty-feed + per-item cost | Maximum transparency; noisier. | |
| Less inclusive — only failed sources (literal OBS-01 text) | Skip aggregates that already live in D-26 header. | |

**User's choice:** Recommended set
**Notes:** Empty-feed 3+ consecutive weeks per D-41 silent-source threshold. Thin items already in footer aside.

### Sub-decision 4c — Copy style

| Option | Description | Selected |
|--------|-------------|----------|
| Plain-English per D-24; planner finalizes strings | No CLI / class names / codes on reader surface. | ✓ |
| Plain-English + 'show technical details' toggle | Power-user debugging affordance. | |

**User's choice:** Plain-English (no toggle)

---

## Design system (Area 5)

### Sub-decision 5a — Tokenization

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Adopt shadcn variable scheme wholesale + shadcn CLI install | React-component ecosystem overhead. | |
| (b) Keep existing palette as Tailwind theme tokens (no variables) | Bespoke; pure Tailwind. | |
| (c) Hybrid — shadcn-shape CSS variables seeded with existing palette converted to HSL | Visual continuity + ecosystem alignment; no CLI install. | ✓ |

**User's choice:** (c)

### Sub-decision 5b — Polish level

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Faithful pixel port | Same visuals as today's HTML inside Astro shell. | |
| (b) Faithful port + table-stakes polish (active tab, focus rings, hover, Briefing numbering weight) | UAT decides escalation. | ✓ |
| (c) Full reference-screenshot polish | Risks slipping the phase. | |

**User's choice:** (b)

### Sub-decision 5c — Light mode?

| Option | Description | Selected |
|--------|-------------|----------|
| Dark-only for v1 | PROJECT.md requirement. | ✓ |
| Both with toggle | Doubles design-token work. | |

**User's choice:** Dark-only

---

## Mobile / responsive (Area 6)

### Sub-decision 6a — Tab bar on narrow screens

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Horizontal scroll | Familiar; offscreen tabs invisible by default. | |
| (b) Wrap to two rows; all 4 visible | Nothing hidden; big touch targets. | ✓ |
| (c) Collapse to dropdown / select | Hides nav; dark-theme select styling hard. | |
| (d) Bottom-fixed tab bar on mobile | App-like; big departure. | |

**User's choice:** (b)

### Sub-decision 6b — Single column?

| Option | Description | Selected |
|--------|-------------|----------|
| Single 720px column at every viewport | Preserves linear Sunday-newspaper skim. | ✓ |
| Two-column grid on desktop, single on mobile | Parallel narratives; breaks skim model. | |

**User's choice:** Single column always

### Sub-decision 6c — Mobile header

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Stack vertically; no hamburger | Clarity over compactness for a weekly read. | ✓ |
| (b) Compact with hamburger nav | Maximum above-the-fold. | |
| (c) Stack project + week; tab bar with inline Archive link | Mixes "tab" and "link to other view." | |

**User's choice:** (a)

### Sub-decision 6d — Archive index layout

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Plain newest-first list at every viewport | Browse-back tool; simple. | ✓ |
| (b) Two-column grid on desktop, list on mobile | More content above the fold. | |
| (c) Compact table on desktop | Different mental model. | |

**User's choice:** (a)

---

## Video indicator polish (Area 7)

### Sub-decision 7a — Indicator form

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Play-icon glyph next to publisher badge | Compact; universal; scales to any video source. | ✓ |
| (b) Colored 'VIDEO' pill badge | Unambiguous; visually heavier. | |
| (c) Keep `[video]` text suffix; polish typography | Minimum diff. | |

**User's choice:** (a)

### Sub-decision 7b — YouTube thumbnails

| Option | Description | Selected |
|--------|-------------|----------|
| (a) No thumbnails for v1 | Preserves D-25 symmetry; no Google tracking pixels. | ✓ |
| (b) Thumbnails via `i.ytimg.com` | Visually richer; tracking pixel per load; breaks card symmetry. | |
| (c) Proxied/self-hosted thumbnails | Privacy-safe; binary churn in git history. | |

**User's choice:** (a)
**Notes:** If reintroduced later, MUST be build-time proxied; never direct hotlinking.

---

## Claude's Discretion

Per CONTEXT.md `<decisions>` section "Claude's Discretion" — the planner gets discretion on:

- Exact Astro project structure inside `web/`
- Exact JSON field-name conventions in `digest_json.py` (snake_case recommended for consistency with existing `pipeline_report.json`)
- Exact play-icon SVG path / asset source
- Exact CSS variable names (recommend keeping shadcn defaults verbatim)
- Whether to install Tailwind 4 via `@astrojs/tailwind` or `@tailwindcss/vite`
- Backfill execution path (recommend folding into the Phase 4 plan wave structure)
- Test framework on the Astro side (Vitest expected default)
- REQUIREMENTS.md DISPLAY-02 / DISPLAY-04 reconciliation mechanics (separate commit vs folded into first plan)

---

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section — full list there. Highlights:

- Light mode + toggle (v2)
- YouTube thumbnails build-time proxied (v1.5)
- Full-text archive search (DISPLAY-V2-01)
- Archive pagination / grouping-by-quarter (after ~52 entries)
- Tabs as a client-side widget (only if interactive need surfaces)
- Reading-time estimate / progress indicator
- shadcn CLI install + component primitives (if/when needed)
- Visual polish escalation ladder (driven by UAT)

---

## Incidental items surfaced during discussion (folded into CONTEXT.md)

These came up while discussing the seven areas but didn't fit any single area. All are captured in CONTEXT.md and the planner should handle them:

1. **REQUIREMENTS.md DISPLAY-02 / DISPLAY-04 staleness** — still lists 4 tabs including `Design`; reconcile to 3 per the PROJECT.md 2026-05-23 cut.
2. **`@astrojs/react` dependency probably unnecessary** — D-A3a (static distinct routes) removes the v1 need.
3. **D-13 narrowing** — `out/` stays gitignored for dev artifacts; canonical archive moves to `web/src/content/`. Update `.gitignore` accordingly.
4. **LOCKED-01 extension** — the pre-partitioned JSON shape is the structural enforcement; add the JSON-emitter partition function as a code anchor in `.planning/LOCKED-DIRECTIVES.md`.
5. **Backfill UAT** — open W19 + W21 in the new dashboard, verify LOCKED-01 routing matches, verify the older W19 schema rows don't crash the emitter.
6. **Astro / pnpm / Node scaffolding is its own work** — likely Wave 1 of the Phase 4 plan.
7. **UI-SPEC.md option** — offered to user via `/gsd-ui-phase 4`; user did not select (skipped final question), interpreted as "ready to write CONTEXT.md." If visual contract rigor is desired before planning, `/gsd-ui-phase 4` is still available.
