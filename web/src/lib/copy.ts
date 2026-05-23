/** Reader-surface copy — mirrors pipeline/render/partition.py (D-24). */
export const BRIEFING_HEADER_TEMPLATE = 'Briefing — Top {n} this week';

export const WEEKLY_ROLLUP_FAILURE_COPY =
  "This week's narrative roll-up couldn't be generated. The Top {n} stories are below.";

export function formatBriefingHeader(topN: number): string {
  return BRIEFING_HEADER_TEMPLATE.replace('{n}', String(topN));
}

export function formatWeeklyRollupFailure(topN: number): string {
  return WEEKLY_ROLLUP_FAILURE_COPY.replace('{n}', String(topN));
}
