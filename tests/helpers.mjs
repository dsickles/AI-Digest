import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { selectLatestPublished } from '../src/lib/week-rules.mjs';

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const DIGESTS = join(ROOT, 'content', 'digests');

export function weekFiles() {
  return readdirSync(DIGESTS)
    .filter((name) => name.endsWith('.json'))
    .sort();
}

export function readWeek(name) {
  return JSON.parse(readFileSync(join(DIGESTS, name), 'utf8'));
}

// The newest week that has ended. The built site shows this one on the home page.
export function latestWeek() {
  return selectLatestPublished(weekFiles().map(readWeek), new Date());
}

// A copy of the newest committed week, for fixtures that change one thing.
export function goodWeek() {
  return structuredClone(latestWeek());
}

export function distinctSources(card) {
  const ids = new Set([card.publisher.source_id, ...(card.also_covered ?? []).map((link) => link.publisher.source_id)]);
  return Math.min(3, ids.size);
}

// A ranking that the validator accepts: Top 5 in file order, scored so each row
// sits at or below the one above it.
export function validRanking(week) {
  return week.briefing.top.map((card, index) => ({
    story_id: card.id,
    importance: 3 - Math.min(index, 3),
    sources: distinctSources(card),
    novelty: 1,
    reason: `It ranks at number ${index + 1} because it matters most after the stories above it.`,
  }));
}
