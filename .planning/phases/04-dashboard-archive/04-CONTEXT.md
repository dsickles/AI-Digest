# Phase 4: Dashboard + Archive - Context

**Gathered:** 2026-05-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the plain-HTML weekly digest renderer (`pipeline/render/html.py`) with a dark-themed Astro static dashboard, a per-week archive committed to git, and an OBS-01 Pipeline-notes surface on the Briefing tab. The Python pipeline stops producing the canonical HTML and instead writes a pre-partitioned per-week digest JSON to `web/src/content/digests/{week_id}.json`; Astro renders the JSON into a multi-page static site with bare-URL routing, native tab pages, and an archive index. The deliverable is the same content the Phase 3 pipeline already produces, now rendered as the dashboard the project was always aimed at — readable on Sunday morning, browseable backward indefinitely.

**In scope (Phase 4):**

- **New `web/` directory** scaffolded from scratch — Astro 6.x + Tailwind 4 + a `package.json` / `pnpm-lock.yaml` / `tsconfig.json` set; Node 22 LTS pinned via `.nvmrc`. No React island for Phase 4 (tabs are static distinct routes per D-A3a).
- **Pipeline `pipeline/render/digest_json.py`** — new module that consumes the Phase 3 `DigestCard` records + cluster artifacts and emits a pre-partitioned JSON shape: `{schema_version: 1, week_id, generated_at, week_range, updated_at, weekly_synthesis, briefing_top_n[], category_sections{edtech, business, technical}, main_feed[], footer_aside[], pipeline_notes{}}`. LOCKED-01 routing happens here via the same `_partition_cards` logic that `pipeline/render/html.py` uses today — extended, not duplicated. Output goes to `web/src/content/digests/{week_id}.json` (committed) and `web/src/content/reports/{week_id}.json` (committed, the per-week `pipeline_report` archive).
- **Astro Content Collections + Zod schema** validating both digest and report JSON shapes at build (`schema_version === 1` is hard-required; bumping requires migration).
- **Static route table** — `/` (latest week's Briefing), `/[topic]` (latest topic tab, where `[topic] ∈ {edtech, business, technical}`), `/digest/[week]` (archived week's Briefing), `/digest/[week]/[topic]` (archived week's topic tab), `/archive` (newest-first index of all past weeks). All pre-rendered at build via `getStaticPaths`. No client-side routing, no React.
- **Header component** — project name, week date range (`Week of MMM D – MMM D, YYYY`), `Updated …` timestamp, expandable `<details>`-based Pipeline-notes notice (D-26 evolved + OBS-01 per-source detail), nav row with tab links + Archive link. On archive pages, also a `← Latest week` link.
- **Briefing tab content** — weekly synthesis paragraph → numbered Top 5 → per-category mini-rollups + their ranked cards. Pipeline-notes `<details>` element sits at the top of `<main>`, collapsed at rest, hidden entirely when zero-state.
- **Topic tab content** — per-category mini-rollup + that category's ranked cards. Cards have no category badge (the tab context conveys it).
- **Archive index** — newest-first single-column list. Each row: week heading + first-sentence-of-weekly-synthesis excerpt (falling back to top-1 story title) + link.
- **Design tokens** — shadcn-shape CSS variables (`--background`, `--foreground`, `--card`, `--muted`, `--border`, `--accent`, `--destructive`) in `:root`, seeded with HSL conversions of the existing `pipeline/render/html.py` palette (`#0e1116`, `#141820`, `#2a3140`, `#e6e6e6`, `#9aa3b2`, `#7eb6ff`). Tailwind config maps the variables to utility classes. No shadcn CLI install for Phase 4.
- **Mobile responsiveness** — tab bar wraps to two rows; single 720px column always; header stacks vertically; archive index stays a list.
- **Video indicator polish** — DISPLAY-06: the existing `[video]` text suffix becomes an inline-SVG play-icon glyph next to the publisher badge. No YouTube thumbnails for v1.
- **Backfill of 2026-W19 + 2026-W21 from SQLite** — `python -m pipeline.run render --week 2026-W19` and `--week 2026-W21` emit the new JSON shape into the content collection. Acts as the integration test for the new emitter against real historic data.
- **REQUIREMENTS.md reconciliation** — DISPLAY-02 and DISPLAY-04 still list four tabs including `Design`; the planner reconciles them to the three-category reality (PROJECT.md 2026-05-23 decision; `pipeline/render/html.py::CATEGORY_ORDER` is the code anchor).
- **`pipeline/render/html.py` deprecation** — kept as a dev-preview path (callable from `python -m pipeline.run render`), explicitly marked deprecated. Stops being the publish surface. Not deleted in Phase 4 because removing it is independent of Phase 4's goals and creates churn; planner picks whether to mark `DEPRECATED` in a docstring or move to `pipeline/render/_legacy_html.py`.
- **D-22 discoverability triad** — every new pipeline subcommand / flag introduced (e.g., a `--web-out` override for the JSON emitter target, if introduced) ships with README + `--help` + UAT.

**Out of scope (Phase 4 — deferred):**

- **Cron / GitHub Actions / scheduled runs** — Phase 5 (OPS-01).
- **Cloudflare Pages deployment, custom domain, build CI** — Phase 5 (OPS-03). Phase 4 verifies via local `pnpm dev` + `pnpm build` only.
- **Secret hygiene + LLM hard $5/week cap + heartbeat + failure-only notifications** — Phase 5 (OPS-04, OPS-05, OBS-03).
- **Residential-IP worker / `--only-pending-transcripts` cron** — Phase 5 (per PROJECT.md Blocking Dependencies; the manual catch-up CLI from Plan 02-04 already exists, just not on a schedule).
- **Light mode + theme toggle** — v2 enhancement; PROJECT.md is explicit on dark-only for v1 (D-A5c).
- **YouTube thumbnails on cards** — deferred to v1.5 / v2 per D-A7b; if reintroduced, MUST be build-time proxied (no direct `i.ytimg.com` hotlinking).
- **Full-text archive search** — REQUIREMENTS DISPLAY-V2-01.
- **Multi-column card grid / two-up desktop layout** — D-A6b explicitly rejects this.
- **Q&A chat over the archive (RAG)** — REQUIREMENTS PIPELINE-V2-01.
- **Shareable read-only deep-link surfaces beyond plain URLs** — DISPLAY-V2-03.
- **Reference-screenshot-pixel-match polish** — D-A5b explicitly capped at "table-stakes polish"; further iteration escalates via a deferred polish ladder driven by UAT.
- **React island install (`@astrojs/react`)** — D-A3a removed the need; Phase 4 ships without it. Only revisit if a real interactive need surfaces.
- **Reading-time estimate, click-through analytics, social-share metadata** — none are in the locked requirements list; planner should not introduce.

**Locked requirements** (from REQUIREMENTS.md — Phase 4 implements all of these):

- **DISPLAY-01** — Dark-themed dashboard, header shows project name + current week date range + Updated timestamp.
- **DISPLAY-02** — Tabbed navigation: Briefing + topic tabs. *Note: REQUIREMENTS.md still lists four topics including `Design`; the actual contract is three (`edtech | business | technical`) per PROJECT.md 2026-05-23. Planner reconciles.*
- **DISPLAY-03** — Briefing shows weekly narrative roll-up + numbered Top N stories.
- **DISPLAY-04** — Topic tab shows that topic's stories for the current week. *Same Design-tab reconciliation note as DISPLAY-02.*
- **DISPLAY-05** — Story card shows title, TL;DR, publisher attribution(s), source link(s), per-item publication date.
- **DISPLAY-06** — YouTube items render with a visual hint (play-icon glyph per D-A7a).
- **DISPLAY-07** — Readable on desktop and modern mobile without layout breakage (D-A6a/b/c/d satisfy this).
- **DISPLAY-08** — Source links open in a new tab (`target="_blank" rel="noopener"` — already in `pipeline/render/html.py`; Astro components inherit).
- **ARCHIVE-01** — Every past weekly digest preserved as committed JSON (D-A2a satisfies).
- **ARCHIVE-02** — Archive index page lists every past week, newest first, with date range + one-line excerpt (D-A2a + D-A6d).
- **ARCHIVE-03** — Each past week has a permalink rendering the full digest as it appeared (D-A3b).
- **ARCHIVE-04** — Past weeks reachable from the live site nav (header `Archive` link).
- **OBS-01** — Briefing tab displays a Pipeline notes section listing sources that failed or were skipped, with one-line reasons (D-A4a/b/c).

</domain>

<decisions>
## Implementation Decisions

### Project-level rules carried forward (NOT re-decided here)

- **Carry LOCKED-01** — Footer-aside is `summary_status='thin'` only. The new pre-partitioned JSON shape (D-A1) is the STRUCTURAL enforcement of this rule for the Astro era: `footer_aside[]` and `main_feed[]` are pre-routed by the same `_partition_cards` function that today's `pipeline/render/html.py` uses. Astro cannot violate the rule because it never sees the routing inputs — only the pre-split lists. **The planner MUST add a note to `.planning/LOCKED-DIRECTIVES.md` LOCKED-01 acknowledging the new code anchor (the JSON emitter's partition function) alongside the existing `pipeline/render/html._partition_cards` reference.**
- **Carry D-24 (PROJECT-level — Reader-surface language)** — every string the dashboard renders is plain English. No `[T]`, no `cat:tech`, no CLI flag syntax, no file paths, no error class names. Applies to: category tab labels (the three enum strings `edtech | business | technical` render exactly as those words, capitalized for display: `Edtech / Business / Technical`), Pipeline-notes copy (D-A4c — planner finalizes a copy library mirroring D-25), rollup-failure copy (carries from D-66 verbatim), archive-page excerpt copy, "← Latest week" back-link.
- **Carry D-25 (PROJECT-level — In-place degradation, NOW subsumed by LOCKED-01)** — failed cards (`summary_status` in `_IN_PLACE_TRANSIENT_STATUSES`) render structurally identical to successful cards. The Astro card component MUST NOT branch its outer structure on summary_status; only the body copy slot changes. This is why D-A7b rejected YouTube thumbnails for v1 — adding an image area would break the structural-symmetry rule for the YouTube subset only.
- **Carry D-22 (PROJECT-level — Hidden capability discoverability)** — any new pipeline subcommand or flag introduced in Phase 4 (the JSON-emitter target override, the deprecated `html` preview command, any backfill helper) ships with README + `--help` + UAT.
- **Carry D-31 (PROJECT-level — Editorial Principle)** — the dashboard surfaces only named-entity sources. No community/crowd framing. Structural rather than enforcement since the v1 catalog has no such sources, but the principle gates any future UI proposal that would smuggle in engagement metrics or "trending" widgets.
- **Carry D-26 (Phase 2 — top-of-digest pipeline notice)** — the `<p class="pipeline-notice">` aggregate line that currently lives in `pipeline/render/html.py` header migrates into the Astro `<details><summary>` element. The aggregate line is the `<summary>`; the per-source breakdown (OBS-01) is the expanded panel. Zero-state hides the whole element.
- **Carry D-30 (Phase 2 — video content indicator)** — the structural intent stays (small, unambiguous, no card-structure change); the FORM evolves from `[video]` text to a play-icon glyph per D-A7a.
- **Carry D-58 / D-66 (Phase 3 — rollup-failure copy)** — `WEEKLY_ROLLUP_FAILURE_COPY` and `PARTIAL_PUBLISH_COPY` constants in `pipeline/render/html.py` move to the JSON emitter as data fields in `pipeline_notes` / a top-level `failure_notice` slot. The Astro component renders the strings verbatim per D-24.
- **Carry D-70 (Phase 3 — `pipeline_report.json` schema)** — the per-week `pipeline_report-{week_id}.json` already has the structure Phase 4 needs for OBS-01 (per-source health, error breakdown, summary_status counts, budget accounting). Phase 4 commits these into `web/src/content/reports/{week_id}.json`; no schema change required.

