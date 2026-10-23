# Phase 3: AI Quality - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-22
**Phase:** 3-ai-quality
**Areas discussed:** Dedup tactics, Categorization, Ranking + Top N, Weekly roll-up, Cost governance + billing, Phase-3 render impact, Idempotency + checkpoint + pipeline_report.json, Execution mode

---

## Area 1 — Dedup tactics

### Q1.1 — Tier 1 title fuzzy threshold

| Option | Description | Selected |
|--------|-------------|----------|
| 0.85 | feedmeup default (recommended starting point; safe under-dedup posture) | ✓ |
| 0.90 | Stricter (fewer false merges, slightly more duplicate cards) | |
| 0.80 | Looser (more aggressive merging, higher false-positive risk) | |
| Configurable, default 0.85; revisit after 2–3 live weeks | Same as 0.85 but explicit knob | |

**User's choice:** 0.85
**Notes:** Recorded in CONTEXT.md D-43 as a `config/digest.yaml` knob anyway (default 0.85), since cost-free to make tunable.

### Q1.2 — Cluster lookback window

| Option | Description | Selected |
|--------|-------------|----------|
| Same ISO week only | Simplest; matches the digest unit | ✓ |
| Rolling 7 days from each item's published_at | Catches Sunday→Monday spillovers | |
| Rolling 14 days | Catches slow-burn stories republished a week later | |

**User's choice:** Same ISO week only
**Notes:** Captured cross-week spillover as a "revisit if it becomes a real visible problem" deferred item.

### Q1.3 — Cluster canonical pick

| Option | Description | Selected |
|--------|-------------|----------|
| First-published wins | Rewards the original source; reproducible | |
| Longest body wins | Best summarization input; feed-summarizer pattern | ✓ |
| Source-tier wins | Would require tier field on sources.yaml | (deferred enhancement) |
| First-published, ties broken by longest body | Deterministic + good input quality | |

**User's choice:** B (longest body) with C (source-tier) as a future enhancement
**Notes:** D-45 records source-tier preference as the future-enhancement direction; revisit at catalog ≥ 20 sources. Deterministic tie-breaker added (first-published, then lexicographic item_id) to keep clustering reproducible.

### Q1.4 — Over-merge guardrails (PITFALLS #9)

