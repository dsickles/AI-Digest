# Dan's AI Digest

A **personal weekly AI reading site**: one finished week at a time, with a short Briefing, topic lists you can skim, and an archive of past weeks. Think a quiet newsletter homepage you own, not a firehose and not a SaaS product.

You open the site to read. Editors (or bots) ship each week as a file in this repo. The site builds from those files. It does not fetch the live web, call an LLM, or talk to a database when someone visits.

**Live site:** https://dans-ai-digest.vercel.app

## Why it exists

| Intent | Meaning |
|--------|---------|
| One week, done | Sunday through Saturday (America/New_York). Only a finished week appears on the home page. |
| Briefing first | A short synthesis and a Top 5, not every link in one pile. |
| Topics for skim | Business, Technical, Education, and Policy and Safety each get their own list. |
| Thin items aside | Quick mentions live under Also seen this week on Briefing only, not in the main topic lists. |
| Own the archive | Past weeks stay readable from the Archive control on the week line. |

## What you get

- A **Briefing** page: the week's synthesis and Top 5
- **Topic tabs** in this order: Business, Technical, Education, Policy and Safety
- **Also seen this week** on Briefing (including an archived briefing), omitted when that week has nothing thin to show
- An **Archive** of past weeks, each with a Read this week link
- Week content checked into git under `content/digests/`
- A static site anyone can open without an account or PIN

## Reading a week

Open the live site (or your local copy). You land on the latest finished week's Briefing.

- **Read the Briefing.** Synthesis at the top, Top 5 under it. If the week has thin items, Also seen this week lists them as links without summaries.
- **Skim a topic.** Use Business, Technical, Education, or Policy and Safety. Each page shows that topic's main list in file order. An empty topic still appears and says so.
- **Open a story.** The title is the link to the article. Where a Summary control exists, it expands or collapses the summary without leaving the page. Top 5 rows stay open. Video items show a play control on the row.
- **Browse the archive.** Archive sits on the week line next to Updated, not in the topic row. Open a past week with Read this week.

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
5. Click around using **Reading a week**. Topic tabs and Archive should match the description above.
6. Optional production-shaped build (still local):

   ```bash
   pnpm build
   pnpm preview
   ```

   Open [http://localhost:4321](http://localhost:4321) again. Same site, served from `dist/`.

## How a week lands in the site

Each week is one JSON file: `content/digests/{week_id}.json` (for example `2026-W40.json`). That file holds the Briefing, Top 5, topic lists, and Also seen links. The schema is `schema/digest.schema.json`. Extra structural checks live in `scripts/validate-weeks.mjs`.

Optional ops notes can sit beside a week as `content/reports/{week_id}.json`. A missing report is fine.

Before you trust a change:

```bash
pnpm validate:weeks
pnpm validate:weeks:self-test
pnpm build
pnpm check:reader
```

`pnpm check:reader` reads the built `dist/` folder and checks that Briefing, topics, Also seen rules, and Archive links match the committed week.

The checked-in source list is `config/sources.yaml`. The site does not fetch those sources when someone visits; it only renders the week files.

## Deploy on Vercel

The public address is https://dans-ai-digest.vercel.app. Do not create or point this project at a different hostname without confirming that URL first.

This is a static Astro site. In the Vercel project:

- Framework Preset: **Astro**
- Output Directory: **`dist`**
- Build Command: `pnpm build`

Do not add `vercel.json`, a Vercel adapter, or environment variables for reading weeks. The preset serves `dist/` as static files.

## Stack

Astro (static output), week JSON in git, JSON Schema plus `validate:weeks` / `check:reader` scripts. No LLM, Gemini, Python, or SQLite in the site path.
