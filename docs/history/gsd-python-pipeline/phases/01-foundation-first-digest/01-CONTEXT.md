# Phase 1: Foundation + First Digest - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>
## Phase Boundary

A runnable Python CLI that reads `config/sources.yaml`, fetches three RSS/Atom feeds, stores normalized items in SQLite keyed by `(source_id, external_id)`, calls Gemini Flash-Lite for per-item TL;DR summaries, and writes a dated plain-HTML digest file (`out/digest-YYYY-Www.html`) a human can open in a browser.

**In scope (Phase 1):** source-config loader; SQLite schema + upsert; RSS adapter; LLM summarization with grounding + degraded-content handling; plain-HTML renderer; ISO-week orchestration with `--week` CLI override; minimum debuggability slice (structured logs + `out/last_run.md` + `pipeline_runs` table).

**Out of scope (other phases):** YouTube/Reddit/HN/email-RSS adapters (Phase 2); dedup, categorization, ranking, weekly rollup, idempotency hard cap, `pipeline_report.json` (Phase 3); Astro dashboard + archive + Briefing Pipeline-notes UI (Phase 4); GHA cron + Cloudflare Pages deploy + secret scanning + hard $5/week cap + heartbeat (Phase 5).

**Locked requirements** (from REQUIREMENTS.md): INGEST-01, INGEST-02, INGEST-07, INGEST-08, PIPELINE-01.

</domain>

<decisions>
## Implementation Decisions

