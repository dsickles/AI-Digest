---
phase: 4
slug: dashboard-archive
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-23
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

> Populated by gsd-planner from 04-RESEARCH.md §Validation Architecture and PLAN.md task breakdown.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥9 (Python pipeline) + Astro (`pnpm astro check` quick / `pnpm build` gate in `web/`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` + `web/astro.config.mjs` |
| **Quick run command** | `pytest tests/render/ -q` (Python); `cd web && pnpm astro check` (Astro waves 3–5 intermediate tasks) |
| **Gate run command** | Wave-final web tasks + Phase 6: `cd web && pnpm build` |
| **Full suite command** | `pytest -x -q && cd web && pnpm build` |
| **Estimated runtime** | ~10s Astro check / ~45s pytest quick / ~2 minutes full incl. Astro build |

---

## Sampling Rate

- **After every task commit:** Run the task's `<automated>` verify from the Per-Task Verification Map.
- **After every plan wave:** `pytest tests/render/ -x -q`; web wave-final tasks run `cd web && pnpm build` (gate).
- **Astro verify split (waves 3–5):** intermediate tasks → `cd web && pnpm astro check` (~10s); wave-final task → `cd web && pnpm build` (~2min). Paths after `cd web` use `dist/` not `web/dist/`.
- **Before `/gsd-verify-work`:** Full suite + W19/W21 backfill present + secret grep on `web/dist` and `web/src/content`.
- **Max feedback latency:** ~10s Astro check / ~45s pytest quick / ~2min full build gate.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 04-01 | 1 | ARCHIVE-01 | T-4-01-01 | Partition extract preserves LOCKED-01 routing | unit | `pytest tests/render/test_partition_cards_phase3.py -x -q` | ✅ | ⬜ |
| 4-01-02 | 04-01 | 1 | ARCHIVE-01 | T-4-01-02 | Docs aligned to 3 tabs | source | `grep -q partition._partition_cards .planning/LOCKED-DIRECTIVES.md` | ✅ | ⬜ |
| 4-02-01 | 04-02 | 2 | ARCHIVE-01, OBS-01 | T-4-02-01 | No secrets in JSON emitter | unit | `pytest tests/render/test_digest_json_schema.py tests/render/test_digest_json_partition_parity.py -x -q` | ❌ Wave 0 | ⬜ |
| 4-02-02 | 04-02 | 2 | ARCHIVE-01 | T-4-02-02 | Pre-partitioned lists via emit_digest_json | unit+wire | `pytest tests/render/test_digest_json_schema.py -x -q && grep -q no-html-preview pipeline/run.py` | ❌ | ⬜ |
| 4-03-01 | 04-03 | 3 | DISPLAY-01 | T-4-03-03 | Zod schema_version literal 1 | check | `cd web && pnpm install && pnpm astro check` | ❌ Wave 0 | ⬜ |
| 4-03-02 | 04-03 | 3 | DISPLAY-01,03,05,08 | T-4-03-02 | noopener on external links | build (gate) | `cd web && pnpm build && test -f dist/index.html` | ❌ | ⬜ |
| 4-04-01 | 04-04 | 4 | DISPLAY-02, ARCHIVE-03 | T-4-04-03 | Static routes only; no Astro partition | check | `cd web && pnpm astro check` | ❌ | ⬜ |
| 4-04-02 | 04-04 | 4 | DISPLAY-04,06 | T-4-04-02 | No ytimg.com hotlinks | build+grep (gate) | `cd web && pnpm build && ! grep -r ytimg.com dist` | ❌ | ⬜ |
| 4-05-01 | 04-05 | 5 | OBS-01 | T-4-05-01 | Plain-English pipeline_notes only | unit | `pytest tests/render/test_pipeline_notes.py -x -q` | ❌ Wave 0 | ⬜ |
| 4-05-02 | 04-05 | 5 | ARCHIVE-02,04, DISPLAY-07 | T-4-05-03 | PipelineNotes omitted when null; single mount in main | build (gate) | `cd web && pnpm build && test -f dist/archive/index.html` | ❌ | ⬜ |
| 4-06-01 | 04-06 | 6 | ARCHIVE-01 | T-4-06-03 | W19/W21 JSON schema_version 1 | integration | `test -f web/src/content/digests/2026-W21.json && grep -q schema_version web/src/content/digests/2026-W21.json` | ❌ | ⬜ |
| 4-06-02 | 04-06 | 6 | DISPLAY-01..08, ARCHIVE-01..04, OBS-01 | T-4-06-01 | dist free of API keys | integration | `pytest -x -q && cd web && pnpm build && ! grep -r GEMINI_API_KEY web/dist` | ❌ | ⬜ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Created during Plan 04-02 Task 1 and Plan 04-03 Task 1 (before dependent tasks):

- [ ] `pipeline/render/partition.py` — extracted LOCKED-01 router (Plan 04-01)
- [ ] `tests/render/test_digest_json_schema.py` — Pydantic schema + schema_version 1 (Plan 04-02)
- [ ] `tests/render/test_digest_json_partition_parity.py` — footer_aside vs main_feed LOCKED-01 parity (Plan 04-02)
- [ ] `tests/render/test_pipeline_notes.py` — OBS-01 zero-state + silent-source threshold (Plan 04-05)
- [ ] `web/` Astro 6 project + `web/src/content.config.ts` — Zod digests/reports collections (Plan 04-03)
- [ ] `web/package.json` with `pnpm build` script — build smoke gate (Plan 04-03)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tab navigation without JS | DISPLAY-02, DISPLAY-04 | Browser JS disabled | Open `/`, disable JS, click Briefing/Edtech/Business/Technical/Archive; each navigates |
| Mobile 375px no horizontal scroll | DISPLAY-07 | Visual responsive | DevTools 375×667 on `/` and `/archive`; no horizontal scrollbar |
| Canonical tags on latest week | ARCHIVE-03 | view-source | On `/` and `/business`, confirm `<link rel="canonical" href="/digest/2026-Wxx">` |
| Pipeline notes mobile affordance | OBS-01 | Touch UX | iOS Safari / Chrome Android: expand `<details>` on Briefing |
| Play-icon contrast | DISPLAY-06 | Visual | W21 page with YouTube items; glyph visible on `#9aa3b2` |
| W19/W21 LOCKED-01 vs HTML | ARCHIVE-01 | Side-by-side compare | Compare `footer_aside` in JSON vs `out/digest-2026-W19.html` `#also-seen` |
| Pipeline notes zero-state | OBS-01 | DOM inspection | Week with no failures: no `<details>` pipeline element in DOM |
| Archive empty-state copy | ARCHIVE-02 | Edge case | Fresh clone with 0 digests (optional); verify UI-SPEC empty copy |

*Full checklist duplicated in `.planning/phases/04-dashboard-archive/04-UAT.md` (Plan 04-06).*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s for quick (`pnpm astro check` / pytest), < 3min for full build gate
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending (execution)
