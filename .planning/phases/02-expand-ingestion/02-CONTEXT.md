# Phase 2: Expand Ingestion - Context

**Gathered:** 2026-05-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Add the YouTube ingestion adapter, expand the RSS source set with three new named-entity publishers, formalize per-source failure isolation into a typed contract, and rewrite the Phase-1 plain-HTML renderer to render every item in-place (no degraded-content footer aside). The deliverable is the same plain-HTML weekly digest, now mixed with YouTube transcript-summarized cards alongside the expanded RSS catalog, with failed items rendered as standard cards carrying plain-English explanations of their state.

**In scope (Phase 2):**
- `YoutubeAdapter` — channel-RSS discovery + `youtube-transcript-api` transcript fetch (cloud-first from GHA in later phases; v1 manual today)
- `transcript_status` lifecycle: `ok` → summarized; `pending_local` → cloud-blocked, retry available via local catch-up command; `missing` → no captions exist, never retry
- Transcript truncation policy: cap at ~6K input tokens; reshape long transcripts to first-4K + last-1K + elision sentinel; persist `summary_input_truncated` flag
- `SourceConfig` becomes a Pydantic discriminated union on `type`; ships two subtypes (`RssSource`, `YoutubeSource`) designed to scale to v2+ source types
- Two new RSS sources (Editorial Principle-fitting, public Substack feeds): `where-your-ed-at`, `bensbites`, `last-week-in-ai` *(see D-33; three new sources total)*
- Two YouTube seed channels: `how-i-ai`, `nate-b-jones`
- Per-source failure isolation contract (INGEST-06): typed error taxonomy in `RunStats.errors`; source-health columns on `sources` table; codified empty-feed contract
- **Renderer rewrite:** remove the "Also seen this week" footer aside from `pipeline/render/html.py`; degraded items render in-place as standard cards with state-aware in-card body copy (per the project-level In-place Degradation rule promoted this session, which supersedes Phase 1 D-05)
- Top-of-digest pipeline notice surface (under the "Updated" timestamp): plain-English aggregate state line that appears when the digest has any incomplete-but-recoverable state (e.g., "N video summaries will fill in when refreshed from a different network"); hides at zero-state

**Out of scope (Phase 2 — deferred):**
- Reddit / Hacker News ingestion → moved out of v1 entirely this session per Editorial Principle (now INGEST-V2-04 community pulse)
- Email→RSS / Kill the Newsletter bridge → moved out of v1 entirely this session per Editorial Principle observation that fitting newsletters all publish public RSS (now INGEST-V2-05)
- Dedup, categorization, ranking, weekly narrative roll-up, `pipeline_report.json` (Phase 3)
- Astro dashboard, archive, formal `Pipeline notes` UI section, full DISPLAY-06 video styling polish (Phase 4)
- GHA cron, Cloudflare Pages deploy, secret scanning, hard $5/week LLM cap, heartbeat, retry-with-backoff, circuit breaker, per-source timeouts (Phase 5)
- One-click YouTube transcript catch-up button (deferred idea; revisit after living with manual flow ~4 weeks)

