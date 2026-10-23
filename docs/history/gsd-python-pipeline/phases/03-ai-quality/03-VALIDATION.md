---
phase: 3
slug: ai-quality
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-22
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `03-RESEARCH.md` § Validation Architecture and refined by the planner.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (carried from Phase 1–2) |
| **Config file** | `pyproject.toml` (existing `[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest -x -q tests/` |
| **Full suite command** | `pytest -q tests/` |
| **Estimated runtime** | ~30s quick / ~90s full (planner refines) |

---

## Sampling Rate

- **After every task commit:** Run `pytest -x -q tests/<plan-scope-dir>/`
- **After every plan wave:** Run `pytest -q tests/`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~30s per task scope, ~90s full

---

## Per-Task Verification Map

> Planner fills the full row set in PLAN.md `<automated>` blocks. This table is the cross-plan index.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | DEDUP-01..04, PIPELINE-02..06, OBS-02 | T-3-01..N | per-plan | unit/integration | per-task | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Per `03-RESEARCH.md` § Validation Architecture (Wave 0 fixture gaps):

- [ ] `tests/dedup/__init__.py` + `tests/dedup/conftest.py` — known-overlap fixtures (canonical URL collisions, title-fuzzy 0.85 boundary cases, Unicode/emoji titles)
- [ ] `tests/dedup/test_url_canonical.py` — Tier 0 deny-list fixtures (UTM, gclid, fbclid, ref, mc_cid, mc_eid, trailing slash, www vs apex, single redirect)
- [ ] `tests/llm/test_categorize_golden.py` — golden-output fixture per category (`edtech | business | technical | design`) + invalid-enum fallback (D-49)
- [ ] `tests/llm/test_rank_determinism.py` — fixed input → fixed rank with locked `model_id` + `prompt_version`
- [ ] `tests/llm/test_rollup_voice.py` — ban-list assertions (`game-changer`, `landscape`, `delve`, `it's worth noting`, `significant implications`, `paradigm shift`) + length bounds
- [ ] `tests/budget/test_budget_halt.py` — simulate `hard_stop_usd=0.01` partial-publish path; assert reservation intact for meta stages
- [ ] `tests/reporting/test_pipeline_report_schema.py` — `pipeline_report.json` shape contract (schema_version, stages, source_health, summary_status, budget)
- [ ] `tests/render/test_partition_cards_phase3.py` — LOCKED-01 routing for new artifact types (cluster summaries, mini-rollups, weekly synthesis)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dedup cluster quality on a real week | DEDUP-02, DEDUP-03 | Subjective "same story or distinct take" judgment | After live run, spot-check 5 random clusters in `out/digest-{week}.html`; confirm each cluster is genuinely one story |
| Category accuracy (single-bucket strict) | PIPELINE-02 | Editorial judgment | Spot-check 10–15 random clusters per week against your intuitive sort; flag misclassifications for escalation ladder |
| Top N ranking reasonableness | PIPELINE-03 | "Anything obviously missing or inflated?" is editorial | Sunday-morning read; if Top N feels off, apply ranking escalation ladder |
| Weekly rollup voice + length | PIPELINE-04 | "Sharp editor, not press release" is qualitative | Read aloud; check for ban-list slop, 150–200 word target, coherent week-tying |
| Per-category mini-rollup quality | PIPELINE-04 | Section opener vs card duplicate is qualitative | Spot-check each of 4 mini-rollups; verify it adds value beyond card list |
| Partial-publish at $2 cap | PIPELINE-05, OBS-02 | Real-budget exercise | Set `pipeline.hard_stop_usd: 0.01` for one run; verify partial-publish renders cleanly with plain-English notice; restore real cap |
| Core Value 15-minute skim | (SC #5) | Reader-experience hypothesis | Sunday-morning read; confirm digest delivers "what happened in AI this week" coherently |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (8 stubs above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s full suite
- [ ] `nyquist_compliant: true` set in frontmatter after planner finishes wiring `<automated>` blocks

**Approval:** pending