### Render pipeline split (Area 1)

- **D-A1:** **Pre-partitioned JSON, LOCKED-01 stays in Python.** New module `pipeline/render/digest_json.py` consumes the same `DigestCard` records + cluster artifacts that today's `pipeline/render/html.py` uses, runs them through the existing `_partition_cards` logic (extended for the JSON shape, not duplicated), and emits a per-week digest JSON to `web/src/content/digests/{week_id}.json`. The JSON shape is opinionated: `{schema_version: 1, week_id, generated_at, week_range: {start, end}, updated_at, weekly_synthesis: {text, status}, briefing_top_n: [DigestCardJson, ...], category_sections: {edtech: {mini_rollup, cards: [...]}, business: {...}, technical: {...}}, main_feed: [DigestCardJson, ...], footer_aside: [DigestCardJson, ...], pipeline_notes: {summary_line, by_source: [...], by_category: {...}}, failure_notice?: {kind, body}}`. Astro is presentational — its components receive pre-routed lists and never compute routing. **Drift between Python and TypeScript is impossible by construction.** `pipeline/render/html.py` is deprecated to a dev-preview path; the canonical publish surface becomes the Astro build.

### Archive storage (Area 2)

- **D-A2a:** **Canonical archive lives at `web/src/content/digests/{week_id}.json` + `web/src/content/reports/{week_id}.json` (committed to git).** Per-week digest JSON is the Astro Content Collection source; per-week pipeline report mirrors today's `pipeline-report-{week_id}.json` shape (D-70) into the same content tree. Astro Content Collections + Zod validate both at build. `out/pipeline_report.json` (always-latest, gitignored) is preserved for Phase 5 OBS-03 heartbeat. **D-13 narrows** — `out/` stays gitignored for fast-iteration dev artifacts (HTML preview, latest-only report); the canonical archive moves to `web/src/content/`.
- **D-A2b:** **Backfill W19 + W21 from SQLite.** `python -m pipeline.run render --week 2026-W19` and `--week 2026-W21` emit the new JSON shape into `web/src/content/digests/`. Backfill is the integration test for the new emitter against real historic data (W19 = Phase 1 era RSS-only no-cluster; W21 = Phase 3 era clustered + categorized + ranked + has actual `quota_exhausted` items). Emitter MUST tolerate `null`/sensible defaults for older `pipeline_runs` rows that pre-date Phase 3 columns. UAT: open both weeks in the Astro dashboard, verify LOCKED-01 routing matches the existing HTML output where comparable, verify the older W19 data doesn't crash the emitter.
- **D-A2c:** **`schema_version: 1` on per-week digest JSON.** Mirrors `schema_version: 1` already in `pipeline_report.json` (D-70). Astro Zod schema hard-requires `schema_version === 1`; future shape changes bump to `2` and require a migration step.

