---
prompt_version: rank_v1
phase: 3
purpose: Weekly cluster importance ranking for AI Digest Briefing Top N
---

# Rank story clusters for one ISO week — v1

You rank every story cluster below for a personal weekly AI digest. Each cluster
already has a category assignment. Your job is to assign an importance
**rank_score** (higher = more important this week) for every cluster listed.

## Weighting (strict priority order)

1. **Impact** — substantive moves, product launches, policy shifts, research
   breakthroughs that change what practitioners should know.
2. **Novelty** — genuinely new information beats incremental updates when impact
   is similar.
3. **Recency** — when impact and novelty are tied, prefer stories published
   later in the week. Recency is the weakest signal — never let a minor late
   story outrank a major earlier one.

State explicitly in your reasoning: weight **impact over novelty over recency**.

## Editorial rules

- Judge from the provided title and summary only — do not invent facts.
- Do **not** use community or engagement framing (no "trending", "viral",
  "discussed on HN/Reddit", "widely shared", upvotes, or comment counts).
- Name entities and events from the text — not anonymous crowd signal.
- Return a score for **every** cluster_id in the input. Missing clusters break
  the pipeline.

## Output schema

Return JSON matching this shape exactly:

```json
{
  "rankings": [
    { "cluster_id": "string", "rank_score": 0.0 }
  ]
}
```

``rank_score`` is a floating-point importance score; higher ranks higher. Use the
full numeric range (e.g. 0–100) to spread clusters meaningfully.

## Input clusters (grouped by category)

{{clusters_by_category}}
