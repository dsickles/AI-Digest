import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse as parseYaml } from 'yaml';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { digestWeekId, isoWeekId, newYorkParts } from '../src/lib/week-rules.mjs';
import { sourcePlacementErrors, validateSourcesDocument } from '../src/lib/source-rules.mjs';
import { canonicalStoryUrl, numberNoteErrors, storyPlacementErrors } from '../src/lib/story-groups.mjs';
import { alsoSeenFillerErrors, alsoSeenFillerKind, visibleAlsoSeen } from '../src/lib/also-seen.mjs';

export { isoWeekId };

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const RUBRIC_PATH = join(ROOT, 'config', 'inclusion-rubric.md');
const GROUPING_PATH = join(ROOT, 'config', 'story-grouping.md');
const BRIEFING_PATH = join(ROOT, 'config', 'briefing.md');
const DIGEST_SCHEMA_PATH = join(ROOT, 'schema', 'digest.schema.json');
const REPORT_SCHEMA_PATH = join(ROOT, 'schema', 'report.schema.json');
const SOURCES_PATH = join(ROOT, 'config', 'sources.yaml');
const DEGRADED_BODY = "The summary couldn't be generated this week.";
const WEEK_ID = /^[0-9]{4}-W(0[1-9]|[1-4][0-9]|5[0-3])$/;
const TOPIC_ORDER = ['edtech', 'business', 'technical', 'policy-and-safety'];
const IN_PLACE_STATUSES = new Set([
  'quota_exhausted',
  'api_error',
  'parse_error',
  'client_init_error',
  'transcript_missing',
  'deferred_budget',
]);

const digestSchema = JSON.parse(readFileSync(DIGEST_SCHEMA_PATH, 'utf8'));
const reportSchema = JSON.parse(readFileSync(REPORT_SCHEMA_PATH, 'utf8'));

if (digestSchema.$defs.mainCard.properties.body.const !== DEGRADED_BODY) {
  throw new Error('digest schema degraded body does not match the locked copy');
}

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validateDigestSchema = ajv.compile(digestSchema);
const validateReportSchema = ajv.compile(reportSchema);

function jsonFiles(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((name) => name.endsWith('.json'))
    .sort()
    .map((name) => join(dir, name));
}

function concatTopics(doc) {
  return TOPIC_ORDER.flatMap((topic) => doc.topics[topic] ?? []);
}

function loadSources() {
  const doc = parseYaml(readFileSync(SOURCES_PATH, 'utf8'));
  const configErrors = validateSourcesDocument(doc);
  if (configErrors.length > 0) {
    throw new Error(configErrors.map((error) => `config/sources.yaml: ${error}`).join('\n'));
  }
  const sources = new Map();
  for (const source of doc.sources) {
    sources.set(source.id, {
      type: source.type,
      name: source.display_name,
      tag: source.tag,
      aiOnly: source.ai_only === true,
    });
  }
  if (sources.size === 0) {
    throw new Error(`no sources parsed from ${relative(ROOT, SOURCES_PATH)}`);
  }
  return sources;
}

function formatAjvErrors(errors = []) {
  return errors.map((error) => {
    const path = error.instancePath || '/';
    return `${path} ${error.message ?? 'is invalid'}`;
  });
}

function readJson(path) {
  try {
    return { doc: JSON.parse(readFileSync(path, 'utf8')) };
  } catch (error) {
    return { error: `invalid JSON (${error.message})` };
  }
}

function deepEqual(left, right) {
  return JSON.stringify(sortKeys(left)) === JSON.stringify(sortKeys(right));
}

function sortKeys(value) {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, sortKeys(value[key])]),
    );
  }
  return value;
}

function newYorkOffset(iso) {
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) return null;
  const name = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    timeZoneName: 'shortOffset',
    hour: '2-digit',
    hourCycle: 'h23',
  })
    .formatToParts(instant)
    .find((part) => part.type === 'timeZoneName')?.value;
  if (!name || name === 'GMT' || name === 'UTC') return '+00:00';
  const match = /^GMT([+-])(\d{1,2})(?::(\d{2}))?$/.exec(name);
  if (!match) return null;
  return `${match[1]}${match[2].padStart(2, '0')}:${match[3] ?? '00'}`;
}

function writtenOffset(iso) {
  if (typeof iso !== 'string') return null;
  if (iso.endsWith('Z')) return '+00:00';
  const match = /([+-]\d{2}:\d{2})$/.exec(iso);
  return match ? match[1] : null;
}

function civilDayNumber(year, month, day) {
  return Math.floor(Date.UTC(year, month - 1, day) / 86400000);
}

function isHttps(url) {
  try {
    return new URL(url).protocol === 'https:';
  } catch {
    return false;
  }
}

function isBannedHost(url) {
  let hostname;
  try {
    hostname = new URL(url).hostname.toLowerCase();
  } catch {
    return false;
  }
  return (
    hostname === 'reddit.com' ||
    hostname.endsWith('.reddit.com') ||
    hostname === 'news.ycombinator.com' ||
    hostname === 'hn.algolia.com'
  );
}

function isBannedPublisher(sourceId, name) {
  if (/^(reddit|hacker-?news|hn|ycombinator)$/i.test(sourceId ?? '')) return true;
  return /\breddit\b/i.test(name ?? '') || /\bhacker news\b/i.test(name ?? '');
}

function validateWeekWindow(doc) {
  const errors = [];
  const start = newYorkParts(doc.week_start);
  const end = newYorkParts(doc.week_end);
  const startOffset = newYorkOffset(doc.week_start);
  const endOffset = newYorkOffset(doc.week_end);
  if (!start || !end || !startOffset || !endOffset) {
    return ['week_start and week_end must be real timestamps'];
  }
  if (writtenOffset(doc.week_start) !== startOffset) {
    errors.push(
      `week_start must use the America/New_York offset ${startOffset} (got ${writtenOffset(doc.week_start) ?? 'none'})`,
    );
  }
  if (writtenOffset(doc.week_end) !== endOffset) {
    errors.push(
      `week_end must use the America/New_York offset ${endOffset} (got ${writtenOffset(doc.week_end) ?? 'none'})`,
    );
  }
  if (!(start.weekday === 'Sun' && start.hour === 0 && start.minute === 0 && start.second === 0)) {
    errors.push('week_start must be Sunday 00:00:00 America/New_York');
  }
  if (!(end.weekday === 'Sat' && end.hour === 23 && end.minute === 59 && end.second === 59)) {
    errors.push('week_end must be Saturday 23:59:59 America/New_York');
  }
  if (civilDayNumber(end.year, end.month, end.day) - civilDayNumber(start.year, start.month, start.day) !== 6) {
    errors.push('week_end must be the Saturday six days after week_start');
  }
  const expectedId = isoWeekId(end.year, end.month, end.day);
  if (doc.week_id !== expectedId) {
    errors.push(`week_id must be the ISO week of the ending Saturday (${expectedId})`);
  }
  return errors;
}

function validateCardIdentity(card, sources, where) {
  const errors = [];
  if (!isHttps(card.url)) errors.push(`${where} url must be https`);
  if (isBannedHost(card.url) || isBannedPublisher(card.publisher.source_id, card.publisher.name)) {
    errors.push(`${where} must be a named-author source, not Reddit or Hacker News`);
  }
  const source = sources.get(card.publisher.source_id);
  if (!source) {
    errors.push(`${where} publisher.source_id ${card.publisher.source_id} is not in config/sources.yaml`);
    return errors;
  }
  if (card.publisher.name !== source.name) {
    errors.push(
      `${where} publisher.name must be ${JSON.stringify(source.name)} for source ${card.publisher.source_id}`,
    );
  }
  if (source.type === 'youtube' && card.media !== 'video') {
    errors.push(`${where} YouTube sources use media "video"`);
  }
  if (source.type === 'rss' && card.media !== 'article') {
    errors.push(`${where} RSS sources use media "article"`);
  }
  if (card.summary_status === 'thin' && source.type !== 'rss' && source.type !== 'youtube') {
    errors.push(`${where} thin cards are RSS links or description-only videos`);
  }
  if (card.summary_status === 'transcript_missing' && source.type !== 'youtube') {
    errors.push(`${where} transcript_missing is a YouTube in-place status`);
  }
  errors.push(...sourcePlacementErrors(card, source, where));
  return errors;
}

