<!--
THIS FILE IS A HARD GATE FOR PHASE PLANNING.

If you are reading this as part of a GSD workflow (discuss-phase,
plan-phase, ingest, ultraplan, autonomous, or any skill that produces
PLAN.md / CONTEXT.md / ROADMAP.md / PROJECT.md content):

1. You MUST read every entry in this file BEFORE drafting any plan,
   research artifact, or roadmap edit.
2. If your in-progress plan would touch any LOCKED rule below, you
   MUST stop, surface the conflict to the user, and wait for explicit
   approval before proceeding. You may not bury the proposed override
   inside a plan document or rationalize it via "the new design is
   better." Propose it as a question; let the user decide.
3. A phase plan can refine HOW a locked rule is implemented. It can
   never relax, override, or supersede WHETHER a locked rule applies.
4. The user authored these rules deliberately. They are not defaults
   to be re-examined every phase.
-->

# Locked Directives

Project-level rules that supersede any phase-level decision. New
phase plans must check this file first.

**Maintained by:** the user, with optional unlocking via explicit
"unlock LOCKED-XX" instruction. Adding a rule requires user approval;
removing one does too.

## Procedural rules

- **Locked rules cannot be overridden by phase decisions.** A
  CONTEXT.md or PLAN.md that contradicts a locked rule must be
  rejected at plan-check time.
- **Proposing a change is allowed, executing one is not.** If an
  agent believes a locked rule should change, it must surface the
  proposal to the user as an explicit question, separate from any
  plan artifact, and wait for approval.
- **Plan documents must cite locked rules they comply with**, not
  just decision IDs from CONTEXT.md. This makes future cross-checks
  cheap.
- **The doc is short on purpose.** Each entry is a single-paragraph
  rule. If it needs more context, link the PROJECT.md row.

---

## LOCKED-01 — Footer-aside is RSS-thin-only

**Locked:** 2026-05-22 after Phase 2 visual UAT
**Refined:** 2026-05-23 during Phase 3 visual UAT (narrowed footer scope)
**Authority:** PROJECT.md `Key Decisions` table → row labeled
"LOCKED — Footer-aside is RSS-thin-only"
**History:**
- Phase 1 D-05 originally established the footer.
- Plan 01-03 inline-regressed the rule once; reverted in commit
  `5f8e9f0`.
- Plan 02-03 D-25 attempted to override it again ("in-place
  degradation, no relegation") and produced a 12-of-38-degraded-card
  main feed that the user rejected during Phase 2 UAT.
- 2026-05-22 lock made footer = "anything we couldn't summarize"
  with quota_exhausted as the sole in-place exception.
- 2026-05-23 refinement (this version) narrowed the footer to
  `summary_status='thin'` only. The 2026-05-22 lock was sending
  long-form videos (full transcripts fetched, LLM hit quota) and
  short RSS stubs to the same footer aside, blurring two genuinely
  different reader signals: "this isn't worth a summary" vs "we
  haven't generated a summary yet". User feedback during Phase 3
  visual UAT was unambiguous: keep the footer for RSS-thin only;
  every other failure mode shows in-place with the locked degraded
  body so the reader sees context (publisher, video badge, date,
  category) rather than just an outbound link in a footer.

**Rule:** Cards route to one of two display surfaces based on
`summary_status`:

1. **Footer aside (`<aside id="also-seen">`)** — outbound link only,
   no body copy. This is the **only** route to the footer:
   - `summary_status='thin'` — RSS body too short to summarize
     (the `content_too_thin` gate fired).

2. **Main feed** — all other cards, including the in-place degraded
   bucket below.
   - `summary_status='ok'` (tldr present) — full card.
   - In-place degraded card (locked body copy
     `"The summary couldn't be generated this week."`):
     - `summary_status='quota_exhausted'` — LLM rate-limit / 429 /
       `RESOURCE_EXHAUSTED`.
     - `summary_status='api_error'` — LLM API errored.
     - `summary_status='parse_error'` — LLM response unparseable.
     - `summary_status='client_init_error'` — LLM client failed
       to init (e.g., key missing).
     - `summary_status='transcript_missing'` — YouTube transcript
       not fetched yet (`pending_local` / `missing`); summary will
       come on the next residential catch-up + summarize run.

**Why these are all the same UX:** the reader doesn't need to know
*why* the summary isn't ready. Quota / api / parse / transcript-pending
are all transient — the next run is likely to fix them. Putting them
all in the same in-place degraded card preserves the weekly skim flow
(category context, publisher, date, position in the briefing). Only
genuinely-thin RSS stubs ("New release: 0.1a4") get the link-only
footer treatment, because they will never have a real summary to add.

**Code anchors:**
- `pipeline/render/partition._partition_cards()` — **primary** single source of
  truth for main-vs-footer routing (Plan 04-01 extract).
- `pipeline/render/digest_json.emit_digest_json()` — Astro-era structural
  enforcement: calls `partition._partition_cards()` before serializing
  `main_feed[]` and `footer_aside[]` to `web/src/content/digests/{week_id}.json`.
  Astro never sees raw routing inputs — only pre-partitioned lists (Plan 04-02).
- `pipeline/render/partition._IN_PLACE_TRANSIENT_STATUSES` — the locked set
  of statuses that route to the in-place degraded card.
- `pipeline/render/html._partition_cards()` — **deprecated** dev-preview
  re-export only; canonical routing lives in `partition.py`.
- `pipeline/llm/summarize._classify_llm_exception()` — classifies
  Gemini errors into the `summary_status` taxonomy.
- `pipeline/orchestrator._infer_summary_status()` — maps legacy rows
  with NULL `summary_status` to one of the locked values.
- `pipeline/render/partition.QUOTA_BODY_COPY` — the locked exact-string
  for the in-place degraded body. Despite its name, this copy is
  shared across all five in-place statuses.
- `store/migrations/003_summary_status.sql` — schema column that
  carries the routing signal forward.

**Phase plans may refine:** the visual treatment of the footer (CSS,
ordering, grouping), the visual treatment of the in-place degraded
card, the exact taxonomy of `summary_status` values (provided every
new value is explicitly placed in either the footer or the in-place
bucket, not silently routed by default).

**Phase plans must not:**
- Route any non-`thin` status to the footer.
- Remove the footer entirely.
- Reword `QUOTA_BODY_COPY` without an explicit unlock request.
- Add a new `summary_status` value without amending this rule and
  the `_IN_PLACE_TRANSIENT_STATUSES` set together.

---

## How to add a new locked rule

1. User decides a rule rises to LOCKED status. (Typically after seeing
   the same wrong outcome happen twice across phases.)
2. Add the rule to `PROJECT.md` `Key Decisions` with the prefix
   `LOCKED —` and a "Locked YYYY-MM-DD" note.
3. Add a `LOCKED-XX` entry here with: rule, history, code anchors,
   what phase plans may refine, what they must not do.
4. Increment the LOCKED counter. Do not renumber existing entries.

## How to retire a locked rule

1. User issues an explicit "unlock LOCKED-XX" instruction in chat.
2. Move the rule from "active" to a "Retired" section below with the
   retirement date and reason.
3. Update `PROJECT.md` to strike through the row but keep the history.

## Retired

*(none yet)*
