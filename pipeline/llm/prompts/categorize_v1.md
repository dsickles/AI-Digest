---
prompt_version: categorize_v1
phase: 3
purpose: Per-cluster category classification for AI Digest
---

# Categorize one story cluster — v1

You classify a single story for a personal weekly AI digest. Each story belongs
in exactly one category based on its content.

## Categories (choose exactly one)

- **edtech** — education, learning, schools, students, teaching with AI
- **business** — companies, markets, strategy, policy, industry moves
- **technical** — engineering, models, tools, research, developer practice,
  UX/product/design tooling, creative tools

## Output schema

Return JSON matching this shape exactly:

```json
{
  "category": "edtech | business | technical",
  "confidence": 0.0
}
```

``confidence`` is optional (0–1) when you are uncertain.

## Rules

1. **Classify from the story content** — title and summary below. Do not invent
   facts not present in the input.
2. When ``source_typically_covers`` is provided, treat it as a **soft hint**
   about the publisher's usual beat — not a hard constraint. The story's
   subject matter wins when it clearly differs from the source's typical coverage.
3. Do **not** use community or crowd framing (no "trending", "discussed on",
   "widely shared"). Name entities and events from the text only.
4. Return **exactly one** category enum value — no secondary labels.

## Input

Title: {{title}}

Summary:
{{summary_text}}

{{source_hint}}
