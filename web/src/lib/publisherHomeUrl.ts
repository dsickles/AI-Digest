/**
 * Resolve the "publisher home page" URL for a card.
 *
 * Preference order:
 *   1. `channelUrl` from the digest JSON — populated by ingestion from
 *      `sources.channel_url` (YouTube: derived from `channel_id`; RSS:
 *      optional `home_url` in `sources.yaml`).
 *   2. Origin of `canonicalUrl` (scheme + host). Works well for blogs / RSS
 *      where the canonical story URL's host IS the publisher front page.
 *
 * Returns null when neither source yields a usable URL — caller should fall
 * back to rendering publisher as plain text.
 */
export function publisherHomeUrl(
  canonicalUrl: string | undefined | null,
  sourceType: string | undefined | null,
  channelUrl?: string | undefined | null,
): string | null {
  if (channelUrl) return channelUrl;

  if (!canonicalUrl) return null;

  // Without an explicit channel_url, deriving from canonical_url for YouTube
  // would just land on youtube.com — keep returning null so the badge stays
  // as plain text rather than offering a misleading link.
  if (sourceType === 'youtube') return null;

  try {
    const url = new URL(canonicalUrl);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    return `${url.protocol}//${url.host}/`;
  } catch {
    return null;
  }
}