### Tabs + URL routing (Area 3)

- **D-A3a:** **Distinct static routes per tab — no React island.** Astro pre-renders `/digest/[week]/[topic].astro` for every (week × topic) at build via `getStaticPaths`. Tab navigation is `<a>` links to other static pages. Zero client-side state. Zero JS shipped for tabs. The `@astrojs/react` dependency recommended by `.planning/research/STACK.md` is NOT added for Phase 4 — there is no v1 interactive surface that requires React. Planner reconsiders only if a genuinely-interactive island need surfaces.
- **D-A3b:** **Full bare-URL symmetry for the latest week.** Route table:
  - `/` → latest week's Briefing tab (renders the newest week from the content collection, no redirect).
  - `/[topic]` → latest week's topic tab — `/edtech`, `/business`, `/technical`.
  - `/digest/[week]` → archived week's Briefing tab — e.g. `/digest/2026-W21`.
  - `/digest/[week]/[topic]` → archived week's topic tab — e.g. `/digest/2026-W21/technical`.
  - `/archive` → newest-first index of all past weeks.

  Topic slugs match the category enum exactly (`edtech | business | technical`). Tab nav uses bare URLs when rendering the latest week, dated URLs when rendering an archived week. Topic-collision risk is structurally non-issue (closed enum, controlled route table).

- **D-A3b-extras:** **Back-link + canonical tag.** Archive-week pages include a small `← Latest week` link in the header pointing at `/`. Latest-week pages (`/` and `/[topic]`) emit `<link rel="canonical" href="/digest/[week]" />` (or `/digest/[week]/[topic]`) so the durable, dated URL is the canonical address even when readers land on the bare URL.
- **D-A3c:** **`/` renders in place.** Build-time picks the newest week from the content collection and renders that week's Briefing at `/`. No HTTP redirect. The "Sunday morning bookmark" stays at `/`.

### Pipeline notes UI / OBS-01 (Area 4)

- **D-A4a:** **`<details>`-based expandable element at the top of `<main>`.** The `<summary>` element renders the existing D-26 plain-English aggregate line (e.g. `"3 video summaries pending"`). The expanded `<details>` panel renders the per-source / per-category breakdown. Native HTML — zero JS, accessible by default, mobile-friendly affordance. Zero-state hides the entire element (the D-26 rule is preserved). Position is "top of `<main>`, above the weekly synthesis" so the reader sees the aggregate signal first; expansion is opt-in.
- **D-A4b:** **What surfaces in Pipeline notes** — the locked signal set:
  1. **Sources that failed this week** — `last_error_category ∈ {fetch_timeout, fetch_http_error, parse_error, adapter_internal}` for the current `week_id`. Per-source plain-English line.
  2. **Pending-local transcript count** (aggregate) — number of items with `transcript_status='pending_local'`; expansion names each channel.
  3. **Quota / API / parse / init error counts** (aggregate) — `summary_status` counts from `pipeline_report.json` for `{quota_exhausted, api_error, parse_error, client_init_error}`. Per-source attribution where available.
  4. **Budget-halt notice** — when `pipeline_report.json::budget.halted === true`, render the partial-publish notice (carrying `PARTIAL_PUBLISH_COPY` from `pipeline/render/html.py` — moved to the JSON emitter as a data field).

  **What does NOT surface here:**

  - **Empty-feed sources** (single week) — single weeks of `empty_feed` are normal (HTTP 304 or genuinely no new items). Only after **3+ consecutive empty weeks** (D-41 silent-source detection threshold) does a source surface as a Pipeline-notes entry. The planner adds the consecutive-week counter to the JSON emitter — reads from `pipeline_runs` history.
  - **Thin RSS items** — already in the footer aside per LOCKED-01.
  - **LLM cost / token counts / spend numbers** — Phase 5 OBS-03 surface; not for the reader.

- **D-A4c:** **Plain-English copy library.** Planner finalizes the exact strings in the D-25 / D-58 voice. Examples (planner adjusts wording within the D-24 constraint):
  - *"Where's Your Ed At didn't publish for the third week in a row."* (silent-source, 3+ empty weeks)
  - *"Ben's Bites couldn't be reached this Sunday morning. The next run will retry."* (fetch_timeout)
  - *"3 video transcripts will fill in when the digest is refreshed from a different network."* (pending_local aggregate)
  - *"2 summaries hit the weekly LLM budget and weren't generated this run."* (quota_exhausted aggregate)
  - *"The pipeline reached its weekly cost cap before finishing every summary. This digest reflects what completed before the cap."* (budget halt — verbatim from `PARTIAL_PUBLISH_COPY`)

