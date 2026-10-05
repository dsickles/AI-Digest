import { basename } from 'node:path';
import { isPublishedWeek, readerNow, selectLatestPublished } from './week-rules.mjs';

export const TOPICS = ['edtech', 'business', 'technical', 'policy-and-safety'] as const;

export type Topic = (typeof TOPICS)[number];

export const TOPIC_LABELS: Record<Topic, string> = {
  edtech: 'Education',
  business: 'Business',
  technical: 'Technical',
  'policy-and-safety': 'Policy and Safety',
};

export const DEGRADED_BODY = "The summary couldn't be generated this week.";

const TIME_ZONE = 'America/New_York';

export interface Publisher {
  source_id: string;
  name: string;
}

export interface MainCard {
  id: string;
  title: string;
  url: string;
  publisher: Publisher;
  published_at: string;
  category: Topic;
  media: 'article' | 'video';
  summary_status:
    | 'ok'
    | 'quota_exhausted'
    | 'api_error'
    | 'parse_error'
    | 'client_init_error'
    | 'transcript_missing'
    | 'deferred_budget';
  summary?: string;
  body?: string;
}

export interface ThinCard {
  id: string;
  title: string;
  url: string;
  publisher: Publisher;
  published_at: string;
  category: Topic;
  media: 'article';
  summary_status: 'thin';
}

export interface Week {
  schema_version: 1;
  week_id: string;
  timezone: typeof TIME_ZONE;
  week_start: string;
  week_end: string;
  generated_at: string;
  briefing: {
    synthesis: string;
    top: MainCard[];
  };
  topics: Record<Topic, MainCard[]>;
  main_feed: MainCard[];
  footer_aside: ThinCard[];
}

type WeekModule = { default: Week };

const weekModules = import.meta.glob('../../content/digests/*.json', {
  eager: true,
}) as Record<string, WeekModule>;

function assertWeek(value: unknown, filePath: string): Week {
  if (!value || typeof value !== 'object') {
    throw new Error(`${filePath} is not a week object`);
  }
  const week = value as Week;
  if (week.schema_version !== 1) {
    throw new Error(`${filePath} schema_version must be 1`);
  }
  if (basename(filePath, '.json') !== week.week_id) {
    throw new Error(`${filePath} does not match week_id ${week.week_id}`);
  }
  if (!week.briefing || typeof week.briefing.synthesis !== 'string' || !Array.isArray(week.briefing.top)) {
    throw new Error(`${filePath} briefing is incomplete`);
  }
  if (!week.topics || !Array.isArray(week.footer_aside)) {
    throw new Error(`${filePath} is missing topic lists or the footer`);
  }
  if (week.topics['policy-and-safety'] === undefined) {
    week.topics['policy-and-safety'] = [];
  }
  for (const topic of TOPICS) {
    if (!Array.isArray(week.topics[topic])) {
      throw new Error(`${filePath} topics.${topic} must be a list`);
    }
  }
  return week;
}

export function loadWeeks(): Week[] {
  const weeks = Object.entries(weekModules).map(([filePath, mod]) => assertWeek(mod.default, filePath));
  weeks.sort((a, b) => b.week_id.localeCompare(a.week_id));
  const seen = new Set<string>();
  for (const week of weeks) {
    if (seen.has(week.week_id)) {
      throw new Error(`duplicate week_id ${week.week_id}`);
    }
    seen.add(week.week_id);
  }
  return weeks;
}

export function publishedWeeks(): Week[] {
  const now = readerNow();
  return loadWeeks().filter((week) => isPublishedWeek(week, now));
}

export function latestWeek(): Week | undefined {
  return selectLatestPublished(loadWeeks(), readerNow());
}

export function weekPath(weekId: string, view: 'briefing' | Topic): string {
  if (view === 'briefing') return `/digest/${weekId}`;
  return `/digest/${weekId}/${view}`;
}

export function latestPath(view: 'briefing' | Topic): string {
  if (view === 'briefing') return '/';
  return `/${view}`;
}

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

export function formatDate(iso: string): string {
  return monthDayYear.format(new Date(iso));
}

export function formatWeekRange(weekStart: string, weekEnd: string): string {
  const startYear = yearOnly.format(new Date(weekStart));
  const endYear = yearOnly.format(new Date(weekEnd));
  const startLabel = startYear === endYear ? monthDay.format(new Date(weekStart)) : formatDate(weekStart);
  return `Week of ${startLabel} – ${formatDate(weekEnd)}`;
}

export function synthesisExcerpt(synthesis: string): string {
  const trimmed = synthesis.trim();
  const match = trimmed.match(/^.+?[.!?](?=\s|$)/);
  return match ? match[0] : trimmed;
}

export function isTopic(value: string): value is Topic {
  return (TOPICS as readonly string[]).includes(value);
}
