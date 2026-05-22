# Phase 3: AI Quality - Context

**Gathered:** 2026-05-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform the existing chronological 8-source item list into a curated weekly briefing. Phase 3 adds five new layers on top of the Phase 1–2 pipeline:

1. **Dedup-before-LLM** — URL canonicalization (Tier 0) + RapidFuzz title fuzzy clustering (Tier 1) collapse same-story coverage into story clusters before any per-item LLM call.
2. **Categorization** — every story is classified into exactly one of `edtech | business | technical | design` via an LLM call constrained by JSON-schema enum.
3. **Ranking** — the LLM ranker produces a `rank_score` and `rank_position` per cluster for the week; results are persisted with `model_id` + `prompt_version` so re-renders are LLM-free and idempotent.
4. **Hierarchical weekly roll-up** — four per-category mini-rollups feed a fifth synthesis call that produces the weekly narrative. The per-category minis also become the per-category section headers in the digest now and the Phase 4 tab openers later.
5. **Pipeline cost governance + structured report** — pre-flight budget estimate, $0.10 reservation for meta stages, $2/week hard stop with partial-publish behavior; every run writes `out/pipeline-report-{week_id}.json` + `out/pipeline_report.json` (latest copy) for Phase 4 OBS-01 and Phase 5 OBS-03 to consume.

**In scope (Phase 3):**
- New `story_clusters` table (cluster_id, canonical_item_id, member_item_ids, canonical_url, title_normalized, week_id) and a `cluster_members` join table.
- New `cluster_summaries` / `cluster_ranks` tables (or equivalent columns) carrying `category`, `category_confidence`, `rank_score`, `rank_position`, `model_id`, `prompt_version`.
- New `weekly_rollups` table (week_id, scope ∈ {category:edtech, category:business, category:technical, category:design, weekly}, narrative_md, model_id, prompt_version, input_token_count, output_token_count, cost_usd_estimate, created_at).
- New `pipeline/dedup/` module (`url.py` for canonicalization; `title_fuzzy.py` for RapidFuzz clustering at threshold 0.85).
- New `pipeline/llm/categorize.py`, `pipeline/llm/rank.py`, `pipeline/llm/rollup.py` and matching versioned prompt files in `pipeline/llm/prompts/`.
- New `pipeline/budget.py` (pre-flight estimate, reservation accounting, hard-stop check between stages).
- New `pipeline/reporting/pipeline_report.py` (JSON projection of `pipeline_runs` + extended fields).
- Renderer changes in `pipeline/render/html.py`: numbered "Briefing — Top N this week" section at the top of `<main>` (per DISPLAY-03 verbatim), per-category sections (each opens with its mini-rollup, then ranked-sorted cards), "Also covered by [Source B], [Source C]" attribution line on clustered cards. Footer aside (`<aside id="also-seen">`) stays exactly as locked by LOCKED-01.
- Orchestrator wiring: new stages (`dedup`, `categorize`, `rank`, `rollup`) added between `summarize` and `render`; subcommand surface grows (`python -m pipeline.run dedup|categorize|rank|rollup [--week ...]`) per D-19/D-22 discoverability triad.
- A configurable `config/digest.yaml` lands here with `top_n_briefing: 5`, hard-stop cap, model tier picks, threshold knobs.

**Out of scope (Phase 3 — deferred):**
- Astro dashboard, tabbed navigation, archive index, Past Weeks UI — Phase 4 (DISPLAY-01..08, ARCHIVE-01..04, OBS-01).
- GitHub Actions cron, Cloudflare Pages deploy, secret scanning, formal hard $5/week LLM cap enforcement at OPS-05 level, heartbeat, dead-man's-switch — Phase 5 (OPS-01..05, OBS-03).
- Tier 2 SimHash and Tier 3 embedding clustering — explicitly v1.5+ per RESEARCH §Dedup Strategy.
- Per-source tier weights / `never_dedup_with` overrides — captured as deferred ideas.
- Few-shot examples in the categorize prompt + per-week category-distribution logging — explicit Phase 3 deferred escalation path if category accuracy proves poor in UAT.
- Anti-recency / anti-hype ranking signals (slow-burn slot reservation, cross-source corroboration boost, source-tier weights) — captured as deferred escalation path if Top-N quality proves poor in UAT.
- Switch to Gemini paid tier — explicitly deferred to post-Phase-3 to be re-decided with real post-dedup volume data (Area 5 D-58).

**Locked requirements** (from REQUIREMENTS.md):
- **DEDUP-01** — URL canonicalization before dedup (Tier 0)
- **DEDUP-02** — Title fuzzy clustering above configurable threshold (Tier 1)
- **DEDUP-03** — Cluster preserves all source attributions
- **DEDUP-04** — Dedup runs BEFORE LLM summarize
- **PIPELINE-02** — Each story is categorized into exactly one of `edtech | business | technical | design`
- **PIPELINE-03** — Rank items and pick a Top N for the Briefing landing page (N configurable, default 5)
- **PIPELINE-04** — Weekly narrative roll-up
- **PIPELINE-05** — Pipeline is idempotent
- **PIPELINE-06** — Pipeline is checkpointed; resumable after crash
- **OBS-02** — Structured run report (errors, items ingested, deduped, LLM calls, cost USD) saved with the digest artifact

</domain>

<decisions>
## Implementation Decisions

