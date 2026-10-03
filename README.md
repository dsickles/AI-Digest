# Dan's Digest

A static site for Dan's weekly AI digest. The app is [Astro](https://astro.build/) with `output: 'static'`. Weekly files will live in `content/digests/`. This repository currently boots an empty shell so you can install and run it on your machine. No hosted platform is required.

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
content/digests/    Weekly digest files (empty)
content/reports/    Optional run reports (empty)
config/sources.yaml Checked-in source list
```

`config/sources.yaml` is the source registry. The site does not fetch those sources.
