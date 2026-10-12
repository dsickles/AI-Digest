# Story grouping

Ingest reads this file when it decides which included items are the same story. The site renders the week file. It does not group items again.

Group items that report the same story. Matching the URL is not enough. Two writeups of one launch, appointment, or finding are one story even when the headlines and URLs differ. A later piece that argues a different question stays its own item.

Run this after the inclusion rubric. Include or exclude each item first. Group only the included items. An excluded item stays in `excluded` and is not an "Also covered by" link.

## Pick the strongest source

Each group is one item. The main link is the strongest source:

1. A full card beats a thin link.
2. A piece about that story beats a roundup that mentions the story among others.
3. When several pieces are about the story, pick the one that states the key facts, including where the accounts disagree.

The main item keeps that source's title, url, publisher, category, summary, `takeaway`, and `include_reason`. It is listed in one section only.

## Also covered by

Put every other included source for that story on the main item as `also_covered`. Each entry has that source's `title`, `url`, and `publisher` (`source_id` and `name`, matching `config/sources.yaml`). Remove those sources from `topics`, `main_feed`, `briefing.top`, and `footer_aside`.

The site prints "Also covered by" and links each publisher name to that source's url.

A roundup joins the story it leads with. When the title gives real space to several stories, join the story that already has a dedicated item, so that story is not listed twice. One url belongs to one item. Do not attach the same source to a second story.

## When numbers disagree

If sources disagree on a key number, set `number_note` to one line that gives each figure and the publisher that reported it. Example: "722 per Education Disrupted, 719 per Last Week in AI". Write both figures. A short form of the publisher name is fine, such as "Education Disrupted" for "Education Disrupted (Stefan Bauschard)". The note must name at least two publishers on that item (the main publisher or an also covered publisher). The site shows the note on the item. Omit `number_note` when the sources agree, and omit it when the item has no `also_covered` source.

## Also seen

A thin item that is the same story as a main item becomes an `also_covered` link on that item. It does not also stay under Also seen. The same url must not appear both as a main item and as an Also seen link.

## For ingest

Weeks before `2026-W41`, including `2026-W40`, omit `also_covered` and `number_note`. Do not backfill them.

From `2026-W41` on, a story with one included source omits both fields. A story with several included sources sets `also_covered`. Set `number_note` only when those sources disagree on a key number.

`also_covered` is a non-empty list. Each entry is `{ "title", "url", "publisher": { "source_id", "name" } }`.

`number_note` is one line, no line break, at most 400 characters.

`main_feed` stays the concatenation of the topic lists. A `briefing.top` copy must match the main item, including `also_covered` and `number_note`.
