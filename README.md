# Dan's Digest

A static site for Dan's weekly AI digest. The app is [Astro](https://astro.build/) with `output: 'static'`. Weekly files live in `content/digests/`. This repository currently boots an empty shell so you can install and run it on your machine. The shell does not render a week yet. No hosted platform is required.

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

Open [http://localhost:4321](http://localhost:4321). The page title is **Dan's Digest** and the digest section is empty.

## Static build

```bash
pnpm build
pnpm preview
```

`pnpm build` writes the site to `dist/`. `pnpm preview` serves that folder locally, again at [http://localhost:4321](http://localhost:4321).

## Layout

```
src/pages/          Astro pages (blank shell)
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