| Option | Description | Selected |
|--------|-------------|----------|
| Category-gate (don't merge if categories would differ) | Requires categorize-then-recheck; complicates flow | |
| Max N per cluster (hard cap) | Excess become own clusters | |
| No guard v1 — trust 0.85 + canonical-URL + same-week | Revisit if over-merge shows up | ✓ |
| Per-source `never_dedup_with: [...]` override | Opinion-source carve-out | |

**User's choice:** No guard v1
**Notes:** Full escalation ladder (raise threshold → never_dedup_with → category-gate → max-per-cluster) documented in CONTEXT.md `<deferred>` so it's findable when needed.

---

## Area 2 — Categorization

### Q2.1 — Storage model

| Option | Description | Selected |
|--------|-------------|----------|
| Strict one bucket | Matches REQUIREMENTS literally; simplest UI | ✓ |
| Primary + optional secondary | Store both; render only primary in v1 | |

**User's choice:** Strict one bucket
**Notes:** User explicitly flagged "this will need strong UAT — let's doc that for future." Captured in CONTEXT.md `<deferred>` Future UAT Watch list; primary+secondary added to escalation ladder as step 3.

### Q2.2 — Source YAML `tag` role in categorize prompt

| Option | Description | Selected |
|--------|-------------|----------|
| Ignored | LLM categorizes purely from content; cleanest | |
| Soft hint in prompt | "This source typically covers X, but classify on the content" | ✓ |
| Hard prior | Source tag IS the default unless LLM high-confidence override | |

**User's choice:** Soft hint
**Notes:** Recorded as D-48; D-02 (tag stays config-only metadata) remains true — we just read it into the prompt at categorize time.

### Q2.3 — Low-confidence fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Default fallback bucket (e.g., 'business') | Safest catch-all for AI content | |
| Fall back to source's YAML tag | Always a valid value | ✓ |
| Route to footer aside per LOCKED-01 | Treat as 'unsummarizable' for ranking | |
| Render with 'uncategorized' label | Contradicts PIPELINE-02 | |

**User's choice:** Source YAML tag
**Notes:** D-49 — persisted with `category_confidence = "fallback_source_tag"` for observability. Quota failures get separate carve-out per LOCKED-01.

### Q2.4 — Anti-drift mechanics

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal (temperature=0 + JSON enum) | Cheapest; ship and observe | ✓ |
| Above + few-shot examples per category | ~500 extra input tokens/call | (deferred ladder step 1) |
| Above + per-week category distribution logging | Drift alerting | (deferred ladder step 2) |
| You decide | — | |

**User's choice:** A (minimal) with explicit user instruction: "requires UAT and may need tweaking over time. make sure this is documented for the future so it's not forgotten in case i end up not liking the outputs and can't figure out why"
**Notes:** D-50 ships minimal anti-drift; CONTEXT.md `<deferred>` "Category accuracy escalation ladder" documents the full PITFALLS #12 mitigation menu (few-shot → distribution logging → primary+secondary → Flash model) so the trigger is findable.

---

## Area 3 — Ranking + Top N

### Q3.1 — Top N default

| Option | Description | Selected |
|--------|-------------|----------|
| 5 | REQUIREMENTS default; tighter editorial pick | |
| 10 | Pending-todo proposal; more breadth | |
| Default 5, configurable | Revisit post-observation | ✓ |
| Default 10, configurable | | |

**User's choice:** Default 5, configurable in `config/digest.yaml`
**Notes:** D-51. Pending-todo's `10` recorded in `<deferred>` as post-UAT candidate. STATE.md "Top N + max-cards-per-category knobs" pending-todo is now folded.

### Q3.2 — Max per-category cap

| Option | Description | Selected |
|--------|-------------|----------|
| 15 (pending-todo proposal) | Generous; tab-section feel | |
| 10 | Tighter; forces ranking to discriminate | |
| No cap in v1 | Rank everything; observe before clipping | ✓ |
| Default 15, configurable | | |

**User's choice:** No cap in v1
**Notes:** D-52. Pending-todo's `15` recorded in `<deferred>` as candidate if a section overwhelms.

### Q3.3 — Ranking signals

| Option | Description | Selected |
|--------|-------------|----------|
| LLM-only (prompt weights impact > novelty > recency) | Simplest | ✓ |
| Above + cross-source cluster-size boost | PITFALLS #10 mitigation | (deferred ladder step 1) |
| Above + reserve 2 slots for tier-1 'slow news' | PITFALLS #11 mitigation | (deferred ladder step 2) |
| All three | Most defensive | |

**User's choice:** A (LLM-only / simplest) with explicit user instruction: "i want to go with the simplest option for v1, but let's make sure this is also explicitly included in potential edits needed post uat"
**Notes:** D-53. CONTEXT.md `<deferred>` "Ranking quality escalation ladder" documents the full PITFALLS #10/#11 menu (cluster-size boost → slow-burn reserved slots → source-tier weights → recency penalty).

### Q3.4 — Rank storage

| Option | Description | Selected |
|--------|-------------|----------|
| DB column only (rank_score, rank_position) | Phase 4 reads, never re-ranks | |
| Digest-time only | Re-renders cost LLM calls; risks PIPELINE-05 | |
| DB + metadata (model_id, prompt_version) | PITFALLS #13 versioning; satisfies PIPELINE-05 | ✓ |

**User's choice:** DB + metadata
**Notes:** D-54. Required disambiguation Q3.4 follow-up — user asked for explanation; user picked DB+metadata after seeing the PIPELINE-05 reproducibility argument.

---

## Area 4 — Weekly roll-up

### Q4.1 — Roll-up shape (first pass)

| Option | Description | Selected |
|--------|-------------|----------|
| Flat (one prompt, Top N input) | 1 LLM call; simplest | |
| Hierarchical (4 per-category + 1 synthesis) | PITFALLS #14 mitigation; per-tab content for Phase 4 | (resolved in Q4.1-v2) |
| Flat with timeline JSON input | Structured input; still single-call | |

**User's response:** "i definitely want roll ups per category, but i'm not sure i understand pros and cons of each approach"
**Notes:** Triggered follow-up Q4.1-v2 with explicit trade-off table comparing flat vs hierarchical given per-category requirement.

### Q4.1-v2 — Roll-up shape (resolved)

| Option | Description | Selected |
|--------|-------------|----------|
| Hierarchical: 4 minis + 1 synthesis | 5 LLM calls; minis double as Phase 4 tab openers | ✓ |
| Hierarchical, but skip synthesis when 1 category dominates | Conditional | |
| Independent: 1 flat weekly + 4 minis (6 calls) | No synthesis dependency | |

**User's choice:** Hierarchical (5 calls)
**Notes:** D-55. Per-category minis serve double duty (synthesis input + Phase 4 tab openers); ~$0.005/week cost rounding error per D-61.

### Q4.2 — Length target

| Option | Description | Selected |
|--------|-------------|----------|
| ~100 words / one tight paragraph | Sunday-morning brevity | |
| ~150–200 words / two paragraphs | Room for narrative | ✓ |
| Short lead + 3–5 bulleted highlights | Most scannable | |

**User's choice:** B (two paragraphs) with explicit user instruction: "include in UAT testing questions if that seems right"
**Notes:** D-56. Flagged in CONTEXT.md `<deferred>` Future UAT Watch list.

### Q4.3 — Voice constraints

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit ban list only | game-changer, landscape, delve, etc. | |
| Ban list + 'sharp editor' guide + 1–2 bad/good examples | D-50 voice guide level | ✓ |
| Minimal: 'concrete, terse, no hedging' instruction | Ship and iterate | |

**User's choice:** B (full voice guide) with explicit user instruction: "again, explicit uat item needing testing"
**Notes:** D-57. Flagged in CONTEXT.md `<deferred>` Future UAT Watch list.

### Q4.4 — Roll-up failure handling

| Option | Description | Selected |
|--------|-------------|----------|
| Publish with plain-English note | Partial-success philosophy; LOCKED-01 framing | ✓ |
| Block publish | Roll-up IS the Core Value | |
| Publish silently without rollup section | Bad observability | |

**User's choice:** Publish with note
**Notes:** D-58. Per-category mini failures are silent (section renders cards without paragraph); only weekly synthesis failure gets the top-of-main notice line.

### Q4.5 (follow-up) — Per-category mini-rollup visibility in Phase 3

| Option | Description | Selected |
|--------|-------------|----------|
| Show in Phase 3 each category section with mini-rollup leading cards | Validates end-to-end now | ✓ |
| Generate + store, don't render until Phase 4 | Keep current flat card list | |
| Show as compact 'In each category' summary block above card list | Preview | |

**User's choice:** Show in Phase 3 (full section treatment)
**Notes:** Resolves Area 6 render question prematurely (by user choice); D-63/D-65 record the section structure.

---

## Area 5 — Cost governance + Gemini billing revisit

### Q5.1 — Hard-stop dollar threshold

| Option | Description | Selected |
|--------|-------------|----------|
| $2/week | Matches PROJECT.md target | ✓ |
| $5/week | Matches Phase 5 hard cap; headroom | |
| $10/week | Phase 3 is noisy/experimenting | |
| No cap; observability only | Risk runaway tail week | |

**User's choice:** $2/week
**Notes:** D-59. Configurable `pipeline.hard_stop_usd` in `config/digest.yaml`. Distinct from Phase 5 OPS-05.

### Q5.2 — Halt order (first pass)

| Option | Description | Selected |
|--------|-------------|----------|
| Skip remaining per-item summaries first; always finish meta | Protect the narrative | |
| Skip in cost-value order | Granular | |
| Halt all remaining | Matches OPS-05 literal text | |
| Warn only; don't halt | Observability-only | |

**User's response:** "having the rollup is the most important. however, if the per item summaries aren't evaluated because the cost is exceeded, how can we make sure there is enough money left over for the roll up to be sufficiently accurate and valuable"
**Notes:** Real concern. Triggered Q5.2-v2 with concrete cost table + reservation mechanism proposal.

### Q5.2-v2 — Budget mechanism (resolved)

| Option | Description | Selected |
|--------|-------------|----------|
| Reserve $0.10 for meta + pre-flight per-item estimate + partial-publish notice | Protects rollup independently of total spend | ✓ |
| No reservation; log overage; still publish everything | Observability-only in Phase 3 | |
| You decide | — | |

**User's choice:** Reservation + pre-flight + mid-run check
**Notes:** D-60. Realistic per-week meta cost is ~$0.003 (D-61 table); $0.10 reservation is ~30× safety margin. Partial-publish notice copy locked to plain-English per D-24.

### Q5.3 — Model tiering (first pass)

| Option | Description | Selected |
|--------|-------------|----------|
| Single model (Flash-Lite everywhere) | Simplest; matches Phase 1–2 | |
| Tiered: Flash-Lite per-item + categorize; Flash rank + rollup | PITFALLS pattern; ~3–5× meta cost | (resolved in Q5.3-v2) |
| You decide | — | |

**User's response:** "how will this effect cost?"
**Notes:** Triggered Q5.3-v2 with concrete cost table.

### Q5.3-v2 — Model tiering (resolved)

| Option | Description | Selected |
|--------|-------------|----------|
| Tiered (Flash-Lite per-item; Flash for rank + 5 rollup calls) | ~$0.005/week extra for quality | ✓ |
| Single Flash-Lite | ~$0.005/week saved; simpler | |
| Tiered only for weekly synthesis | Hybrid | |

**User's choice:** Tiered
**Notes:** D-61. ~$0.005/week delta is rounding error; quality matters more for the meta stages, especially the weekly synthesis (PITFALLS #14 implicitly assumes Flash for hierarchical synthesis).

### Q5.4 — Gemini billing decision

| Option | Description | Selected |
|--------|-------------|----------|
| Stay free tier; revisit if >30 quota-blocks/week | LOCKED-01 carve-out covers UX | |
| Switch to paid as part of Phase 3 | Removes 20 req/day cap | |
| Defer to post-Phase-3 | Decide with real numbers after dedup | ✓ |

**User's choice:** Defer to post-Phase-3
**Notes:** D-62. STATE.md "Pending Todos" updated, not closed — new trigger condition is "1–2 live Phase 3 weeks observation."

---

## Area 6 — Phase-3 render impact

**User's response:** "Questions skipped by the user, continue with the information you already have"
**Notes:** Captured as Claude's Discretion per user direction. Defaults applied with plain-English / DISPLAY-03-compatible reasoning:
- **Top N display:** Dedicated numbered "Briefing — Top N this week" section at top of `<main>` (matches DISPLAY-03 verbatim; Phase 4 inherits structure). → D-63
- **Cluster attribution:** Plain-English "Also covered by [Source B], [Source C]" line with clickable source links (best for attribution trust per PITFALLS #15; plain-English per D-24). → D-64
- **Category labels:** Section header only, not on individual cards (avoid visual noise; section context conveys category). → D-65
- **Roll-up failure copy:** Planner finalizes within LOCKED-01 plain-English family. → D-66

---

## Area 7 — Idempotency + checkpoint + `pipeline_report.json`

User requested recommendations + reasoning before answering. All four answered with recommended options after explanation.

### Q7.1 — Checkpoint granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Stage-level (each stage = completed marker; crash = redo stage) | Coarsest | |
| Item-level (per-item commit; crash = pick up next item) | Matches existing `_summarize_week_items` pattern | |
| Hybrid (item for summarize/categorize; stage for rank/rollup) | Best fit | ✓ |

**User's choice:** Hybrid (recommended)
**Notes:** D-67. Mirrors existing pattern in `pipeline/orchestrator.py::_summarize_week_items` — `get_existing_summary` skip-on-hit + per-call commit.

### Q7.2 — Cascading invalidation

| Option | Description | Selected |
|--------|-------------|----------|
| Narrow (only that item's summary recomputed) | Under-protects | |
| Cluster-wide with conservative triggers | Re-summarize → maybe re-cluster → maybe re-rank → maybe re-rollup | ✓ |
| Wholesale (any item change → full meta re-run) | Wasteful | |

**User's choice:** Cluster-wide conservative (recommended)
**Notes:** D-68. Dominant case is YouTube `pending_local` → `ok` catch-up. New CLI flags `--rebuild-clusters` / `--rebuild-rollup` for unconditional re-run, subject to D-22 triad.

### Q7.3 — `pipeline_report.json` location

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone per-week (`out/pipeline-report-{week_id}.json`) | Phase 4 reads | |
| Latest-only (`out/pipeline_report.json`) | Phase 5 heartbeat | |
| Both (per-week + always-latest copy) | Both readers covered | ✓ |

**User's choice:** Both (recommended)
**Notes:** D-69. `pipeline_runs` SQLite table remains the cross-week source of truth; JSON files are projections + ephemeral (out/ gitignored per D-13). Phase 4 will eventually move per-week JSON into `web/src/content/digests/`.

### Q7.4 — `pipeline_report.json` fields

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal (ROADMAP SC #4 literal) | Floor | |
| Extended (per-stage + per-source health + summary_status counts + category distribution + budget accounting) | Phase 4 OBS-01 + Phase 5 OBS-03 readers | ✓ |
| You decide | — | |

**User's choice:** Extended (recommended)
**Notes:** D-70. Planner finalizes exact field names. `schema_version: 1` field added so future readers can detect shape changes.

---

## Area 8 — Execution mode

**User's response (after explanation of dev-workflow vs runtime-artifact distinction):** "i'm fine with however you want to do the work as long as you take into account dependencies and make sure decisions are documented and followed in future steps"

**Captured as Claude's Discretion** per user direction.

| Option | Description | Selected |
|--------|-------------|----------|
| Inline execution; atomic commits per task; deviations in VERIFICATION.md | Phase 2 proven 30% faster | ✓ |
| Cursor `Task` subagents for plan execution | Untested in this project | |
| Switch to claude-cli / Claude Desktop | Loses Cursor IDE integration | |

**Captured choice:** Inline execution; Cursor `Task` available as a tool for genuinely parallel read-only work (research, audits). Constraints from user: (a) dependencies between tasks made explicit in PLAN.md wave structure; (b) every CONTEXT.md decision cited in PLAN.md plan(s) so downstream steps honor them.
**Notes:** D-71. Pipeline deliverable stays Cursor-independent (no `.cursor/` artifacts in shipped code; all planning artifacts are plain Markdown + JSON).

---

## Claude's Discretion

User explicitly handed these to Claude:
- **Area 6 (Phase-3 render impact)** — all four sub-questions skipped; defaults applied per D-63/D-64/D-65/D-66.
- **Area 8 (Execution mode)** — defer to Claude with constraints (dependencies tracked, decisions documented + followed).
- **All "you decide" items within otherwise-answered areas** — captured in CONTEXT.md `<decisions>::Claude's Discretion` section (RapidFuzz function choice, exact URL canonicalization rules, schema layout, JSON key names, budget.py API surface, exact UI text, CLI flag names, test framework choices).

## Deferred Ideas

Comprehensive deferred list in CONTEXT.md `<deferred>`. Major themes:
- **Future UAT Watch** — categorization accuracy (D-47/D-48/D-50), Top N ranking quality (D-53), weekly rollup voice + length (D-56/D-57), partial-publish at the $2 cap (D-60), per-category mini-rollup quality (D-55).
- **Category accuracy escalation ladder** — few-shot examples → distribution logging → primary+secondary → Flash model (PITFALLS #12).
- **Ranking quality escalation ladder** — cluster-size boost → slow-burn slots → source-tier weights → recency penalty (PITFALLS #10, #11).
- **Dedup over-merge escalation ladder** — raise threshold → never_dedup_with override → category-gate → max-per-cluster (PITFALLS #9).
- **Source tier/weight field** on `sources.yaml` (D-45 canonical-pick + D-53 ranking signals). Revisit at catalog ≥ 20 sources.
- **Tier 2 SimHash + Tier 3 embedding clustering** — explicit v1.5+ (RESEARCH §Dedup Strategy).
- **Top N = 10** and **`max_cards_per_category = 15`** — pending-todo's proposed values kept as post-UAT candidates.
- **Cross-week dedup window** (D-44 same-week-only) — revisit if Sunday→Monday spillovers prove visible.
- **Gemini paid tier** — re-evaluate after 1–2 live Phase 3 weeks (D-62; STATE.md pending todo updated).
- **Phase 4 / Phase 5 hand-offs** — Astro dashboard, archive promotion of per-week JSON, formal $5 hard cap, heartbeat reader.
- **Phase 2 UAT tests 6 + 7b** — not blocking Phase 3 entry; can be exercised opportunistically during build.
