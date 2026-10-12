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

export function compareSourceNames(left, right) {
  return left.localeCompare(right, 'en', { sensitivity: 'base', numeric: true });
}

export function sourceTypeLabel(type) {
  if (type === 'rss') return 'RSS';
  if (type === 'youtube') return 'YouTube';
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

function citeSource(counts, seen, sourceId, url) {
  if (typeof sourceId !== 'string' || sourceId.length === 0) return;
  const key = `${sourceId}\n${typeof url === 'string' ? url : ''}`;
  if (seen.has(key)) return;
  seen.add(key);
  counts.set(sourceId, (counts.get(sourceId) ?? 0) + 1);
}

// Items cited from each source in one week file. A story that also appears in
// the Top 5 or main_feed counts once. An also_covered link counts for its own
// publisher. Excluded items are left out.
export function countSourceReferences(week) {
  const counts = new Map();
  if (!week || typeof week !== 'object') return counts;
  const seenItems = new Set();
  const seenCitations = new Set();
  const lists = [
    week.briefing?.top,
    ...Object.values(week.topics ?? {}),
    week.main_feed,
    week.footer_aside,
  ];
  for (const list of lists) {
    if (!Array.isArray(list)) continue;
    for (const card of list) {
      if (!card || typeof card !== 'object') continue;
      if (typeof card.id === 'string') {
        if (seenItems.has(card.id)) continue;
        seenItems.add(card.id);
      }
      citeSource(counts, seenCitations, card.publisher?.source_id, card.url);
      if (!Array.isArray(card.also_covered)) continue;
      for (const extra of card.also_covered) {
        citeSource(counts, seenCitations, extra?.publisher?.source_id, extra?.url);
      }
    }
  }
  return counts;
}
