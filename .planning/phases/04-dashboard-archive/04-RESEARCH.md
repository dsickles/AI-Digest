# Phase 4: Dashboard + Archive - Research

**Researched:** 2026-05-23
**Domain:** Astro 6 static dashboard + Python JSON archive emitter + LOCKED-01 pre-partitioned publish path
**Confidence:** HIGH (codebase + official Astro/Tailwind docs); MEDIUM (first Astro scaffold in repo, OBS-01 silent-source counter is new logic)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-A1:** Pre-partitioned JSON in `pipeline/render/digest_json.py`; LOCKED-01 routing via shared `_partition_cards` (extract, not duplicate); output to `web/src/content/digests/{week_id}.json`; `html.py` deprecated dev-preview only.
- **D-A2a–c:** Canonical archive at `web/src/content/digests/` + `web/src/content/reports/`; backfill W19 + W21; `schema_version: 1` hard-required at Astro build.
- **D-A3a–c:** Static routes only — `/`, `/[topic]`, `/digest/[week]`, `/digest/[week]/[topic]`, `/archive`; no React, no client-side tabs; canonical tags on latest-week pages.
- **D-A4a–c:** `<details>` Pipeline notes at top of `<main>`; expanded OBS-01 signal set; plain-English copy library; zero-state = no DOM node.
- **D-A5a–c:** shadcn-shape CSS variables from existing palette; dark-only; table-stakes polish per UI-SPEC.
- **D-A6a–d:** 720px column; tab wrap; mobile header stack; plain archive list.
- **D-A7a–b:** Inline-SVG play icon (UI-SPEC: hand-authored, no `astro-icon`); no YouTube thumbnails v1.
- **Carry LOCKED-01, D-24, D-25, D-22, D-26, D-58/D-66, D-70** — see `04-CONTEXT.md` §Implementation Decisions.
- **No `@astrojs/react`, no shadcn CLI** for Phase 4.
- **Planner MUST update LOCKED-01 code anchors** in `.planning/LOCKED-DIRECTIVES.md` to include JSON emitter partition module.

### Claude's Discretion

- Exact `web/` directory layout, JSON field naming (recommend snake_case), Tailwind install path (`@tailwindcss/vite` vs deprecated `@astrojs/tailwind`), play-icon SVG source (UI-SPEC locked hand-authored), backfill wave placement, test framework on Astro side, REQUIREMENTS.md reconciliation commit mechanics.

### Deferred Ideas (OUT OF SCOPE)

- Cron/GHA deploy (Phase 5), light mode, thumbnails, archive search/pagination, React islands, reading-time/analytics — see `04-CONTEXT.md` §Deferred.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DISPLAY-01 | Dark dashboard header: project name, week range, Updated timestamp | D-A5a tokens + `Header.astro`; week range from JSON `week_range`; `04-UI-SPEC.md` typography/color |
| DISPLAY-02 | Tabbed nav: Briefing + 3 topic tabs | D-A3a static `<a>` routes; `TabBar.astro`; reconcile REQUIREMENTS 4→3 tabs |
| DISPLAY-03 | Briefing: weekly synthesis + numbered Top N | Pre-partitioned `briefing_top_n[]` + `weekly_synthesis` in JSON; `BriefingTopN.astro` |
| DISPLAY-04 | Topic tab shows that topic's stories | `category_sections.{topic}.cards[]`; `/[topic]` + `/digest/[week]/[topic]` routes |
| DISPLAY-05 | Card: title, TL;DR, publisher, links, date | `DigestCardJson` fields → `Card.astro`; DISPLAY-08 on links |
| DISPLAY-06 | Video visual hint | `PlayIcon.astro` inline SVG when `source_type === 'youtube'` (UI-SPEC) |
| DISPLAY-07 | Desktop + mobile without breakage | D-A6 + UI-SPEC spacing/touch targets; Tailwind utilities |
| DISPLAY-08 | Links open new tab | `target="_blank" rel="noopener noreferrer"` in `Card.astro` |
| ARCHIVE-01 | Past digests as committed JSON | `web/src/content/digests/{week_id}.json` via `digest_json.py` |
| ARCHIVE-02 | Archive index newest-first + excerpt | `/archive` + `ArchiveList.astro`; sort `getCollection('digests')` by `week_id` desc |
| ARCHIVE-03 | Permalink full digest | `/digest/[week]` + topic permalinks via `getStaticPaths` |
| ARCHIVE-04 | Archive reachable from nav | `TabBar.astro` Archive link |
| OBS-01 | Pipeline notes on Briefing | `<details>` + JSON `pipeline_notes` built from D-70 report + D-A4b rules |
</phase_requirements>

