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

## LOCKED-01 — Footer-aside for thin / unsummarizable items

**Locked:** 2026-05-22 after Phase 2 visual UAT
**Authority:** PROJECT.md `Key Decisions` table → row labeled
"LOCKED — Footer-aside for thin / unsummarizable items"
**History:**
- Phase 1 D-05 originally established the footer.
- Plan 01-03 inline-regressed the rule once; reverted in commit
  `5f8e9f0`.
- Plan 02-03 D-25 attempted to override it again ("in-place
  degradation, no relegation") and produced a 12-of-38-degraded-card
  main feed that the user rejected during Phase 2 UAT.

**Rule:** Items that the pipeline cannot turn into a real TL;DR
fall into two buckets:

1. **Content-thin / unsummarizable** — RSS body too short, YouTube
   transcript missing or pending, content-too-thin gate, enrichment
   failed, parse error, api error other than rate-limit — these go
   to the `<aside id="also-seen">` footer of the digest as outbound
   links only. They do not appear in the main feed.

2. **Transient LLM-call failure (quota_exhausted carve-out)** — the
   ONLY exception. When the summary could not be generated because
   the LLM call itself failed with a rate-limit / quota /
   `RESOURCE_EXHAUSTED` / HTTP 429 signal, the item DOES appear
   in-place in the main feed with the verbatim copy:
   `"The summary couldn't be generated this week."`
   These items had enough content to summarize and the next run is
   likely to succeed.

**Code anchors:**
- `pipeline/render/html._partition_cards()` — the single source of
  truth for routing.
- `pipeline/llm/summarize._classify_llm_exception()` — classifies
  Gemini errors into the `summary_status` taxonomy.
- `pipeline/render/html.QUOTA_BODY_COPY` — the locked exact-string
  for the carve-out body.
- `store/migrations/003_summary_status.sql` — schema column that
  carries the routing signal forward.

**Phase plans may refine:** the visual treatment of the footer (CSS,
ordering, grouping), the exact taxonomy of `summary_status` values,
the renderer's pipeline-notice copy.

**Phase plans must not:** route any non-quota_exhausted unsummarizable
item into the main feed; remove the footer; loosen the carve-out
beyond rate-limit / quota / 429 signals; reword the locked body copy
without an explicit unlock request.

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
