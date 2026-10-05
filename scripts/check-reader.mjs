import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  digestWeekId,
  isCompleteWeek,
  isPublishedWeek,
  isoWeekId,
  newYorkParts,
  selectLatestPublished,
} from '../src/lib/week-rules.mjs';

const DEGRADED_BODY = "The summary couldn't be generated this week.";
const WEEK_ID = '2026-W40';
const DIST = 'dist';

const week = JSON.parse(readFileSync(`content/digests/${WEEK_ID}.json`, 'utf8'));
const MIDWEEK = '2026-10-07T15:00:00-04:00';
// One second before 2026-W41 ends. The build clock stays inside the open week.
const SITE_AS_OF = '2026-10-10T23:59:58-04:00';
const CLOCK_SYNTHESIS = 'Clock canary synthesis from the saved file.';
const OPEN_SYNTHESIS = 'Open week fixture stays off the home page.';
const DRAFT_SYNTHESIS = 'Half-finished draft fixture stays off the home page.';
const OLDER_SYNTHESIS = 'Saved older week synthesis from the file. The second sentence stays put too.';

function fail(message) {
  throw new Error(message);
}

function fixtureCard(id, category, summary, publishedAt) {
  return {
    id,
    title: id,
    url: `https://example.com/${id}`,
    publisher: { source_id: 'import-ai', name: 'Import AI' },
    published_at: publishedAt,
    category,
    media: 'article',
    summary_status: 'ok',
    summary,
  };
}

function completeWeek(weekId, weekStart, weekEnd, synthesis, cards, topics) {
  return {
    schema_version: 1,
    week_id: weekId,
    timezone: 'America/New_York',
    week_start: weekStart,
    week_end: weekEnd,
    generated_at: '2026-10-04T16:00:00Z',
    briefing: { synthesis, top: cards },
    topics,
    main_feed: [],
    footer_aside: [],
  };
}

function proveWeekRules() {
  const start = newYorkParts(week.week_start);
  const end = newYorkParts(week.week_end);
  if (week.timezone !== 'America/New_York') fail('committed week timezone is not America/New_York');
  if (week.week_start !== '2026-09-27T00:00:00-04:00' || week.week_end !== '2026-10-03T23:59:59-04:00') {
    fail('committed week is not Sun Sep 27 00:00:00 through Sat Oct 3 23:59:59, offset -04:00');
  }
  if (!start || start.weekday !== 'Sun' || start.hour !== 0 || start.minute !== 0 || start.second !== 0) {
    fail('week_start is not Sunday 00:00:00 America/New_York');
  }
  if (!end || end.weekday !== 'Sat' || end.hour !== 23 || end.minute !== 59 || end.second !== 59) {
    fail('week_end is not Saturday 23:59:59 America/New_York');
  }
  if (week.week_id !== '2026-W40' || week.week_id !== isoWeekId(end.year, end.month, end.day)) {
    fail('week_id is not the ISO week of the ending Saturday');
  }
  if (digestWeekId('2026-10-04T12:00:00-04:00') !== '2026-W41') {
    fail('Sunday Oct 4, 2026 must be in-progress digest week 2026-W41');
  }
  if (digestWeekId('2026-10-03T12:00:00-04:00') !== '2026-W40') {
    fail('Saturday Oct 3, 2026 must stay in digest week 2026-W40');
  }
  if (JSON.stringify(week).includes(DEGRADED_BODY)) fail('committed week includes the degraded sentence');
  if (week.footer_aside[0]?.title !== 'September sponsors-only newsletter') {
    fail('committed week is missing the September sponsors footer');
  }

  const sunday = new Date('2026-10-04T12:00:00-04:00');
  const wednesday = new Date(MIDWEEK);
  const sundayAfterClose = new Date('2026-10-11T00:00:00-04:00');
  if (!isCompleteWeek(week) || !isPublishedWeek(week, sunday)) {
    fail('2026-W40 must be the published week on Sunday Oct 4, 2026');
  }
  const openCards = [1, 2, 3, 4, 5].map((n) =>
    fixtureCard(`open-week-${n}`, 'technical', `Open week summary ${n} from the file.`, '2026-10-05T15:00:00Z'),
  );
  const openWeek = completeWeek(
    '2026-W41',
    '2026-10-04T00:00:00-04:00',
    '2026-10-10T23:59:59-04:00',
    OPEN_SYNTHESIS,
    openCards,
    { edtech: [], business: [], technical: [] },
  );
  const halfWeek = completeWeek(
    '2027-W01',
    '2026-09-27T00:00:00-04:00',
    '2026-10-03T23:59:59-04:00',
    DRAFT_SYNTHESIS,
    [fixtureCard('half-finished-draft', 'business', 'Draft card summary from the file.', '2026-09-29T15:00:00Z')],
    { edtech: [], business: [], technical: [] },
  );
  if (isPublishedWeek(openWeek, wednesday)) fail('a week that is still open must not count as published');
  if (isPublishedWeek(halfWeek, wednesday)) fail('a half-finished draft must not count as published');
  const midweek = selectLatestPublished([halfWeek, openWeek, week], wednesday);
  if (midweek?.week_id !== WEEK_ID) fail(`mid-week selector picked ${midweek?.week_id ?? 'nothing'}`);
  const afterClose = selectLatestPublished([week, openWeek], sundayAfterClose);
  if (afterClose?.week_id !== '2026-W41') {
    fail('a completed week must become latest once its Saturday has ended');
  }
  console.log('week rules passed for 2026-W40, Sunday Oct 4, and Wednesday Oct 7');
}