### Design system (Area 5)

- **D-A5a:** **Hybrid token strategy — shadcn-shape CSS variables seeded with the existing palette.** `:root` defines the standard shadcn variable names (`--background`, `--foreground`, `--card`, `--card-foreground`, `--muted`, `--muted-foreground`, `--border`, `--accent`, `--accent-foreground`, `--destructive`) with HSL values converted from the existing `pipeline/render/html.py` palette. Tailwind config maps the variables to utility classes (`bg-background`, `text-foreground`, `border-border`, etc.). **No shadcn CLI install for Phase 4** — we use the variable convention, not the component library. The door is open for shadcn components in a future phase if needed. Visual continuity with the existing renderer is day-one identical.
- **D-A5b:** **Faithful port + table-stakes polish.** Phase 4 ships a visually equivalent dark theme to today's `pipeline/render/html.py`, plus:
  - Header with project name + week date range + Updated timestamp + nav.
  - Tab bar with clear visible active state.
  - Focus rings on all interactive elements (accessibility baseline).
  - Hover affordances on cards and tab links.
  - Tighter visual weight on the Briefing Top-N numbering (the number should feel like a real ordinal, not body copy).

  Phase 4 does NOT chase reference-screenshot pixel match. If UAT says the visual needs more polish, escalate via a deferred polish ladder (more whitespace, denser typographic hierarchy, decorative section dividers — none of which are blocking for Sunday-morning skim).

- **D-A5c:** **Dark-only.** PROJECT.md explicit. Light mode is a v2 enhancement; if added, it requires splitting design tokens by mode + a toggle + doubled UAT surface.

### Mobile / responsive (Area 6)

- **D-A6a:** **Tab bar wraps to two rows on narrow screens.** With Briefing + 3 topic tabs (4 items), wrapping is cheap visually and means **nothing is hidden** on mobile. No horizontal scroll, no collapsed dropdown, no bottom-fixed bar. Touch targets stay >= 44pt.
- **D-A6b:** **Single 720px column at every viewport.** No multi-column card grid at any breakpoint. Side padding scales down on mobile. Preserves the linear "Sunday newspaper skim" model.
- **D-A6c:** **Mobile header stacks vertically.** Order: project name → week range → Updated timestamp → expandable pipeline notice (collapsed at rest) → nav row (tabs + Archive). No hamburger menu. For a once-weekly read, clarity beats above-the-fold compactness.
- **D-A6d:** **Archive index is a plain single-column list at every viewport.** Each row: `Week of MMM D – MMM D, YYYY` heading + one-line excerpt (first sentence of the weekly synthesis, falling back to the top-1 story title) + link. No grid, no compact table. Pagination/grouping-by-quarter deferred to v1.5 when the archive grows past ~52 entries.

### Video indicator polish (Area 7)

- **D-A7a:** **Play-icon glyph next to the publisher badge.** Replaces the existing `[video]` text suffix from D-30. Inline-SVG implementation (via `astro-icon` or hand-authored — planner picks; no React dependency required because tabs are static routes per D-A3a). Subtle muted accent color matching the `--muted-foreground` token. Universally recognizable. Scales to any future video source (Loom, conference talks, podcast video).
- **D-A7b:** **No YouTube thumbnails on cards for v1.** Three reasons: (1) preserves D-25 structural symmetry between successful and failed cards (adding an image area for the YouTube subset only would break this); (2) every external image load is a Google tracking pixel, at odds with the project's "personal, off-network" framing; (3) the play-icon glyph (D-A7a) already gives the at-a-glance video signal cheaply. **Deferred to v1.5 / v2** — if reintroduced, the build-time-proxied option (pipeline downloads thumbnails to `web/public/thumbs/{videoId}.jpg`, commits them, Astro serves locally) is the right shape. **NO direct `i.ytimg.com` hotlinking.**

### Claude's Discretion

- **Exact Astro project structure inside `web/`** — Phase 4 specifies the route table, content collection schemas, design tokens, and component contracts. The exact directory layout under `web/src/components/`, naming conventions for component files (PascalCase `.astro` files, presumably), and how shared bits (the card component, the header, the footer aside) get factored is planner discretion. Reference: `.planning/research/ARCHITECTURE.md` §Static-First Pattern shows the feedmeup layout (`src/pages/{...}.astro`, `src/components/`, `src/content/digests/`) as a starting point.
- **Exact JSON field names in `digest_json.py`** — D-A1 locks the structural shape (`schema_version, briefing_top_n, category_sections, main_feed, footer_aside, pipeline_notes, ...`). The exact field-name conventions (camelCase vs snake_case, nested `week_range: {start, end}` vs flat `week_start / week_end`, etc.) are planner discretion subject to D-A2c (`schema_version: 1` for the locked shape, Zod schema enforcement at build). Recommend matching the existing `pipeline_report.json` snake_case convention for consistency.
- **Exact play-icon SVG path / asset source** — D-A7a locks the form (play-icon glyph, inline SVG, muted accent color, near publisher badge). Whether it comes from `astro-icon` + Lucide, a hand-authored 16×16 inline SVG, or another icon source is planner discretion.
- **Exact CSS variable names for the design tokens** — D-A5a locks the shadcn-shape convention. Whether the variables are named exactly `--background / --foreground / --card / ...` (shadcn defaults) or slightly adapted (`--bg / --fg / --card-bg / ...`) is planner discretion. Recommend keeping shadcn defaults verbatim so future component imports drop in cleanly.
- **Whether to install Tailwind 4 via the official `@astrojs/tailwind` integration or via `@tailwindcss/vite`** — STACK.md mentions both; planner picks based on current 2026-05 docs. The behavior is equivalent.
- **Backfill execution path** — D-A2b says backfill W19 + W21. Whether that runs as part of the Phase 4 plan's wave structure (likely Wave N: "backfill historic weeks as the integration test") or as a one-off operator action after Phase 4 ships is planner discretion. Recommendation: include in the plan so the integration test runs in CI / locally and the dashboard ships with two real archived weeks already viewable.
- **Test framework choices, UAT checklist additions** — Phase 1–3 set the pytest precedent for pipeline-side tests. The Astro side will likely use the framework Astro recommends (Vitest is the current default). UAT must explicitly include: (1) backfill W19 + W21 and visually compare against the existing HTML output; (2) verify LOCKED-01 routing on a synthetic week mixing all `_IN_PLACE_TRANSIENT_STATUSES` values; (3) tab navigation works without JS (browse with JS disabled — should still work because tabs are static routes); (4) mobile viewport (375px) renders without horizontal scroll; (5) `/` + `/[topic]` canonical tags resolve to the dated permalinks; (6) archive index renders correctly with 2 weeks initially (W19 + W21), and gracefully when there are 0 archived weeks (edge case for fresh setups).
- **REQUIREMENTS.md reconciliation mechanics** — D-A3 / phase boundary says the planner reconciles DISPLAY-02 / DISPLAY-04 (4 tabs → 3) to match PROJECT.md. Whether that's a separate `docs(req): reconcile DISPLAY-02/04 to 3-category reality` commit or folded into the first plan's commit is planner discretion. The text edit itself is mechanical (strike `Design` from the tab list).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level gates (MANDATORY first reads)