**Locked requirements** (from REQUIREMENTS.md after this session's scope-reduction commits):
- **INGEST-03** — System fetches new uploads from configured YouTube channels and retrieves transcripts where available
- **INGEST-06** — A single failing source does not break the weekly run; other sources still complete and the failure is recorded

INGEST-04 (Reddit/HN) and INGEST-05 (email→RSS) were removed from v1 during this discuss session; see `docs(02): drop Reddit/HN from v1` (commit `f4d7be3`) and `docs(02): drop email→RSS/KTN from v1` (commit `49d0720`). They live in REQUIREMENTS.md v2 section as INGEST-V2-04 and INGEST-V2-05.

</domain>

<decisions>
## Implementation Decisions

### Stack & adapter pattern carried forward (from Phase 1; not re-decided here)
- **Carry D-00d:** Adapter registry pattern with `IngestAdapter` protocol from `pipeline/adapters/base.py`. Phase 2 adds `YoutubeAdapter` as a sibling implementation; `pipeline/orchestrator._pick_adapter` switches on the new discriminated-union subtype (D-36).
- **Carry D-00c:** Item primary key strategy `UNIQUE(source_id, external_id)` is unchanged. YouTube items use the video ID as `external_id` (extracted from the feed entry's `yt:videoId` or derived from the canonical watch URL via the same sha256 fallback Phase 1 uses).
- **Carry Phase 1 orchestrator pattern:** per-source try/except in `pipeline/orchestrator._ingest` already gives INGEST-06's happy path; Phase 2 layers the typed error taxonomy on top.

### Editorial Principle (project-level — promoted to PROJECT.md this session)
- **D-31 (project-level):** **The digest is a collection of known entities and their takes, not anonymous community signal.** Every v1 source must fit this principle. Direct consequences this session:
  - Reddit and Hacker News removed from v1 → INGEST-V2-04 (community pulse, a distinct product surface)
  - Email→RSS/KTN removed from v1 → INGEST-V2-05 (every fitting newsletter has turned out to have public RSS; KTN's residual case is email-only sources we don't currently want)
- See `.planning/PROJECT.md` Editorial Principle section for full text; the principle becomes the gate for any future source-type proposal.

### Reader-surface language (project-level — promoted)
- **D-24 (project-level):** **Reader-surface language policy.** The digest site, the Phase 4 dashboard, and the future Phase 4 `Pipeline notes` UI use **plain English only** — no shell commands, no flag syntax, no file paths, no code identifiers, no error class names. Technical surfaces (`out/last_run.md`, README, `--help`) keep their literal commands. Applies retroactively to D-23 (the YouTube pending-transcript notice copy) and to D-26 (top-of-digest pipeline notice). Phase 4 inherits this rule by reference.

### In-place degradation rendering (project-level — promoted, supersedes Phase 1 D-05)
- **D-25 (project-level):** **In-place degradation rendering.** Items that fail any pipeline stage (transcript fetch, summary generation, full-text enrichment, LLM call failure) MUST render in their natural sort position alongside successful items, as standard-shaped cards. The failure state is communicated inside the card body in plain English (per D-24). There MUST be no "Also seen this week" footer aside, no separate degraded section, no relegation. The card's outer structure matches a successful item; only the summary-area body copy changes to describe what is shown, what is missing, and (where applicable) how it might be filled in later — without naming code, files, or commands.
- **This supersedes Phase 1 D-05.** Phase 2's plan MUST include revising `pipeline/render/html.py` to remove `_render_pipeline_notes`, `OMITTED_SECTION_HEADING`, the `_is_displayable` partitioning, and the footer `<aside class="pipeline-notes">`. The header item count reverts to total items (no displayed-vs-omitted distinction).
- **Failure copy library** (examples — planner finalizes exact wording, must stay plain-English per D-24):
  - YouTube `pending_local`: *"This video's transcript wasn't reachable during the weekly run. The summary will be added when the digest is refreshed from a different network. Title and description are below."*
  - YouTube `missing`: *"No captions are available for this video, so there's no transcript to summarize. The title and description are below."*
  - Phase 1 thin-RSS path: *"The source published only a short teaser, so the summary is limited to what's in the title and the available preview."*
  - Full-fetch failed (Phase 1 enrichment path): *"The full article couldn't be retrieved, so this summary is based on the source's short preview."*
  - LLM call failed (any phase): *"The summary couldn't be generated this week. The title and link are below; the summary will appear if the digest re-runs successfully."*

### YouTube fetch strategy
- **D-23:** **Free-first YouTube transcripts.** Phase 2 uses `youtube-transcript-api` only — no paid transcript service in v1. Recovery path is a local catch-up command (manually invoked from a residential IP) rather than a paid API fallback. `transcript_status` enum on items: `ok` (summary path), `pending_local` (cloud-blocked or transient; eligible for catch-up retry), `missing` (no captions exist on the video; never retried). The local catch-up CLI flag (e.g., `--only-pending-transcripts`) is a new "hidden capability" and MUST satisfy Phase 1 D-22 (covered in README + `--help` + UAT).
- **D-27:** **YouTube discovery via channel RSS.** New uploads are discovered through `https://www.youtube.com/feeds/videos.xml?channel_id={id}`, parsed by the existing `feedparser` dependency. `yt-dlp` is *not* a Phase 2 dependency. `YoutubeAdapter` is structurally close to `RssAdapter`; the YouTube-specific work is (a) extracting `external_id` from `yt:videoId`, (b) the post-fetch transcript-API call, (c) the `transcript_status` lifecycle. RSS endpoint returns ~15 most recent uploads — acceptable cap at v1 channel count and weekly cadence.
- **D-28:** **Transcript truncation policy.** When a YouTube transcript exceeds ~6,000 input tokens (~24K chars), the LLM input is reshaped to: first ~4,000 tokens + final ~1,000 tokens + an explicit elision sentinel in the prompt body (so the model does not fabricate to cover the gap). `item_summaries` rows carry a `summary_input_truncated` boolean for observability. Cap value lives in config (tunable). Mid-content elision pattern is named in PITFALLS #7.
- **D-29:** **YouTube seed channels (two).** `config/sources.yaml` ships with two YouTube entries:
  - `how-i-ai` — channel ID `UCRYY7IEbkHLH_ScJCu9eWDQ` — *How I AI* — tag: technical
  - `nate-b-jones` — channel ID `UC0C-17n9iuUQPylguM1d-lQ` — *Nate B Jones* (full channel title: "AI News & Strategy Daily | Nate B Jones") — tag: business
  - Both verified live and publishing as of 2026-05-21.
- **D-30:** **Video content indicator.** YouTube source cards carry a small visual indicator that the source is a video (e.g., a tiny suffix or glyph adjacent to the source badge). Exact form is planner discretion (must be small, must be unambiguous, must not change the card's structural footprint per D-25). Phase 4 owns the formal DISPLAY-06 polish.

### Top-of-digest pipeline notice
- **D-26:** **Top-of-digest pipeline notice surface.** When any pipeline state affects the digest's completeness (e.g., pending-local transcripts present, source fetch failures during the week), a single plain-English summary line renders **under the "Updated" timestamp in the header area** of the HTML digest. No bottom footer; no aside. Zero-state hides the line entirely. Per D-25, individual cards still carry their own state in-card; this header line is the aggregate hint so the reader sees it Sunday morning without scrolling. Phase 4 inherits this rule when it builds the formal `Pipeline notes` UI section (OBS-01).

### RSS source expansion
- **D-33:** **Three new RSS sources** added to `config/sources.yaml` (joining the three from Phase 1 D-01):
  - `where-your-ed-at` — *Where's Your Ed At* (Ed Zitron) — `https://www.wheresyoured.at/feed` — tag: business
  - `bensbites` — *Ben's Bites* (Ben Tossell) — `https://www.bensbites.com/feed` — tag: business
  - `last-week-in-ai` — *Last Week in AI* (Andrey Kurenkov & Daniel Bashir) — `https://lastweekin.ai/feed` — tag: technical
  - All three are Substack-style public RSS — zero new code, mechanical config rows. RSS catalog grows 3 → 6.

### Source registry schema (extension)
- **D-36:** **`SourceConfig` becomes a Pydantic discriminated union on `type`.** Each source type has its own typed subtype with its own fields. Phase 2 ships two subtypes:
  - **`RssSource`** — `id, type="rss", url, display_name, tag?, enabled` (shape unchanged from Phase 1; existing rows parse identically — no migration of YAML data).
  - **`YoutubeSource`** — `id, type="youtube", channel_id, display_name, tag?, enabled` (RSS feed URL derived by the adapter from `channel_id`; never stored). `channel_id` validator enforces `^UC[A-Za-z0-9_-]{22}$`.
  - Loader returns `list[SourceConfig]` typed as the union; orchestrator `_pick_adapter` switches on the subtype.
  - **Scaling property:** future source types (v2 `RedditSource`, `KtnSource`, podcast, LinkedIn) each add a subtype with their own fields without touching existing subtypes. Migration from current shape is a one-step mechanical wrap-existing-fields edit the planner does in Phase 2.
  - Planner finalizes the exact Pydantic syntax (`Annotated[Union[...], Field(discriminator="type")]` is the standard Pydantic v2 pattern; already a project dependency).
- **D-37:** **Tag assignments for the five new sources.** YouTube `how-i-ai` → technical; YouTube `nate-b-jones` → business; RSS `where-your-ed-at` → business; RSS `bensbites` → business; RSS `last-week-in-ai` → technical. Phase 1 D-02 still holds: tags are config-only metadata for human reference; Phase 3 owns LLM categorization and may supersede the field.
- **D-38:** **No `max_items`, no per-source User-Agent, no per-source fetch delay** in the Phase 2 schema. The ISO-week window is the natural cap; a sanity hard-cap of 1000 items per feed-parse is planner discretion to prevent OOM on a runaway feed. Per-source overrides ship only when a real source forces them.

### Per-source failure isolation contract (INGEST-06)
- **D-39:** **Typed error taxonomy in `RunStats.errors`.** Each entry carries `category` (enum: `fetch_timeout`, `fetch_http_error`, `parse_error`, `empty_feed`, `adapter_internal`), `source_id`, `phase`, `message` (free-text human detail), and optional `http_status`. Free-text message is preserved for `out/last_run.md` rendering. Categories chosen to cover Phase 2's surface and to feed Phase 3 `pipeline_report.json` (OBS-02), Phase 4 `Pipeline notes` UI (OBS-01), and Phase 5 heartbeat (OBS-03) without rework.
- **D-40:** **Source-health columns on `sources` table.** Add `last_success_at` (timestamp), `last_item_at` (timestamp — when this source last contributed any item to a successful run), and `last_error_category` (nullable, mirrors the D-39 enum). Orchestrator writes these in the same SQLite commit that finalizes `pipeline_runs`. Migration cost is near-zero now (small data volume); deferring incurs backfill cost later. Used by Phase 4 OBS-01 and Phase 5 heartbeat.
- **D-41:** **Empty-feed contract.** A successful fetch returning zero new items in the week window is recorded as `category=empty_feed` in `RunStats.errors`. It does NOT fail the run, NOT abort other sources, NOT trigger "source failed" UI in either the top-of-digest notice (D-26) or per-card body copy (D-25). It DOES update `last_success_at` (the fetch worked) and is visible to source-health detection: 3+ consecutive weeks of `empty_feed` for the same source = silent source per PITFALLS #6 (alerting/UI surfacing of this is Phase 4/5, not Phase 2). Phase 1's existing HTTP 304 handling in `pipeline/adapters/rss.py` is the precedent; Phase 2 codifies the contract uniformly across all adapters.
- **D-42:** **Circuit breaker, retry-with-backoff, and per-source timeouts deferred to Phase 5 (Ops).** Phase 1's project-wide 20s timeout plus Phase 2's per-source isolation already cover the weekly-cadence happy path; manual re-run next week is the fallback for transient failures at this scale and cadence. Phase 5 owns the formal retry/circuit/backoff policy when GHA cron lands and the failure surface broadens.

### Claude's Discretion
- **`YoutubeAdapter` class shape** — sibling class to `RssAdapter` is the assumed factoring; planner finalizes after reading `pipeline/adapters/rss.py` and `pipeline/orchestrator.py`. Composition (RSS-fetch + transcript-post-step) vs full sibling implementation is the planner's call; behavior must satisfy D-23 / D-27 / D-28 either way.
- **`transcript_status` column placement** — default to the `items` table (per-item property of source content, orthogonal to summary state); planner may move it to `item_summaries` if the schema is cleaner that way.
- **Exact form of the video content indicator (D-30)** — text suffix (`[video]`), glyph (▶, ▷), italic source name, etc. — planner picks; must be small, unambiguous, and not change card structural footprint (per D-25).
- **Exact wording of the failure-state copy on degraded cards (D-25 examples)** — planner refines; must stay plain-English per D-24.
- **Exact Pydantic discriminated-union syntax (D-36)** — `Annotated[Union[...], Field(discriminator="type")]` is the standard v2 pattern; planner confirms.
- **Sanity hard-cap on items-per-feed-parse (D-38)** — planner picks the number (1000 suggested as a starting point); OOM guard, not a config knob.
- **YouTube channel-RSS adapter HTTP behavior** — User-Agent, timeout, 304 handling — reuse RssAdapter's defaults unless YouTube's CDN forces different.
- **CLI flag name for the local YouTube catch-up command (D-23)** — `--only-pending-transcripts` is a placeholder; planner picks a name and ensures it satisfies the D-22 discoverability triad (README + `--help` + UAT).
- **Test framework choices, coverage targets, UAT checklist additions** — Phase 1 set the precedent (pytest, in-line tests); planner finalizes Phase 2 additions, including explicit UAT entries for: the new sources actually producing items, transcript-pending UX rendering, in-place degradation card copy (D-25), top-of-digest pipeline notice (D-26), and the local catch-up command (D-23 + D-22 triad).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase boundary, requirements, and Editorial Principle (planner reads first)
- `.planning/ROADMAP.md` §Phase 2 — locked phase goal, success criteria, narrowed requirements list (INGEST-03, INGEST-06), explicit Phase-2 non-scope, and the in-place-degradation requirement now codified as success criterion #5
- `.planning/REQUIREMENTS.md` §Ingestion + §v2 Extended Ingestion — full text of INGEST-03, INGEST-06; v2 entries INGEST-V2-04 (community pulse) and INGEST-V2-05 (email→RSS bridge) that capture what was descoped from v1 this session
- `.planning/PROJECT.md` §Editorial Principle + §Core Value + §Out of Scope + §Key Decisions — Editorial Principle is the gate for any future source-type proposal; Out of Scope contains the reasoned exclusions for Reddit/HN, email→RSS, Twitter/X, podcast audio, etc.; Key Decisions table now contains the two rows added this session

### Stack & architecture (researcher + planner)
- `.planning/research/STACK.md` §3 (feedparser — handles YouTube channel RSS without new dependency), §4 (YouTube — `youtube-transcript-api` for transcripts; `yt-dlp` only as caption-fallback path, not used in Phase 2), §6 (Gemini Flash-Lite + google-genai — same model for YouTube summaries), §7 (SQLite for working store)
- `.planning/research/PITFALLS.md` #6 (RSS feed rot — source-health columns from D-40 mitigate), #7 (YouTube transcript gaps from cloud IP — D-23 free-first + pending_local lifecycle is the named mitigation; D-28 transcript truncation), #13 (prompt versioning — existing `prompt_version` on `item_summaries` covers YouTube summaries identically)
- `.planning/research/SUMMARY.md` §Cross-Cutting Tensions + §Risk Top-5 — keeps the cost/quality framing top-of-mind for transcript truncation decisions
- `.planning/research/ARCHITECTURE.md` §Component Responsibilities + §Data Model — Phase 1's existing layout is the structural model; YouTube adapter slots into `pipeline/adapters/` as a sibling; schema changes from D-40 are additive

### Phase 1 decisions still in force
- `.planning/phases/01-foundation-first-digest/01-CONTEXT.md` — most relevant Phase-1 carries:
  - **D-00d** — `IngestAdapter` protocol + registry pattern (Phase 2 extends)
  - **D-00c** — `UNIQUE(source_id, external_id)` PK strategy (Phase 2 uses YouTube `videoId` as `external_id`)
  - **D-22 (project-level)** — Hidden-capability discoverability policy: any new CLI flag/env var MUST be in README + `--help` + UAT. Phase 2's local catch-up command (D-23) is the next test of this policy.
  - **D-05** — **SUPERSEDED THIS SESSION** by project-level D-25 (in-place degradation). Phase 2's renderer rewrite explicitly removes the footer-aside pattern D-05 described.

### Existing Phase-1 code Phase 2 will extend or revise
- `pipeline/adapters/base.py` — `IngestAdapter` protocol + `FetchError`. Unchanged in Phase 2; `YoutubeAdapter` implements the same protocol.
- `pipeline/adapters/rss.py` — Reference implementation. `YoutubeAdapter` mirrors its shape (fetch → parse → emit `NormalizedItem`s).
- `pipeline/orchestrator.py` — `_pick_adapter` registry switches to discriminated-union dispatch (D-36); `_ingest` per-source try/except evolves to populate the typed error taxonomy (D-39).
- `pipeline/models.py` — `NormalizedItem` unchanged in Phase 2; YouTube items use the same shape (title = video title; publisher = channel display name; raw_content = video description).
- `pipeline/config.py` — `SourceConfig` becomes the discriminated union per D-36; `SourceType` literal grows to `rss | youtube`; validators per subtype.
- `pipeline/render/html.py` — **REWRITE per D-25.** Remove `_render_pipeline_notes`, `OMITTED_SECTION_HEADING`, `_is_displayable` partitioning, the `<aside class="pipeline-notes">` block, and the `.pipeline-notes` CSS. Add in-place per-card body copy for the failure states (D-25 examples). Add the top-of-digest pipeline notice surface under the "Updated" timestamp (D-26).
- `config/sources.yaml` — Add three RSS rows (D-33) and two YouTube rows (D-29) with their tags (D-37). Schema must conform to the new discriminated union (D-36).
- `store/db.py` — Schema additions for source-health columns (D-40: `last_success_at`, `last_item_at`, `last_error_category` on `sources` table); migration is additive (no existing rows lose data).

### Process & state
- `.planning/STATE.md` — Updated by the SDK after this discuss-phase session completes.
- `.planning/phases/02-expand-ingestion/02-DISCUSSION-LOG.md` — Audit trail of options considered in this session (human-only).

No external ADRs, external specs, or design docs were referenced. The two scope-reduction commits from this session (`f4d7be3` and `49d0720`) capture the consequence in the project tree.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`pipeline/adapters/base.py` `IngestAdapter` protocol + `FetchError`** — `YoutubeAdapter` implements the same protocol; one new entry in `_pick_adapter` registry wires it in.
- **`pipeline/adapters/rss.py` HTTP fetch shape** — User-Agent, 20s timeout, follow_redirects, raise-on-bozo logic is the reference for the YouTube channel-RSS HTTP call (the YouTube CDN serves the same XML shape as a regular RSS feed; feedparser handles it transparently).
- **`pipeline/models.py` `NormalizedItem`** — UTC-aware `published_at`, `content_hash`, `strip_html()` are reused as-is. YouTube `raw_content` = video description; `content_hash` = sha256 of description (same shape).
- **`pipeline/orchestrator.py` `_ingest` per-source try/except** — Already gives the INGEST-06 happy path. Phase 2 layers the typed error taxonomy (D-39) on top without changing the control flow.
- **`pipeline/reporting/last_run.py` `RunSummary` + `write_last_run_md`** — Already renders per-source items + errors. Phase 2 extends to render the new `category` field in human-readable form on the technical surface.
- **`store/db.py` schema migrations** — `sources` table already exists from Phase 1 Plan 01-01; D-40 adds three columns (additive migration).
- **`feedparser` dependency** — Already in use for RSS; the same parser handles YouTube's `feeds/videos.xml` output. No new dependency for YouTube discovery.

### Established Patterns Phase 2 extends or relies on
- **Adapter registry pattern (Phase 1 D-00d)** — One-line addition to `_pick_adapter` per new source type. D-36's discriminated union slightly evolves this: the switch is on the subtype, not on a string literal alone.
- **`NormalizedItem` as the canonical contract between adapters and the store** — Adapters never see SQLite. Phase 1 invariant; preserved.
- **Versioned prompt files (Phase 1 D-04)** — YouTube summaries use the same prompt file (`pipeline/llm/prompts/summarize_v1.md`). No new prompt version unless transcript content materially changes the summarization contract — which it does NOT (D-04's grounding rules apply identically to transcript text vs RSS body).
- **Orchestrator parameterizes `week_id` end-to-end (Phase 1 D-11)** — YouTube path inherits this — no `datetime.now()` calls inside the YouTube adapter.
- **`pipeline_runs` table as observability substrate (Phase 1 D-09)** — Phase 2 extends with `last_error_category` per D-40, populated by the same finalizer code path.
- **Reader-surface vs technical-surface language split (D-24)** — Already an implicit Phase 1 distinction (`out/last_run.md` is technical, the HTML digest is reader-facing). Phase 2 makes the rule explicit; the renderer rewrite is the first concrete test.

### Integration Points
- **`web/` directory remains dormant** — Phase 2 does not touch Astro / Content Collections; Phase 4 still owns the formal dashboard. Phase 2's `out/digest-{week_id}.html` remains the deliverable artifact.
- **Phase 3 dependency hand-off** — Phase 2's typed error taxonomy (D-39) and `transcript_status` lifecycle (D-23) feed Phase 3's `pipeline_report.json` (OBS-02) and the dedup-before-LLM constraint (DEDUP-04) — YouTube items are deduped against their canonical watch URL like RSS items are deduped against their canonical article URL.
- **Phase 4 dependency hand-off** — Phase 2 establishes the top-of-digest pipeline notice surface (D-26) and the in-place degradation card copy (D-25) — both are inherited verbatim into the Astro dashboard (Phase 4 styles, not rewrites). Phase 2's source-health columns (D-40) feed Phase 4's OBS-01 "Pipeline notes" UI.
- **Phase 5 dependency hand-off** — Phase 5's heartbeat (OBS-03) reads `last_success_at` from D-40; circuit/retry/backoff layers on top of D-39's error categories.

</code_context>

<specifics>
## Specific Ideas

- **Concrete seed sources are named, not "you pick":**
  - Two YouTube channel IDs verified live and active (D-29).
  - Three new RSS feed URLs verified live and active (D-33).
  - Planner uses these exact identities; integration tests run against real feeds.
- **The Editorial Principle ("known entities and their takes, not anonymous community signal") is now the gate for any future source-type proposal.** Two scope reductions this session (Reddit/HN, email→RSS/KTN) directly trace to it. The principle text in PROJECT.md is the canonical version; any future source addition starts with "does this fit the Editorial Principle?"
- **Reader-surface language must be plain English (D-24).** No CLI commands, paths, flags, or code names appear in the digest HTML or future dashboard. The user is the reader, not a developer, when looking at the digest. Failure-state copy on degraded cards is the immediate test of this rule.
- **All failed items render in-place (D-25), not in a footer.** The reader's eye sees the failures alongside successes in chronological position, with plain-English explanations of what's missing and why. No "Also seen this week" relegation.
- **The top-of-digest pipeline notice (D-26) replaces the bottom footer for aggregate pipeline state.** Visible Sunday morning without scrolling; hides when zero-state.
- **Local YouTube catch-up command is a "hidden capability" subject to Phase 1 D-22** — README documentation + `--help` description + explicit UAT entry are mandatory.

</specifics>

<deferred>
## Deferred Ideas

- **One-click YouTube transcript catch-up** — In-digest button or shortcut that triggers a local re-fetch of pending YouTube transcripts without manually opening a terminal. Implementation candidates explored this session:
  - **Paid YouTube transcript API** (Supadata, Tactiq, AssemblyAI, etc.) used as fallback or primary — would make the button trivially work via any serverless function. Decided **not** for v1 (free-first per D-23); ~$1–5/mo capability if desired later.
  - **GHA self-hosted runner on the laptop** — button → workflow_dispatch → laptop runner. Real solution; high ops/security cost. Phase 5+ / v2 territory.
  - **`cursor://` deep-link** — opens the project in the IDE; user runs the command from there. Barely a button.
  - **Menu-bar app / desktop notification** — local always-on infra.
  - Revisit after living with the manual local-catch-up flow for ~4 weeks to see how often it actually triggers and whether the manual cost justifies any of these.
- **Inherited from Phase 1:** *In-dashboard "force re-summarize this card" button.* Still deferred; same family of feature as the YouTube catch-up button. May converge into a single "refresh this card / source" UX in a later phase.

No other scope-creep redirects were needed. Two scope **reductions** were the major outputs of this discussion (Reddit/HN and email→RSS/KTN dropped from v1) — both already committed to PROJECT.md / REQUIREMENTS.md / ROADMAP.md in separate commits and surfaced as INGEST-V2-04 and INGEST-V2-05 in the v2 backlog.

</deferred>

---

*Phase: 2-expand-ingestion*
*Context gathered: 2026-05-22*
