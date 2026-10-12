# Takeaway and summary length

Ingest reads this file when it writes each main item. The site renders the week file. It does not invent a takeaway.

From `2026-W41` on, every main item has a `takeaway`. Weeks before `2026-W41`, including `2026-W40`, omit it. Do not backfill those weeks. Thin Also seen items omit it too. An excluded item is not a main item and does not need one.

## Takeaway

`takeaway` is one sentence saying why it matters. It is the line a reader sees under the title while Summary is closed. Do not write a second sentence. End with `.`, `!`, or `?`. The first sentence must be the whole string, so do not put a period in the middle (write "US", not "U.S.").

Do not restate the title. The title already says what the piece is called. The takeaway says why a reader should care.

Write it only from that item's summary and source. Do not invent facts, numbers, or names. On a merged story, use the main item's summary. Do not add a claim that appears only in an Also covered source unless that claim is already in the summary.

Write the takeaway without an em dash or an en dash.

## Summary length

From `2026-W41` on, an ok summary is at most 60 words, counted as whitespace-separated words. Keep the facts that carry the story, including the numbers and names a reader needs, and cut the rest. Do not add facts to make the shorter summary flow. Write it without an em dash or an en dash.

Weeks before `2026-W41` may keep a longer summary.

A degraded main item has no summary. It still needs a takeaway from `2026-W41` on, written from the source, with no invented facts.

## For ingest

From `2026-W41` on, each main item keeps its summary and adds:

```json
{
  "takeaway": "One sentence on why this story matters."
}
```

Put `takeaway` on the main item in `topics`, `main_feed`, and `briefing.top`. Those copies must match. Do not put `takeaway` on an Also seen link.
