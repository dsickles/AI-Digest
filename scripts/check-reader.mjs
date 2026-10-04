import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const DEGRADED_BODY = "The summary couldn't be generated this week.";
const WEEK_ID = '2026-W40';
const DIST = 'dist';

const week = JSON.parse(readFileSync(`content/digests/${WEEK_ID}.json`, 'utf8'));

function fail(message) {
  throw new Error(message);
}

function decode(value) {
  return value
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(Number(code)))
    .replace(/&#x([0-9a-f]+);/gi, (_, code) => String.fromCharCode(parseInt(code, 16)))
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
}

function walk(dir) {
  const files = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) files.push(...walk(path));
    else if (name.endsWith('.html')) files.push(path);
  }
  return files;
}

function readPage(path) {
  try {
    return readFileSync(join(DIST, path), 'utf8');
  } catch (error) {
    fail(`missing ${join(DIST, path)} (${error.message})`);
  }
}

function extractArticle(html, id) {
  const match = html.match(new RegExp(`<article\\b[^>]*\\bid="${id}"[^>]*>[\\s\\S]*?</article>`));
  if (!match) fail(`missing article ${id}`);
  return match[0];
}

function articleIds(html, className) {
  const ids = [];
  for (const match of html.matchAll(/<article\b([^>]*)>/g)) {
    const attrs = match[1];
    const classMatch = attrs.match(/class="([^"]*)"/);
    const idMatch = attrs.match(/\bid="([^"]*)"/);
    if (!classMatch || !idMatch) continue;
    if (classMatch[1].split(/\s+/).includes(className)) ids.push(idMatch[1]);
  }
  return ids;
}

function splitFooter(html) {
  const marker = '<aside id="also-seen"';
  const index = html.indexOf(marker);
  if (index === -1) return { main: html, footer: '' };
  return { main: html.slice(0, index), footer: html.slice(index) };
}

function summaries(article) {
  return [...article.matchAll(/<p class="summary">([^<]*)<\/p>/g)].map((match) => decode(match[1]).trim());
}

function assertCard(html, card) {
  const article = extractArticle(html, card.id);
  if (!article.includes(`href="${card.url}"`)) fail(`${card.id} is missing its outbound link`);
  if (!article.includes('target="_blank"') || !article.includes('rel="noopener noreferrer"')) {
    fail(`${card.id} outbound link is missing target or rel`);
  }
  if (!decode(article).includes(card.title)) fail(`${card.id} is missing its title`);
  if (!decode(article).includes(card.publisher.name)) fail(`${card.id} is missing its publisher`);
  if (!article.includes(`datetime="${card.published_at}"`)) fail(`${card.id} is missing its date`);
  const summarySlot = summaries(article);
  if (card.summary_status === 'ok') {
    if (summarySlot.length !== 1 || summarySlot[0] !== card.summary) {
      fail(`${card.id} summary does not match the file`);
    }
  } else if (card.summary_status === 'thin') {
    if (summarySlot.length !== 0 || article.includes('class="summary"')) {
      fail(`${card.id} thin card invented a summary`);
    }
  } else {
    if (summarySlot.length !== 1 || summarySlot[0] !== DEGRADED_BODY) {
      fail(`${card.id} degraded summary must be exactly the locked sentence`);
    }
    if (article.includes(card.summary_status)) fail(`${card.id} shows its status name`);
  }
  const video = card.media === 'video';
  const hasPlay = article.includes('class="play"');
  if (video !== hasPlay) fail(`${card.id} play icon ${video ? 'missing' : 'should be absent'}`);
}

function assertOrder(html, className, cards, label) {
  const ids = articleIds(html, className);
  const expected = cards.map((card) => card.id);
  if (ids.join(',') !== expected.join(',')) {
    fail(`${label} order is ${ids.join(', ')} but the file says ${expected.join(', ')}`);
  }
}