- `.planning/LOCKED-DIRECTIVES.md` — **MANDATORY first read** for any plan/research artifact. LOCKED-01 governs every reader-surface routing decision in Phase 4. The new pre-partitioned JSON shape (D-A1) is the STRUCTURAL enforcement; the planner MUST update LOCKED-01's "Code anchors" section to add the JSON emitter's partition function alongside the existing `pipeline/render/html._partition_cards` reference.
- `.planning/PROJECT.md` §What This Is + §Editorial Principle + §Key Decisions + §Pre-public-release Privacy Sweep — the "dark-themed dashboard, three topic tabs" framing comes from here. The 2026-05-23 cut of the `design` category lives in §Key Decisions and is the canonical source for DISPLAY-02 reconciliation. The Privacy Sweep section means no infrastructure-identifying detail enters any new doc / code / commit message.

### Phase boundary, requirements (planner reads first)

- `.planning/ROADMAP.md` §Phase 4 — locked phase goal, success criteria (especially SC #1 dark dashboard + tabbed nav, SC #2 Briefing + Pipeline notes, SC #4 archive index + permalinks, SC #5 mobile + desktop), the requirements list (DISPLAY-01..08, ARCHIVE-01..04, OBS-01), and the locked dependency on Phase 3.
- `.planning/REQUIREMENTS.md` §Presentation + §Archive + §Observability — full text of DISPLAY-01..08, ARCHIVE-01..04, OBS-01. **NOTE the known stale text** in DISPLAY-02 and DISPLAY-04 (lists 4 tabs including `Design`); planner reconciles to 3 per the PROJECT.md 2026-05-23 decision.

### Stack + architecture + research

- `.planning/research/STACK.md` §1 (Executive Recommendation) + §3.1 (Astro 6.x) + §6 (Tailwind + shadcn approach) + §7 (Cloudflare Pages) — primary stack guidance. **Phase 4 deviates from STACK.md in two places:** (1) no `@astrojs/react` install per D-A3a (tabs are static routes; no React island needed for v1); (2) no shadcn CLI install per D-A5a (we use the variable convention without installing the component library).
- `.planning/research/ARCHITECTURE.md` §Components + §Static-First Pattern + §Data Model (the "Working store vs Published archive" split) + §Build Order step 7–8 (site shell + archive routes) — the `web/content/digests/` content-collection layout is the architectural anchor for D-A2a. The feedmeup reference (`web/content/digests/2026-W21.json` committed) is the precedent.
- `.planning/research/SUMMARY.md` — the static-first publish model + the personal-scale framing.
- `.planning/research/PITFALLS.md` #19 (archive growth) — explicitly informs D-A6d ("plain list at every viewport; pagination/grouping deferred until ~52 entries"). PITFALLS #5 (secret hygiene) is relevant later for Phase 5 deploy but Phase 4 must already follow it — no `GEMINI_API_KEY` anywhere in the static build output, no `.env` content rendered in any Astro component.

### Phase 1 + 2 + 3 decisions still in force

- `.planning/phases/01-foundation-first-digest/01-CONTEXT.md` — D-04 (versioned prompts / `prompt_version` on every LLM artifact), D-09 (`pipeline_runs` substrate), D-11 (week_id parameterization, no `datetime.now()` inside modules — Phase 4's JSON emitter respects this), D-13 (`out/` is ephemeral — **narrowed in Phase 4 per D-A2a**: `out/` stays gitignored for dev artifacts; canonical archive moves to `web/src/content/`), D-22 (discoverability triad), D-15 (degraded-cards display contract — superseded by LOCKED-01).
- `.planning/phases/02-expand-ingestion/02-CONTEXT.md` — D-24 (reader-surface plain English — gates every string Phase 4 renders), D-25 (in-place degradation — gates the card-structural-symmetry rule that D-A7b cites for rejecting thumbnails), D-26 (top-of-digest pipeline notice — evolves into the `<details>` element in D-A4a), D-30 (video indicator — form evolves in D-A7a; intent preserved), D-36 (discriminated-union source config — Phase 4 doesn't touch it but the `source_type` field on `DigestCard` flows through to the JSON shape), D-39 / D-40 (typed `RunStats.errors` + source-health columns — Phase 4 reads these for OBS-01 per-source notes), D-41 (empty-feed contract / silent-source after 3+ weeks — gates D-A4b's empty-feed surfacing rule).
- `.planning/phases/03-ai-quality/03-CONTEXT.md` — D-43..D-71 in their entirety apply to the data Phase 4 displays. Highest-relevance carries:
  - **D-50** (anti-slop voice / ban list) — applies to any new copy Phase 4 introduces (Pipeline-notes copy library, archive excerpt phrasing).
  - **D-55 / D-56 / D-57** (hierarchical rollup structure + length + voice) — the weekly synthesis and per-category mini-rollups Phase 4 renders are already produced by Phase 3; Phase 4 just lays them out.
  - **D-58 / D-66** (rollup-failure copy) — the strings `WEEKLY_ROLLUP_FAILURE_COPY` and `PARTIAL_PUBLISH_COPY` move from `pipeline/render/html.py` into the JSON emitter as data fields; the Astro component renders them verbatim.
  - **D-63 / D-64 / D-65** (Briefing Top-N + Also-covered-by + per-section category headers) — class-name-compatibility was an explicit Phase 3 design intent so Phase 4 styles cleanly; the new Astro components honor the same semantic boundaries.
  - **D-67 / D-68** (hybrid checkpointing + cascading invalidation) — Phase 4's backfill of W19 + W21 (D-A2b) MUST use the existing checkpoint-aware orchestrator entry points; no new re-summarize triggered just because the JSON emitter changed.
  - **D-69 / D-70** (`pipeline_report.json` location + schema) — Phase 4 commits the per-week report into `web/src/content/reports/{week_id}.json`. The schema (D-70) is already what OBS-01 needs; no shape change required.

### Existing code Phase 4 will extend or revise

- `pipeline/render/html.py` — the deprecated target. Phase 4 keeps it as a dev-preview path (marked DEPRECATED). The `_partition_cards` function is the LOCKED-01 router; the new `digest_json.py` calls it (or extracts the shared partition logic into a module both can import — planner picks). Constants `QUOTA_BODY_COPY`, `WEEKLY_ROLLUP_FAILURE_COPY`, `PARTIAL_PUBLISH_COPY`, `BRIEFING_HEADER_TEMPLATE`, `CATEGORY_ORDER`, `CATEGORY_LABELS`, `ALSO_COVERED_PREFIX`, `ALSO_COVERED_SEPARATOR`, `VIDEO_INDICATOR`, `_IN_PLACE_TRANSIENT_STATUSES` move to (or are referenced from) the JSON emitter so the Astro components consume them as data.
- `pipeline/render/__init__.py` — exposes whichever entry points the new layout requires. Planner picks the public surface (`emit_digest_json(week_id) -> Path`, etc.).
- `pipeline/orchestrator.py` — `_render_week` (or equivalent — the existing call chain that produces `out/digest-{week_id}.html`) now also produces `web/src/content/digests/{week_id}.json` + `web/src/content/reports/{week_id}.json`. The `run_render` public entry point grows a parameter (or the new emitter is wired into `run_all` directly). Backfill commands for W19 + W21 use the same `run_render` path with `--week`.
- `pipeline/reporting/pipeline_report.py` — already emits `pipeline-report-{week_id}.json` to `out/`. Phase 4 adds an output path under `web/src/content/reports/` (committed) alongside the existing `out/` write. The shape stays per D-70.
- `pipeline/run.py` — CLI surface: the existing `python -m pipeline.run render --week …` subcommand now produces both the dev preview HTML and the canonical Astro JSON. New `--no-html-preview` / `--web-only` flags (planner picks names) for explicit control. D-22 triad: README + `--help` + UAT entries for any new flags.
- `pipeline/orchestrator.py::DigestCard` (currently in `pipeline/render/html.py`, may move) — the in-memory card record that flows into the renderer. The JSON emitter serializes this record into the `DigestCardJson` shape (planner picks the exact serialization — Pydantic model + `.model_dump()` is the clean path).
- `store/db.py` — read-only for Phase 4 (no new tables, no new migrations). Existing tables (`items`, `item_summaries`, `story_clusters`, `cluster_members`, `cluster_summaries`, `cluster_ranks`, `weekly_rollups`, `sources`, `pipeline_runs`) provide everything Phase 4 needs.
- `.gitignore` — refines: `out/` stays ignored (dev artifacts); `web/node_modules/` added; `web/.astro/` added; `web/dist/` added (build output, Phase 5 publishes this to Cloudflare Pages); explicitly DO NOT ignore `web/src/content/digests/` or `web/src/content/reports/` (these are the committed archive).
- **New module `pipeline/render/digest_json.py`** — the JSON emitter. Mirrors the shape of `pipeline/render/html.py` (same input data, same `_partition_cards` routing, different output: JSON instead of HTML). Pydantic models for the output schema; serializes to per-week JSON.
- **New directory `web/`** — Astro project root. Phase 4 scaffolds it from scratch.
  - `web/package.json` — Astro 6.x + Tailwind 4 + `astro-icon` (or equivalent) deps; no `@astrojs/react`.
  - `web/pnpm-lock.yaml` — pnpm lock; commit it.
  - `web/.nvmrc` — Node 22 LTS.
  - `web/astro.config.mjs` — content collection config, Tailwind integration.
  - `web/tsconfig.json` — TS config (Astro default).
  - `web/src/content/digests/{week_id}.json` — per-week digest JSONs (committed; the archive of record).
  - `web/src/content/reports/{week_id}.json` — per-week pipeline reports (committed).
  - `web/src/content/config.ts` — Zod schemas for `digests` + `reports` collections, validating `schema_version === 1`.
  - `web/src/pages/index.astro` — latest week's Briefing.
  - `web/src/pages/[topic].astro` — latest week's topic tab (statically generates for the 3 topic slugs).
  - `web/src/pages/digest/[week].astro` — archived week's Briefing (`getStaticPaths` from the content collection).
  - `web/src/pages/digest/[week]/[topic].astro` — archived week's topic tab.
  - `web/src/pages/archive.astro` — newest-first archive index.
  - `web/src/components/` — `Header.astro`, `TabBar.astro`, `Card.astro`, `BriefingTopN.astro`, `CategorySection.astro`, `FooterAside.astro`, `PipelineNotes.astro`, `PlayIcon.astro` (or inline-SVG component), `BackToLatest.astro` (planner picks the final component split).
  - `web/src/styles/globals.css` — Tailwind 4 entrypoint + `:root` CSS variable definitions (the design tokens).
  - `web/src/lib/` — helpers (latest-week resolver, week-range formatter, canonical-URL emitter).
- **No `web/public/`** beyond the Astro defaults — no thumbnails directory, no fonts (system stack only), no images.

### Process & state

- `.planning/STATE.md` — pending todos list will be updated by this session (no new folded todos; existing pending items unchanged).
- `.planning/phases/04-dashboard-archive/04-DISCUSSION-LOG.md` — full audit trail of options considered in this session (human-only, not consumed by downstream agents).

No external ADRs, vendor specs, or third-party design docs were referenced during this discussion; everything is contained in the `.planning/` tree above plus the in-repo research artifacts and the existing pipeline code.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`pipeline/render/html.py::_partition_cards`** — the LOCKED-01 router. The single source of truth for "thin → footer, everything else → main feed in-place degraded." D-A1 extends (or shared-module extracts) this function as the partition logic the new JSON emitter calls. Astro never re-implements this routing.
- **`pipeline/render/html.py::DigestCard`** dataclass — the in-memory card record that the orchestrator builds. The JSON emitter consumes the same record; the Astro components consume the JSON serialization of it.
- **`pipeline/render/html.py` constants** — `QUOTA_BODY_COPY`, `WEEKLY_ROLLUP_FAILURE_COPY`, `PARTIAL_PUBLISH_COPY`, `BRIEFING_HEADER_TEMPLATE`, `CATEGORY_ORDER`, `CATEGORY_LABELS`, `ALSO_COVERED_PREFIX`, `ALSO_COVERED_SEPARATOR`, `_IN_PLACE_TRANSIENT_STATUSES`. All flow into the JSON as data fields; Astro renders them verbatim. The Python module remains the single source-of-truth for the locked copy strings.
- **`pipeline/render/html.py` CSS block** — the existing palette (`#0e1116`, `#141820`, `#2a3140`, `#e6e6e6`, `#9aa3b2`, `#7eb6ff`, `#1f2630`, `#c8cdd5`, `#6b7280`, `#4a5260`, `#8b6914`, `#1a1610`, `#c8b896`) is the literal source for D-A5a's HSL conversion. The planner runs each through a hex→HSL conversion (e.g., `#0e1116` → `220 17% 7%`) and seeds the CSS variables in `web/src/styles/globals.css`.
- **`pipeline/reporting/pipeline_report.py`** — already emits the D-70 schema. Phase 4 adds a second output target (`web/src/content/reports/{week_id}.json`) in addition to the existing `out/pipeline-report-{week_id}.json`.
- **`pipeline/orchestrator.py::RunStats`** — accumulates per-stage cost, errors, summary-status counts. Phase 4's emitter reads from the persisted `pipeline_runs` row (D-09 / D-69 — `pipeline_runs` is the substrate, `pipeline_report.json` is the projection); no orchestrator changes for Phase 4.
- **`pipeline/week.py::week_bounds` / `parse_week_id`** — the week-range header in the dashboard reads from `week_bounds(week_id)`. No changes needed; just a new call site in the JSON emitter.

### Established Patterns Phase 4 extends or relies on

- **LOCKED-01 routing centralization** — `_partition_cards` is the only function that may make a "footer vs main vs in-place degraded" decision. Phase 4 strengthens this by making it STRUCTURALLY impossible for Astro to violate the rule (the JSON pre-routes; Astro only sees the lists).
- **D-04 versioned prompts / `prompt_version` + `model_id` persistence** — every LLM artifact the dashboard renders carries these fields. The JSON emitter passes them through into the per-card / per-rollup JSON objects so Phase 5's heartbeat / observability can attribute LLM output to specific prompt versions.
- **D-09 `pipeline_runs` substrate** — `pipeline_report.json` is a projection. Phase 4 commits a second projection (per-week, into `web/src/content/reports/`). SQLite remains source of truth for cross-week queries.
- **D-13 narrowing** — `out/` stays ephemeral for dev artifacts; canonical archive lives at `web/src/content/`. Planner updates `.gitignore` accordingly.
- **D-22 discoverability triad** — every new CLI flag introduced (e.g., emitter target override, dev-preview suppress) ships with README + `--help` + UAT.
- **D-24 reader-surface plain English** — gates every string Phase 4 renders in any of the new Astro components.
- **D-25 / LOCKED-01 card structural symmetry** — the Astro `Card.astro` component MUST NOT branch its outer structure on summary_status. Only the body slot changes (full TL;DR vs locked degraded copy). Cited explicitly in D-A7b as the reason for rejecting per-card thumbnails on YouTube items.
- **D-26 pipeline notice → `<details>` evolution** — the aggregate plain-English line is preserved; the expanded panel is new (OBS-01 surface).
- **D-70 `pipeline_report.json` schema versioning (`schema_version: 1`)** — mirrored in the new digest JSON per D-A2c.

### Integration Points

- **JSON emitter ↔ orchestrator** — the new `pipeline/render/digest_json.py` is called from `pipeline/orchestrator._render_week` (or wherever the existing HTML render hooks in). The orchestrator picks up the new JSON output and writes it to `web/src/content/digests/`. The existing HTML output stays as a dev-preview path; the JSON output becomes canonical.
- **`pipeline_report.py` ↔ archive** — `pipeline/reporting/pipeline_report.py` grows a second write target: in addition to `out/pipeline-report-{week_id}.json` (existing) and `out/pipeline_report.json` (always-latest, existing), it also writes `web/src/content/reports/{week_id}.json` (committed archive copy). The shape is identical across all three; only the path differs.
- **Astro ↔ content collections** — `web/src/content/config.ts` defines Zod schemas for `digests` and `reports`. The schema hard-requires `schema_version === 1` on each. Build fails fast if Python emits an invalid shape.
- **Backfill ↔ existing SQLite** — `python -m pipeline.run render --week 2026-W19` and `--week 2026-W21` read existing W19 + W21 rows from SQLite and emit the new JSON. No re-summarize, no LLM calls, no new database writes. Uses the existing checkpoint-aware render path (D-67 / D-68).
- **Phase 5 hand-off** — Phase 5 reads `out/pipeline_report.json` (always-latest, gitignored) for heartbeat (OBS-03). Phase 5 publishes `web/dist/` to Cloudflare Pages (OPS-03). Phase 5 doesn't change the JSON shape Phase 4 produces.
- **YouTube transcript catch-up (D-23 / Plan 02-04)** — when `--only-pending-transcripts` flips items from `pending_local` → `ok`, the D-68 cascading invalidation re-emits the affected week's digest JSON. Pipeline-notes count for `pending_local` decreases on the next render. No code change required; the cascade already triggers a re-render.

</code_context>

<specifics>
## Specific Ideas

- **The pre-partitioned JSON shape is the structural lock-in for LOCKED-01.** Past phases relied on convention ("Don't reroute cards in the renderer") and that convention was broken twice. Phase 4 makes violation structurally impossible: Astro receives pre-routed lists and has no way to put a card in the wrong place. This is the most important architectural decision in the phase — not the choice of Astro, not the URL shape, not the design tokens. Every other Phase 4 decision is downstream of this one.
- **Distinct static routes per tab is "Astro as content" taken seriously.** A tab is a real page with a real URL — `/digest/2026-W21/technical`. The dashboard doesn't pretend to be a SPA; it IS a static newspaper with sections. The cost (build emits `weeks × 4` pages) is irrelevant at this scale. The benefit (every URL is bookmarkable, crawlable, JS-free, deep-linkable) compounds for years.
- **Bare URLs for the latest week is the "Sunday morning bookmark" feature.** Readers bookmark `/business` and always land on this week's Business. The canonical-tag pairing (D-A3b-extras) means the dated URL is what tools and crawlers index, so the "latest" URLs stay clean for humans.
- **`<details>` is the right primitive for Pipeline notes.** Native HTML, zero JS, accessible by default, scales fine on mobile. The temptation to build a "richer" custom-toggle drawer should be resisted — `<details>` is exactly the affordance the content needs.
- **shadcn-variable convention without the shadcn install** is the right trade-off for Phase 4. We get the token discipline (semantic names, themability potential) without committing to the React-component ecosystem we'd have to rip out later if we decided we didn't need it. If Phase N decides to install shadcn for real, the variables are already named correctly.
- **No thumbnails on cards** is a structural decision (D-25 symmetry) AND a values decision (no Google tracking pixels on a "personal, off-network" project). If thumbnails ever come back, they MUST be build-time proxied — never hotlinked.
- **REQUIREMENTS.md DISPLAY-02 / DISPLAY-04 reconciliation** is the only piece of documentation drift this discussion surfaced. PROJECT.md correctly cut `design` on 2026-05-23; REQUIREMENTS.md still lists 4 tabs; the code (`CATEGORY_ORDER`) already enforces 3. Phase 4's first plan-wave includes the doc reconciliation so the spec, the requirement, and the code finally agree.
- **Backfill is the integration test.** W19 (Phase 1 era, RSS-only, no clusters) and W21 (Phase 3 era, full cluster/category/rank/rollup) cover the schema range Phase 4's emitter has to handle. If the emitter can round-trip both, it'll round-trip everything Phase 5's automation throws at it.

</specifics>

<deferred>
## Deferred Ideas

### Visual polish escalation ladder (if Phase 4 UAT says the design feels under-built)

*If the dashboard feels too plain after Phase 4 ships, escalate in this order:*
1. **Denser typographic hierarchy** — heavier weight on Briefing Top-N numbering, tighter line-height in mini-rollups, larger weekly synthesis paragraph. Zero structural change.
2. **Subtle decorative section dividers** between Briefing and the topic tab content. Just CSS.
3. **Accent color on hover for cards** (currently muted; could pulse the `--accent` color subtly). Just CSS.
4. **Reference-screenshot-inspired full polish** — explicit Phase N redesign with new UI-SPEC. Major scope.

### Future Astro / dashboard enhancements (post-v1)

- **Light mode + toggle** — design tokens split per mode; `prefers-color-scheme` default; UI toggle. v2 enhancement per D-A5c.
- **YouTube thumbnails on cards (build-time proxied)** — download to `web/public/thumbs/{videoId}.jpg` at pipeline time; commit them; Astro serves locally. v1.5 / v2 per D-A7b. Note: meaningful git history churn; consider git-lfs if archive grows large.
- **Full-text search across past weeks** — REQUIREMENTS DISPLAY-V2-01. Likely implementation: build-time Lunr/Pagefind index over all committed digest JSONs.
- **Archive pagination / grouping-by-quarter** — D-A6d defers until the archive grows past ~52 entries.
- **Tabs as a client-side widget** — only if a real interactive need surfaces (e.g., swipe gestures on mobile). Install `@astrojs/react` at that point.
- **Reading-time estimate / progress indicator** — small enhancement; not in v1 scope but easy to add later.
- **shadcn CLI install + component primitives** — when (if) we decide we want shadcn components, the design tokens are already named correctly and components drop in cleanly.

### Phase 5 hand-off items (NOT Phase 4 scope but Phase 4 prepares for them)

- **Cloudflare Pages auto-deploy** — Phase 5 OPS-03. Phase 4 ensures `pnpm build` produces a clean `web/dist/`.
- **GHA cron wiring** — Phase 5 OPS-01. Phase 4 doesn't add any cron / workflow YAML.
- **Heartbeat reading `out/pipeline_report.json`** — Phase 5 OBS-03. Phase 4 keeps the always-latest report at the same path; Phase 5 wires it.
- **Hard $5/week LLM cap CI enforcement** — Phase 5 OPS-05. The Phase 3 D-60 budget machinery (`pipeline/budget.py`) is the seam.
- **Secret hygiene + pre-commit / build-time secret scan** — Phase 5 OPS-04. Phase 4 must not introduce any secret-leakage path (no API keys in components, no `.env` content rendered, no debug-mode dumps to the static output).

### Future UAT Watch (must be tested in the first 1–2 live Phase 4 weeks)

- **Backfill correctness** — open W19 + W21 in the dashboard, compare LOCKED-01 routing against the existing `out/digest-2026-W19.html` and `out/digest-2026-W21.html` byte-by-byte where comparable. Verify older W19 schema rows don't crash the emitter.
- **Tab navigation without JS** — disable JS in the browser, verify all routes work, tabs navigate, archive index loads. Phase 4 should be JS-free at every URL.
- **Mobile viewport 375px** — verify no horizontal scroll, tab bar wraps cleanly, header stacks vertically, archive index reads.
- **Canonical tags resolve correctly** — view source on `/` and `/business`, verify `<link rel="canonical">` points to `/digest/[latest-week]` or `/digest/[latest-week]/business` respectively.
- **`<details>` element on mobile** — verify the Pipeline notes affordance is obvious on iOS Safari and Chrome Android.
- **Play-icon glyph contrast** — verify against the muted-foreground color in actual dark mode; the icon should be visible but not aggressive.
- **Archive empty-state** — what does `/archive` render when there are 0 weeks? (Edge case for fresh setups; planner picks copy.)
- **Pipeline-notes zero-state** — when nothing is wrong, the `<details>` element MUST be entirely absent from the DOM, not just `display: none`. Existing D-26 rule.

### Reviewed Todos (not folded)

*None — no STATE.md pending todos matched Phase 4 scope. The Gemini billing decision and the Phase 2 manual UAT tests 6 + 7b stay on their existing tracks; the live three-feed E2E and live backfill UAT items will get exercised naturally by the W19 + W21 backfill (D-A2b).*

</deferred>

---

*Phase: 4-dashboard-archive*
*Context gathered: 2026-05-23*
