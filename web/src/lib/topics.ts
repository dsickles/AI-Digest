/** Topic slugs and labels — mirrors pipeline/render/partition.py CATEGORY_ORDER / CATEGORY_LABELS. */
export const TOPICS = ['edtech', 'business', 'technical'] as const;

export type Topic = (typeof TOPICS)[number];

export const TOPIC_LABELS: Record<Topic, string> = {
  edtech: 'Edtech',
  business: 'Business',
  technical: 'Technical',
};

export function isTopic(value: string): value is Topic {
  return (TOPICS as readonly string[]).includes(value);
}
