import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse as parseYaml } from 'yaml';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DIGEST_SCHEMA_PATH = join(ROOT, 'schema', 'digest.schema.json');
const REPORT_SCHEMA_PATH = join(ROOT, 'schema', 'report.schema.json');
const SOURCES_PATH = join(ROOT, 'config', 'sources.yaml');
const DEGRADED_BODY = "The summary couldn't be generated this week.";
const WEEK_ID = /^[0-9]{4}-W(0[1-9]|[1-4][0-9]|5[0-3])$/;
const TOPIC_ORDER = ['edtech', 'business', 'technical'];
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

function loadSources() {
  const doc = parseYaml(readFileSync(SOURCES_PATH, 'utf8'));
  const sources = new Map();
  for (const source of doc?.sources ?? []) {
    sources.set(source.id, {
      type: source.type,
      name: source.display_name,
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

function newYorkParts(iso) {
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) return null;
  const formatted = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    weekday: 'short',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(instant);
  const parts = Object.fromEntries(
    formatted.filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]),
  );
  return {
    weekday: parts.weekday,
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    hour: Number(parts.hour),
    minute: Number(parts.minute),
    second: Number(parts.second),
  };
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

export function isoWeekId(year, month, day) {
  const date = new Date(Date.UTC(year, month - 1, day));
  const dayNum = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - dayNum);
  const isoYear = date.getUTCFullYear();
  const yearStart = new Date(Date.UTC(isoYear, 0, 1));
  const week = Math.ceil(((date - yearStart) / 86400000 + 1) / 7);
  return `${isoYear}-W${String(week).padStart(2, '0')}`;
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
  if (card.summary_status === 'thin' && source.type !== 'rss') {
    errors.push(`${where} thin cards are RSS-only`);
  }
  if (card.summary_status === 'transcript_missing' && source.type !== 'youtube') {
    errors.push(`${where} transcript_missing is a YouTube in-place status`);
  }
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

  const grouped = TOPIC_ORDER.flatMap((topic) => doc.topics[topic]);
  if (!deepEqual(doc.main_feed, grouped)) {
    errors.push('main_feed must equal topics.edtech + topics.business + topics.technical, in that order');
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

  const startMs = Date.parse(doc.week_start);
  const endMs = Date.parse(doc.week_end);
  for (const card of [...doc.main_feed, ...doc.footer_aside]) {
    const publishedMs = Date.parse(card.published_at);
    if (Number.isNaN(publishedMs) || publishedMs < startMs || publishedMs > endMs) {
      errors.push(`${card.id} published_at is outside the week window`);
    }
    errors.push(...validateCardIdentity(card, sources, card.id));
  }

  return errors;
}

function validateReportDocument(doc, filename) {
  if (!validateReportSchema(doc)) return formatAjvErrors(validateReportSchema.errors);
  if (filename !== `${doc.week_id}.json`) return [`filename must be ${doc.week_id}.json`];
  return [];
}

export function validateArchive(contentDir, sources) {
  const digestPaths = jsonFiles(join(contentDir, 'digests'));
  const reportPaths = jsonFiles(join(contentDir, 'reports'));
  const errors = [];

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
  week.main_feed = [...week.topics.edtech, ...week.topics.business, ...week.topics.technical];
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

  const samplePath = join(ROOT, 'content', 'digests', '2026-W40.json');
  const sample = JSON.parse(readFileSync(samplePath, 'utf8'));
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
      healthy.topics[topic] = healthy.topics[topic].filter((card) => card.summary_status === 'ok');
    }
    healthy.main_feed = [...healthy.topics.edtech, ...healthy.topics.business, ...healthy.topics.technical];
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

  console.log('self-test PASS');
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
