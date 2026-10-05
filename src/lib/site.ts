export const SITE_TITLE = "Dan's AI Digest";

export function documentTitle(...parts: string[]): string {
  const extra = parts.filter((part) => part.length > 0);
  return extra.length === 0 ? SITE_TITLE : `${SITE_TITLE}: ${extra.join(": ")}`;
}
