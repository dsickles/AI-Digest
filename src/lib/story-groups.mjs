const TRACKING_PARAMS = new Set(['gclid', 'fbclid', 'ref', 'mc_cid', 'mc_eid']);

// Same story can arrive under trivial URL variants. Compare those as one link.
export function canonicalStoryUrl(url) {
  if (typeof url !== 'string' || url.length === 0) return '';
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return url;
  }
  parsed.hash = '';
  const host = parsed.hostname.toLowerCase().replace(/^www\./, '');
  const path = parsed.pathname.replace(/\/+$/, '') || '/';
  const params = [...parsed.searchParams.entries()].filter(([key]) => {
    const name = key.toLowerCase();
    return !name.startsWith('utm_') && !TRACKING_PARAMS.has(name);
  });
  params.sort((left, right) => left[0].localeCompare(right[0]) || left[1].localeCompare(right[1]));
  const search = new URLSearchParams(params).toString();
  return `${parsed.protocol}//${host}${path}${search ? `?${search}` : ''}`;
}

export function publisherLabels(name) {
  const full = String(name ?? '').trim();
  if (full.length === 0) return [];
  const short = full.split(' (')[0].trim();
  if (short.length >= 4 && short !== full) return [full, short];
  return [full];
}

export function noteCitesPublisher(note, name) {
  if (typeof note !== 'string') return false;
  return publisherLabels(name).some((label) => note.includes(label));
}

function citedKeys(note, names) {
  const hits = new Set();
  for (const name of names) {
    if (!noteCitesPublisher(note, name)) continue;
    const labels = publisherLabels(name);
    hits.add(labels[labels.length - 1]);
  }
  return hits;
}

export function numberNoteErrors(card) {
  if (!card || typeof card !== 'object' || !Object.hasOwn(card, 'number_note')) return [];
  const note = card.number_note;
  const errors = [];
  const id = card.id ?? 'item';
  if (typeof note !== 'string' || note.trim().length === 0 || /[\r\n]/.test(note) || note.length > 400) {
    errors.push(`${id} number_note must be one non-empty line of at most 400 characters`);
  }
  const links = Array.isArray(card.also_covered) ? card.also_covered : [];
  if (links.length === 0) {
    errors.push(`${id} number_note needs at least one also covered source`);
    return errors;
  }
  if (typeof note !== 'string') return errors;
  const names = [card.publisher?.name, ...links.map((link) => link?.publisher?.name)].filter(
    (name) => typeof name === 'string' && name.length > 0,
  );
  if (citedKeys(note, names).size < 2) {
    errors.push(`${id} number_note must name at least two publishers on the item`);
  }
  return errors;
}

function claimUrl(seen, errors, url, role, id) {
  const key = canonicalStoryUrl(url);
  if (!key) return;
  const prev = seen.get(key);
  if (!prev) {
    seen.set(key, { role, id });
    return;
  }
  const roles = [prev.role, role];
  const alsoSeen = roles.includes('also-seen');
  const onMainItem = roles.includes('main') || roles.includes('also-covered');
  if (alsoSeen && onMainItem) {
    errors.push(`${url} appears both as a main item and as an Also seen link`);
    return;
  }
  errors.push(`${url} is listed more than once (${prev.role}: ${prev.id}; ${role}: ${id})`);
}

export function storyPlacementErrors(doc) {
  const errors = [];
  const seen = new Map();
  const lists = [
    ['main', doc?.main_feed],
    ['also-seen', doc?.footer_aside],
    ['excluded', doc?.excluded],
  ];
  for (const [role, cards] of lists) {
    if (!Array.isArray(cards)) continue;
    for (const card of cards) {
      if (!card || typeof card !== 'object') continue;
      claimUrl(seen, errors, card.url, role, card.id ?? role);
    }
  }
  const cards = [...(doc?.main_feed ?? []), ...(doc?.footer_aside ?? []), ...(doc?.excluded ?? [])];
  for (const card of cards) {
    if (!card || typeof card !== 'object' || !Array.isArray(card.also_covered)) continue;
    card.also_covered.forEach((link, index) => {
      claimUrl(seen, errors, link?.url, 'also-covered', `${card.id ?? 'item'} also covered ${index + 1}`);
    });
  }
  return errors;
}