function validateDigestDocument(doc, filename, sources) {
  if (!validateDigestSchema(doc)) {
    return formatAjvErrors(validateDigestSchema.errors);
  }

  const errors = [];
  if (filename !== `${doc.week_id}.json`) {
    errors.push(`filename must be ${doc.week_id}.json`);
  }
  if (!WEEK_ID.test(doc.week_id)) errors.push('week_id is not an ISO week id');
  errors.push(...validateWeekWindow(doc));

  const grouped = concatTopics(doc);
  if (!deepEqual(doc.main_feed, grouped)) {
    errors.push(
      'main_feed must equal topics.edtech + topics.business + topics.technical + topics.policy-and-safety, in that order',
    );
  }

  const mainById = new Map();
  const seen = new Set();
  for (const card of doc.main_feed) {
    if (seen.has(card.id)) errors.push(`duplicate card id ${card.id}`);
    seen.add(card.id);
    mainById.set(card.id, card);
    if (card.summary_status === 'ok') {
      if (typeof card.summary !== 'string' || card.summary.length === 0) {
        errors.push(`${card.id} ok card is missing summary`);
      }
      if ('body' in card) errors.push(`${card.id} ok card must not include body`);
    } else if (IN_PLACE_STATUSES.has(card.summary_status)) {
      if (card.body !== DEGRADED_BODY) {
        errors.push(`${card.id} degraded body must be exactly ${JSON.stringify(DEGRADED_BODY)}`);
      }
      if ('summary' in card) errors.push(`${card.id} degraded card must not include summary`);
    } else {
      errors.push(`${card.id} summary_status ${card.summary_status} is not an in-place main status`);
    }
  }

  const topIds = new Set();
  for (const card of doc.briefing.top) {
    if (topIds.has(card.id)) errors.push(`duplicate briefing top id ${card.id}`);
    topIds.add(card.id);
    const main = mainById.get(card.id);
    if (!main) {
      errors.push(`briefing top ${card.id} is not in main_feed`);
    } else if (!deepEqual(card, main)) {
      errors.push(`briefing top ${card.id} must match its main_feed card`);
    }
    if (card.summary_status !== 'ok') {
      errors.push(`briefing top ${card.id} must be an ok summary, not ${card.summary_status}`);
    }
  }

  for (const card of doc.footer_aside) {
    if (seen.has(card.id)) errors.push(`duplicate card id ${card.id}`);
    seen.add(card.id);
    if (card.summary_status !== 'thin') errors.push(`${card.id} footer cards must be summary_status thin`);
    if ('summary' in card || 'body' in card) errors.push(`${card.id} footer cards are link-only`);
  }

  const excluded = Array.isArray(doc.excluded) ? doc.excluded : [];
  for (const card of excluded) {
    if (!card || typeof card !== 'object') continue;
    if (seen.has(card.id)) errors.push(`duplicate card id ${card.id}`);
    seen.add(card.id);
    if (card.included !== false) errors.push(`${card.id} excluded items must set included to false`);
  }

  const startMs = Date.parse(doc.week_start);
  const endMs = Date.parse(doc.week_end);
  for (const card of [...doc.main_feed, ...doc.footer_aside, ...excluded]) {
    const publishedMs = Date.parse(card.published_at);
    if (Number.isNaN(publishedMs) || publishedMs < startMs || publishedMs > endMs) {
      errors.push(`${card.id} published_at is outside the week window`);
    }
    errors.push(...validateCardIdentity(card, sources, card.id));
  }

  errors.push(...validateRubric(doc));
  errors.push(...validateGrouping(doc, sources));
  errors.push(...validateBriefingScan(doc));
  errors.push(...alsoSeenFillerErrors(doc));
  return errors;
}

function validateCoverageLink(link, sources, where) {
  const errors = [];
  if (!link || typeof link !== 'object') {
    errors.push(`${where} also covered link is missing`);
    return errors;
  }
  if (!isHttps(link.url)) errors.push(`${where} also covered url must be https`);
  if (isBannedHost(link.url) || isBannedPublisher(link.publisher?.source_id, link.publisher?.name)) {
    errors.push(`${where} also covered link must be a named-author source, not Reddit or Hacker News`);
  }
  const source = sources.get(link.publisher?.source_id);
  if (!source) {
    errors.push(`${where} also covered source_id ${link.publisher?.source_id} is not in config/sources.yaml`);
  } else if (link.publisher.name !== source.name) {
    errors.push(`${where} also covered publisher name must be ${JSON.stringify(source.name)}`);
  }
  if (typeof link.title !== 'string' || link.title.trim().length === 0) {
    errors.push(`${where} also covered link is missing a title`);
  }
  return errors;
}

function validateGrouping(doc, sources) {
  const errors = [...storyPlacementErrors(doc)];
  const cards = [...doc.main_feed, ...doc.footer_aside, ...(Array.isArray(doc.excluded) ? doc.excluded : [])];
  for (const card of cards) {
    if (!card || typeof card !== 'object') continue;
    errors.push(...numberNoteErrors(card));
    if (!Array.isArray(card.also_covered)) continue;
    card.also_covered.forEach((link, index) => {
      errors.push(...validateCoverageLink(link, sources, `${card.id} also covered ${index + 1}`));
    });
  }
  return errors;
}

const RUBRIC_WEEK = '2026-W41';

function rubricApplies(doc) {
  return typeof doc.week_id === 'string' && doc.week_id >= RUBRIC_WEEK;
}

function reasonErrors(card, where, required) {
  const errors = [];
  const hasIncluded = !!card && Object.hasOwn(card, 'included');
  const hasReason = !!card && Object.hasOwn(card, 'include_reason');
  if (required && (!hasIncluded || !hasReason)) {
    errors.push(`${where} must record included and a one-line include_reason`);
    return errors;
  }
  if (hasIncluded !== hasReason) {
    errors.push(`${where} must set included and include_reason together`);
    return errors;
  }
  if (!hasReason) return errors;
  const reason = card.include_reason;
  if (typeof reason !== 'string' || reason.trim().length === 0 || /[\r\n]/.test(reason) || reason.length > 240) {
    errors.push(`${where} include_reason must be one non-empty line of at most 240 characters`);
  }
  if (typeof card.included !== 'boolean') errors.push(`${where} included must be true or false`);
  return errors;
}

function validateRubric(doc) {
  const errors = [];
  const required = rubricApplies(doc);
  if (required && !Array.isArray(doc.excluded)) {
    errors.push('excluded must be a list from 2026-W41 on, even when nothing was excluded');
  }
  const rendered = [...doc.main_feed, ...doc.footer_aside, ...doc.briefing.top];
  for (const card of rendered) {
    errors.push(...reasonErrors(card, card.id, required));
    if (card.included === false) {
      errors.push(`${card.id} is excluded and must live in excluded, not in a rendered list`);
    } else if (required && card.included !== true) {
      errors.push(`${card.id} must set included to true`);
    }
    if (card.summary_status === 'thin' && !doc.footer_aside.includes(card)) {
      errors.push(`${card.id} thin items belong in footer_aside and Also seen, not on Briefing or a topic page`);
    }
  }
  for (const card of Array.isArray(doc.excluded) ? doc.excluded : []) {
    if (!card || typeof card !== 'object') continue;
    errors.push(...reasonErrors(card, card.id, true));
  }
  return errors;
}

function validateReportDocument(doc, filename) {
  if (!validateReportSchema(doc)) return formatAjvErrors(validateReportSchema.errors);
  if (filename !== `${doc.week_id}.json`) return [`filename must be ${doc.week_id}.json`];
  return [];
}

const THEME_WEEK = '2026-W41';
const DASH = /[\u2013\u2014]/;

function wordCount(text) {
  return String(text ?? '')
    .trim()
    .split(/\s+/)
    .filter(Boolean).length;
}

function isOneSentence(text) {
  const trimmed = String(text ?? '').trim();
  const match = trimmed.match(/^.+?[.!?](?=\s|$)/);
  return Boolean(match) && match[0].length === trimmed.length;
}

function storyKeys(card) {
  const keys = new Set();
  const add = (url) => {
    const key = canonicalStoryUrl(url);
    if (key) keys.add(key);
  };
  if (card && typeof card === 'object') {
    add(card.url);
    for (const link of card.also_covered ?? []) add(link?.url);
  }
  return keys;
}

