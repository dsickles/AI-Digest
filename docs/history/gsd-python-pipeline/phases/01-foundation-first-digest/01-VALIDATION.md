---
phase: 1
slug: foundation-first-digest
status: signed-off
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-21
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `01-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python 3.12+) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 installs |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds (unit + integration; excludes `@pytest.mark.live`) |

`@pytest.mark.live` reserved for opt-in tests that hit real Gemini — never run in default suite.

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

> Populated by the planner during plan generation. Each plan task should append a row mapping task ID → requirement → automated command.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | INGEST-01 | T-01-01 | .env gitignored; no key in repo | unit | `pytest tests/test_store.py -x -q` | ✅ | ✅ green |
| 1-01-02 | 01 | 1 | INGEST-01, INGEST-02, INGEST-07 | T-01-03 | RSS treated as untrusted input | unit | `pytest tests/test_store.py -x -q` | ✅ | ✅ green |
| 1-01-03 | 01 | 1 | PIPELINE-01 | T-01-02, T-01-04 | html.escape; grounding prompt | smoke | `python -c "import pipeline.run"` + manual E2E with key | ✅ | ✅ green |
| 1-02-01 | 02 | 2 | INGEST-01, INGEST-02 | T-01-06 | No hard-coded feed URLs in code | unit | `python -c "from pipeline.config import load_sources; assert len(load_sources())==3"` | ✅ | ✅ green |
| 1-02-02 | 02 | 2 | INGEST-07, INGEST-08 | T-01-07 | PK uniqueness enforced | integration | `pytest tests/test_store.py tests/test_ingest.py -x -q` | ✅ | ✅ green |
| 1-02-03 | 02 | 2 | INGEST-02 | T-01-06 | Per-source isolation | unit | `pytest tests/test_ingest.py -x -q` | ✅ | ✅ green |
| 1-03-01 | 03 | 3 | PIPELINE-01 | T-01-08 | trafilatura fetch timeout | unit | `python -c "from pipeline.content_enrich import prepare_input_text"` | ✅ | ✅ green |
| 1-03-02 | 03 | 3 | PIPELINE-01 | T-01-08, T-01-04 | Sentinel + prompt_version | unit | `pytest tests/test_summarize.py -x -q` | ✅ | ✅ green |
| 1-03-03 | 03 | 3 | PIPELINE-01 | T-01-02 | Degraded path escaped | unit | `pytest tests/test_render.py -x -q` | ✅ | ✅ green |
| 1-04-01 | 04 | 4 | PIPELINE-01 | T-01-10 | week_id validated | unit | `python -c "from pipeline.week import parse_week_id, week_bounds"` | ✅ | ✅ green |
| 1-04-02 | 04 | 4 | PIPELINE-01 | T-01-11 | render no network | smoke | `python -m pipeline.run --help \| grep -i week` | ✅ | ✅ green |
| 1-04-03 | 04 | 4 | PIPELINE-01 | T-01-10 | D-22 UAT test | integration | `pytest tests/test_pipeline.py -x -q` | ✅ | ✅ green |
| 1-05-01 | 05 | 5 | PIPELINE-01 | T-01-05 | No secrets in logs | integration | `pytest tests/test_pipeline.py -x -q` | ✅ | ✅ green |
| 1-05-02 | 05 | 5 | PIPELINE-01 | T-01-01 | last_run.md no API key | smoke | `test -f out/last_run.md` after run | ✅ | ✅ green |
| 1-05-03 | 05 | 5 | INGEST-01–08, PIPELINE-01 | T-01-02 | rel=noopener; header polish | full suite | `pytest tests/ -x -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Greenfield project — the entire `tests/` tree does not exist yet. Wave 0 must install pytest, create `tests/conftest.py` with shared fixtures (temp SQLite DB, recorded feed XML loader, mocked `genai.Client`), and stub one test per phase requirement:

- [x] `tests/conftest.py` — shared fixtures (temp DB, feed-xml loader, mocked Gemini client)
- [x] `tests/fixtures/feeds/` — recorded XML snippets for Atom (Simon Willison) and Substack RSS (One Useful Thing, Import AI)
- [x] `tests/test_ingest.py` — stubs for INGEST-01, INGEST-02
- [x] `tests/test_store.py` — stubs for INGEST-07, INGEST-08 (PK uniqueness, idempotent upsert)
- [x] `tests/test_pipeline.py` — stub for PIPELINE-01 (end-to-end smoke)
- [x] `pyproject.toml` `[project.optional-dependencies] dev = ["pytest", "pytest-httpx"]` + pytest config

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Status |
|----------|-------------|------------|-------------------|--------|
| Real Gemini summary is grounded (no invented facts) | PIPELINE-01 / D-04 | LLM output is non-deterministic; semantic grounding cannot be asserted by snapshot | Run `pytest -m live tests/test_summarize.py::test_real_summary_groundedness` after exporting `GEMINI_API_KEY`; manually read the summary against the fixture article | ⬜ pending |
| Digest HTML is "Sunday-morning readable" in a browser | D-15, D-17, D-18 | Visual judgment; styling intent is qualitative | `open out/digest-2026-W21.html` in browser; confirm dark theme, ~720px content width, system font, source badges visible, links open in new tab | ⬜ pending |
| `--week` backfill works for a past week | D-11, D-12, D-22 | UAT discoverability policy requires a human-run check, not just a unit test | Run `python -m pipeline.run all --week 2026-W19`; confirm `out/digest-2026-W19.html` exists and references week of May 4–10, 2026 | ⬜ pending |
| Live three-feed E2E idempotency | INGEST-08 | Requires real network + non-sandbox TLS | Run `pipeline.run all` twice; confirm stable item counts in SQLite | ⬜ pending |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags (`--watch`, `-w`) in any verify command
- [x] Feedback latency < 15s (quick suite)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** Phase 1 automated validation complete 2026-05-21. Manual UAT rows remain for live network/browser checks.