### Project-level rules carried forward (NOT re-decided here)
- **Carry LOCKED-01 (PROJECT-level):** Footer-aside for thin/unsummarizable items. The single in-place carve-out is `summary_status = quota_exhausted` (Gemini `RESOURCE_EXHAUSTED` / 429 / rate-limit). Phase 3 adds four new LLM stages (categorize, rank, mini-rollup ×4, weekly synthesis) and all of them MUST extend the same `_classify_llm_exception` mechanism — quota failures keep their owning artifact eligible for in-place "couldn't be generated this week" copy; every other exception routes the affected artifact to a sensible degradation (footer for items, omit-with-plain-English-note for rollups). The renderer's `_partition_cards` is the single source of truth for routing and MUST be extended (not duplicated) to handle the new artifact types.
- **Carry D-31 (PROJECT-level — Editorial Principle):** "Known entities and their takes, not anonymous community signal." Phase 3 introduces categorization, ranking, and narrative roll-up — all reader-surface artifacts. None of them may surface community/crowd framing ("trending on HN", "discussed on Reddit"); the v1 catalog has no such sources, so this is structural rather than enforcement, but the principle gates any future ranking signal proposal that smuggles in engagement metrics.
- **Carry D-24 (PROJECT-level — Reader-surface language):** Everything readers see is plain English. Category labels (`edtech | business | technical | design`) are reader-surface; render exactly those words (no `cat:tech`, no `[T]`). Mini-rollup and weekly-rollup text must follow the anti-slop voice constraints (D-50). Partial-publish notices use plain English (no exception class names, no CLI command paths, no flag syntax).
- **Carry D-22 (PROJECT-level — Hidden capability discoverability):** Every new CLI subcommand and flag introduced in Phase 3 (`dedup`, `categorize`, `rank`, `rollup` as `python -m pipeline.run` subcommands; `--top-n`, `--max-cost-usd`, `--rebuild-clusters`, `--rebuild-rollup`, and any others) MUST land with README + `--help` + UAT coverage. Same triad as D-12/D-23.
- **Carry D-00c, D-00d, D-36 (Phase 1–2):** Adapter registry pattern, `UNIQUE(source_id, external_id)` PK strategy, and discriminated-union source config are unchanged. Phase 3 does not touch adapters, sources, or the `items` PK strategy.
- **Carry D-04 + PITFALLS #13 (Phase 1 — Prompt versioning):** Every new LLM artifact (`cluster_summaries.category`, `cluster_ranks.rank_score`, `weekly_rollups.narrative_md`) persists `prompt_version` + `model_id` on the row. New prompts live in `pipeline/llm/prompts/`: `categorize_v1.md`, `rank_v1.md`, `rollup_category_v1.md`, `rollup_weekly_v1.md`. Renderer never re-calls the LLM; reads stored values.
- **Carry D-09 (Phase 1 — `pipeline_runs` substrate):** The new `pipeline_report.json` is a *projection* of `pipeline_runs` rows + new extended fields, not a parallel substrate. Phase 4 archive UI reads the JSON; the SQLite table remains source-of-truth for cross-week queries.

### Dedup (Area 1)
- **D-43:** **Tier 1 title fuzzy threshold = 0.85.** RapidFuzz `token_set_ratio` on `title_normalized` (lowercase, strip punctuation, collapse whitespace). Matches feedmeup default and RESEARCH §Dedup recommendation. Lives in `config/digest.yaml` as a config knob — revisit after 2–3 live weeks of observed cluster-merge quality. Tier 0 (canonical URL exact match, strip UTM/tracking params, lowercase host, resolve a single redirect) runs first and is parameter-free.
- **D-44:** **Cluster lookback window = same ISO week only.** Items are eligible for cluster membership only with other items whose `published_at` falls in the same `[week_start, week_end]` window. Cross-week stories are independent clusters — accepted trade-off for v1 simplicity; revisit if Sunday→Monday spillovers actually become a visible problem.
- **D-45:** **Cluster canonical pick = longest `raw_content` body.** Wins because it gives summarization the best input. Deterministic tie-breaker: first-published by `published_at`, then by lexicographic `item_id`. Source-tier preference (Tier-1 sources beat aggregators regardless of body length) is **captured as a future enhancement** — would require adding a `tier` or `weight` column to `sources.yaml` and is meaningful only after the v1 catalog grows beyond the current 8 named entities. Revisit at catalog ≥ 20 sources.
- **D-46:** **No anti-over-merge guardrail in v1.** Trust the 0.85 threshold + canonical-URL Tier 0 + same-week window. PITFALLS #9 (category-gate, max-per-cluster caps, `never_dedup_with` per-source overrides) are explicit deferred escalation paths — revisit if a live UAT spot-check shows distinct takes collapsed into one card. The over-merge taxonomy from PITFALLS #9 is reproduced in the deferred-ideas section so it's findable.

### Categorization (Area 2)
- **D-47:** **Strict one bucket per story.** Per REQUIREMENTS PIPELINE-02 literally. `cluster_summaries.category` is a non-nullable enum constrained to `edtech | business | technical | design`. No primary+secondary in v1. **UAT-critical** — this is the decision most likely to feel wrong in real reading; flagged in the deferred-ideas Future UAT Watch list.
- **D-48:** **Source YAML `tag` = soft hint in the categorize prompt.** Pass the source's tag (where present) as `source_typically_covers: <tag>` in the prompt body, not as a hard prior. Prompt instruction: "Classify based on the story content; the source's typical beat is a hint, not a constraint." Sources without a tag (none currently, but the schema allows it) pass through with the hint omitted. D-02 (tag stays config-only metadata for human reference) remains true — we just read it into the prompt at categorize time.
- **D-49:** **Low-confidence fallback = the source's YAML tag.** When the LLM returns an invalid enum value (after one JSON-schema retry), or when categorize fails with a non-quota error (`api_error`, `parse_error`, `client_init_error`), the cluster's `category` defaults to the canonical item's source `tag`. Source tags are guaranteed to be valid enum values (validator in `pipeline/config.py` will enforce). Persisted with `category_confidence = "fallback_source_tag"` for observability. Quota failures route the cluster's category artifact in-place per LOCKED-01 spirit (use last-known category if available, otherwise source tag with `category_confidence = "quota_exhausted_fallback"`).
- **D-50:** **Anti-drift = minimal in v1 (`temperature=0` + JSON-schema enum constraint only).** Few-shot examples in the prompt and per-week category distribution logging are explicit deferred escalation paths. They are NOT shipping in Phase 3 but ARE documented in `<deferred>` as the "category accuracy escalation ladder" so a future operator who notices categorization drift has a documented next step without having to rediscover the mitigation. **UAT-critical** — categorization quality is a real risk per PITFALLS #12 and the v1 minimal posture means we ship and observe.

