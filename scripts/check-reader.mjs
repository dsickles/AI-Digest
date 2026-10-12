import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
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
import { storyPlacementErrors } from '../src/lib/story-groups.mjs';
import { alsoSeenFillerKind, visibleAlsoSeen } from '../src/lib/also-seen.mjs';

const DEGRADED_BODY = "The summary couldn't be generated this week.";
const WEEK_ID = '2026-W40';
const DIST = 'dist';
let builtAsOf = readerNow();

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

function alsoSeenBlock(html) {
  return html.match(/<aside\b[^>]*\bid="also-seen"[^>]*>[\s\S]*?<\/aside>/)?.[0] ?? '';
}

function assertBriefingOmitsAlsoSeen(html, label) {
  if (html.includes('id="also-seen"') || html.includes('class="also-label"') || /\bAlso seen\b/.test(decode(html))) {
    fail(`${label} shows Also seen`);
  }
}

function assertTopicAlsoSeen(html, items, label) {
  const block = alsoSeenBlock(html);
  const headings = html.match(/class="also-label"/g)?.length ?? 0;
  if (items.length === 0) {
    if (block || headings !== 0 || html.includes('id="also-seen"') || /\bAlso seen\b/.test(decode(html))) {
      fail(`${label} shows Also seen with no thin items`);
    }
    return;
  }
  if (headings !== 1 || !block) fail(`${label} should show Also seen once`);
  if (!/<h2\b[^>]*class="also-label"[^>]*>\s*Also seen\s*<\/h2>/.test(block)) {
    fail(`${label} Also seen label is missing`);
  }
  const parts = splitFooter(html);
  const mainIds = articleIds(parts.main, 'card');
  const lastMain = mainIds.length === 0 ? -1 : html.indexOf(`id="${mainIds[mainIds.length - 1]}"`);
  const asideAt = html.indexOf('id="also-seen"');
  if (lastMain !== -1 && asideAt < lastMain) fail(`${label} Also seen is not at the bottom`);
  assertOrder(block, 'thin', items, `${label} Also seen`);
  for (const title of cardTitles(block)) {
    if (alsoSeenFillerKind({ title })) fail(`${label} Also seen includes ${title}`);
  }
  for (const item of items) {
    if (alsoSeenFillerKind(item)) fail(`${label} Also seen includes ${item.title}`);
    assertCard(block, item);
    const article = extractArticle(block, item.id);
    if (article.includes('section-label')) fail(`${label} ${item.id} still has a section label`);
    if (article.includes('class="summary"')) fail(`${label} ${item.id} thin link shows a summary`);
    if (parts.main.includes(`id="${item.id}"`)) fail(`${label} moved thin item ${item.id} into the main list`);
  }
}

function cardTitles(html) {
  return [...html.matchAll(/<h3\b[^>]*class="[^"]*\bcard-title\b[^"]*"[^>]*>([\s\S]*?)<\/h3>/g)].map((match) =>
    decode(match[1].replace(/<[^>]*>/g, '')).replace(/\s+/g, ' ').trim(),
  );
}

function topicAlsoSeen(weekDoc, topicId) {
  return footerCards(weekDoc).filter((card) => card?.category === topicId);
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
  assertCoverage(article, card);
  assertTakeaway(article, card);
}

function assertTakeaway(article, card) {
  const markers = [...article.matchAll(/<p class="takeaway">([\s\S]*?)<\/p>/g)];
  if (card.summary_status === 'thin' || typeof card.takeaway !== 'string') {
    if (markers.length !== 0) fail(`${card.id} shows a takeaway the file does not have`);
    return;
  }
  if (markers.length !== 1) fail(`${card.id} takeaway is missing`);
  const shown = decode(markers[0][1]).replace(/\s+/g, ' ').trim();
  const expected = card.takeaway.replace(/\s+/g, ' ').trim();
  if (shown !== expected) fail(`${card.id} takeaway does not match the file`);
  const takeawayAt = markers[0].index ?? article.indexOf(markers[0][0]);
  const metaAt = article.search(/<p\b[^>]*\bclass="[^"]*\bmeta\b/);
  if (metaAt === -1 || takeawayAt < metaAt) fail(`${card.id} takeaway is not under the meta line`);
  const panelAt = article.search(/<div class="summary-panel"/);
  const summaryAt = article.search(/<p class="summary">/);
  const boundary = [panelAt, summaryAt].filter((index) => index !== -1).sort((a, b) => a - b)[0];
  if (boundary !== undefined && takeawayAt > boundary) {
    fail(`${card.id} takeaway is not visible while Summary is closed`);
  }
  if (panelAt !== -1 && article.slice(panelAt).includes('class="takeaway"')) {
    fail(`${card.id} takeaway is inside the summary panel`);
  }
}

