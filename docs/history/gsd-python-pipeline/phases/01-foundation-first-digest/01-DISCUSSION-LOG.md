# Phase 1: Foundation + First Digest - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-21
**Phase:** 1-foundation-first-digest
**Areas discussed:** Seed sources, LLM grounding & degraded content, Debuggability slice (Area 2 follow-up), Week window definition, Plain-HTML output shape, Run interface (CLI), Standing project-level policy on hidden capabilities

---

## Area 1 — Seed source list

| Option | Description | Selected |
|--------|-------------|----------|
| Accept recommended 3 | Simon Willison (atom/everything) + One Useful Thing (Substack) + Import AI (Substack) | ✓ |
| Use 2 of recommended | Drop one of the three | |
| Custom list | User pastes own URLs | |
| Swap one | Keep 2, replace 1 | |

**User's choice:** Accept the recommended 3.
**Notes:** All three are full-text feeds; one technical voice (Simon Willison), two business-leaning voices (One Useful Thing, Import AI). Chosen for parseability + variety + known stability. Recorded in CONTEXT.md D-01/D-02.

---

## Area 2a — LLM input strategy (first pass)

| Option | Description | Selected |
|--------|-------------|----------|
| Snippet-only | RSS body only; simplest | |
| Always fetch full | GET canonical URL + extract main content for every item | |
| Hybrid (500-char threshold) | Snippet by default; fetch full only when RSS body < 500 chars | (deferred — user asked for clarification) |
| Hybrid custom threshold | User picks the threshold | |

**User's response:** Asked for clarification on how snippet-only could produce good summaries.
**Notes:** Claude explained the distinction between full-text feeds (where RSS body IS the article) vs truncated feeds, and that all three Phase-1 sources are full-text. Re-asked with that context.

## Area 2a — LLM input strategy (second pass)

| Option | Description | Selected |
|--------|-------------|----------|
| Snippet-only | Simpler; fragile if a feed becomes truncated | |
| Hybrid 500-char | Snippet by default; full-fetch fallback under threshold | (deferred — user asked observability question) |
| Always fetch full | Most robust, slowest, most failure modes | |
| Hybrid custom threshold | User picks the threshold | |

**User's response:** Asked how future fetch attempts' failures would be visible and debuggable.
**Notes:** This triggered the debuggability slice discussion (separate section below). After answering, Claude re-asked once more.

## Area 2a — LLM input strategy (final)

| Option | Description | Selected |
|--------|-------------|----------|
| Snippet-only | | |
| Hybrid 500-char (with observability slice) | | ✓ |
| Always fetch full | | |
| Hybrid custom threshold | | |

**User's choice:** Hybrid with 500-char threshold.
**Notes:** Locked as CONTEXT.md D-03 with `trafilatura` preferred for extraction, failures logged via the debuggability slice.

---

## Area 2b — Degraded-content behavior

| Option | Description | Selected |
|--------|-------------|----------|
| A — Skip silently | Item removed from digest | |
| B — Card with note | Title+link+date + `[summary unavailable]` line | |
| C — Same as B + persist `summary_confidence` field now | Phase 3 inherits the column without migration | ✓ |

**User's choice:** Option C.
**Notes:** User also asked whether a "force re-summarize" button could be added later. Claude clarified that no current phase contains this; captured as a deferred idea. Locked as CONTEXT.md D-04/D-05/D-06.

---

## Area 2 follow-up — Observability slice in Phase 1?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — full slice | structlog stdout + `out/last_run.md` + `pipeline_runs` SQLite table | ✓ |
| Yes — minimal | structlog stdout only | |
| No | Keep Phase 1 strict to roadmap; raw stdout only | |

**User's choice:** Yes — full slice.
**Notes:** Officially Phase 3 owns `pipeline_report.json` and Phase 4 owns Briefing notes UI; Claude flagged that the slice is enabling-only (debuggability for Phase 1 iteration) and creates the substrate later phases consume. Locked as CONTEXT.md D-07/D-08/D-09.

---

## Area 3 — "This week" window (first pass)

| Option | Description | Selected |
|--------|-------------|----------|
| A+D — ISO week + `--week` CLI override | Canonical week_id is `YYYY-Www`; CLI accepts `--week` for backfill | (deferred — user asked what CLI override meant) |
| A only — ISO week, no CLI | | |
| B — Sun–Sat US-style window | | |
| C — Trailing 7 days from now | Simplest but breaks idempotency | |
| Discuss boundary trade-off | | |

**User's response:** Asked what "CLI override" meant.
**Notes:** Claude explained the override with concrete use cases (missed-week recovery, prompt iteration, manual catch-up, dev testing), trade-offs, and recommended including it now to avoid Phase-5 refactor of `datetime.now()` calls.

## Area 3 — "This week" window (final)

