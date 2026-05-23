---
phase: 04-dashboard-archive
reviewed: 2026-05-23T23:30:00Z
depth: standard
files_reviewed: 42
files_reviewed_list:
  - pipeline/render/partition.py
  - pipeline/render/digest_json.py
  - pipeline/render/html.py
  - pipeline/render/__init__.py
  - pipeline/orchestrator.py
  - pipeline/run.py
  - pipeline/reporting/pipeline_report.py
  - tests/render/test_digest_json_partition_parity.py
  - tests/render/test_digest_json_schema.py
  - tests/render/test_pipeline_notes.py
  - tests/budget/test_budget_halt.py
  - web/src/content.config.ts
  - web/src/pages/index.astro
  - web/src/pages/[topic].astro
  - web/src/pages/archive.astro
  - web/src/pages/digest/[week].astro
  - web/src/pages/digest/[week]/[topic].astro
  - web/src/components/ArchiveList.astro
  - web/src/components/BackToLatest.astro
  - web/src/components/BriefingTopN.astro
  - web/src/components/Card.astro
  - web/src/components/CategorySection.astro
  - web/src/components/DigestBriefing.astro
  - web/src/components/FooterAside.astro
  - web/src/components/Header.astro
  - web/src/components/PartialPublishNotice.astro
  - web/src/components/PipelineNotes.astro
  - web/src/components/PlayIcon.astro
  - web/src/components/TabBar.astro
  - web/src/components/WeeklySynthesis.astro
  - web/src/lib/archiveExcerpt.ts
  - web/src/lib/canonicalUrl.ts
  - web/src/lib/copy.ts
  - web/src/lib/formatWeekRange.ts
  - web/src/lib/latestWeek.ts
  - web/src/lib/topics.ts
  - web/src/layouts/BaseLayout.astro
  - web/astro.config.mjs
  - web/package.json
  - README.md
  - .gitignore
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: major
---

# Phase 4: Code Review Report

**Reviewed:** 2026-05-23T23:30:00Z  
**Depth:** standard  
**Files Reviewed:** 42  
**Status:** major

## Summary

Phase 4 delivers a solid LOCKED-01 partition extract (`partition.py`), a pre-partitioned digest JSON emitter with OBS-01 pipeline notes, and an Astro static dashboard with archive routes. Partition routing, JSON schema tests, and footer-aside rendering align with LOCKED-01. The primary defect is a **week-ID URL case mismatch**: Astro content collection IDs are lowercased (`2026-w21`) while archive links and canonical tags emit uppercase ISO week IDs (`2026-W21`), producing broken links on case-sensitive hosts and incorrect canonical URLs. Several maintainability gaps (stale docstring, duplicated degraded copy) increase LOCKED-01 regression risk but do not affect current routing behavior.

## Critical Issues

*(none — LOCKED-01 routing implementation and tests are correct)*

## Warnings

### WR-01: Week permalink case mismatch breaks archive and canonical links

**File:** `web/src/components/ArchiveList.astro:38`, `web/src/lib/canonicalUrl.ts:4-8`, `web/src/pages/index.astro:12`

**Issue:** Astro's glob content loader lowercases collection entry IDs (`digest.id` → `2026-w21`), and static routes are built at `/digest/2026-w21/`. Archive "Read this week" links and `<link rel="canonical">` tags use `data.week_id` from JSON (`2026-W21`, uppercase `W`). Built output confirms the mismatch: archive links point to `/digest/2026-W21` while pages exist at `/digest/2026-w21`; index canonical is `/digest/2026-W21` while the permalink page is `/digest/2026-w21`. Works on case-insensitive macOS dev; fails on Linux/GitHub Pages.

**Fix:** Derive URL slugs from `digest.id` (or normalize consistently):

```typescript
// web/src/lib/canonicalUrl.ts
export function canonicalDigestUrl(digestId: string, topic?: Topic): string {
  const slug = digestId.toLowerCase();
  return topic ? `/digest/${slug}/${topic}` : `/digest/${slug}`;
}
```

Update `ArchiveList.astro`, `index.astro`, and `[topic].astro` to pass `digest.id` instead of `data.week_id` for href generation.

---

### WR-02: Stale `DigestCard` docstring contradicts LOCKED-01 routing

