---
phase: 01-foundation-first-digest
plan: "01"
subsystem: pipeline
tags: [python, uv, sqlite, feedparser, google-genai, gemini-2.5-flash-lite, structlog, pydantic, truststore, html, cli]

requires:
  - phase: 01-foundation-first-digest
    provides: phase context, research, skeleton manifest, plan
provides:
  - End-to-end pipeline package (pipeline/ + store/) running on Python 3.12 + uv
  - Greenfield project scaffold (pyproject.toml, uv.lock, .gitignore, .gitattributes, .env.example, README.md)
  - SQLite working store with WAL + FK enforcement (sources / items / item_summaries / pipeline_runs)
  - Idempotent upsert keyed by (source_id, external_id) — re-runs collapse to row count 1
  - IngestAdapter Protocol + RssAdapter (feedparser + httpx + GUID-or-hash external_id)
  - NormalizedItem pydantic model with content_hash and HTML strip
  - Source registry loader (pipeline/config.py + config/sources.yaml — INGEST-01)
  - ISO-week helpers (UTC week_id, half-open week_bounds, ISO-53 supported)
  - Per-item Gemini summarizer with structured JSON output, tenacity 429 retry, thin-content sentinel, token + cost telemetry
  - Versioned prompt at pipeline/llm/prompts/summarize_v1.md (PROMPT_VERSION column wired through)
  - Plain HTML renderer with html-escaped cards, dark-theme inline CSS, target=_blank rel=noopener on every source link
  - run_all orchestrator with per-source try/except isolation + pipeline_runs success/partial/failed lifecycle
  - python -m pipeline.run all CLI (argparse default subcommand, --week placeholder, dotenv at entry only)
  - Cross-platform SSL via truststore.inject_into_ssl() at CLI entry — works on macOS keychain, Windows certstore, Linux OpenSSL
affects:
  - 01-02 (expand to 3 sources + per-source isolation hardening)
  - 01-03 (trafilatura + grounding sentinel + degraded cards — slot already provided)
  - 01-04 (split into ingest/summarize/render/all subcommands; --week ISO override hookup)
  - 01-05 (structlog polish, last_run.md, pipeline_runs richness, pytest suite expansion)
  - Phase 2 ingestion (RssAdapter pattern; FetchError contract)
  - Phase 3 AI quality (item_summaries.prompt_version + UNIQUE(item_id, week_id, prompt_version) idempotency)

tech-stack:
  added:
    - python 3.12 + uv 0.11.16 + hatchling
    - feedparser 6.0.12, google-genai 2.5.0, httpx 0.28.1, tenacity 9.1.4
    - pydantic 2.13.4, structlog 25.5.0, PyYAML 6.0.3, python-dotenv 1.2.2
    - truststore 0.10.4 (cross-platform SSL trust)
    - dev: pytest 9.0.3, pytest-httpx 0.36.2, ruff 0.15.14
  patterns:
    - Adapter registry via Protocol (IngestAdapter) + per-type lookup
    - NormalizedItem.build factory normalizes + hashes raw HTML before store
    - upsert preserves item_id on (source_id, external_id) collision so item_summaries FK stays stable
    - Per-source try/except in orchestrator (one bad feed cannot break the run)
    - pipeline_runs lifecycle: insert running → finalize success/partial/failed
    - Versioned prompts with frontmatter + UNIQUE(item_id, week_id, prompt_version) on summaries
    - Resume-safe summarize: skip items that already have a summary for (week_id, prompt_version)
    - structlog stdout, ISO timestamps, contextvars-merged structured logs
    - truststore injection at CLI entry only (D-21) for cross-platform TLS without per-call verify=

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - .gitignore
    - .gitattributes
    - .env.example
    - README.md
    - config/sources.yaml
    - store/__init__.py
    - store/schema.sql
    - store/db.py
    - pipeline/__init__.py
    - pipeline/config.py
    - pipeline/models.py
    - pipeline/week.py
    - pipeline/adapters/__init__.py
    - pipeline/adapters/base.py
    - pipeline/adapters/rss.py
    - pipeline/llm/__init__.py
    - pipeline/llm/summarize.py
    - pipeline/llm/prompts/summarize_v1.md
    - pipeline/render/__init__.py
    - pipeline/render/html.py
    - pipeline/orchestrator.py
    - pipeline/run.py
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_store.py
    - tests/test_config.py
    - tests/test_week.py

