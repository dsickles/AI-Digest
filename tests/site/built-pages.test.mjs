// Checks the built site in dist/. Run `pnpm build` first; `pnpm test` does both.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { parse as parseYaml } from 'yaml';
import { beforeAll, describe, expect, it } from 'vitest';
import { isPublishedWeek } from '../../src/lib/week-rules.mjs';
import { ROOT, latestWeek, readWeek, weekFiles } from '../helpers.mjs';

const DIST = join(ROOT, 'dist');
const SECTIONS = [
  { id: 'business', label: 'Business' },
  { id: 'technical', label: 'Technical' },
  { id: 'edtech', label: 'Education' },
  { id: 'policy-and-safety', label: 'Policy and Safety' },
];

function page(path) {
  const file = join(DIST, path, 'index.html');
  if (!existsSync(file)) throw new Error(`${path || '/'} was not built; run pnpm build first`);
  return readFileSync(file, 'utf8');
}

function shownCount(week, topic) {
  return (week.topics[topic] ?? []).filter((card) => card.included !== false && card.summary_status !== 'thin').length;
}

function weekLineWords(html) {
  const line = html.match(/<p class="bar week-line">([\s\S]*?)<\/p>/)?.[1] ?? '';
  return line
    .replace(/<[^>]+>/g, ' ')
    .split(/[\s·]+/)
    .filter((word) => ['Updated', 'About', 'Archive'].includes(word));
}

function meta(html, property) {
  return html.match(new RegExp(`<meta (?:property|name)="${property}" content="([^"]*)"`))?.[1];
}

const latest = latestWeek();
const pages = [
  ['Briefing', ''],
  ...SECTIONS.map((section) => [section.label, section.id]),
  ['Archive', 'archive'],
  ['How it works', 'about/how-it-works'],
  ['Sources', 'about/sources'],
];

beforeAll(() => {
  if (!existsSync(DIST)) throw new Error('dist/ is missing; run pnpm build first');
});

describe.each(pages)('%s page', (_name, path) => {
  it('has the week line in the order Updated, About, Archive', () => {
    expect(weekLineWords(page(path))).toEqual(['Updated', 'About', 'Archive']);
  });

  it('shows each section with the latest week story count, including Policy and Safety', () => {
    const html = page(path);
    for (const section of SECTIONS) {
      expect(html).toContain(`aria-label="${section.label} ${shownCount(latest, section.id)}"`);
    }
  });

  it('carries a link preview with an absolute image', () => {
    const html = page(path);
    expect(meta(html, 'og:image')).toBe('https://dans-ai-digest.vercel.app/share.png');
    expect(meta(html, 'og:title')).toBeTruthy();
    expect(meta(html, 'twitter:card')).toBe('summary_large_image');
  });
});

describe('Briefing', () => {
  it('shows the latest week and its Top 5 in file order', () => {
    const html = page('');
    expect(html).toContain(`href="/digest/${latest.week_id}"`);
    const positions = latest.briefing.top.map((card) => html.indexOf(`<article class="card" id="${card.id}"`));
    expect(positions.every((at) => at > -1)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
  });

  it('shares the week by its dates and lead', () => {
    const html = page('');
    expect(meta(html, 'og:title')).toMatch(/^Dan's AI Digest: Week of /);
    if (latest.briefing.lead) expect(html).toContain(`<meta property="og:description" content="${latest.briefing.lead.replaceAll('&', '&amp;')}"`);
  });
});

describe('each topic page', () => {
  it.each(SECTIONS)('$label lists every shown story in the latest week', (section) => {
    const html = page(section.id);
    const cards = (latest.topics[section.id] ?? []).filter(
      (card) => card.included !== false && card.summary_status !== 'thin',
    );
    for (const card of cards) expect(html).toContain(`id="${card.id}"`);
  });
});

describe('Archive', () => {
  it('links every published week', () => {
    const html = page('archive');
    const published = weekFiles()
      .map(readWeek)
      .filter((week) => isPublishedWeek(week, new Date()));
    expect(published.length).toBeGreaterThan(0);
    for (const week of published) expect(html).toContain(`href="/digest/${week.week_id}"`);
  });
});

describe('About', () => {
  it('Sources counts every enabled source in config/sources.yaml', () => {
    const config = parseYaml(readFileSync(join(ROOT, 'config', 'sources.yaml'), 'utf8'));
    const enabled = config.sources.filter((source) => source.enabled === true).length;
    expect(page('about/sources')).toContain(`<span class="tot">(${enabled})</span>`);
  });

  it('How it works states the latest week story count', () => {
    expect(page('about/how-it-works')).toContain(`${latest.main_feed.length} stories`);
  });

  it('How it works describes the Top 5 order the latest week uses', () => {
    const html = page('about/how-it-works');
    if (latest.briefing.ranking) expect(html).toContain('ranked by lasting importance');
    else expect(html).toContain('There is no rank order.');
  });
});
