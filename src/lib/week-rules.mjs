const TIME_ZONE = 'America/New_York';
const TOPICS = ['edtech', 'business', 'technical'];
const WEEKDAY_INDEX = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };

export function isoWeekId(year, month, day) {
  const date = new Date(Date.UTC(year, month - 1, day));
  const dayNum = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - dayNum);
  const isoYear = date.getUTCFullYear();
  const yearStart = new Date(Date.UTC(isoYear, 0, 1));
  const week = Math.ceil(((date - yearStart) / 86400000 + 1) / 7);
  return `${isoYear}-W${String(week).padStart(2, '0')}`;
}

export function newYorkParts(iso) {
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) return null;
  const formatted = new Intl.DateTimeFormat('en-US', {
    timeZone: TIME_ZONE,
    weekday: 'short',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(instant);
  const parts = Object.fromEntries(
    formatted.filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]),
  );
  return {
    weekday: parts.weekday,
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    hour: Number(parts.hour),
    minute: Number(parts.minute),
    second: Number(parts.second),
  };
}

// Digest weeks run Sunday 00:00 through Saturday 23:59:59 America/New_York.
// week_id is the ISO week of that Saturday, not the ISO week of the Sunday.
export function digestWeekId(iso) {
  const parts = newYorkParts(iso);
  const index = parts ? WEEKDAY_INDEX[parts.weekday] : undefined;
  if (index === undefined) return null;
  const daysUntilSaturday = (6 - index + 7) % 7;
  const saturday = new Date(Date.UTC(parts.year, parts.month - 1, parts.day + daysUntilSaturday));
  return isoWeekId(saturday.getUTCFullYear(), saturday.getUTCMonth() + 1, saturday.getUTCDate());
}

export function isCompleteWeek(week) {
  if (!week?.briefing || typeof week.briefing.synthesis !== 'string') return false;
  if (week.briefing.synthesis.trim().length === 0) return false;
  if (!Array.isArray(week.briefing.top) || week.briefing.top.length !== 5) return false;
  if (!week.topics) return false;
  return TOPICS.every((topic) => Array.isArray(week.topics[topic]));
}

export function isPublishedWeek(week, now) {
  if (!isCompleteWeek(week)) return false;
  const end = Date.parse(week.week_end);
  if (Number.isNaN(end)) return false;
  return end <= now.getTime();
}

export function selectLatestPublished(weeks, now) {
  return weeks
    .filter((week) => isPublishedWeek(week, now))
    .sort((left, right) => String(right.week_id).localeCompare(String(left.week_id)))[0];
}

export function readerNow(env = process.env) {
  const raw = env.DIGEST_AS_OF;
  if (typeof raw === 'string' && raw.length > 0) {
    const parsed = new Date(raw);
    if (!Number.isNaN(parsed.getTime())) return parsed;
  }
  return new Date();
}