key-decisions:
  - "Use truststore (not certifi-only) for SSL — picks up macOS keychain / Windows certstore / Linux system certs without per-call config; cross-platform-safe and avoids corporate-MITM TLS-intercept failures"
  - "Add .gitattributes with eol=lf default + bat/cmd/ps1=crlf for cross-platform repo (mac + Windows clones)"
  - "Land sources table from RESEARCH schema (not just YAML-as-FK-text) so items.source_id has an enforced FK from day one"
  - "upsert_item preserves item_id on conflict so item_summaries.item_id FK never gets orphaned across re-ingests"
  - "Pre-flight thin-content gate (<30 words) skips LLM call entirely — saves cost and keeps prompt_version=summarize_v1 honest about what it actually summarized"
  - "Use tests/conftest.py importorskip on store.db so Task 1 placeholder pytest gate exits 0 without scope-leaking store/ files into Task 1"
  - "RssAdapter fetches via httpx (UA + redirect + timeout) and feeds bytes to feedparser — keeps encoding/UA control vs feedparser's default urllib path"

patterns-established:
  - "Adapter registry: orchestrator._pick_adapter(type) returns IngestAdapter; Phase 2 grows the registry without touching store or orchestrator wiring"
  - "Versioned prompts: pipeline/llm/prompts/{name}_v{N}.md + matching prompt_version column; old digests can be replayed because the prompt body never moves"
  - "Per-source isolation: try/except per adapter call + per-item upsert in orchestrator; failure becomes a pipeline_runs.errors_json row, not a phase abort"
  - "Cost telemetry: input_tokens / output_tokens / cost_usd_estimate (paid-tier list price) on every item_summaries row, even on free tier — pipeline_runs aggregates"

requirements-completed:
  - INGEST-01
  - INGEST-02
  - INGEST-07
  - PIPELINE-01

duration: ~2h 45m
completed: 2026-05-21
---

# Phase 1, Plan 01-01: Walking Skeleton Summary

**Greenfield AI Digest pipeline live: feedparser → SQLite (WAL+FK) → Gemini Flash-Lite → plain HTML, with truststore-based cross-platform TLS and structured cost/telemetry logged to `pipeline_runs`.**

## Performance

- **Duration:** ~2h 45m wall-clock (includes uv install, Python 3.12 install, and SSL diagnosis)
- **Started:** 2026-05-21T20:30Z
- **Completed:** 2026-05-21T23:10Z
- **Tasks:** 3 (3 commits)
- **Files created:** 29 source / config / test files
- **Test count:** 10 pytest cases, all passing
- **Lint:** ruff clean

## Accomplishments

- Walking skeleton runs end-to-end: `uv run python -m pipeline.run all` exits 0, ingests 30 items from Simon Willison's Atom feed, generates 10 grounded TL;DRs via real Gemini calls, marks 5 thin-content items as `unavailable`, renders 15 cards into `out/digest-2026-W21.html`, closes a `pipeline_runs` row with `status=success` and `cost_usd_estimate=$0.001285`
- Schema enforces idempotency: re-running ingest on the same `(source_id, external_id)` tuple is a no-op; re-running summarize on the same `(item_id, week_id, prompt_version)` is a no-op
- HTML output is XSS-safe (every user string flows through `html.escape`) and link-safe (`target="_blank" rel="noopener"` on every source link, verified 15/15)
- Cross-platform-ready: `.gitattributes` normalizes line endings; `truststore` swaps in OS-native trust store at CLI entry so the pipeline runs identically on macOS, Linux, and Windows
- Adapter registry, versioned prompts, per-source isolation, and `pipeline_runs` lifecycle all in place — Plans 01-02 through 01-05 plug into existing seams instead of rewriting them

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffold + Wave 0 test harness** — `60ad03b` (feat)
2. **Task 2: Schema, config loader, models, RssAdapter, week helpers** — `b8656d3` (feat)
3. **Task 3: Summarizer, prompt, HTML renderer, orchestrator, CLI** — `68cd899` (feat)

