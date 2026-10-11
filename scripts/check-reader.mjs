import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { formatDate, formatWeekRange } from '../src/lib/format-date.mjs';
import {
  digestWeekId,
  isCompleteWeek,
  isPublishedWeek,
  isoWeekId,
  newYorkParts,
  readerNow,
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

function proveReaderDates() {
  const stamp = '2026-10-03T03:00:18Z';
  const shown = formatDate(stamp);
  if (shown.includes('Oct 3')) fail(`${stamp} renders as Oct 3`);
  if (shown !== 'Oct 2, 2026') fail(`${stamp} shows ${shown}`);

  const sameInstant = formatDate('2026-10-03T03:00:18+00:00');
  if (sameInstant.includes('Oct 3')) fail('2026-10-03T03:00:18+00:00 renders as Oct 3');
  if (sameInstant !== 'Oct 2, 2026') fail(`2026-10-03T03:00:18+00:00 shows ${sameInstant}`);

  const dateOnly = '2026-10-03';
  const dateOnlyShown = formatDate(dateOnly);
  if (dateOnlyShown !== 'Oct 3, 2026') fail(`date-only ${dateOnly} shows ${dateOnlyShown}`);
  console.log('reader dates passed for 2026-10-03T03:00:18Z and date-only 2026-10-03');
}

proveWeekRules();
proveReaderDates();

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

function cardTitles(html) {
  return [...html.matchAll(/<h3\b[^>]*class="[^"]*\bcard-title\b[^"]*"[^>]*>([\s\S]*?)<\/h3>/g)].map((match) =>
    decode(match[1].replace(/<[^>]*>/g, '')).replace(/\s+/g, ' ').trim(),
  );
}

function assertTopicOmitsAlsoSeen(html, items, label) {
  const { headings, sections } = alsoSeenCount(html);
  if (headings !== 0 || sections !== 0 || html.includes('id="also-seen"')) {
    fail(`${label} shows Also seen`);
  }
  const titles = cardTitles(html);
  for (const item of items) {
    // A summary may name the same story. The thin card itself has this id and heading.
    if (html.includes(`id="${item.id}"`) || titles.includes(item.title)) {
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

const SECTION_LABELS = ['Business', 'Technical', 'Education', 'Policy and Safety'];
const SECTION_IDS = ['business', 'technical', 'edtech', 'policy-and-safety'];

function navBlock(html, className) {
  const pattern = new RegExp(`<nav\\b[^>]*class="[^"]*\\b${className}\\b[^"]*"[^>]*>[\\s\\S]*?</nav>`);
  return html.match(pattern)?.[0] ?? '';
}

function linkLabels(block) {
  return [...block.matchAll(/<a\b[^>]*>([^<]*)<\/a>/g)].map((match) => decode(match[1]).trim());
}

function linkHrefs(block) {
  return [...block.matchAll(/<a\b[^>]*href="([^"]*)"[^>]*>/g)].map((match) => match[1]);
}

function assertReaderChrome(html, label) {
  const briefing = navBlock(html, 'nav-briefing');
  const sections = navBlock(html, 'nav-sections');
  if (!briefing) fail(`${label} is missing the Briefing line`);
  if (!sections) fail(`${label} is missing the sections row`);
  const briefingAt = html.indexOf(briefing);
  const sectionsAt = html.indexOf(sections);
  if (briefingAt < 0 || sectionsAt < 0 || briefingAt + briefing.length > sectionsAt) {
    fail(`${label} Briefing is not on its own line above the sections`);
  }
  const briefingLabels = linkLabels(briefing);
  if (briefingLabels.length !== 1 || briefingLabels[0] !== 'Briefing') {
    fail(`${label} Briefing line reads ${briefingLabels.join(', ') || 'nothing'}`);
  }
  const sectionLabels = linkLabels(sections);
  if (sectionLabels.join('|') !== SECTION_LABELS.join('|')) {
    fail(`${label} sections are ${sectionLabels.join(', ') || 'missing'}`);
  }
  if (sections.includes('>Archive<') || sections.includes('href="/archive"')) {
    fail(`${label} Archive is in the sections row`);
  }
  if (sections.includes('>Edtech<') || sections.includes('>Ed tech<')) {
    fail(`${label} sections row says Edtech`);
  }
  const briefingHref = linkHrefs(briefing)[0];
  const weekMatch = briefingHref?.match(/^\/digest\/(\d{4}-W\d{2})$/);
  const expectedHrefs =
    briefingHref === '/'
      ? SECTION_IDS.map((id) => `/${id}`)
      : weekMatch
        ? SECTION_IDS.map((id) => `/digest/${weekMatch[1]}/${id}`)
        : null;
  if (!expectedHrefs) fail(`${label} Briefing link is ${briefingHref ?? 'missing'}`);
  const hrefs = linkHrefs(sections);
  if (hrefs.join('|') !== expectedHrefs.join('|')) {
    fail(`${label} section links are ${hrefs.join(', ')}`);
  }
  const mainAt = html.indexOf('<main');
  const header = mainAt === -1 ? html : html.slice(0, mainAt);
  if (header.includes('>Edtech<') || header.includes('>Ed tech<')) fail(`${label} shows Edtech`);
  const weekLine = html.match(/<p class="week-line">[\s\S]*?<\/p>/)?.[0];
  if (!weekLine) fail(`${label} is missing the week line`);
  const archiveHrefs = [...html.matchAll(/href="\/archive"/g)];
  if (archiveHrefs.length !== 1 || !weekLine.includes('href="/archive"') || !weekLine.includes('>Archive<')) {
    fail(`${label} Archive is not the week-line link to /archive`);
  }
  const rangeAt = weekLine.indexOf('class="week-range"');
  const timeAt = weekLine.indexOf('<time');
  const updatedText = decode(weekLine.match(/<time\b[^>]*>([^<]*)<\/time>/)?.[1] ?? '').trim();
  if (rangeAt === -1 || timeAt === -1 || rangeAt > timeAt || !updatedText.startsWith('Updated ')) {
    fail(`${label} week line should show the week range, then the Updated date`);
  }
  const timeEnd = weekLine.indexOf('</time>');
  if (timeEnd === -1) fail(`${label} Updated date is missing`);
  const afterTime = weekLine.slice(timeEnd + '</time>'.length);
  const archiveAt = afterTime.search(/<a\b[^>]*href="\/archive"[^>]*>/);
  if (archiveAt === -1) fail(`${label} Archive is not to the right of Updated`);
  const between = decode(afterTime.slice(0, archiveAt)).replace(/&middot;/gi, '·').replace(/<[^>]*>/g, '');
  if (between.includes(',')) fail(`${label} has a comma between Updated and Archive`);
  if (!/^[\s·]*$/.test(between)) fail(`${label} puts "${between}" between Updated and Archive`);
}

function assertBuiltChrome(scope) {
  for (const file of walk(DIST)) {
    assertReaderChrome(readFileSync(file, 'utf8'), `${scope} ${file}`);
  }
}

const SECTION_TABS = SECTION_IDS.map((id, index) => ({ id, label: SECTION_LABELS[index] }));

function loadDigestWeeks() {
  const weeks = [];
  for (const name of readdirSync('content/digests')) {
    if (!name.endsWith('.json')) continue;
    weeks.push(JSON.parse(readFileSync(join('content/digests', name), 'utf8')));
  }
  return weeks;
}

// Topic tabs render topics[id] only. Also seen is footer_aside and stays on Briefing.
function sectionCards(weekDoc, topicId) {
  const list = weekDoc.topics?.[topicId];
  return Array.isArray(list) ? list : [];
}

function readerFacingText(weeks) {
  return weeks
    .flatMap((item) => [
      item.briefing?.synthesis,
      ...[...(item.main_feed ?? []), ...(item.footer_aside ?? []), ...(item.briefing?.top ?? [])].flatMap((card) => [
        card.title,
        card.summary,
        card.body,
        card.publisher?.name,
      ]),
    ])
    .filter((value) => typeof value === 'string')
    .join('\n');
}

function emptyMessage(label) {
  return `Nothing in ${label} this week.`;
}

function emptyParagraphs(html) {
  return [...html.matchAll(/<p\b([^>]*)>([\s\S]*?)<\/p>/g)]
    .filter((match) => {
      const classMatch = match[1].match(/class="([^"]*)"/);
      return classMatch && classMatch[1].split(/\s+/).includes('empty');
    })
    .map((match) => decode(match[2]).replace(/\s+/g, ' ').trim());
}

function emptyRuleIsDimmed(html) {
  const css = [...html.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)].map((match) => match[1]).join('\n');
  return /\.empty\b[^{]*\{[^}]*color:\s*var\(--muted\)/.test(css);
}

function assertDimmedEmptyState(html, label, expectEmpty, where) {
  const message = emptyMessage(label);
  const paragraphs = emptyParagraphs(html);
  const hasMessage = decode(html).includes(message);
  if (expectEmpty) {
    if (!hasMessage) fail(`${where} empty ${label} tab has no empty state`);
    if (!paragraphs.includes(message) || !emptyRuleIsDimmed(html)) {
      fail(`${where} empty ${label} tab is missing the dimmed empty state`);
    }
    return;
  }
  if (hasMessage || paragraphs.length > 0) fail(`${where} ${label} showed an empty state while it had stories`);
}

function fromMain(html) {
  const mainAt = html.indexOf('<main');
  return mainAt === -1 ? html : html.slice(mainAt);
}

function sentenceHits(parts) {
  return parts.reduce((total, part) => {
    if (typeof part !== 'string' || !part.includes(DEGRADED_BODY)) return total;
    return total + part.split(DEGRADED_BODY).length - 1;
  }, 0);
}

function renderedCopy(cards) {
  return cards.flatMap((card) => (card.summary_status === 'ok' ? [card.summary] : [card.body]));
}

function assertDegradedHits(html, parts, label) {
  const shown = decode(fromMain(html)).split(DEGRADED_BODY).length - 1;
  const expected = sentenceHits(parts);
  if (shown !== expected) {
    fail(`${label} showed the degraded sentence ${shown} times; the file has ${expected}`);
  }
}

function assertSectionTab(html, weekDoc, topic, where) {
  const cards = sectionCards(weekDoc, topic.id);
  const parts = splitFooter(html);
  const shown = articleIds(parts.main, 'card');
  if (shown.length !== cards.length) {
    fail(
      `${where} ${topic.label} tab shows ${shown.length} stories; the week file has ${cards.length} (Also seen excluded)`,
    );
  }
  assertOrder(parts.main, 'card', cards, `${where} ${topic.label}`);
  for (const card of cards) assertCard(parts.main, card);
  assertTopicOmitsAlsoSeen(html, weekDoc.footer_aside ?? [], `${where} ${topic.label}`);
  assertDimmedEmptyState(html, topic.label, cards.length === 0, where);
  assertDegradedHits(html, renderedCopy(cards), `${where} ${topic.label}`);
}

function assertBriefingTab(html, weekDoc, where) {
  const cards = weekDoc.briefing.top;
  const parts = splitFooter(html);
  const shown = articleIds(parts.main, 'card');
  if (shown.length !== cards.length) {
    fail(`${where} briefing shows ${shown.length} stories; the file has ${cards.length}`);
  }
  if (!decode(parts.main).includes(`Top ${cards.length} this week`)) {
    fail(`${where} briefing does not show Top ${cards.length} this week`);
  }
  if (!decode(html).includes(weekDoc.briefing.synthesis)) fail(`${where} briefing is missing the synthesis`);
  assertOrder(parts.main, 'card', cards, `${where} briefing`);
  for (const card of cards) assertCard(parts.main, card);
  assertBriefingAlsoSeen(html, weekDoc.footer_aside ?? [], where);
  assertDegradedHits(html, [weekDoc.briefing.synthesis, ...renderedCopy(cards)], `${where} briefing`);
}

function findShownCard(weekDoc, predicate) {
  const pools = [['briefing', weekDoc.briefing.top], ...SECTION_TABS.map((topic) => [topic.id, sectionCards(weekDoc, topic.id)])];
  for (const [place, cards] of pools) {
    const card = cards.find(predicate);
    if (card) return { place, card };
  }
  return null;
}

function assertMediaCase(weekDoc, pageMap, where, required) {
  const video = findShownCard(weekDoc, (card) => card.media === 'video');
  const article = findShownCard(weekDoc, (card) => card.media !== 'video');
  if (!video) {
    if (required) fail(`${where} is missing a video story for the play icon check`);
    console.log(`${where} has no video story; play icon stays covered by /digest/${WEEK_ID}/`);
  } else {
    assertCard(pageMap[video.place], video.card);
  }
  if (!article) {
    if (required) fail(`${where} is missing an article story for the non-video check`);
    console.log(`${where} has no article story; non-video card stays covered by /digest/${WEEK_ID}/`);
  } else {
    assertCard(pageMap[article.place], article.card);
  }
}

function assertWeekReader(weekDoc, pageMap, where, logIfNoEmpty) {
  assertBriefingTab(pageMap.briefing, weekDoc, where);
  for (const topic of SECTION_TABS) assertSectionTab(pageMap[topic.id], weekDoc, topic, where);
  assertMediaCase(weekDoc, pageMap, where, !logIfNoEmpty);
  const counts = SECTION_TABS.map((topic) => `${topic.label} ${sectionCards(weekDoc, topic.id).length}`).join(', ');
  console.log(`${where} section counts: ${counts}`);
  if (logIfNoEmpty && SECTION_TABS.every((topic) => sectionCards(weekDoc, topic.id).length > 0)) {
    const covered = SECTION_TABS.filter((topic) => sectionCards(week, topic.id).length === 0).map((topic) => topic.label);
    if (covered.length === 0) {
      console.log(
        `${where} has no empty section; empty-state message and dimmed styling stay covered by the empty-topic fixture`,
      );
    } else {
      console.log(
        `${where} has no empty section; empty-state message and dimmed styling stay covered by /digest/${WEEK_ID}/ (${covered.join(', ')})`,
      );
    }
  }
}

function firstSentence(synthesis) {
  const trimmed = synthesis.trim();
  return trimmed.match(/^.+?[.!?](?=\s|$)/)?.[0] ?? trimmed;
}

const pages = {
  home: readPage('index.html'),
  edtech: readPage('edtech/index.html'),
  business: readPage('business/index.html'),
  technical: readPage('technical/index.html'),
  policy: readPage('policy-and-safety/index.html'),
  archive: readPage('archive/index.html'),
  digest: readPage(`digest/${WEEK_ID}/index.html`),
  digestBusiness: readPage(`digest/${WEEK_ID}/business/index.html`),
  digestTechnical: readPage(`digest/${WEEK_ID}/technical/index.html`),
  digestEdtech: readPage(`digest/${WEEK_ID}/edtech/index.html`),
  digestPolicy: readPage(`digest/${WEEK_ID}/policy-and-safety/index.html`),
};

const htmlFiles = walk(DIST);
const allHtml = htmlFiles.map((path) => readFileSync(path, 'utf8')).join('\n');
const digestWeeks = loadDigestWeeks();
const latest = selectLatestPublished(digestWeeks, readerNow());
if (!latest) fail('no published week to check');
const readerFacing = readerFacingText(digestWeeks);

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

const tabLabels = ['Briefing', 'Education', 'Business', 'Technical', 'Policy and Safety', 'Archive'];
for (const html of Object.values(pages)) {
  for (const label of tabLabels) {
    if (!html.includes(`>${label}<`)) fail(`missing tab ${label}`);
  }
}
assertBuiltChrome('reader');

if (!pages.home.includes(`href="/edtech"`) || !pages.home.includes(`href="/policy-and-safety"`)) {
  fail('home nav is missing an Education or Policy and Safety link');
}
if (pages.home.includes('>Edtech<') || pages.home.includes('>Ed tech<')) {
  fail('nav still says Edtech');
}
if (!pages.home.includes(`rel="canonical" href="/digest/${latest.week_id}"`)) {
  fail('home canonical should be the week permalink');
}
if (!pages.business.includes(`rel="canonical" href="/digest/${latest.week_id}/business"`)) {
  fail('business canonical should be the week topic permalink');
}
if (!pages.home.includes(formatWeekRange(latest.week_start, latest.week_end))) fail('home is missing the week range');
if (!pages.business.includes('aria-current="page"')) fail('business tab is missing the current tab');
if (!pages.digestBusiness.includes('aria-current="page"')) fail('business permalink is missing the current tab');

const easternStamp = '2026-10-03T03:00:18+00:00';
const easternPattern = easternStamp.replaceAll('+', '\\+');
const easternLabels = [...allHtml.matchAll(new RegExp(`<time datetime="${easternPattern}">([^<]*)</time>`, 'g'))].map(
  (match) => decode(match[1]).trim(),
);
if (easternLabels.length === 0) fail(`built site is missing ${easternStamp}`);
for (const label of easternLabels) {
  if (label.includes('Oct 3')) fail(`${easternStamp} renders as Oct 3`);
  if (label !== 'Oct 2, 2026') fail(`${easternStamp} shows ${label}`);
}

const latestPages = {
  briefing: pages.home,
  business: pages.business,
  technical: pages.technical,
  edtech: pages.edtech,
  'policy-and-safety': pages.policy,
};
const archivePages = {
  briefing: pages.digest,
  business: pages.digestBusiness,
  technical: pages.digestTechnical,
  edtech: pages.digestEdtech,
  'policy-and-safety': pages.digestPolicy,
};
if (latest.week_id !== WEEK_ID) {
  console.log(`latest published week is ${latest.week_id}; archive checks stay on /digest/${WEEK_ID}/`);
}
assertWeekReader(latest, latestPages, `latest ${latest.week_id}`, true);
assertWeekReader(week, archivePages, `archive ${WEEK_ID}`, false);
if (!decode(archivePages.briefing).includes('September sponsors-only newsletter')) {
  fail(`archive ${WEEK_ID} briefing is missing the September sponsors footer`);
}

const excerpt = firstSentence(week.briefing.synthesis);
if (!excerpt || !decode(pages.archive).includes(excerpt)) fail('archive is missing the week excerpt');
const latestExcerpt = firstSentence(latest.briefing.synthesis);
if (!latestExcerpt || !decode(pages.archive).includes(latestExcerpt)) fail('archive is missing the latest week excerpt');
if (!pages.archive.includes('>Read this week</a>')) fail('archive path must be labeled Read this week');
if (!pages.archive.includes(`href="/digest/${WEEK_ID}"`)) fail('archive path does not open the week');
if (!pages.archive.includes(`href="/digest/${latest.week_id}"`)) fail('archive path does not open the latest week');
if (pages.archive.includes('class="summary"')) fail('archive invented a card summary');

const thin = week.footer_aside[0];
if (thin && thin.summary_status !== 'thin') fail('footer item is not thin');

// Throwaway build fixture. A week file that was already on disk is restored afterward, and dist is rebuilt from the files on disk.
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
const olderPolicy = fixtureCard(
  'saved-policy',
  'policy-and-safety',
  'Saved policy and safety summary from the file.',
  '2026-09-25T16:00:00Z',
);
const policyEastern = fixtureCard(
  'policy-eastern-stamp',
  'policy-and-safety',
  'Policy stamp summary from the file.',
  '2026-10-03T03:00:18Z',
);
const policyDateOnly = fixtureCard(
  'policy-date-only',
  'policy-and-safety',
  'Policy date-only summary from the file.',
  '2026-10-03',
);
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
    'policy-and-safety': [olderPolicy, policyEastern, policyDateOnly],
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

const originalWeekIds = new Set(loadDigestWeeks().map((item) => item.week_id));
const fixtureOriginals = new Map();
for (const path of Object.keys(fixtureFiles)) {
  if (existsSync(path)) fixtureOriginals.set(path, readFileSync(path));
}
for (const [path, doc] of Object.entries(fixtureFiles)) {
  writeFileSync(path, `${JSON.stringify(doc, null, 2)}\n`);
}
try {
  rebuild({ DIGEST_AS_OF: SITE_AS_OF });
  const emptyEdtech = readPage('digest/1999-W01/edtech/index.html');
  const emptyTechnical = readPage('digest/1999-W01/technical/index.html');
  const filledBusiness = readPage('digest/1999-W01/business/index.html');
  const emptyPolicy = readPage('digest/1999-W01/policy-and-safety/index.html');
  assertDimmedEmptyState(emptyEdtech, 'Education', true, 'fixture');
  assertDimmedEmptyState(emptyTechnical, 'Technical', true, 'fixture');
  assertDimmedEmptyState(emptyPolicy, 'Policy and Safety', true, 'fixture');
  assertDimmedEmptyState(filledBusiness, 'Business', false, 'fixture');
  if (!filledBusiness.includes('Fixture card')) fail('Business dropped its only card');
  if (!decode(filledBusiness).includes(DEGRADED_BODY)) {
    fail('degraded fixture card did not render the locked sentence');
  }
  if (filledBusiness.includes('api_error')) fail('degraded fixture card shows its status name');
  for (const html of [emptyEdtech, emptyTechnical, emptyPolicy, filledBusiness]) {
    for (const label of tabLabels) {
      if (!html.includes(`>${label}<`)) fail(`a zero-item week hid the ${label} tab`);
    }
  }
  const homeDuringWeek = decode(readPage('index.html'));
  if (!homeDuringWeek.includes(week.briefing.synthesis)) {
    fail('the empty fixture replaced the latest week');
  }
  if (!homeDuringWeek.includes(formatWeekRange(week.week_start, week.week_end))) {
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
  if (!archiveDuringWeek.includes(formatWeekRange(olderWeek.week_start, olderWeek.week_end))) {
    fail('archive is missing the older week range');
  }

  const olderBriefingHtml = readPage('digest/2026-W39/index.html');
  const olderEdtechHtml = readPage('digest/2026-W39/edtech/index.html');
  const olderBusinessHtml = readPage('digest/2026-W39/business/index.html');
  const olderTechnicalHtml = readPage('digest/2026-W39/technical/index.html');
  const olderPolicyHtml = readPage('digest/2026-W39/policy-and-safety/index.html');
  assertBriefingAlsoSeen(olderBriefingHtml, [olderThin], 'archived briefing');
  assertTopicOmitsAlsoSeen(olderEdtechHtml, [olderThin], 'archived Education');
  assertTopicOmitsAlsoSeen(olderBusinessHtml, [olderThin], 'archived business');
  assertTopicOmitsAlsoSeen(olderTechnicalHtml, [olderThin], 'archived technical');
  assertTopicOmitsAlsoSeen(olderPolicyHtml, [olderThin], 'archived Policy and Safety');
  assertBriefingAlsoSeen(readPage('digest/1999-W01/index.html'), [], 'briefing with no thin items');
  const olderBriefing = decode(olderBriefingHtml);
  const olderEdtechPage = decode(olderEdtechHtml);
  const olderBusinessPage = decode(olderBusinessHtml);
  const olderTechnicalPage = decode(olderTechnicalHtml);
  const olderPolicyPage = decode(olderPolicyHtml);
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
    fail('older Education tab did not render the saved topic list');
  }
  if (!olderBusinessPage.includes(olderBusiness.summary) || olderBusinessPage.includes(olderEdtech.summary)) {
    fail('older Business tab did not render the saved topic list');
  }
  for (const saved of [olderTechnical, olderTechnicalExtra, olderTechnicalThird]) {
    if (!olderTechnicalPage.includes(saved.summary)) fail(`older Technical tab dropped ${saved.id}`);
  }
  if (olderTechnicalPage.includes(olderBusiness.summary) || olderTechnicalPage.includes(olderPolicy.summary)) {
    fail('older Technical tab included a saved card from another topic');
  }
  if (!olderPolicyPage.includes(olderPolicy.summary) || olderPolicyPage.includes(olderTechnical.summary)) {
    fail('older Policy and Safety tab did not render only its saved card');
  }
  const policyStampLabel = olderPolicyPage.match(
    /<time datetime="2026-10-03T03:00:18Z">([^<]*)<\/time>/,
  )?.[1]?.trim();
  if (policyStampLabel?.includes('Oct 3')) {
    fail('Policy and Safety card 2026-10-03T03:00:18Z renders as Oct 3');
  }
  if (policyStampLabel !== 'Oct 2, 2026') {
    fail(`Policy and Safety card 2026-10-03T03:00:18Z shows ${policyStampLabel ?? 'nothing'}`);
  }
  const policyDateOnlyLabel = olderPolicyPage.match(/<time datetime="2026-10-03">([^<]*)<\/time>/)?.[1]?.trim();
  if (policyDateOnlyLabel !== 'Oct 3, 2026') {
    fail(`Policy and Safety date-only card shows ${policyDateOnlyLabel ?? 'nothing'}`);
  }
  for (const html of [olderBriefing, olderEdtechPage, olderBusinessPage, olderTechnicalPage, olderPolicyPage]) {
    for (const label of tabLabels) {
      if (!html.includes(`>${label}<`)) fail(`older week hid the ${label} tab`);
    }
  }
  const olderNav = readPage('digest/2026-W39/index.html');
  for (const href of [
    '/digest/2026-W39/edtech',
    '/digest/2026-W39/business',
    '/digest/2026-W39/technical',
    '/digest/2026-W39/policy-and-safety',
  ]) {
    if (!olderNav.includes(`href="${href}"`)) fail(`older week tab does not link to ${href}`);
  }
  if (!olderNav.includes('← Latest week')) fail('older week is missing the link back to the latest week');
  assertBuiltChrome('fixture');
} finally {
  for (const path of Object.keys(fixtureFiles)) {
    if (fixtureOriginals.has(path)) writeFileSync(path, fixtureOriginals.get(path));
    else rmSync(path, { force: true });
  }
  rebuild();
}

const throwawayIds = ['1999-W01', '2026-W39', '2026-W41', '2027-W01', '2020-W01'];
const leftoverFiles = Object.keys(fixtureFiles).filter((path) => !fixtureOriginals.has(path) && existsSync(path));
const leftoverDist = throwawayIds.filter((id) => !originalWeekIds.has(id) && existsSync(`dist/digest/${id}`));
if (leftoverFiles.length > 0 || leftoverDist.length > 0) fail('throwaway week fixtures were left behind');
const rebuiltLatest = selectLatestPublished(loadDigestWeeks(), readerNow());
if (!rebuiltLatest) fail('rebuilt site has no published week');
if (rebuiltLatest.week_id !== latest.week_id) {
  fail(`rebuilt latest week is ${rebuiltLatest.week_id}; the check started on ${latest.week_id}`);
}
assertDegradedHits(
  readPage('business/index.html'),
  renderedCopy(sectionCards(rebuiltLatest, 'business')),
  'rebuilt business',
);
assertBuiltChrome('rebuilt');

console.log(`reader check passed for latest ${latest.week_id} and archive ${WEEK_ID}`);
