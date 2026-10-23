# Phase 2: Expand Ingestion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `02-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-22
**Phase:** 2-expand-ingestion
**Areas discussed:** YouTube fetch & fallback strategy; Reddit/HN (retired mid-discussion); Email→RSS/KTN (retired mid-discussion); Source registry schema extension; Per-source failure isolation contract
**Mode:** default (interactive, single-question turns)

---

## YouTube fetch & fallback strategy

### Q1.1 — Where does YouTube transcript fetch run?

| Option | Description | Selected |
|--------|-------------|----------|
| 1 | Local-only fetch, no cloud fallback (run from residential IP only) | |
| 2 | Cloud-first with metadata fallback (title+description summary on block) | |
| 3 | Cloud-first with `yt-dlp --write-auto-subs` fallback | |
| 4 | Defer YouTube to a spike first | |
| 5 (user-proposed) | **Cloud-first with LOCAL fallback** (GHA tries first; failures get `pending_local` status; user re-runs locally to catch up) | ✓ |
| (revised) | Hybrid considered: **paid transcript API** as fallback or primary | not for v1 |
| (final form) | **Free-first** — `youtube-transcript-api` from GHA only; failures get `pending_local`; manual local catch-up; no paid API | ✓ |

**User's choice:** Cloud-first with local fallback, refined to free-first only (no paid API in v1).
**Notes:** The user initially asked "is cloud-first with local fallback an option?" — yes, and it became the preferred shape. Then asked about a button to trigger re-runs; this led to a substantive design discussion (see Q1.1b/1.1c below). Final choice: free-first only, user manually triggers local catch-up on their laptop when needed. Captured as D-23.

### Q1.1b — How does the reader know to run the local catch-up?

| Option | Description | Selected |
|--------|-------------|----------|
| 1 | HTML footer notice | |
| 2 | `out/last_run.md` only | |
| 3 | Both (footer + last_run.md) | |
| 4 | Defer to Phase 5 (heartbeat) | |
| (revised after D-25 promotion) | Per-card state only (strict reading of "no relegation to footer") | |
| **(final)** | **Top-of-digest summary line under the "Updated" timestamp**, plain-English, no footer | ✓ |

**User's choice:** Top-of-digest summary line.
**Notes:** User explicitly rejected the bottom-footer pattern with the broader rule "anything that failed shouldn't be relegated to the bottom footer; rather, it should be placed as if it ran correctly, just with the information about how it failed" — promoted to project-level D-25 (in-place degradation rendering). The aggregate top-of-digest notice (D-26) is the surface for digest-wide state that doesn't fit a single card.

### Q1.1c — Button feasibility for triggering the YouTube catch-up

