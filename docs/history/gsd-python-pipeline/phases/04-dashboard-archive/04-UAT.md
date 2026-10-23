---
status: complete
phase: 04-dashboard-archive
source: 04-03-SUMMARY.md, 04-04-SUMMARY.md, 04-05-SUMMARY.md, 04-06-SUMMARY.md
started: 2026-05-23T23:15:00Z
updated: 2026-05-24T01:46:00Z
---

## Current Test

[testing complete]

## Tests

### 1. W19/W21 LOCKED-01 routing vs HTML dev preview
expected: Backfilled JSON matches LOCKED-01 partition rules; thin items in footer_aside only; quota_exhausted and other transient statuses in main_feed in-place degraded cards; compare against deprecated `out/digest-*.html` when present
result: pass
evidence: |
  W19 JSON: footer_aside=9 (all summary_status=thin), main_feed=1 (ok)
  W21 JSON: footer_aside=1 (thin), main_feed=25 (22 ok + 3 quota_exhausted)
  No quota_exhausted items leaked into footer_aside for either week. LOCKED-01 partition holds.

### 2. Tab navigation with JavaScript disabled
expected: Browse `/`, `/edtech`, `/business`, `/technical`, and `/digest/2026-W21/edtech` with JS disabled — each tab is a static route; links navigate without client-side routing
result: pass
evidence: User walked the JS-disabled flow (/, /edtech, /business, /technical, /archive, /digest/2026-w21, /digest/2026-w21/edtech). All pages rendered with full-page navigation; no SPA routing errors.

### 3. Mobile 375px — no horizontal scroll
expected: DevTools 375×667 on `/` and `/archive` — no horizontal scrollbar; TabBar wraps to two rows; header stacks vertically (D-A6c)
result: pass
evidence: User confirmed iPhone-SE viewport on / and /archive — no horizontal scroll, TabBar wraps to two rows, header stacks vertically.

### 4. Canonical tags on `/` and `/business`
expected: View source on `/` and `/business` — each has `<link rel="canonical">` pointing to the dated permalink under `/digest/{week_id}/…` (ARCHIVE-03)
result: pass
evidence: |
  Built dist (pnpm build, 13 pages, exit 0):
    web/dist/index.html         → <link rel="canonical" href="/digest/2026-w21">
    web/dist/business/index.html → <link rel="canonical" href="/digest/2026-w21/business">
  Both lowercase; slugs match `dist/digest/2026-w21/` directory (case-exact for case-sensitive hosts).

### 5. Archive index with two weeks
expected: `/archive` lists 2026-W19 and 2026-W21 newest-first as one-line "Week of …" links that resolve to the dated permalink. (Excerpt + "Read this week" CTA removed per UAT-driven redesign; heading is the link.)
result: pass
evidence: User confirmed two rows newest-first (W21 then W19), single-line entries, click-through to /digest/2026-w21 and /digest/2026-w19 works.

### 6. Pipeline notes (render + zero-state)
expected: W21 Briefing renders `<details>` pipeline-notes element with summary line + expandable details list. Zero-state DOM-absence guaranteed by PipelineNotes.astro line 16 (`{pipelineNotes && (…)}`) and 17 passing unit tests in tests/render/test_pipeline_notes.py
result: pass
evidence: |
  User confirmed W21 strip: summary "3 budget-limited summaries"; expanded bullets
  "3 summaries hit the weekly LLM budget…" and "One Useful Thing didn't publish for the
  fourth week in a row." Zero-state path code-verified (no live empty-pipeline-notes week
  after W19 deletion, but emitter unit tests cover null branch).

### 7. YouTube video badge (was: play-icon contrast)
expected: Cards with `source_type='youtube'` show the accent-tinted "video" text badge next to the publisher badge; publisher badge links to @handle URL; no `[video]` text suffix anywhere.
result: pass
evidence: |
  User confirmed business + technical tabs render YouTube cards with: gray publisher pill
  linking to /@NateBJones or /@howiaipodcast, accent-blue "video" badge directly to the right,
  date after. No legacy [video] text. Treatment driven by SourceTypeBadge.astro (UAT pass 2)
  + publisherHomeUrl helper preferring card.channel_url (UAT pass 3 ingestion change).
