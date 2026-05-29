import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const alsoCoveredSchema = z.object({
  display_name: z.string(),
  url: z.string().url(),
});

const digestCardSchema = z.object({
  title: z.string(),
  publisher: z.string(),
  canonical_url: z.string().url(),
  published_at: z.string(),
  tldr: z.string().nullable(),
  summary_status: z.string().nullable(),
  source_type: z.string().default('rss'),
  also_covered: z.array(alsoCoveredSchema).default([]),
  category: z.enum(['edtech', 'business', 'technical']).nullable(),
  rank_position: z.number().int().nullable(),
  degraded_body: z.string().nullable().optional(),
  channel_url: z.string().url().nullable().optional(),
});

const categorySectionSchema = z.object({
  mini_rollup: z.string().nullable(),
  cards: z.array(digestCardSchema),
});

const pipelineNotesSchema = z.object({
  show: z.boolean().default(true),
  summary_line: z.string(),
  details: z.array(z.string()).default([]),
});

const failureNoticeSchema = z.object({
  kind: z.string(),
  body: z.string(),
});

const digests = defineCollection({
  loader: glob({ base: './src/content/digests', pattern: '**/*.json' }),
  schema: z.object({
    schema_version: z.literal(1),
    week_id: z.string(),
    generated_at: z.string(),
    week_range: z.object({
      start: z.string(),
      end: z.string(),
    }),
    updated_at: z.string(),
    weekly_synthesis: z.object({
      text: z.string().nullable(),
      status: z.string(),
    }),
    briefing_top_n: z.array(digestCardSchema),
    category_sections: z.object({
      edtech: categorySectionSchema,
      business: categorySectionSchema,
      technical: categorySectionSchema,
    }),
    main_feed: z.array(digestCardSchema),
    footer_aside: z.array(digestCardSchema),
    pending_transcripts_count: z.number().int().nonnegative().default(0),
    pipeline_notes: pipelineNotesSchema.nullable().optional(),
    failure_notice: failureNoticeSchema.nullable().optional(),
  }),
});

// Phase 5 plan 05-03: budget block carries the two reader-banner
// inputs (hard_cap_hit, deferred_items_count) plus the existing
// halt/cap fields. We tighten the schema from a permissive
// `z.record` so Astro fails the build when the pipeline emits a
// report missing either field — that's the contract OBS-03's
// StatusBanner depends on.
const budgetSchema = z.object({
  cap_usd: z.number().nonnegative(),
  reserved_meta_usd: z.number().nonnegative(),
  spent_usd: z.number().nonnegative(),
  pre_flight_estimate_usd: z.number().nonnegative().optional(),
  halted: z.boolean(),
  halted_at_stage: z.string().nullable(),
  hard_cap_hit: z.boolean(),
  deferred_items_count: z.number().int().nonnegative(),
});

const reports = defineCollection({
  loader: glob({ base: './src/content/reports', pattern: '**/*.json' }),
  schema: z.object({
    schema_version: z.literal(1),
    week_id: z.string(),
    generated_at: z.string(),
    run_id: z.string(),
    status: z.string(),
    items_ingested: z.number(),
    clusters: z.number(),
    llm_calls: z.number(),
    cost_usd: z.number(),
    errors: z.array(z.unknown()),
    summary_status: z.record(z.string(), z.number()),
    stages: z.record(z.string(), z.unknown()),
    source_health: z.record(z.string(), z.unknown()),
    budget: budgetSchema,
  }),
});

export const collections = { digests, reports };
