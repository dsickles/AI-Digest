# Inclusion rubric

Dan can edit the criteria in this file. Ingest reads the file when it decides which items make the digest. The site renders the week file. It does not score items again.

There is no per-source item cap. A source can contribute as many items as pass this rubric.

## Include an item if it meets at least one

- **New:** a launch, a finding, a policy move, or real data.
- **Argued:** a real argument or analysis, not just a pointer to someone else's.
- **Relevant:** it touches a theme from this week or a running story.

## Leave these out

- Shorts with no substance.
- Quotes with no commentary.
- Minor version releases.

Version bumps and quote-only posts are excluded. They do not appear in Also seen.

## Thin summaries

Summaries written only from a video description are marked thin. They appear as links under Also seen this week, on Briefing only. They are not full cards on Briefing or on a topic page.

A feed item with no article body is the same kind of link.

## For ingest

This section is the contract for the week file. The criteria above can change. These fields stay.

From week `2026-W41` on, every item records:

- `included`: `true` or `false`
- `include_reason`: one line, no line break, at most 240 characters, saying why

Weeks before `2026-W41`, including `2026-W40`, stay valid without these fields. Do not backfill them unless you are rewriting that week.

Put included items in the lists the site renders:

- Full cards (`summary_status` `ok`, or an in-place degraded card) go in `topics`, `main_feed`, and, for the five best, `briefing.top`.
- Thin items (`summary_status` `thin`, no summary and no body) go in `footer_aside` only. A YouTube item can be thin. Its `media` stays `video`. Also seen shows a play icon on those links.

Put excluded items only in `excluded`. Set `included` to `false`. Keep the rest of the card, including a summary if one was written, so the reason can be checked later. Do not also place them in `topics`, `main_feed`, `briefing.top`, or `footer_aside`.

`excluded` is required from `2026-W41` on, even when nothing was excluded. `main_feed` stays the concatenation of the topic lists. Each `briefing.top` card must match the same id in `main_feed`, including `included` and `include_reason`.

Do not cap how many items a source can contribute. Do not drop a later item because that source already has one.

## Same story, several sources

Grouping is a separate step from this rubric. Read `config/story-grouping.md`. Include or exclude each item first. Then group the included items that are the same story. Grouping does not put an excluded item back on the page.