## Summary

Phase 4 is a **publish-path swap**: Python stops being the canonical HTML renderer and becomes a **typed JSON publisher**; Astro validates and statically renders that JSON into a multi-route, JS-free dark dashboard. The architectural linchpin is **D-A1 pre-partitioned JSON** — `main_feed[]`, `footer_aside[]`, and `briefing_top_n[]` are computed in Python via the existing LOCKED-01 router so Astro cannot mis-route cards.

The codebase already has everything Phase 4 needs on the Python side: `DigestCard`, `_partition_cards`, briefing/category section builders in `html.py`, D-70 `pipeline_report.json` in `pipeline/reporting/pipeline_report.py`, and a **render-only** entry point (`run_render`) that reads SQLite without LLM calls — safe for W19/W21 backfill. The `web/` directory does not exist yet; Astro 6 content collections use **`src/content.config.ts`** (not the older `src/content/config.ts` path listed in CONTEXT — planner should follow Astro 6 docs).

Tailwind 4 integration is **not** via `@astrojs/tailwind` (officially deprecated for Tailwind 4); use **`@tailwindcss/vite`** per Astro + Tailwind docs. Icons: **UI-SPEC locks hand-authored inline SVG** — do not install `astro-icon`.

**Primary recommendation:** Extract LOCKED-01 routing + card types to `pipeline/render/partition.py`, implement `digest_json.py` with Pydantic models whose `model_dump(mode="json")` matches a mirrored Zod schema in `web/src/content.config.ts`, wire `run_render` to emit JSON + copy reports to `web/src/content/reports/`, scaffold Astro with `@tailwindcss/vite`, then backfill W19/W21 as the integration gate.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| LOCKED-01 card routing | Python API / pipeline | — | Pre-partition before publish; structural enforcement (D-A1) |
| Digest + report JSON emission | Python API / pipeline | — | Orchestrator `run_render` / `_finalize` hooks |
| Schema validation (`schema_version: 1`) | Astro build (SSG) | Python Pydantic pre-write | Zod fails build; Pydantic catches bugs before commit |
| Tab navigation + archive pages | CDN / static (Astro SSG) | — | Pre-rendered HTML; zero client JS |
| Pipeline notes (OBS-01) copy | Python JSON (`pipeline_notes`) | Astro presentational (`PipelineNotes.astro`) | Plain-English generation stays D-24/D-A4c in emitter |
| Design tokens / layout | Browser (CSS via Tailwind) | Astro components | shadcn-variable convention in `globals.css` |
| Week backfill / cascade safety | Python CLI | — | `run_render` is DB-read-only; cascade never runs on render-only |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **astro** | 6.3.7 [VERIFIED: npm registry] | Static dashboard SSG | Project STACK.md; Content Collections fit digest JSON archive |
| **tailwindcss** | 4.3.0 [VERIFIED: npm registry] | Utility styling | STACK.md; maps shadcn-shape CSS variables |
| **@tailwindcss/vite** | 4.3.0 [VERIFIED: npm registry] | Tailwind 4 in Astro | Official Astro + Tailwind docs — preferred over deprecated `@astrojs/tailwind` |
| **zod** (via `astro/zod`) | bundled with Astro 6 [CITED: docs.astro.build] | Content collection schemas | Build-time validation of committed JSON |
| **pydantic** | ≥2.13.4 [VERIFIED: pyproject.toml] | Python digest JSON models | Already used across pipeline; `model_dump(mode="json")` for ISO dates |
| **pnpm** | 9+ [ASSUMED] | Node package manager | CONTEXT D-A2a; not installed on dev machine — install in plan |
| **Node.js** | 22 LTS [ASSUMED per CONTEXT] | Astro build runtime | `.nvmrc` in `web/` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest** | 9.x [VERIFIED: pyproject.toml] | Python contract tests | JSON shape, partition parity, emitter integration |
| **Vitest** | latest [ASSUMED] | Optional Astro unit tests | Only if planner adds component tests; not required for MVP — `pnpm build` is the Astro gate |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@tailwindcss/vite` | `@astrojs/tailwind` 6.0.2 | Integration deprecated for Tailwind 4 — avoid |
| Hand-authored SVG | `astro-icon` + Lucide | UI-SPEC rejected — extra dep, zero JS goal |
| `@astrojs/react` tabs | Static route tabs (chosen) | CONTEXT D-A3a — no v1 interactive surface |
| shadcn CLI | CSS variables only (chosen) | D-A5a — convention without React/Radix install |

**Installation (web scaffold):**
```bash
cd web
pnpm create astro@latest . --template minimal --typescript strict --install
pnpm add tailwindcss @tailwindcss/vite
```

**Version verification:** `npm view astro version` → 6.3.7; `npm view tailwindcss version` → 4.3.0 (2026-05-23).

## Package Legitimacy Audit

> slopcheck unavailable at research time — all packages tagged for planner `checkpoint:human-verify` before install.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| astro | npm | years | very high | github.com/withastro/astro | n/a | Approved [VERIFIED: npm registry] |
| tailwindcss | npm | years | very high | github.com/tailwindlabs/tailwindcss | n/a | Approved [VERIFIED: npm registry] |
| @tailwindcss/vite | npm | ~1 yr | high | github.com/tailwindlabs/tailwindcss | n/a | Approved [VERIFIED: npm registry] |

**Packages removed due to slopcheck [SLOP] verdict:** none (slopcheck not run)
**Packages flagged as suspicious [SUS]:** none

*Explicitly NOT installing per locked decisions:* `@astrojs/react`, `astro-icon`, shadcn CLI.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CLI: python -m pipeline.run render --week YYYY-Www                      │
│  (run_render — SQLite read only, no LLM, no cascade)                     │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  orchestrator: _build_cards_from_db → DigestCard[]                       │
│  digest_json.py: partition → briefing/category/notes → Pydantic dump     │
└───────────────┬─────────────────────────────┬───────────────────────────┘
                │                             │
                ▼                             ▼
   web/src/content/digests/{week}.json   web/src/content/reports/{week}.json
   (pre-partitioned digest)              (D-70 pipeline_report copy)
                │                             │
                └──────────────┬──────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Astro build: content.config.ts Zod validate → getStaticPaths → HTML     │
│  Routes: / /{topic} /digest/{week} /digest/{week}/{topic} /archive       │
└───────────────────────────────┬─────────────────────────────────────────┘
                                ▼
                         web/dist/ (Phase 5 publishes)
```

