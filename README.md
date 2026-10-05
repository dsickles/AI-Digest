# Dan's AI Digest

A static weekly AI digest site. Built with [Astro](https://astro.build/) (`output: 'static'`). Week content lives in `content/digests/` as JSON. The site reads those files at build time and shows the latest week whose Saturday 23:59:59 America/New_York has already passed. A later file for a week that is still open, including a half-finished draft, stays off the home page and the archive. No LLM, database, or Python runs at build or serve time.

Live site: [https://dans-ai-digest.vercel.app](https://dans-ai-digest.vercel.app)

## Prerequisites

- [Node.js](https://nodejs.org/) **22.12** or newer
- [pnpm](https://pnpm.io/) **10** (this repo pins `packageManager` to pnpm 10.33.3)

If `pnpm` is not on your PATH:

```bash
corepack enable
corepack prepare pnpm@10.33.3 --activate
```

## Install and run locally

From the repository root:

```bash
pnpm install
pnpm dev
```

Open [http://localhost:4321](http://localhost:4321). That is the latest week's Briefing.

What you should see:

- **Briefing**: synthesis and Top 5 only. When the week has thin items, **Also seen this week** appears here (and on an archived briefing). When there are none, that heading is omitted. Topic pages never show Also seen.
- **Topic tabs** (in order): Business, Technical, Education, Policy and safety. Each shows that topic's main list in file order. An empty topic stays in the nav and says so.
- **Archive**: sits on the week line (next to Updated), not in the topic row. Archive lists past weeks with a **Read this week** link (for example `/digest/2026-W40`).

## Static build

```bash
pnpm build
pnpm preview
```

`pnpm build` writes the site to `dist/`. `pnpm preview` serves that folder locally at [http://localhost:4321](http://localhost:4321).

## Layout

```
src/pages/          Briefing, topic tabs, week permalinks, archive
public/             Static assets copied as-is
content/digests/    Week files: content/digests/{week_id}.json
content/reports/    Optional ops reports: content/reports/{week_id}.json
config/sources.yaml Checked-in source list (the site does not fetch these)
schema/             JSON Schema for week files and optional reports
```

## Week files

`content/digests/{week_id}.json` is one week: metadata, Briefing synthesis plus Top 5, per-topic main lists, `main_feed`, and a thin-link `footer_aside`. The schema is `schema/digest.schema.json`. Rules JSON Schema cannot express (the Sunday-Saturday America/New_York window, source ids, list equality) live in `scripts/validate-weeks.mjs`.

`content/reports/{week_id}.json` is optional. A missing report does not fail the check. When a report is present, `schema/report.schema.json` applies.

Same checks as schema CI:

```bash
pnpm validate:weeks
pnpm validate:weeks:self-test
```

`pnpm validate:weeks` checks the committed week files. `pnpm validate:weeks:self-test` does that, then writes a temporary invalid week, expects the checker to reject it, and deletes the temp file. Nothing under `content/` is left invalid.

After `pnpm build`, `pnpm check:reader` reads `dist/` and checks the committed week: file order, Top 5 only, Also seen rules, archive **Read this week** link, and the absence of status chrome. A degraded card is not required in the committed week. When one is present, its summary is exactly `The summary couldn't be generated this week.`

## Deploy on Vercel

Public address: [https://dans-ai-digest.vercel.app](https://dans-ai-digest.vercel.app)

This is a static Astro site. Do not add `vercel.json`, a Vercel adapter, or environment variables for the reader.

In the Vercel project settings:

- Framework Preset: **Astro**
- Output Directory: **`dist`**
- Build Command: `pnpm build` (the Astro preset's `astro build` writes the same `dist/` directory)

`astro.config.mjs` sets `output: 'static'`. The preset serves `dist/` as static files.
