# Briefing lead and themes

Ingest reads this file when it writes the Briefing scan line. The site renders the week file. It does not invent a lead or themes.

The synthesis paragraph stays in the file. From `2026-W41` on, the page leads with one sentence and short theme rows. The paragraph sits behind "Read the full briefing". Weeks before `2026-W41`, including `2026-W40`, omit `lead` and `themes`. The site then shows the synthesis paragraph, as it does today. Do not backfill those weeks.

## Lead

`briefing.lead` is one sentence. It is the line Dan reads first. Do not write a second sentence. End with `.`, `!`, or `?`. The first sentence must be the whole string, so do not put a period in the middle (write "US", not "U.S.").

## Themes

`briefing.themes` is a list of 4 to 6 themes. Each theme is one row:

- `label`: a short label, at most 4 words and 32 characters. Not a sentence. No period.
- `sentence`: one sentence of 25 to 35 words, counted as whitespace-separated words. Same one-sentence rule as the lead.
- `story_ids`: the item ids for that theme. Each id is the merged main item in `main_feed` (the strongest source after `config/story-grouping.md`). One id per story.

Link the group's main item only. Do not link an `also_covered` source, an excluded item, or an Also seen item as if it were a second copy. Do not list the same id twice in one theme. Do not list two ids that share a url, including a url already on the main item as `also_covered`. A story may appear in more than one theme. Each of those rows still links the same main id.

Set `lead` and `themes` together. A week that has one and not the other is invalid.

Write the label, the sentence, and the lead without an em dash or an en dash.

## For ingest

From `2026-W41` on, `briefing` keeps `synthesis` and `top`, and adds:

```json
{
  "lead": "One sentence for the week.",
  "themes": [
    {
      "label": "Agents",
      "sentence": "Twenty five to thirty five words in a single sentence that names the merged stories and nothing that is not in the week file at all.",
      "story_ids": ["main-item-id"]
    }
  ]
}
```

`story_ids` entries match `id` on a `main_feed` card. A `briefing.top` card is a copy of that same card, so link the id once. The site points a Top 5 id at that story on the Briefing page and any other id at the story on its topic page.
