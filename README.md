# Dan's Digest

A static site for Dan's weekly AI digest. The app is [Astro](https://astro.build/) with `output: 'static'`. Weekly files live in `content/digests/`. The site reads those files at build time and renders the latest week whose Saturday 23:59:59 America/New_York has already passed. A later file for a week that is still open, including a half-finished draft, stays off the home page and the archive. No LLM, Gemini, Python, or SQLite runs at build or serve time.

## Prerequisites

- [Node.js](https://nodejs.org/) **22.12** or newer
- [pnpm](https://pnpm.io/) **10** (this repo pins `packageManager` to pnpm 10.33.3)

Enable Corepack if `pnpm` is not already on your PATH:

```bash
corepack enable
corepack prepare pnpm@10.33.3 --activate
```

## Install and start

From the repository root:

```bash
pnpm install
pnpm dev
```

Open [http://localhost:4321](http://localhost:4321). That is the latest week’s Briefing. With the checked-in file, the week is **2026-W40**.

- **Briefing** shows the synthesis and the Top 5 only.
- **Education**, **Business**, **Technical**, and **Policy and Safety** stay in the nav and show that topic’s main list in file order. An empty topic stays on the nav and says so.
- **Education** is empty in the checked-in week and says so. **Policy and Safety** is empty there too. A degraded card, when a week has one, uses exactly `The summary couldn't be generated this week.`
- **Also seen this week**, under the lists, is the thin footer link with no summary. The checked-in week has one, the Simon Willison sponsors newsletter.
- **Archive** shows an excerpt and a **Read this week** link to `/digest/2026-W40`.

## Static build

```bash
pnpm build
pnpm preview
```

`pnpm build` writes the site to `dist/`. `pnpm preview` serves that folder locally, again at [http://localhost:4321](http://localhost:4321).

## Layout

```
src/pages/          Briefing, topic tabs, week permalinks, archive
public/             Static assets copied as-is
content/digests/    Week files, `content/digests/{week_id}.json`
content/reports/    Optional ops reports, `content/reports/{week_id}.json`
config/sources.yaml Checked-in source list
schema/             JSON Schema for week files and optional reports
```

`config/sources.yaml` is the source registry. The site does not fetch those sources.

## Week files

`content/digests/{week_id}.json` is the week: metadata, Briefing synthesis plus Top 5, per-topic main lists, `main_feed`, and a thin-link `footer_aside`. The schema is `schema/digest.schema.json`. Structural rules that JSON Schema cannot express (the Sunday–Saturday America/New_York window, source ids, and list equality) live in `scripts/validate-weeks.mjs`.

`content/reports/{week_id}.json` is optional. A missing report does not fail the check. When a report is present, `schema/report.schema.json` applies.

Run the same checks as schema CI:

```bash
pnpm validate:weeks
pnpm validate:weeks:self-test
```

`pnpm validate:weeks` checks the committed week files and passes a tree that has no report. `pnpm validate:weeks:self-test` does that, then writes a temporary invalid week, expects the checker to reject it, and deletes the temp file. Nothing under `content/` is left invalid.

After `pnpm build`, `pnpm check:reader` reads `dist/` and checks the committed week: file order, Top 5 only, the thin footer item, archive’s **Read this week** link, and the absence of status chrome. A degraded card is not required in the committed week. When one is present, its summary is the locked sentence. The reader fixture covers that sentence.

## Deploy on Vercel

This is a static Astro site. Do not add `vercel.json`, a Vercel adapter, or environment variables for the reader.

In the Vercel project settings:

- Framework Preset: **Astro**
- Output Directory: **`dist`**
- Build Command: `pnpm build` (the Astro preset’s `astro build` writes the same `dist/` directory)

`astro.config.mjs` sets `output: 'static'`. The preset serves `dist/` as static files.
