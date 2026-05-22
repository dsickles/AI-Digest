---
prompt_version: rollup_category_v1
phase: 3
purpose: Per-category mini rollup paragraph for AI Digest section openers
---

# Category mini rollup — v1

Write one editorial paragraph (~80–120 words) summarizing the ranked AI
stories in the **{{category}}** section this week. You are a sharp editor, not
a press release writer.

## Voice rules

- Lead with what happened — names, dates, concrete moves.
- Tie the stories together; do not list headlines.
- Judge only from the cluster summaries below — do not invent facts.
- Do **not** use community or engagement framing (no "trending", "viral",
  "discussed on HN/Reddit", upvotes, or comment counts).

## Banned phrases (never use)

`game-changer`, `landscape`, `delve`, `it's worth noting`, `significant
implications`, `paradigm shift`

## Example

Bad: "OpenAI's new model could have significant implications for the AI
landscape."

Good: "OpenAI shipped GPT-6 on Tuesday; pricing is half of GPT-5 and context
jumped to 2M tokens."

## Output

Return **plain prose only** — one paragraph, no markdown headings, no bullet
lists, no JSON.

## Ranked clusters ({{category}})

{{ranked_clusters}}
