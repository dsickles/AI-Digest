export const SECTION_TAGS = ['edtech', 'business', 'technical', 'policy-and-safety'];

// These tags are the card category. business and technical stay hints:
// shipped weeks already place some of those items in another section.
export const ASSIGNED_TAGS = new Set(['edtech', 'policy-and-safety']);

const KEBAB = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const CHANNEL_ID = /^UC[A-Za-z0-9_-]{22}$/;
const AI_TEXT =
  /\b(?:ai|a\.i\.|artificial intelligence|machine learning|deep learning|neural networks?|large language models?|llms?|generative|chatbots?|chatgpt|gpt-\d[\w.-]*|openai|anthropic|claude|gemini|copilot)\b/i;

export function mentionsAi(text) {
  return AI_TEXT.test(String(text ?? ''));
}

export function cardText(card) {
  return [card?.title, card?.summary, card?.body].filter((part) => typeof part === 'string' && part.length > 0).join('\n');
}

function isHttps(url) {
  try {
    return typeof url === 'string' && new URL(url).protocol === 'https:';
  } catch {
    return false;
  }
}

export function validateSourcesDocument(doc) {
  const errors = [];
  if (!doc || typeof doc !== 'object' || !Array.isArray(doc.sources)) {
    return ['sources.yaml must contain a sources list'];
  }
  const seen = new Set();
  const allowed = new Set([
    'id',
    'type',
    'url',
    'home_url',
    'channel_id',
    'channel_url',
    'display_name',
    'tag',
    'ai_only',
    'enabled',
  ]);
  doc.sources.forEach((source, index) => {
    const where = `sources[${index}]`;
    if (!source || typeof source !== 'object' || Array.isArray(source)) {
      errors.push(`${where} must be a source`);
      return;
    }
    for (const key of Object.keys(source)) {
      if (!allowed.has(key)) errors.push(`${where} has unknown field ${key}`);
    }
    if (typeof source.id !== 'string' || !KEBAB.test(source.id)) {
      errors.push(`${where} id must be kebab-case`);
    } else if (seen.has(source.id)) {
      errors.push(`${where} duplicates id ${source.id}`);
    } else {
      seen.add(source.id);
    }
    if (typeof source.display_name !== 'string' || source.display_name.trim().length === 0) {
      errors.push(`${where} display_name is required`);
    }
    if (!SECTION_TAGS.includes(source.tag)) {
      errors.push(`${where} tag must be one of ${SECTION_TAGS.join(', ')}`);
    }
    if (typeof source.enabled !== 'boolean') {
      errors.push(`${where} enabled must be true or false`);
    }
    if (source.ai_only !== undefined && typeof source.ai_only !== 'boolean') {
      errors.push(`${where} ai_only must be true or false`);
    }
    if (source.type === 'rss') {
      if (!isHttps(source.url)) errors.push(`${where} url must be an https feed`);
      if (source.home_url !== undefined && !isHttps(source.home_url)) {
        errors.push(`${where} home_url must be an https URL`);
      }
      if (source.channel_id !== undefined || source.channel_url !== undefined) {
        errors.push(`${where} rss sources do not use channel_id or channel_url`);
      }
    } else if (source.type === 'youtube') {
      if (typeof source.channel_id !== 'string' || !CHANNEL_ID.test(source.channel_id)) {
        errors.push(`${where} channel_id must be a YouTube UC id`);
      }
      if (source.channel_url !== undefined && !isHttps(source.channel_url)) {
        errors.push(`${where} channel_url must be an https URL`);
      }
      if (source.url !== undefined || source.home_url !== undefined) {
        errors.push(`${where} youtube sources do not use url or home_url`);
      }
    } else {
      errors.push(`${where} type must be rss or youtube`);
    }
  });
  return errors;
}

export function sourcePlacementErrors(card, source, where) {
  const errors = [];
  if (!source) return errors;
  if (ASSIGNED_TAGS.has(source.tag) && card.category !== source.tag) {
    errors.push(
      `${where} must use category ${source.tag} so source ${card.publisher?.source_id} stays on that section`,
    );
  }
  if (source.aiOnly && !mentionsAi(cardText(card))) {
    errors.push(`${where} is not about AI, so it stays out of the digest`);
  }
  return errors;
}
