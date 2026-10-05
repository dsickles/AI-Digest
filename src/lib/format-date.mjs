const TIME_ZONE = 'America/New_York';
const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

const monthDayYear = new Intl.DateTimeFormat('en-US', {
  timeZone: TIME_ZONE,
  month: 'short',
  day: 'numeric',
  year: 'numeric',
});

const monthDay = new Intl.DateTimeFormat('en-US', {
  timeZone: TIME_ZONE,
  month: 'short',
  day: 'numeric',
});

const yearOnly = new Intl.DateTimeFormat('en-US', {
  timeZone: TIME_ZONE,
  year: 'numeric',
});

// A date with no time is that calendar date. Noon UTC stays on the same date in New York.
function readerInstant(iso) {
  const match = DATE_ONLY.exec(iso);
  if (!match) return new Date(iso);
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  return new Date(Date.UTC(year, month - 1, day, 12));
}

export function formatDate(iso) {
  return monthDayYear.format(readerInstant(iso));
}

export function formatWeekRange(weekStart, weekEnd) {
  const startYear = yearOnly.format(readerInstant(weekStart));
  const endYear = yearOnly.format(readerInstant(weekEnd));
  const startLabel = startYear === endYear ? monthDay.format(readerInstant(weekStart)) : formatDate(weekStart);
  return `Week of ${startLabel} – ${formatDate(weekEnd)}`;
}
