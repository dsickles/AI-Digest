import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { parse as parseYaml } from 'yaml';
import { validateSourcesDocument } from './source-rules.mjs';

// Same order as the section nav: Business, Technical, Education, Policy and Safety.
export const SOURCE_SECTIONS = [
  { id: 'business', label: 'Business' },
  { id: 'technical', label: 'Technical' },
  { id: 'edtech', label: 'Education' },
  { id: 'policy-and-safety', label: 'Policy and Safety' },
];

const SOURCES_PATH = join(process.cwd(), 'config', 'sources.yaml');

// The mock files a leading "The" under the following word: "The 74" with the
// numbers, "The Pragmatic Engineer" with P. The compare stays case-insensitive.
function sourceSortKey(name) {
  return String(name).replace(/^the\s+/i, '');
}

export function compareSourceNames(left, right) {
  const byKey = sourceSortKey(left).localeCompare(sourceSortKey(right), 'en', {
    sensitivity: 'base',
    numeric: true,
  });
  if (byKey !== 0) return byKey;
  return left.localeCompare(right, 'en', { sensitivity: 'base', numeric: true });
}

export function sourceTypeLabel(type) {
  if (type === 'rss') return 'RSS';
  if (type === 'youtube') return 'YouTube';
  if (type === 'page-fetch') return 'Page';
  throw new Error(`unknown source type ${type}`);
}

// Publisher home for the index. An explicit home_url wins. A feed URL with no
// home uses the site origin. YouTube uses the channel page.
export function sourceHomeUrl(source) {
  if (source.type === 'youtube') {
    if (typeof source.channel_url === 'string' && source.channel_url.length > 0) return source.channel_url;
    return `https://www.youtube.com/channel/${source.channel_id}`;
  }
  if (typeof source.home_url === 'string' && source.home_url.length > 0) return source.home_url;
  return `${new URL(source.url).origin}/`;
}

export function indexSources(doc) {
  const errors = validateSourcesDocument(doc);
  if (errors.length > 0) {
    throw new Error(errors.join('\n'));
  }
  const enabled = doc.sources.filter((source) => source.enabled === true);
  const listed = enabled.map((source) => ({
    id: source.id,
    name: source.display_name,
    tag: source.tag,
    type: source.type,
    typeLabel: sourceTypeLabel(source.type),
    homeUrl: sourceHomeUrl(source),
  }));
  const sections = SOURCE_SECTIONS.map((section) => {
    const sources = listed
      .filter((source) => source.tag === section.id)
      .sort((left, right) => compareSourceNames(left.name, right.name));
    return { id: section.id, label: section.label, count: sources.length, sources };
  }).filter((section) => section.count > 0);
  return { total: listed.length, sources: listed, sections };
}

export function loadSourceIndex(path = SOURCES_PATH) {
  const doc = parseYaml(readFileSync(path, 'utf8'));
  return indexSources(doc);
}

export function sourceWeekCountLabel(count) {
  return count > 0 ? `${count} this week` : 'None this week';
}

function firstString(...values) {
  return values.find((value) => typeof value === 'string' && value.length > 0) ?? '';
}

function matchSourceItem(item, byId, byFeed, byName) {
  const publisher = item?.publisher && typeof item.publisher === 'object' ? item.publisher : {};
  const sourceId = firstString(publisher.source_id);
  if (sourceId && (byId.size === 0 || byId.has(sourceId))) return sourceId;
  const feed = firstString(item?.feed_url, publisher.feed_url);
  if (feed && byFeed.has(feed)) return byFeed.get(feed);
  const name = firstString(publisher.name).toLocaleLowerCase('en');
  if (name && byName.has(name)) return byName.get(name);
  return '';
}

// Items in the four section lists, plus Also seen, matched to enabled sources.
// A source counts in every section where one of its items appears. Top 5 and
// main_feed repeat those items, so they are not counted again. Excluded items
// and also_covered links stay out.
export function countSourceReferences(week, sources = []) {
  const counts = new Map();
  const byId = new Map();
  const byFeed = new Map();
  const byName = new Map();
  for (const source of sources) {
    if (!source || typeof source.id !== 'string' || source.id.length === 0) continue;
    byId.set(source.id, source.id);
    for (const feed of [source.url, source.channel_url, source.feedUrl]) {
      if (typeof feed === 'string' && feed.length > 0) byFeed.set(feed, source.id);
    }
    const name = firstString(source.display_name, source.name).toLocaleLowerCase('en');
    if (name) byName.set(name, source.id);
  }
  if (!week || typeof week !== 'object') return counts;
  const lists = SOURCE_SECTIONS.map((section) => week.topics?.[section.id]);
  lists.push(week.footer_aside);
  for (const list of lists) {
    if (!Array.isArray(list)) continue;
    for (const item of list) {
      const id = matchSourceItem(item, byId, byFeed, byName);
      if (!id) continue;
      counts.set(id, (counts.get(id) ?? 0) + 1);
    }
  }
  return counts;
}
