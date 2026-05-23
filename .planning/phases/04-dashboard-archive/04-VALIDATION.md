---
phase: 4
slug: dashboard-archive
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-23
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

> This file is a scaffold seeded from the project template. The gsd-planner agent
> populates the Per-Task Verification Map, Wave 0 Requirements, and Manual-Only
> Verifications sections as it produces PLAN.md files. The Validation Architecture
> section of 04-RESEARCH.md is the source of truth for sampling rate and per-task
> verification design.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (Python pipeline) + vitest (Astro `web/`) |
| **Config file** | `pyproject.toml` / `pytest.ini` (existing) + `web/vitest.config.ts` (Wave 0 installs) |
| **Quick run command** | `pytest tests/render/ -q` + `pnpm --dir web test --run` |
| **Full suite command** | `pytest -q` + `pnpm --dir web test --run && pnpm --dir web build` |
| **Estimated runtime** | ~60 seconds (quick) / ~3 minutes (full incl. Astro build) |

---

## Sampling Rate

- **After every task commit:** Run the quick command for the relevant side (Python or web/).
- **After every plan wave:** Run the full suite (both Python and web).
- **Before `/gsd-verify-work`:** Full suite must be green; W19 + W21 backfill renders + `pnpm build` must succeed.
- **Max feedback latency:** ~60 seconds for quick, ~3 minutes for full.

---

## Per-Task Verification Map

*Planner fills this in once PLAN.md files are generated. Each task gets a row.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Planner fills this in. Expected items (from 04-RESEARCH.md §Validation Architecture):*

- [ ] `tests/render/test_partition.py` — golden tests for the extracted `_partition_cards` (LOCKED-01 router).
- [ ] `tests/render/test_digest_json.py` — schema_version, shape, LOCKED-01 round-trip on synthetic week mixing all `_IN_PLACE_TRANSIENT_STATUSES`.
- [ ] `web/vitest.config.ts` + `web/package.json` test script — Vitest install.
- [ ] `web/src/content.config.ts` — Zod schemas for `digests` + `reports` collections (build fails on shape mismatch).

---

## Manual-Only Verifications

*Planner fills this in from 04-RESEARCH.md §Validation Architecture "Manual UAT" subsection. Expected items:*

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tab navigation works without JS | DISPLAY-02, DISPLAY-04 | Requires real browser with JS disabled | Open `/`, disable JS in devtools, click each tab, verify navigation |
| Mobile viewport 375px renders without horizontal scroll | DISPLAY-07 | Visual / responsive | Open `/` at 375×667; verify no horizontal scroll, tab bar wraps cleanly |
| Canonical tags resolve to dated permalinks | ARCHIVE-03 | Requires view-source on rendered HTML | Open `/` and `/business`; view source; verify `<link rel="canonical">` |
| `<details>` Pipeline notes affordance is obvious on mobile | OBS-01 | Touch / visual | iOS Safari + Chrome Android; tap to expand |
| Play-icon glyph contrast against dark muted-foreground | DISPLAY-06 | Visual | Render a digest with YouTube items; verify glyph visible but not aggressive |
| Backfill correctness — W19 + W21 LOCKED-01 routing matches existing HTML | ARCHIVE-01, ARCHIVE-02 | Comparing two renders | Run backfill, open new Astro routes side-by-side with `out/digest-2026-W19.html` / `out/digest-2026-W21.html` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s for quick, < 3min for full
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