function assertCoverage(article, card) {
  const decoded = decode(article);
  const links = Array.isArray(card.also_covered) ? card.also_covered : [];
  if (card.number_note) {
    if (!article.includes('class="number-note"') || !decoded.includes(card.number_note)) {
      fail(`${card.id} is missing its number disagreement note`);
    }
  } else if (article.includes('class="number-note"')) {
    fail(`${card.id} shows a number note the file does not have`);
  }
  if (links.length === 0) {
    if (decoded.includes('Also covered by')) fail(`${card.id} shows Also covered by with no other sources`);
    return;
  }
  if (!decoded.includes('Also covered by')) fail(`${card.id} is missing Also covered by`);
  for (const link of links) {
    if (!article.includes(`href="${link.url}"`)) fail(`${card.id} is missing also covered link ${link.url}`);
    if (!article.includes('target="_blank"') || !article.includes('rel="noopener noreferrer"')) {
      fail(`${card.id} also covered link is missing target or rel`);
    }
    if (!decoded.includes(link.publisher.name)) fail(`${card.id} also covered link is missing ${link.publisher.name}`);
  }
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

function assertReaderChrome(html, label, file = '') {
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
  const sectionLabels = sectionAnchors(sections).map((anchor) => anchor.label);
  if (sectionLabels.join('|') !== SECTION_LABELS.join('|')) {
    fail(`${label} sections are ${sectionAnchors(sections).map((anchor) => `${anchor.label} ${anchor.count ?? ''}`).join(', ') || 'missing'}`);
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
  if (header.includes('\u2014')) fail(`${label} header copy contains an em dash`);
  const weekLine = html.match(/<p\b[^>]*class="[^"]*\bweek-line\b[^"]*"[^>]*>[\s\S]*?<\/p>/)?.[0];
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
  assertSectionCounts(html, file, label);
  assertTitle(html, file, label);
}

const ICON_SHA256 = {
  'favicon.svg': '66b0d4fe033afd2160dea476be35c10424d8f6d5bec9edbecacf3626e5ded6f3',
  'favicon-32.png': '6abed1b8715d817ee214cab76db3b4732de94000f090bc9170f71487160488f3',
  'favicon-16.png': 'fa9146ee507c367ef046f8e978ef0cedcb46e3e59904e255a10a422254d9a830',
  'apple-touch-icon.png': 'af3f6e6e141281216972964be3f592bff1217f5c917111e39f6b6098e514cb26',
  'icon-512.png': '17371d042f1a311b555b644e7be696a26329e41c491e0ea7010cb402973229e3',
};

const ICON_HEAD = [
  '<link rel="icon" type="image/svg+xml" href="/favicon.svg"',
  '<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png"',
  '<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png"',
  '<link rel="apple-touch-icon" href="/apple-touch-icon.png"',
  '<link rel="manifest" href="/site.webmanifest"',
  '<meta name="theme-color" content="#08090a"',
];

const STALE_ICONS = ['favicon.ico', 'favicon.png'];
let iconFilesLogged = false;

function sha256File(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function assertIconFiles() {
  for (const [name, expected] of Object.entries(ICON_SHA256)) {
    const path = join('public', name);
    if (!existsSync(path)) fail(`missing ${path}`);
    const actual = sha256File(path);
    if (actual !== expected) fail(`${path} sha256 is ${actual}; expected the approved asset`);
    const distPath = join(DIST, name);
    if (!existsSync(distPath)) fail(`missing ${distPath}`);
    const built = sha256File(distPath);
    if (built !== expected) fail(`${distPath} sha256 is ${built}; expected the approved asset`);
  }
  for (const name of STALE_ICONS) {
    if (existsSync(join('public', name)) || existsSync(join(DIST, name))) fail(`old icon file ${name} is still present`);
  }
  const manifestPath = 'public/site.webmanifest';
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  if (manifest.name !== "Dan's AI Digest" || manifest.short_name !== 'AI Digest') {
    fail('site.webmanifest name or short_name is wrong');
  }
  if (manifest.background_color !== '#08090a' || manifest.theme_color !== '#08090a') {
    fail('site.webmanifest colors are not #08090a');
  }
  const icons = Array.isArray(manifest.icons) ? manifest.icons : [];
  const icon512 = icons.find((icon) => icon.src === '/icon-512.png' && icon.sizes === '512x512');
  const icon180 = icons.find((icon) => icon.src === '/apple-touch-icon.png' && icon.sizes === '180x180');
  if (!icon512 || !icon180) fail('site.webmanifest is missing the 512 or 180 icon');
  const distManifest = join(DIST, 'site.webmanifest');
  if (!existsSync(distManifest) || !readFileSync(distManifest).equals(readFileSync(manifestPath))) {
    fail('built site.webmanifest does not match public/site.webmanifest');
  }
  if (!iconFilesLogged) {
    console.log('site icon files match the approved sha256 hashes');
    iconFilesLogged = true;
  }
}

function assertIconHead(html, label) {
  const head = html.match(/<head\b[^>]*>([\s\S]*?)<\/head>/)?.[1];
  if (!head) fail(`${label} is missing a head`);
  for (const tag of ICON_HEAD) {
    if (!head.includes(tag)) fail(`${label} head is missing ${tag}`);
  }
  if (/favicon\.ico|rel="shortcut icon"/i.test(head)) fail(`${label} still has an old favicon tag`);
}

function assertBuiltChrome(scope) {
  const files = walk(DIST);
  if (files.length === 0) fail(`${scope} produced no HTML`);
  assertIconFiles();
  assertProgramCss(readFileSync(files[0], 'utf8'), scope);
  for (const file of files) {
    const html = readFileSync(file, 'utf8');
    assertIconHead(html, `${scope} ${file}`);
    assertReaderChrome(html, `${scope} ${file}`, file);
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

function isShownStory(card) {
  return card?.included !== false && card?.summary_status !== 'thin';
}

function briefingCards(weekDoc) {
  return (weekDoc.briefing?.top ?? []).filter(isShownStory);
}

function footerCards(weekDoc) {
  return visibleAlsoSeen(weekDoc.footer_aside);
}

// Topic tabs render included topic cards only. The tab number counts those main items.
// Thin Also seen links stay off the number.
function sectionCards(weekDoc, topicId) {
  const list = weekDoc.topics?.[topicId];
  return Array.isArray(list) ? list.filter(isShownStory) : [];
}

function readerFacingText(weeks) {
  return weeks
    .flatMap((item) => [
      item.briefing?.synthesis,
      ...[...(item.main_feed ?? []), ...(item.footer_aside ?? []), ...(item.briefing?.top ?? [])].flatMap((card) => [
        card.title,
        card.takeaway,
        card.summary,
        card.body,
        card.number_note,
        card.publisher?.name,
        ...(card.also_covered ?? []).flatMap((link) => [link.title, link.publisher?.name]),
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

function stylesheetText(html) {
  const chunks = [...html.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)].map((match) => match[1]);
  for (const match of html.matchAll(/<link\b[^>]*href="([^"]+\.css)"[^>]*>/g)) {
    const href = match[1];
    if (/^https?:/i.test(href)) continue;
    const path = join(DIST, href.replace(/^\//, ''));
    if (existsSync(path)) chunks.push(readFileSync(path, 'utf8'));
  }
  return chunks.join('\n');
}

function emptyRuleIsDimmed(html) {
  const css = stylesheetText(html).replace(/\/\*[\s\S]*?\*\//g, '');
  return [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].some((match) => {
    const selectors = match[1].split(',').map((selector) => selector.trim());
    return selectors.length === 1 && selectors[0] === '.empty' && /color:\s*var\(--ink-3\)/.test(match[2]);
  });
}

function compactCss(css) {
  let out = '';
  let quote = '';
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, '');
  for (let index = 0; index < stripped.length; index += 1) {
    const ch = stripped[index];
    if (quote) {
      out += ch;
      if (ch === quote && stripped[index - 1] !== '\\') quote = '';
      continue;
    }
    if (ch === '"' || ch === "'") {
      quote = ch;
      out += ch;
      continue;
    }
    if (/\s/.test(ch)) continue;
    out += ch;
  }
  return out;
}

function ruleBody(css, selector) {
  const forms = [
    selector,
    selector.replace(/::/g, ':'),
    selector.replace(/"/g, ''),
    selector.replace(/::/g, ':').replace(/"/g, ''),
  ];
  const haystacks = [css, css.replace(/"/g, '')];
  for (const haystack of haystacks) {
    for (const form of forms) {
      const needle = `${form.replace(/\s+/g, '')}{`;
      let from = 0;
      while (from < haystack.length) {
        const start = haystack.indexOf(needle, from);
        if (start === -1) break;
        const prev = start === 0 ? '{' : haystack[start - 1];
        if (start === 0 || prev === '{' || prev === '}' || prev === ',') {
          const open = start + needle.length - 1;
          return haystack.slice(open + 1, haystack.indexOf('}', open));
        }
        from = start + needle.length;
      }
    }
  }
  return '';
}

function mediaBody(css, query) {
  const queries = Array.isArray(query) ? query : [query];
  for (const item of queries) {
    const token = `@media(${item.replace(/\s+/g, '')})`;
    const start = css.indexOf(token);
    if (start === -1) continue;
    const open = css.indexOf('{', start);
    let depth = 0;
    for (let index = open; index < css.length; index += 1) {
      if (css[index] === '{') depth += 1;
      else if (css[index] === '}') {
        depth -= 1;
        if (depth === 0) return css.slice(open + 1, index);
      }
    }
  }
  return '';
}

function pageTopic(file) {
  const normalized = String(file).replaceAll('\\', '/');
  const match = normalized.match(/(?:^|\/)(business|technical|edtech|policy-and-safety)\/index\.html$/);
  return match?.[1] ?? null;
}

function pageTitle(html) {
  return decode(html.match(/<title>([\s\S]*?)<\/title>/)?.[1] ?? '').replace(/\s+/g, ' ').trim();
}

function topicCount(doc, id) {
  return sectionCards(doc, id).length;
}

function asideCount(doc, id) {
  return footerCards(doc).filter((card) => card?.category === id).length;
}

function readWeekDoc(weekId) {
  const path = `content/digests/${weekId}.json`;
  if (!existsSync(path)) fail(`missing week ${weekId} while checking section counts`);
  return JSON.parse(readFileSync(path, 'utf8'));
}

function weekForChrome(briefingHref) {
  if (briefingHref === '/') {
    const docs = readdirSync('content/digests')
      .filter((name) => name.endsWith('.json'))
      .map((name) => JSON.parse(readFileSync(join('content/digests', name), 'utf8')));
    const selected = selectLatestPublished(docs, builtAsOf);
    if (!selected) fail('section counts have no published week');
    return selected;
  }
  const match = briefingHref?.match(/^\/digest\/(\d{4}-W\d{2})$/);
  if (!match) return null;
  return readWeekDoc(match[1]);
}

function sectionAnchors(block) {
  const anchors = [];
  for (const match of block.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/g)) {
    const attrs = match[1];
    const inner = match[2];
    const className = attrs.match(/\bclass="([^"]*)"/)?.[1] ?? '';
    const count = inner.match(/<span\b[^>]*\bclass="[^"]*\bn\b[^"]*"[^>]*>(\d+)<\/span>/);
    anchors.push({
      label: decode(inner.replace(/<span\b[\s\S]*<\/span>/g, '')).replace(/\s+/g, ' ').trim(),
      count: count ? Number(count[1]) : null,
      href: attrs.match(/\bhref="([^"]*)"/)?.[1] ?? '',
      current: /\baria-current="page"/.test(attrs),
      zero: className.split(/\s+/).includes('zero'),
    });
  }
  return anchors;
}

function assertSectionCounts(html, file, label) {
  const sections = navBlock(html, 'nav-sections');
  const briefing = navBlock(html, 'nav-briefing');
  const anchors = sectionAnchors(sections);
  if (anchors.length !== SECTION_IDS.length) fail(`${label} is missing a section story count`);
  const doc = weekForChrome(linkHrefs(briefing)[0]);
  if (!doc) fail(`${label} section counts have no week`);
  const topicOnPage = pageTopic(file);
  const rendered = topicOnPage ? articleIds(splitFooter(html).main, 'card').length : null;
  anchors.forEach((anchor, index) => {
    const id = SECTION_IDS[index];
    const name = SECTION_LABELS[index];
    if (anchor.label !== name || anchor.count === null) {
      fail(`${label} ${name} is missing its story count`);
    }
    const mainFeed = topicCount(doc, id);
    const aside = asideCount(doc, id);
    if (aside > 0 && anchor.count === mainFeed + aside) fail(`${label} ${name} counts Also seen items`);
    if (anchor.count !== mainFeed) {
      fail(`${label} ${name} count is ${anchor.count} but the main feed has ${mainFeed}`);
    }
    if (topicOnPage === id && anchor.count !== rendered) {
      fail(`${label} ${name} count is ${anchor.count} but the page renders ${rendered} main-feed stories`);
    }
    if (anchor.count === 0 && !anchor.zero) fail(`${label} zero section ${name} is not muted`);
    if (anchor.count > 0 && anchor.zero) fail(`${label} ${name} is muted with ${anchor.count} stories`);
    if (topicOnPage === id && !anchor.current) {
      fail(`${label} ${anchor.count === 0 ? 'zero ' : ''}${name} lost its active marker`);
    }
    if (anchor.href !== linkHrefs(sections)[index]) fail(`${label} ${name} count sits on the wrong link`);
  });
}

function assertTitle(html, file, label) {
  const title = pageTitle(html);
  const topic = pageTopic(file);
  const normalized = String(file).replaceAll('\\', '/');
  if (topic) {
    const name = SECTION_LABELS[SECTION_IDS.indexOf(topic)];
    if (title !== `Dan's AI Digest: ${name}`) fail(`${label} title is "${title}"`);
    return;
  }
  if (/(?:^|\/)archive\/index\.html$/.test(normalized)) {
    if (title !== "Dan's AI Digest: Archive") fail(`${label} title is "${title}"`);
    return;
  }
  if (title !== "Dan's AI Digest") fail(`${label} title is "${title}"`);
}

function assertTopicRanks(html, cards, label) {
  const main = splitFooter(html).main;
  const opens = [...main.matchAll(/<ol\b([^>]*\bclass="[^"]*\brows\b[^"]*"[^>]*)>/g)];
  if (cards.length === 0) {
    if (opens.length !== 0) fail(`${label} empty topic rendered a ranked list`);
    return;
  }
  const expected = cards.length === 1 ? 1 : 2;
  if (opens.length !== expected) fail(`${label} has ${opens.length} topic lists; expected ${expected}`);
  const starts = opens.map((match) => Number(match[1].match(/\bstart="(\d+)"/)?.[1] ?? '1'));
  const mid = Math.ceil(cards.length / 2);
  if (starts[0] !== 1) fail(`${label} first topic list starts at ${starts[0]}`);
  if (expected === 2 && starts[1] !== mid + 1) {
    fail(`${label} second topic list starts at ${starts[1]}; expected ${mid + 1}`);
  }
  if (expected === 2) {
    const reset = opens[1][1].match(/counter-reset:\s*topic-rank\s+(\d+)/);
    if (!reset || Number(reset[1]) !== mid) fail(`${label} rank does not continue across the two lists`);
  }
  const ids = opens.flatMap((match) => {
    const list = main.slice(match.index).match(/<ol\b[^>]*>[\s\S]*?<\/ol>/);
    return list ? articleIds(list[0], 'card') : [];
  });
  if (ids.join(',') !== cards.map((card) => card.id).join(',')) {
    fail(`${label} topic list order is ${ids.join(', ') || 'empty'}`);
  }
  cards.forEach((card, index) => {
    const article = extractArticle(main, card.id);
    const meta = article.match(/<p\b[^>]*\bclass="[^"]*\bmeta\b[^"]*"[^>]*>([\s\S]*?)<\/p>/);
    if (!meta || !meta[0].includes(`datetime="${card.published_at}"`)) {
      fail(`${label} ${card.id} date is not on the meta line`);
    }
    if (/<time\b[^>]*class="[^"]*\bd\b/.test(article)) fail(`${label} ${card.id} still parks the date in the margin`);
    const toggle = article.match(/<button\b([^>]*)>([\s\S]*?)<\/button>/);
    if (!toggle) fail(`${label} ${card.id} is missing the Summary control`);
    const buttonText = decode(toggle[2].replace(/<[^>]*>/g, '')).replace(/\s+/g, ' ').trim();
    if (buttonText !== 'Summary') fail(`${label} ${card.id} Summary control reads "${buttonText}"`);
    if (!/\baria-expanded="false"/.test(toggle[1])) fail(`${label} ${card.id} Summary control does not start closed`);
    const controls = toggle[1].match(/\baria-controls="([^"]*)"/)?.[1];
    if (!controls || !article.includes(`id="${controls}"`)) {
      fail(`${label} ${card.id} Summary control does not point at its summary`);
    }
    if (!/viewBox="0 0 10 10"/.test(toggle[2]) || !/stroke-linecap="round"/.test(toggle[2])) {
      fail(`${label} ${card.id} Summary chevron is missing`);
    }
    if (article.includes('class="num"')) fail(`${label} ${card.id} uses a Top 5 numeral`);
    if (ids[index] !== card.id) fail(`${label} rank ${index + 1} is not ${card.id}`);
  });
}

function assertProgramCss(html, label) {
  const css = compactCss(stylesheetText(html));
  for (const token of [
    '--ground:#08090a',
    '--ink:#f2f3f4',
    '--ink-2:#c3c7cb',
    '--ink-3:#8f949a',
    '--mute:#777b82',
    '--rule:#202225',
    '--rule-strong:#34373b',
    '--signal:#ff4b2b',
  ]) {
    if (!css.includes(token)) fail(`${label} design token ${token} is missing`);
  }
  if (!css.includes('--sans:"Host Grotesk","Helvetica Neue",Arial,sans-serif')) {
    fail(`${label} is missing Host Grotesk`);
  }
  if (!ruleBody(css, 'body').includes('font-family:var(--sans)')) fail(`${label} body is not Host Grotesk`);
  const mast = ruleBody(css, '.mast');
  if (!mast.includes('font-weight:700') || !mast.includes('font-size:clamp(38px,7vw,104px)')) {
    fail(`${label} masthead is not Host Grotesk 700 at the program size`);
  }
  const numeral = ruleBody(css, '.num');
  if (!numeral.includes('color:var(--signal)') || !numeral.includes('font-size:88px')) {
    fail(`${label} Top 5 numeral is not the vermilion program figure`);
  }
  if (css.includes('.index')) fail(`${label} Top 5 index styles are still present`);
  const leadPlace = ruleBody(css, '.syn > .lead');
  const leadBesideThemes =
    leadPlace.includes('grid-column:1/9') || leadPlace.includes('grid-area:1/1/auto/9');
  if (!leadBesideThemes) fail(`${label} lead line is not in the left columns`);
  const themePlace = ruleBody(css, '.syn > .themes');
  const themesBesideLead =
    (themePlace.includes('grid-column:9/13') && themePlace.includes('grid-row:1')) ||
    themePlace.includes('grid-area:1/9/auto/13') ||
    themePlace.includes('grid-area:1/9/span2/13');
  if (!themesBesideLead) fail(`${label} theme rows do not sit beside the lead`);
  const storyBox = ruleBody(css, '.story');
  if (!storyBox.includes('break-inside:avoid') || !storyBox.includes('list-style:none')) {
    fail(`${label} a Top 5 story can split across columns or show a list marker beside the numeral`);
  }
  const rank = ruleBody(css, '.row::before');
  if (!rank.includes('content:counter(topic-rank)') || !rank.includes('color:var(--ink-3)')) {
    fail(`${label} topic rank is not the grey list position`);
  }
  if (rank.includes('var(--signal)') || rank.includes('decimal-leading-zero')) {
    fail(`${label} topic rank uses vermilion or zero padding`);
  }
  const rowsets = ruleBody(css, '.rowsets');
  if (!rowsets.includes('grid-template-columns:repeat(2,minmax(0,1fr))')) {
    fail(`${label} topic page is not two side-by-side lists`);
  }
  const flow = ruleBody(css, '.flow');
  if (!flow.includes('columns:2') || !flow.includes('column-gap:48px')) {
    fail(`${label} Top 5 does not flow in two columns`);
  }
  const bar = ruleBody(css, '.bar');
  if (!bar.includes('border-top:1pxsolidvar(--rule-strong)')) fail(`${label} masthead hairline is missing`);
  if (!ruleBody(css, '.row').includes('border-bottom:1pxsolidvar(--rule)')) {
    fail(`${label} topic rows are missing hairlines`);
  }
  const chevron = ruleBody(css, '.toggle[aria-expanded="true"] svg');
  if (!chevron.includes('transform:rotate(180deg)') || !chevron.includes('color:var(--signal)')) {
    fail(`${label} open Summary chevron does not turn up in vermilion`);
  }
  if (!ruleBody(css, '.summary-panel').includes('grid-template-rows:0fr')) {
    fail(`${label} Summary does not collapse under its title`);
  }
  const tablet = mediaBody(css, ['max-width:1080px', 'width<=1080px']);
  if (!tablet.includes('.flow{columns:1}') || !tablet.includes('.rowsets{grid-template-columns:1fr}')) {
    fail(`${label} mid-width layout does not drop to one column`);
  }
  const themesStack =
    tablet.includes('.syn>.themes') &&
    ((tablet.includes('grid-column:1/-1') && tablet.includes('grid-row:auto')) ||
      tablet.includes('grid-area:auto/1/auto/-1'));
  if (!themesStack) fail(`${label} theme rows do not drop under the lead on a narrow window`);
  if (tablet.includes('.index')) fail(`${label} narrow window still styles the Top 5 index`);
  const play = ruleBody(css, '.play');
  if (!play.includes('width:1.1em') || !play.includes('height:1.1em') || !play.includes('color:var(--ink-2)')) {
    fail(`${label} play icon is not the 1.1em ink mark`);
  }
  const motion = mediaBody(css, 'prefers-reduced-motion:reduce');
  if (!motion.includes('transition:none!important')) fail(`${label} reduced motion still animates`);
  const zero = ruleBody(css, '.nav a.zero[aria-current="page"]');
  if (!zero.includes('border-bottom-color:var(--signal)')) {
    fail(`${label} zero-count current section loses the active underline`);
  }
  const bare = css.replace(/"/g, '');
  if (!bare.includes('.nava.zero[aria-current=page],.nava.zero[aria-current=page].n{color:var(--mute)}')) {
    fail(`${label} zero-count current section does not stay muted`);
  }
  if (/\bblue\b/i.test(stylesheetText(html)) || stylesheetText(html).includes('#7eb6ff')) {
    fail(`${label} stylesheet uses blue`);
  }
  if (!html.includes('Host+Grotesk')) fail(`${label} does not load Host Grotesk`);
  const sectionLabel = ruleBody(css, '.also-label');
  if (
    !sectionLabel.includes('font-family:var(--sans)') ||
    !sectionLabel.includes('font-size:12px') ||
    !sectionLabel.includes('font-weight:600') ||
    !(sectionLabel.includes('letter-spacing:0.08em') || sectionLabel.includes('letter-spacing:.08em')) ||
    !sectionLabel.includes('text-transform:uppercase') ||
    !sectionLabel.includes('color:var(--ink-3)')
  ) {
    fail(`${label} Also seen section label is not the grey uppercase program label`);
  }
  if (
    sectionLabel.includes('background') ||
    sectionLabel.includes('var(--signal)') ||
    sectionLabel.includes('border-radius')
  ) {
    fail(`${label} Also seen section label is a colored chip`);
  }
  assertPhoneCss(css, label);
}

function assertPhoneCss(css, label) {
  const phone = mediaBody(css, ['max-width:720px', 'width<=720px']);
  if (!phone) fail(`${label} phone layout is missing`);
  const mast = ruleBody(phone, '.mast');
  if (!mast.includes('font-size:clamp(30px,10.4vw,52px)') || !mast.includes('white-space:nowrap')) {
    fail(`${label} masthead does not stay on one line at phone width`);
  }
  if (!ruleBody(phone, '.bar').includes('display:block')) {
    fail(`${label} week line does not move onto its own line at phone width`);
  }
  if (!ruleBody(phone, '.bar .right').includes('margin-top:2px')) {
    fail(`${label} Updated and Archive do not sit on the line under the week`);
  }
  if (!ruleBody(phone, '.nav-sections').includes('grid-template-columns:1fr')) {
    fail(`${label} sections do not stack at phone width`);
  }
  if (!ruleBody(phone, '.row').includes('grid-template-columns:36pxminmax(0,1fr)')) {
    fail(`${label} topic rank is not in the 36px margin`);
  }
  if (!ruleBody(phone, '.num').includes('font-size:48px')) {
    fail(`${label} Top 5 numeral is not 48px at phone width`);
  }
  if (phone.includes('.index')) fail(`${label} phone still styles the Top 5 index`);
  if (!ruleBody(phone, '.page-title').includes('font-size:40px')) {
    fail(`${label} phone topic title is not 40px`);
  }
  const phoneToggle = ruleBody(phone, '.row .toggle');
  if (!phoneToggle.includes('grid-row:2')) {
    fail(`${label} Summary control does not drop under the title at phone width`);
  }
  if (
    !phoneToggle.includes('padding:var(--s2)var(--s2)var(--s2)0') ||
    !phoneToggle.includes('margin-bottom:calc(-1*var(--s2))')
  ) {
    fail(`${label} Summary control tap target is shorter than the reference padding`);
  }
  const briefingToggle = ruleBody(phone, '.briefing-full .toggle');
  if (!briefingToggle.includes('min-height:34px') || !briefingToggle.includes('padding:var(--s2)var(--s2)var(--s2)0')) {
    fail(`${label} Read the full briefing tap target is shorter than 34px`);
  }
  const alsoRow = ruleBody(css, '.topic > .also');
  if (!alsoRow.includes('grid-column:1/-1')) {
    fail(`${label} Also seen does not span the topic tab`);
  }
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
      `${where} ${topic.label} tab shows ${shown.length} main stories; the week file has ${cards.length}`,
    );
  }
  assertOrder(parts.main, 'card', cards, `${where} ${topic.label}`);
  for (const card of cards) assertCard(parts.main, card);
  assertTopicRanks(html, cards, `${where} ${topic.label}`);
  assertTopicAlsoSeen(html, topicAlsoSeen(weekDoc, topic.id), `${where} ${topic.label}`);
  assertDimmedEmptyState(html, topic.label, cards.length === 0, where);
  assertDegradedHits(html, renderedCopy(cards), `${where} ${topic.label}`);
}

function themeHref(weekDoc, id) {
  if ((weekDoc.briefing.top ?? []).some((card) => card.id === id)) return `#${id}`;
  const card = (weekDoc.main_feed ?? []).find((item) => item.id === id);
  if (!card) return null;
  return `/digest/${weekDoc.week_id}/${card.category}#${id}`;
}

function assertBriefingScan(html, weekDoc, where) {
  const themes = weekDoc.briefing.themes;
  const hasScan = typeof weekDoc.briefing.lead === 'string' && Array.isArray(themes) && themes.length > 0;
  if (!hasScan) {
    if (html.includes('Read the full briefing')) fail(`${where} shows Read the full briefing without theme data`);
    if (html.includes('class="lead"') || html.includes('class="theme"')) {
      fail(`${where} shows a lead line or theme row without theme data`);
    }
    if (!html.includes('class="synthesis"')) fail(`${where} briefing dropped the synthesis paragraph`);
    return;
  }
  if (themes.length < 4 || themes.length > 6) fail(`${where} has ${themes.length} themes; expected 4 to 6`);
  const lead = html.match(/<p class="lead">([\s\S]*?)<\/p>/);
  if (!lead || decode(lead[1]).trim() !== weekDoc.briefing.lead) fail(`${where} lead line does not match the week file`);
  if (html.includes('class="synthesis"')) fail(`${where} still shows the synthesis as the open paragraph`);
  const rows = [...html.matchAll(/<li class="theme">([\s\S]*?)<\/li>/g)];
  if (rows.length !== themes.length) fail(`${where} shows ${rows.length} theme rows; the file has ${themes.length}`);
  themes.forEach((theme, index) => {
    const row = decode(rows[index][1]);
    if (!row.includes(theme.label)) fail(`${where} theme ${index + 1} is missing its label`);
    if (!row.includes(theme.sentence)) fail(`${where} theme ${index + 1} is missing its sentence`);
    const hrefs = [...rows[index][1].matchAll(/href="([^"]+)"/g)].map((match) => match[1]);
    const expected = theme.story_ids.map((id) => themeHref(weekDoc, id));
    if (hrefs.join('|') !== expected.join('|')) {
      fail(`${where} theme ${theme.label} links ${hrefs.join(', ') || 'nothing'}`);
    }
    if (new Set(hrefs).size !== hrefs.length) fail(`${where} theme ${theme.label} links two copies of the same story`);
    for (const id of theme.story_ids) {
      if (!(weekDoc.main_feed ?? []).some((card) => card.id === id)) {
        fail(`${where} theme ${theme.label} does not link the merged main item ${id}`);
      }
    }
  });
  const button = html.match(/<button\b([^>]*)>([\s\S]*?)<\/button>/);
  if (!button) fail(`${where} is missing Read the full briefing`);
  const buttonText = decode(button[2].replace(/<[^>]*>/g, '')).replace(/\s+/g, ' ').trim();
  if (buttonText !== 'Read the full briefing') fail(`${where} briefing toggle reads "${buttonText}"`);
  if (!/\baria-expanded="false"/.test(button[1])) fail(`${where} Read the full briefing does not start closed`);
  if (/\bclass="briefing-full open"/.test(html)) fail(`${where} full briefing starts open`);
  const controls = button[1].match(/\baria-controls="([^"]*)"/)?.[1];
  if (!controls) fail(`${where} Read the full briefing is missing aria-controls`);
  const panel = html.match(new RegExp(`<div class="summary-panel" id="${controls}">([\\s\\S]*?)</div>`));
  if (!panel || !decode(panel[1]).includes(weekDoc.briefing.synthesis)) {
    fail(`${where} full briefing toggle does not hold the synthesis`);
  }
  if (!/viewBox="0 0 10 10"/.test(button[2]) || !/stroke-linecap="round"/.test(button[2])) {
    fail(`${where} Read the full briefing chevron does not match Summary`);
  }
  if (!button[2].includes('M1.75 3.25 5 6.75 8.25 3.25')) {
    fail(`${where} Read the full briefing chevron does not point down`);
  }
}

function visibleCopy(html) {
  const stripped = html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<span class="visually-hidden">[\s\S]*?<\/span>/g, ' ');
  return decode(stripped.replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();
}

function assertNoTopIndex(html, cards, where) {
  if (html.includes('class="index"')) fail(`${where} still shows the Top 5 index`);
  if (/class="k"/.test(html)) fail(`${where} still shows an index numeral`);
  if (/aria-label="Top \d+ this week"/.test(html)) fail(`${where} still labels a Top 5 index`);
  const copy = visibleCopy(html);
  for (const card of cards) {
    const hits = copy.split(card.title).length - 1;
    if (hits !== 1) fail(`${where} shows "${card.title}" ${hits} times`);
  }
}

function assertStoryNumber(article, card, rank, where) {
  const nums = [...article.matchAll(/<span\b([^>]*\bclass="num"[^>]*)>([\s\S]*?)<\/span>/g)];
  if (nums.length !== 1) fail(`${where} ${card.id} has ${nums.length} rank numerals`);
  const value = decode(nums[0][2]).replace(/\s+/g, '');
  if (value !== String(rank)) fail(`${where} ${card.id} rank numeral is not ${rank}`);
  if (!/\baria-hidden="true"/.test(nums[0][1])) {
    fail(`${where} ${card.id} exposes the numeral to a screen reader as well as the list marker`);
  }
  const withoutNum = article.replace(nums[0][0], ' ');
  const text = visibleCopy(withoutNum);
  const at = text.indexOf(card.title);
  if (at < 0) fail(`${where} ${card.id} is missing its title`);
  const before = text.slice(0, at);
  if (new RegExp(`(?:^|\\s)${rank}(?:\\s|\\.|$)`).test(before)) {
    fail(`${where} ${card.id} numbers the story twice`);
  }
}

function assertBriefingTab(html, weekDoc, where) {
  const cards = briefingCards(weekDoc);
  const parts = splitFooter(html);
  const shown = articleIds(parts.main, 'card');
  if (shown.length !== cards.length) {
    fail(`${where} briefing shows ${shown.length} stories; the file has ${cards.length}`);
  }
  const topLabel = `Top ${cards.length} this week`;
  if (!decode(parts.main).includes(topLabel)) {
    fail(`${where} briefing does not show ${topLabel}`);
  }
  if (!html.includes('aria-label="This week"')) fail(`${where} briefing is missing the synthesis region`);
  if (!/<ol class="stories">/.test(parts.main)) fail(`${where} Top 5 is not a single numbered list`);
  assertNoTopIndex(parts.main, cards, where);
  cards.forEach((card, index) => {
    const article = extractArticle(parts.main, card.id);
    assertStoryNumber(article, card, index + 1, where);
  });
  if (!decode(html).includes(weekDoc.briefing.synthesis)) fail(`${where} briefing is missing the synthesis`);
  assertBriefingScan(html, weekDoc, where);
  assertOrder(parts.main, 'card', cards, `${where} briefing`);
  for (const card of cards) assertCard(parts.main, card);
  assertBriefingOmitsAlsoSeen(html, where);
  assertDegradedHits(html, [weekDoc.briefing.synthesis, ...renderedCopy(cards)], `${where} briefing`);
}

function findShownCard(weekDoc, predicate) {
  const pools = [['briefing', briefingCards(weekDoc)], ...SECTION_TABS.map((topic) => [topic.id, sectionCards(weekDoc, topic.id)])];
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

function assertRubric(weekDoc, pageMap, where) {
  const rendered = [...briefingCards(weekDoc), ...SECTION_TABS.flatMap((topic) => sectionCards(weekDoc, topic.id)), ...footerCards(weekDoc)];
  const excluded = Array.isArray(weekDoc.excluded) ? weekDoc.excluded : [];
  const usesRubric = weekDoc.week_id >= '2026-W41' || rendered.some((card) => Object.hasOwn(card, 'include_reason')) || excluded.length > 0;
  if (!usesRubric) return;
  if (weekDoc.week_id >= '2026-W41' && !Array.isArray(weekDoc.excluded)) {
    fail(`${where} is missing the excluded list`);
  }
  for (const card of [...rendered, ...excluded]) {
    if (typeof card.included !== 'boolean') fail(`${where} ${card.id} is missing included`);
    if (typeof card.include_reason !== 'string' || card.include_reason.trim().length === 0 || /[\r\n]/.test(card.include_reason)) {
      fail(`${where} ${card.id} is missing a one-line include_reason`);
    }
  }
  for (const card of rendered) {
    if (card.included !== true) fail(`${where} rendered ${card.id} but included is not true`);
  }
  const html = Object.values(pageMap).join('\n');
  for (const card of excluded) {
    if (card.included !== false) fail(`${where} ${card.id} is in excluded but included is not false`);
    if (html.includes(`id="${card.id}"`)) fail(`${where} rendered excluded item ${card.id}`);
    if (cardTitles(html).includes(card.title)) fail(`${where} shows the excluded title ${card.title}`);
  }
  for (const card of footerCards(weekDoc)) {
    if (card.summary_status !== 'thin') fail(`${where} Also seen item ${card.id} is not thin`);
    if (pageMap.briefing.includes(`id="${card.id}"`)) fail(`${where} thin item ${card.id} is still on Briefing`);
    const article = extractArticle(pageMap[card.category], card.id);
    if (article.includes('class="summary"')) fail(`${where} thin item ${card.id} shows a summary`);
    if (article.includes('section-label')) fail(`${where} ${card.id} still has a section label`);
    for (const topic of SECTION_TABS) {
      if (topic.id !== card.category && pageMap[topic.id].includes(`id="${card.id}"`)) {
        fail(`${where} thin item ${card.id} appears on ${topic.label}`);
      }
    }
  }
  if (weekDoc.week_id !== '2026-W41') return;
  for (const title of [
    'AI Benchmarks are dead #AI #benchmarks #Google #Gemini #AInews',
    'llm-mistral 0.16',
    'Quoting Carson Gross',
  ]) {
    if (!excluded.some((card) => card.title === title)) fail(`2026-W41 did not exclude ${title}`);
  }
  const thinItems = footerCards(weekDoc);
  const thinVideo = thinItems.find((card) => card.media === 'video');
  const thinArticle = thinItems.find((card) => card.media !== 'video');
  if (!thinArticle) fail('2026-W41 Also seen is missing a thin article link');
  if (!thinVideo) fail('2026-W41 did not mark a description-only video as a thin Also seen link');
  const videoArticle = extractArticle(pageMap[thinVideo.category], thinVideo.id);
  if (!videoArticle.includes('class="play"')) fail(`${thinVideo.id} thin video is missing its play icon`);
}

function assertStoryGroups(weekDoc, pageMap, where) {
  if (weekDoc.week_id !== '2026-W41') return;
  const mathId = 'dont-worry-about-the-vase-new-math-from-openai';
  const claytonId = 'nextgov-fcw-experts-hope-new-ai-czars-leadership-can-move-the-needle-on-regulation';
  const math = (weekDoc.main_feed ?? []).find((card) => card.id === mathId);
  const clayton = (weekDoc.main_feed ?? []).find((card) => card.id === claytonId);
  if (!math || (math.also_covered ?? []).length !== 3) fail(`${where} OpenAI math release is not one item with three other sources`);
  if (!clayton || (clayton.also_covered ?? []).length !== 1) {
    fail(`${where} Jay Clayton appointment is not one item with its other source`);
  }
  if (!String(math.number_note).includes('722') || !String(math.number_note).includes('719')) {
    fail(`${where} math item must note 722 and 719`);
  }
  const policy = pageMap['policy-and-safety'];
  const briefing = pageMap.briefing;
  if (!policy || !briefing) fail(`${where} is missing Briefing or Policy and Safety HTML`);
  const policyMath = policy.match(new RegExp(`id="${mathId}"`, 'g'))?.length ?? 0;
  const policyClayton = policy.match(new RegExp(`id="${claytonId}"`, 'g'))?.length ?? 0;
  if (policyMath !== 1) fail(`${where} math item appears ${policyMath} times on Policy and Safety`);
  if (policyClayton !== 1) fail(`${where} Clayton item appears ${policyClayton} times on Policy and Safety`);
  if (briefing.includes(`id="${mathId}"`) || briefing.includes(`id="${claytonId}"`)) {
    fail(`${where} duplicated a grouped story onto Briefing`);
  }
  const absorbed = [
    'education-disrupted-ai-is-inventing-new-math-it-has-722-papers-to-show-for-it',
    'last-week-in-ai-last-week-in-ai-346-719-math-manuscripts-2-western-open-models-1-more-safety-resignation',
    'dont-worry-about-the-vase-ai-189-new-math',
    'tech-policy-press-an-ai-accord-a-new-czar-and-an-autonomous-warfare-command',
  ];
  for (const id of absorbed) {
    if (policy.includes(`id="${id}"`) || briefing.includes(`id="${id}"`)) fail(`${where} still renders ${id} as its own item`);
  }
  const mathArticle = extractArticle(policy, mathId);
  const claytonArticle = extractArticle(policy, claytonId);
  if (!decode(mathArticle).includes('Also covered by') || !decode(claytonArticle).includes('Also covered by')) {
    fail(`${where} grouped items are missing Also covered by`);
  }
  if (!decode(mathArticle).includes(math.number_note)) fail(`${where} Policy and Safety drops the 722 vs 719 note`);
  if (!decode(briefing).includes('722') || !decode(briefing).includes('719')) {
    fail(`${where} Briefing drops the 722 vs 719 note`);
  }
}

function assertItemSetPreserved(weekDoc, pageMap, where) {
  const thin = footerCards(weekDoc);
  const mains = SECTION_TABS.flatMap((topic) => sectionCards(weekDoc, topic.id));
  const ids = new Set();
  for (const card of [...mains, ...thin]) {
    if (ids.has(card.id)) fail(`${where} repeats ${card.id}`);
    ids.add(card.id);
    if (!pageMap[card.category]?.includes(`id="${card.id}"`)) fail(`${where} dropped ${card.id}`);
  }
  for (const card of briefingCards(weekDoc)) {
    if (!pageMap[card.category]?.includes(`id="${card.id}"`)) {
      fail(`${where} Top 5 item ${card.id} is missing from its topic tab`);
    }
  }
  let rendered = 0;
  for (const topic of SECTION_TABS) {
    const html = pageMap[topic.id];
    rendered += articleIds(splitFooter(html).main, 'card').length;
    rendered += articleIds(splitFooter(html).footer, 'thin').length;
  }
  if (rendered !== mains.length + thin.length) {
    fail(`${where} renders ${rendered} topic items; the file has ${mains.length + thin.length}`);
  }
}

function assertTakeawayCoverage(weekDoc, pageMap, where) {
  const main = [
    ...briefingCards(weekDoc),
    ...SECTION_TABS.flatMap((topic) => sectionCards(weekDoc, topic.id)),
  ];
  const required = weekDoc.week_id >= '2026-W41';
  for (const card of main) {
    if (required && (typeof card.takeaway !== 'string' || card.takeaway.trim().length === 0)) {
      fail(`${where} ${card.id} is missing a takeaway`);
    }
  }
  for (const card of weekDoc.footer_aside ?? []) {
    if (card && Object.hasOwn(card, 'takeaway')) fail(`${where} Also seen item ${card.id} has a takeaway`);
  }
  if (!required && main.every((card) => typeof card.takeaway !== 'string')) {
    const html = Object.values(pageMap).join('\n');
    if (html.includes('class="takeaway"')) fail(`${where} invented a takeaway for a week that has none`);
  }
}

function assertWeekReader(weekDoc, pageMap, where, { requireMedia = false, emptyCoverageWeek = null } = {}) {
  assertBriefingTab(pageMap.briefing, weekDoc, where);
  for (const topic of SECTION_TABS) assertSectionTab(pageMap[topic.id], weekDoc, topic, where);
  assertItemSetPreserved(weekDoc, pageMap, where);
  assertRubric(weekDoc, pageMap, where);
  assertStoryGroups(weekDoc, pageMap, where);
  assertTakeawayCoverage(weekDoc, pageMap, where);
  assertMediaCase(weekDoc, pageMap, where, requireMedia);
  for (const error of storyPlacementErrors(weekDoc)) fail(`${where} ${error}`);
  const counts = SECTION_TABS.map((topic) => `${topic.label} ${sectionCards(weekDoc, topic.id).length}`).join(', ');
  console.log(`${where} section counts: ${counts}`);
  const noEmptyTab = SECTION_TABS.every((topic) => sectionCards(weekDoc, topic.id).length > 0);
  if (!emptyCoverageWeek || !noEmptyTab) return;
  const covered = SECTION_TABS.filter((topic) => sectionCards(emptyCoverageWeek, topic.id).length === 0).map(
    (topic) => topic.label,
  );
  if (covered.length === 0) {
    console.log(
      `${where} has no empty section; empty-state message and dimmed styling stay covered by the empty-topic fixture`,
    );
    return;
  }
  console.log(
    `${where} has no empty section; empty-state message and dimmed styling stay covered by /digest/${WEEK_ID}/ (${covered.join(', ')})`,
  );
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

const fixedTabs = ['Briefing', 'Archive'];
for (const html of Object.values(pages)) {
  for (const label of fixedTabs) {
    if (!html.includes(`>${label}<`)) fail(`missing tab ${label}`);
  }
}
if (!allHtml.includes('r="6.25"') || !allHtml.includes('stroke-width="1.25"')) {
  fail('play icon SVG no longer matches the existing PlayIcon');
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
assertWeekReader(latest, latestPages, `latest ${latest.week_id}`, { emptyCoverageWeek: week });
const groupedWeek = digestWeeks.find((item) => item.week_id === '2026-W41');
if (!groupedWeek) fail('missing 2026-W41');
if (latest.week_id !== '2026-W41') {
  assertWeekReader(
    groupedWeek,
    {
      briefing: readPage('digest/2026-W41/index.html'),
      business: readPage('digest/2026-W41/business/index.html'),
      technical: readPage('digest/2026-W41/technical/index.html'),
      edtech: readPage('digest/2026-W41/edtech/index.html'),
      'policy-and-safety': readPage('digest/2026-W41/policy-and-safety/index.html'),
    },
    'week 2026-W41',
    { emptyCoverageWeek: week },
  );
}
assertWeekReader(week, archivePages, `archive ${WEEK_ID}`, { requireMedia: true });
if (!decode(archivePages.technical).includes('September sponsors-only newsletter')) {
  fail(`archive ${WEEK_ID} technical tab is missing the September sponsors footer`);
}
if (decode(archivePages.briefing).includes('September sponsors-only newsletter')) {
  fail(`archive ${WEEK_ID} briefing still lists the September sponsors footer`);
}
if (!pages.digest.includes('Week of Sep 27 \u2013 Oct 3, 2026')) {
  fail('archive 2026-W40 is missing the week range');
}

const excerpt = firstSentence(week.briefing.synthesis);
if (!excerpt || !decode(pages.archive).includes(excerpt)) fail('archive is missing the week excerpt');
const latestExcerpt = firstSentence(latest.briefing.synthesis);
if (!latestExcerpt || !decode(pages.archive).includes(latestExcerpt)) fail('archive is missing the latest week excerpt');
if (!pages.archive.includes('>Read this week</a>')) fail('archive path must be labeled Read this week');
if (!pages.archive.includes(`href="/digest/${WEEK_ID}"`)) fail('archive path does not open the week');
if (!pages.archive.includes(`href="/digest/${latest.week_id}"`)) fail('archive path does not open the latest week');
if (pages.archive.includes('class="summary"')) fail('archive invented a card summary');
if (decode(fromMain(pages.archive)).includes(DEGRADED_BODY)) fail('archive includes the degraded sentence');

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
  if (typeof extraEnv.DIGEST_AS_OF === 'string' && extraEnv.DIGEST_AS_OF.length > 0) {
    const parsed = new Date(extraEnv.DIGEST_AS_OF);
    if (Number.isNaN(parsed.getTime())) fail(`DIGEST_AS_OF is not a time: ${extraEnv.DIGEST_AS_OF}`);
    builtAsOf = parsed;
  } else {
    builtAsOf = new Date();
  }
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
const excludedNoise = fixtureCard(
  'excluded-noise',
  'technical',
  'Excluded noise must not render.',
  '2026-09-24T12:00:00Z',
);
excludedNoise.included = false;
excludedNoise.include_reason = 'Excluded: fixture noise.';
const misplacedThin = {
  id: 'misplaced-thin',
  title: 'Misplaced thin item from the file.',
  url: 'https://example.com/misplaced-thin',
  publisher: { source_id: 'import-ai', name: 'Import AI' },
  published_at: '2026-09-25T17:00:00Z',
  category: 'technical',
  media: 'article',
  summary_status: 'thin',
  included: true,
  include_reason: 'Thin: this fixture must stay off the topic page.',
};
const olderThinVideo = {
  id: 'saved-thin-video',
  title: 'Saved thin video from the file.',
  url: 'https://www.youtube.com/shorts/saved-thin-video',
  publisher: { source_id: 'how-i-ai', name: 'How I AI' },
  published_at: '2026-09-25T19:00:00Z',
  category: 'technical',
  media: 'video',
  summary_status: 'thin',
  included: true,
  include_reason: 'Thin: the summary only restates the video description.',
};
function savedThin(id, title, category, publishedAt) {
  return {
    id,
    title,
    url: `https://example.com/${id}`,
    publisher: { source_id: 'import-ai', name: 'Import AI' },
    published_at: publishedAt,
    category,
    media: 'article',
    summary_status: 'thin',
  };
}
const olderEducationThin = savedThin(
  'saved-education-thin',
  'Saved education thin link from the file.',
  'edtech',
  '2026-09-25T18:10:00Z',
);
const olderBusinessThin = savedThin(
  'saved-business-thin',
  'Saved business thin link from the file.',
  'business',
  '2026-09-25T18:20:00Z',
);
const olderPolicyThin = savedThin(
  'saved-policy-thin',
  'Saved policy thin link from the file.',
  'policy-and-safety',
  '2026-09-25T18:30:00Z',
);
const fillerVersionBump = savedThin(
  'filler-version-bump',
  'llm-mistral 0.16',
  'technical',
  '2026-09-25T18:40:00Z',
);
fillerVersionBump.included = true;
fillerVersionBump.include_reason = 'Thin: the feed had no article body, so this stays a link in Also seen.';
const fillerLetterVersion = savedThin(
  'filler-letter-version',
  'datasette-atom 0.11a0',
  'technical',
  '2026-09-25T18:50:00Z',
);
fillerLetterVersion.included = true;
fillerLetterVersion.include_reason = 'Excluded: minor version release (datasette-atom 0.11a0).';
const fillerQuote = savedThin(
  'filler-quote-only',
  'Quoting Carson Gross',
  'technical',
  '2026-09-25T18:55:00Z',
);
fillerQuote.included = true;
fillerQuote.include_reason = 'Excluded: a quote with no commentary.';
const olderWeek = completeWeek(
  '2026-W39',
  '2026-09-20T00:00:00-04:00',
  '2026-09-26T23:59:59-04:00',
  OLDER_SYNTHESIS,
  [olderEdtech, olderBusiness, olderTechnical, olderTechnicalExtra, olderTechnicalThird],
  {
    edtech: [olderEdtech],
    business: [olderBusiness],
    technical: [olderTechnical, excludedNoise, olderTechnicalExtra, misplacedThin, olderTechnicalThird],
    'policy-and-safety': [olderPolicy, policyEastern, policyDateOnly],
  },
);
olderWeek.footer_aside = [
  olderThin,
  fillerVersionBump,
  olderEducationThin,
  fillerQuote,
  olderThinVideo,
  olderBusinessThin,
  fillerLetterVersion,
  olderPolicyThin,
];
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
    for (const label of fixedTabs) {
      if (!html.includes(`>${label}<`)) fail(`a zero-item week hid the ${label} tab`);
    }
  }
  const homeDuringWeek = decode(readPage('index.html'));
  if (!homeDuringWeek.includes(week.briefing.synthesis)) {
    fail('the empty fixture replaced the latest week');
  }
  if (!homeDuringWeek.includes('Week of Sep 27 \u2013 Oct 3, 2026')) {
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
  if (!archiveDuringWeek.includes('Week of Sep 20 \u2013 Sep 26, 2026')) {
    fail('archive is missing the older week range');
  }

  const olderBriefingHtml = readPage('digest/2026-W39/index.html');
  const olderEdtechHtml = readPage('digest/2026-W39/edtech/index.html');
  const olderBusinessHtml = readPage('digest/2026-W39/business/index.html');
  const olderTechnicalHtml = readPage('digest/2026-W39/technical/index.html');
  const olderPolicyHtml = readPage('digest/2026-W39/policy-and-safety/index.html');
  const archivedThin = visibleAlsoSeen(olderWeek.footer_aside);
  if (
    archivedThin.length !== 5 ||
    !archivedThin.some((card) => card.id === 'saved-thin-video') ||
    !archivedThin.some((card) => card.category === 'business') ||
    !archivedThin.some((card) => card.category === 'edtech') ||
    !archivedThin.some((card) => card.category === 'policy-and-safety')
  ) {
    fail('archived Also seen fixture dropped a thin link');
  }
  assertBriefingOmitsAlsoSeen(olderBriefingHtml, 'archived briefing');
  const archivedPages = [olderBriefingHtml, olderEdtechHtml, olderBusinessHtml, olderTechnicalHtml, olderPolicyHtml];
  for (const filler of [fillerVersionBump, fillerLetterVersion, fillerQuote]) {
    if (archivedPages.some((html) => html.includes(`id="${filler.id}"`) || cardTitles(html).includes(filler.title))) {
      fail(`archived week rendered filler ${filler.title}`);
    }
  }
  assertTopicAlsoSeen(olderEdtechHtml, topicAlsoSeen(olderWeek, 'edtech'), 'archived Education');
  assertTopicAlsoSeen(olderBusinessHtml, topicAlsoSeen(olderWeek, 'business'), 'archived business');
  assertTopicAlsoSeen(olderTechnicalHtml, topicAlsoSeen(olderWeek, 'technical'), 'archived technical');
  assertTopicAlsoSeen(olderPolicyHtml, topicAlsoSeen(olderWeek, 'policy-and-safety'), 'archived Policy and Safety');
  if (olderTechnicalHtml.includes('id="excluded-noise"') || decode(olderTechnicalHtml).includes('Excluded noise must not render.')) {
    fail('archived technical rendered an excluded item');
  }
  if (olderTechnicalHtml.includes('id="misplaced-thin"')) {
    fail('archived technical rendered a thin item in the topic list');
  }
  assertBriefingOmitsAlsoSeen(readPage('digest/1999-W01/index.html'), 'Briefing has no Also seen');
  assertTopicAlsoSeen(
    readPage('digest/1999-W01/business/index.html'),
    [],
    'Also seen is omitted when a tab has no thin items',
  );
  assertTopicAlsoSeen(readPage('digest/1999-W01/edtech/index.html'), [], 'Also seen is omitted on an empty tab');
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
    for (const label of fixedTabs) {
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
for (const [path, original] of fixtureOriginals) {
  const restored = existsSync(path) ? readFileSync(path) : null;
  if (!restored || !restored.equals(original)) fail(`restored ${path} does not match the original bytes`);
}
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