const pages = {
  home: readPage('index.html'),
  edtech: readPage('edtech/index.html'),
  business: readPage('business/index.html'),
  technical: readPage('technical/index.html'),
  archive: readPage('archive/index.html'),
  digest: readPage(`digest/${WEEK_ID}/index.html`),
  digestBusiness: readPage(`digest/${WEEK_ID}/business/index.html`),
};

const htmlFiles = walk(DIST);
const allHtml = htmlFiles.map((path) => readFileSync(path, 'utf8')).join('\n');
const readerFacing = [
  week.briefing.synthesis,
  ...[...week.main_feed, ...week.footer_aside, ...week.briefing.top].flatMap((card) => [
    card.title,
    card.summary,
    card.body,
    card.publisher.name,
  ]),
]
  .filter((value) => typeof value === 'string')
  .join('\n');

for (const banned of [
  'transcript_missing',
  'quota_exhausted',
  'summary_status',
  'api_error',
  'client_init_error',
  'deferred_budget',
  'parse_error',
  'Gemini',
  'GEMINI',
]) {
  if (allHtml.includes(banned) && !readerFacing.includes(banned)) {
    fail(`built site contains status chrome: ${banned}`);
  }
}

if (/class="[^"]*(status|banner|notice|pipeline)/i.test(allHtml)) {
  fail('built site contains a status, banner, or notice element');
}

const tabLabels = ['Briefing', 'Edtech', 'Business', 'Technical', 'Archive'];
for (const html of Object.values(pages)) {
  for (const label of tabLabels) {
    if (!html.includes(`>${label}<`)) fail(`missing tab ${label}`);
  }
}

if (!pages.home.includes('rel="canonical" href="/digest/2026-W40"')) {
  fail('home canonical should be the week permalink');
}
if (!pages.business.includes('rel="canonical" href="/digest/2026-W40/business"')) {
  fail('business canonical should be the week topic permalink');
}
if (!pages.home.includes('Week of Sep 27 – Oct 3, 2026')) fail('home is missing the week range');
if (!decode(pages.home).includes(week.briefing.synthesis)) fail('briefing is missing the synthesis');

const homeParts = splitFooter(pages.home);
assertOrder(homeParts.main, 'card', week.briefing.top, 'briefing');
if (articleIds(homeParts.main, 'card').length !== week.briefing.top.length) {
  fail('briefing must show the Top list only');
}
for (const card of week.briefing.top) assertCard(homeParts.main, card);
assertOrder(homeParts.footer, 'thin', week.footer_aside, 'home footer');
for (const item of week.footer_aside) assertCard(homeParts.footer, item);

const businessParts = splitFooter(pages.business);
assertOrder(businessParts.main, 'card', week.topics.business, 'business');
for (const card of week.topics.business) assertCard(businessParts.main, card);
assertOrder(businessParts.footer, 'thin', week.footer_aside, 'business footer');
if (week.footer_aside[0] && businessParts.main.includes(week.footer_aside[0].id)) {
  fail('thin item was placed in the business list');
}
const degradedBusiness = week.topics.business.filter((card) => card.summary_status !== 'ok');
const degradedShown = decode(businessParts.main).split(DEGRADED_BODY).length - 1;
if (degradedShown !== degradedBusiness.length) {
  fail(
    `business page showed the degraded sentence ${degradedShown} times; the file has ${degradedBusiness.length}`,
  );
}

const edtechParts = splitFooter(pages.edtech);
assertOrder(edtechParts.main, 'card', week.topics.edtech, 'edtech');
for (const card of week.topics.edtech) assertCard(edtechParts.main, card);

const technicalParts = splitFooter(pages.technical);
assertOrder(technicalParts.main, 'card', week.topics.technical, 'technical');
for (const card of week.topics.technical) assertCard(technicalParts.main, card);

const digestParts = splitFooter(pages.digest);
assertOrder(digestParts.main, 'card', week.briefing.top, 'permalink briefing');
if (!pages.digestBusiness.includes('aria-current="page"')) fail('business permalink is missing the current tab');

