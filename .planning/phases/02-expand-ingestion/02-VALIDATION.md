---
phase: 2
slug: expand-ingestion
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-22
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Note:** Phase 2 RESEARCH.md `## Validation Architecture` (lines 478–550) is the source of truth for the per-requirement test map.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥9.0.3 (existing — `pyproject.toml` `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_youtube.py tests/test_ingest.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~10–20 seconds (offline fixtures only — no live network calls in unit tests) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_<module>.py -x -q` for the module the task touched
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 02-01 | 1 | D-40 (partial schema) | T-02-SC | Migration idempotent | unit | `uv run pytest tests/test_store.py::test_phase2_schema_migration -x -q` | ❌ W0 | ⬜ pending |
| 2-01-02 | 02-01 | 1 | D-36 | T-02-02 | channel_id regex + http(s) url | unit | `uv run pytest tests/test_config.py::test_union_loads_mixed_sources -x -q` | ❌ W0 | ⬜ pending |
| 2-01-03 | 02-01 | 1 | INGEST-03 | T-02-03 | per-item transcript fail isolation | unit | `uv run pytest tests/test_youtube.py -x -q` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02-02 | 2 | INGEST-06 / D-39 | T-02-06 | category in technical last_run | unit | `uv run pytest tests/test_ingest.py::test_error_taxonomy_category -x -q` | ❌ W0 | ⬜ pending |
| 2-02-02 | 02-02 | 2 | D-40 / D-41 | — | empty_feed non-fatal | unit | `uv run pytest tests/test_ingest.py::test_empty_feed_non_fatal -x -q` | ❌ W0 | ⬜ pending |
| 2-02-03 | 02-02 | 2 | D-33 / INGEST-06 | T-02-04 | checked-in RSS URLs only | unit | `uv run pytest tests/test_config.py -x -q` | ✅ extend | ⬜ pending |
| 2-03-01 | 02-03 | 3 | D-25 | T-02-07 | html.escape on card copy | unit | `uv run pytest tests/test_render.py::test_degraded_renders_in_place -x -q` | ❌ rewrite | ⬜ pending |
| 2-03-02 | 02-03 | 3 | D-26 / D-24 | T-02-08 | plain-English notice only | unit | `uv run pytest tests/test_render.py::test_pipeline_header_notice -x -q` | ❌ W0 | ⬜ pending |
| 2-03-03 | 02-03 | 3 | D-25 | T-02-07 | no footer aside | unit | `uv run pytest tests/test_render.py -x -q` | ✅ rewrite | ⬜ pending |
| 2-04-01 | 02-04 | 4 | D-23 | T-02-09 | catch-up scoped to pending_local rows | smoke | `uv run python -m pipeline.run ingest --help \| grep -i pending` | ❌ W0 | ⬜ pending |
| 2-04-02 | 02-04 | 4 | D-22 | — | README + UAT triad | smoke | `grep -q "only-pending-transcripts" README.md` | ✅ extend | ⬜ pending |
| 2-04-03 | 02-04 | 4 | INGEST-03 | T-02-SC | automated catch-up status flip | unit | `uv run pytest tests/ -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

(Wave 0 folded into Plan 02-01 Task 1; remaining gaps close as tasks land)

- [ ] `tests/test_youtube.py` — INGEST-03 adapter + transcript lifecycle
- [ ] `tests/fixtures/feeds/youtube_channel.xml` — offline channel RSS fixture
- [ ] `tests/test_render.py` — rewrite for D-25 / D-26 (Plan 02-03)
- [ ] `tests/test_config.py` — discriminated union + 8 source rows
- [ ] `tests/test_ingest.py` — typed `category` field + empty_feed contract
- [ ] `tests/test_store.py` — additive migration idempotency
- [ ] `store/migrations/002_expand_ingestion.sql` — ALTER columns
- [ ] `pipeline/adapters/youtube.py` — target module
- [ ] `pyproject.toml` — add `youtube-transcript-api` pinned dependency

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live YouTube transcript fetch from residential IP | INGEST-03 (D-23) | Cloud IP block environmental | Run `uv run python -m pipeline.run ingest --only-pending-transcripts` from residential network; confirm pending_local → ok |
| Browser-rendered digest visual check | Success #4, #5 | Reader-experience contract | Open `out/digest-{week_id}.html`; no "Also seen this week"; in-place degraded cards; header notice when pending_local > 0 |
| Live ingest of all 8 sources | INGEST-03, INGEST-06 | Real network | `uv run python -m pipeline.run all`; digest contains RSS + YouTube voices |
| README + `--help` discoverability | D-22 | Cross-surface | README section + `ingest --help` + 02-UAT.md checkbox |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 20s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planner locked 2026-05-22