### Recommended Project Structure

```
web/
├── astro.config.mjs          # vite.plugins: [@tailwindcss/vite()]
├── src/content.config.ts     # digests + reports collections (Astro 6 path)
├── src/content/digests/      # committed JSON archive
├── src/content/reports/      # committed D-70 copies
├── src/pages/
│   ├── index.astro
│   ├── [topic].astro
│   ├── archive.astro
│   └── digest/[week].astro
│   └── digest/[week]/[topic].astro
├── src/components/           # per UI-SPEC inventory
├── src/lib/                  # latestWeek, formatWeekRange, canonicalUrl
└── src/styles/globals.css    # @import "tailwindcss" + :root tokens

pipeline/render/
├── partition.py              # NEW: DigestCard, _partition_cards, constants (extract)
├── digest_json.py            # NEW: emit_digest_json()
└── html.py                   # DEPRECATED dev preview (imports partition)
```

### Pattern 1: Astro 6 JSON Content Collections

**What:** `glob()` loader over `src/content/digests/**/*.json`; Zod schema validates entire JSON root as `entry.data`.

**When to use:** All committed digest + report files.

**Example:**
```typescript
// Source: https://docs.astro.build/en/guides/content-collections/
import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const digestCard = z.object({
  title: z.string(),
  publisher: z.string(),
  canonical_url: z.string().url(),
  published_at: z.string(), // ISO8601 from Python
  tldr: z.string().nullable(),
  summary_status: z.string().nullable(),
  source_type: z.string(),
  also_covered: z.array(z.object({ display_name: z.string(), url: z.string().url() })),
  category: z.enum(['edtech', 'business', 'technical']).nullable(),
  rank_position: z.number().int().nullable(),
  degraded_body: z.string().optional(), // QUOTA_BODY_COPY when in-place degraded
});

const digests = defineCollection({
  loader: glob({ base: './src/content/digests', pattern: '**/*.json' }),
  schema: z.object({
    schema_version: z.literal(1),
    week_id: z.string(),
    generated_at: z.string(),
    week_range: z.object({ start: z.string(), end: z.string() }),
    updated_at: z.string(),
    weekly_synthesis: z.object({ text: z.string().nullable(), status: z.string() }),
    briefing_top_n: z.array(digestCard),
    category_sections: z.object({
      edtech: z.object({ mini_rollup: z.string().nullable(), cards: z.array(digestCard) }),
      business: z.object({ mini_rollup: z.string().nullable(), cards: z.array(digestCard) }),
      technical: z.object({ mini_rollup: z.string().nullable(), cards: z.array(digestCard) }),
    }),
    main_feed: z.array(digestCard),
    footer_aside: z.array(digestCard),
    pipeline_notes: z.object({ /* OBS-01 — see Open Questions */ }),
    failure_notice: z.object({ kind: z.string(), body: z.string() }).optional(),
  }),
});

export const collections = { digests };
```

