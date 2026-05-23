import type { CollectionEntry } from 'astro:content';

/** First sentence of weekly synthesis, or top-1 briefing title (D-A6d). */
export function archiveExcerpt(digest: CollectionEntry<'digests'>): string {
  const text = digest.data.weekly_synthesis.text?.trim();
  if (text) {
    const match = text.match(/^[^.!?]+[.!?]/);
    if (match) {
      return match[0].trim();
    }
    const line = text.split('\n')[0]?.trim();
    if (line) {
      return line;
    }
  }
  return digest.data.briefing_top_n[0]?.title ?? '';
}
