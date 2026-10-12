// Also seen is the thin-link list on Briefing. Version bumps and quote-only
// posts stay out, even when a later week file puts them in footer_aside.

const VERSION_REASON =
  /\b(?:minor version|version release|version bump|minor release|minor alpha|alpha release|patch release)\b/i;
const PACKAGE_VERSION_TITLE =
  /^[\w][\w.+-]*(?:\/[\w.+-]+)?(?:\s+[\w.+-]+)*\s+v?\d+\.\d+(?:\.\d+)?[a-z]?\d*$/i;
const THREE_PART_VERSION = /\b\d+\.\d+\.\d+\b/;
const LETTER_VERSION = /\b\d+\.\d+[a-z]\d*\b/i;
const QUOTE_REASON = /\b(?:quote with no commentary|quotes with no commentary|quote-only|quote only)\b/i;

export const SECTION_LABELS = {
  edtech: 'Education',
  business: 'Business',
  technical: 'Technical',
  'policy-and-safety': 'Policy and Safety',
};

export function isVersionBump(card) {
  const title = String(card?.title ?? '').trim();
  const reason = String(card?.include_reason ?? '');
  if (VERSION_REASON.test(reason)) return true;
  if (PACKAGE_VERSION_TITLE.test(title)) return true;
  if (LETTER_VERSION.test(title)) return true;
  if (THREE_PART_VERSION.test(title)) return true;
  return false;
}

export function isQuoteOnly(card) {
  const title = String(card?.title ?? '').trim();
  const reason = String(card?.include_reason ?? '');
  if (/^quoting\b/i.test(title)) return true;
  if (QUOTE_REASON.test(reason)) return true;
  return false;
}

export function alsoSeenFillerKind(card) {
  if (isVersionBump(card)) return 'version-bump';
  if (isQuoteOnly(card)) return 'quote-only';
  return null;
}

export function visibleAlsoSeen(cards) {
  return (Array.isArray(cards) ? cards : []).filter(
    (card) => card && card.included !== false && !alsoSeenFillerKind(card),
  );
}

export function alsoSeenFillerErrors(doc) {
  const errors = [];
  for (const card of doc?.footer_aside ?? []) {
    if (!card || typeof card !== 'object') continue;
    const kind = alsoSeenFillerKind(card);
    if (kind === 'version-bump') {
      errors.push(`${card.id ?? 'footer item'} is a version bump and must not appear in Also seen`);
    } else if (kind === 'quote-only') {
      errors.push(`${card.id ?? 'footer item'} is a quote-only post and must not appear in Also seen`);
    }
  }
  return errors;
}