**Validation behavior:** Build fails with Zod error pointing at file path if any field wrong or `schema_version !== 1`. Sort order from `getCollection()` is non-deterministic — **always sort** archive index by `week_id` descending in application code [CITED: docs.astro.build].

**File path convention:** `2026-W21.json` → collection `id` = `2026-W21` (URL-friendly from filename).

### Pattern 2: Nested `getStaticPaths` for `/digest/[week]/[topic]`

**What:** Cartesian product of digest entries × closed topic enum at build time.

**Example:**
```astro
---
// Source: https://docs.astro.build/en/guides/content-collections/#generating-routes-from-content
import { getCollection, getEntry } from 'astro:content';

const TOPICS = ['edtech', 'business', 'technical'] as const;

export async function getStaticPaths() {
  const weeks = await getCollection('digests');
  return weeks.flatMap((week) =>
    TOPICS.map((topic) => ({
      params: { week: week.id, topic },
      props: { weekId: week.id, topic },
    }))
  );
}

const { weekId, topic } = Astro.props;
const digest = await getEntry('digests', weekId);
---
```

**Performance:** At personal scale (≤52 weeks × 3 topics ≈ 156 pages + 4 latest routes + archive) build time is negligible [ASSUMED — scale from PITFALLS #19].

**`/[topic].astro` collision guard:** `getStaticPaths` must return **only** the three topic slugs — Astro will not generate paths for unknown params. Reserved routes (`archive`, `digest`) live as static files and take precedence over dynamic segments.

### Pattern 3: Pydantic → JSON → Zod alignment

**What:** Single Python module defines `DigestDocument` Pydantic model; tests assert JSON Schema or golden files match Zod expectations.

**Example (follows existing pipeline style):**
```python
# Source: pipeline/llm/summarize.py pattern
from pydantic import BaseModel, Field

class DigestCardJson(BaseModel):
    title: str
    publisher: str
    canonical_url: str
    published_at: str  # UTC ISO8601
    tldr: str | None
    summary_status: str | None
    source_type: str = "rss"
    also_covered: list[AlsoCoveredJson] = Field(default_factory=list)
    category: str | None = None
    rank_position: int | None = None
    degraded_body: str | None = None  # populated when in-place degraded

class DigestDocument(BaseModel):
    schema_version: Literal[1] = 1
    week_id: str
    # ... mirrors Zod ...

def emit_digest_json(...) -> Path:
    doc = DigestDocument(...)
    path.write_text(doc.model_dump_json(indent=2) + "\n")
```

**Drift prevention:** Add `tests/render/test_digest_json_schema.py` that loads emitted JSON and validates against Pydantic; optional CI step runs `pnpm build` after backfill.

### Pattern 4: Extract `_partition_cards` to shared module

**What:** Move `DigestCard`, `AlsoCoveredMember`, `_partition_cards`, `_IN_PLACE_TRANSIENT_STATUSES`, and display constants from `html.py` to `pipeline/render/partition.py`.

**Why extract over import-from-html:** `html.py` is deprecated; LOCKED-01 anchor update requires a non-deprecated module; avoids `digest_json` importing from a legacy surface.

**Re-export:** `html.py` imports from `partition.py` for backward-compatible tests.

### Anti-Patterns to Avoid

- **Routing cards in Astro:** Violates D-A1/LOCKED-01 — Astro only renders lists it receives.
- **Using `@astrojs/tailwind` for Tailwind 4:** Deprecated path [CITED: docs.astro.build/en/guides/integrations-guide/tailwind].
- **Installing React/shadcn for tabs:** Locked out; static `<a>` pages are the product model.
- **Calling `run_all` for backfill:** Would re-run LLM stages — use `render --week` only.
- **Putting secrets in JSON or Astro env:** PITFALLS #5 — static output must grep clean.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON schema validation (TS) | Custom validator | Astro Content Collections + Zod | Build fails fast; typed `entry.data` |
| JSON schema validation (Py) | ad-hoc dict assembly | Pydantic v2 models | Matches existing pipeline; ISO serialization |
| Tab routing / SPA | Client router | Static routes + `<a href>` | D-A3a; works JS-disabled |
| Hex → HSL tokens | Runtime conversion | Precomputed values in UI-SPEC | Already computed — copy verbatim |
| Play icon | Image sprite / icon font | `PlayIcon.astro` inline SVG | UI-SPEC; zero deps, no tracking pixels |
| Archive sort/index | DB query at runtime | `getCollection` + sort at build | Static-first pattern |

**Key insight:** Phase 4's complexity is **data shaping in Python**, not Astro wizardry. The site is a typed pretty-printer over committed JSON.

## Common Pitfalls

### Pitfall 1: Astro 6 content config path drift

**What goes wrong:** Planner scaffolds `src/content/config.ts` (Astro 2–4 path); collections silently don't load.

**Why it happens:** CONTEXT canonical refs predate Astro 6 `src/content.config.ts` rename.

**How to avoid:** Use `src/content.config.ts` + `glob` loader per [Content collections docs](https://docs.astro.build/en/guides/content-collections/).

**Warning signs:** `getCollection('digests')` returns empty; no Zod errors on bad JSON.

### Pitfall 2: Backfill triggers re-summarize

**What goes wrong:** Operator runs `run all` instead of `render`; W21 LLM costs spike.

**Why it happens:** Muscle memory from prior phases.

**How to avoid:** Document and test `python -m pipeline.run render --week 2026-W19` — `run_render` only reads DB (`orchestrator.py:1733–1772`).

**Warning signs:** Log lines `phase=summarize` during backfill.

### Pitfall 3: PARTIAL_PUBLISH_COPY string drift

**What goes wrong:** HTML constant, UI-SPEC copy, and JSON emitter disagree.

**Why it happens:** `html.py` uses shorter legacy string; UI-SPEC/D-A4c uses longer approved copy.

**How to avoid:** Single constant in `partition.py` matching UI-SPEC verbatim; update `html.py` re-export.

**Warning signs:** Budget-halt band text differs between old HTML and Astro dashboard.

### Pitfall 4: `[topic].astro` route shadowing

**What goes wrong:** `/archive` or `/digest` captured by `[topic].astro` if misconfigured.

**Why it happens:** Dynamic segment at pages root.

**How to avoid:** Static pages for `archive.astro`, `digest/` folder; constrain `getStaticPaths` to enum triple only.

### Pitfall 5: OBS-01 over-surfaces empty feeds

**What goes wrong:** Pipeline notes noise every week for quiet sources.

**Why it happens:** D-A4b requires **3+ consecutive** empty weeks — not implemented in current `_pipeline_notice_counts`.

**How to avoid:** New emitter logic querying ingest history; unit test threshold.

### Pitfall 6: Committed JSON with API keys

**What goes wrong:** Debug fields leak `GEMINI_API_KEY` into git.

**Why it happens:** Copy-paste from `RunStats.errors` raw payloads.

**How to avoid:** Whitelist OBS-01 fields; never embed env or stack traces in reader JSON (PITFALLS #5).

## Code Examples

### Existing LOCKED-01 router (extract source)

```337:363:pipeline/render/html.py
def _partition_cards(
    cards: list[DigestCard],
) -> tuple[list[DigestCard], list[DigestCard]]:
    """Return ``(main_feed, also_seen)`` per the PROJECT.md LOCKED-01 directive."""
    main_feed: list[DigestCard] = []
    also_seen: list[DigestCard] = []
    for card in cards:
        if _is_healthy(card) or _is_quota_in_place(card):
            main_feed.append(card)
        else:
            also_seen.append(card)
    return main_feed, also_seen
```

### Safe render-only backfill entry

```1733:1769:pipeline/orchestrator.py
def run_render(
    week_id: str,
    *,
    db_path: Path | str | None = None,
    out_dir: Path | None = None,
    top_n_briefing: int | None = None,
) -> RunStats:
    """Render HTML from existing SQLite data — no network, no LLM (D-20)."""
    # ...
    cards = _build_cards_from_db(conn, week_rows, week_id)
    stats.out_path = render_digest(...)
```

### D-70 report fields for OBS-01

```203:243:pipeline/reporting/pipeline_report.py
    return {
        "schema_version": 1,
        "week_id": week_id,
        "summary_status": _summary_status_counts(conn, week_id),
        "stages": { /* ingest, dedup, summarize, categorize, rank, rollup */ },
        "source_health": _source_health_snapshot(conn, week_id),
        "budget": budget_block,  # budget.halted drives partial-publish band
    }
```

### Tailwind 4 + Astro config

```javascript
// Source: https://tailwindcss.com/docs/installation/framework-guides/astro
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  vite: { plugins: [tailwindcss()] },
});
```

### Design tokens (from UI-SPEC — use verbatim)

```css
:root {
  color-scheme: dark;
  --background: 216 22% 7%;
  --foreground: 0 0% 90%;
  --card: 216 20% 10%;
  --muted-foreground: 216 13% 65%;
  --border: 216 21% 20%;
  --accent: 213 100% 75%;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `src/content/config.ts` | `src/content.config.ts` + loaders API | Astro 5+ / 6 | Planner must scaffold new path |
| `@astrojs/tailwind` integration | `@tailwindcss/vite` plugin | Tailwind 4 (2025+) | Do not install deprecated integration |
| Content in MD frontmatter | JSON-only digest files | Phase 4 D-A2a | Pipeline emits JSON; no MD body |
| `[video]` text suffix | Inline SVG play glyph | Phase 4 D-A7a / UI-SPEC | DISPLAY-06 |
| 4 topic tabs incl. Design | 3 tabs | PROJECT.md 2026-05-23 | Reconcile DISPLAY-02/04 |

**Deprecated/outdated:**
- `@astrojs/tailwind` for Tailwind 4 — official docs mark deprecated; use Vite plugin.
- STACK.md `@astrojs/react` + shadcn CLI — Phase 4 explicitly deviates (D-A3a, D-A5a).

## MVP Vertical Slices (planning guide)

Each slice should end testable:

| Slice | Delivers | Verification |
|-------|----------|--------------|
| **S0** | Extract `partition.py`; existing pytest green | `tests/render/test_partition_cards_phase3.py` |
| **S1** | `digest_json.py` + Pydantic models; wire `run_render` | pytest golden JSON; partition parity vs HTML |
| **S2** | `web/` scaffold + content.config.ts + tokens + layout | `pnpm build` empty collections or fixture JSON |
| **S3** | Routes: `/`, `/[topic]`, `/digest/*`, `/archive` | `pnpm build` page count; manual link crawl |
| **S4** | Components: Card, Header, TabBar, Briefing, FooterAside | Visual compare W21 HTML vs Astro |
| **S5** | OBS-01 `pipeline_notes` + `<details>` | pytest emitter notes; DOM absent when zero-state |
| **S6** | Report copy to `web/src/content/reports/` | Schema test re-use D-70 |
| **S7** | Backfill W19 + W21; REQUIREMENTS reconciliation | UAT checklist below |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | pnpm 9+ available after plan install step | Standard Stack | Build blocked until pnpm installed |
| A2 | Node 22 LTS on operator machine | Environment | Astro may warn; use `.nvmrc` |
| A3 | W19/W21 SQLite rows exist locally for backfill | Integration | Backfill UAT skipped if DB empty |
| A4 | ~4 pages/week × N weeks is fine at build | getStaticPaths | Revisit pagination at ~52 entries (D-A6d) |

## Open Questions (RESOLVED)

1. **`pipeline_notes` exact JSON shape for OBS-01 expanded signals**
   - What we know: D-A4b lists signals; D-70 has `source_health`, `summary_status`, `budget.halted`; silent-source needs new consecutive-week query.
   - What's unclear: Whether per-source lines are pre-rendered strings in JSON (recommended for D-24) vs structured codes for Astro to map.
   - Recommendation: **Pre-render plain-English strings in Python** (`pipeline_notes.summary_line`, `pipeline_notes.details[]`); Astro is dumb template.
   - **RESOLVED:** Pre-render plain-English strings in Python (`pipeline_notes.summary_line`, `pipeline_notes.details[]`); Astro is a dumb template only.

2. **W19 schema gaps (pre-Phase-3 columns)**
   - What we know: D-A2b requires null/sensible defaults for missing cluster/rank/rollup.
   - Recommendation: Emitter tolerates empty `briefing_top_n`, missing mini-rollups; Zod fields nullable.
   - **RESOLVED:** Emitter tolerates empty `briefing_top_n`, missing mini-rollups; Zod fields nullable.

3. **Vitest vs build-only for Astro**
   - Recommendation: **`pnpm build` + manual UAT** for Phase 4 MVP; add Vitest only if component logic grows.
   - **RESOLVED:** `pnpm astro check` for per-task quick feedback (~10s); `pnpm build` as wave-final and Phase 6 gate; manual UAT for visual checks; Vitest deferred unless component logic grows.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | digest_json.py | ✓ | 3.9.6 local / 3.12+ project | Use 3.12+ venv per pyproject |
| Node.js | Astro build | ✓ | v25.1.0 | `.nvmrc` pins 22 LTS |
| pnpm | CONTEXT | ✗ | — | `corepack enable && corepack prepare pnpm@latest --activate` |
| Astro CLI | web/ scaffold | ✗ (no web/) | — | Created in plan Wave 0/1 |
| SQLite W19/W21 data | backfill UAT | ✓ [ASSUMED] | — | Run render after confirming DB |

**Missing dependencies with no fallback:**
- `web/` directory (must be scaffolded)

**Missing dependencies with fallback:**
- pnpm (npm can substitute temporarily; CONTEXT prefers pnpm)

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥9.0.3 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/render/test_partition_cards_phase3.py -x` |
| Full suite command | `pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LOCKED-01 | thin→footer; transient→main degraded | unit | `pytest tests/render/test_partition_cards_phase3.py -x` | ✅ |
| ARCHIVE-01 | JSON emitted with schema_version 1 | unit | `pytest tests/render/test_digest_json_schema.py -x` | ❌ Wave 0 |
| DISPLAY-02/03 | briefing_top_n ordering | unit | `pytest tests/render/test_digest_json_briefing.py -x` | ❌ Wave 0 |
| OBS-01 | pipeline_notes zero-state + signals | unit | `pytest tests/render/test_pipeline_notes.py -x` | ❌ Wave 0 |
| DISPLAY-07 | mobile 375px no horizontal scroll | manual | UAT checklist | ❌ manual |
| DISPLAY-02 | tabs work JS disabled | manual | UAT checklist | ❌ manual |
| ARCHIVE-03 | canonical tags on `/` | manual | view-source UAT | ❌ manual |
| INTEGRATION | W19/W21 backfill | integration | `python -m pipeline.run render --week 2026-W21 && cd web && pnpm build` | ❌ Wave N |

### Sampling Rate

- **Per task commit:** `pytest tests/render/ -x`
- **Per wave merge:** `pytest -x -q`
- **Phase gate:** `pnpm build` green + W19/W21 visual UAT + full pytest suite

### Wave 0 Gaps

- [ ] `tests/render/test_digest_json_schema.py` — Pydantic/Zod parity, REQ ARCHIVE-01
- [ ] `tests/render/test_digest_json_partition_parity.py` — JSON lists match HTML render lists
- [ ] `tests/render/test_pipeline_notes.py` — OBS-01 zero-state + D-A4b thresholds
- [ ] `web/` Astro project — `pnpm build` smoke
- [ ] `pipeline/render/partition.py` — extract from html.py

### UAT Checklist (from CONTEXT — manual-only gates)

1. Backfill W19 + W21; compare LOCKED-01 routing vs existing `out/digest-*.html`
2. Synthetic week mixing all `_IN_PLACE_TRANSIENT_STATUSES` in JSON output
3. Tab navigation with JS disabled
4. Mobile 375px — no horizontal scroll; tab wrap
5. Canonical tags on `/` and `/business`
6. Archive index with 2 weeks + empty-state copy
7. Pipeline notes `<details>` absent when zero-state (not `display:none`)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Static site; no auth v1 |
| V3 Session Management | no | — |
| V4 Access Control | no | Public read-only digest |
| V5 Input Validation | yes | Zod at Astro build; Pydantic at emit; no user input forms |
| V6 Cryptography | no | No crypto in Phase 4 |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key in committed JSON/static HTML | Information disclosure | Never embed secrets in emitter; grep `GEMINI`, `sk-` in CI |
| XSS via card titles/TL;DR | Tampering | Astro auto-escapes `{expr}`; Python already escaped HTML — JSON is data, Astro text nodes safe |
| `target="_blank"` tabnabbing | Spoofing | `rel="noopener noreferrer"` (DISPLAY-08 / UI-SPEC) |

## Project Constraints (from .cursor/rules/)

- **GSD workflow:** Phase work should flow through `/gsd-plan-phase` → `/gsd-execute-phase`; planning artifacts stay in `.planning/`.
- **LOCKED-01:** Footer-aside is `summary_status='thin'` only — enforced in Python partition, not Astro.
- **No direct repo edits outside GSD** unless user explicitly bypasses (research artifact creation is orchestrator-requested).

## Sources

### Primary (HIGH confidence)

- [Astro Content Collections](https://docs.astro.build/en/guides/content-collections/) — loaders, Zod, getStaticPaths
- [Astro Styling / Tailwind](https://docs.astro.build/en/guides/styling/#tailwind) — `@tailwindcss/vite`, deprecated integration
- [Tailwind Astro guide](https://tailwindcss.com/docs/installation/framework-guides/astro) — Vite plugin setup
- [Astro @astrojs/tailwind integration doc](https://docs.astro.build/en/guides/integrations-guide/tailwind/) — deprecation notice
- In-repo: `pipeline/render/html.py`, `pipeline/orchestrator.py`, `pipeline/reporting/pipeline_report.py`
- `04-CONTEXT.md`, `04-UI-SPEC.md`, `.planning/LOCKED-DIRECTIVES.md`

### Secondary (MEDIUM confidence)

- `.planning/research/STACK.md` — versions (partially superseded for React/shadcn)
- `.planning/research/ARCHITECTURE.md` — build order steps 7–8, static-first pattern
- `.planning/research/PITFALLS.md` — #19 archive growth, #5 secret hygiene

### Tertiary (LOW confidence)

- Local Python 3.9.6 vs project 3.12+ — verify venv in execution

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — npm + official docs verified 2026-05-23
- Architecture: HIGH — codebase anchors inspected; extract partition recommended
- Pitfalls: HIGH — LOCKED-01 tests exist; OBS-01 silent-source is new

**Research date:** 2026-05-23
**Valid until:** 2026-06-23 (Astro/Tailwind stable); re-verify if Astro 6.4+ changes content config API
