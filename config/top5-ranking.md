# Top 5 ranking

Swartz reads this file when ordering the Briefing Top 5. The site renders `briefing.top` in file order and shows each story's reason from `briefing.ranking`. It does not rank anything.

This file restates the ranking criteria from DAS-63. Swartz's own rubric (`top5-ranking-rubric.md`, Oct 14) replaces the tie-break section when it is added here.

## How to rank

Pick the five stories first, as today. Then score each one on three tests and sort by them in this order:

1. **Lasting importance, 0 to 3.** Will this still matter in a month?
   - 3: it changes what a lab, school, company, or government can do or must do.
   - 2: a major launch, finding, or policy move that others will build on or answer.
   - 1: worth knowing this week, but unlikely to come up again.
   - 0: interesting, with no lasting effect.
2. **Distinct sources, capped at 3.** The story's main publisher plus each different publisher in `also_covered`. A source counts once however many pieces it wrote. Four or more sources count as 3.
3. **Novelty, 0 to 2.**
   - 2: firsthand data: the source's own research, test results, filing, or survey.
   - 1: reported data: the source reports someone else's numbers or documents.
   - 0: commentary: argument or analysis with no new data.

A higher importance always wins. Sources break a tie on importance, and novelty breaks a tie on both.

## Tie-breaks

When two stories tie on all three tests, use the first of these that separates them:

1. The story that more of this week's themes link to.
2. The story that touches more readers: schools, jobs, or safety rules over a single company's product.
3. The earlier first publication date.

## For Swartz

`briefing.ranking` is optional for now. Weeks without it keep the old unranked Top 5, and the About page says so. Do not backfill earlier weeks.

When a week has it, write exactly one row per `briefing.top` card, in the same order as `briefing.top`. Row 1 is rank 1.

- `story_id`: the id of the `briefing.top` card at that rank.
- `importance`: 0 to 3.
- `sources`: the distinct source count, capped at 3. The validator recounts it from the card's `publisher` and `also_covered`, so it must match.
- `novelty`: 0 to 2.
- `reason`: one sentence of 25 words or fewer that a reader sees under the story. Say why it sits where it does, not what it says. No em dash or en dash.

```json
{
  "ranking": [
    {
      "story_id": "epoch-ai-can-ai-automate-ai-r-d-yet",
      "importance": 3,
      "sources": 1,
      "novelty": 2,
      "reason": "Firsthand test results on the question labs are betting on: whether AI can do AI research without people."
    }
  ]
}
```

The validator fails a week when a row names a different story than `briefing.top` at that position, when a lower-scored story sits above a higher-scored one, or when the source count is wrong. It does not check the tie-breaks, which are judgment.
