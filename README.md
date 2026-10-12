# Dan's AI Digest

A **personal weekly AI reading site**: one finished week at a time, with a short Briefing, topic lists you can skim, and an archive of past weeks. Think a quiet newsletter homepage you own, not a firehose and not a SaaS product.

You open the site to read. Editors (or bots) ship each week as a file in this repo. The site builds from those files. It does not fetch the live web, call an LLM, or talk to a database when someone visits.

**Live site:** https://dans-ai-digest.vercel.app

## Why it exists

| Intent | Meaning |
|--------|---------|
| One week, done | Sunday through Saturday (America/New_York). Only a finished week appears on the home page. |
| Briefing first | A short lead, the Number of the week, five themes, and the Top 5. No wall of text. |
| Topics for skim | Business, Technical, Education, and Policy and Safety each get their own list, with quick mentions under Also seen at the bottom. |
| Own the archive | Past weeks stay readable from the Archive control on the week line. |
| Every source listed | A Sources page lists all 33 feeds the digest reads, by section, with how many items each gave this week. |

## What you get

- A **Briefing** page: a lead of one to three sentences, then the Number of the week, then This week's themes (always five) in the left column, with the Top 5 in the wider right column. The number sits in that left column, under the lead and above the themes. On a phone: lead, number, themes, Top 5.
- **Topic tabs**: Business, Technical, Education, Policy and Safety. Each ends with Also seen when that topic has thin items.
- A **Sources** page at `/sources`, linked from the week line (Sources · Archive). The heading is Sources (33). A note names the week, at the right of the heading on a desktop and under the heading on a phone. Each row shows "N this week" or "None this week".
- An **Archive** of past weeks, each with a Read this week link. Weeks from before the redesign still show their briefing paragraph.
- A site icon for browser tabs and the phone home screen.
- Week content checked into git under `content/digests/`
- A static site anyone can open without an account or PIN

## Reading a week

Open the live site (or your local copy). You land on the latest finished week's Briefing.

- **Read the Briefing.** The lead sums up the week. The Number of the week is one figure with what was measured, why it matters, and a link to its story. Each theme is one sentence with links to the stories behind it. The Top 5 sits beside them. On a phone the order is lead, number, themes, Top 5. A week from before the redesign shows its briefing paragraph instead.
- **Skim a topic.** Use Business, Technical, Education, or Policy and Safety. Each page shows that topic's main list in file order. Thin links, when that topic has them, sit at the bottom under Also seen. An empty topic still appears and says so. The tab count is the main list only.
- **Open a story.** The title is the link to the article. A one-line takeaway under the title says why it matters, and it stays visible while Summary is closed. Where a Summary control exists, it expands or collapses the shorter summary without leaving the page. Top 5 rows stay open, with the takeaway above the summary. Video items show a play control on the row.
- **Browse the archive.** Archive is the far-right link on the week line, after Sources, and it is not in the topic row. Open a past week with Read this week.
- **See every source.** The week line reads Updated · Sources · Archive. The heading is Sources (33). A note names the week, at the right of the heading on a desktop and under the heading on a phone. Each row shows "N this week" or "None this week".

A week that is still open (including a half-finished draft file) stays off the home page and out of the archive until its Saturday 23:59:59 America/New_York has passed.

## Try it on your computer

You run a local copy to read the checked-in week the same way the live site does. No account, no PIN, no calendar of your own to connect.