function validateBriefingScan(doc) {
  const errors = [];
  const briefing = doc?.briefing;
  if (!briefing || typeof briefing !== 'object') return errors;
  const hasLead = Object.hasOwn(briefing, 'lead');
  const hasThemes = Object.hasOwn(briefing, 'themes');
  const required = typeof doc.week_id === 'string' && doc.week_id >= THEME_WEEK;
  if (required && (!hasLead || !hasThemes)) {
    errors.push('briefing must include a lead line and 4 to 6 themes from 2026-W41 on');
  } else if (hasLead !== hasThemes) {
    errors.push('briefing lead and themes must be set together');
  }
  if (!hasLead && !hasThemes) return errors;

  if (typeof briefing.lead !== 'string' || !isOneSentence(briefing.lead)) {
    errors.push('briefing lead must be one sentence');
  } else if (DASH.test(briefing.lead)) {
    errors.push('briefing lead must not use an em dash or an en dash');
  }

  const themes = Array.isArray(briefing.themes) ? briefing.themes : [];
  if (themes.length < 4 || themes.length > 6) {
    errors.push('briefing must include 4 to 6 themes');
  }
  const mainById = new Map((doc.main_feed ?? []).filter((card) => card && typeof card === 'object').map((card) => [card.id, card]));
  themes.forEach((theme, index) => {
    if (!theme || typeof theme !== 'object') {
      errors.push(`theme ${index + 1} is missing`);
      return;
    }
    const where = `theme ${theme.label || index + 1}`;
    const label = typeof theme.label === 'string' ? theme.label.trim() : '';
    if (label.length === 0 || label.length > 32 || wordCount(label) > 4 || /[.!?]/.test(label) || /[\r\n]/.test(label)) {
      errors.push(`${where} label must be a short label of at most 4 words`);
    } else if (DASH.test(label)) {
      errors.push(`${where} label must not use an em dash or an en dash`);
    }
    if (typeof theme.sentence !== 'string' || !isOneSentence(theme.sentence)) {
      errors.push(`${where} sentence must be one sentence`);
    } else {
      const count = wordCount(theme.sentence);
      if (count < 25 || count > 35) errors.push(`${where} sentence must be 25 to 35 words`);
      if (DASH.test(theme.sentence)) errors.push(`${where} sentence must not use an em dash or an en dash`);
    }
    const ids = Array.isArray(theme.story_ids) ? theme.story_ids : [];
    if (ids.length === 0) errors.push(`${where} must link at least one merged story`);
    const seenIds = new Set();
    const linked = [];
    for (const id of ids) {
      if (seenIds.has(id)) {
        errors.push(`${where} links ${id} twice`);
        continue;
      }
      seenIds.add(id);
      const card = mainById.get(id);
      if (!card) {
        errors.push(`${where} story ${id} must be the merged main item`);
        continue;
      }
      linked.push(card);
    }
    for (let left = 0; left < linked.length; left += 1) {
      const leftKeys = storyKeys(linked[left]);
      for (let right = left + 1; right < linked.length; right += 1) {
        const rightKeys = storyKeys(linked[right]);
        const shared = [...leftKeys].some((key) => rightKeys.has(key));
        if (shared) {
          errors.push(
            `${where} links two copies of the same story (${linked[left].id} and ${linked[right].id})`,
          );
        }
      }
    }
  });
  return errors;
}

function briefingFileErrors() {
  if (!existsSync(BRIEFING_PATH)) return ['config/briefing.md is missing'];
  const text = readFileSync(BRIEFING_PATH, 'utf8');
  const required = [
    ['lead', 'config/briefing.md must tell ingest how to write the lead line'],
    ['themes', 'config/briefing.md must tell ingest how to write themes'],
    ['25 to 35', 'config/briefing.md must tell ingest the theme sentence is 25 to 35 words'],
    ['story_ids', 'config/briefing.md must tell ingest to link themes by story id'],
    ['merged main item', 'config/briefing.md must tell ingest to link the merged main item'],
    ['2026-W40', 'config/briefing.md must keep weeks before 2026-W41, including 2026-W40, valid without a lead or themes'],
  ];
  for (const [needle, message] of required) {
    if (!text.includes(needle)) return [message];
  }
  return [];
}

function rubricFileErrors() {
  if (!existsSync(RUBRIC_PATH)) return ['config/inclusion-rubric.md is missing'];
  const text = readFileSync(RUBRIC_PATH, 'utf8');
  if (!text.includes('include_reason') || !text.includes('excluded')) {
    return ['config/inclusion-rubric.md must tell ingest about include_reason and excluded'];
  }
  if (!/per-source/i.test(text)) {
    return ['config/inclusion-rubric.md must say there is no per-source cap'];
  }
  if (!text.includes('story-grouping.md')) {
    return ['config/inclusion-rubric.md must point ingest at config/story-grouping.md'];
  }
  return [];
}

function groupingFileErrors() {
  if (!existsSync(GROUPING_PATH)) return ['config/story-grouping.md is missing'];
  const text = readFileSync(GROUPING_PATH, 'utf8');
  const required = [
    ['same story', 'config/story-grouping.md must say ingest groups the same story, not only the same URL'],
    ['strongest source', 'config/story-grouping.md must say how to pick the strongest source'],
    ['Also covered by', 'config/story-grouping.md must tell ingest to list the other sources as Also covered by'],
    ['number_note', 'config/story-grouping.md must tell ingest how to write number_note when a key number disagrees'],
    ['Also seen', 'config/story-grouping.md must say an item cannot be both a main item and an Also seen link'],
    ['2026-W40', 'config/story-grouping.md must keep weeks before 2026-W41, including 2026-W40, valid without grouping fields'],
  ];
  for (const [needle, message] of required) {
    if (!text.includes(needle)) return [message];
  }
  return [];
}

export function validateArchive(contentDir, sources) {
  const digestPaths = jsonFiles(join(contentDir, 'digests'));
  const reportPaths = jsonFiles(join(contentDir, 'reports'));
  const errors = [...rubricFileErrors(), ...groupingFileErrors(), ...briefingFileErrors()];

  if (digestPaths.length === 0) {
    errors.push(`${contentDir}/digests has no week json files`);
  }

  for (const path of digestPaths) {
    const loaded = readJson(path);
    const label = basename(path);
    if (loaded.error) {
      errors.push(`${label}: ${loaded.error}`);
      continue;
    }
    const fileErrors = validateDigestDocument(loaded.doc, label, sources);
    for (const error of fileErrors) errors.push(`${label}: ${error}`);
  }

  for (const path of reportPaths) {
    const loaded = readJson(path);
    const label = `reports/${basename(path)}`;
    if (loaded.error) {
      errors.push(`${label}: ${loaded.error}`);
      continue;
    }
    for (const error of validateReportDocument(loaded.doc, basename(path))) {
      errors.push(`${label}: ${error}`);
    }
  }

  return {
    errors,
    digestCount: digestPaths.length,
    reportCount: reportPaths.length,
  };
}

function printResult(prefix, result) {
  if (result.errors.length === 0) {
    console.log(
      `${prefix}PASS ${result.digestCount} week file(s), ${result.reportCount} report file(s); a missing report does not fail this check`,
    );
    return true;
  }
  console.error(`${prefix}FAIL`);
  for (const error of result.errors) console.error(`- ${error}`);
  return false;
}

function validateFile(path, sources) {
  const loaded = readJson(path);
  if (loaded.error) return [loaded.error];
  return validateDigestDocument(loaded.doc, basename(path), sources);
}

function withLockedDegradedExample(doc) {
  const week = structuredClone(doc);
  const card = {
    id: 'locked-degraded-example',
    title: 'Locked degraded example',
    url: 'https://simonwillison.net/2026/Sep/28/locked-degraded-example/',
    publisher: { source_id: 'simon-willison', name: 'Simon Willison' },
    published_at: week.week_start,
    category: 'technical',
    media: 'article',
    summary_status: 'api_error',
    body: DEGRADED_BODY,
  };
  week.topics.technical.push(card);
  week.main_feed = concatTopics(week);
  return week;
}

