import { describe, expect, it } from 'vitest';
import { loadSources, validateDigestDocument, validateRanking } from '../../scripts/validate-weeks.mjs';
import { distinctSources, goodWeek, readWeek, validRanking, weekFiles } from '../helpers.mjs';

const sources = loadSources();

function errorsFor(week) {
  return validateDigestDocument(week, `${week.week_id}.json`, sources);
}

describe('committed weeks', () => {
  it.each(weekFiles())('%s passes the schema and every rule', (name) => {
    expect(validateDigestDocument(readWeek(name), name, sources)).toEqual([]);
  });
});

describe('bad week files fail with a clear message', () => {
  const cases = [
    {
      name: 'a Top 5 with only four stories',
      change: (week) => week.briefing.top.pop(),
      message: /briefing\/top.*fewer than 5 items/,
    },
    {
      name: 'a missing week_id',
      change: (week) => delete week.week_id,
      message: /week_id/,
    },
    {
      name: 'a file named for a different week',
      filename: '2026-W01.json',
      change: () => {},
      message: /filename must be/,
    },
    {
      name: 'a Top 5 story that is not in the main feed',
      change: (week) => {
        week.briefing.top[0] = { ...week.briefing.top[0], id: 'not-in-the-week' };
      },
      message: /briefing top not-in-the-week is not in main_feed/,
    },
    {
      name: 'topic lists that do not add up to the main feed',
      change: (week) => week.main_feed.reverse(),
      message: /main_feed must equal topics/,
    },
    {
      name: 'a lead with no themes',
      change: (week) => delete week.briefing.themes,
      message: /lead of 1 to 3 sentences and exactly 5 themes/,
    },
    {
      name: 'a story dated outside the week',
      change: (week) => {
        const card = week.main_feed.at(-1);
        card.published_at = '2020-01-01T00:00:00Z';
        for (const list of [...Object.values(week.topics), week.briefing.top]) {
          const copy = list.find((item) => item.id === card.id);
          if (copy) copy.published_at = card.published_at;
        }
      },
      message: /published_at is outside the week window/,
    },
  ];

  it.each(cases)('$name', ({ change, filename, message }) => {
    const week = goodWeek();
    change(week);
    const errors = validateDigestDocument(week, filename ?? `${week.week_id}.json`, sources);
    expect(errors.join('\n')).toMatch(message);
  });
});

describe('Top 5 ranking', () => {
  it('is optional', () => {
    const week = goodWeek();
    delete week.briefing.ranking;
    expect(validateRanking(week)).toEqual([]);
  });

  it('accepts a ranking that follows the rubric', () => {
    const week = goodWeek();
    week.briefing.ranking = validRanking(week);
    expect(errorsFor(week)).toEqual([]);
  });

  it('rejects a row that names a different story than the Top 5 at that rank', () => {
    const week = goodWeek();
    week.briefing.ranking = validRanking(week);
    week.briefing.ranking[0].story_id = week.briefing.top[1].id;
    expect(validateRanking(week).join('\n')).toMatch(/ranking row 1 is .* but Top 5 story 1 is/);
  });

  it('rejects a lower-scored story above a higher-scored one', () => {
    const week = goodWeek();
    week.briefing.ranking = validRanking(week);
    week.briefing.ranking[1].importance = 3;
    week.briefing.ranking[0].importance = 2;
    expect(validateRanking(week).join('\n')).toMatch(/ranking row 2 .* outranks row 1/);
  });

  it('lets sources break a tie on importance', () => {
    const week = goodWeek();
    const tied = (cards) =>
      cards.map((card) => ({ ...validRanking(week).find((row) => row.story_id === card.id), importance: 2, novelty: 0 }));
    week.briefing.top.sort((left, right) => distinctSources(right) - distinctSources(left));
    week.briefing.ranking = tied(week.briefing.top);
    expect(validateRanking(week)).toEqual([]);

    week.briefing.top.reverse();
    week.briefing.ranking = tied(week.briefing.top);
    expect(validateRanking(week).join('\n')).toMatch(/outranks/);
  });

  it('rejects a source count that does not match the card', () => {
    const week = goodWeek();
    week.briefing.ranking = validRanking(week);
    const row = week.briefing.ranking[0];
    row.sources = row.sources === 3 ? 2 : row.sources + 1;
    expect(validateRanking(week).join('\n')).toMatch(/ranking row 1 .* counts \d sources; the card has \d/);
  });

  it('rejects a reason that is not one short sentence', () => {
    const week = goodWeek();
    week.briefing.ranking = validRanking(week);
    week.briefing.ranking[2].reason = 'First sentence. Second sentence.';
    week.briefing.ranking[3].reason = 'It ranks here — for a reason.';
    week.briefing.ranking[4].reason = `${'word '.repeat(30).trim()}.`;
    const errors = validateRanking(week).join('\n');
    expect(errors).toMatch(/ranking row 3 reason must be one sentence/);
    expect(errors).toMatch(/ranking row 4 reason must not use an em dash/);
    expect(errors).toMatch(/ranking row 5 reason must be 25 words or fewer/);
  });

  it('rejects a ranking with the wrong number of rows through the schema', () => {
    const week = goodWeek();
    week.briefing.ranking = validRanking(week).slice(0, 4);
    expect(errorsFor(week).join('\n')).toMatch(/briefing\/ranking.*fewer than 5 items/);
  });
});