| Option | Description | Selected |
|--------|-------------|----------|
| ISO week + `--week` CLI override | Recommended | ✓ |
| ISO week only, no CLI | | |
| Sunday–Saturday window | | |
| Trailing 7 days | | |
| More questions | | |

**User's choice:** ISO week + `--week` CLI override.
**Notes:** User asked that the override be documented in capabilities so it isn't forgotten, AND tested so it's known to work. This triggered the project-level policy decision below. Locked as CONTEXT.md D-10/D-11/D-12.

---

## Standing project-level policy — Hidden-capability discoverability

| Option | Description | Selected |
|--------|-------------|----------|
| Always doc + always test | CONTEXT.md decision + README + UAT/verification check; opt-out required | ✓ |
| Always doc; test on request | | |
| Ask each time | | |
| Doc only, no test | | |

**User's choice:** Always doc + always test.
**Notes:** Captured as a project-level decision (CONTEXT.md D-22) that will be promoted to PROJECT.md Key Decisions at the next phase transition. Applies retroactively to the `--week` flag from Area 3.

---

## Area 4a — HTML file location/naming

| Option | Description | Selected |
|--------|-------------|----------|
| `out/digest-2026-W21.html` | Dated, gitignored | ✓ |
| `out/index.html` (overwritten) | No Phase 1 archive | |
| `out/2026-W21/index.html` | Directory-per-week | |
| `web/src/content/digests/2026-W21.html` | Into Astro's future path | |

**User's choice:** `out/digest-{week_id}.html`.
**Notes:** Locked as CONTEXT.md D-13.

---

## Area 4b — Structure within the file

| Option | Description | Selected |
|--------|-------------|----------|
| Flat chrono + source badge per card | Matches Phase 4 Briefing shape | ✓ |
| Grouped by source with H2 headers | | |
| Flat chrono, no source label | | |

**User's choice:** Flat newest-first with source badge per card.
**Notes:** Chosen as a structural dry-run of the Phase 4 Briefing tab. Locked as CONTEXT.md D-14.

---

## Area 4c — Source link target

| Option | Description | Selected |
|--------|-------------|----------|
| New tab (`target="_blank" rel="noopener"`) | Matches Phase 4 DISPLAY-08 | ✓ |
| Same tab | | |

**User's choice:** New tab.
**Notes:** Locked as CONTEXT.md D-16.

---

## Area 4d — Styling level

| Option | Description | Selected |
|--------|-------------|----------|
| A — Truly bare HTML | Default browser styling | |
| B — ~40 lines inline `<style>` | Readable line-length, system font, dark bg, light hierarchy | ✓ |
| C — Polished single-file CSS | Hover/focus states, design system | |

**User's choice:** Option B.
**Notes:** Locked as CONTEXT.md D-17. Specifically NOT the Phase 4 dashboard — must remain throwaway. PITFALLS #25 (content-first gate) honored.

---

## Area 5 — Run interface (CLI shape)

| Option | Description | Selected |
|--------|-------------|----------|
| C — Split subcommands + `all` default | `ingest`/`summarize`/`render`/`all`; bare command runs `all` | ✓ |
| B — Split subcommands only | Always require subcommand | |
| A — Single end-to-end command only | | |
| More questions | | |

**User's choice:** Option C.
**Notes:** Chosen specifically to enable cheap iteration on the summarization prompt (re-run `summarize` without re-fetching) and on HTML/CSS (re-run `render` without network or LLM). Locked as CONTEXT.md D-19/D-20/D-21.

---

## Final check — anything else?

| Option | Description | Selected |
|--------|-------------|----------|
| Write the context | | ✓ |
| Discuss LLM choice (Gemini Flash-Lite) | | |
| Discuss Python project tooling | | |
| Discuss `GEMINI_API_KEY` handling | | |
| Freeform | | |

**User's choice:** Write the context.
**Notes:** Model choice, project tooling, and API-key handling left to Claude's discretion within research-recommended defaults. See CONTEXT.md "Claude's Discretion" section.

---

## Claude's Discretion

- LLM batch-vs-streaming call shape (research recommends batch)
- Exact `IngestAdapter` protocol signature and `NormalizedItem` Pydantic shape
- Whether `trafilatura` or `readability-lxml` is the primary extractor (behavior is what's locked, not the library)
- Python tooling (`uv` vs `pip + venv`, lockfile placement, ruff config)
- `GEMINI_API_KEY` loading mechanism (`.env` via `python-dotenv` vs plain `os.environ`)
- Test framework, CI hook timing, and coverage targets (with the one mandatory `--week` UAT check per D-22)

## Deferred Ideas

- **In-dashboard "force re-summarize this card" button** — not in any current phase; would require webhook → GHA workflow_dispatch → targeted re-summarize + re-render. Captured for roadmap backlog; revisit post-Phase 5 as v1.x or v2.