function runSelfTest(sources) {
  const archive = validateArchive(join(ROOT, 'content'), sources);
  if (!printResult('archive ', archive)) return false;
  if (archive.reportCount !== 0) {
    console.error('self-test expected the committed tree to omit content/reports/*.json');
    return false;
  }

  if (isoWeekId(2026, 10, 3) !== '2026-W40') {
    console.error('iso week of 2026-10-03 must be 2026-W40');
    return false;
  }
  if (isoWeekId(2026, 1, 3) !== '2026-W01' || isoWeekId(2027, 1, 2) !== '2026-W53') {
    console.error('iso week year-boundary checks failed');
    return false;
  }
  // Sunday Oct 4, 2026 is inside ISO week W40, and it opens digest week W41.
  // week_id follows the ending Saturday, not the Sunday's own ISO week.
  if (isoWeekId(2026, 10, 4) !== '2026-W40' || digestWeekId('2026-10-04T12:00:00-04:00') !== '2026-W41') {
    console.error('Sunday 2026-10-04 must open digest week 2026-W41');
    return false;
  }
  if (digestWeekId('2026-10-03T12:00:00-04:00') !== '2026-W40') {
    console.error('Saturday 2026-10-03 must stay in digest week 2026-W40');
    return false;
  }
  if (digestWeekId('2026-10-07T15:00:00-04:00') !== '2026-W41') {
    console.error('Wednesday 2026-10-07 must stay in digest week 2026-W41');
    return false;
  }

  const samplePath = join(ROOT, 'content', 'digests', '2026-W40.json');
  const sample = JSON.parse(readFileSync(samplePath, 'utf8'));
  const sampleStart = newYorkParts(sample.week_start);
  const sampleEnd = newYorkParts(sample.week_end);
  const sampleWindowOk =
    sample.timezone === 'America/New_York' &&
    sample.week_id === '2026-W40' &&
    sample.week_start === '2026-09-27T00:00:00-04:00' &&
    sample.week_end === '2026-10-03T23:59:59-04:00' &&
    sampleStart?.weekday === 'Sun' &&
    sampleStart.hour === 0 &&
    sampleStart.minute === 0 &&
    sampleStart.second === 0 &&
    sampleEnd?.weekday === 'Sat' &&
    sampleEnd.hour === 23 &&
    sampleEnd.minute === 59 &&
    sampleEnd.second === 59 &&
    civilDayNumber(sampleEnd.year, sampleEnd.month, sampleEnd.day) -
      civilDayNumber(sampleStart.year, sampleStart.month, sampleStart.day) ===
      6 &&
    sample.week_id === isoWeekId(sampleEnd.year, sampleEnd.month, sampleEnd.day);
  if (!sampleWindowOk) {
    console.error('2026-W40 must be Sunday 2026-09-27 00:00:00 through Saturday 2026-10-03 23:59:59 America/New_York, offset -04:00');
    return false;
  }
  console.log('self-test PASS 2026-W40 Sunday through Saturday window');
  const root = mkdtempSync(join(tmpdir(), 'week-schema-'));
  try {
    const digestDir = join(root, 'digests');
    mkdirSync(digestDir, { recursive: true });
    writeFileSync(join(digestDir, '2026-W40.json'), JSON.stringify(sample));
    const missingReport = validateArchive(root, sources);
    if (missingReport.errors.length !== 0 || missingReport.reportCount !== 0) {
      console.error('self-test: a digest with no report file must pass');
      for (const error of missingReport.errors) console.error(`- ${error}`);
      return false;
    }
    console.log('self-test PASS missing report');

    const reportDir = join(root, 'reports');
    mkdirSync(reportDir);
    writeFileSync(
      join(reportDir, '2026-W40.json'),
      JSON.stringify({
        schema_version: 1,
        week_id: '2026-W40',
        generated_at: '2026-10-04T13:00:00Z',
        note: 'optional ops detail',
      }),
    );
    const withReport = validateArchive(root, sources);
    if (withReport.errors.length !== 0) {
      console.error('self-test: a valid optional report must pass');
      for (const error of withReport.errors) console.error(`- ${error}`);
      return false;
    }
    console.log('self-test PASS optional report present');

    writeFileSync(
      join(reportDir, '2026-W40.json'),
      JSON.stringify({ schema_version: 1, week_id: '2026-W39', generated_at: '2026-10-04T13:00:00Z' }),
    );
    const badReport = validateArchive(root, sources);
    if (badReport.errors.length === 0) {
      console.error('self-test: an invalid report must fail');
      return false;
    }
    console.log('self-test PASS invalid report rejected');
    for (const error of badReport.errors) console.log(`  expected: ${error}`);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }

  const exampleDir = mkdtempSync(join(tmpdir(), 'week-schema-example-'));
  try {
    const example = withLockedDegradedExample(sample);
    const examplePath = join(exampleDir, '2026-W40.json');
    writeFileSync(examplePath, JSON.stringify(example));
    const child = spawnSync(process.execPath, [fileURLToPath(import.meta.url), '--file', examplePath], {
      encoding: 'utf8',
      cwd: ROOT,
    });
    if (child.status !== 0) {
      console.error('self-test: locked degraded example unexpectedly failed');
      console.error(child.stdout);
      console.error(child.stderr);
      return false;
    }
    console.log('self-test PASS locked degraded example');

    const exampleRoot = mkdtempSync(join(tmpdir(), 'week-schema-example-archive-'));
    try {
      const digestDir = join(exampleRoot, 'digests');
      mkdirSync(digestDir, { recursive: true });
      writeFileSync(join(digestDir, '2026-W40.json'), JSON.stringify(example));
      const archived = validateArchive(exampleRoot, sources);
      if (archived.errors.length !== 0) {
        console.error('self-test: an archive whose only week has a locked degraded card must pass');
        for (const error of archived.errors) console.error(`- ${error}`);
        return false;
      }
      console.log('self-test PASS archive with locked degraded example');
    } finally {
      rmSync(exampleRoot, { recursive: true, force: true });
    }
  } finally {
    rmSync(exampleDir, { recursive: true, force: true });
  }

  const healthyRoot = mkdtempSync(join(tmpdir(), 'week-schema-healthy-'));
  try {
    const digestDir = join(healthyRoot, 'digests');
    mkdirSync(digestDir, { recursive: true });
    const healthy = structuredClone(sample);
    for (const topic of TOPIC_ORDER) {
      healthy.topics[topic] = (healthy.topics[topic] ?? []).filter((card) => card.summary_status === 'ok');
    }
    healthy.main_feed = concatTopics(healthy);
    healthy.footer_aside = [];
    const mainById = new Map(healthy.main_feed.map((card) => [card.id, card]));
    healthy.briefing.top = healthy.briefing.top
      .filter((card) => mainById.has(card.id))
      .map((card) => mainById.get(card.id));
    writeFileSync(join(digestDir, '2026-W40.json'), JSON.stringify(healthy));
    const archived = validateArchive(healthyRoot, sources);
    if (archived.errors.length !== 0) {
      console.error('self-test: a healthy week with no degraded card and no thin footer must pass');
      for (const error of archived.errors) console.error(`- ${error}`);
      return false;
    }
    console.log('self-test PASS healthy week without example cards');
  } finally {
    rmSync(healthyRoot, { recursive: true, force: true });
  }

  const cases = [
    {
      name: 'degraded body is not the locked copy',
      filename: '2026-W40.json',
      base: withLockedDegradedExample,
      mutate(doc) {
        for (const list of [doc.main_feed, doc.topics.business, doc.topics.edtech, doc.topics.technical]) {
          for (const card of list) {
            if (card.summary_status !== 'ok') card.body = 'Summary unavailable.';
          }
        }
      },
    },
    {
      name: 'week_id is not the ISO week of the ending Saturday',
      filename: '2026-W01.json',
      mutate(doc) {
        doc.week_id = '2026-W01';
      },
    },
    {
      name: 'footer item is not a named-author source',
      filename: '2026-W40.json',
      mutate(doc) {
        const card = doc.footer_aside[0];
        card.publisher = { source_id: 'reddit', name: 'Reddit' };
        card.url = 'https://www.reddit.com/r/MachineLearning/comments/sample';
      },
    },
    {
      name: 'briefing top is not exactly 5',
      filename: '2026-W40.json',
      mutate(doc) {
        doc.briefing.top = doc.briefing.top.slice(0, 4);
      },
    },
  ];

  for (const testCase of cases) {
    const dir = mkdtempSync(join(tmpdir(), 'week-schema-bad-'));
    const path = join(dir, testCase.filename);
    try {
      const doc = testCase.base ? testCase.base(sample) : structuredClone(sample);
      testCase.mutate(doc);
      writeFileSync(path, JSON.stringify(doc));
      const child = spawnSync(process.execPath, [fileURLToPath(import.meta.url), '--file', path], {
        encoding: 'utf8',
        cwd: ROOT,
      });
      if (child.status === 0) {
        console.error(`self-test: invalid week unexpectedly passed (${testCase.name})`);
        console.error(child.stdout);
        return false;
      }
      console.log(`self-test PASS deliberately invalid week failed (${testCase.name})`);
      const detail = `${child.stdout ?? ''}${child.stderr ?? ''}`.trim();
      for (const line of detail.split('\n')) console.log(`  ${line}`);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  }

  const goodDir = mkdtempSync(join(tmpdir(), 'week-schema-good-'));
  const goodPath = join(goodDir, '2026-W40.json');
  try {
    writeFileSync(goodPath, JSON.stringify(sample));
    const child = spawnSync(process.execPath, [fileURLToPath(import.meta.url), '--file', goodPath], {
      encoding: 'utf8',
      cwd: ROOT,
    });
    if (child.status !== 0) {
      console.error('self-test: good week file unexpectedly failed');
      console.error(child.stdout);
      console.error(child.stderr);
      return false;
    }
    console.log('self-test PASS good week file');
    process.stdout.write(child.stdout ?? '');
  } finally {
    rmSync(goodDir, { recursive: true, force: true });
  }

  if (!proveInclusion(sources, sample)) return false;
  if (!proveGrouping(sources)) return false;
  if (!proveBriefing(sources)) return false;
  if (!proveSourceRules(sources, sample)) return false;

  console.log('self-test PASS');
  return true;
}

function thinAlsoSeenCard(id, title, reason = 'Thin: the feed had no article body, so this stays a link in Also seen.') {
  return {
    id,
    title,
    url: `https://simonwillison.net/2026/Oct/6/${id}/`,
    publisher: { source_id: 'simon-willison', name: 'Simon Willison' },
    published_at: '2026-10-06T18:00:00-04:00',
    category: 'technical',
    media: 'article',
    summary_status: 'thin',
    included: true,
    include_reason: reason,
  };
}

function rubricCard(id, title) {
  return {
    id,
    title,
    url: `https://simonwillison.net/2026/Oct/6/${id}/`,
    publisher: { source_id: 'simon-willison', name: 'Simon Willison' },
    published_at: '2026-10-06T15:00:00-04:00',
    category: 'technical',
    media: 'article',
    summary_status: 'ok',
    summary: `${title} is a real note about AI tooling.`,
    included: true,
    include_reason: 'New: a launch worth a full card.',
  };
}

function themeSentence() {
  return 'This theme ties together the included items that belong on one short scan line for the week and points at each merged main story once only.';
}

function rubricWeek() {
  const cards = [1, 2, 3, 4, 5, 6, 7, 8].map((n) => rubricCard(`rubric-item-${n}`, `Rubric item ${n}`));
  const excluded = {
    ...rubricCard('rubric-minor-release', 'llm-example 0.2'),
    included: false,
    include_reason: 'Excluded: minor version release.',
  };
  const thinVideo = {
    id: 'rubric-thin-video',
    title: 'Description only video',
    url: 'https://www.youtube.com/shorts/rubric-thin-video',
    publisher: { source_id: 'how-i-ai', name: 'How I AI' },
    published_at: '2026-10-06T16:00:00-04:00',
    category: 'technical',
    media: 'video',
    summary_status: 'thin',
    included: true,
    include_reason: 'Thin: the summary only restates the video description, so this stays a link in Also seen.',
  };
  return {
    schema_version: 1,
    week_id: '2026-W41',
    timezone: 'America/New_York',
    week_start: '2026-10-04T00:00:00-04:00',
    week_end: '2026-10-10T23:59:59-04:00',
    generated_at: '2026-10-11T15:00:00Z',
    briefing: {
      synthesis: 'Eight items from one source still fit, because there is no per-source cap.',
      lead: 'Eight included items from one source still fit in a single week.',
      themes: [1, 2, 3, 4].map((n) => ({
        label: `Theme ${n}`,
        sentence: themeSentence(),
        story_ids: [`rubric-item-${n}`],
      })),
      top: cards.slice(0, 5),
    },
    topics: { edtech: [], business: [], technical: cards },
    main_feed: cards,
    footer_aside: [thinVideo],
    excluded: [excluded],
  };
}

function expectRubricFailure(sources, doc, needle, name) {
  const errors = validateDigestDocument(doc, `${doc.week_id}.json`, sources);
  if (!errors.some((error) => error.includes(needle))) {
    console.error(`self-test: ${name} was not rejected`);
    for (const error of errors) console.error(`- ${error}`);
    return false;
  }
  console.log(`self-test PASS ${name}`);
  return true;
}

function proveInclusion(sources, sample) {
  const open = rubricWeek();
  const openErrors = validateDigestDocument(open, '2026-W41.json', sources);
  if (openErrors.length !== 0) {
    console.error('self-test: a rubric week with many items from one source must pass');
    for (const error of openErrors) console.error(`- ${error}`);
    return false;
  }
  console.log('self-test PASS rubric week with no per-source cap');
  if (!open.footer_aside.some((card) => card.summary_status === 'thin')) {
    console.error('self-test: rubric week dropped its thin Also seen link');
    return false;
  }
  console.log('self-test PASS thin items stay in Also seen');

  const emptyAlsoSeen = rubricWeek();
  emptyAlsoSeen.footer_aside = [];
  const emptyAlsoSeenErrors = validateDigestDocument(emptyAlsoSeen, '2026-W41.json', sources);
  if (emptyAlsoSeenErrors.length !== 0) {
    console.error('self-test: a week with no Also seen items must pass');
    for (const error of emptyAlsoSeenErrors) console.error(`- ${error}`);
    return false;
  }
  console.log('self-test PASS Also seen can be empty');

  const versionBump = rubricWeek();
  versionBump.footer_aside.push(thinAlsoSeenCard('rubric-version-bump', 'llm-mistral 0.16'));
  if (
    !expectRubricFailure(
      sources,
      versionBump,
      'must not appear in Also seen',
      'version bump in Also seen',
    )
  ) {
    return false;
  }

  const letterVersion = rubricWeek();
  letterVersion.footer_aside.push(thinAlsoSeenCard('rubric-letter-version', 'datasette-atom 0.11a0'));
  if (
    !expectRubricFailure(
      sources,
      letterVersion,
      'must not appear in Also seen',
      'letter-suffix version bump in Also seen',
    )
  ) {
    return false;
  }

  const quoteTitle = rubricWeek();
  quoteTitle.footer_aside.push(thinAlsoSeenCard('rubric-quote-title', 'Quoting Carson Gross'));
  if (
    !expectRubricFailure(
      sources,
      quoteTitle,
      'must not appear in Also seen',
      'quote-only title in Also seen',
    )
  ) {
    return false;
  }

  const quoteReason = rubricWeek();
  quoteReason.footer_aside.push(
    thinAlsoSeenCard('rubric-quote-reason', 'A pointer with no argument', 'Excluded: a quote with no commentary.'),
  );
  if (
    !expectRubricFailure(
      sources,
      quoteReason,
      'must not appear in Also seen',
      'quote-only reason in Also seen',
    )
  ) {
    return false;
  }

  const missingList = rubricWeek();
  delete missingList.excluded;
  if (!expectRubricFailure(sources, missingList, 'excluded must be a list', 'rubric week without excluded')) {
    return false;
  }

  const missingReason = rubricWeek();
  delete missingReason.topics.technical[0].include_reason;
  delete missingReason.main_feed[0].include_reason;
  delete missingReason.briefing.top[0].include_reason;
  if (!expectRubricFailure(sources, missingReason, 'include_reason', 'rendered item with no reason')) {
    return false;
  }

  const placedWrong = rubricWeek();
  const banned = placedWrong.excluded[0];
  placedWrong.topics.technical.push(banned);
  placedWrong.main_feed = concatTopics(placedWrong);
  if (
    !expectRubricFailure(
      sources,
      placedWrong,
      'must live in excluded',
      'excluded item copied into a topic list',
    )
  ) {
    return false;
  }

  const halfField = structuredClone(sample);
  const target = halfField.main_feed[0];
  target.included = true;
  for (const list of Object.values(halfField.topics)) {
    const match = Array.isArray(list) ? list.find((card) => card.id === target.id) : undefined;
    if (match) match.included = true;
  }
  const topMatch = halfField.briefing.top.find((card) => card.id === target.id);
  if (topMatch) topMatch.included = true;
  if (!expectRubricFailure(sources, halfField, 'include_reason', 'included without a reason on an older week')) {
    return false;
  }

  const w41Path = join(ROOT, 'content', 'digests', '2026-W41.json');
  if (!existsSync(w41Path)) {
    console.error('self-test: 2026-W41.json is missing');
    return false;
  }
  const committed = JSON.parse(readFileSync(w41Path, 'utf8'));
  const stripped = structuredClone(committed);
  if (!Array.isArray(stripped.excluded) || stripped.excluded.length === 0) {
    console.error('self-test: 2026-W41 must record excluded items');
    return false;
  }
  delete stripped.excluded[0].include_reason;
  if (!expectRubricFailure(sources, stripped, 'include_reason', '2026-W41 excluded item with no reason')) {
    return false;
  }
  const filler = (committed.footer_aside ?? []).filter((card) => alsoSeenFillerKind(card));
  if (filler.length !== 0) {
    console.error(`self-test: 2026-W41 Also seen still includes ${filler.map((card) => card.title).join(', ')}`);
    return false;
  }
  const seen = visibleAlsoSeen(committed.footer_aside);
  const thinVideo = seen.find(
    (card) => card.media === 'video' && /video description/i.test(String(card.include_reason ?? '')),
  );
  const thinArticle = seen.find((card) => card.summary_status === 'thin' && card.media !== 'video');
  if (!thinVideo || !thinArticle) {
    console.error('self-test: 2026-W41 Also seen must keep thin articles and description-only videos');
    return false;
  }
  const excludedFiller = (committed.excluded ?? []).filter(
    (card) => card.title === 'llm-mistral 0.16' || card.title === 'datasette-atom 0.11a0' || card.title === 'Quoting Carson Gross',
  );
  if (excludedFiller.length !== 3 || excludedFiller.some((card) => visibleAlsoSeen([card]).length !== 0)) {
    console.error('self-test: 2026-W41 version bumps and quote-only posts must stay excluded');
    return false;
  }
  console.log('self-test PASS 2026-W41 Also seen keeps thin links and drops filler');
  return true;
}

function proveGrouping(sources) {
  const grouped = rubricWeek();
  const primary = grouped.topics.technical[0];
  primary.also_covered = [
    {
      title: 'Import AI on the same launch',
      url: 'https://importai.substack.com/p/rubric-same-launch',
      publisher: { source_id: 'import-ai', name: 'Import AI' },
    },
  ];
  primary.number_note = '8 per Simon Willison, 3 per Import AI';
  const groupedErrors = validateDigestDocument(grouped, '2026-W41.json', sources);
  if (groupedErrors.length !== 0) {
    console.error('self-test: a grouped story with a number note must pass');
    for (const error of groupedErrors) console.error(`- ${error}`);
    return false;
  }
  console.log('self-test PASS grouped story with a number note');

  const silent = rubricWeek();
  silent.topics.technical[0].number_note = '8 per Simon Willison, 3 per Import AI';
  if (!expectRubricFailure(sources, silent, 'number_note needs at least one also covered source', 'number note without also covered')) {
    return false;
  }

  const oneName = rubricWeek();
  oneName.topics.technical[0].also_covered = [
    {
      title: 'Import AI on the same launch',
      url: 'https://importai.substack.com/p/rubric-same-launch',
      publisher: { source_id: 'import-ai', name: 'Import AI' },
    },
  ];
  oneName.topics.technical[0].number_note = '8 per Simon Willison';
  if (
    !expectRubricFailure(
      sources,
      oneName,
      'number_note must name at least two publishers',
      'number note that names one publisher',
    )
  ) {
    return false;
  }

  const seenTwice = rubricWeek();
  seenTwice.footer_aside[0].url = `${seenTwice.main_feed[0].url}?utm_source=digest`;
  if (
    !expectRubricFailure(
      sources,
      seenTwice,
      'appears both as a main item and as an Also seen link',
      'main url repeated under Also seen',
    )
  ) {
    return false;
  }

  const coveredAndSeen = rubricWeek();
  const coveredUrl = 'https://importai.substack.com/p/rubric-same-launch';
  coveredAndSeen.topics.technical[0].also_covered = [
    {
      title: 'Import AI on the same launch',
      url: coveredUrl,
      publisher: { source_id: 'import-ai', name: 'Import AI' },
    },
  ];
  coveredAndSeen.footer_aside[0].url = coveredUrl;
  if (
    !expectRubricFailure(
      sources,
      coveredAndSeen,
      'appears both as a main item and as an Also seen link',
      'also covered url still listed under Also seen',
    )
  ) {
    return false;
  }

  const w41Path = join(ROOT, 'content', 'digests', '2026-W41.json');
  const w41 = JSON.parse(readFileSync(w41Path, 'utf8'));
  const mathId = 'dont-worry-about-the-vase-new-math-from-openai';
  const claytonId = 'nextgov-fcw-experts-hope-new-ai-czars-leadership-can-move-the-needle-on-regulation';
  const math = w41.main_feed.find((card) => card.id === mathId);
  const clayton = w41.main_feed.find((card) => card.id === claytonId);
  const mathUrls = [
    'https://stefanbauschard.substack.com/p/ai-is-inventing-new-math-it-has-722',
    'https://lastweekin.ai/p/last-week-in-ai-346-719-math-manuscripts',
    'https://thezvi.substack.com/p/ai-189-new-math',
  ];
  const claytonUrls = ['https://www.techpolicy.press/an-ai-accord-a-new-czar-and-an-autonomous-warfare-command/'];
  const renderedUrls = new Set([...w41.main_feed, ...w41.footer_aside].map((card) => card.url));
  const topIds = [
    'metr-ai-systems-could-cover-up-misbehavior',
    'transformer-bengio-if-you-prioritize-safety-leave-frontier-ai-companies',
    'epoch-ai-can-ai-automate-ai-r-d-yet',
    'where-your-ed-at-credit-crunch',
    'education-week-chatgpts-teen-mode-is-unsafe-for-students-report-concludes',
  ];
  const absorbed = [
    'education-disrupted-ai-is-inventing-new-math-it-has-722-papers-to-show-for-it',
    'last-week-in-ai-last-week-in-ai-346-719-math-manuscripts-2-western-open-models-1-more-safety-resignation',
    'dont-worry-about-the-vase-ai-189-new-math',
    'tech-policy-press-an-ai-accord-a-new-czar-and-an-autonomous-warfare-command',
  ];
  const renderedIds = new Set([...w41.main_feed, ...w41.footer_aside].map((card) => card.id));
  const mathCovered = (math?.also_covered ?? []).map((link) => link.url);
  const claytonCovered = (clayton?.also_covered ?? []).map((link) => link.url);
  const w41Grouped =
    math &&
    clayton &&
    mathCovered.length === mathUrls.length &&
    mathUrls.every((url) => mathCovered.includes(url)) &&
    mathUrls.every((url) => !renderedUrls.has(url)) &&
    claytonCovered.length === 1 &&
    claytonUrls.every((url) => claytonCovered.includes(url)) &&
    claytonUrls.every((url) => !renderedUrls.has(url)) &&
    typeof math.number_note === 'string' &&
    math.number_note.includes('722') &&
    math.number_note.includes('719') &&
    math.number_note.includes('Education Disrupted') &&
    math.number_note.includes('Last Week in AI') &&
    w41.briefing.synthesis.includes('722') &&
    w41.briefing.synthesis.includes('719') &&
    topIds.every((id, index) => w41.briefing.top[index]?.id === id) &&
    absorbed.every((id) => !renderedIds.has(id));
  if (!w41Grouped) {
    console.error('self-test: 2026-W41 must show the math release once and the Clayton appointment once');
    console.error(JSON.stringify({ mathCovered, claytonCovered, note: math?.number_note }, null, 2));
    return false;
  }
  console.log('self-test PASS 2026-W41 math release and Clayton appointment are each one item');
  return true;
}

function proveBriefing(sources) {
  const open = rubricWeek();
  const openErrors = validateDigestDocument(open, '2026-W41.json', sources);
  if (openErrors.length !== 0) {
    console.error('self-test: a rubric week with a lead line and themes must pass');
    for (const error of openErrors) console.error(`- ${error}`);
    return false;
  }
  console.log('self-test PASS lead line and themes');

  const missing = rubricWeek();
  delete missing.briefing.lead;
  delete missing.briefing.themes;
  if (
    !expectRubricFailure(
      sources,
      missing,
      'lead line and 4 to 6 themes',
      'rubric week without a lead line or themes',
    )
  ) {
    return false;
  }

  const short = rubricWeek();
  short.briefing.themes[0].sentence = 'Too short to pass the word count rule today.';
  if (!expectRubricFailure(sources, short, '25 to 35 words', 'theme sentence outside 25 to 35 words')) {
    return false;
  }

  const twoSentences = rubricWeek();
  twoSentences.briefing.themes[0].sentence = 'This is one sentence. This is a second sentence that should not be in the theme row.';
  if (!expectRubricFailure(sources, twoSentences, 'must be one sentence', 'theme sentence that is two sentences')) {
    return false;
  }

  const missingStory = rubricWeek();
  missingStory.briefing.themes[0].story_ids = ['not-a-real-item'];
  if (
    !expectRubricFailure(
      sources,
      missingStory,
      'must be the merged main item',
      'theme link that is not a merged main item',
    )
  ) {
    return false;
  }

  const copies = rubricWeek();
  const primary = copies.topics.technical[0];
  const second = copies.topics.technical[1];
  second.url = 'https://importai.substack.com/p/same-story-copy';
  primary.also_covered = [
    {
      title: 'Same story from the other source',
      url: second.url,
      publisher: { source_id: 'import-ai', name: 'Import AI' },
    },
  ];
  copies.briefing.themes[0].story_ids = [primary.id, second.id];
  if (
    !expectRubricFailure(
      sources,
      copies,
      'two copies of the same story',
      'theme links two copies of the same story',
    )
  ) {
    return false;
  }

  const few = rubricWeek();
  few.briefing.themes = few.briefing.themes.slice(0, 3);
  if (!expectRubricFailure(sources, few, 'fewer than 4', 'fewer than 4 themes')) return false;

  const w40 = JSON.parse(readFileSync(join(ROOT, 'content', 'digests', '2026-W40.json'), 'utf8'));
  if (Object.hasOwn(w40.briefing, 'lead') || Object.hasOwn(w40.briefing, 'themes')) {
    console.error('self-test: 2026-W40 must omit lead and themes');
    return false;
  }
  const w40Errors = validateDigestDocument(w40, '2026-W40.json', sources);
  if (w40Errors.length !== 0) {
    console.error('self-test: 2026-W40 without a lead line or themes must pass');
    for (const error of w40Errors) console.error(`- ${error}`);
    return false;
  }
  console.log('self-test PASS 2026-W40 without a lead line or themes');

  const w41Path = join(ROOT, 'content', 'digests', '2026-W41.json');
  const w41 = JSON.parse(readFileSync(w41Path, 'utf8'));
  const mathId = 'dont-worry-about-the-vase-new-math-from-openai';
  const absorbed = [
    'education-disrupted-ai-is-inventing-new-math-it-has-722-papers-to-show-for-it',
    'last-week-in-ai-last-week-in-ai-346-719-math-manuscripts-2-western-open-models-1-more-safety-resignation',
    'dont-worry-about-the-vase-ai-189-new-math',
  ];
  const research = (w41.briefing.themes ?? []).find((theme) => theme.label === 'Research');
  const themeIds = (w41.briefing.themes ?? []).flatMap((theme) => theme.story_ids ?? []);
  const w41Scan =
    typeof w41.briefing.lead === 'string' &&
    isOneSentence(w41.briefing.lead) &&
    Array.isArray(w41.briefing.themes) &&
    w41.briefing.themes.length >= 4 &&
    w41.briefing.themes.length <= 6 &&
    research &&
    research.story_ids.includes(mathId) &&
    research.story_ids.every((id) => !absorbed.includes(id)) &&
    themeIds.every((id) => !absorbed.includes(id)) &&
    new Set(research.story_ids).size === research.story_ids.length;
  if (!w41Scan) {
    console.error('self-test: 2026-W41 themes must link the merged math item, not a second copy');
    console.error(JSON.stringify({ lead: w41.briefing.lead, research }, null, 2));
    return false;
  }
  console.log('self-test PASS 2026-W41 themes link merged stories');
  return true;
}

const ORIGINAL_EIGHT = [
  {
    id: 'simon-willison',
    type: 'rss',
    url: 'https://simonwillison.net/atom/everything/',
    display_name: 'Simon Willison',
    tag: 'technical',
    enabled: true,
  },
  {
    id: 'one-useful-thing',
    type: 'rss',
    url: 'https://www.oneusefulthing.org/feed',
    display_name: 'One Useful Thing',
    tag: 'business',
    enabled: true,
  },
  {
    id: 'import-ai',
    type: 'rss',
    url: 'https://importai.substack.com/feed',
    display_name: 'Import AI',
    tag: 'business',
    enabled: true,
  },
  {
    id: 'where-your-ed-at',
    type: 'rss',
    url: 'https://www.wheresyoured.at/feed',
    display_name: "Where's Your Ed At",
    tag: 'business',
    enabled: true,
  },
  {
    id: 'bensbites',
    type: 'rss',
    url: 'https://www.bensbites.com/feed',
    display_name: "Ben's Bites",
    tag: 'business',
    enabled: true,
  },
  {
    id: 'last-week-in-ai',
    type: 'rss',
    url: 'https://lastweekin.ai/feed',
    display_name: 'Last Week in AI',
    tag: 'technical',
    enabled: true,
  },
  {
    id: 'how-i-ai',
    type: 'youtube',
    channel_id: 'UCRYY7IEbkHLH_ScJCu9eWDQ',
    channel_url: 'https://www.youtube.com/@howiaipodcast',
    display_name: 'How I AI',
    tag: 'technical',
    enabled: true,
  },
  {
    id: 'nate-b-jones',
    type: 'youtube',
    channel_id: 'UC0C-17n9iuUQPylguM1d-lQ',
    channel_url: 'https://www.youtube.com/@NateBJones',
    display_name: 'AI News & Strategy Daily | Nate B Jones',
    tag: 'business',
    enabled: true,
  },
];

const APPROVED_AFTER_EIGHT = [
  {
    id: 'hechinger-report',
    type: 'rss',
    url: 'https://hechingerreport.org/tags/artificial-intelligence/feed/',
    home_url: 'https://hechingerreport.org/',
    display_name: 'Hechinger Report',
    tag: 'edtech',
    enabled: true,
  },
  {
    id: 'educause-review',
    type: 'rss',
    url: 'https://er.educause.edu/channels/emerging-technologies-trends/rss',
    home_url: 'https://er.educause.edu/',
    display_name: 'EDUCAUSE Review',
    tag: 'edtech',
    ai_only: true,
    enabled: true,
  },
  {
    id: 'education-week',
    type: 'rss',
    url: 'https://www.edweek.org/technology/artificial-intelligence.rss',
    home_url: 'https://www.edweek.org/',
    display_name: 'Education Week',
    tag: 'edtech',
    enabled: true,
  },
  {
    id: 'philippa-hardman',
    type: 'rss',
    url: 'https://drphilippahardman.substack.com/feed',
    home_url: 'https://drphilippahardman.substack.com/',
    display_name: 'Philippa Hardman',
    tag: 'edtech',
    enabled: true,
  },
  {
    id: 'ai-as-normal-technology',
    type: 'rss',
    url: 'https://www.normaltech.ai/feed',
    home_url: 'https://www.normaltech.ai/',
    display_name: 'AI as Normal Technology',
    tag: 'business',
    enabled: true,
  },
  {
    id: 'chinai',
    type: 'rss',
    url: 'https://chinai.substack.com/feed',
    home_url: 'https://chinai.substack.com/',
    display_name: 'ChinAI',
    tag: 'business',
    enabled: true,
  },
  {
    id: 'interconnects',
    type: 'rss',
    url: 'https://www.interconnects.ai/feed',
    home_url: 'https://www.interconnects.ai/',
    display_name: 'Interconnects',
    tag: 'technical',
    enabled: true,
  },
  {
    id: 'ahead-of-ai',
    type: 'rss',
    url: 'https://magazine.sebastianraschka.com/feed',
    home_url: 'https://magazine.sebastianraschka.com/',
    display_name: 'Ahead of AI',
    tag: 'technical',
    enabled: true,
  },
  {
    id: 'metr',
    type: 'rss',
    url: 'https://metr.org/feed.xml',
    home_url: 'https://metr.org/',
    display_name: 'METR',
    tag: 'technical',
    enabled: true,
  },
  {
    id: 'ai-alignment-forum',
    type: 'rss',
    url: 'https://www.alignmentforum.org/feed.xml',
    home_url: 'https://www.alignmentforum.org/',
    display_name: 'AI Alignment Forum',
    tag: 'policy-and-safety',
    enabled: true,
  },
  {
    id: 'pragmatic-engineer',
    type: 'rss',
    url: 'https://newsletter.pragmaticengineer.com/feed',
    home_url: 'https://newsletter.pragmaticengineer.com/',
    display_name: 'The Pragmatic Engineer (Gergely Orosz)',
    tag: 'technical',
    ai_only: true,
    enabled: true,
  },
  {
    id: 'the-74',
    type: 'rss',
    url: 'https://www.the74million.org/tag/artificial-intelligence/feed/',
    home_url: 'https://www.the74million.org/',
    display_name: 'The 74',
    tag: 'edtech',
    enabled: true,
  },
  {
    id: 'edtech-insiders',
    type: 'rss',
    url: 'https://edtechinsiders.substack.com/feed',
    home_url: 'https://edtechinsiders.substack.com/',
    display_name: 'Edtech Insiders',
    tag: 'edtech',
    ai_only: true,
    enabled: true,
  },
  {
    id: 'educating-ai',
    type: 'rss',
    url: 'https://nickpotkalitsky.substack.com/feed',
    home_url: 'https://nickpotkalitsky.substack.com/',
    display_name: 'Educating AI (Nick Potkalitsky)',
    tag: 'edtech',
    enabled: true,
  },
  {
    id: 'education-disrupted',
    type: 'rss',
    url: 'https://stefanbauschard.substack.com/feed',
    home_url: 'https://stefanbauschard.substack.com/',
    display_name: 'Education Disrupted (Stefan Bauschard)',
    tag: 'edtech',
    ai_only: true,
    enabled: true,
  },
  {
    id: 'cognitive-resonance',
    type: 'rss',
    url: 'https://buildcognitiveresonance.substack.com/feed',
    home_url: 'https://buildcognitiveresonance.substack.com/',
    display_name: 'Cognitive Resonance (Benjamin Riley)',
    tag: 'edtech',
    ai_only: true,
    enabled: true,
  },
  {
    id: 'transformer',
    type: 'rss',
    url: 'https://www.transformernews.ai/feed',
    home_url: 'https://www.transformernews.ai/',
    display_name: 'Transformer (Shakeel Hashim)',
    tag: 'policy-and-safety',
    enabled: true,
  },
  {
    id: 'dont-worry-about-the-vase',
    type: 'rss',
    url: 'https://thezvi.substack.com/feed',
    home_url: 'https://thezvi.substack.com/',
    display_name: "Don't Worry About the Vase (Zvi Mowshowitz)",
    tag: 'policy-and-safety',
    ai_only: true,
    enabled: true,
  },
  {
    id: 'just-security',
    type: 'rss',
    url: 'https://www.justsecurity.org/tag/artificial-intelligence/feed/',
    home_url: 'https://www.justsecurity.org/',
    display_name: 'Just Security',
    tag: 'policy-and-safety',
    enabled: true,
  },
  {
    id: 'schneier-on-security',
    type: 'rss',
    url: 'https://www.schneier.com/tag/ai/feed/',
    home_url: 'https://www.schneier.com/',
    display_name: 'Schneier on Security',
    tag: 'policy-and-safety',
    enabled: true,
  },
  {
    id: 'nextgov-fcw',
    type: 'rss',
    url: 'https://www.nextgov.com/rss/artificial-intelligence/',
    home_url: 'https://www.nextgov.com/',
    display_name: 'Nextgov/FCW',
    tag: 'policy-and-safety',
    enabled: true,
  },
  {
    id: 'tech-policy-press',
    type: 'rss',
    url: 'https://www.techpolicy.press/rss/feed.xml',
    home_url: 'https://www.techpolicy.press/',
    display_name: 'Tech Policy Press',
    tag: 'policy-and-safety',
    ai_only: true,
    enabled: true,
  },
  {
    id: 'epoch-ai',
    type: 'rss',
    url: 'https://epochai.substack.com/feed',
    home_url: 'https://epochai.substack.com/',
    display_name: 'Epoch AI',
    tag: 'technical',
    enabled: true,
  },
  {
    id: 'latent-space',
    type: 'rss',
    url: 'https://www.latent.space/feed',
    home_url: 'https://www.latent.space/',
    display_name: 'Latent Space',
    tag: 'technical',
    enabled: true,
  },
  {
    id: 'nieman-lab',
    type: 'rss',
    url: 'https://www.niemanlab.org/tag/ai/feed/',
    home_url: 'https://www.niemanlab.org/',
    display_name: 'Nieman Lab',
    tag: 'business',
    enabled: true,
  },
];

function sourceArticle(sample, id, sourceId, name, category, title, summary) {
  return {
    id,
    title,
    url: `https://example.com/${id}`,
    publisher: { source_id: sourceId, name },
    published_at: sample.week_start,
    category,
    media: 'article',
    summary_status: 'ok',
    summary,
  };
}

function weekWithCard(sample, topic, card) {
  const week = structuredClone(sample);
  if (!Array.isArray(week.topics[topic])) week.topics[topic] = [];
  week.topics[topic].push(card);
  week.main_feed = concatTopics(week);
  return week;
}

function proveSourceRules(sources, sample) {
  const doc = parseYaml(readFileSync(SOURCES_PATH, 'utf8'));
  if (!deepEqual(doc.sources.slice(0, 8), ORIGINAL_EIGHT)) {
    console.error('self-test: the original eight sources changed');
    return false;
  }
  if (!deepEqual(doc.sources.slice(8), APPROVED_AFTER_EIGHT) || doc.sources.length !== 33) {
    console.error('self-test: approved sources do not match the registry after the original eight');
    return false;
  }
  const mustBeAiOnly = [
    'educause-review',
    'pragmatic-engineer',
    'edtech-insiders',
    'education-disrupted',
    'cognitive-resonance',
    'dont-worry-about-the-vase',
    'tech-policy-press',
  ];
  const mustNotBeAiOnly = [
    'education-week',
    'the-74',
    'educating-ai',
    'transformer',
    'just-security',
    'schneier-on-security',
    'nextgov-fcw',
    'epoch-ai',
    'latent-space',
    'nieman-lab',
  ];
  if (
    mustBeAiOnly.some((id) => sources.get(id)?.aiOnly !== true) ||
    mustNotBeAiOnly.some((id) => sources.get(id)?.aiOnly !== false)
  ) {
    console.error(
      'self-test: AI-only must be set on EDUCAUSE Review, The Pragmatic Engineer, Edtech Insiders, Education Disrupted, Cognitive Resonance, Don\'t Worry About the Vase, and Tech Policy Press, and not on Education Week or the other new sources',
    );
    return false;
  }
  if (
    sources.get('ai-alignment-forum')?.tag !== 'policy-and-safety' ||
    sources.get('metr')?.tag !== 'technical' ||
    sources.get('the-74')?.tag !== 'edtech' ||
    sources.get('transformer')?.tag !== 'policy-and-safety' ||
    sources.get('epoch-ai')?.tag !== 'technical' ||
    sources.get('nieman-lab')?.tag !== 'business'
  ) {
    console.error(
      'self-test: METR stays technical, AI Alignment Forum is policy-and-safety, and the new sources use edtech, Policy and Safety, technical, or business',
    );
    return false;
  }
  const badTag = structuredClone(doc);
  badTag.sources[0] = { ...badTag.sources[0], tag: 'design' };
  if (validateSourcesDocument(badTag).length === 0) {
    console.error('self-test: a source tag outside the section list must fail');
    return false;
  }
  if (sample.topics['policy-and-safety'] !== undefined) {
    console.error('self-test: 2026-W40 must not grow a policy-and-safety list');
    return false;
  }
  const w40Errors = validateDigestDocument(sample, '2026-W40.json', sources);
  if (w40Errors.length !== 0) {
    console.error('self-test: 2026-W40 must stay valid without a policy-and-safety list');
    for (const error of w40Errors) console.error(`- ${error}`);
    return false;
  }

  const rejected = [
    [
      'edtech source filed as business',
      weekWithCard(
        sample,
        'business',
        sourceArticle(
          sample,
          'hechinger-misfile',
          'hechinger-report',
          'Hechinger Report',
          'business',
          'AI on campus',
          'Colleges are buying AI tools.',
        ),
      ),
      'must use category edtech',
    ],
    [
      'policy source filed as technical',
      weekWithCard(
        sample,
        'technical',
        sourceArticle(
          sample,
          'alignment-misfile',
          'ai-alignment-forum',
          'AI Alignment Forum',
          'technical',
          'A new alignment result',
          'The post discusses AI alignment.',
        ),
      ),
      'must use category policy-and-safety',
    ],
    [
      'EDUCAUSE item that is not about AI',
      weekWithCard(
        sample,
        'edtech',
        sourceArticle(
          sample,
          'educause-wifi',
          'educause-review',
          'EDUCAUSE Review',
          'edtech',
          'Campus Wi-Fi upgrade',
          'The network team replaced access points across the residence halls.',
        ),
      ),
      'not about AI',
    ],
  ];
  for (const [name, week, needle] of rejected) {
    const errors = validateDigestDocument(week, '2026-W40.json', sources);
    if (!errors.some((error) => error.includes(needle))) {
      console.error(`self-test: ${name} was not rejected`);
      for (const error of errors) console.error(`- ${error}`);
      return false;
    }
    console.log(`self-test PASS ${name} rejected`);
  }

  const accepted = [
    weekWithCard(
      sample,
      'edtech',
      sourceArticle(
        sample,
        'educause-ai',
        'educause-review',
        'EDUCAUSE Review',
        'edtech',
        'AI tutoring pilots',
        'The campus tested a generative model for tutoring.',
      ),
    ),
    weekWithCard(
      sample,
      'policy-and-safety',
      sourceArticle(
        sample,
        'alignment-ok',
        'ai-alignment-forum',
        'AI Alignment Forum',
        'policy-and-safety',
        'A new alignment result',
        'The post discusses AI alignment.',
      ),
    ),
  ];
  for (const week of accepted) {
    const errors = validateDigestDocument(week, '2026-W40.json', sources);
    if (errors.length !== 0) {
      console.error('self-test: a correctly filed source card must pass');
      for (const error of errors) console.error(`- ${error}`);
      return false;
    }
  }
  console.log('self-test PASS assigned sections and EDUCAUSE AI-only rule');
  return true;
}

function main() {
  const args = process.argv.slice(2);
  const sources = loadSources();

  if (args[0] === '--self-test' && args.length === 1) {
    process.exit(runSelfTest(sources) ? 0 : 1);
  }

  if (args[0] === '--file' && args.length === 2) {
    const errors = validateFile(resolve(args[1]), sources);
    if (errors.length === 0) {
      console.log(`PASS ${args[1]}`);
      process.exit(0);
    }
    console.error(`FAIL ${args[1]}`);
    for (const error of errors) console.error(`- ${error}`);
    process.exit(1);
  }

  if (args.length === 0) {
    const result = validateArchive(join(ROOT, 'content'), sources);
    process.exit(printResult('', result) ? 0 : 1);
  }

  console.error('Usage: node scripts/validate-weeks.mjs [--self-test | --file <week.json>]');
  process.exit(2);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
