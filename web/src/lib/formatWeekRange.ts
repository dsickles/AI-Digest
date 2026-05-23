const MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const;

function dayLabel(iso: string): string {
  const d = new Date(iso);
  const month = MONTHS[d.getUTCMonth()]!;
  return `${month} ${d.getUTCDate()}`;
}

/** D-18: ``Week of May 18 – May 24, 2026`` from ISO8601 week bounds. */
export function formatWeekRange(startIso: string, endIso: string): string {
  const end = new Date(endIso);
  return `Week of ${dayLabel(startIso)} – ${dayLabel(endIso)}, ${end.getUTCFullYear()}`;
}

/** Card meta row date (YYYY-MM-DD). */
export function formatPublishedDate(iso: string): string {
  return iso.slice(0, 10);
}

/** Header ``Updated {ISO8601}`` line. */
export function formatUpdated(iso: string): string {
  return `Updated ${iso}`;
}