### Stack carried forward (from PROJECT.md + research; not re-decided here)
- **D-00a:** Python 3.12+ pipeline; `feedparser` for RSS/Atom; SQLite as ephemeral working store; `google-genai` SDK calling `gemini-2.5-flash-lite` for per-item summaries; `structlog` for structured logging.
- **D-00b:** Project layout follows ARCHITECTURE.md `Recommended Project Structure` — `config/`, `pipeline/`, `store/`, `web/` (dormant in Phase 1), `data/` (gitignored), `out/` (gitignored).
- **D-00c:** Item primary key strategy: `UNIQUE(source_id, external_id)` where `external_id = guid` if stable, else `sha256(canonical_url + published_date_day)`. Matches ARCHITECTURE §Data Model.
- **D-00d:** Adapter registry pattern with `IngestAdapter` protocol; `RssAdapter` is the only implementation in Phase 1. No hard-coded URLs inside adapter code (anti-pattern #4 from ARCHITECTURE).

### Seed sources (Area 1)
- **D-01:** Phase 1 ships with exactly three RSS sources in `config/sources.yaml`:
  - `simon-willison` — `https://simonwillison.net/atom/everything/` (type: rss, tag: technical)
  - `one-useful-thing` — `https://www.oneusefulthing.org/feed` (type: rss, tag: business)
  - `import-ai` — `https://importai.substack.com/feed` (type: rss, tag: business)
- **D-02:** All three are full-text feeds; no `category` field on items in Phase 1 (categorization is Phase 3) — the `tag` is config-only metadata for human reference.

### LLM grounding & degraded content (Area 2)
- **D-03:** **Hybrid input strategy.** Summarizer's input source is the RSS body by default. When the RSS body is < 500 characters, fetch the canonical URL and extract main content with `trafilatura` (preferred; `readability-lxml` as fallback if `trafilatura` fails). Full-fetch failures (HTTP 4xx/5xx, parse failures, timeouts) are logged with `source_id`, `item_id`, URL, status, and error class; the pipeline falls back to whatever snippet exists.
- **D-04:** **Grounding contract for summaries.** Prompt enforces: 2–4 sentences; no claims not supported by the input text; no invented numbers/dates/quotes; if input is too thin to summarize honestly, return a sentinel value (e.g., empty string or `{"summary": null, "reason": "thin_content"}`) rather than fabricating. Prompt is versioned in `pipeline/llm/prompts/summarize_v1.md`; `prompt_version` is persisted with each `ItemSummary` row (anticipates PITFALLS #13).
- **D-05:** **Degraded-content UI — FINAL FORM (revised 2026-05-21).** When the LLM returns the thin-content sentinel (or summary generation fails), the item is **NOT silently dropped**, but it does **NOT render as a full `<article>` card** either. Instead it collapses into a single "Also seen this week" `<aside class="pipeline-notes">` footer section at the bottom of `<main>`, listed as a title-only clickable link (`target="_blank" rel="noopener"`, middot-separated when multiple). The literal phrase `[summary unavailable — content too thin]` appears once as the aside's lead-in text. The header's item count reflects the **displayed** count, not the total. Rationale: in a "15-minute read" digest, full-size "Summary unavailable" cards are visual noise; the footer keeps the items discoverable without paying scroll-tax for empty content (post-Plan 01-01 live-digest review). **Plan 01-03 briefly violated this and was reverted in commit `fix(01-03)` (2026-05-21). Any future renderer change MUST honor this contract or update this decision first.**
- **D-06:** **`summary_confidence` field is persisted in `item_summaries` from Phase 1** (enum: `high` | `low` | `unavailable`). Phase 3's confidence work inherits the column without a migration. Phase 1 sets it to `high` for successful summaries, `low` if full-fetch was triggered but yielded < 500 chars, and `unavailable` for the degraded path.

### Debuggability slice (Area 2 follow-up — included in Phase 1 scope)
- **D-07:** `structlog` emits structured logs to stdout for every fetch attempt, summarize attempt, and render step. Fields include `source_id`, `item_id` (where applicable), HTTP status, duration_ms, token counts.
- **D-08:** Each run writes `out/last_run.md` summarizing the run: per-source items fetched / summaries written / items degraded; LLM call count + estimated cost; any source errors with one-line reasons. Overwritten each run (no archive; per-run history lives in the SQLite `pipeline_runs` table).
- **D-09:** `pipeline_runs` SQLite table is created in Phase 1's schema and populated by the orchestrator. Columns: `run_id`, `started_at`, `finished_at`, `week_id`, `phase` (`ingest`/`summarize`/`render`/`all`), `status`, `errors_json`, `items_fetched`, `summaries_written`, `items_degraded`, `cost_usd_estimate`. Phase 3's formal `pipeline_report.json` will read from this table.

### Week window (Area 3)
- **D-10:** **Canonical week identifier is ISO week.** `week_id` format is `YYYY-Www` (e.g., `2026-W21`); `week_start` is the Monday of that ISO week, `week_end` is the following Sunday, both in UTC.
- **D-11:** **Orchestrator accepts `week_id` as a parameter from day one.** The CLI exposes `--week YYYY-Www` (e.g., `--week 2026-W19`) for backfill / replay. When omitted, defaults to the current ISO week derived from `datetime.now(timezone.utc)`. Hardcoding `datetime.now()` anywhere downstream of the orchestrator entry point is forbidden — the value is threaded through as a parameter.
- **D-12:** **Hidden-capability documentation policy applies** (D-22 below): the `--week` flag MUST be (a) explained in the README's "Manual run / backfill" section with two concrete example invocations, (b) surfaced in `--help` output with a one-line description that mentions backfill, and (c) covered by an explicit verification check listed in Phase 1's UAT.

### HTML output (Area 4)
- **D-13:** **Output path:** `out/digest-{week_id}.html` (e.g., `out/digest-2026-W21.html`). `out/` is gitignored — Phase 4 produces a different artifact (JSON into Astro Content Collections) and will own the publishable archive.
- **D-14:** **Structure within the file:** a single flat list of item cards, sorted newest-first by `published_at`. Each card displays a small source badge (e.g., `[Simon Willison]`) so the publisher is visible without grouping. No per-source `<h2>` sections.
- **D-15:** **Per-card content** (per success criterion #2): title (clickable, links to canonical URL), publisher attribution (from `display_name` in `sources.yaml`), publication date (`YYYY-MM-DD`), and TL;DR (2–4 sentences) OR the degraded `[summary unavailable — content too thin]` line.
- **D-16:** **Source links** open in a new tab with `target="_blank" rel="noopener"`. Matches Phase 4's DISPLAY-08 contract; cheap to do correctly now.
- **D-17:** **Styling level:** approximately 40 lines of inline `<style>` in the document head. Goals: readable line-length (`max-width: 720px`, centered), `system-ui` font stack, dark background (e.g., `#0e1116` bg / `#e6e6e6` text), comfortable line-height (~1.6), light visual hierarchy (h1 for digest title, subtle card borders or spacing). No external CSS, no JavaScript, no design-system tokens. Explicitly NOT the Phase 4 dashboard — it must remain throwaway.
- **D-18:** Header of the HTML shows: project name ("AI Digest"), week range ("Week of MMM D – MMM D, YYYY" rendered from `week_start`/`week_end`), and an "Updated" timestamp (UTC ISO 8601). This is a structural dry-run of the Phase 4 Briefing header so the same fields are produced.

### CLI shape (Area 5)
- **D-19:** **Split subcommands with `all` as the default.** The CLI exposes:
  - `python -m pipeline.run ingest [--week YYYY-Www]` — fetch all enabled sources and upsert into SQLite
  - `python -m pipeline.run summarize [--week YYYY-Www]` — summarize items in the week window that are missing a current summary
  - `python -m pipeline.run render [--week YYYY-Www]` — render the HTML digest from existing SQLite data
  - `python -m pipeline.run all [--week YYYY-Www]` — runs `ingest` → `summarize` → `render` sequentially
  - Bare `python -m pipeline.run [--week YYYY-Www]` is an alias for `all` (no subcommand required for the common case)
- **D-20:** `render` MUST NOT touch the network or the LLM — pure transformation from SQLite to HTML. This enables fast iteration on CSS / card layout without spending tokens.
- **D-21:** All four subcommands accept `--week`. Subcommand-and-default behavior is documented in the README and exposed via `--help` (subject to D-22).

### Standing project-level policy (decided here; promote to PROJECT.md at next transition)
- **D-22:** **Hidden-capability discoverability policy.** Any "hidden capability" introduced in any phase — CLI flag, env var, internal config option, opt-in behavior that isn't obvious from the main UI — MUST: (a) be captured as a numbered decision in that phase's CONTEXT.md, (b) be documented in the README (or equivalent user-facing doc) with at least one concrete example, AND (c) be covered by an explicit UAT/verification check. Opt-out is required; default is "all three." This decision is project-level and applies retroactively to D-11 / D-12 (the `--week` flag).

### Claude's Discretion
- Token budgeting / batch-vs-streaming for Gemini calls — research recommends batch; planner picks the concrete call shape.
- Exact `IngestAdapter` protocol signature and `NormalizedItem` Pydantic model shape — driven by ARCHITECTURE §Data Model; planner finalizes.
- Whether `trafilatura` or `readability-lxml` is the primary full-fetch extractor (D-03 names `trafilatura` as preferred, but planner may flip if dependency footprint or licensing makes it a poor fit; the *behavior* is what's locked).
- Python project tooling (`uv` vs `pip + venv`, lockfile placement, ruff config) — STACK.md recommends `uv`; planner confirms.
- `GEMINI_API_KEY` loading mechanism in Phase 1 (`.env` via `python-dotenv`, plain `os.environ`, etc.) — research-default is `.env` file gitignored; planner confirms. Phase 5 will harden secrets formally.
- Test framework, CI hook timing, and coverage targets for Phase 1 — planner decides, but D-22 requires the `--week` UAT check.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase boundary & requirements (planner reads first)
- `.planning/ROADMAP.md` §Phase 1 — locked phase goal, success criteria, requirements list, and explicit Phase-1 non-scope ("no Astro, no archive, no dedup, no categorize/rank/rollup")
- `.planning/REQUIREMENTS.md` §Ingestion + §AI Pipeline — full text of INGEST-01, INGEST-02, INGEST-07, INGEST-08, PIPELINE-01
- `.planning/PROJECT.md` §Core Value + §Constraints + §Key Decisions — weekly cadence, "Sunday morning read," personal-scale cost ceiling, hard-coded source list for v1

### Stack & architecture (researcher + planner)
- `.planning/research/STACK.md` §1 (Astro is dormant in Phase 1), §2 (Python in GHA), §3 (feedparser), §6 (Gemini Flash-Lite + google-genai), §7 (SQLite + git-committed JSON — the JSON half is dormant in Phase 1) — locks library and model choices
- `.planning/research/ARCHITECTURE.md` §Component Responsibilities + §Recommended Project Structure + §Data Model (esp. §Primary Key Strategy for Items + §WeeklyDigest Idempotency Keys) + §Pipeline Orchestration §Weekly Cycle + §Suggested Build Order (items 1–3, 5–6 are Phase 1) — locks structure, PK strategy, store-and-forward pattern, build order
- `.planning/research/SUMMARY.md` §Cross-Cutting Tensions + §Cost Guardrails + §Risk Top-5 — the tension table calls out "Dedup scope in v1" (Tier 0–1 is Phase 3) and the cost table sets the $2/week target Phase 1 must respect even without enforcement code

### Quality invariants (planner + executor)
- `.planning/research/PITFALLS.md` #13 (prompt versioning in files with `prompt_version` on every summary), #14 (hierarchical roll-up — flagged for Phase 3, but the per-item grounding prompt established here is the seed), #25 (content-first gate — "two readable digests in ugly HTML before dashboard polish"; Phase 1 must NOT become a Phase 4 dry run)

### Process / state
- `.planning/STATE.md` — current position (Phase 1 of 5, no plans yet); session continuity log

No external ADRs, external specs, or design docs were referenced during this discussion; everything is contained in the planning tree above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — the project root is empty (greenfield). No existing modules, components, or utilities to reuse.

### Established Patterns
- None established in code yet. Patterns to ESTABLISH in Phase 1 (so later phases inherit them):
  - Adapter registry + `IngestAdapter` protocol (Phase 2 adds YouTube/Reddit/HN/email_rss adapters against the same protocol)
  - `NormalizedItem` Pydantic model as the canonical contract between adapters and the store
  - Versioned prompt files in `pipeline/llm/prompts/` with `prompt_version` persisted on each LLM output row
  - Orchestrator parameterizes `week_id` end-to-end (never calls `datetime.now()` past the entry point) — enables backfill, replay, and Phase 5 cron
  - `pipeline_runs` table as the substrate for all later observability (Phase 3 `pipeline_report.json`, Phase 4 Briefing notes, Phase 5 heartbeat)

### Integration Points
- `web/` directory is reserved but untouched in Phase 1. Phase 4 will populate `web/src/content/digests/{week_id}.json`. Phase 1's HTML output (`out/digest-{week_id}.html`) is deliberately a separate artifact so Phase 4 can replace the renderer without migrating data.

</code_context>

<specifics>
## Specific Ideas

- Three concrete seed sources are specified by name and feed URL (D-01); not a "you pick" — the planner uses these exact URLs.
- HTML styling brief specifies system-ui font, dark background, ~720px max-width, ~1.6 line-height (D-17). The planner is free to refine but the *vibe* is "readable Sunday morning, obviously not the Phase 4 dashboard."
- The user explicitly wants the `--week` CLI override visible and testable, not buried (D-12). This was the trigger for the project-level discoverability policy in D-22.

</specifics>

<deferred>
## Deferred Ideas

- **In-dashboard "force re-summarize this card" button** — not in Phase 3, 4, or 5 today. Captured during the Area 2 discussion. Likely a post-Phase-5 enhancement (v1.x or v2). Would require a webhook → GHA workflow_dispatch → targeted re-summarize + re-render path; non-trivial against a static site. Add to roadmap backlog for future consideration.

No other scope-creep redirects were needed — the discussion stayed inside Phase 1's boundary.

</deferred>

---

*Phase: 1-foundation-first-digest*
*Context gathered: 2026-05-21*
