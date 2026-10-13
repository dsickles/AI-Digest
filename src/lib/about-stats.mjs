const COUNT_WORDS = ['Zero', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten'];

// Counts for How it works. Stories are main_feed. Merged in is the also_covered
// links on those stories (topics repeat the same cards, so they are not added
// again). Also seen is footer_aside. Left out is excluded.
export function aboutCounts(week) {
  const main = Array.isArray(week?.main_feed) ? week.main_feed : [];
  const aside = Array.isArray(week?.footer_aside) ? week.footer_aside : [];
  const excluded = Array.isArray(week?.excluded) ? week.excluded : [];
  const stories = main.length;
  const merged = main.reduce(
    (sum, card) => sum + (Array.isArray(card?.also_covered) ? card.also_covered.length : 0),
    0,
  );
  const alsoSeen = aside.length;
  const leftOut = excluded.length;
  const considered = stories + merged + alsoSeen + leftOut;
  const themes = Array.isArray(week?.briefing?.themes) ? week.briefing.themes.length : 0;
  const picks = Array.isArray(week?.briefing?.top) ? week.briefing.top.length : 0;
  const rawValue = week?.briefing?.number_of_week?.value;
  const numberValue = typeof rawValue === 'string' ? rawValue : '';
  const weekMatch = /^(\d{4})-W(\d{2})$/.exec(String(week?.week_id ?? ''));
  const weekLabel = weekMatch ? `W${weekMatch[2]}` : '';
  return { stories, merged, alsoSeen, leftOut, considered, themes, picks, numberValue, weekLabel };
}

export function countWord(count) {
  if (Number.isInteger(count) && count >= 0 && count < COUNT_WORDS.length) return COUNT_WORDS[count];
  return String(count);
}

export function joinAnd(items) {
  const names = items.filter((item) => typeof item === 'string' && item.length > 0);
  if (names.length === 0) return '';
  if (names.length === 1) return names[0];
  if (names.length === 2) return `${names[0]} and ${names[1]}`;
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

// "Education Disrupted (Stefan Bauschard)" reads as "Education Disrupted" in the step.
export function shortSourceName(name) {
  const full = String(name ?? '').trim();
  const short = full.split(' (')[0].trim();
  return short.length > 0 ? short : full;
}

export function countedNoun(count, singular, plural) {
  return `${count} ${count === 1 ? singular : plural}`;
}

export function numberBadge(counts) {
  if (!counts.weekLabel) return counts.numberValue;
  if (!counts.numberValue) return counts.weekLabel;
  return `${counts.weekLabel}: ${counts.numberValue}`;
}

// Reader copy on How it works. Digits stay digits. A count inside a sentence
// uses the lowercase word, and a count that opens a sentence stays capitalized.
export function consideredLine(counts) {
  return `${countedNoun(counts.considered, 'item', 'items')} considered this week: ${countedNoun(counts.stories, 'story', 'stories')}, ${counts.merged} merged into others, ${countedNoun(counts.alsoSeen, 'short link', 'short links')}, ${counts.leftOut} left out.`;
}

export function themeCountPhrase(count) {
  return `${countWord(count).toLowerCase()} ${count === 1 ? 'theme' : 'themes'}`;
}

export function pickCountPhrase(count) {
  return `${countWord(count)} ${count === 1 ? 'full story' : 'full stories'}`;
}

export function aiOnlyLine(names) {
  if (names.length === 0) return 'Items not about AI, from the sources Dan marked AI only.';
  const noun = names.length === 1 ? 'source' : 'sources';
  return `Items not about AI, from the ${countWord(names.length).toLowerCase()} ${noun} Dan marked AI only: ${joinAnd(names)}.`;
}
