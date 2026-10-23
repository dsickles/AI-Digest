export const SITE_TITLE = "Dan's AI Digest";

// Link previews need absolute URLs. Kept here rather than as Astro's `site`
// setting, which would also make the redirect pages' canonical links absolute.
export const SITE_URL = 'https://dans-ai-digest.vercel.app';

export function documentTitle(...parts: string[]): string {
  const extra = parts.filter((part) => part.length > 0);
  return extra.length === 0 ? SITE_TITLE : `${SITE_TITLE}: ${extra.join(": ")}`;
}