### Ranking + Top N (Area 3)
- **D-51:** **Top N default = 5, configurable in `config/digest.yaml` as `top_n_briefing`.** Matches REQUIREMENTS PIPELINE-03 default literally. Revisit after 2–3 live weeks of post-dedup observed cluster volume — if 5 feels like too tight a Briefing, the knob is there. The pending-todo proposal of 10 is recorded in `<deferred>` as a candidate value to test post-UAT.
- **D-52:** **No `max_cards_per_category` cap in v1.** Rank everything within each category; render in rank order. The pending-todo proposal of 15 is recorded in `<deferred>` as a candidate value to test if a single category overwhelms its section in a real week. Phase 4 may revisit when tab UI lands.
- **D-53:** **Ranking signals = LLM-only with explicit prompt weighting ("impact > novelty > recency").** No cross-source corroboration boost, no slow-burn reserved slots, no source-tier weights in v1. **Explicit deferred escalation path** — PITFALLS #10 (recency bias) and PITFALLS #11 (hype bias) mitigation menu (cluster-size boost in prompt, reserve 2 of Top-N for tier-1 sources, source-tier weights) is documented in `<deferred>` as the "ranking quality escalation ladder." **UAT-critical** — this is the second most likely Phase 3 output to feel off (after categorization).
- **D-54:** **Rank storage = DB + metadata.** New `cluster_ranks` table (or equivalent columns on `cluster_summaries`): `cluster_id`, `week_id`, `rank_score`, `rank_position`, `model_id`, `prompt_version`, `created_at`. The renderer reads these — never calls the rank LLM. Satisfies PIPELINE-05 (idempotent re-render) and PITFALLS #13 (prompt versioning means future prompt changes don't retroactively re-rank archived weeks). Matches the existing `item_summaries` pattern exactly.