**File:** `pipeline/render/partition.py:82-87`

**Issue:** The class docstring still states that `api_error`, `parse_error`, `client_init_error`, and `None` route to the footer. LOCKED-01 (2026-05-23 refinement) routes only `thin` to the footer; all transient statuses go in-place. The implementation in `_partition_cards` is correct — the docstring is wrong and could mislead a future edit into reintroducing a LOCKED-01 violation.

**Fix:** Replace lines 82–87 with the routing table from the module header (thin → footer; transient + healthy → main feed).

---

### WR-03: Duplicated LOCKED degraded body copy in Astro Card component

**File:** `web/src/components/Card.astro:18`

**Issue:** In-place degraded cards fall back to a hardcoded string `"The summary couldn't be generated this week."` instead of importing `QUOTA_BODY_COPY` from a shared module. Python emits `degraded_body` from `QUOTA_BODY_COPY` in JSON, so normal paths are fine, but the Astro fallback duplicates the LOCKED exact-string and could drift if the Python constant changes.

**Fix:** Export the copy from `web/src/lib/copy.ts` (mirroring `partition.py`) and import it in `Card.astro`:

```typescript
export const QUOTA_BODY_COPY = "The summary couldn't be generated this week.";
```

---

### WR-04: `transcript_missing` omitted from pipeline report summary counts

**File:** `pipeline/reporting/pipeline_report.py:21-28`

**Issue:** `_SUMMARY_STATUS_KEYS` lists six statuses but omits `transcript_missing`, which LOCKED-01 treats as a first-class in-place transient status. Rows with this status are silently dropped from the `summary_status` block in archived reports, understating pending-transcript volume in OBS-02 telemetry.

**Fix:** Add `"transcript_missing"` to `_SUMMARY_STATUS_KEYS`.

---

## Info

### IN-01: Archived week pages omit canonical metadata

**File:** `web/src/pages/digest/[week].astro:22`, `web/src/pages/digest/[week]/[topic].astro:29`

**Issue:** Latest-week routes (`/`, `/business`) emit `<link rel="canonical">`; archived week routes do not pass `canonicalHref` to `BaseLayout`. UI-SPEC focuses on latest-week canonicals (ARCHIVE-03), so this is a minor SEO gap rather than a functional bug.

**Fix:** Pass `canonicalHref={canonicalDigestUrl(digest.id, topic)}` using the normalized slug from WR-01.

---

### IN-02: `PipelineNotes.show` field is never honored

**File:** `web/src/components/PipelineNotes.astro:16`

**Issue:** The component renders whenever `pipelineNotes` is truthy, ignoring `show: false`. The emitter always sets `show: true` when notes exist, so no current user impact.

**Fix:** Guard with `pipelineNotes?.show !== false` if future emitters need to suppress display.

---

### IN-03: `run all` lacks `--no-html-preview` / `--web-out` flags

**File:** `pipeline/run.py:169-175`, `pipeline/orchestrator.py:2001-2002`

**Issue:** Phase 4 documents `render --no-html-preview` for CI publish paths, but `all` always writes deprecated HTML and cannot override the web content output dir. Phase 5 GHA wiring will likely call `render` separately; not blocking now.

**Fix:** Thread render flags through `run_all` when full-pipeline CI publish is needed.

---

## Positive Observations

- **LOCKED-01 enforcement:** `emit_digest_json()` calls `_partition_cards()` before serializing lists; parity tests in `test_digest_json_partition_parity.py` cover thin, quota_exhausted, and all in-place transient statuses.
- **Import boundaries:** `partition.py` and `digest_json.py` avoid adapter/LLM imports (D-20).
- **Security:** No `innerHTML`/`set:html`; Astro auto-escapes user-facing strings; digest JSON emitter source grep confirms no GEMINI literals.
- **OBS-01:** Pipeline notes builder excludes thin-status references; silent-source streak requires three consecutive empty weeks; fetch-failure copy matches UI-SPEC.
- **Footer aside:** `FooterAside.astro` renders link-only items with no body copy, matching LOCKED-01.

---

_Reviewed: 2026-05-23T23:30:00Z_  
_Reviewer: Claude (gsd-code-reviewer)_  
_Depth: standard_