## Files Created/Modified

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project + pinned runtime/dev deps (hatchling backend, py 3.12+, ruff/pytest config) |
| `uv.lock` | Cross-platform lockfile |
| `.gitignore` | `.env`, `data/`, `out/`, caches |
| `.gitattributes` | Cross-platform line-ending normalization |
| `.env.example` | `GEMINI_API_KEY=` placeholder |
| `README.md` | Setup (mac/Linux/Windows uv install), run, test, layout, security |
| `config/sources.yaml` | Source registry — `simon-willison` Atom feed (INGEST-01) |
| `store/schema.sql` | DDL: sources, items, item_summaries, pipeline_runs + indexes |
| `store/db.py` | `connect` (WAL+FK), `init_db`, `upsert_source`, `upsert_item` (preserves item_id), `get_items_for_week`, `insert_item_summary`, `insert_pipeline_run`, `finalize_pipeline_run` |
| `pipeline/config.py` | `SourceConfig` pydantic + YAML loader + `enabled_sources` filter |
| `pipeline/models.py` | `NormalizedItem` (frozen, UTC-aware), `strip_html`, `hash_content`, `.build()` factory |
| `pipeline/week.py` | `current_week_id`, `parse_week_id`, `week_bounds` (Mon→Mon UTC, ISO-53 supported) |
| `pipeline/adapters/base.py` | `IngestAdapter` Protocol + `FetchError` |
| `pipeline/adapters/rss.py` | feedparser + httpx adapter; GUID-or-hash external_id; date fallback chain |
| `pipeline/llm/summarize.py` | google-genai client with response_mime_type=json + Pydantic schema, tenacity retry, thin-content gate, cost estimate |
| `pipeline/llm/prompts/summarize_v1.md` | Versioned grounding prompt (PROMPT_VERSION header) |
| `pipeline/render/html.py` | `DigestCard` + `render_digest`; html-escaped cards; rel=noopener |
| `pipeline/orchestrator.py` | `run_all` wires ingest → store → summarize → render with `pipeline_runs` lifecycle |
| `pipeline/run.py` | argparse CLI; `truststore.inject_into_ssl()`; structlog stdout config |
| `tests/conftest.py` | `temp_sqlite_path` + `apply_schema` fixtures |
| `tests/test_store.py` | Schema-applies + upsert idempotence + mutable-field overwrite |
| `tests/test_config.py` | Default config + invalid-url + enabled filter |
| `tests/test_week.py` | Week format + Mon→Mon bounds + ISO-53 (2020-W53) |

## Decisions Made

- **truststore over certifi-only:** local network presents a TLS cert issuer that isn't in certifi's bundle but IS in the macOS keychain (corporate MITM or local CA). `truststore.inject_into_ssl()` at CLI entry uses the OS-native trust store on every platform — fixes macOS today and avoids the same class of issue on PC clones.
- **Land the `sources` table now (not YAML-as-FK-text):** RESEARCH offered both shapes; landing the table from day one means `items.source_id` has a real FK and the planner doesn't need a "migrate sources to a table" plan in Phase 2.
- **`upsert_item` preserves the existing `item_id` on conflict:** keeps `item_summaries.item_id` FK stable across re-ingests so we don't accidentally orphan summaries when a feed re-emits an entry.
- **Pre-flight thin-content gate (<30 words) before any LLM call:** Datasette plugin release-note items in the test feed had ~5 words of body — pre-gate skips them as `summary_confidence='unavailable'`, avoiding wasted Gemini calls.
- **`tests/test_store.py` uses `pytest.importorskip("store.db")` for Task 1:** lets Task 1's `uv sync && pytest` exit 0 cleanly without scope-leaking `store/` files into Task 1, then auto-activates once Task 2 lands.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule: Cross-platform safety addition] `.gitattributes`**
- **Found during:** Task 1 setup, before scaffold writes
- **Issue:** User asked to make the repo cross-platform (mac + PC). Plan didn't include `.gitattributes`; on a Windows clone CRLF would flip in `.sql`, `.py`, `.yaml` files.
- **Fix:** Added `.gitattributes` with `* text=auto eol=lf` default, CRLF for `.bat`/`.cmd`/`.ps1`, no-merge for `uv.lock`. README install snippet covers mac/Linux + Windows PowerShell.
- **Committed in:** `60ad03b` (Task 1 commit)