| Option | Description | Selected |
|--------|-------------|----------|
| A | Vercel serverless → GHA workflow_dispatch (button works; cloud IP still blocks → doesn't solve the problem) | |
| B | Vercel function fetches transcript directly (AWS IP, also blocked) | |
| C | Vercel function → paid YouTube transcript API (works, ~$1–5/mo) | not for v1 |
| D | Paid API as primary, no fallback dance (works, eliminates problem class) | not for v1 |
| E | GHA self-hosted runner on the laptop (works, but heavy ops + security) | not for v1 |
| F | Tiny VPS with residential proxy subscription | not for v1 |
| G | Free-first, local catch-up command, no button | ✓ |

**User's choice:** G (free-first, manual local catch-up). All button options captured as deferred ideas; revisit after living with manual flow ~4 weeks.
**Notes:** User pushed back on initial framing ("why are you saying it's not practical?") — fair correction. The honest landscape was laid out; the free-first decision was made knowing the trade-off (a small manual step on the laptop). Captured as a deferred idea in CONTEXT.md.

### Q1.2 — How does Phase 2 discover new YouTube uploads (channel listing)?

| Option | Description | Selected |
|--------|-------------|----------|
| 1 | YouTube's native RSS feed per channel (`feeds/videos.xml?channel_id=…`) — reuses `feedparser` | ✓ |
| 2 | `yt-dlp --flat-playlist --dateafter now-7days` | |
| 3 | Hybrid (effectively same as 1) | |

**User's choice:** Option 1.
**Notes:** Zero new dependency for discovery; structurally close to existing `RssAdapter`; lowest risk of GHA breakage on YouTube's discovery surface (transcript fetch is the harder part). Captured as D-27.

### Q1.3 — Transcript truncation policy before sending to LLM

| Option | Description | Selected |
|--------|-------------|----------|
| 1 | **Hard cap by token count + smart-extract** (first ~4K + last ~1K + elision sentinel, cap ~6K total) | ✓ |
| 2 | Hard cap by token count + first-N-only (cap ~5K) | |
| 3 | No cap in Phase 2 — defer to Phase 3 cost guardrails | |
| 4 | Two-pass chunk-summarize then summarize-the-summaries | |

**User's choice:** Option 1, with note that the UX will be tested with real digests and the cap value adjusted if summaries feel clipped.
**Notes:** Pattern is named in PITFALLS #7. `summary_input_truncated` flag persisted on `item_summaries` rows for observability. Captured as D-28.

### Q1.4 — Seed YouTube channels for Phase 2

| Option | Description | Selected |
|--------|-------------|----------|
| 1 | User names 2–3 channels directly | ✓ |
| 2 | Default trio (Two Minute Papers + AI Explained + Latent Space) | |
| 3 | One seed channel only | |
| 4 | Empty list — adapter ships with no real seed | |

**User's choice:** Option 1 — user named two channels: `@howiaipodcast` and `@NateBJones`.
**Notes:** Channel IDs resolved live from the channel URL pages: `UCRYY7IEbkHLH_ScJCu9eWDQ` (How I AI) and `UC0C-17n9iuUQPylguM1d-lQ` (Nate B Jones). Both RSS feeds verified live and currently publishing as of 2026-05-21. Captured as D-29.

### Area 1 wrap-up sub-questions

After Q1.4, three open YouTube items were identified and surfaced for triage:

| Sub-item | Status |
|---|---|
| Adapter class shape (sibling vs composition) | → Claude's Discretion |
| `transcript_status` column placement (`items` vs `item_summaries`) | → Claude's Discretion |
| Visual indicator for video content in the card | → D-30 (small indicator; exact form is planner discretion) |

**User's choice:** Path 2 — keep (1) and (2) as discretion, lock (3) as a "small indicator that the source is a video."
**Notes:** User asked for clarification on what "planner discretion" meant; example from Phase 1's "Claude's Discretion" section was cited.

---

## Reddit & Hacker News (Area 2 — retired during discussion)

### Q2.1 — Outbound URL unwrapping policy at ingest

| Option | Description | Selected |
|--------|-------------|----------|
| 1 | Outbound URL canonical; discussion URL secondary | not applicable |
| 2 | Discussion URL canonical; outbound URL secondary | not applicable |
| 3 | Both equally — render two links per card | not applicable |
| 4 | Outbound canonical, discussion as small inline affordance | not applicable |
| (user-raised) | **Drop Reddit & HN from v1 entirely** | ✓ |

**User's choice:** Drop both from v1.
**Notes:** User articulated a sharper product principle that Reddit/HN don't fit: *"this digest is more a collection of known entities and their takes on things, rather than anonymous discussion."* This principle was promoted to project-level (D-31) and committed to PROJECT.md as the "Editorial Principle" section. The "Reddit pulse check" framing the user proposed was captured as INGEST-V2-04 (community pulse) in REQUIREMENTS.md v2. Three docs committed in a single change (`f4d7be3`): PROJECT.md, REQUIREMENTS.md, ROADMAP.md.

**Implication:** Original Area 2 was retired. The question set (subreddit selection, rate limiting, HN feed picks, attribution rendering) became moot.

---

## Email→RSS / Kill the Newsletter (Area 3)

### Q3.1 — Where do KTN feed URLs live?

| Option | Description | Selected |
|--------|-------------|----------|
| 1 | Env-var interpolation in `config/sources.yaml` | |
| 2 | Gitignored overlay (`config/sources.private.yaml`) | ✓ |
| 3 | Hybrid env-var pattern | |
| 4 | All in `.env`, JSON blob | |

**User's choice:** Option 2. **Rationale check:** user confirmed the repo will be public, making the leakage-prevention property of option 2 worth the small two-file overhead. Captured as D-32. *(Note: D-32 became moot when KTN was deferred entirely below; preserved in CONTEXT.md as the pattern to use whenever KTN ships in a v2+ context.)*

### Q3.2 — Seed newsletter(s) for Phase 2

User asked about *Ed Zitron* and *Ben's Bites*. Investigation showed both have public RSS feeds:
- Ed Zitron / *Where's Your Ed At* — `https://www.wheresyoured.at/feed`
- Ben's Bites — `https://www.bensbites.com/feed` (Substack-hosted)
- Last Week in AI (raised as a question follow-up) — `https://lastweekin.ai/feed` (Substack-hosted)

This surfaced a pattern: Editorial Principle-fitting newsletters all turn out to publish public RSS. KTN's residual case is email-only sources, which haven't surfaced as v1 needs.

| Option | Description | Selected |
|--------|-------------|----------|
| 1 | Add the three via RSS; **defer KTN adapter** to a later phase | |
| 2 | Add the three via RSS AND build KTN with one email-only seed | |
| 3 | Add the three via RSS AND build KTN with no seed (mocks only) | |
| (final) | **Drop KTN from v1 entirely; move INGEST-05 → INGEST-V2-05** | ✓ |

**User's choice:** Drop KTN from v1 entirely. *"If in the future I run into a truly newsletter only situation, I can explore it then as a v2+ enhancement."*
**Notes:** Second scope-reduction commit of the session (`49d0720`) updates PROJECT.md, REQUIREMENTS.md (added INGEST-V2-05), and ROADMAP.md. Phase 2 effective scope narrows further. The three RSS additions are captured as D-33.

---

## Source registry schema extension (Area 4)

### Q4.1 — How does the YouTube entry shape look in YAML?

| Option | Description | Selected |
|--------|-------------|----------|
| 1 | Reuse the `url` field — store full RSS URL with channel_id in query string | |
| 2 | Add `channel_id` field, derive `url` at adapter-load time | |
| 3 | **Pydantic discriminated union — separate subtypes per `type`** | ✓ |

**User's choice:** Option 3. *"I want the structure to be set up to scale to more format types. don't assume only 2 format types."*
**Notes:** User explicitly anchored the schema on the v2+ trajectory (community pulse, KTN, podcast, LinkedIn). Captured as D-36 with concrete v2-scaling examples.

### Q4.2 — Tags, per-source knobs, and the rest of the schema (combined)

| Sub-item | Selection |
|---|---|
| **Tags for the 5 new sources** | Proposed defaults accepted: how-i-ai/technical, nate-b-jones/business, where-your-ed-at/business, bensbites/business, last-week-in-ai/technical (D-37) |
| **`max_items` per source** | No (week filter is the natural cap) — D-38 |
| **Per-source User-Agent override** | No (project-wide UA in Phase 1 sufficient) — D-38 |
| **Per-source fetch delay** | No (no source forces it yet) — D-38 |

**User's choice:** "agree to both 1 and 2" — confirmed proposed tags and the "no per-source knobs in Phase 2" stance.

---

## Per-source failure isolation contract (Area 5 — INGEST-06)

### Q5.1–5.4 (combined — user accepted all defaults)

| Sub-item | Default | Selected |
|---|---|---|
| **Q5.1 Typed error taxonomy** | Yes, add now (5 categories: fetch_timeout / fetch_http_error / parse_error / empty_feed / adapter_internal) | ✓ (D-39) |
| **Q5.2 Source-health columns** | Yes, add all three (`last_success_at`, `last_item_at`, `last_error_category`) | ✓ (D-40) |
| **Q5.3 Empty-feed contract** | Codify (zero items = `empty_feed` category, not error; updates `last_success_at`) | ✓ (D-41) |
| **Q5.4 Circuit breaker / retry / per-source timeouts** | Defer to Phase 5 (Ops) | ✓ (D-42) |

**User's choice:** "defaults all work for me."
**Notes:** Each layer chosen specifically to feed forward — D-39 feeds OBS-02 in Phase 3; D-40 feeds OBS-01 in Phase 4 and OBS-03 in Phase 5; D-41 codifies what Phase 1's HTTP 304 path already does. D-42 was the only "no" — deferred until the weekly cron actually lands and changes the failure surface.

---

## Claude's Discretion

- `YoutubeAdapter` class factoring (composition vs sibling implementation)
- `transcript_status` column placement (`items` vs `item_summaries`)
- Exact form of the video content indicator (D-30)
- Exact failure-state copy wording on degraded cards (D-25 examples are starting points)
- Exact Pydantic discriminated-union syntax
- Sanity hard-cap on items-per-feed-parse (planner picks the number)
- YouTube channel-RSS adapter HTTP details (UA, timeout, 304 handling) — defaults from `RssAdapter`
- CLI flag name for the local YouTube catch-up command (must satisfy D-22 triad)
- Test framework choices, coverage targets, UAT checklist additions

## Deferred Ideas

- **One-click YouTube transcript catch-up button.** Implementation options explored: paid transcript API, GHA self-hosted runner on laptop, `cursor://` deep-link, menu-bar app. All rejected for v1 — revisit after ~4 weeks of living with the manual local-catch-up flow to see how often it actually triggers.
- **Inherited Phase-1 deferred:** in-dashboard "force re-summarize this card" button. Same family of feature; may converge with the YouTube catch-up button later.

## Out-of-session commits (scope reductions promoted to project tree)

- `f4d7be3` — **docs(02): drop Reddit/HN from v1; promote Editorial Principle** — updates PROJECT.md (added Editorial Principle section + Out of Scope entry + Key Decisions row), REQUIREMENTS.md (removed INGEST-04 from v1, added INGEST-V2-04), ROADMAP.md (narrowed Phase 2 requirements + success criteria).
- `49d0720` — **docs(02): drop email→RSS/KTN from v1; Phase 2 narrows to YouTube + RSS expansion** — updates PROJECT.md (removed email→RSS from Active Ingestion, added Out of Scope entry, added Key Decisions row), REQUIREMENTS.md (removed INGEST-05 from v1, added INGEST-V2-05), ROADMAP.md (narrowed Phase 2 again + added success criterion #5 codifying the in-place degradation requirement).

Both commits are part of the audit trail for this discussion — the actual CONTEXT.md commit follows.
