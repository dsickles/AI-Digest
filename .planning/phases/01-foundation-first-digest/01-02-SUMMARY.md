---
phase: 01-foundation-first-digest
plan: "02"
subsystem: pipeline
tags: [python, sqlite, feedparser, httpx, pytest, rss, atom, upsert, structlog]

requires:
  - phase: 01-foundation-first-digest
    plan: "01"
    provides: walking skeleton — RssAdapter, orchestrator, upsert_item, single-source config
provides:
  - Full D-01 three-source registry in config/sources.yaml (simon-willison, one-useful-thing, import-ai)
  - Hardened INSERT ON CONFLICT upsert with ingested_at refresh and stable item_id (INGEST-08)
  - Fixture-backed RSS/Atom adapter contract tests (Simon Atom + Substack RSS + hash fallback)
  - Per-source FetchError isolation with structlog error + pipeline_runs.errors_json (no run abort)
  - HTTP 304 Not Modified treated as success with zero new items
affects:
  - 01-03 (trafilatura fallback builds on adapter + store seams)
  - 01-04 (CLI subcommands inherit three-source ingest loop)
  - 01-05 (pytest suite expansion — test_ingest.py is the new anchor)
  - Phase 2 (FetchError + per-source try/except pattern proven)

tech-stack:
  added: []
  patterns:
    - ON CONFLICT(source_id, external_id) DO UPDATE with ingested_at refresh
    - Fixture monkeypatch on rss._fetch_bytes for offline adapter tests
    - FetchError-specific catch + generic Exception fallback in orchestrator ingest loop
    - HTTP 304 → empty item list (not an error)

key-files:
  created:
    - tests/fixtures/feeds/simon_atom.xml
    - tests/fixtures/feeds/substack_rss.xml
    - tests/fixtures/feeds/no_guid_rss.xml
    - tests/test_ingest.py
  modified:
    - config/sources.yaml
    - store/db.py
    - pipeline/orchestrator.py
    - pipeline/adapters/rss.py
    - tests/test_store.py
    - tests/test_config.py

key-decisions:
  - "Keep FetchError in pipeline/adapters/base.py (already established in 01-01) — rss.py imports it; no duplicate definition needed"
  - "upsert_item uses SQLite ON CONFLICT DO UPDATE instead of SELECT-then-UPDATE/INSERT — single round-trip, ingested_at always refreshed on re-ingest"
  - "_fetch_bytes returns (body, status_code) tuple so 304 is distinguishable from empty 200 bodies"

patterns-established:
  - "Offline adapter tests: monkeypatch pipeline.adapters.rss._fetch_bytes with fixture bytes + status 200"
  - "Isolation tests: monkeypatch orchestrator._pick_adapter to inject per-source success/failure adapters"

requirements-completed:
  - INGEST-01
  - INGEST-02
  - INGEST-07
  - INGEST-08

duration: ~25min
completed: 2026-05-21
---

# Phase 1, Plan 01-02: Three Sources + Idempotent Upsert Summary

**All three D-01 RSS feeds configured with proven INGEST-08 idempotent upsert, fixture-backed adapter tests, and per-source failure isolation that keeps the weekly ingest alive when one feed fails.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-21T23:45Z
- **Completed:** 2026-05-21T00:10Z
- **Tasks:** 3 (3 commits)
- **Files modified:** 9
- **Test count:** 21 pytest cases (9 new in test_ingest.py + test_upsert_idempotent), all passing
- **Lint:** ruff clean

## Accomplishments

- `config/sources.yaml` lists all three D-01 sources enabled: simon-willison, one-useful-thing, import-ai; `load_sources()` returns 3
- `upsert_item` hardened with `INSERT ... ON CONFLICT(source_id, external_id) DO UPDATE` — stable `item_id`, refreshed `ingested_at`; `test_upsert_idempotent` proves single row per key
- Fixture-backed adapter tests cover Atom parsing, Substack `guid` external_id, and sha256 hash fallback when guid absent
- Orchestrator ingest catches `FetchError` per source, logs at error level, appends to `stats.errors`, continues; simulated failure test confirms good source still ingests
- `RssAdapter` treats HTTP 304 as success with zero items (not an error)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add remaining seed sources** — `59a1821` (feat)
2. **Task 2: Idempotent upsert and external_id contract tests** — `d6d9fd2` (feat)
3. **Task 3: Per-source failure isolation in ingest** — `b812b87` (test)

**Plan metadata:** `4b18855` (docs: complete plan)

## Files Created/Modified

| File | Purpose |
|------|---------|
| `config/sources.yaml` | Three D-01 RSS sources (INGEST-01 complete for Phase 1 seed list) |
| `store/db.py` | ON CONFLICT upsert with ingested_at refresh |
| `pipeline/adapters/rss.py` | `(body, status)` fetch tuple; 304 → empty list |
| `pipeline/orchestrator.py` | FetchError-specific catch; error-level structlog on ingest failure |
| `tests/fixtures/feeds/*.xml` | Minimal Atom + RSS fixtures for offline adapter tests |
| `tests/test_ingest.py` | Parser, external_id, 304, isolation tests |
| `tests/test_store.py` | `test_upsert_idempotent` (INGEST-08) |
| `tests/test_config.py` | Asserts all three D-01 sources present |

## Decisions Made

- **FetchError stays in `base.py`:** Plan text mentions defining it in `rss.py`, but 01-01 already placed it on the adapter Protocol module — importing from `base.py` is the correct contract boundary.
- **ON CONFLICT over SELECT-then-branch:** Plan asked for INSERT ON CONFLICT; refactored from the working SELECT/UPDATE pattern in 01-01 to match spec and refresh `ingested_at` atomically.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `_fetch_bytes` return type change for 304 support**
- **Found during:** Task 3 (304 handling)
- **Issue:** Task 2 fixture monkeypatches returned raw `bytes`; Task 3 changed `_fetch_bytes` to return `(body, status_code)`.
- **Fix:** Updated `_fetch_fixture` helper to return `(body, 200)` tuple.
- **Files modified:** `tests/test_ingest.py`
- **Verification:** All 21 pytest cases pass
- **Committed in:** `b812b87` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (test helper adjusted for API change in same plan)
**Impact on plan:** No scope change; deviation is internal test plumbing for the 304 feature requested in Task 3.

## Issues Encountered

None — all verification ran offline with fixtures. Live three-feed re-run (`python -m pipeline.run all` twice) deferred to manual follow-up (requires network outside sandbox).

## User Setup Required

None — no new external services. Existing `GEMINI_API_KEY` from Plan 01-01 suffices for live E2E when run manually.

## Manual Follow-up

- Run `uv run python -m pipeline.run all` twice on a network-enabled shell and confirm `SELECT COUNT(DISTINCT source_id || external_id) FROM items` is unchanged on second run across all three feeds.

## Next Phase Readiness

Ready for **Plan 01-03** (Wave 3 — trafilatura fallback, grounding sentinel, summary_confidence, degraded cards):

- Three-source ingest loop proven; adapter fixtures reusable for thin-content edge cases
- `summary_confidence` column and degraded render branch already exist from 01-01
- INGEST-08 automated; ROADMAP success criterion #3 satisfied in unit tests

**No blockers for Wave 3 execution.**

## Self-Check: PASSED

- `tests/test_ingest.py` — FOUND
- `tests/test_store.py::test_upsert_idempotent` — FOUND (passes)
- Commits `59a1821`, `d6d9fd2`, `b812b87` — FOUND in git log

---
*Phase: 01-foundation-first-digest*
*Completed: 2026-05-21*
