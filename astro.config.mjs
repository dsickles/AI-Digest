import { defineConfig } from 'astro/config';

// Static HTML in `dist/`. Vercel’s Astro preset serves that directory with no adapter and no vercel.json.
export default defineConfig({
  output: 'static',
});