### Weekly roll-up (Area 4)
- **D-55:** **Hierarchical roll-up shape — 4 per-category mini-rollups + 1 weekly synthesis (5 LLM calls).** Per-category minis (`rollup_category_v1.md`) take that category's ranked clusters as input and produce a ~80–120 word paragraph. Weekly synthesis (`rollup_weekly_v1.md`) takes the 4 mini-rollups as input (NOT raw cluster lists) and produces the weekly narrative. PITFALLS #14 (lost-in-the-middle) mitigated by short synthesis input. Per-category minis double as Phase 4 tab openers (zero rework when Phase 4 lands). Stored in `weekly_rollups` table with `scope` discriminator.
- **D-56:** **Roll-up length target = ~150–200 words / two paragraphs for the weekly synthesis.** Per-category minis target ~80–120 words / one paragraph each. Prompt constraints are explicit. **UAT-critical** — flagged in the deferred-ideas Future UAT Watch list to confirm the length feels right in real Sunday reading.
- **D-57:** **Voice constraints = explicit ban list + "sharp editor, not press release" guide + 1–2 bad-vs-good examples in both rollup prompts (D-50 voice guide level).** Ban list (PITFALLS #16): `game-changer`, `landscape`, `delve`, `it's worth noting`, `significant implications`, `paradigm shift`. Examples format: "Bad: 'OpenAI's new model could have significant implications for the AI landscape.' Good: 'OpenAI shipped GPT-6 on Tuesday; pricing is half of GPT-5 and context jumped to 2M tokens.'" **UAT-critical** — flagged for explicit voice/tone testing in real digest reads.
- **D-58:** **Roll-up failure = publish digest with plain-English note where the roll-up would go.** Mirrors LOCKED-01 quota carve-out philosophy. Failure copy: planner finalizes within the LOCKED-01 plain-English family ("The summary couldn't be generated this week." → adapted as "This week's narrative roll-up couldn't be generated. The Top N stories are below." or similar). Per-category mini-rollup failures: the section renders its cards without the mini-rollup paragraph, with no notice (the section's existence implies the category has content; absence of mini-rollup is unobtrusive). Weekly synthesis failure: a one-line plain-English placeholder at the top of `<main>`, then the Briefing Top N + per-category sections render normally. The digest **always publishes** if any cards are present; never block-on-rollup-failure.

### Cost governance (Area 5)
- **D-59:** **Hard-stop dollar threshold = $2/week, configurable in `config/digest.yaml` as `pipeline.hard_stop_usd`.** Matches PROJECT.md target line. The formal $5/week Phase 5 hard cap (OPS-05) is a separate Phase 5 decision and may differ; Phase 3 ships its own knob so cost governance can be exercised + UAT-tested before Phase 5 enforces. Pre-flight estimate uses last-week's actual per-item cost as the projection baseline (falls back to a hardcoded ~$0.001/item conservative estimate on cold start).
- **D-60:** **Budget mechanism = reservation + pre-flight + mid-run check.** Reserve $0.10 of the cap for meta stages (categorize + rank + per-category rollups + weekly synthesis — realistic ~$0.005 + tiered Flash overhead, so $0.10 is a ~20× safety margin). Per-item summaries can only spend `cap - reservation = $1.90`. Before any LLM call: pre-flight estimate of remaining work; if `estimated_remaining + already_spent > cap` then halt before the next call. Mid-run check between stages: if reserved budget is intact, the rollup stages always run, even if summaries got halted. Partial publish on halt: render whatever exists with a plain-English header notice ("Pipeline cost estimate exceeded the weekly budget; this week's digest reflects what completed before the cap.") per D-24.
- **D-61:** **Model tiering = Flash-Lite for per-item (summarize, categorize); Flash for meta (rank, per-category rollups, weekly synthesis).** Cost delta ~$0.005/week (rounding error in absolute terms; ~$0.25/year). Flash is the next tier up from Flash-Lite and is the model PITFALLS #14 implicitly assumes for hierarchical synthesis. Prompt + `model_id` pairing is per-stage:
  - `summarize_v1.md` → `gemini-2.5-flash-lite` (unchanged from Phase 1)
  - `categorize_v1.md` → `gemini-2.5-flash-lite`
  - `rank_v1.md` → `gemini-2.5-flash`
  - `rollup_category_v1.md` → `gemini-2.5-flash`
  - `rollup_weekly_v1.md` → `gemini-2.5-flash`
- **D-62:** **Gemini billing decision = DEFER to post-Phase-3.** Stay on free tier (20 req/day) through Phase 3 build + first 1–2 live runs. Re-evaluate with real numbers (actual post-dedup items/week, % items hitting 429, perceived reader impact) AFTER dedup is shipped and observable. The STATE.md pending-todo from 2026-05-22 is updated, not closed: trigger condition becomes "we've seen 1–2 live post-dedup weeks AND >30 quota-blocked items in either week OR perceived reader impact from quota-exhausted footer items." LOCKED-01 quota_exhausted carve-out keeps the UX coherent in the interim.

### Phase-3 render impact (Area 6 — Claude's Discretion per user direction)
- **D-63:** **Top N display = dedicated numbered "Briefing — Top N this week" section at the top of `<main>`, before the per-category sections.** Matches DISPLAY-03 verbatim. Numbered list 1..N with each item rendering as a standard card. Phase 4 inherits this structure when it builds the Briefing tab; the HTML markup chosen here should be class-naming-compatible (e.g., `.briefing`, `.briefing-card`) so Phase 4's CSS can style without HTML restructure.
- **D-64:** **Cluster attribution on canonical cards = plain-English "Also covered by [Source B], [Source C]" line under the TL;DR.** Each source name is a small clickable link to that member item's canonical URL. Hidden when cluster size = 1. Plain-English per D-24; no count-only / no badge row. Best-effort attribution trust per PITFALLS #15.
- **D-65:** **Category labels on cards = section header only, not on individual cards.** Each per-category section opens with: `<h2>` category label (capitalized, e.g., "Technical") + the mini-rollup paragraph + ranked cards. Cards within a section don't repeat the category badge — the section context already conveys it. Phase 4's tab UI replaces the section headers with tabs; cards stay identically shaped.
- **D-66:** **Roll-up failure copy = planner finalizes within the LOCKED-01 plain-English family.** Constraint: stay in the existing voice ("The summary couldn't be generated this week" → adapt to rollup scope), avoid CLI/path/code references per D-24, fit in one line at the top of `<main>` (weekly synthesis failure) or zero text (per-category mini failure — section renders cards without the opening paragraph).

### Idempotency + checkpointing + `pipeline_report.json` (Area 7)
- **D-67:** **Checkpoint granularity = hybrid.** Item-level for the high-volume stages (`summarize`, `categorize`) — each LLM result is committed individually as it succeeds, so crash mid-stage picks up at the next unprocessed item (matches the existing `get_existing_summary` skip pattern in `_summarize_week_items`). Stage-level for the meta stages (`dedup`, `rank`, `rollup`) — they're single-call or low-call-count, so a crash just redoes the whole stage from scratch; results are idempotent given the same input. `dedup` is fully deterministic (no LLM) so re-run is free.
- **D-68:** **Cascading invalidation = cluster-wide with conservative triggers.** When an item's `content_hash` changes (catch-up YouTube transcript flip is the dominant case): re-summarize that item; if the item is its cluster's canonical OR the item's `title_normalized` changed, re-cluster the week; if cluster membership of any current Top-N candidate cluster shifted, re-rank; if Top-N composition itself changed, re-run mini-rollups + weekly synthesis. Most edits don't trigger the full cascade. New CLI flag `--rebuild-clusters` (and `--rebuild-rollup`) forces unconditional re-run of those stages, subject to D-22 discoverability triad.
- **D-69:** **`pipeline_report.json` location = both — per-week file + always-latest copy.** Write `out/pipeline-report-{week_id}.json` (per-week archive precursor — Phase 4 will likely move this into `web/src/content/digests/` when it builds the archive) AND `out/pipeline_report.json` (always-latest, overwritten each run — Phase 5 heartbeat reads this without needing to know the week_id). Both gitignored per D-13 (out/ is ephemeral in Phase 3). `pipeline_runs` SQLite table remains the cross-week source of truth.
- **D-70:** **`pipeline_report.json` schema = extended; planner finalizes exact field names.** Required content beyond the ROADMAP SC #4 minimum (`week_id`, `generated_at`, `items_ingested`, `clusters`, `llm_calls`, `cost_usd`, `errors[]`):
  - **Per-stage breakdown:** `stages: { ingest: { items: N, duration_ms: M }, dedup: { clusters_created: N, items_clustered: M }, summarize: { llm_calls: N, cost_usd: M, items_unchanged: K }, categorize: { llm_calls: N, cost_usd: M, distribution: { edtech: N, business: N, technical: N, design: N, fallback_source_tag: N } }, rank: { ... }, rollup: { mini_rollups: N, weekly: bool, ... } }`
  - **Per-source health snapshot:** for each source — `last_success_at`, `last_error_category`, `items_this_week`, `clusters_canonical_this_week`.
  - **`summary_status` counts:** `{ ok: N, thin: N, quota_exhausted: N, api_error: N, parse_error: N, client_init_error: N }` — direct LOCKED-01 routing observability.
  - **Budget accounting:** `budget: { cap_usd: 2.0, reserved_meta_usd: 0.10, spent_usd: N, pre_flight_estimate_usd: M, halted: bool, halted_at_stage: str | null }`.
  Phase 4 OBS-01 and Phase 5 OBS-03 consume this JSON directly; no other surface should compute these counts from raw tables.

### Execution mode (Area 8 — Claude's Discretion per user direction)
- **D-71:** **Phase 3 development workflow = inline execution in Cursor, atomic commits per task, dependency-aware wave ordering in PLAN.md, deviations documented in VERIFICATION.md.** Continues the proven Phase 2 pattern (30% faster per plan than Phase 1 subagent mode, with equivalent quality — STATE.md velocity table). The pipeline itself remains fully Cursor-independent: no `.cursor/` artifacts get committed into the deliverable, all `.planning/` artifacts are plain Markdown + JSON, and the runtime is pure Python — Phase 5 GHA cron will prove this. Cursor's native `Task` subagents available as a tool for genuinely parallel read-only work (e.g., research, audits) if needed during Phase 3, but plan execution stays inline. **Constraint per user direction:** dependencies between tasks must be made explicit in PLAN.md wave structure; every decision in this CONTEXT.md must be cited in the relevant PLAN.md plan(s) so downstream steps honor them.

### Folded Todos
- **Top N + max-cards-per-category knobs for Phase 3 ranking** (captured 2026-05-21 from Plan 01-01 review) — resolved by D-51 (`top_n_briefing: 5` configurable, pending-todo's proposed `10` recorded as post-UAT candidate) and D-52 (no `max_cards_per_category` cap in v1, pending-todo's proposed `15` recorded as candidate for if a section overwhelms).

### Reviewed Todos (kept on watch, not folded into Phase 3 scope)
- **Gemini billing decision** (deferred 2026-05-22 post Phase 2 UAT) — updated, not closed, by D-62. New trigger: post-1–2 live Phase 3 weeks observation. Stays in STATE.md "Pending Todos" with updated trigger condition.

### Claude's Discretion
- **Exact RapidFuzz function (D-43)** — `token_set_ratio` is the recommended choice (handles word reordering); planner may pick `token_sort_ratio` or `WRatio` if a corner case in real titles argues for it. The threshold of 0.85 is locked; the scoring function is planner discretion within the RapidFuzz family.
- **URL canonicalization rule set (D-43 Tier 0)** — strip UTM params (`utm_*`), strip common tracking params (`gclid`, `fbclid`, `ref`, `mc_cid`, `mc_eid`); lowercase the host; resolve `www.` vs apex per source consistency; single redirect follow with 5s timeout. Planner finalizes the exact deny-list of params and whether to canonicalize trailing slash. Should reuse `httpx` (already a dependency from Phase 1).
- **Exact schema layout for `story_clusters` and cluster-attached artifacts (categories, ranks, rollups)** — single table with denormalized columns vs. separate tables joined on `cluster_id` is a planner call. Constraint: `prompt_version` + `model_id` MUST be persisted next to every LLM-derived field (D-04 / D-54 / D-55), and the schema must support PIPELINE-05 idempotent re-render without LLM calls.
- **Concrete `pipeline_report.json` field names and JSON structure** (D-70) — the *content* is locked; the exact key names (`per_stage` vs `stages`, `health` vs `source_health`, etc.) are planner discretion. Add a top-level `schema_version: 1` so Phase 4 + Phase 5 readers can detect future shape changes.
- **`pipeline/budget.py` API surface** (D-60) — the *behavior* is locked (reservation, pre-flight, mid-run check, partial-publish on halt); the exact function signatures and integration points in the orchestrator are planner discretion. Should integrate cleanly with the existing `RunStats.cost_usd_estimate` accumulator in `pipeline/orchestrator.py`.
- **Exact text of the "Briefing — Top N this week" header label, per-category section headers, and "Also covered by" connective text** (D-63, D-64, D-65) — must stay plain-English per D-24; capitalization (`Technical` vs `technical`), punctuation (commas vs middots in "also covered by"), and exact phrasing are planner discretion subject to that constraint.
- **CLI flag names for `--top-n`, `--max-cost-usd`, `--rebuild-clusters`, `--rebuild-rollup`** — final names are planner choice subject to D-22 (README + `--help` + UAT triad). The `dedup|categorize|rank|rollup` subcommand surface itself IS locked (the user-visible verbs map 1:1 to stages).
- **Test framework choices, coverage targets, UAT checklist additions for Phase 3** — Phase 1 + 2 set the pytest precedent. Phase 3 must add explicit UAT entries (deferred-ideas section flags which) for: dedup cluster quality on a real week, category accuracy spot-check (single-bucket assignments), Top N ordering reasonableness, weekly rollup voice/length (D-50, D-56), partial-publish behavior at the $2 cap, per-category mini-rollup quality.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level gates (MUST read first)
- `.planning/LOCKED-DIRECTIVES.md` — **MANDATORY first read** for any plan/research artifact. LOCKED-01 governs every new Phase 3 stage that produces a reader-surface artifact: thin/unsummarizable goes to footer; only quota_exhausted earns an in-place carve-out. The Phase 3 categorize/rank/rollup stages MUST extend `_classify_llm_exception` and route per LOCKED-01.
- `.planning/PROJECT.md` §Editorial Principle + §Core Value + §Key Decisions — Editorial Principle gates any future ranking-signal proposal; Core Value ("coherent narrative of what happened in AI this week, read in 15 minutes") is the success bar the hierarchical rollup must deliver against; Key Decisions table contains LOCKED-01 history and the v1 source-scope decisions.

### Phase boundary, requirements (planner reads first)
- `.planning/ROADMAP.md` §Phase 3 — locked phase goal, success criteria (especially SC #4 — `pipeline_report.json` shape; SC #5 — testable Core Value hypothesis), the requirements list (DEDUP-01..04, PIPELINE-02..06, OBS-02), and the locked dependency on Phase 2.
- `.planning/REQUIREMENTS.md` §Dedup + §AI Pipeline + §Observability — full text of DEDUP-01..04, PIPELINE-02..06, OBS-02; categorization enum is reader-surface so the four exact strings `edtech | business | technical | design` are not up for renaming.

### Stack + architecture + research
- `.planning/research/ARCHITECTURE.md` §Dedup Strategy + §Pipeline Orchestration + §Data Model + §Suggested Build Order — Tier 0/1/2/3 dedup tiering rationale; weekly cycle phase order; PK strategy and StoryCluster sketch (Phase 3 implements the cluster-PK pattern that Architecture sketched but Phase 1–2 didn't need yet); build order positions dedup → LLM in the right sequence.
- `.planning/research/STACK.md` §3 + §6 + §7 — feedparser/SQLite already in place; Gemini Flash-Lite vs Flash tiering for D-61; RapidFuzz is the recommended fuzzy-match library.
- `.planning/research/SUMMARY.md` §Risk Top-5 + §Cross-Cutting Tensions + §Cost Guardrails — Risk #1 (under-dedup) and #2 (runaway LLM cost) and #4 (hallucination) are all Phase 3 primary mitigations; Cost Guardrails table sets the $2/week target that D-59 enforces.
- `.planning/research/PITFALLS.md` — Phase 3 primary mitigations: #1 (Runaway LLM cost — pre-flight budget, dedup-before-summarize, tiered models — D-59/D-60/D-61), #2 (Hallucinated summaries — grounding contract from D-04 carries forward), #8 (Under-dedup — D-43/D-44/D-45), #9 (Over-dedup — D-46 deferred guardrails), #10 (Recency bias — D-53 deferred escalation), #11 (Hype beats important — D-53 deferred escalation), #12 (Categorization drift — D-47/D-48/D-49/D-50), #13 (Prompt versioning — every new LLM artifact persists prompt_version + model_id), #14 (Lost-in-the-middle — D-55 hierarchical), #16 (Generic slop — D-57 voice + ban list). PITFALLS #15 (mismatched attribution) — D-64 plain-English "Also covered by" with per-member URLs.

### Phase 1 + Phase 2 decisions still in force
- `.planning/phases/01-foundation-first-digest/01-CONTEXT.md` — most relevant carries:
  - **D-04** — Grounding contract + versioned prompts in `pipeline/llm/prompts/`; persisted `prompt_version` on every LLM output row. New Phase 3 prompts inherit the pattern.
  - **D-09** — `pipeline_runs` table is the substrate; `pipeline_report.json` projects from it.
  - **D-22 (project-level)** — Hidden capability discoverability triad. Every Phase 3 CLI flag (`--top-n`, `--max-cost-usd`, `--rebuild-clusters`, `--rebuild-rollup`) and subcommand (`dedup`, `categorize`, `rank`, `rollup`) needs README + `--help` + UAT.
- `.planning/phases/02-expand-ingestion/02-CONTEXT.md` — most relevant carries:
  - **D-24 (project-level)** — Reader-surface language is plain English. Category labels render as the four enum strings; rollup text follows the anti-slop voice (D-57); partial-publish notices avoid CLI / code / path references.
  - **D-25 / LOCKED-01 superseding context** — `_partition_cards` in `pipeline/render/html.py` is the SINGLE source of truth for routing. Phase 3 extends it for new artifact types (cluster-level summaries, per-category mini-rollups, weekly synthesis) without duplicating the logic.
  - **D-36** — discriminated-union source config. Phase 3 doesn't touch it but the *pattern* (typed unions, validators per subtype) is the precedent for how the new schema additions (cluster types, rollup scopes) should be modeled in Pydantic.
  - **D-39 / D-40** — typed `RunStats.errors` taxonomy + source-health columns. `pipeline_report.json` (D-70) consumes these directly for per-source health snapshot and error breakdown.

### Existing code Phase 3 will extend or revise
- `pipeline/orchestrator.py` — central wiring. New stages (`_dedup`, `_categorize`, `_rank`, `_rollup`) slot in between `_summarize_week_items` and the render call. `run_dedup`, `run_categorize`, `run_rank`, `run_rollup` are new public entry points mirroring `run_ingest`/`run_summarize`/`run_render`. `run_all` chains them. Budget reservation (D-60) wraps the stage sequence.
- `pipeline/llm/summarize.py` — `_classify_llm_exception` is the model for the new stages' exception classification; extend the same `summary_status` taxonomy (`ok` / `quota_exhausted` / `api_error` / `parse_error` / `client_init_error`) per artifact type. `SummaryResult.summary_status` is the per-row routing signal that LOCKED-01 already locked in.
- `pipeline/render/html.py` — `_partition_cards` is the LOCKED-01 router. Phase 3 extends it (not duplicates) for new artifact types. New Briefing-Top-N section + per-category sections + "Also covered by" line are additive HTML structure; LOCKED-01 footer aside stays as-is.
- `pipeline/run.py` — CLI subcommand surface grows by 4 verbs (`dedup`, `categorize`, `rank`, `rollup`); bare invocation alias for `all` (D-19) inherits the new stages in sequence; lazy LLM/adapter imports for render path (D-20) extend to lazy import the new LLM modules.
- `pipeline/config.py` — adds `digest.yaml` loader (`config/digest.yaml`) for runtime knobs: `top_n_briefing`, `dedup.title_fuzzy_threshold`, `pipeline.hard_stop_usd`, `pipeline.meta_reservation_usd`, model picks per stage. Source config (`SourceConfig` discriminated union) unchanged. `tag` field on `RssSource`/`YoutubeSource` is read by the categorize prompt (D-48).
- `store/db.py` + `store/migrations/` — new migration `004_dedup_categorize_rank_rollup.sql` adds `story_clusters`, `cluster_members`, and the cluster-attached artifact tables (categories, ranks, rollups). Migration is additive per existing pattern; PK strategy on `items` is unchanged.
- `pipeline/reporting/last_run.py` — extends to surface dedup/categorize/rank/rollup counts in `out/last_run.md` (technical surface — can use CLI/path language per D-24).
- New module: `pipeline/dedup/` — `url.py` (canonicalize, hash) + `title_fuzzy.py` (RapidFuzz wrapper at 0.85 threshold) + `cluster.py` (the dedup engine that consumes `items` rows and writes `story_clusters` + `cluster_members`).
- New module: `pipeline/llm/categorize.py`, `pipeline/llm/rank.py`, `pipeline/llm/rollup.py` — mirror the shape of `pipeline/llm/summarize.py`: Pydantic structured-output schema, tenacity retry, `_classify_llm_exception` adaptation, prompt loader.
- New module: `pipeline/budget.py` — reservation + pre-flight + mid-run check accounting (D-60).
- New module: `pipeline/reporting/pipeline_report.py` — extended JSON projection (D-70).
- New config: `config/digest.yaml` — runtime knobs (D-51, D-59, D-43 threshold, etc.).
- New prompts: `pipeline/llm/prompts/categorize_v1.md`, `rank_v1.md`, `rollup_category_v1.md`, `rollup_weekly_v1.md`.

### Process & state
- `.planning/STATE.md` — pending todos updated by this session: `Top N + max-cards-per-category knobs` is now resolved (folded into D-51/D-52 with deferred candidate values); `Gemini billing decision` updated, not closed, with new trigger condition per D-62.
- `.planning/phases/03-ai-quality/03-DISCUSSION-LOG.md` — full audit trail of options considered in this session (human-only).

No external ADRs, external specs, or design docs were referenced during this discussion; everything is contained in the planning tree above plus the in-repo research artifacts.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`pipeline/llm/summarize.py` structure** — Pydantic structured-output schema (`SummaryResponse`), tenacity retry decorator, `_classify_llm_exception` taxonomy mapper, lazy `_build_client` with `GeminiKeyMissing` carve-out, versioned prompt loader (`_load_prompt_body`), per-call cost estimate helper (`_estimate_cost`). All four new Phase 3 LLM modules (categorize, rank, rollup-category, rollup-weekly) inherit the same shape — copy + adapt the structured-output schema and the response handling.
- **`pipeline/orchestrator.py::_summarize_week_items`** — the item-level checkpoint pattern (call `get_existing_summary` before each LLM call, skip on hit, persist per call) is the model for `_categorize_week_clusters`. D-67 hybrid checkpointing inherits this.
- **`store/db.py` migration runner** (`_strip_sql_line_comments` + idempotent execution from `002_expand_ingestion.sql` / `003_summary_status.sql`) — Phase 3's `004_*.sql` migration follows the same pattern.
- **`pipeline/render/html.py::_partition_cards`** — the LOCKED-01 router. Phase 3 extends it for cluster-level artifacts; the routing logic is centralized and tested.
- **`pipeline/render/html.py::QUOTA_BODY_COPY`** — locked exact-string carve-out for LOCKED-01 in-place copy. Phase 3 adds analogous locked-string copy for rollup-failure scenarios (D-58, D-66) — same pattern, new constants.
- **`pipeline/orchestrator.py::RunStats`** — already accumulates cost (`cost_usd_estimate`) and typed errors. Phase 3 extends with per-stage breakdowns that feed `pipeline_report.json` (D-70).
- **`pipeline/reporting/last_run.py::write_last_run_md`** — already aggregates per-source items + errors. Phase 3 extends to render dedup/categorize/rank/rollup summaries on the technical surface (per D-24, last_run.md may use literal command names; the digest HTML may not).
- **`pipeline/week.py::week_bounds`** — the ISO-week parameterization (D-10/D-11) feeds the dedup-window-same-ISO-week decision (D-44) directly.
- **`pipeline/content_enrich.py`** — `EnrichableItem` + `prepare_input_text` pattern is shared between summarize and the future canonical-pick (D-45) which uses `raw_content` length; no change needed, just reuse.

### Established Patterns Phase 3 extends or relies on
- **Adapter registry / discriminated union (D-00d, D-36)** — Phase 3 doesn't add sources but the pattern (Pydantic discriminated union on a `type` literal) is the precedent for modeling `weekly_rollups.scope` (`category:edtech` / `category:business` / `category:technical` / `category:design` / `weekly`).
- **Versioned prompts (D-04 + PITFALLS #13)** — every Phase 3 LLM output row carries `prompt_version` + `model_id`. New prompts follow the `pipeline/llm/prompts/{stage}_v1.md` naming and YAML-frontmatter pattern.
- **Per-source try/except + typed error taxonomy (D-39)** — Phase 3 stages extend the `RunStats.errors` shape with `category` values for new failure modes (e.g., `dedup_internal`, `categorize_invalid_enum`, `rank_partial`, `rollup_synthesis_failed`).
- **`week_id` parameterization end-to-end (D-11)** — no `datetime.now()` inside any new Phase 3 module; all stages accept `week_id: str`. Inherited.
- **`out/` is gitignored (D-13)** — `pipeline_report-{week_id}.json` and `pipeline_report.json` land in `out/`; Phase 4 will own promoting per-week reports to `web/src/content/digests/` for the archive of record.
- **`pipeline_runs` substrate (D-09)** — `pipeline_report.json` is a projection, not a parallel store. SQLite remains source of truth for cross-week queries.
- **Reader-surface vs technical-surface language split (D-24)** — explicit in renderer rewrite. Phase 3's new HTML strings (category labels, "Also covered by", Briefing header, partial-publish notice, rollup-failure copy) are reader-surface; `out/last_run.md` and `--help` output may use literal commands.

### Integration Points
- **`web/` directory remains dormant** — Phase 3 does not touch Astro. The plain-HTML digest evolves substantially (Briefing section, per-category sections, mini-rollups) but the artifact stays at `out/digest-{week_id}.html`. Phase 4 builds the Astro dashboard reading the same `pipeline_report-{week_id}.json` + a future per-week digest JSON (Phase 4 owns the JSON shape).
- **Phase 4 dependency hand-off** — Phase 3 produces: (a) `pipeline_report-{week_id}.json` with extended schema (Phase 4 OBS-01 reads), (b) per-category mini-rollups stored in `weekly_rollups` (Phase 4 tab openers read), (c) `cluster_summaries.category` (Phase 4 tab routing reads), (d) `cluster_ranks` (Phase 4 Briefing Top-N reads). The renderer's Briefing-section HTML class names should be Phase-4-CSS-compatible so the dashboard styles can apply without HTML restructure.
- **Phase 5 dependency hand-off** — Phase 5 OBS-03 heartbeat reads `out/pipeline_report.json` (always-latest); OPS-05 hard cap layers on top of D-60 budget machinery (Phase 3's $2 knob becomes Phase 5's $5 with halt-and-publish semantics formalized at the CI/cron level).
- **YouTube catch-up integration (D-23 from Phase 2)** — `--only-pending-transcripts` flips items from `pending_local` → `ok`, which triggers the D-68 cascading invalidation. The cascade rules MUST be tested with a real YouTube catch-up scenario (UAT entry).
- **Phase 1–2 already wrote `summary_status` rows** — Phase 3 dedup operates on existing `items` rows (no migration of summary status needed); the renderer's footer aside continues to work because the LOCKED-01 routing is per-item, not per-cluster.

</code_context>

<specifics>
## Specific Ideas

- **The hierarchical rollup is doing real Phase 4 work for free.** Per-category mini-rollups (D-55) are the natural Phase 4 tab openers. Choosing flat would have meant rewriting the rollup pipeline in Phase 4. The 5-call cost is rounding error (~$0.005/week — D-61 table) and the architectural payoff is real.
- **Top N default stays at 5, not 10.** The pending-todo proposal of 10 is preserved as a post-UAT candidate value (D-51). The reasoning: 5 is the REQUIREMENTS default and the tighter editorial pick; we can loosen to 10 if a real week feels too narrow, but we can't tighten without re-evaluating the user's mental model of "Briefing."
- **Strict one bucket per story is UAT-critical.** The user explicitly flagged this for "strong UAT" testing. Same for the minimal anti-drift posture (D-50) and the LLM-only ranking signals (D-53) — three explicit "ship and observe" decisions where the escalation path is documented in `<deferred>` so a future operator who notices the output drifting has a documented next step instead of having to rediscover the mitigation.
- **The $2 hard stop is a mechanism, not yet an enforced ceiling.** Realistic post-dedup spend is ~$0.05/week (D-61 table). The $2 knob exists so cost governance can be exercised + UAT-tested before Phase 5 enforces a formal cap. Reservation + pre-flight + mid-run check (D-60) protects the rollup independently of total spend by reserving meta budget upfront.
- **Phase 3 keeps shipping a readable Sunday digest.** Per-category sections + Briefing Top N + cluster attribution + weekly rollup all render in the existing plain HTML (`out/digest-{week_id}.html`) so success criterion #5 ("skim full digest in ~15 min, coherent sense of the week") is testable BEFORE Phase 4's Astro dashboard lands. Phase 3 is the first phase where the Core Value hypothesis can actually be evaluated.
- **The pipeline remains fully Cursor-independent (D-71).** Inline-in-Cursor is a development workflow choice for speed; the deliverable artifact is a pure Python CLI with no IDE coupling. Phase 5 GHA cron will prove this.

</specifics>

<deferred>
## Deferred Ideas

### Future UAT Watch (must be tested in the first 1–2 live Phase 3 weeks)
- **Categorization accuracy** (D-47 single-bucket strict + D-48 source-tag-as-soft-hint + D-50 minimal anti-drift) — spot-check 10–15 random clusters per week against your intuitive sort. If accuracy feels poor, escalate via the documented ladder (few-shot examples → per-week distribution logging → primary+secondary storage). Document the trigger criteria in the UAT.
- **Top N ranking quality** (D-53 LLM-only signals, no anti-recency/anti-hype mitigation) — read the Top N Sunday morning; ask "is anything obviously missing or obviously inflated?" If yes, escalate via the documented ladder (cluster-size boost in prompt → slow-burn reserved slots → source-tier weights → reserve 2 of Top-N for tier-1 sources).
- **Weekly rollup voice + length** (D-56 ~150–200 words, D-57 voice + ban list) — does it read like a sharp editor? Does it tie the week together coherently? Does it skip mid-week items (PITFALLS #14 still leaking through despite hierarchical)? Adjust prompts iteratively.
- **Partial-publish at the $2 cap** (D-60) — deliberately set `pipeline.hard_stop_usd: 0.01` in `config/digest.yaml` for one test run; verify the partial-publish path renders cleanly with the plain-English notice; restore the real cap.
- **Per-category mini-rollup quality** (D-55) — each of the four mini-rollups should be a useful section opener, not a duplicate of the cards below. Spot-check.

### Category accuracy escalation ladder (PITFALLS #12)
*If categorization quality is poor in UAT, escalate in this order:*
1. **Add few-shot examples to `categorize_v1.md`.** 3–5 worked examples per category baked into the prompt. Cost: ~500 extra input tokens per call (~$0.0005 total/week additional).
2. **Log per-week category distribution to `pipeline_report.json`.** Alert if any category is <10% or >50% of clusters in a week. Already inferred in D-70 schema (distribution counts are listed); this would activate the alert side.
3. **Add primary + secondary categorization** (DB schema change — `category` + `category_secondary`). Render only primary in the Phase 3 digest; Phase 4 can cross-link in topic tabs.
4. **Bump categorize model to Flash from Flash-Lite.** Cost delta ~$0.001/week.

### Ranking quality escalation ladder (PITFALLS #10, #11)
*If Top N quality is poor in UAT, escalate in this order:*
1. **Add cross-source corroboration boost in the rank prompt.** "Clusters with ≥2 independent source members are stronger candidates." Zero schema change; prompt-only.
2. **Reserve 2 of Top-N slots for tier-1 sources** (when sources have a tier/weight field — see D-45 future enhancement). Requires sources.yaml schema addition.
3. **Add source-tier weights as explicit prompt input.** Pass each cluster's max member-source tier to the ranker; rank prompt rule: "Source tier 1 outweighs source tier 3 unless story impact is overwhelming."
4. **Penalize single-source low-engagement items published in last 6 hours.** Requires `published_at` proximity check in the ranker.

### Dedup over-merge escalation ladder (PITFALLS #9)
*If over-merge is observed in UAT (distinct takes collapsed into one card), escalate in this order:*
1. **Raise threshold from 0.85 to 0.90** in `config/digest.yaml::dedup.title_fuzzy_threshold`. Zero code change.
2. **Add `never_dedup_with: [source_ids]` per-source override** in `sources.yaml`. Useful for opinion-source carve-outs (e.g., never merge Simon Willison's take with Ed Zitron's).
3. **Add category-gate guard** — re-categorize after preliminary clustering; if cluster members would split categories, break the cluster. Adds a feedback loop; costs an extra categorize pass.
4. **Add `max_per_cluster: N` cap** — clusters can have at most N members; excess become their own clusters. Crude but predictable.

### Other deferred items
- **Source tier / weight field on `sources.yaml`** (D-45 canonical-pick future enhancement; D-53 ranking signal escalation; D-45 source-tier-prefers-original). Revisit at catalog ≥ 20 sources OR when ranking/canonical-pick quality demands it.
- **Tier 2 SimHash + Tier 3 embedding clustering** (RESEARCH §Dedup Strategy) — explicit v1.5+. URL + title fuzzy is sufficient for v1.
- **Story-level cross-week persistence** (D-44 same-week-only window) — if Sunday→Monday spillovers become a real visible problem, revisit the lookback window.
- **Astro / dashboard rendering of the new artifacts** — Phase 4 owns DISPLAY-01..08 and ARCHIVE-01..04. Phase 3's plain-HTML structure is class-naming-compatible (D-63 note) so Phase 4 can style without HTML restructure.
- **Formal $5/week hard cap with CI/cron-level enforcement** — Phase 5 OPS-05 layers on top of D-60 budget machinery.
- **Heartbeat / dead-man's-switch ping reading `out/pipeline_report.json`** — Phase 5 OBS-03.
- **Move per-week `pipeline_report-{week_id}.json` from `out/` to `web/src/content/digests/`** for archive-of-record durability — Phase 4 owns this migration.

### Reviewed Todos (kept on watch, not folded into Phase 3 scope)
- **Gemini billing decision** — STATE.md pending todo (deferred 2026-05-22 post Phase 2 UAT). Updated by D-62 with new trigger: re-evaluate after 1–2 live Phase 3 weeks of post-dedup observation. Stays in STATE.md "Pending Todos" with the updated trigger condition.

### Reviewed Todos from Phase 2 UAT (not Phase 3 scope)
- **Phase 2 manual UAT tests 6 (confirmed-missing transcripts) + 7b (deliberate 404 source isolation)** — STATE.md flagged as deferred from Phase 2 close-out; not blocking Phase 3 entry. Can be exercised during Phase 3 build any time a YouTube catch-up or RSS failure happens naturally.

</deferred>

---

*Phase: 3-ai-quality*
*Context gathered: 2026-05-22*