1. Install **Node.js 22.12 or newer** from [nodejs.org](https://nodejs.org). Close and reopen your terminal after the installer finishes.
2. Check versions: `node -v` should be `v22.12` or higher. This repo uses **pnpm 10**. If `pnpm -v` is missing:

   ```bash
   corepack enable
   corepack prepare pnpm@10.33.3 --activate
   ```

3. Download the project and open its folder:

   ```bash
   git clone https://github.com/dsickles/AI-Digest.git
   cd AI-Digest
   ```

   You are in the right place when the folder contains `package.json`.
4. Install and start:

   ```bash
   pnpm install
   pnpm dev
   ```

   Leave that terminal open. Open [http://localhost:4321](http://localhost:4321). You should see the latest finished week's Briefing.
5. Click around using **Reading a week**. Topic tabs, Archive, and Sources should match the description above.
6. Optional production-shaped build (still local):

   ```bash
   pnpm build
   pnpm preview
   ```

   Open [http://localhost:4321](http://localhost:4321) again. Same site, served from `dist/`.

## How a week lands in the site

Each week is one JSON file: `content/digests/{week_id}.json` (for example `2026-W40.json`). That file holds the Briefing, Top 5, topic lists, and the Also seen links for those topic tabs. The schema is `schema/digest.schema.json`. Extra structural checks live in `scripts/validate-weeks.mjs`.

What gets into a week is decided before the file is written. The rules Dan can edit are in `config/inclusion-rubric.md`. Ingest should read that file. There is no cap on how many items can come from one source.

From `2026-W41` on, every item has `included` (`true` or `false`) and a one-line `include_reason`. Items that fail the rubric are listed in `excluded` and are not rendered. They do not count toward the section tabs. Thin items, including a video whose summary was written only from the description, render as Also seen links at the bottom of their topic tab. Those links do not count toward the section tabs either. `2026-W40` and earlier weeks omit these fields and stay valid.

Items about the same story are one item, even when the URLs differ. Ingest follows `config/story-grouping.md`. The strongest source is the main link. The other sources show on that item as "Also covered by" links with publisher names. When those sources disagree on a key number, the item says so (for example "722 per Education Disrupted, 719 per Last Week in AI"). A story does not appear both as a main item and as an Also seen link. `2026-W40` omits `also_covered` and `number_note` and stays valid.

From `2026-W41` on, the Briefing also carries `lead` (1 to 3 sentences) and `themes` (exactly 5 rows). Each theme has a short `label`, one `sentence` of 25 to 35 words, and `story_ids` pointing at the merged main items. Ingest follows `config/briefing.md`. The page does not render the synthesis paragraph. `2026-W40` omits `lead` and `themes` and the page keeps that paragraph. The archive excerpt still uses the first sentence of `synthesis`.

From `2026-W42` on, the Briefing also carries `number_of_week`: a short `value`, one plain-English `what` sentence, one plain-English `why` sentence, and a `story_id` for an item in the week. Swartz follows `config/number-of-week.md`. The page shows the value, then those two sentences, then a link to that story, in the left column under the lead and above the themes. On a phone the order is lead, Number of the week, themes, Top 5. `2026-W41` and earlier, including `2026-W40`, stay valid without the field and show no empty slot.

From `2026-W41` on, every main item also has a `takeaway`: one sentence on why it matters, not a restatement of the title. The page shows that line under the title and meta line, on Top 5 and on every topic page, including while Summary is closed. An opened summary is 60 words or fewer. Ingest follows `config/takeaway.md`. Thin Also seen items omit `takeaway`. `2026-W40` omits it, can keep a longer summary, and still renders.

Optional ops notes can sit beside a week as `content/reports/{week_id}.json`. A missing report is fine.

Before you trust a change:

```bash
pnpm validate:weeks
pnpm validate:weeks:self-test
pnpm build
pnpm check:reader
```

`pnpm check:reader` reads the built `dist/` folder and checks that Briefing, topics, takeaways, the Number of the week, Also seen rules, Archive links, and the Sources page (heading count, week note, and each source's count) match the committed week and `config/sources.yaml`.

The Sources page reads `config/sources.yaml` at build time, so adding or removing a source there updates the page on the next build. Today it lists 33: Business 8, Technical 9, Education 9, Policy and Safety 7. The heading is Sources (33). A note names the week, at the right of the heading on a desktop and under the heading on a phone. Each row shows "N this week" or "None this week". Within a section, names are sorted alphabetically, and a leading "The" is ignored. Counts come from the current week file, so a row that says "None this week" had nothing that made the cut that week. The site does not fetch those sources when someone visits; it only renders the week files.

## What makes the cut

Ingest follows editable files in `config/`. `config/inclusion-rubric.md` decides what gets in: an item must be new, argued, or relevant, with no cap per source. `config/story-grouping.md` merges coverage of the same story into one item with Also covered by links, and flags numbers that disagree. `config/briefing.md` sets the lead and the five themes. `config/number-of-week.md` sets the Number of the week rubric. The five tests are: it changes the picture (it shifts what a reader believes, beyond a big headline figure), it is firsthand (from the source's own research, data, or filing), it has something to compare against (such as last year, humans, or a target), it is about something real (money, schools, safety, jobs, or policy), and it is new this week and will still matter in a month. Items with a real summary go in the topic lists, and thin items that still pass go to that tab's Also seen. A main item whose summary could not be generated stays in the topic list too.

## Deploy on Vercel

The public address is https://dans-ai-digest.vercel.app. Do not create or point this project at a different hostname without confirming that URL first.

This is a static Astro site. In the Vercel project:

- Framework Preset: **Astro**
- Output Directory: **`dist`**
- Build Command: `pnpm build`

Do not add `vercel.json`, a Vercel adapter, or environment variables for reading weeks. The preset serves `dist/` as static files.

## Stack

Astro (static output), week JSON in git, JSON Schema plus `validate:weeks` / `check:reader` scripts. No LLM, Gemini, Python, or SQLite in the site path.
