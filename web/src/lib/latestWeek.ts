import { getCollection, type CollectionEntry } from 'astro:content';

export type DigestEntry = CollectionEntry<'digests'>;

/** Newest ISO week from the digests collection (lexicographic sort on YYYY-Www). */
export async function getLatestDigest(): Promise<DigestEntry> {
  const digests = await getCollection('digests');
  if (digests.length === 0) {
    throw new Error('No digest entries in content collection');
  }
  const sorted = [...digests].sort((a, b) =>
    b.data.week_id.localeCompare(a.data.week_id),
  );
  return sorted[0]!;
}
