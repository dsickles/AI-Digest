# Number of the week

Swartz reads this file when picking the Briefing number. The site renders `briefing.number_of_week`. It does not pick a number.

Candidate numbers come from that week's in-window pieces. Score each candidate on these five tests:

1. It changes the picture. It shifts what a reader believes, beyond just being a big headline figure.
2. It's firsthand, from the source's own research, data, or filing.
3. It has something to compare against, such as last year, humans, or a target.
4. It's about something real: money, schools, safety, jobs, or policy.
5. It's new this week and will still matter in a month.

Pick the candidate that passes the most tests. Write the figure, the what line, and the why line without an em dash or an en dash.

## For Swartz

From `2026-W42` on, `briefing.number_of_week` is required. `2026-W41` and earlier, including `2026-W40`, stay valid without it. Do not backfill those weeks.

Write four fields:

- `value`: a short figure, for example "15%". Not a sentence. At most 24 characters.
- `what`: one plain-English sentence on what was measured.
- `why`: one plain-English sentence on why it matters to a non-expert.
- `story_id`: the item id in the week. It must be the merged main item in `main_feed`. The Briefing links that story.

```json
{
  "number_of_week": {
    "value": "15%",
    "what": "Epoch AI asked top AI systems to rediscover a recent research breakthrough on their own, and they captured only 15% of the improvement the human researchers got.",
    "why": "AI isn't close to doing AI research without people, which is the leap labs are betting on.",
    "story_id": "epoch-ai-can-ai-automate-ai-r-d-yet"
  }
}
```

The page shows the value large, then the what line, then the why line, then a source line for that story. It does not show a technical caption. A week that omits the field shows no empty slot.