proveWeekRules();

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

function alsoSeenCount(html) {
  return {
    headings: html.match(/Also seen this week/g)?.length ?? 0,
    sections: html.match(/<aside\b[^>]*\bid="also-seen"/g)?.length ?? 0,
  };
}

function assertBriefingAlsoSeen(html, items, label) {
  const { headings, sections } = alsoSeenCount(html);
  if (items.length === 0) {
    if (headings !== 0 || sections !== 0 || html.includes('id="also-seen"')) {
      fail(`${label} shows Also seen with no thin items`);
    }
    return;
  }
  if (headings !== 1 || sections !== 1) {
    fail(`${label} should show Also seen once (heading ${headings}, section ${sections})`);
  }
  const parts = splitFooter(html);
  if (!parts.footer.includes('<h2>Also seen this week</h2>')) {
    fail(`${label} Also seen heading is missing`);
  }
  if (!parts.footer.includes('class="thin"')) fail(`${label} Also seen section is empty`);
  assertOrder(parts.footer, 'thin', items, `${label} footer`);
  for (const item of items) {
    assertCard(parts.footer, item);
    if (parts.main.includes(`id="${item.id}"`)) fail(`${label} moved thin item ${item.id} into the main list`);
  }
}

function assertTopicOmitsAlsoSeen(html, items, label) {
  const { headings, sections } = alsoSeenCount(html);
  if (headings !== 0 || sections !== 0 || html.includes('id="also-seen"')) {
    fail(`${label} shows Also seen`);
  }
  for (const item of items) {
    if (html.includes(`id="${item.id}"`) || decode(html).includes(item.title)) {
      fail(`${label} placed thin item ${item.id} in the topic list`);
    }
  }
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
if (!decode(pages.home).includes('September sponsors-only newsletter')) {
  fail('home is missing the September sponsors footer');
}
for (const [name, html] of Object.entries(pages)) {
  if (html.includes(DEGRADED_BODY)) fail(`${name} includes the degraded sentence`);
}

const homeParts = splitFooter(pages.home);
assertOrder(homeParts.main, 'card', week.briefing.top, 'briefing');
if (articleIds(homeParts.main, 'card').length !== week.briefing.top.length) {
  fail('briefing must show the Top list only');
}
for (const card of week.briefing.top) assertCard(homeParts.main, card);
assertBriefingAlsoSeen(pages.home, week.footer_aside, 'current briefing');

const businessParts = splitFooter(pages.business);
assertOrder(businessParts.main, 'card', week.topics.business, 'business');
for (const card of week.topics.business) assertCard(businessParts.main, card);
assertTopicOmitsAlsoSeen(pages.business, week.footer_aside, 'business');
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
assertTopicOmitsAlsoSeen(pages.edtech, week.footer_aside, 'edtech');

const technicalParts = splitFooter(pages.technical);
assertOrder(technicalParts.main, 'card', week.topics.technical, 'technical');
for (const card of week.topics.technical) assertCard(technicalParts.main, card);
assertTopicOmitsAlsoSeen(pages.technical, week.footer_aside, 'technical');
assertTopicOmitsAlsoSeen(pages.digestBusiness, week.footer_aside, 'business permalink');

const digestParts = splitFooter(pages.digest);
assertOrder(digestParts.main, 'card', week.briefing.top, 'permalink briefing');
assertBriefingAlsoSeen(pages.digest, week.footer_aside, 'current week briefing permalink');
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

function rebuild(extraEnv = {}) {
  const env = { ...process.env, ...extraEnv };
  if (!Object.hasOwn(extraEnv, 'DIGEST_AS_OF')) delete env.DIGEST_AS_OF;
  const result = spawnSync('pnpm', ['exec', 'astro', 'build'], { stdio: 'inherit', env });
  if (result.status !== 0) fail('astro build failed');
}

const olderEdtech = fixtureCard(
  'saved-edtech',
  'edtech',
  'Saved edtech summary from the file.',
  '2026-09-21T15:00:00Z',
);
const olderBusiness = fixtureCard(
  'saved-business',
  'business',
  'Saved business summary from the file.',
  '2026-09-22T15:00:00Z',
);
const olderTechnical = fixtureCard(
  'saved-technical',
  'technical',
  'Saved technical summary from the file.',
  '2026-09-23T15:00:00Z',
);
const olderTechnicalExtra = fixtureCard(
  'saved-technical-extra',
  'technical',
  'Saved technical extra summary from the file.',
  '2026-09-24T15:00:00Z',
);
const olderTechnicalThird = fixtureCard(
  'saved-technical-third',
  'technical',
  'Saved technical third summary from the file.',
  '2026-09-25T15:00:00Z',
);
const olderThin = {
  id: 'saved-thin-footer',
  title: 'Saved thin footer item from the file.',
  url: 'https://example.com/saved-thin-footer',
  publisher: { source_id: 'import-ai', name: 'Import AI' },
  published_at: '2026-09-25T18:00:00Z',
  category: 'technical',
  media: 'article',
  summary_status: 'thin',
};
const olderWeek = completeWeek(
  '2026-W39',
  '2026-09-20T00:00:00-04:00',
  '2026-09-26T23:59:59-04:00',
  OLDER_SYNTHESIS,
  [olderEdtech, olderBusiness, olderTechnical, olderTechnicalExtra, olderTechnicalThird],
  {
    edtech: [olderEdtech],
    business: [olderBusiness],
    technical: [olderTechnical, olderTechnicalExtra, olderTechnicalThird],
  },
);
olderWeek.footer_aside = [olderThin];
const openWeek = completeWeek(
  '2026-W41',
  '2026-10-04T00:00:00-04:00',
  '2026-10-10T23:59:59-04:00',
  OPEN_SYNTHESIS,
  [1, 2, 3, 4, 5].map((n) =>
    fixtureCard(`open-week-${n}`, 'technical', `Open week summary ${n} from the file.`, '2026-10-05T15:00:00Z'),
  ),
  { edtech: [], business: [], technical: [] },
);
const halfWeek = completeWeek(
  '2027-W01',
  '2026-09-27T00:00:00-04:00',
  '2026-10-03T23:59:59-04:00',
  DRAFT_SYNTHESIS,
  [fixtureCard('half-finished-draft', 'business', 'Draft card summary from the file.', '2026-09-29T15:00:00Z')],
  { edtech: [], business: [], technical: [] },
);
const clockWeek = completeWeek(
  '2020-W01',
  '2020-01-05T00:00:00-05:00',
  SITE_AS_OF,
  CLOCK_SYNTHESIS,
  [1, 2, 3, 4, 5].map((n) =>
    fixtureCard(`clock-canary-${n}`, 'technical', `Clock canary summary ${n} from the file.`, '2020-01-06T15:00:00Z'),
  ),
  { edtech: [], business: [], technical: [] },
);
if (!isPublishedWeek(clockWeek, new Date(SITE_AS_OF))) fail('clock canary should be published at the build clock');
if (isPublishedWeek(clockWeek, new Date(new Date(SITE_AS_OF).getTime() - 1000))) {
  fail('clock canary should still be open a second before the build clock');
}
const fixtureFiles = {
  [fixturePath]: fixture,
  'content/digests/2026-W39.json': olderWeek,
  'content/digests/2026-W41.json': openWeek,
  'content/digests/2027-W01.json': halfWeek,
  'content/digests/2020-W01.json': clockWeek,
};

for (const [path, doc] of Object.entries(fixtureFiles)) {
  writeFileSync(path, `${JSON.stringify(doc, null, 2)}\n`);
}
try {
  rebuild({ DIGEST_AS_OF: SITE_AS_OF });
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
  const homeDuringWeek = decode(readPage('index.html'));
  if (!homeDuringWeek.includes(week.briefing.synthesis)) {
    fail('the empty fixture replaced the latest week');
  }
  if (!homeDuringWeek.includes('Week of Sep 27 – Oct 3, 2026')) {
    fail('mid-week home left the last published week');
  }
  if (
    homeDuringWeek.includes(OPEN_SYNTHESIS) ||
    homeDuringWeek.includes(DRAFT_SYNTHESIS) ||
    homeDuringWeek.includes(OLDER_SYNTHESIS) ||
    homeDuringWeek.includes(CLOCK_SYNTHESIS)
  ) {
    fail('mid-week home showed an open week, a half-finished draft, or an older week');
  }
  if (!readPage('index.html').includes('rel="canonical" href="/digest/2026-W40"')) {
    fail('mid-week home canonical left 2026-W40');
  }

  const archiveDuringWeek = decode(readPage('archive/index.html'));
  if (
    !archiveDuringWeek.includes('href="/digest/2026-W40"') ||
    !archiveDuringWeek.includes('href="/digest/2026-W39"') ||
    !archiveDuringWeek.includes('href="/digest/2020-W01"')
  ) {
    fail('archive must link the published weeks, including the clock canary');
  }
  if (!archiveDuringWeek.includes(CLOCK_SYNTHESIS)) fail('archive clock canary does not match the saved file');
  if (archiveDuringWeek.includes('/digest/2026-W41') || archiveDuringWeek.includes('/digest/2027-W01')) {
    fail('archive listed an open week or a half-finished draft');
  }
  if (!archiveDuringWeek.includes('Saved older week synthesis from the file.')) {
    fail('archive excerpt for the older week does not match the saved file');
  }
  if (!archiveDuringWeek.includes('Week of Sep 20 – Sep 26, 2026')) {
    fail('archive is missing the older week range');
  }

  const olderBriefingHtml = readPage('digest/2026-W39/index.html');
  const olderEdtechHtml = readPage('digest/2026-W39/edtech/index.html');
  const olderBusinessHtml = readPage('digest/2026-W39/business/index.html');
  const olderTechnicalHtml = readPage('digest/2026-W39/technical/index.html');
  assertBriefingAlsoSeen(olderBriefingHtml, [olderThin], 'archived briefing');
  assertTopicOmitsAlsoSeen(olderEdtechHtml, [olderThin], 'archived edtech');
  assertTopicOmitsAlsoSeen(olderBusinessHtml, [olderThin], 'archived business');
  assertTopicOmitsAlsoSeen(olderTechnicalHtml, [olderThin], 'archived technical');
  assertBriefingAlsoSeen(readPage('digest/1999-W01/index.html'), [], 'briefing with no thin items');
  const olderBriefing = decode(olderBriefingHtml);
  const olderEdtechPage = decode(olderEdtechHtml);
  const olderBusinessPage = decode(olderBusinessHtml);
  const olderTechnicalPage = decode(olderTechnicalHtml);
  if (!olderBriefing.includes(OLDER_SYNTHESIS)) fail('older briefing does not render the saved synthesis');
  if (olderBriefing.includes(week.briefing.synthesis)) fail('older briefing picked up the latest week synthesis');
  for (const saved of [
    olderEdtech,
    olderBusiness,
    olderTechnical,
    olderTechnicalExtra,
    olderTechnicalThird,
  ]) {
    if (!olderBriefing.includes(saved.summary)) fail(`older briefing dropped the saved summary for ${saved.id}`);
  }
  if (!olderEdtechPage.includes(olderEdtech.summary) || olderEdtechPage.includes(olderBusiness.summary)) {
    fail('older Edtech tab did not render the saved topic list');
  }
  if (!olderBusinessPage.includes(olderBusiness.summary) || olderBusinessPage.includes(olderEdtech.summary)) {
    fail('older Business tab did not render the saved topic list');
  }
  for (const saved of [olderTechnical, olderTechnicalExtra, olderTechnicalThird]) {
    if (!olderTechnicalPage.includes(saved.summary)) fail(`older Technical tab dropped ${saved.id}`);
  }
  if (olderTechnicalPage.includes(olderBusiness.summary)) {
    fail('older Technical tab included a saved card from another topic');
  }
  for (const html of [olderBriefing, olderEdtechPage, olderBusinessPage, olderTechnicalPage]) {
    for (const label of tabLabels) {
      if (!html.includes(`>${label}<`)) fail(`older week hid the ${label} tab`);
    }
  }
  const olderNav = readPage('digest/2026-W39/index.html');
  for (const href of ['/digest/2026-W39/edtech', '/digest/2026-W39/business', '/digest/2026-W39/technical']) {
    if (!olderNav.includes(`href="${href}"`)) fail(`older week tab does not link to ${href}`);
  }
  if (!olderNav.includes('← Latest week')) fail('older week is missing the link back to the latest week');
} finally {
  for (const path of Object.keys(fixtureFiles)) rmSync(path, { force: true });
  rebuild();
}

if (
  Object.keys(fixtureFiles).some((path) => existsSync(path)) ||
  ['1999-W01', '2026-W39', '2026-W41', '2027-W01', '2020-W01'].some((id) => existsSync(`dist/digest/${id}`))
) {
  fail('throwaway week fixtures were left behind');
}
const rebuiltShown = decode(readPage('business/index.html')).split(DEGRADED_BODY).length - 1;
if (rebuiltShown !== degradedBusiness.length) {
  fail('rebuilt business page does not match the week file degraded cards');
}

console.log(`reader check passed for ${WEEK_ID}`);
