import type { Topic } from './topics';

/** Permalink for an archived week Briefing or topic tab (D-A3b-extras). */
export function canonicalDigestUrl(weekId: string, topic?: Topic): string {
  const slug = weekId.toLowerCase();
  if (topic) {
    return `/digest/${slug}/${topic}`;
  }
  return `/digest/${slug}`;
}