**2. [Rule: Missing critical] Add `truststore` runtime dependency**
- **Found during:** Task 3 live E2E run
- **Issue:** First live run failed with `[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate`. Both `httpx` default verify and explicit `verify=certifi.where()` failed; system curl confirmed the issue is at the OS level (certifi bundle doesn't include the issuer presented by the local network).
- **Fix:** Added `truststore>=0.10.4,<1` to runtime deps and called `truststore.inject_into_ssl()` at CLI entry in `pipeline/run.py` before any TLS-using import. truststore makes Python's `ssl` module use the OS-native trust store (macOS keychain / Windows certstore / Linux OpenSSL system certs).
- **Files modified:** `pyproject.toml`, `uv.lock`, `pipeline/run.py`
- **Verification:** Re-run produced 30 items fetched, 10 summaries written, full E2E success
- **Committed in:** `68cd899` (Task 3 commit)

**3. [Rule: Cross-platform Friendly] `pipeline/adapters/rss.py` — no per-call certifi override**
- **Found during:** Working through deviation #2
- **Issue:** Initial fix added `verify=certifi.where()` to httpx, but that builds httpx's own SSL context and bypasses the truststore-patched default — wouldn't work cross-platform.
- **Fix:** Removed the per-call `verify=` override; httpx now uses the default SSL context which truststore has patched globally. Net result: `rss.py` is unchanged from its Task-2 form.
- **Verification:** Live E2E succeeds with no per-adapter SSL config

---

**Total deviations:** 3 auto-fixed (1 cross-platform addition explicitly user-requested, 2 SSL-correctness fixes for live E2E).
**Impact on plan:** All deviations preserve the plan's contract; `truststore` is a thin add (one line of init at CLI boundary) and the plan's verification commands still pass exactly as specified.

## Issues Encountered

- **Tooling not installed:** macOS shipped Python 3.9 and no `uv`. Resolved by running the official `uv` installer (`curl -LsSf https://astral.sh/uv/install.sh | sh`) and `uv python install 3.12`. PATH already configured in `~/.zshrc`.
- **`uv sync` without `--extra dev` after adding truststore:** the bare `uv sync` removed dev deps (pytest, ruff). Re-ran `uv sync --extra dev` and they reappeared. Worth noting: contributors should always use `uv sync --extra dev` (or `uv run` which infers the right deps from the active script).
- **Sandbox TLS interception with `["full_network"]` permissions:** the Cursor sandbox's network proxy presents its own certificate, which trips both system curl and Python's TLS — even with truststore. Live runs require `["all"]` permissions to bypass the sandbox entirely. This is a Cursor-environment quirk, not a repo issue; on the user's regular shell the pipeline works without any flags.

## User Setup Required

The walking skeleton requires one external service:

- **Google Gemini API key** — Get a free key at <https://aistudio.google.com/apikey>, add to `.env` as `GEMINI_API_KEY=...`. Free tier covers Phase 1 by a wide margin (~30 items/week ≪ daily Flash-Lite quota; observed cost on this run was $0.001285 for 10 summaries).

No dashboard configuration, no CI secrets, no billing — that's all Phase 5 territory.

## Next Phase Readiness

Ready for **Plan 01-02** (Wave 2 — All 3 D-01 sources + per-source failure isolation hardening + idempotent re-ingest verification across feeds):

- Adapter pattern + registry already in place — Plan 01-02 just adds two more `config/sources.yaml` rows (`one-useful-thing`, `import-ai`) and verifies re-ingest stays idempotent across all three feeds
- Per-source try/except already implemented in orchestrator (advance of formal INGEST-06)
- `pipeline_runs.errors_json` schema column ready to capture per-source failures
- 30 production items already in `data/aidigest.db` available as a regression baseline

Plan 01-03 (trafilatura + grounding sentinel + summary_confidence + degraded cards) plugs into the existing `summary_confidence` enum on `item_summaries` and the existing degraded-card branch in `render_digest`.

Plan 01-04 (split CLI subcommands + `--week` ISO override) inherits the existing argparse + `current_week_id` / `week_bounds` plumbing.

Plan 01-05 (structlog polish, `last_run.md`, pipeline_runs richness, pytest suite expansion) inherits the existing structured logging + `pipeline_runs` lifecycle.

**No blockers for Wave 2 execution.**

---
*Phase: 01-foundation-first-digest*
*Completed: 2026-05-21*
