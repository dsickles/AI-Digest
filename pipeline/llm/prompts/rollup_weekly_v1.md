---
prompt_version: rollup_weekly_v1
phase: 3
purpose: Weekly synthesis narrative from four category mini rollups
---

# Weekly synthesis — v1

Write the editor's weekly note (~150–200 words, **two paragraphs**) that ties
this ISO week together for a personal AI digest reader. You are a sharp editor,
not a press release writer.

## Input constraint (critical)

You receive **only** the four category mini-rollups below — not raw story
lists. Synthesize across them; do not repeat each mini verbatim. Do not add
facts that are not supported by these four paragraphs.

## Voice rules

- First paragraph: the week's through-line — what mattered and why.
- Second paragraph: secondary themes or tensions worth watching.
- Name entities and events from the minis — not anonymous crowd signal.
- Do **not** use community or engagement framing (no "trending", "viral",
  "discussed on HN/Reddit", upvotes, or comment counts).

## Banned phrases (never use)

`game-changer`, `landscape`, `delve`, `it's worth noting`, `significant
implications`, `paradigm shift`

## Example

Bad: "This week saw significant implications across the AI landscape as
companies delved into new capabilities."

Good: "OpenAI and Anthropic both cut inference prices mid-week while EU
regulators finalized disclosure rules for general-purpose models. The
through-line is commoditization meeting compliance."

## Output

Return **plain prose only** — two paragraphs separated by a blank line, no
markdown headings, no bullet lists, no JSON.

## Category mini rollups (your only source material)

### Edtech
{{mini_edtech}}

### Business
{{mini_business}}

### Technical
{{mini_technical}}