const excerpt = week.briefing.synthesis.trim().match(/^.+?[.!?](?=\s|$)/)?.[0];
if (!excerpt || !decode(pages.archive).includes(excerpt)) fail('archive is missing the week excerpt');
if (!pages.archive.includes('>Read this week</a>')) fail('archive path must be labeled Read this week');
if (!pages.archive.includes(`href="/digest/${WEEK_ID}"`)) fail('archive path does not open the week');
if (pages.archive.includes('class="summary"')) fail('archive invented a card summary');

const thin = week.footer_aside[0];
if (thin && thin.summary_status !== 'thin') fail('footer item is not thin');

// Throwaway build fixture. Not a sample week: it is deleted, and dist is rebuilt from the real files.
const fixturePath = 'content/digests/1999-W01.json';
const fixture = {
  schema_version: 1,
  week_id: '1999-W01',
  timezone: 'America/New_York',
  week_start: '1999-01-03T00:00:00-05:00',
  week_end: '1999-01-09T23:59:59-05:00',
  generated_at: '1999-01-10T15:00:00Z',
  briefing: { synthesis: 'Empty-topic fixture.', top: [] },
  topics: {
    edtech: [],
    business: [
      {
        id: 'empty-topic-fixture',
        title: 'Fixture card',
        url: 'https://example.com/fixture',
        publisher: { source_id: 'import-ai', name: 'Import AI' },
        published_at: '1999-01-04T15:00:00Z',
        category: 'business',
        media: 'article',
        summary_status: 'ok',
        summary: 'Fixture summary.',
      },
      {
        id: 'locked-degraded-fixture',
        title: 'Locked degraded fixture',
        url: 'https://example.com/locked-degraded-fixture',
        publisher: { source_id: 'import-ai', name: 'Import AI' },
        published_at: '1999-01-05T15:00:00Z',
        category: 'business',
        media: 'article',
        summary_status: 'api_error',
        body: DEGRADED_BODY,
      },
    ],
    technical: [],
  },
  main_feed: [],
  footer_aside: [],
};

function rebuild() {
  const result = spawnSync('pnpm', ['exec', 'astro', 'build'], { stdio: 'inherit' });
  if (result.status !== 0) fail('astro build failed');
}

writeFileSync(fixturePath, `${JSON.stringify(fixture, null, 2)}\n`);
try {
  rebuild();
  const emptyEdtech = readPage('digest/1999-W01/edtech/index.html');
  const emptyTechnical = readPage('digest/1999-W01/technical/index.html');
  const filledBusiness = readPage('digest/1999-W01/business/index.html');
  if (!emptyEdtech.includes('Nothing in Edtech this week.')) fail('empty Edtech tab has no empty state');
  if (!emptyTechnical.includes('Nothing in Technical this week.')) fail('empty Technical tab has no empty state');
  if (filledBusiness.includes('Nothing in Business this week.')) fail('Business showed an empty state while it had a card');
  if (!filledBusiness.includes('Fixture card')) fail('Business dropped its only card');
  if (!decode(filledBusiness).includes(DEGRADED_BODY)) {
    fail('degraded fixture card did not render the locked sentence');
  }
  if (filledBusiness.includes('api_error')) fail('degraded fixture card shows its status name');
  for (const html of [emptyEdtech, emptyTechnical, filledBusiness]) {
    for (const label of tabLabels) {
      if (!html.includes(`>${label}<`)) fail(`a zero-item week hid the ${label} tab`);
    }
  }
  if (!decode(readPage('index.html')).includes(week.briefing.synthesis)) {
    fail('the empty fixture replaced the latest week');
  }
} finally {
  rmSync(fixturePath, { force: true });
  rebuild();
}

if (existsSync(fixturePath) || existsSync('dist/digest/1999-W01')) {
  fail('empty-topic fixture was left behind');
}
const rebuiltShown = decode(readPage('business/index.html')).split(DEGRADED_BODY).length - 1;
if (rebuiltShown !== degradedBusiness.length) {
  fail('rebuilt business page does not match the week file degraded cards');
}

console.log(`reader check passed for ${WEEK_ID}`);
