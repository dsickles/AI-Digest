import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { describe, expect, it } from 'vitest';
import WeekBody from '../../src/components/WeekBody.astro';
import { goodWeek, validRanking } from '../helpers.mjs';

async function renderBriefing(week) {
  const container = await AstroContainer.create();
  return container.renderToString(WeekBody, { props: { week, view: 'briefing' } });
}

describe('Top 5 on the Briefing', () => {
  it('shows each story with its rank and its reason when the week is ranked', async () => {
    const week = goodWeek();
    week.briefing.ranking = validRanking(week);
    const html = await renderBriefing(week);
    week.briefing.ranking.forEach((row, index) => {
      expect(html).toContain(`Why #${index + 1}</span> ${row.reason}`);
    });
    const order = week.briefing.top.map((card) => html.indexOf(`id="${card.id}"`));
    expect(order.every((at, index) => at > -1 && (index === 0 || at > order[index - 1]))).toBe(true);
  });

  it('shows no reason line for a week without a ranking', async () => {
    const week = goodWeek();
    delete week.briefing.ranking;
    const html = await renderBriefing(week);
    expect(html).not.toContain('rank-why');
  });
});