note: |
  Test scope was redefined during UAT. Original DISPLAY-05 expectation (16x16 inline SVG play
  glyph contrast on #141820) was replaced with a labeled text badge per user preference.
  UI-SPEC DISPLAY-05/06 should be updated to reflect the new badge styling.

### 8. Deprecated HTML dev preview path
expected: `uv run python -m pipeline.run render --week 2026-W21` (without `--no-html-preview`) still writes `out/digest-2026-W21.html`; module docstring marks `pipeline/render/html.py` as DEPRECATED dev-preview only
result: pass
evidence: |
  Re-ran .venv/bin/python -m pipeline.run render --week 2026-W21 → exit 0;
  out/digest-2026-W21.html rewritten (30141 bytes at 2026-05-23T21:46).
  pipeline/render/html.py line 1 docstring: "Plain-HTML weekly digest renderer — DEPRECATED dev-preview only."
  Sphinx ".. deprecated::" marker present line 3 with link to Plan 04-02 / partition.

## Summary

total: 8
passed: 8
issues: 6
pending: 0
skipped: 0
blocked: 0

## Decisions (during UAT)

- **W19 fixture removed.** Pre-Phase-3 backfill was sparse, footer-heavy, and produced
  false silent-source notes ("Simon Willison didn't publish for the 12th week in a row").
  Deleted `web/src/content/digests/2026-W19.json`, `web/src/content/reports/2026-W19.json`,
  and `out/digest-2026-W19.html`. Archive now lists W21 only (and will grow as new weeks
  ingest). The `_infer_summary_status` legacy-NULL branches stay (cheap, harmless).
- **Footer ("Also seen this week") kept as-is.** User feedback was about W19's footer
  *content* being wrong (9 thin items dominating a sparse week), not about the footer
  concept. Once W19 was deleted, the W21 footer (1 thin RSS item) reads correctly.

## Gaps

- truth: "Briefing tab shows weekly synthesis + Top N + per-topic category sections + footer aside"
  status: failed
  reason: "User reported: stories are duplicated on the Briefing tab; per-topic stories should appear only on the individual topic tabs (Edtech/Business/Technical), not also on Briefing."
  severity: major
  test: ad-hoc (Briefing layout — surfaced during Test 1 navigation)
  source_file: web/src/components/DigestBriefing.astro
  artifacts:
    - web/src/components/DigestBriefing.astro
    - web/src/pages/index.astro
    - web/src/pages/digest/[week].astro
  missing:
    - Briefing render path must omit per-topic CategorySection list; topic content stays on /edtech, /business, /technical (and per-week /digest/{week}/{topic}).
  fix: |
    DigestBriefing.astro currently renders WeeklySynthesis + BriefingTopN + TOPICS.map(CategorySection) + FooterAside.
    Remove the TOPICS.map(CategorySection) block so Briefing = WeeklySynthesis + BriefingTopN + FooterAside only.
  spec_note: |
    UI-SPEC Visual Hierarchy currently says "Secondary hierarchy: category mini-rollup headings → per-category cards → footer aside" on Briefing.
    Per UAT feedback the spec should be updated: Briefing = synthesis + Top N + footer aside; category sections live only on topic tabs.

- truth: "Archive index newest-first with one-line excerpt and 'Read this week' link"
  status: failed
  reason: "User reported: archive list should be tighter — no summary excerpt; the 'Week of …' heading itself should be the link to that week's permalink."
  severity: minor
  test: 5 (Archive index with two weeks — surfaced ahead of formal test)
  source_file: web/src/components/ArchiveList.astro
  artifacts:
    - web/src/components/ArchiveList.astro
  missing:
    - Excerpt paragraph removed
    - "Read this week" link removed; week heading becomes anchor
    - List spacing tightened (no border between rows, smaller vertical rhythm)
  fix: |
    Make each row a single <li> with the week heading wrapped in <a href="/digest/{digest.id}">; drop excerpt paragraph and CTA link; reduce space-y-8 to space-y-3 and drop border-b/pb-8.
  spec_note: |
    UI-SPEC ARCHIVE-02 currently describes a one-line excerpt; update to a tight title-only list per UAT feedback.

- truth: "Empty category section on a topic tab tells the reader nothing was published"
  status: failed
  reason: "User reported: when a category has zero cards this week (e.g., Edtech on W21), the topic tab renders an empty <main>. Add a simple 'No items in this category this week' line."
  severity: minor
  test: ad-hoc (Topic tab empty state — surfaced during Briefing/topic fix loop)
  source_file: web/src/components/CategorySection.astro
  artifacts:
    - web/src/components/CategorySection.astro
    - web/src/pages/[topic].astro
    - web/src/pages/digest/[week]/[topic].astro
  missing:
    - Empty-state copy "No items in this category this week." rendered on topic-variant when section.cards is empty
    - Briefing-variant continues to omit the section entirely (unchanged behavior)
  fix: |
    Compute isEmpty; if briefing variant + empty → return null (unchanged). On topic variant + empty, render the mini_rollup (if present) then an empty-state <p>.
  spec_note: |
    UI-SPEC should add: "Topic tab — when section.cards is empty, render mini-rollup (if any) and the line 'No items in this category this week.'"

- truth: "YouTube items are visually distinguishable from articles on the card row"
  status: failed
  reason: "User reported: the 16px play icon is not discoverable. Prefers an explicit 'video' label — likely 'video' or '(video)' next to the publisher badge. Also flags future need: filter cards by item type (videos / blog posts / podcasts)."
  severity: minor
  test: 7 (YouTube play icon contrast — surfaced ahead of formal test)
  source_file: web/src/components/Card.astro
  artifacts:
    - web/src/components/Card.astro
    - web/src/components/SourceTypeBadge.astro
    - web/src/components/PlayIcon.astro
  missing:
    - Explicit text label "video" on YouTube cards (not glyph-only)
    - Architectural seam for future source-type filters (podcast / blog)
  fix: |
    Replace bare PlayIcon usage with a new SourceTypeBadge.astro component that maps source_type → labeled text badge.
    youtube → accent-tinted pill "video" (text only, no glyph) per UAT preference.
    Default/rss → renders nothing (no card-row noise).
    Card.astro now delegates to <SourceTypeBadge sourceType={card.source_type} />.
  follow_up: |
    Future enhancement (Phase 5+ or backlog): add a filter UI on topic tabs / Briefing to show only items of a given source_type.
    Requires source_type taxonomy expansion in ingestion (podcast adapter, blog vs newsletter distinction) before UI filter is meaningful.
    SourceTypeBadge.BADGE_MAP is the single hook point — add entries there as new source types ship.
  spec_note: |
    UI-SPEC DISPLAY-06 ("YouTube visual hint on cards") should be widened to "Source-type label on cards"
    with badge styling spec (accent-tinted pill, 3.5x3.5 glyph, lowercase label).

- truth: "Publisher badge on each card links to the publisher's front page / channel"
  status: failed
  reason: "User reported: card publisher badge should link to the channel / front page of the blog so readers can jump to the source's main site."
  severity: minor
  test: ad-hoc (Card publisher linkification — surfaced during card polish)
  source_file: web/src/components/Card.astro
  artifacts:
    - web/src/components/Card.astro
    - web/src/lib/publisherHomeUrl.ts
    - web/src/content.config.ts
  missing:
    - Publisher badge anchor wired to publisher home URL
    - publisher_url / channel_url field in digest JSON schema (proper home URL for YouTube channels)
  fix: |
    Two-pass fix.
    Pass 1 (UI-only): web/src/lib/publisherHomeUrl.ts derives "{scheme}://{host}/" from card.canonical_url
    for non-youtube sources; Card.astro renders publisher as <a target="_blank" rel="noopener noreferrer">
    when publisherHref is non-null, falls back to plain <span>.
    Pass 2 (Channel-URL ingestion, done in same UAT loop per user direction):
      * pipeline/config.py — YoutubeSource.channel_url derived from channel_id
        (https://www.youtube.com/channel/{channel_id}); RssSource gains optional `home_url` (default null).
      * store/schema.sql + store/migrations/005_channel_url.sql — `channel_url TEXT` column on sources.
      * store/db.py — upsert_source writes channel_url; get_items_for_week + get_pending_transcript_items
        SELECT sources.channel_url AS channel_url.
      * pipeline/render/partition.py DigestCard — adds channel_url field (default None).
      * pipeline/orchestrator.py _build_card_from_row — pulls channel_url from joined row.
      * pipeline/render/digest_json.py — DigestCardJson exposes channel_url; _card_to_json passes through.
      * web/src/content.config.ts — Zod schema accepts optional nullable channel_url.
      * web/src/lib/publisherHomeUrl.ts — prefers card.channel_url over origin-derivation.
      * Reseeded sources + re-rendered W19/W21 JSON. YouTube cards now carry real
        https://www.youtube.com/channel/UC… URLs; RSS cards keep channel_url=null and use origin fallback.
  follow_up: |
    Pass-3 polish shipped in same UAT loop per user request: YoutubeSource gained optional
    `channel_url` YAML field (aliased to `channel_url_override` internally). When set, it
    overrides the derived `/channel/UC…` URL with the friendly `/@handle` form. Both seeded
    channels updated (`@howiaipodcast`, `@NateBJones`); user confirmed both links work.
    Remaining knob: RSS sources where canonical-URL origin is wrong (e.g., feed proxied
    through Substack but publisher's real home is elsewhere) can set `home_url:` in
    sources.yaml — already supported, no current source needs it.
  spec_note: |
    UI-SPEC DISPLAY-05 ("Card metadata") should be extended: publisher badge is a link to publisher home URL when known.
    Anchor uses target="_blank" rel="noopener noreferrer" matching the title link convention (D-A3a privacy framing preserved — no client-side navigation, no JS).
    Schema: digest cards now carry an optional `channel_url` field (null when unknown).
  status_post_fix: closed
